#Copyright 2010 Miquel Torres <tobami@googlemail.com>
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

# LittleChef: Configuration management using Chef Solo in a push based system
import fabric
from fabric.api import *
from fabric.contrib.files import upload_template, append
from fabric.contrib.console import confirm
import ConfigParser, os
import simplejson as json


NODEPATH = "nodes/"
APPNAME  = "littlechef"

def _readconfig():
    '''Read main fabric configuration'''
    import sys
    if sys.argv[3] == "new_deployment": return
    
    for dirname in ['nodes', 'roles', 'cookbooks', 'auth.cfg']:
        if not os.path.exists(dirname):
            msg = "You are executing 'cook' outside of a deployment directory\n"
            msg += "To create a new deployment in the current directory you can"
            msg += " type 'cook new_deployment'"
            abort(msg)
    config = ConfigParser.ConfigParser()
    config.read("auth.cfg")
    try:
        try:
            env.user = config.get('userinfo', 'user')
            if not env.user: raise ValueError
        except (ConfigParser.NoOptionError, ValueError):
            abort('You need to define a valid user in auth.cfg')
        env.password = config.get('userinfo', 'password')
    except ConfigParser.NoSectionError:
        abort('You need to define a user and password in the "userinfo" section of auth.cfg. Refer to the README for help (http://github.com/tobami/littlechef)')
    env.loglevel = "info"

_readconfig()

fabric.state.output['running'] = False

@hosts('setup')
def new_deployment():
    '''Create LittleChef directory structure (Kitchen)'''
    local('mkdir -p nodes')
    local('mkdir -p cookbooks')
    local('mkdir -p roles')
    local('touch auth.cfg')
    local('echo "[userinfo]\\nuser     = \\npassword = " > auth.cfg')

@hosts('setup')
def debug():
    '''Sets logging level to debug'''
    print "Setting logging level to 'debug'..."
    env.loglevel = 'debug'

@hosts('setup')
def node(host):
    '''Select a node'''
    if host == 'all':
        env.hosts = [node[APPNAME]['nodeid'] for node in _get_nodes()]
        if not len(env.hosts):
            abort('No nodes found')
    else:
        env.hosts = [host]

def deploy_chef(distro):
    '''Install Chef-solo on a node'''
    if not len(env.hosts):
        abort('no node specified\nUsage: cook node:MYNODE deploy_chef:MYDISTRO')
    
    distro_type = _check_supported_distro(distro)
    if not distro_type:
        abort('%s is not a supported distro' % distro)
    message = 'Are you sure you want to install Chef at the '
    message += 'nodes %s, using "%s" packages?' % (", ".join(env.hosts), distro)
    if not confirm(message):
        abort('Aborted by user')
    
    if distro_type == "debian": _apt_install(distro)
    elif distro_type == "rpm": _rpm_install(distro)
    else: abort('wrong distro type: %s' % distro_type)
    
    # Setup
    sudo('touch /etc/chef/solo.rb')
    sudo('rm /etc/chef/solo.rb')
    append('file_cache_path "/tmp/chef-solo"',
        '/etc/chef/solo.rb', use_sudo=True)
    append('cookbook_path "/tmp/chef-solo/cookbooks"',
        '/etc/chef/solo.rb', use_sudo=True)
    append('role_path "/tmp/chef-solo/roles"',
        '/etc/chef/solo.rb', use_sudo=True)
    sudo('mkdir -p /tmp/chef-solo/roles')
    
    # Copy cookbooks
    _update_cookbooks()

def recipe(recipe, save=False):
    '''Execute the given recipe,ignores existing config'''
    if not len(env.hosts):
        abort('no node specified\nUsage: cook node:MYNODE recipe:MYRECIPE')
    with hide('stdout', 'running'): hostname = run('hostname')
    print "\n== Executing recipe %s on node %s ==" % (recipe, hostname)
    configfile = hostname + ".json"
    if not os.path.exists('cookbooks/' + recipe.split('::')[0]):
        abort("Recipe '%s' not found" % recipe)
    data = {
        APPNAME: {'nodename': hostname, 'nodeid': env.host_string},
        "run_list": [ "recipe[%s]" % recipe ],
    }
    filepath = _save_config(save, data)
    _sync_node(filepath)

def role(role, save=False):
    '''Execute the given role, ignores existing config'''
    if not len(env.hosts):
        abort('no node specified\nUsage: cook node:MYNODE role:MYRECIPE')
    with hide('stdout', 'running'): hostname = run('hostname')
    print "\n== Applying role %s to node %s ==" % (role, hostname)
    if not os.path.exists('roles/' + role + '.json'):
        abort("Role '%s' not found" % role)
    data = {
        APPNAME: {'nodename': hostname, 'nodeid': env.host_string},
        "run_list": [ "role[%s]" % role ],
    }
    filepath = _save_config(save, data)
    _sync_node(filepath)

def configure():
    '''Configure node using existing config file'''
    if not len(env.hosts):
        msg = 'no node specified\n'
        msg += 'Usage:\n  cook node:MYNODE configure\n  cook node:all configure'
        abort(msg)
    with hide('stdout', 'running'): hostname = run('hostname')
    print "\n== Configuring %s ==" % hostname
    configfile = hostname + ".json"
    if not os.path.exists(NODEPATH + configfile):
        print "Warning: No config file found for %s" % hostname
        print "Warning: Chef run aborted"
        return
    _sync_node(NODEPATH + configfile)

@hosts('api')
def list_nodes():
    '''List all nodes'''
    for node in _get_nodes():
        _print_node(node)

@hosts('api')
def list_nodes_with_recipe(recipe):
    '''Show all nodes which have asigned a given recipe'''
    for node in _get_nodes():
        recipename = 'recipe[' + recipe + ']'
        if recipename in node.get('run_list'):
            _print_node(node)

@hosts('api')
def list_nodes_with_role(role):
    '''Show all nodes which have asigned a given recipe'''
    for node in _get_nodes():
        recipename = 'role[' + role + ']'
        if recipename in node.get('run_list'):
            _print_node(node)

@hosts('api')
def list_recipes():
    '''Show all available recipes'''
    for recipe in _get_recipes():
        _print_recipe(recipe)

#########################
### Private functions ###
#########################
def _get_recipes_in_cookbook(name):
    recipes = []
    try:
        with open('cookbooks/' + name + '/metadata.json', 'r') as f:
            cookbook = json.loads(f.read())
            for recipe in cookbook.get('recipes', []):
                recipes.append(
                    {
                        'name': recipe,
                        'description': cookbook['recipes'][recipe],
                        'dependencies': cookbook.get('dependencies').keys(),
                        'attributes': cookbook.get('attributes').keys(),
                    }
                )
    except IOError:
        print "Warning: invalid cookbook '%s'" % name
    return recipes

def _get_recipes():
    recipes = []
    for dirname in sorted(os.listdir('cookbooks')):
        recipes.extend(_get_recipes_in_cookbook(dirname))
    return recipes

def _print_recipe(recipe):
    '''Prety print a recipe'''
    print "\nRecipe: " + recipe['name']
    print "  description:", recipe['description']
    print "  dependencies:", ", ".join(recipe['dependencies'])
    print "  attributes:", ", ".join(recipe['attributes'])

def _apt_install(distro):
    sudo('rm /etc/apt/sources.list.d/opscode.list')
    append('deb http://apt.opscode.com/ %s main' % distro,
        '/etc/apt/sources.list.d/opscode.list', use_sudo=True)
    sudo('wget -qO - http://apt.opscode.com/packages@opscode.com.gpg.key | sudo apt-key add -')
    sudo('apt-get update')
    with hide('stdout'):
        sudo('DEBIAN_FRONTEND=noninteractive apt-get --yes install chef')
    
    # We only want chef-solo
    sudo('update-rc.d -f chef-client remove')
    with settings(hide('warnings'), warn_only=True): sudo('pkill chef-client')

def _rpm_install(distro):
    # Install the EPEL Yum Repository.
    sudo('rpm -Uvh http://download.fedora.redhat.com/pub/epel/5/i386/epel-release-5-4.noarch.rpm')
    # Install the ELFF Yum Repository.
    sudo('rpm -Uvh http://download.elff.bravenet.com/5/i386/elff-release-5-3.noarch.rpm')
    # Install Chef Solo
    sudo('yum install chef')

def _check_supported_distro(distro):
    debianbased_distros = [
        'lucid', 'karmic', 'jaunty', 'hardy', 'sid', 'squeeze', 'lenny']
    rmpbased_distros = [
        'centos', 'rhel']
    if distro in debianbased_distros:
        return 'debian'
    elif distro in rmpbased_distros:
        return 'rpm'
    else:
        return False

def _save_config(save, data):
    filepath = NODEPATH + data[APPNAME]['nodename'] + ".json"
    if os.path.exists(filepath) and not save:
        filepath = 'tmp_node.json'
    with open(filepath, 'w') as f:
        f.write(json.dumps(data))
        f.write('\n')
    return filepath

def _get_nodes():
    if not os.path.exists(NODEPATH): return []
    nodes = []
    for filename in sorted(
        [f for f in os.listdir(NODEPATH) if not os.path.isdir(f) and ".json" in f]):
        with open(NODEPATH + filename, 'r') as f:
            try:
                nodes.append(json.loads(f.read()))
            except json.decoder.JSONDecodeError:
                print "Warning: file %s contains no JSON" % filename
    return nodes

def _sync_node(filepath):
    _update_cookbooks(filepath)
    _configure_node(filepath)

def _get_recipes_in_node(node):
    recipes = []
    for a in node.get('run_list'):
        if a.startswith("recipe"):
            recipe = a.split('[')[1].split(']')[0]
            recipe = a.lstrip('recipe[').rstrip(']')
            recipes.append(recipe)
    return recipes

def _get_roles_in_node(node):
    roles = []
    for a in node.get('run_list'):
        if a.startswith("role"):
            role = a.split('[')[1].split(']')[0]
            roles.append(role)
    return roles

def _print_node(node):
    print "\n" + node[APPNAME]['nodename']
    for recipe in _get_recipes_in_node(node):
        print "  Recipe:", recipe
        print "    attributes: " + str(node.get(recipe))
    for role in _get_roles_in_node(node):
        print "  Role:", role
        print "    attributes: " + str(node.get(role))

def _configure_node(configfile):
    print "Uploading node.json..."
    with hide('running'):
        upload_template(
            configfile,
            '/etc/chef/node.json',
            context={},
            use_sudo=True
        )
        print "Cooking..."
        with settings(hide('warnings'), warn_only=True):
            output = sudo('chef-solo -l %s -j /etc/chef/node.json' % env.loglevel)#
            if "ERROR:" in output:
                print "\nERROR: A problem occurred while executing chef-solo"
            else:
                print "\nSUCCESS: Node correctly configured"

def _update_cookbooks(configfile):
    # Clean up node
    sudo('rm -rf /tmp/chef-solo/cookbooks')
    sudo('rm -rf /tmp/chef-solo/roles')
    
    print "Uploading cookbooks..."
    cookbooks = []
    with open(configfile, 'r') as f:
        node = json.loads(f.read())
    
    # Fetch cookbooks needed for recipes
    for recipe in _get_recipes_in_node(node):
        recipe = recipe.split('::')[0]
        if recipe not in cookbooks:
            cookbooks.append(recipe)
    
    # Fetch cookbooks needed for role recipes
    for role in _get_roles_in_node(node):
        with open('roles/' + role + '.json', 'r') as f:
            roles = json.loads(f.read())
            # Check that name is correct
            if roles.get("name") != role:
                print "Warning: role '%s' has an incorrect name defined" % role
            # Reuse _get_recipes_in_node to extract recipes in a role
            for recipe in _get_recipes_in_node(roles):
                recipe = recipe.split('::')[0]
                if recipe not in cookbooks:
                    cookbooks.append(recipe)
    
    # Fetch dependencies
    for cookbook in cookbooks:
        for recipe in _get_recipes_in_cookbook(cookbook):
            # Only care about base recipe
            if len(recipe['name'].split('::')) > 1: continue
            for dep in recipe['dependencies']:
                if dep not in cookbooks:
                    if not os.path.exists('cookbooks/' + dep):
                        print "Warning: Possible error because of missing dependency"
                        print "         Cookbook '%s' not found" % dep
                    else:
                        cookbooks.append(dep)
    
    _upload_and_unpack(['cookbooks/' + f for f in cookbooks])
    
    print "Uploading roles..."
    _upload_and_unpack(['roles'])

def _upload_and_unpack(source):
    with hide('running'):
        local('tar czf temp.tar.gz %s' % " ".join(source))
        put('temp.tar.gz', 'temp.tar.gz')
        sudo('mv temp.tar.gz /tmp/chef-solo/')
        local('rm temp.tar.gz')
        with cd('/tmp/chef-solo/'):
            sudo('tar -xzf temp.tar.gz')
            sudo('rm temp.tar.gz')
