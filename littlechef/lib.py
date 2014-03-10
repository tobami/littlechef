#Copyright 2010-2013 Miquel Torres <tobami@gmail.com>
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
"""Library for parsing and printing role, cookbook and node information"""
import os
import json
import subprocess
import imp

from fabric import colors
from fabric.api import env
from fabric.contrib.console import confirm
from fabric.utils import abort

from littlechef import cookbook_paths
from littlechef.exceptions import FileNotFoundError

knife_installed = True


def _resolve_hostname(name):
    """Returns resolved hostname using the ssh config"""
    if env.ssh_config is None:
        return name
    elif not os.path.exists(os.path.join("nodes", name + ".json")):
        resolved_name = env.ssh_config.lookup(name)['hostname']
        if os.path.exists(os.path.join("nodes", resolved_name + ".json")):
            name = resolved_name
    return name


def get_env_host_string():
    if not env.host_string:
        abort('no node specified\nUsage: fix node:<MYNODES> <COMMAND>')
    if '@' in env.host_string:
        env.user = env.host_string.split('@')[0]
    return _resolve_hostname(env.host_string)


def env_from_template(name):
    """Returns a basic environment structure"""
    return {
        "name": name,
        "default_attributes": {},
        "json_class": "Chef::Environment",
        "chef_type": "environment",
        "description": "",
        "cookbook_versions": {}
    }


def get_environment(name):
    """Returns a JSON environment file as a dictionary"""
    if name == "_default":
        return env_from_template(name)
    filename = os.path.join("environments", name + ".json")
    try:
        with open(filename) as f:
            try:
                return json.loads(f.read())
            except ValueError as e:
                msg = 'LittleChef found the following error in'
                msg += ' "{0}":\n                {1}'.format(filename, str(e))
                abort(msg)
    except IOError:
        raise FileNotFoundError('File {0} not found'.format(filename))


def get_environments():
    """Gets all environments found in the 'environments' directory"""
    envs = []
    for root, subfolders, files in os.walk('environments'):
        for filename in files:
            if filename.endswith(".json"):
                path = os.path.join(
                    root[len('environments'):], filename[:-len('.json')])
                envs.append(get_environment(path))
    return sorted(envs, key=lambda x: x['name'])


def get_node(name, merged=False):
    """Returns a JSON node file as a dictionary"""
    if merged:
        node_path = os.path.join("data_bags", "node", name.replace('.', '_') + ".json")
    else:
        node_path = os.path.join("nodes", name + ".json")
    if os.path.exists(node_path):
        # Read node.json
        with open(node_path, 'r') as f:
            try:
                node = json.loads(f.read())
            except ValueError as e:
                msg = 'LittleChef found the following error in'
                msg += ' "{0}":\n                {1}'.format(node_path, str(e))
                abort(msg)
    else:
        print "Creating new node file '{0}.json'".format(name)
        node = {'run_list': []}
    # Add node name so that we can tell to which node it is
    node['name'] = name
    if not node.get('chef_environment'):
        node['chef_environment'] = '_default'
    return node


def get_nodes(environment=None):
    """Gets all nodes found in the nodes/ directory"""
    if not os.path.exists('nodes'):
        return []
    nodes = []
    for filename in sorted(
            [f for f in os.listdir('nodes')
             if (not os.path.isdir(f)
                 and f.endswith(".json") and not f.startswith('.'))]):
        fqdn = ".".join(filename.split('.')[:-1])  # Remove .json from name
        node = get_node(fqdn)
        if environment is None or node.get('chef_environment') == environment:
            nodes.append(node)
    return nodes


def get_nodes_with_role(role_name, environment=None):
    """Get all nodes which include a given role,
    prefix-searches are also supported

    """
    prefix_search = role_name.endswith("*")
    if prefix_search:
        role_name = role_name.rstrip("*")
    for n in get_nodes(environment):
        roles = get_roles_in_node(n, recursive=True)
        if prefix_search:
            if any(role.startswith(role_name) for role in roles):
                yield n
        else:
            if role_name in roles:
                yield n


def get_nodes_with_tag(tag, environment=None, include_guests=False):
    """Get all nodes which include a given tag"""
    nodes = get_nodes(environment)
    nodes_mapping = dict((n['name'], n) for n in nodes)
    for n in nodes:
        if tag in n.get('tags', []):
            # Remove from node mapping so it doesn't get added twice by
            # guest walking below
            try:
                del nodes_mapping[n['fqdn']]
            except KeyError:
                pass
            yield n
            # Walk guest if it is a host
            if include_guests and n.get('virtualization', {}).get('role') == 'host':
                for guest in n['virtualization']['guests']:
                    try:
                        yield nodes_mapping[guest['fqdn']]
                    except KeyError:
                        # we ignore guests which are not in the same
                        # chef environments than their hosts for now
                        pass


def get_nodes_with_recipe(recipe_name, environment=None):
    """Get all nodes which include a given recipe,
    prefix-searches are also supported

    """
    prefix_search = recipe_name.endswith("*")
    if prefix_search:
        recipe_name = recipe_name.rstrip("*")
    for n in get_nodes(environment):
        recipes = get_recipes_in_node(n)
        for role in get_roles_in_node(n, recursive=True):
            recipes.extend(get_recipes_in_role(role))
        if prefix_search:
            if any(recipe.startswith(recipe_name) for recipe in recipes):
                yield n
        else:
            if recipe_name in recipes:
                yield n


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


def print_nodes(nodes, detailed=False):
    """Prints all the given nodes"""
    found = 0
    for node in nodes:
        found += 1
        print_node(node, detailed=detailed)
    print("\nFound {0} node{1}".format(found, "s" if found != 1 else ""))


def _generate_metadata(path, cookbook_path, name):
    """Checks whether metadata.rb has changed and regenerate metadata.json"""
    global knife_installed
    if not knife_installed:
        return
    metadata_path_rb = os.path.join(path, 'metadata.rb')
    metadata_path_json = os.path.join(path, 'metadata.json')
    if (os.path.exists(metadata_path_rb) and
            (not os.path.exists(metadata_path_json) or
             os.stat(metadata_path_rb).st_mtime >
             os.stat(metadata_path_json).st_mtime)):
        error_msg = "Warning: metadata.json for {0}".format(name)
        error_msg += " in {0} is older that metadata.rb".format(cookbook_path)
        error_msg += ", cookbook attributes could be out of date\n\n"
        try:
            proc = subprocess.Popen(
                ['knife', 'cookbook', 'metadata', '-o', cookbook_path, name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            resp, error = proc.communicate()
            if ('ERROR:' in resp or 'FATAL:' in resp
                    or 'Generating metadata for' not in resp):
                if("No user specified, pass via -u or specifiy 'node_name'"
                        in error):
                    error_msg += "You need to have an up-to-date (>=0.10.x)"
                    error_msg += " version of knife installed locally in order"
                    error_msg += " to generate metadata.json.\nError "
                else:
                    error_msg += "Unkown error "
                error_msg += "while executing knife to generate "
                error_msg += "metadata.json for {0}".format(path)
                print(error_msg)
                print resp
            if env.loglevel == 'debug':
                print "\n".join(resp.split("\n")[:2])
        except OSError:
            knife_installed = False
            error_msg += "If you locally install Chef's knife tool, LittleChef"
            error_msg += " will regenerate metadata.json files automatically\n"
            print(error_msg)
        else:
            print("Generated metadata.json for {0}\n".format(path))


def get_recipes_in_cookbook(name):
    """Gets the name of all recipes present in a cookbook
    Returns a list of dictionaries

    """
    recipes = {}
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

        _generate_metadata(path, cookbook_path, name)

        # Now try to open metadata.json
        try:
            with open(os.path.join(path, 'metadata.json'), 'r') as f:
                try:
                    cookbook = json.loads(f.read())
                except ValueError as e:
                    msg = "Little Chef found the following error in your"
                    msg += " {0} file:\n  {1}".format(
                        os.path.join(path, 'metadata.json'), e)
                    abort(msg)
                # Add each recipe defined in the cookbook
                metadata_exists = True
                recipe_defaults = {
                    'description': '',
                    'version': cookbook.get('version'),
                    'dependencies': cookbook.get('dependencies', {}).keys(),
                    'attributes': cookbook.get('attributes', {})
                }
                for recipe in cookbook.get('recipes', []):
                    recipes[recipe] = dict(
                        recipe_defaults,
                        name=recipe,
                        description=cookbook['recipes'][recipe]
                    )
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
    # Add recipes found in the 'recipes' directory but not listed
    # in the metadata
    for cookbook_path in cookbook_paths:
        recipes_dir = os.path.join(cookbook_path, name, 'recipes')
        if not os.path.isdir(recipes_dir):
            continue
        for basename in os.listdir(recipes_dir):
            fname, ext = os.path.splitext(basename)
            if ext != '.rb':
                continue
            if fname != 'default':
                recipe = '%s::%s' % (name, fname)
            else:
                recipe = name
            if recipe not in recipes:
                recipes[recipe] = dict(recipe_defaults, name=recipe)
    # When a recipe has no default recipe (libraries?),
    # add one so that it is listed
    if not recipes:
        recipes[name] = dict(
            recipe_defaults,
            name=name,
            description='This cookbook has no default recipe'
        )
    return recipes.values()


def get_recipes_in_role(rolename):
    """Gets all recipes defined in a role's run_list"""
    recipes = get_recipes_in_node(_get_role(rolename))
    return recipes


def get_recipes_in_node(node):
    """Gets the name of all recipes present in the run_list of a node"""
    recipes = []
    for elem in node.get('run_list', []):
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


def get_roles_in_node(node, recursive=False, depth=0):
    """Returns a list of roles found in the run_list of a node
    * recursive: True feches roles recursively
    * depth: Keeps track of recursion depth

    """
    LIMIT = 5
    roles = []
    for elem in node.get('run_list', []):
        if elem.startswith("role"):
            role = elem.split('[')[1].split(']')[0]
            if role not in roles:
                roles.append(role)
                if recursive and depth <= LIMIT:
                    roles.extend(get_roles_in_node(_get_role(role),
                                                   recursive=True,
                                                   depth=depth + 1))
    return list(set(roles))


def _get_role(rolename):
    """Reads and parses a file containing a role"""
    path = os.path.join('roles', rolename + '.json')
    if not os.path.exists(path):
        abort("Couldn't read role file {0}".format(path))
    with open(path, 'r') as f:
        try:
            role = json.loads(f.read())
        except ValueError as e:
            msg = "Little Chef found the following error in your"
            msg += " {0}.json file:\n  {1}".format(rolename, str(e))
            abort(msg)
        role['fullname'] = rolename
        return role


def get_roles():
    """Gets all roles found in the 'roles' directory"""
    roles = []
    for root, subfolders, files in os.walk('roles'):
        for filename in files:
            if filename.endswith(".json"):
                path = os.path.join(
                    root[len('roles'):], filename[:-len('.json')])
                roles.append(_get_role(path))
    return sorted(roles, key=lambda x: x['fullname'])


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
    if detailed:
        print("    run_list: {0}".format(role.get('run_list')))
    print("")


def print_plugin_list():
    """Prints a list of available plugins"""
    print("List of available plugins:")
    for plugin in get_plugins():
        _pprint(plugin)


def get_plugins():
    """Gets available plugins by looking into the plugins/ directory"""
    if os.path.exists('plugins'):
        for filename in sorted([f for f in os.listdir('plugins')
                if not os.path.isdir(f) and f.endswith(".py")]):
            plugin_name = filename[:-3]
            try:
                plugin = import_plugin(plugin_name)
            except SystemExit as e:
                description = "Plugin has a syntax error"
            else:
                description = plugin.__doc__ or "No description found"
            yield {plugin_name: description}


def import_plugin(name):
    """Imports plugin python module"""
    path = os.path.join("plugins", name + ".py")
    try:
        with open(path, 'rb') as f:
            try:
                plugin = imp.load_module(
                    "p_" + name, f, name + '.py',
                    ('.py', 'rb', imp.PY_SOURCE)
                )
            except SyntaxError as e:
                error = "Found plugin '{0}', but it seems".format(name)
                error += " to have a syntax error: {0}".format(str(e))
                abort(error)
    except IOError:
        abort("Sorry, could not find '{0}.py' in the plugin directory".format(
              name))
    return plugin


def get_cookbook_path(cookbook_name):
    """Returns path to the cookbook for the given cookbook name"""
    for cookbook_path in cookbook_paths:
        path = os.path.join(cookbook_path, cookbook_name)
        if os.path.exists(path):
            return path
    raise IOError('Can\'t find cookbook with name "{0}"'.format(cookbook_name))


def global_confirm(question, default=True):
    """Shows a confirmation that applies to all hosts
    by temporarily disabling parallel execution in Fabric
    """
    if env.abort_on_prompts:
        return True
    original_parallel = env.parallel
    env.parallel = False
    result = confirm(question, default)
    env.parallel = original_parallel
    return result


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
