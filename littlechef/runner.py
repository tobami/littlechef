#Copyright 2010-2011 Miquel Torres <tobami@googlemail.com>
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
from paramiko.config import SSHConfig as _SSHConfig

from littlechef import solo
from littlechef import lib
from littlechef import chef
from littlechef.settings import cookbook_paths


# Fabric settings
import fabric
fabric.state.output['running'] = False
env.loglevel = "info"
env.output_prefix = False


@hosts('setup')
def debug():
    """Sets logging level to debug"""
    print "Setting Chef Solo log level to 'debug'..."
    env.loglevel = 'debug'


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
    for cookbook_path in cookbook_paths:
        _mkdir(cookbook_path)
    # Add skeleton auth.cfg
    if not os.path.exists("auth.cfg"):
        with open("auth.cfg", "w") as authfh:
            print >> authfh, "[userinfo]"
            print >> authfh, "user = "
            print >> authfh, "password = "
            print >> authfh, "keypair-file = "
            print >> authfh, "ssh-config = "
            print "auth.cfg file created..."


@hosts('setup')
def nodes_with_role(rolename):
    nodes = lib.get_nodes_with_roles(rolename)
    return node(*[n['name'] for n in nodes])


@hosts('setup')
def node(*nodes):
    """Selects and configures a list of nodes. 'all' configures all nodes"""
    if not len(nodes) or nodes[0] == '':
        abort('No node was given')
    elif nodes[0] == 'all':
        # Fetch all nodes and add them to env.hosts
        for node in lib.get_nodes():
            env.hosts.append(node['name'])
        if not len(env.hosts):
            abort('No nodes found in /nodes/')
    else:
        # A list of nodes was given
        env.hosts = nodes
    env.all_hosts = list(env.hosts)

    # Check whether another command was given in addition to "node:"
    execute = True
    if 'node:' not in sys.argv[-1]:
        execute = False
    # If user didn't type recipe:X, role:Y or deploy_chef, just run configure
    if execute:
        for hostname in env.hosts:
            env.host = hostname
            env.host_string = hostname
            lib.print_header("Configuring {0}".format(env.host))
            # Read node data and configure node
            node = lib.get_node(env.host)
            chef.sync_node(node)


def deploy_chef(gems="no", ask="yes", version="0.10",
    distro_type=None, distro=None, stop_client='yes'):
    """Install chef-solo on a node"""
    if not env.host_string:
        abort('no node specified\nUsage: fix node:MYNODE deploy_chef')
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

    solo.install(distro_type, distro, gems, version, stop_client)
    solo.configure()


def recipe(recipe):
    """Apply the given recipe to a node
    Sets the run_list to the given recipe
    If no nodes/hostname.json file exists, it creates one
    """
    # Check that a node has been selected
    if not env.host_string:
        abort('no node specified\nUsage: fix node:MYNODE recipe:MYRECIPE')
    lib.print_header(
        "Applying recipe '{0}' on node {1}".format(recipe, env.host_string))

    # Now create configuration and sync node
    data = lib.get_node(env.host_string)
    data["run_list"] = ["recipe[{0}]".format(recipe)]
    chef.sync_node(data)


def role(role):
    """Apply the given role to a node
    Sets the run_list to the given role
    If no nodes/hostname.json file exists, it creates one
    """
    # Check that a node has been selected
    if not env.host_string:
        abort('no node specified\nUsage: fix node:MYNODE role:MYROLE')
    lib.print_header(
        "Applying role '{0}' to {1}".format(role, env.host_string))

    # Now create configuration and sync node
    data = lib.get_node(env.host_string)
    data["run_list"] = ["role[{0}]".format(role)]
    chef.sync_node(data)


@hosts('setup')
def get_ips():
    """Ping all nodes and update their 'ipaddress' field"""
    import subprocess
    for node in lib.get_nodes():
        # For each node, ping the hostname
        env.host_string = node['name']
        proc = subprocess.Popen(['ping', '-c', '1', node['name']],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        resp, error = proc.communicate()
        if not error:
            # Get lines from output and parse the first line to get the IP
            lines = resp.split("\n")
            ip = lines[0].split()[2].lstrip("(").rstrip(")")
            if not ip:
                print "Warning: could not get IP address from node {0}".format(
                    node['name'])
                continue
            print "Node {0} has IP {1}".format(node['name'], ip)
            # Update with the ipaddress field in the corresponding node.json
            del node['name']
            node['ipaddress'] = ip
            os.remove(chef.save_config(node, ip))
        else:
            print "Warning: could not resolve node {0}".format(node['name'])


@hosts('api')
def list_nodes():
    """List all configured nodes"""
    for node in lib.get_nodes():
        lib.print_node(node)


@hosts('api')
def list_nodes_detailed():
    """Show a detailed list of all nodes"""
    for node in lib.get_nodes():
        lib.print_node(node, detailed=True)


@hosts('api')
def list_nodes_with_recipe(recipe):
    """Show all nodes which have asigned a given recipe"""
    for node in lib.get_nodes():
        if recipe in lib.get_recipes_in_node(node):
            lib.print_node(node)
        else:
            for role in lib.get_roles_in_node(node):
                with open('roles/' + role + '.json', 'r') as f:
                    roles = json.loads(f.read())
                    # Reuse _get_recipes_in_node to extract recipes in a role
                    if recipe in lib.get_recipes_in_node(roles):
                        lib.print_node(node)
                        break


@hosts('api')
def list_nodes_with_role(role):
    """Show all nodes which have asigned a given role"""
    for node in lib.get_nodes_with_roles(role):
        lib.print_node(node)


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


# Check that user is cooking inside a kitchen and configure authentication #
def _check_appliances():
    """Look around and return True or False based on whether we are in a
    kitchen
    """
    names = os.listdir(os.getcwd())
    missing = []
    for dirname in ['nodes', 'roles', 'cookbooks', 'data_bags']:
        if (dirname not in names) or (not os.path.isdir(dirname)):
            missing.append(dirname)
    if 'auth.cfg' not in names:
        missing.append('auth.cfg')
    return (not bool(missing)), missing


def _readconfig():
    """Configure environment"""
    # Check that all dirs and files are present
    in_a_kitchen, missing = _check_appliances()
    missing_str = lambda m: ' and '.join(', '.join(m).rsplit(', ', 1))
    if not in_a_kitchen:
        msg = "Couldn't find {0}. ".format(missing_str(missing))
        msg += "Are you are executing 'fix' outside of a kitchen?\n"\
               "To create a new kitchen in the current directory "\
               " type 'fix new_kitchen'"
        abort(msg)
    config = ConfigParser.ConfigParser()
    config.read("auth.cfg")

    # We expect an ssh_config file here,
    # and/or a user, (password/keyfile) pair
    env.ssh_config = None
    try:
        ssh_config = config.get('userinfo', 'ssh-config')
    except ConfigParser.NoSectionError:
        msg = 'You need to define a "userinfo" section'
        msg += ' in auth.cfg. Refer to the README for help'
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
            msg += ' of auth.cfg. Refer to the README for help'
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

    if user_specified and (not env.password and not env.key_filename):
        abort('You need to define a password or a keypair-file in auth.cfg.')


# Only read config if fix is being used and we are not creating a new kitchen
import littlechef
if littlechef.__cooking__:
    # Called from command line
    if 'new_kitchen' not in sys.argv:
        _readconfig()
else:
    # runner module has been imported
    env.ssh_config = None
