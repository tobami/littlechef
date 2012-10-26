#Copyright 2010-2012 Miquel Torres <tobami@gmail.com>
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
import simplejson as json

from fabric.api import *
from fabric.contrib.files import append, exists
from fabric.contrib.console import confirm
from ssh.config import SSHConfig as _SSHConfig

import littlechef
from littlechef import solo
from littlechef import lib
from littlechef import chef


# Fabric settings
import fabric
fabric.state.output['running'] = False
env.loglevel = "info"
env.output_prefix = False
__testing__ = False


@hosts('setup')
def new_kitchen():
    """Create LittleChef directory structure (Kitchen)"""
    def _mkdir(d):
        if not os.path.exists(d):
            os.mkdir(d)
            # Add an empty README so that it can be added to version control
            readme_path = os.path.join(d, 'README')
            if not os.path.exists(readme_path):
                with open(readme_path, "w") as readme:
                    print >> readme, ""
            print "{0}/ directory created...".format(d)

    _mkdir("nodes")
    _mkdir("roles")
    _mkdir("data_bags")
    for cookbook_path in littlechef.cookbook_paths:
        _mkdir(cookbook_path)
    # Add skeleton config.cfg
    if not os.path.exists("config.cfg"):
        with open("config.cfg", "w") as configfh:
            print >> configfh, "[userinfo]"
            print >> configfh, "user = "
            print >> configfh, "password = "
            print >> configfh, "keypair-file = "
            print >> configfh, "ssh-config = "
            print >> configfh, "[kitchen]"
            print >> configfh, "node_work_path = /tmp/chef-solo/"
            print "config.cfg file created..."


@hosts('setup')
def nodes_with_role(rolename):
    """Sets a list of nodes that have the given role
    in their run list and calls node()

    """
    nodes_in_env = []
    nodes = lib.get_nodes_with_role(rolename)
    if env.chef_environment is None:
        # Pass all nodes
        nodes_in_env = [n['name'] for n in nodes]
    else:
        # Only nodes in environment
        nodes_in_env = [n['name'] for n in nodes \
                        if n.get('chef_environment') == env.chef_environment]
    if not len(nodes_in_env):
        print("No nodes found with role '{0}'".format(rolename))
        sys.exit(0)
    return node(*nodes_in_env)


@hosts('setup')
def node(*nodes):
    """Selects and configures a list of nodes. 'all' configures all nodes"""
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
            if not confirm(message):
                abort('Aborted by user')
    else:
        # A list of nodes was given
        env.hosts = list(nodes)
    env.all_hosts = list(env.hosts)  # Shouldn't be needed
    if len(env.hosts) > 1:
        print "Configuring nodes: {0}...".format(", ".join(env.hosts))

    # Check whether another command was given in addition to "node:"
    execute = True
    if not(littlechef.__cooking__ and
            'node:' not in sys.argv[-1] and
            'nodes_with_role:' not in sys.argv[-1]):
        # If user didn't type recipe:X, role:Y or deploy_chef,
        # configure the nodes
        for hostname in env.hosts:
            env.host = hostname
            env.host_string = hostname
            node = lib.get_node(env.host)
            lib.print_header("Configuring {0}".format(env.host))
            if __testing__:
                print "TEST: would now configure {0}".format(env.host)
            else:
                chef.sync_node(node)


def deploy_chef(gems="no", ask="yes", version="0.10",
    distro_type=None, distro=None, stop_client='yes'):
    """Install chef-solo on a node"""
    if not env.host_string:
        abort('no node specified\nUsage: fix node:MYNODES deploy_chef')
    chef_versions = ["0.9", "0.10"]
    if version not in chef_versions:
        abort('Wrong Chef version specified. Valid versions are {0}'.format(
            ", ".join(chef_versions)))
    if distro_type is None and distro is None:
        distro_type, distro = solo.check_distro()
    elif distro_type is None or distro is None:
        abort('Must specify both or neither of distro_type and distro')
    if ask == "yes":
        message = '\nAre you sure you want to install Chef {0}'.format(version)
        message += ' at the node {0}'.format(env.host_string)
        if gems == "yes":
            message += ', using gems for "{0}"?'.format(distro)
        else:
            message += ', using "{0}" packages?'.format(distro)
        if not confirm(message):
            abort('Aborted by user')
    else:
        if gems == "yes":
            method = 'using gems for "{0}"'.format(distro)
        else:
            method = '{0} using "{1}" packages'.format(version, distro)
        print("Deploying Chef {0}...".format(method))

    if not __testing__:
        solo.install(distro_type, distro, gems, version, stop_client)
        solo.configure()


def recipe(recipe):
    """Apply the given recipe to a node
    Sets the run_list to the given recipe
    If no nodes/hostname.json file exists, it creates one

    """
    # Check that a node has been selected
    if not env.host_string:
        abort('no node specified\nUsage: fix node:MYNODES recipe:MYRECIPE')
    lib.print_header(
        "Applying recipe '{0}' on node {1}".format(recipe, env.host_string))

    # Now create configuration and sync node
    data = lib.get_node(env.host_string)
    data["run_list"] = ["recipe[{0}]".format(recipe)]
    if not __testing__:
        chef.sync_node(data)


def role(role):
    """Apply the given role to a node
    Sets the run_list to the given role
    If no nodes/hostname.json file exists, it creates one

    """
    # Check that a node has been selected
    if not env.host_string:
        abort('no node specified\nUsage: fix node:MYNODES role:MYROLE')
    lib.print_header(
        "Applying role '{0}' to {1}".format(role, env.host_string))

    # Now create configuration and sync node
    data = lib.get_node(env.host_string)
    data["run_list"] = ["role[{0}]".format(role)]
    if not __testing__:
        chef.sync_node(data)


def ssh(name):
    """Executes the given command"""
    if not env.host_string:
        abort('no node specified\nUsage: fix node:MYNODES ssh:COMMAND')
    print("\nExecuting the command '{0}' on the node {1}...".format(
          name, env.host_string))
    # Execute remotely using either the sudo or the run fabric functions
    with settings(hide("warnings"), warn_only=True):
        if name.startswith("sudo "):
            with lib.credentials():
                sudo(name[5:])
        else:
            with lib.credentials():
                run(name)


def plugin(name):
    """Executes the selected plugin
    Plugins are expected to be found in the kitchen's 'plugins' directory

    """
    if not env.host_string:
        abort('No node specified\nUsage: fix node:MYNODES plugin:MYPLUGIN')
    plug = lib.import_plugin(name)
    print("Executing plugin '{0}' on {1}".format(name, env.host_string))
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
    """Show all nodes which have asigned a given recipe"""
    lib.print_nodes(lib.get_nodes_with_recipe(recipe, env.chef_environment))


@hosts('api')
def list_nodes_with_role(role):
    """Show all nodes which have asigned a given role"""
    lib.print_nodes(lib.get_nodes_with_role(role, env.chef_environment))


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
    for dirname in ['nodes', 'roles', 'cookbooks', 'data_bags']:
        if (dirname not in filenames) or (not os.path.isdir(dirname)):
            missing.append(dirname)
    return (not bool(missing)), missing


def _readconfig():
    """Configures environment variables"""
    config = ConfigParser.SafeConfigParser()
    try:
        found = config.read([littlechef.CONFIGFILE, 'auth.cfg'])
    except ConfigParser.ParsingError as e:
        abort(str(e))
    if not len(found):
        abort('No config.cfg file found in the current directory')

    in_a_kitchen, missing = _check_appliances()
    missing_str = lambda m: ' and '.join(', '.join(m).rsplit(', ', 1))
    if not in_a_kitchen:
        msg = "Couldn't find {0}. ".format(missing_str(missing))
        msg += "Are you are executing 'fix' outside of a kitchen?\n"\
               "To create a new kitchen in the current directory "\
               " type 'fix new_kitchen'"
        abort(msg)

    # We expect an ssh_config file here,
    # and/or a user, (password/keyfile) pair
    env.ssh_config = None
    try:
        ssh_config = config.get('userinfo', 'ssh-config')
    except ConfigParser.NoSectionError:
        msg = 'You need to define a "userinfo" section'
        msg += ' in config.cfg. Refer to the README for help'
        msg += ' (http://github.com/tobami/littlechef)'
        abort(msg)
    except ConfigParser.NoOptionError:
        ssh_config = None

    if ssh_config:
        env.ssh_config = _SSHConfig()
        try:
            env.ssh_config.parse(open(os.path.expanduser(ssh_config)))
        except IOError:
            msg = "Couldn't open the ssh-config file '{0}'".format(ssh_config)
            abort(msg)
        except Exception:
            msg = "Couldn't parse the ssh-config file '{0}'".format(ssh_config)
            abort(msg)

    try:
        env.user = config.get('userinfo', 'user')
        user_specified = True
    except ConfigParser.NoOptionError:
        if not ssh_config:
            msg = 'You need to define a user in the "userinfo" section'
            msg += ' of config.cfg. Refer to the README for help'
            msg += ' (http://github.com/tobami/littlechef)'
            abort(msg)
        user_specified = False

    try:
        env.password = config.get('userinfo', 'password') or None
    except ConfigParser.NoOptionError:
        pass
    try:
        #If keypair-file is empty, assign None or fabric will try to read key "
        env.key_filename = config.get('userinfo', 'keypair-file') or None
    except ConfigParser.NoOptionError:
        pass

    if user_specified and not env.password and not env.ssh_config:
        abort('You need to define a password or a ssh-config file in config.cfg')

    # Node's Chef Solo working directory for storing cookbooks, roles, etc.
    try:
        env.node_work_path = os.path.expanduser(config.get('kitchen',
                                                'node_work_path'))
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        env.node_work_path = littlechef.node_work_path
    else:
        if not env.node_work_path:
            abort('The "node_work_path" option cannot be empty')


# Only read config if fix is being used and we are not creating a new kitchen
env.chef_environment = littlechef.chef_environment
env.loglevel = littlechef.loglevel
env.verbose = littlechef.verbose
env.node_work_path = littlechef.node_work_path

if littlechef.__cooking__:
    # Called from command line
    if env.chef_environment:
        print("\nEnvironment: {0}".format(env.chef_environment))
    if 'new_kitchen' not in sys.argv:
        _readconfig()
else:
    # runner module has been imported
    env.ssh_config = None
