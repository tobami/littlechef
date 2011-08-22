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
import shutil
import simplejson as json

from fabric.api import *
from fabric.contrib.files import append, exists
from fabric import colors
from fabric.utils import abort
from fabric.contrib.project import rsync_project

from littlechef import lib
from littlechef import solo
from littlechef.settings import node_work_path, cookbook_paths

# Path to local patch
basedir = os.path.abspath(os.path.dirname(__file__).replace('\\', '/'))


def _save_config(node):
    """Saves node configuration
    if no nodes/hostname.json exists, it creates one
    it also saves to tmp_node.json
    """
    filepath = os.path.join("nodes/", env.host_string + ".json")
    files_to_create = ['tmp_node.json']
    if not os.path.exists(filepath):
        # Only save to nodes/ if there is not already a file
        print "Saving node configuration to {0}...".format(filepath)
        files_to_create.append(filepath)
    for node_file in files_to_create:
        with open(node_file, 'w') as f:
            f.write(json.dumps(node, indent=4))
    return 'tmp_node.json'


def sync_node(node):
    """Buils, synchronizes and configures a node"""
    with lib.credentials():
        # Always configure Chef Solo
        solo.configure()
        _synchronize_node()
        # Everything was configured alright, so save the node configuration
        filepath = _save_config(node)
        _configure_node(filepath)


def _synchronize_node():
    """Performs the Synchronize step of a Chef run:
    Uploads all cookbooks, all roles and all databags to a node and add the
    patch for data bags
    """
    _build_node_data_bag()
    print "Synchronizing cookbooks, roles and data bags..."
    rsync_project(
        node_work_path, './',
        exclude=(
            '/auth.cfg', # might contain users credentials
            '*.svn', '.bzr*', '.git*', '.hg*', # ignore vcs data
            '/cache/', '/site-cookbooks/data_bag_lib/' # ignore data generated
                                                       # by littlechef
        ),
        delete=True,
        extra_opts="-q",
    )
    _remove_node_data_bag()
    _add_data_bag_patch()


def _build_node_data_bag():
    """Builds one 'node' data bag item per file found in the 'nodes' directory

    Attributes for a node item:
        'id': It adds data bag 'id' using the filename minus the .json extension
        'name': same as 'id'
        all attributes found in nodes/<item>.json file

    """
    nodes = lib.get_nodes()
    node_data_bag_path = os.path.join('data_bags', 'node')
    _remove_node_data_bag()
    os.makedirs(node_data_bag_path)
    for node in nodes:
        node['id'] = node['name']
        # Build extended role list
        node['role'] = lib.get_roles_in_node(node)
        node['roles'] = node['role'][:]
        for role in node['role']:
            node['roles'].extend(lib.get_roles_in_role(role))
        node['roles'] = list(set(node['roles']))
        # Build extended recipe list
        node['recipes'] = lib.get_recipes_in_node(node)
        # Add recipes found inside each roles in the extended role list
        for role in node['roles']:
            node['recipes'].extend(lib.get_recipes_in_role(role))
        node['recipes'] = list(set(node['recipes']))
        # Save node data bag item
        with open(os.path.join(
                    'data_bags', 'node', node['name'] + '.json'), 'w') as f:
            f.write(json.dumps(node))


def _remove_node_data_bag():
    """Removes generated 'node' data_bag"""
    node_data_bag_path = os.path.join('data_bags', 'node')
    if os.path.exists(node_data_bag_path):
        shutil.rmtree(node_data_bag_path)


def _add_data_bag_patch():
    """ Adds data_bag_lib cookbook, which provides a library to read and search
    data bags.
    """
    # Create extra cookbook dir
    lib_path = os.path.join(
                node_work_path, cookbook_paths[0], 'data_bag_lib', 'libraries')
    sudo('mkdir -p {0}'.format(lib_path))
    # Create remote data bags patch
    put(os.path.join(basedir, 'data_bags.rb'),
        os.path.join(lib_path, 'data_bags.rb'), use_sudo=True)
    put(os.path.join(basedir, 'search.rb'),
        os.path.join(lib_path, 'search.rb'), use_sudo=True)


def _configure_node(configfile):
    """Exectutes chef-solo to apply roles and recipes to a node"""
    print "Uploading node.json..."
    remote_file = '/root/{0}'.format(configfile.split("/")[-1])
    # Ensure secure permissions
    put(configfile, remote_file, use_sudo=True, mode=400)
    sudo('chown root:root {0}'.format(remote_file)),
    sudo('mv {0} /etc/chef/node.json'.format(remote_file)),
    # Remove local temporary node file
    os.remove(configfile)

    print colors.yellow("\n== Cooking ==")
    with settings(hide('warnings', 'running'), warn_only=True):
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

