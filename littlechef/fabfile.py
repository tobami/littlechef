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
from fabric import colors

from version import version
import solo
import lib


env.loglevel = "info"
fabric.state.output['running'] = False


@hosts('setup')
def debug():
    """Sets logging level to debug"""
    print "Setting Chef Solo log level to 'debug'..."
    env.loglevel = 'debug'


@hosts('setup')
def new_deployment():
    """Create LittleChef directory structure (Kitchen)"""
    def _mkdir(d):
        if not os.path.exists(d):
            os.mkdir(d)
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

    print "\n== Executing recipe {0} on node {1} ==".format(
        recipe, env.host_string)

    recipe_found = False
    for cookbook_path in cookbook_paths:
        if os.path.exists(os.path.join(cookbook_path, recipe.split('::')[0])):
            recipe_found = True
            break
    if not recipe_found:
        abort('Cookbook "{0}" not found'.format(recipe))

    # Now create configuration and sync node
    data = {"run_list": ["recipe[{0}]".format(recipe)]}
    filepath = _save_config(save, data, env.host_string)
    _sync_node(filepath)


def role(role, save=False):
    """Apply the given role to a node
        ignores existing config unless save=True"""
    # Do some checks
    if not env.host_string:
        abort('no node specified\nUsage: cook node:MYNODE role:MYROLE')

    print "\n== Applying role {0} to node {1} ==".format(role, env.host_string)
    if not os.path.exists('roles/' + role + '.json'):
        if os.path.exists('roles/' + role + '.rb'):
            msg = "Role '{0}' only found as '{1}.rb'.".format(role, role)
            msg += " It should be in json format."
            abort(msg)
        else:
            abort("Role '{0}' not found".format(role))

    # Now create configuration and sync node
    data = {"run_list": ["role[{0}]".format(role)]}
    filepath = _save_config(save, data, env.host_string)
    _sync_node(filepath)


def configure():
    """Configure node using existing config file"""
    # Do some checks
    if not env.host_string:
        msg = 'no node specified\n'
        msg += 'Usage:\n  cook node:MYNODE configure\n  cook node:all configure'
        abort(msg)

    print(colors.yellow("\n== Configuring {0} ==".format(env.host_string)))
    configfile = env.host_string + ".json"
    node_path = os.path.join("nodes", configfile)
    if not os.path.exists(node_path):
        print "Warning: No config file found for {0}".format(env.host_string)
        print "Warning: Chef run aborted"
        return

    # Configure node
    _sync_node(node_path)


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
    for role in _get_roles():
        lib.print_role(role)


# Check that user is cooking inside a kitchen and configure authentication #
def _readconfig():
    """Configure environment"""
    # Check that all dirs and files are present
    for dirname in ['nodes', 'roles', 'cookbooks', 'auth.cfg']:
        if not os.path.exists(dirname):
            msg = "You are executing 'cook' outside of a deployment directory\n"
            msg += "To create a new deployment in the current directory"
            msg += " type 'cook new_deployment'"
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


if len(sys.argv) > 3 and sys.argv[1] == "-f" and sys.argv[3] != "new_deployment":
    # If littlechef.py has been called from the cook script, read configuration
    _readconfig()
else:
    # If it has been imported (usually len(sys.argv) < 4) don't read auth.cfg
    pass


################################################################################
### Private functions                                                        ###
################################################################################

##################################################################
### Node configuration and syncing                             ###
### See                                                        ###
### http://wiki.opscode.com/display/chef/Anatomy+of+a+Chef+Run ###
##################################################################
def _save_config(save, data, hostname):
    """Saves node configuration either to tmp_node.json or to hostname.json"""
    filepath = NODEPATH + hostname + ".json"
    if os.path.exists(filepath) and not save:
        filepath = 'tmp_node.json'
    with open(filepath, 'w') as f:
        f.write(json.dumps(data, indent=4))
        f.write('\n')
    return filepath


def _sync_node(filepath):
    """Buils, synchronizes and configures a node"""
    _synchronize_node(filepath)
    _configure_node(filepath)


def _synchronize_node(configfile):
    """Performs the Synchronize step of a Chef run:
    Uploads needed cookbooks and all roles to a node
    """
    # Clean up node
    for path in ['roles'] + cookbook_paths:
        with hide('stdout'):
            sudo('rm -rf {0}/{1}'.format(node_work_path, path))

    cookbooks = []
    with open(configfile, 'r') as f:
        try:
            node = json.loads(f.read())
        except json.decoder.JSONDecodeError as e:
            msg = 'Little Chef found the following error in'
            msg += ' "{0}":\n                {1}'.format(configfile, str(e))
            abort(msg)
    # Fetch cookbooks needed for recipes
    for recipe in lib.get_recipes_in_node(node):
        recipe = recipe.split('::')[0]
        if recipe not in cookbooks:
            cookbooks.append(recipe)

    # Fetch cookbooks needed for role recipes
    for role in lib.get_roles_in_node(node):
        try:
            with open('roles/' + role + '.json', 'r') as f:
                try:
                    roles = json.loads(f.read())
                except json.decoder.JSONDecodeError as e:
                    msg = 'Little Chef found the following error in your'
                    msg += ' "{0}" role file:\n                {1}'.format(
                        role, str(e))
                    abort(msg)
                # Reuse _get_recipes_in_node to extract recipes in a role
                for recipe in lib.get_recipes_in_node(roles):
                    recipe = recipe.split('::')[0]
                    if recipe not in cookbooks:
                        cookbooks.append(recipe)
        except IOError:
            abort(colors.red("Role '{0}' not found".format(role)))

    # Fetch dependencies
    warnings = []
    for cookbook in cookbooks:
        for recipe in lib.get_recipes_in_cookbook(cookbook, cookbook_paths):
            for dep in recipe['dependencies']:
                if dep not in cookbooks:
                    try:
                        lib.get_cookbook_path(dep, cookbook_paths)
                        cookbooks.append(dep)
                    except IOError:
                        if dep not in warnings:
                            warnings.append(dep)
                            print "Warning: Possible error because of missing",
                            print "dependency for cookbook {0}".format(recipe['name'])
                            print "         Cookbook '{0}' not found".format(dep)
                            import time
                            time.sleep(1)

    cookbooks_by_path = {}
    for cookbook in cookbooks:
        for cookbook_path in cookbook_paths:
            path = os.path.join(cookbook_path, cookbook)
            if os.path.exists(path):
                cookbooks_by_path[path] = cookbook

    print "Uploading cookbooks... ({0})".format(
            ", ".join(c for c in cookbooks))
    _upload_and_unpack(p for p in cookbooks_by_path.keys())

    print "Uploading roles..."
    _upload_and_unpack(['roles'])


def _configure_node(configfile):
    """Exectutes chef-solo to apply roles and recipes to a node"""
    with hide('running'):
        print "Uploading node.json..."
        remote_file = '/root/{0}'.format(configfile.split("/")[-1])
        put(configfile, remote_file, use_sudo=True, mode=_file_mode)
        sudo('chown root:root {0}'.format(remote_file)),
        sudo('mv {0} /etc/chef/node.json'.format(remote_file)),

        print "\n== Cooking ==\n"
        with settings(hide('warnings'), warn_only=True):
            output = sudo(
                'chef-solo -l {0} -j /etc/chef/node.json'.format(env.loglevel))
            if output.failed:
                if 'chef-solo: command not found' in output:
                    print(
                        colors.red(
                            "\nFAILED: Chef Solo is not installed on this node"))
                    print(
                        "Type 'cook nodes:{0} deploy_chef' to install it".format(
                            env.host))
                    abort("")
                else:
                    print(colors.red(
                        "\nFAILED: A problem occurred while executing chef-solo"))
                    abort("")
            else:
                print(colors.green("\nSUCCESS: Node correctly configured"))


def _upload_and_unpack(source):
    """Packs the given directories, uploads the tar.gz to the node
    and unpacks it in the node_work_path (typically '/var/chef-solo') directory
    """
    with hide('running', 'stdout'):
        # Local archive relative path
        local_archive = 'temp.tar.gz'
        # Remote archive absolute path
        remote_archive = '/root/{0}'.format(local_archive)
        # Remove existing temporary directory
        local('(chmod -R u+rwX tmp; rm -rf tmp) > /dev/null 2>&1')
        # Create temporary directory
        local('mkdir tmp')
        # Copy selected sources into temporary directory
        for item in source:
            local('mkdir -p tmp/{0}'.format(os.path.dirname(item)))
            local('cp -R {0} tmp/{1}'.format(item, item))
        # Set secure permissions on copied sources
        local('chmod -R u=rX,go= tmp')
        # Create archive locally
        local(
            'cd tmp && COPYFILE_DISABLE=true tar czf ../{0} --exclude=".svn" .'.format(
                local_archive))
        # Upload archive to remote
        put(local_archive, remote_archive, use_sudo=True, mode=_file_mode)
        # Remove local copy of archive and directory
        local('rm {0}'.format(local_archive))
        local('chmod -R u+w tmp')
        local('rm -rf tmp')
        if not exists(node_work_path):
            # Report error with remote paths
            msg = "the {0} directory was not found at ".format(node_work_path)
            msg += "the node. Is Chef correctly installed?"
            msg += "\nYou can deploy chef-solo by typing:\n"
            msg += "  cook node:{0} deploy_chef".format(env.host)
            abort(msg)
        with cd(node_work_path):
            # Install the remote copy of archive
            sudo('tar xzf {0}'.format(remote_archive))
            # Fix ownership
            sudo('chown -R root:root {0}'.format(node_work_path))
            # Remove the remote copy of archive
            sudo('rm {0}'.format(remote_archive))


#################
### Constants ###
#################

# Paths that may contain cookbooks
cookbook_paths = ['site-cookbooks', 'cookbooks']

# Node's work directory for storing cookbooks, roles, etc.
node_work_path = '/var/chef-solo'

# Upload sensitive files with secure permissions
_file_mode = 400
