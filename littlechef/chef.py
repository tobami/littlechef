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


def save_config(node, force=False):
    """Saves node configuration
    if no nodes/hostname.json exists, or force=True, it creates one
    it also saves to tmp_node.json
    """
    filepath = os.path.join("nodes/", env.host_string + ".json")
    files_to_create = ['tmp_node.json']
    if not os.path.exists(filepath) or force:
        # Only save to nodes/ if there is not already a file
        print "Saving node configuration to {0}...".format(filepath)
        files_to_create.append(filepath)
    for node_file in files_to_create:
        with open(node_file, 'w') as f:
            f.write(json.dumps(node, indent=4))
    return 'tmp_node.json'


def _get_ipaddress(node):
    """If the node has not the key 'ipaddress' set, get the value with ohai"""
    if "ipaddress" not in node:
        with settings(hide('stdout'), warn_only=True):
            output = sudo('ohai ipaddress')
        if output.succeeded:
            node['ipaddress'] = json.loads(output)[0]
            return True
    return False


def sync_node(node):
    """Builds, synchronizes and configures a node.
    It also injects the ipaddress to the node's config file if not already
    existent.
    """
    with lib.credentials():
        current_node = _synchronize_node()
        # Always configure Chef Solo
        solo.configure(current_node)
        # Everything was configured alright, so save the node configuration
        filepath = save_config(node, _get_ipaddress(node))
        _configure_node(filepath)


def _synchronize_node():
    """Performs the Synchronize step of a Chef run:
    Uploads all cookbooks, all roles and all databags to a node and add the
    patch for data bags
        
    Returns the node object of the node which is about to be configured, or None
    if this node object cannot be found.
    """
    current_node = _build_node_data_bag()
    print "Synchronizing cookbooks, roles and data bags..."
    rsync_project(
        node_work_path, './',
        exclude=(
            '/auth.cfg', # might contain users credentials
            '*.svn', '.bzr*', '.git*', '.hg*', # ignore vcs data
            '/cache/', '/site-cookbooks/chef_solo_search_lib/' # ignore data generated
                                                               # by littlechef
        ),
        delete=True,
        extra_opts="-q",
    )
    _remove_node_data_bag()
    _add_search_patch()
    return current_node


def build_dct(dic, keys, value):
    """Builds a dictionary with arbitrary depth out of a key list"""
    key = keys.pop(0)
    if len(keys):
        dic.setdefault(key, {})
        build_dct(dic[key], keys, value)
    else:
        dic[key] = value

def update_dct(dic1, dic2):
    """Merges two dictionaries recursively
    dic2 will have preference over dic1

    """
    for key, val in dic2.items():
        if isinstance(val, dict):
            dic1.setdefault(key, {})
            update_dct(dic1[key], val)
        else:
            dic1[key] = val


def _merge_attributes(node, all_recipes, all_roles):
    """Merges attributes from cookbooks, node and roles

    Chef Attribute precedence:
    http://wiki.opscode.com/display/chef/Attributes#Attributes-AttributeTypeandPrecedence
    LittleChef implements, in precedence order:
        - Cookbook default
        - Role default
        - Node normal
        - Role override

    NOTE: In order for cookbook attributes to be read, they need to be
        correctly defined in its metadata.json
    """
    # Get cookbooks from extended recipes
    attributes = {}
    for recipe in node['recipes']:
        # Find this recipe
        for r in all_recipes:
            if recipe == r['name']:
                for attr in r['attributes']:
                    if r['attributes'][attr].get('type') == "hash":
                        value = {}
                    else:
                        value = r['attributes'][attr].get('default')
                    build_dct(attributes, attr.split("/"), value)

    # Get default role attributes
    for role in node['roles']:
        for r in all_roles:
            if role == r['name']:
                update_dct(attributes, r['default_attributes'])

    # Get normal node attributes
    non_attribute_fields = [
        'id', 'name', 'role', 'roles', 'recipes', 'run_list', 'ipaddress']
    node_attributes = {}
    for key in node:
        if key in non_attribute_fields:
            continue
        node_attributes[key] = node[key]
    update_dct(attributes, node_attributes)

    # Get override role attributes
    for role in node['roles']:
        for r in all_roles:
            if role == r['name']:
                update_dct(attributes, r['override_attributes'])
    node.update(attributes)
    return node


def _build_node_data_bag():
    """Builds one 'node' data bag item per file found in the 'nodes' directory

    Attributes for a node item:
        'id': It adds data bag 'id' using the filename minus the .json extension
        'name': same as 'id'
        all attributes found in nodes/<item>.json file
        
    Returns the node object of the node which is about to be configured, or None
    if this node object cannot be found.
    """
    current_node = None
    nodes = lib.get_nodes()
    node_data_bag_path = os.path.join('data_bags', 'node')
    _remove_node_data_bag()
    os.makedirs(node_data_bag_path)
    all_recipes = lib.get_recipes()
    all_roles = lib.get_roles()
    for node in nodes:
        node['id'] = node['name'].split('.')[0]
        node['fqdn'] = node['name']
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
        # Add attributes
        node = _merge_attributes(node, all_recipes, all_roles)
        # Save node data bag item
        with open(os.path.join(
                    'data_bags', 'node', node['id'] + '.json'), 'w') as f:
            f.write(json.dumps(node))
        if node['name'] == env.host_string:
            current_node = node
    return current_node


def _remove_node_data_bag():
    """Removes generated 'node' data_bag"""
    node_data_bag_path = os.path.join('data_bags', 'node')
    if os.path.exists(node_data_bag_path):
        shutil.rmtree(node_data_bag_path)


def _add_search_patch():
    """ Adds chef_solo_search_lib cookbook, which provides a library to read and search
    data bags.
    """
    # Create extra cookbook dir
    lib_path = os.path.join(
                node_work_path, cookbook_paths[0], 'chef_solo_search_lib', 'libraries')
    with hide('running', 'stdout'):
        sudo('mkdir -p {0}'.format(lib_path))
    # Create remote data bags patch
    for filename in ('search.rb', 'parser.rb', 'environment.rb'):
        put(os.path.join(basedir, filename),
            os.path.join(lib_path, filename), use_sudo=True)


def _configure_node(configfile):
    """Exectutes chef-solo to apply roles and recipes to a node"""
    print "Uploading node.json..."
    remote_file = '/root/{0}'.format(configfile.split("/")[-1])
    # Ensure secure permissions
    put(configfile, remote_file, use_sudo=True, mode=400)
    with hide('stdout'):
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

