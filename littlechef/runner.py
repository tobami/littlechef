#Copyright 2010-2014 Miquel Torres <tobami@gmail.com>
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.
#
"""LittleChef: Configuration Management using Chef Solo"""
import ConfigParser
import os
import sys
import json

from fabric.api import *
from fabric.contrib.console import confirm
from paramiko.config import SSHConfig as _SSHConfig

import littlechef
from littlechef import solo, lib, chef

# Fabric settings
import fabric
fabric.state.output['running'] = False
env.loglevel = littlechef.loglevel
env.verbose = littlechef.verbose
env.abort_on_prompts = littlechef.noninteractive
env.chef_environment = littlechef.chef_environment
env.node_work_path = littlechef.node_work_path

if littlechef.concurrency:
    env.output_prefix = True
    env.parallel = True
    env.pool_size = littlechef.concurrency
else:
    env.output_prefix = False

__testing__ = False


@hosts('setup')
def new_kitchen():
    """Create LittleChef directory structure (Kitchen)"""
    def _mkdir(d, content=""):
        if not os.path.exists(d):
            os.mkdir(d)
            # Add a README so that it can be added to version control
            readme_path = os.path.join(d, 'README')
            if not os.path.exists(readme_path):
                with open(readme_path, "w") as readme:
                    print >> readme, content
            print "{0}/ directory created...".format(d)

    content = "# The /nodes directory contains your nodes as JSON files "
    content += "representing a node.\n"
    content += "# Example node file `nodes/myfqdn.json`:\n"
    data = {
        "chef_environment": "production",
        "apt": {"cacher_port": 3143},
        "run_list": ["recipe[apt]"]
    }
    content += "{0}".format(json.dumps(data, indent=2))
    _mkdir("nodes", content)
    _mkdir("roles")
    _mkdir("data_bags")
    _mkdir("environments")
    for cookbook_path in littlechef.cookbook_paths:
        _mkdir(cookbook_path)
    # Add skeleton config file
    if not os.path.exists(littlechef.CONFIGFILE):
        with open(littlechef.CONFIGFILE, 'w') as configfh:
            print >> configfh, "[userinfo]"
            print >> configfh, "user = "
            print >> configfh, "password = "
            print >> configfh, "keypair-file = "
            print >> configfh, "ssh-config = "
            print >> configfh, "encrypted_data_bag_secret = "
            print >> configfh, "[kitchen]"
            print >> configfh, "node_work_path = /tmp/chef-solo/"
            print "{0} file created...".format(littlechef.CONFIGFILE)


def nodes_with_role(rolename):
    """Configures a list of nodes that have the given role in their run list"""
    nodes = [n['name'] for n in
             lib.get_nodes_with_role(rolename, env.chef_environment)]
    if not len(nodes):
        print("No nodes found with role '{0}'".format(rolename))
        sys.exit(0)
    return node(*nodes)


def nodes_with_recipe(recipename):
    """Configures a list of nodes that have the given recipe in their run list
    """
    nodes = [n['name'] for n in
             lib.get_nodes_with_recipe(recipename, env.chef_environment)]
    if not len(nodes):
        print("No nodes found with recipe '{0}'".format(recipename))
        sys.exit(0)
    return node(*nodes)


def nodes_with_tag(tag):
    """Sets a list of nodes that have the given tag assigned and calls node()"""
    nodes = lib.get_nodes_with_tag(tag, env.chef_environment,
                                   littlechef.include_guests)
    nodes = [n['name'] for n in nodes]
    if not len(nodes):
        print("No nodes found with tag '{0}'".format(tag))
        sys.exit(0)
    return node(*nodes)


@hosts('setup')
def node(*nodes):
    """Selects and configures a list of nodes. 'all' configures all nodes"""
    chef.build_node_data_bag()
    if not len(nodes) or nodes[0] == '':
        abort('No node was given')
    elif nodes[0] == 'all':
        # Fetch all nodes and add them to env.hosts
        for node in lib.get_nodes(env.chef_environment):
            env.hosts.append(node['name'])
        if not len(env.hosts):
            abort('No nodes found in /nodes/')
        message = "Are you sure you want to configure all nodes ({0})".format(
            len(env.hosts))
        if env.chef_environment:
            message += " in the {0} environment".format(env.chef_environment)
        message += "?"
        if not __testing__:
            if not lib.global_confirm(message):
                abort('Aborted by user')
    else:
        # A list of nodes was given
        env.hosts = list(nodes)
    env.all_hosts = list(env.hosts)  # Shouldn't be needed

    # Check whether another command was given in addition to "node:"
    if not(littlechef.__cooking__ and
            'node:' not in sys.argv[-1] and
            'nodes_with_role:' not in sys.argv[-1] and
            'nodes_with_recipe:' not in sys.argv[-1] and
            'nodes_with_tag:' not in sys.argv[-1]):
        # If user didn't type recipe:X, role:Y or deploy_chef,
        # configure the nodes
        with settings():
            execute(_node_runner)
        chef.remove_local_node_data_bag()


def _configure_fabric_for_platform(platform):
    """Configures fabric for a specific platform"""
    if platform == "freebsd":
        env.shell = "/bin/sh -c"


def _node_runner():
    """This is only used by node so that we can execute in parallel"""
    env.host_string = lib.get_env_host_string()
    node = lib.get_node(env.host_string)

    _configure_fabric_for_platform(node.get("platform"))

    if __testing__:
        print "TEST: would now configure {0}".format(env.host_string)
    else:
        lib.print_header("Configuring {0}".format(env.host_string))
        chef.sync_node(node)


def deploy_chef(gems="no", ask="yes", version="0.10", distro_type=None,
                distro=None, platform=None, stop_client='yes', method=None):
    """Install chef-solo on a node"""
    env.host_string = lib.get_env_host_string()
    deprecated_parameters = [distro_type, distro, platform]
    if any(param is not None for param in deprecated_parameters) or gems != 'no':
        print("DeprecationWarning: the parameters 'gems', distro_type',"
              " 'distro' and 'platform' will no longer be supported "
              "in future versions of LittleChef. Use 'method' instead")
    if distro_type is None and distro is None:
        distro_type, distro, platform = solo.check_distro()
    elif distro_type is None or distro is None:
        abort('Must specify both or neither of distro_type and distro')
    if method:
        if method not in ['omnibus', 'gentoo', 'pacman']:
            abort('Invalid omnibus method {0}. Supported methods are '
                  'omnibus, gentoo and pacman'.format(method))
        msg = "{0} using the {1} installer".format(version, method)
    else:
        if gems == "yes":
            msg = 'using gems for "{0}"'.format(distro)
        else:
            msg = '{0} using "{1}" packages'.format(version, distro)
    if method == 'omnibus' or ask == "no" or littlechef.noninteractive:
        print("Deploying Chef {0}...".format(msg))
    else:
        message = ('\nAre you sure you want to install Chef '
                   '{0} on node {1}?'.format(msg, env.host_string))
        if not confirm(message):
            abort('Aborted by user')

    _configure_fabric_for_platform(platform)

    if not __testing__:
        solo.install(distro_type, distro, gems, version, stop_client, method)
        solo.configure()

        # Build a basic node file if there isn't one already
        # with some properties from ohai
        with settings(hide('stdout'), warn_only=True):
            output = sudo('ohai -l warn')
        if output.succeeded:
            try:
                ohai = json.loads(output)
            except ValueError:
                abort("Could not parse ohai's output"
                      ":\n  {0}".format(output))
            node = {"run_list": []}
            for attribute in ["ipaddress", "platform", "platform_family",
                              "platform_version"]:
                if ohai.get(attribute):
                    node[attribute] = ohai[attribute]
            chef.save_config(node)


def recipe(recipe):
    """Apply the given recipe to a node
    Sets the run_list to the given recipe
    If no nodes/hostname.json file exists, it creates one

    """
    env.host_string = lib.get_env_host_string()
    lib.print_header(
        "Applying recipe '{0}' on node {1}".format(recipe, env.host_string))

    # Create configuration and sync node
    data = lib.get_node(env.host_string)
    data["run_list"] = ["recipe[{0}]".format(recipe)]
    if not __testing__:
        chef.sync_node(data)


def role(role):
    """Apply the given role to a node
    Sets the run_list to the given role
    If no nodes/hostname.json file exists, it creates one

    """
    env.host_string = lib.get_env_host_string()
    lib.print_header(
        "Applying role '{0}' to {1}".format(role, env.host_string))

    # Now create configuration and sync node
    data = lib.get_node(env.host_string)
    data["run_list"] = ["role[{0}]".format(role)]
    if not __testing__:
        chef.sync_node(data)


def ssh(name):
    """Executes the given command"""
    env.host_string = lib.get_env_host_string()
    print("\nExecuting the command '{0}' on node {1}...".format(
          name, env.host_string))
    # Execute remotely using either the sudo or the run fabric functions
    with settings(hide("warnings"), warn_only=True):
        if name.startswith("sudo "):
            sudo(name[5:])
        else:
            run(name)


def plugin(name):
    """Executes the selected plugin
    Plugins are expected to be found in the kitchen's 'plugins' directory

    """
    env.host_string = lib.get_env_host_string()
    plug = lib.import_plugin(name)
    lib.print_header("Executing plugin '{0}' on "
                     "{1}".format(name, env.host_string))
    node = lib.get_node(env.host_string)
    if node == {'run_list': []}:
        node['name'] = env.host_string
    plug.execute(node)
    print("Finished executing plugin")


@hosts('api')
def list_nodes():
    """List all configured nodes"""
    lib.print_nodes(lib.get_nodes(env.chef_environment))


@hosts('api')
def list_nodes_detailed():
    """Show a detailed list of all nodes"""
    lib.print_nodes(lib.get_nodes(env.chef_environment), detailed=True)


@hosts('api')
def list_nodes_with_recipe(recipe):
    """Show all nodes which have assigned a given recipe"""
    lib.print_nodes(lib.get_nodes_with_recipe(recipe, env.chef_environment))


@hosts('api')
def list_nodes_with_role(role):
    """Show all nodes which have assigned a given role"""
    lib.print_nodes(lib.get_nodes_with_role(role, env.chef_environment))


@hosts('api')
def list_envs():
    """List all environments"""
    for env in lib.get_environments():
        margin_left = lib.get_margin(len(env['name']))
        print("{0}{1}{2}".format(
            env['name'], margin_left,
            env.get('description', '(no description)')))


@hosts('api')
def list_nodes_with_tag(tag):
    """Show all nodes which have assigned a given tag"""
    lib.print_nodes(lib.get_nodes_with_tag(tag, env.chef_environment,
                                           littlechef.include_guests))


@hosts('api')
def list_recipes():
    """Show a list of all available recipes"""
    for recipe in lib.get_recipes():
        margin_left = lib.get_margin(len(recipe['name']))
        print("{0}{1}{2}".format(
            recipe['name'], margin_left, recipe['description']))


@hosts('api')
def list_recipes_detailed():
    """Show detailed information for all recipes"""
    for recipe in lib.get_recipes():
        lib.print_recipe(recipe)


@hosts('api')
def list_roles():
    """Show a list of all available roles"""
    for role in lib.get_roles():
        margin_left = lib.get_margin(len(role['fullname']))
        print("{0}{1}{2}".format(
            role['fullname'], margin_left,
            role.get('description', '(no description)')))


@hosts('api')
def list_roles_detailed():
    """Show detailed information for all roles"""
    for role in lib.get_roles():
        lib.print_role(role)


@hosts('api')
def list_plugins():
    """Show all available plugins"""
    lib.print_plugin_list()


def _check_appliances():
    """Looks around and return True or False based on whether we are in a
    kitchen
    """
    filenames = os.listdir(os.getcwd())
    missing = []
    for dirname in ['nodes', 'environments', 'roles', 'cookbooks', 'data_bags']:
        if (dirname not in filenames) or (not os.path.isdir(dirname)):
            missing.append(dirname)
    return (not bool(missing)), missing


def _readconfig():
    """Configures environment variables"""
    config = ConfigParser.SafeConfigParser()
    try:
        found = config.read(littlechef.CONFIGFILE)
    except ConfigParser.ParsingError as e:
        abort(str(e))
    if not len(found):
        try:
            found = config.read(['config.cfg', 'auth.cfg'])
        except ConfigParser.ParsingError as e:
            abort(str(e))
        if len(found):
            print('\nDeprecationWarning: deprecated config file name \'{0}\'.'
                  ' Use {1}'.format(found[0], littlechef.CONFIGFILE))
        else:
            abort('No {0} file found in the current '
                  'directory'.format(littlechef.CONFIGFILE))

    in_a_kitchen, missing = _check_appliances()
    missing_str = lambda m: ' and '.join(', '.join(m).rsplit(', ', 1))
    if not in_a_kitchen:
        abort("Couldn't find {0}. "
              "Are you executing 'fix' outside of a kitchen?\n"
              "To create a new kitchen in the current directory "
              " type 'fix new_kitchen'".format(missing_str(missing)))

    # We expect an ssh_config file here,
    # and/or a user, (password/keyfile) pair
    try:
        env.ssh_config_path = config.get('userinfo', 'ssh-config')
    except ConfigParser.NoSectionError:
        abort('You need to define a "userinfo" section'
              ' in the config file. Refer to the README for help '
              '(http://github.com/tobami/littlechef)')
    except ConfigParser.NoOptionError:
        env.ssh_config_path = None

    if env.ssh_config_path:
        env.ssh_config = _SSHConfig()
        env.ssh_config_path = os.path.expanduser(env.ssh_config_path)
        env.use_ssh_config = True
        try:
            env.ssh_config.parse(open(env.ssh_config_path))
        except IOError:
            abort("Couldn't open the ssh-config file "
                  "'{0}'".format(env.ssh_config_path))
        except Exception:
            abort("Couldn't parse the ssh-config file "
                  "'{0}'".format(env.ssh_config_path))
    else:
        env.ssh_config = None

    # check for a gateway
    try:
        env.gateway = config.get('connection', 'gateway')
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        env.gateway = None

    # Check for an encrypted_data_bag_secret file and set the env option
    try:
        env.encrypted_data_bag_secret = config.get('userinfo',
                                                   'encrypted_data_bag_secret')
    except ConfigParser.NoOptionError:
        env.encrypted_data_bag_secret = None

    if env.encrypted_data_bag_secret:
        env.encrypted_data_bag_secret = os.path.expanduser(
            env.encrypted_data_bag_secret)
        try:
            open(env.encrypted_data_bag_secret)
        except IOError as e:
            abort("Failed to open encrypted_data_bag_secret file at "
                  "'{0}'".format(env.encrypted_data_bag_secret))

    try:
        sudo_prefix = config.get('ssh', 'sudo_prefix', raw=True)
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        pass
    else:
        env.sudo_prefix = sudo_prefix

    try:
        env.user = config.get('userinfo', 'user')
    except ConfigParser.NoOptionError:
        if not env.ssh_config_path:
            msg = 'You need to define a user in the "userinfo" section'
            msg += ' of {0}. Refer to the README for help'
            msg += ' (http://github.com/tobami/littlechef)'
            abort(msg.format(littlechef.CONFIGFILE))
        user_specified = False
    else:
        user_specified = True

    try:
        env.password = config.get('userinfo', 'password') or None
    except ConfigParser.NoOptionError:
        pass

    try:
        #If keypair-file is empty, assign None or fabric will try to read key "
        env.key_filename = config.get('userinfo', 'keypair-file') or None
    except ConfigParser.NoOptionError:
        pass

    if (user_specified and not env.password and not env.key_filename
            and not env.ssh_config):
        abort('You need to define a password, keypair file, or ssh-config '
              'file in {0}'.format(littlechef.CONFIGFILE))

    # Node's Chef Solo working directory for storing cookbooks, roles, etc.
    try:
        env.node_work_path = os.path.expanduser(config.get('kitchen',
                                                'node_work_path'))
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        env.node_work_path = littlechef.node_work_path
    else:
        if not env.node_work_path:
            abort('The "node_work_path" option cannot be empty')

    # Follow symlinks
    try:
        env.follow_symlinks = config.getboolean('kitchen', 'follow_symlinks')
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        env.follow_symlinks = False

    # Upload Directory
    try:
        env.sync_packages_dest_dir = config.get('sync-packages',
                                                'dest-dir')
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        env.sync_packages_dest_dir = None

    # Local Directory
    try:
        env.sync_packages_local_dir = config.get('sync-packages',
                                                 'local-dir')
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        env.sync_packages_local_dir = None

# Only read config if fix is being used and we are not creating a new kitchen
if littlechef.__cooking__:
    # Called from command line
    if env.chef_environment:
        print("\nEnvironment: {0}".format(env.chef_environment))
    if env.verbose:
        print("\nVerbose output on")
    if env.loglevel == "debug":
        print("\nDebug level on")
    if 'new_kitchen' not in sys.argv:
        _readconfig()
else:
    # runner module has been imported
    env.ssh_config = None
    env.follow_symlinks = False
    env.encrypted_data_bag_secret = None
    env.sync_packages_dest_dir = None
    env.sync_packages_local_dir = None
