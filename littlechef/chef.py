#Copyright 2010-2012 Miquel Torres <tobami@googlemail.com>
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
from littlechef.settings import cookbook_paths
from littlechef import LOGFILE, enable_logs as ENABLE_LOGS


# Path to local patch
basedir = os.path.abspath(os.path.dirname(__file__).replace('\\', '/'))


def save_config(node, force=False):
    """Saves node configuration
    if no nodes/hostname.json exists, or force=True, it creates one
    it also saves to tmp_node.json
    """
    filepath = os.path.join("nodes", env.host_string + ".json")
    tmp_filename = 'tmp_{0}.json'.format(env.host_string)
    files_to_create = [tmp_filename]
    if not os.path.exists(filepath) or force:
        # Only save to nodes/ if there is not already a file
        print "Saving node configuration to {0}...".format(filepath)
        files_to_create.append(filepath)
    for node_file in files_to_create:
        with open(node_file, 'w') as f:
            f.write(json.dumps(node, indent=4))
    return tmp_filename


def _get_ipaddress(node):
    """Adds the ipaddress attribute to the given node object if not already
    present and it is correctly given by ohai
    Returns True if ipaddress is added, False otherwise
    """
    if "ipaddress" not in node:
        with settings(hide('stdout'), warn_only=True):
            output = sudo('ohai ipaddress')
        if output.succeeded:
            try:
                node['ipaddress'] = json.loads(output)[0]
            except json.JSONDecodeError:
                abort("Could not parse ohai's output for ipaddress"
                      ":\n  {0}".format(output))
            return True
    return False


def sync_node(node):
    """Builds, synchronizes and configures a node.
    It also injects the ipaddress to the node's config file if not already
    existent.
    """
    if node.get('dummy'):
        lib.print_header("Skipping dummy: {0}".format(env.host))
        return
    # Get merged attributes
    current_node = _build_node_data_bag()
    with lib.credentials():
        # Always configure Chef Solo
        solo.configure(current_node)
        ipaddress = _get_ipaddress(node)
    # Everything was configured alright, so save the node configuration
    # This is done without credentials, so that we keep the node name used
    # by the user and not the hostname or IP translated by .ssh/config
    filepath = save_config(node, ipaddress)
    with lib.credentials():
        try:
            # Synchronize the kitchen directory
            _synchronize_node(filepath, node)
            # Execute Chef Solo
            _configure_node()
        finally:
            _remove_local_node_data_bag()
            _node_cleanup()


def _synchronize_node(configfile, node):
    """Performs the Synchronize step of a Chef run:
    Uploads all cookbooks, all roles and all databags to a node and add the
    patch for data bags

    Returns the node object of the node which is about to be configured,
    or None if this node object cannot be found.
    """
    print "Synchronizing node, cookbooks, roles and data bags..."
    # First upload node.json
    remote_file = '/etc/chef/node.json'
    put(configfile, remote_file, use_sudo=True, mode=400)
    root_user = "root"
    if node.get('platform') in ["freebsd", "mac_os_x"]:
        root_user = "wheel"
    with hide('stdout'):
        sudo('chown root:{0} {1}'.format(root_user, remote_file))
    # Remove local temporary node file
    os.remove(configfile)
    # Synchronize kitchen
    rsync_project(
        env.node_work_path, './cookbooks ./data_bags ./roles ./site-cookbooks',
        exclude=('*.svn', '.bzr*', '.git*', '.hg*'),
        delete=True,
        extra_opts="-q",
    )
    _add_search_patch()


def build_dct(dic, keys, value):
    """Builds a dictionary with arbitrary depth out of a key list"""
    key = keys.pop(0)
    if len(keys):
        dic.setdefault(key, {})
        build_dct(dic[key], keys, value)
    else:
        # Transform cookbook default attribute strings into proper booleans
        if value == "false":
            value = False
        elif value == "true":
            value = True
        # It's a leaf, assign value
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


def _add_automatic_attributes(node):
    """Adds some of Chef's automatic attributes:
        http://wiki.opscode.com/display/chef/Recipes#Recipes
        -CommonAutomaticAttributes

    """
    node['fqdn'] = node['name']
    node['hostname'] = node['fqdn'].split('.')[0]
    node['domain'] = ".".join(node['fqdn'].split('.')[1:])


def _add_merged_attributes(node, all_recipes, all_roles):
    """Merges attributes from cookbooks, node and roles

    Chef Attribute precedence:
    http://wiki.opscode.com/display/chef/Attributes#Attributes
    -AttributeTypeandPrecedence
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
        found = False
        for r in all_recipes:
            if recipe == r['name']:
                found = True
                for attr in r['attributes']:
                    if r['attributes'][attr].get('type') == "hash":
                        value = {}
                    else:
                        value = r['attributes'][attr].get('default')
                    # Attribute dictionaries are defined as a single
                    # compound key. Split and build proper dict
                    build_dct(attributes, attr.split("/"), value)
        if not found:
            error = "Could not find recipe '{0}' while ".format(recipe)
            error += "building node data bag for '{0}'".format(node['name'])
            abort(error)

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
    # Merge back to the original node object
    node.update(attributes)


def _build_node_data_bag():
    """Builds one 'node' data bag item per file found in the 'nodes' directory

    Automatic attributes for a node item:
        'id': It adds data bag 'id', same as filename but with underscores
        'name': same as the filename
        'fqdn': same as the filename (LittleChef filenames should be fqdns)
        'hostname': Uses the first part of the filename as the hostname
            (until it finds a period) minus the .json extension
        'domain': filename minus the first part of the filename (hostname)
            minus the .json extension
    In addition, it will contain the merged attributes from:
        All default cookbook attributes corresponding to the node
        All attributes found in nodes/<item>.json file
        Default and override attributes from all roles

    Returns the node object of the node which is about to be configured, or
    None if this node object cannot be found.

    """
    current_node = None
    nodes = lib.get_nodes()
    node_data_bag_path = os.path.join('data_bags', 'node')
    # In case there are leftovers
    _remove_local_node_data_bag()
    os.makedirs(node_data_bag_path)
    all_recipes = lib.get_recipes()
    all_roles = lib.get_roles()
    for node in nodes:
        # Dots are not allowed (only alphanumeric), substitute by underscores
        node['id'] = node['name'].replace('.', '_')

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

        # Add node attributes
        _add_merged_attributes(node, all_recipes, all_roles)
        _add_automatic_attributes(node)

        # Save node data bag item
        with open(os.path.join(
                    'data_bags', 'node', node['id'] + '.json'), 'w') as f:
            f.write(json.dumps(node))
        if node['name'] == env.host_string:
            current_node = node
    return current_node


def _remove_local_node_data_bag():
    """Removes generated 'node' data_bag locally"""
    node_data_bag_path = os.path.join('data_bags', 'node')
    if os.path.exists(node_data_bag_path):
        shutil.rmtree(node_data_bag_path)


def _remove_remote_node_data_bag():
    """Removes generated 'node' data_bag from the remote node"""
    node_data_bag_path = os.path.join(env.node_work_path, 'data_bags', 'node')
    if exists(node_data_bag_path):
        sudo("rm -rf {0}".format(node_data_bag_path))


def _node_cleanup():
    if env.loglevel is not "debug":
        with hide('running', 'stdout'):
            _remove_remote_node_data_bag()
            with settings(warn_only=True):
                sudo("rm '/etc/chef/node.json'")


def _add_search_patch():
    """ Adds chef_solo_search_lib cookbook, which provides a library to read
    and search data bags

    """
    # Create extra cookbook dir
    lib_path = os.path.join(
        env.node_work_path, cookbook_paths[0], 'chef_solo_search_lib', 'libraries')
    with hide('running', 'stdout'):
        sudo('mkdir -p {0}'.format(lib_path))
    # Add search and environment patch to the node's cookbooks
    for filename in ('search.rb', 'parser.rb', 'environment.rb'):
        put(os.path.join(basedir, filename),
            os.path.join(lib_path, filename), use_sudo=True)


def _configure_node():
    """Exectutes chef-solo to apply roles and recipes to a node"""
    print("\nCooking...")
    # Backup last report
    with settings(hide('stdout', 'warnings', 'running'), warn_only=True):
        sudo("mv {0} {0}.1".format(LOGFILE))
    # Build chef-solo command
    cmd = 'chef-solo -l {0} -j /etc/chef/node.json'.format(env.loglevel)
    if ENABLE_LOGS:
        cmd += ' | tee {0}'.format(LOGFILE)
    if env.loglevel == "debug":
        print(
            "Executing Chef Solo with the following command:\n{0}".format(cmd))
    with settings(hide('warnings', 'running'), warn_only=True):
        output = sudo(cmd)
    if (output.failed or "FATAL: Stacktrace dumped" in output or
            ("Chef Run complete" not in output and
            "Report handlers complete" not in output)):
        if 'chef-solo: command not found' in output:
            print(
                colors.red(
                    "\nFAILED: Chef Solo is not installed on this node"))
            print(
                "Type 'fix nodes:{0} deploy_chef' to install it".format(
                    env.host))
            abort("")
        else:
            print(colors.red(
                "\nFAILED: chef-solo could not finish configuring the node\n"))
            import sys
            sys.exit(1)
    else:
        print(colors.green("\nSUCCESS: Node correctly configured"))
