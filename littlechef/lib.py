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
from fabric.utils import abort


def get_nodes():
    """Gets all nodes found in the nodes/ directory"""
    if not os.path.exists('nodes/'):
        return []
    nodes = []
    for filename in sorted(
        [f for f in os.listdir('nodes/') if not os.path.isdir(f) and ".json" in f]):
        with open('nodes/' + filename, 'r') as f:
            try:
                node = json.loads(f.read())
                # Don't append "nodename" to the root namespace
                # because it could colide with some cookbook's attribute
                node['littlechef'] = {'nodename': ".".join(filename.split('.')[:-1])}
                nodes.append(node)
            except json.decoder.JSONDecodeError as e:
                msg = "Little Chef found the following error in your"
                msg += " {0} file:\n  {1}".format(filename, e)
                abort(msg)
    return nodes


def print_node(node):
    """Pretty prints the given node"""
    nodename = node['littlechef']['nodename']
    print(colors.yellow("\n" + nodename))
    for recipe in get_recipes_in_node(node):
        print "  Recipe:", recipe
        print "    attributes: " + str(node.get(recipe, ""))
    for role in get_roles_in_node(node):
        print_role(_get_role(role), detailed=False)

    print "  Node attributes:"
    for attribute in node.keys():
        if attribute == "run_list" or attribute == "littlechef":
            continue
        print "    {0}: {1}".format(attribute, node[attribute])


def get_recipes_in_cookbook(name, cookbook_paths):
    """Gets the name of all recipes present in a cookbook"""
    recipes = []
    path = None
    for cookbook_path in cookbook_paths:
        path = '{0}/{1}/metadata.json'.format(cookbook_path, name)
        try:
            with open(path, 'r') as f:
                try:
                    cookbook = json.loads(f.read())
                    for recipe in cookbook.get('recipes', []):
                        recipes.append(
                            {
                                'name': recipe,
                                'description': cookbook['recipes'][recipe],
                                'version': cookbook.get('version'),
                                'dependencies': cookbook.get('dependencies').keys(),
                                'attributes': cookbook.get('attributes').keys(),
                            }
                        )
                except json.decoder.JSONDecodeError, e:
                    print e
                    msg = "Little Chef found the following error in your"
                    msg += " {0} file:\n  {1}".format(path, e)
                    abort(msg)
            break
        except IOError:
            None
    if not recipes:
        abort('Unable to find cookbook "{0}" with metadata.json'.format(name))
    return recipes


def get_recipes_in_node(node):
    """Gets the name of all recipes present in the run_list of a node"""
    recipes = []
    for elem in node.get('run_list'):
        if elem.startswith("recipe"):
            recipe = elem.split('[')[1].split(']')[0]
            recipes.append(recipe)
    return recipes


def get_recipes(cookbook_paths):
    """Gets all recipes found in the cookbooks/ directory"""
    recipes = []
    for dirname in sorted(
        [d for d in os.listdir('cookbooks') if os.path.isdir(
            os.path.join('cookbooks', d)) and not d.startswith('.')]):
        recipes.extend(get_recipes_in_cookbook(dirname, cookbook_paths))
    return recipes


def print_recipe(recipe):
    """Pretty prints the given recipe"""
    print(colors.yellow("\n{0}".format(recipe['name'])))
    print "  description:  {0}".format(recipe['description'])
    print "  version:      {0}".format(recipe['version'])
    print "  dependencies: {0}".format(", ".join(recipe['dependencies']))
    print "  attributes:   {0}".format(", ".join(recipe['attributes']))


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
        except json.decoder.JSONDecodeError as e:
            msg = "Little Chef found the following error in your"
            msg += " {0} file:\n  {0}".format(rolename, str(e))
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
    return roles


def print_role(role, detailed=True):
    """Pretty prints the given role"""
    if detailed:
        print(colors.yellow(role.get('fullname')))
    else:
        print("  Role: {0}".format(role.get('fullname')))
    if detailed:
        print("    description: {0}".format(role.get('description')))
    print detailed
    if 'default_attributes' in role:
        print("    default_attributes:")
        _pprint(role['default_attributes'])
    if 'override_attributes' in role:
        print("    override_attributes:")
        _pprint(role['override_attributes'])
    print("")


def get_cookbook_path(cookbook_name, cookbook_paths):
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
