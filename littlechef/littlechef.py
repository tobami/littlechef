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
"""LittleChef: Configuration Management using Chef without a Chef Server"""
import ConfigParser
import os
import sys
import simplejson as json

import fabric
from fabric.api import *
from fabric.contrib.files import append, exists
from fabric.contrib.console import confirm

from version import version
import solo
import lib
import chef


# Fabric settings
env.loglevel = "info"
fabric.state.output['running'] = False
# Paths that may contain cookbooks
cookbook_paths = ['site-cookbooks', 'cookbooks']
# Node's Chef Solo working directory for storing cookbooks, roles, etc.
node_work_path = '/var/chef-solo'


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
            readme_path = os.path.join(d, 'README')
            if not os.path.exists(readme_path):
                with open(readme_path, "w") as readme:
                    print >> readme, ""
            print "{0}/ directory created...".format(d)

    _mkdir("nodes")
    _mkdir("roles")
    for cookbook_path in cookbook_paths:
        _mkdir(cookbook_path)
    if not os.path.exists("auth.cfg"):
        with open("auth.cfg", "w") as authfh:
            print >> authfh, "[userinfo]"
            print >> authfh, "user = "
            print >> authfh, "password = "
            print >> authfh, "keypair-file = "
            print "auth.cfg file created..."


@hosts('setup')
def node(host):
    """Select a node"""
    if host == 'all':
        for node in lib.get_nodes():
            env.hosts.append(node['littlechef']['nodename'])
        if not len(env.hosts):
            abort('No nodes found')
    else:
        env.hosts = [host]


def deploy_chef(gems="no", ask="yes"):
    """Install chef-solo on a node"""
    if not env.host_string:
        abort('no node specified\nUsage: cook node:MYNODE deploy_chef')

    distro_type, distro = solo.check_distro()
    message = '\nAre you sure you want to install Chef at the node {0}'.format(
        env.host_string)
    if gems == "yes":
        message += ', using gems for "{0}"?'.format(distro)
    else:
        message += ', using "{0}" packages?'.format(distro)
    if ask != "no" and not confirm(message):
        abort('Aborted by user')

    if distro_type == "debian":
        if gems == "yes":
            solo.gem_apt_install()
        else:
            solo.apt_install(distro)
    elif distro_type == "rpm":
        if gems == "yes":
            solo.gem_rpm_install()
        else:
            solo.rpm_install()
    elif distro_type == "gentoo":
        solo.emerge_install()
    else:
        abort('wrong distro type: {0}'.format(distro_type))
    solo.configure_chef_solo(node_work_path, cookbook_paths)


def recipe(recipe, save=False):
    """Apply the given recipe to a node
        ignores existing config unless save=True
    """
    # Do some checks
    if not env.host_string:
        abort('no node specified\nUsage: cook node:MYNODE recipe:MYRECIPE')
    lib.print_header(
        "Executing recipe '{0}' on node {1}".format(recipe, env.host_string))

    recipe_found = False
    for cookbook_path in cookbook_paths:
        if os.path.exists(os.path.join(cookbook_path, recipe.split('::')[0])):
            recipe_found = True
            break
    if not recipe_found:
        abort("Cookbook '{0}' not found".format(recipe))

    # Now create configuration and sync node
    data = {"run_list": ["recipe[{0}]".format(recipe)]}
    filepath = chef.save_config(save, data, env.host_string)
    chef.sync_node(filepath, cookbook_paths, node_work_path)


def role(role, save=False):
    """Apply the given role to a node
        ignores existing config unless save=True"""
    # Do some checks
    if not env.host_string:
        abort('no node specified\nUsage: cook node:MYNODE role:MYROLE')
    lib.print_header("Applying role '{0}' to node {1}".format(role, env.host_string))

    if not os.path.exists('roles/' + role + '.json'):
        if os.path.exists('roles/' + role + '.rb'):
            msg = "Role '{0}' only found as '{1}.rb'.".format(role, role)
            msg += " It should be in json format."
            abort(msg)
        else:
            abort("Role '{0}' not found".format(role))

    # Now create configuration and sync node
    data = {"run_list": ["role[{0}]".format(role)]}
    filepath = chef.save_config(save, data, env.host_string)
    chef.sync_node(filepath, cookbook_paths, node_work_path)


def configure():
    """Configure node using existing config file"""
    # Do some checks
    if not env.host_string:
        msg = 'no node specified\n'
        msg += 'Usage:\n  cook node:MYNODE configure\n  cook node:all configure'
        abort(msg)

    lib.print_header("Configuring {0}".format(env.host_string))
    configfile = env.host_string + ".json"
    node_path = os.path.join("nodes", configfile)
    if not os.path.exists(node_path):
        print "Warning: No config file found for {0}".format(env.host_string)
        print "Warning: Chef run aborted"
        return

    # Configure node
    chef.sync_node(node_path, cookbook_paths, node_work_path)


@hosts('api')
def list_nodes():
    """List all nodes"""
    for node in lib.get_nodes():
        lib.print_node(node)


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
    for node in lib.get_nodes():
        recipename = 'role[' + role + ']'
        if recipename in node.get('run_list'):
            lib.print_node(node)


@hosts('api')
def list_recipes():
    """Show a list of all available recipes"""
    for recipe in lib.get_recipes(cookbook_paths):
        margin_left = lib.get_margin(len(recipe['name']))
        print("{0}{1}{2}".format(
            recipe['name'], margin_left, recipe['description']))


@hosts('api')
def list_recipes_detailed():
    """Show information for all recipes"""
    for recipe in lib.get_recipes(cookbook_paths):
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
    """Show information for all roles"""
    for role in lib.get_roles():
        lib.print_role(role)


# Check that user is cooking inside a kitchen and configure authentication #
def _readconfig():
    """Configure environment"""
    # Check that all dirs and files are present
    for dirname in ['nodes', 'roles', 'cookbooks', 'auth.cfg']:
        if not os.path.exists(dirname):
            msg = "You are executing 'cook' outside of a kitchen\n"
            msg += "To create a new kitchen in the current directory"
            msg += " type 'cook new_kitchen'"
            abort(msg)
    config = ConfigParser.ConfigParser()
    config.read("auth.cfg")
    try:
        env.user = config.get('userinfo', 'user')
        if not env.user:
            raise ValueError('user variable is empty')
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError, ValueError):
        msg = 'You need to define a user in the "userinfo" section'
        msg += ' of auth.cfg. Refer to the README for help'
        msg += ' (http://github.com/tobami/littlechef)'
        abort(msg)

    # Allow password OR keypair-file not to be present
    try:
        env.password = config.get('userinfo', 'password')
    except ConfigParser.NoOptionError:
        pass
    try:
        env.key_filename = config.get('userinfo', 'keypair-file')
    except ConfigParser.NoOptionError:
        pass

    # Both cannot be empty
    if not env.password and not env.key_filename:
        abort('You need to define a password or a keypair-file in auth.cfg.')


if len(sys.argv) > 3 and sys.argv[1] == "-f" and sys.argv[3] != "new_kitchen":
    # If littlechef.py has been called from the cook script, read configuration
    _readconfig()
else:
    # If it has been imported (usually len(sys.argv) < 4) don't read auth.cfg
    pass
