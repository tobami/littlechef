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
"""library for parsing and printing role, cookbook and node information"""
import os
import simplejson as json

from fabric import colors
from fabric.api import env, settings
from fabric.utils import abort

from littlechef.settings import cookbook_paths


def get_nodes():
    """Gets all nodes found in the nodes/ directory"""
    if not os.path.exists('nodes/'):
        return []
    nodes = []
    for filename in sorted([f for f in os.listdir('nodes/')
                                if not os.path.isdir(f) and ".json" in f
                                    and not f.startswith('.')]):
        hostname = ".".join(filename.split('.')[:-1])  # Remove .json from name
        node = get_node(hostname)
        # Add node name so that we can tell to which node the data belongs to
        node['name'] = hostname
        nodes.append(node)
    return nodes


def get_node(name):
    node_path = os.path.join("nodes", name + ".json")
    if not os.path.exists(node_path):
        return {'run_list': []}
    # Read node.json
    with open(node_path, 'r') as f:
        try:
            node = json.loads(f.read())
        except json.JSONDecodeError as e:
            msg = 'LittleChef found the following error in'
            msg += ' "{0}":\n                {1}'.format(node_path, str(e))
            abort(msg)
    return node


def print_node(node, detailed=False):
    """Pretty prints the given node"""
    nodename = node['name']
    print(colors.yellow("\n" + nodename))
    # Roles
    if detailed:
        for role in get_roles_in_node(node):
            print_role(_get_role(role), detailed=False)
    else:
        print('  Roles: {0}'.format(", ".join(get_roles_in_node(node))))
    # Recipes
    if detailed:
        for recipe in get_recipes_in_node(node):
            print "  Recipe:", recipe
            print "    attributes: {0}".format(node.get(recipe, ""))
    else:
        print('  Recipes: {0}'.format(", ".join(get_recipes_in_node(node))))
    # Node attributes
    print "  Node attributes:"
    for attribute in node.keys():
        if attribute == "run_list" or attribute == "name":
            continue
        print "    {0}: {1}".format(attribute, node[attribute])


def get_recipes_in_cookbook(name):
    """Gets the name of all recipes present in a cookbook
    Returns a list of dictionaries

    """
    recipes = []
    path = None
    cookbook_exists = False
    metadata_exists = False
    for cookbook_path in cookbook_paths:
        path = os.path.join(cookbook_path, name)
        path_exists = os.path.exists(path)
        # cookbook exists if present in any of the cookbook paths
        cookbook_exists = cookbook_exists or path_exists
        if not path_exists:
            continue
        # Now try to open metadata.json
        try:
            with open(os.path.join(path, 'metadata.json'), 'r') as f:
                try:
                    cookbook = json.loads(f.read())
                except json.JSONDecodeError as e:
                    msg = "Little Chef found the following error in your"
                    msg += " {0}.json file:\n  {1}".format(
                        os.path.join(path, 'metadata.json'), e)
                    abort(msg)
                # Add each recipe defined in the cookbook
                metadata_exists = True
                for recipe in cookbook.get('recipes', []):
                    recipes.append({
                        'name': recipe,
                        'description': cookbook['recipes'][recipe],
                        'version': cookbook.get('version'),
                        'dependencies': cookbook.get('dependencies', {}).keys(),
                        'attributes': cookbook.get('attributes', {}),
                        })
                # When a recipe has no default recipe (libraries?),
                # add one so that it is listed
                if not recipes:
                    recipes.append({
                        'name': name,
                        'description': 'This cookbook has no default recipe',
                        'version': cookbook.get('version'),
                        'dependencies': cookbook.get('dependencies', {}).keys(),
                        'attributes': cookbook.get('attributes', {})
                    })
            # Cookbook metadata.json was found, don't try next cookbook path
            # because metadata.json in site-cookbooks has preference
            break
        except IOError:
            # metadata.json was not found, try next cookbook_path
            pass
    if not cookbook_exists:
        abort('Unable to find cookbook "{0}"'.format(name))
    elif not metadata_exists:
        abort('Cookbook "{0}" has no metadata.json'.format(name))
    return recipes


def get_recipes_in_role(rolename):
    """Gets all recipes defined in a role's run_list"""
    recipes = []
    role = _get_role(rolename)
    recipes.extend(get_recipes_in_node(role))
    return recipes


def get_recipes_in_node(node):
    """Gets the name of all recipes present in the run_list of a node"""
    recipes = []
    for elem in node.get('run_list'):
        if elem.startswith("recipe"):
            recipe = elem.split('[')[1].split(']')[0]
            recipes.append(recipe)
    return recipes


def get_recipes():
    """Gets all recipes found in the cookbook directories"""
    dirnames = set()
    for path in cookbook_paths:
        dirnames.update([d for d in os.listdir(path) if os.path.isdir(
                            os.path.join(path, d)) and not d.startswith('.')])
    recipes = []
    for dirname in dirnames:
        recipes.extend(get_recipes_in_cookbook(dirname))
    return sorted(recipes, key=lambda x: x['name'])


def print_recipe(recipe):
    """Pretty prints the given recipe"""
    print(colors.yellow("\n{0}".format(recipe['name'])))
    print "  description:  {0}".format(recipe['description'])
    print "  version:      {0}".format(recipe['version'])
    print "  dependencies: {0}".format(", ".join(recipe['dependencies']))
    print "  attributes:   {0}".format(", ".join(recipe['attributes']))


def get_roles_in_role(rolename):
    """Gets all roles defined in a role's run_list"""
    return get_roles_in_node(_get_role(rolename))


def get_roles_in_node(node):
    """Gets the name of all roles found in the run_list of a node"""
    roles = []
    for elem in node.get('run_list'):
        if elem.startswith("role"):
            role = elem.split('[')[1].split(']')[0]
            roles.append(role)
    return roles


def _get_role(rolename):
    """Reads and parses a file containing a role"""
    path = 'roles/' + rolename + '.json'
    if not os.path.exists(path):
        abort("Couldn't read role file {0}".format(path))
    with open(path, 'r') as f:
        try:
            role = json.loads(f.read())
        except json.JSONDecodeError as e:
            msg = "Little Chef found the following error in your"
            msg += " {0}.json file:\n  {1}".format(rolename, str(e))
            abort(msg)
        role['fullname'] = rolename
        return role


def get_roles():
    """Gets all roles found in the roles/ directory"""
    roles = []
    for root, subfolders, files in os.walk('roles/'):
        for filename in files:
            if filename.endswith(".json"):
                path = os.path.join(
                    root[len('roles/'):], filename[:-len('.json')])
                roles.append(_get_role(path))
    return sorted(roles, key=lambda x: x['fullname'])


def get_nodes_with_roles(rolename):
    """ Get all nodes which include a given role,
    prefix-searches are also supported
    """
    prefix_search = rolename.endswith("*")
    if prefix_search:
        rolename = rolename.rstrip("*")
    for n in get_nodes():
        if prefix_search:
            roles = get_roles_in_node(n)
            if any(role.startswith(rolename) for role in roles):
                yield n
        else:
            if rolename in get_roles_in_node(n):
                yield n


def print_role(role, detailed=True):
    """Pretty prints the given role"""
    if detailed:
        print(colors.yellow(role.get('fullname')))
    else:
        print("  Role: {0}".format(role.get('fullname')))
    if detailed:
        print("    description: {0}".format(role.get('description')))
    if 'default_attributes' in role:
        print("    default_attributes:")
        _pprint(role['default_attributes'])
    if 'override_attributes' in role:
        print("    override_attributes:")
        _pprint(role['override_attributes'])
    print("")


def get_cookbook_path(cookbook_name):
    """Returns path to the cookbook for the given cookbook name"""
    for cookbook_path in cookbook_paths:
        path = os.path.join(cookbook_path, cookbook_name)
        if os.path.exists(path):
            return path
    raise IOError('Can\'t find cookbook with name "{0}"'.format(cookbook_name))


def _pprint(dic):
    """Prints a dictionary with one indentation level"""
    for key, value in dic.items():
        print("        {0}: {1}".format(key, value))


def print_header(string):
    """Prints a colored header"""
    print(colors.yellow("\n== {0} ==".format(string)))


def get_margin(length):
    """Add enough tabs to align in two columns"""
    if length > 23:
        margin_left = "\t"
        chars = 1
    elif length > 15:
        margin_left = "\t\t"
        chars = 2
    elif length > 7:
        margin_left = "\t\t\t"
        chars = 3
    else:
        margin_left = "\t\t\t\t"
        chars = 4
    return margin_left


def credentials(*args, **kwargs):
    """Override default credentials with contents of .ssh/config,
    if appropriate
    """
    if env.ssh_config:
        credentials = env.ssh_config.lookup(env.host)
        # translate from paramiko params to fabric params
        if 'identityfile' in credentials:
            credentials['key_filename'] = credentials['identityfile']
        credentials.update(kwargs)
    else:
        credentials = kwargs
    return settings(*args, **credentials)
