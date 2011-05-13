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
"""Node configuration and syncing
See http://wiki.opscode.com/display/chef/Anatomy+of+a+Chef+Run
"""
import os
import simplejson as json
import time

from fabric.api import *
from fabric.contrib.files import append, exists
from fabric import colors
from fabric.utils import abort

import littlechef
import lib


# Upload sensitive files with secure permissions
_file_mode = 400


def _save_config(node):
    """Saves node configuration
    if no nodes/hostname.json exists, it creates one
    it also saves to tmp_node.json
    """
    filepath = os.path.join("nodes/", env.host_string + ".json")
    files_to_create = ['tmp_node.json']
    if not os.path.exists(filepath):
        # Only save to nodes/ if there is not already a file
        print "Saving configuration to {0}".format(filepath)
        files_to_create.append(filepath)
    for node_file in files_to_create:
        with open(node_file, 'w') as f:
            f.write(json.dumps(node, indent=4))
            f.write('\n')
    return 'tmp_node.json'


def sync_node(node):
    """Buils, synchronizes and configures a node"""
    cookbooks = _build_node(node)
    with lib.credentials():
        _synchronize_node(cookbooks)
        # Everything was configured alright, so save the node configuration
        filepath = _save_config(node)
        _configure_node(filepath)


def _build_node(node):
    """Performs the Synchronize step of a Chef run:
    Uploads needed cookbooks and all roles to a node
    """
    cookbooks = []
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
            abort("Role '{0}' not found".format(role))

    # Fetch dependencies
    warnings = []
    for cookbook in cookbooks:
        for recipe in lib.get_recipes_in_cookbook(
                                        cookbook, littlechef.cookbook_paths):
            for dep in recipe['dependencies']:
                if dep not in cookbooks:
                    try:
                        lib.get_cookbook_path(dep, littlechef.cookbook_paths)
                        cookbooks.append(dep)
                    except IOError:
                        if dep not in warnings:
                            warnings.append(dep)
                            print "Warning: Possible error because of missing",
                            print "dependency for cookbook {0}".format(
                                recipe['name'])
                            print "         Cookbook '{0}' not found".format(
                                dep)
                            time.sleep(1)
    return cookbooks


def _synchronize_node(cookbooks):
    # Clean up node
    for path in ['roles'] + littlechef.cookbook_paths:
        with hide('stdout'):
            sudo('rm -rf {0}/{1}'.format(littlechef.node_work_path, path))

    cookbooks_by_path = {}
    for cookbook in cookbooks:
        for cookbook_path in littlechef.cookbook_paths:
            path = os.path.join(cookbook_path, cookbook)
            if os.path.exists(path):
                cookbooks_by_path[path] = cookbook
    print "Uploading roles and cookbooks:"
    print " ({0})".format(", ".join(c for c in cookbooks))
    to_upload = [p for p in cookbooks_by_path.keys()]
    to_upload.append('roles')
    _upload_and_unpack(to_upload)


def _configure_node(configfile):
    """Exectutes chef-solo to apply roles and recipes to a node"""
    with hide('running'):
        print "Uploading node.json..."
        remote_file = '/root/{0}'.format(configfile.split("/")[-1])
        put(configfile, remote_file, use_sudo=True, mode=_file_mode)
        sudo('chown root:root {0}'.format(remote_file)),
        sudo('mv {0} /etc/chef/node.json'.format(remote_file)),
        # Remove local temporary node file
        os.remove(configfile)

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
        if not exists(littlechef.node_work_path):
            # Report error with remote paths
            msg = "the {0} directory was".format(littlechef.node_work_path)
            msg += " not found at the node. Is Chef correctly installed?"
            msg += "\nYou can deploy chef-solo by typing:\n"
            msg += "  cook node:{0} deploy_chef".format(env.host)
            abort(msg)
        with cd(littlechef.node_work_path):
            # Install the remote copy of archive
            sudo('tar xzf {0}'.format(remote_archive))
            # Fix ownership
            sudo('chown -R root:root {0}'.format(littlechef.node_work_path))
            # Remove the remote copy of archive
            sudo('rm {0}'.format(remote_archive))
