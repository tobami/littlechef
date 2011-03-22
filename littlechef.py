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

'''LittleChef: Configuration Management using Chef without a Chef Server'''
import fabric
from fabric.api import *
from fabric.contrib.files import append, exists
from fabric.contrib.console import confirm
import ConfigParser, os, sys
import simplejson as json


NODEPATH = "nodes/"
APPNAME  = "littlechef"

env.loglevel = "info"
fabric.state.output['running'] = False

@hosts('setup')
def debug():
    '''Sets logging level to debug'''
    print "Setting Chef Solo log level to 'debug'..."
    env.loglevel = 'debug'

@hosts('setup')
def new_deployment():
    '''Create LittleChef directory structure (Kitchen)'''
    def _mkdir(d):
        if not os.path.exists(d):
            os.mkdir(d)
            print "%s/ directory created..." % d
    
    _mkdir("nodes")
    _mkdir("cookbooks")
    _mkdir("roles")
    if not os.path.exists("auth.cfg"):
        with open("auth.cfg", "w") as authfh:
            print >>authfh, "[userinfo]"
            print >>authfh, "user = "
            print >>authfh, "password = "
            print >>authfh, "keypair-file = "
            print "auth.cfg file created..."

@hosts('setup')
def node(host):
    '''Select a node'''
    if host == 'all':
        for node in _get_nodes():
            env.hosts.append(node[APPNAME]['nodename'])
        if not len(env.hosts):
            abort('No nodes found')
    else:
        env.hosts = [host]

def deploy_chef(gems="no", ask="yes"):
    '''Install chef-solo on a node'''
    # Do some checks
    if not env.host_string:
        abort('no node specified\nUsage: cook node:MYNODE deploy_chef:MYDISTRO')
    
    distro_type, distro = _check_distro()
    print
    message = 'Are you sure you want to install Chef at the node %s' % env.host_string
    if gems == "yes":
        message += ', using gems for "%s"?' % distro
    else:
        message += ', using "%s" packages?' % distro
    if ask != "no" and not confirm(message):
        abort('Aborted by user')
    
    if distro_type == "debian":
        if gems == "yes":
            _gem_apt_install()
        else:
            _apt_install(distro)
    elif distro_type == "rpm":
        if gems == "yes":
            _gem_rpm_install()
        else:
            _rpm_install()
    else:
        abort('wrong distro type: %s' % distro_type)
    
    # Chef Solo Setup
    run('touch solo.rb', pty=True)
    append('file_cache_path "/tmp/chef-solo"', 'solo.rb')
    append('cookbook_path "/tmp/chef-solo/cookbooks"', 'solo.rb')
    append('role_path "/tmp/chef-solo/roles"', 'solo.rb')
    sudo('mkdir -p /etc/chef', pty=True)
    sudo('mv solo.rb /etc/chef/', pty=True)
    sudo('mkdir -p /tmp/chef-solo', pty=True)

def recipe(recipe, save=False):
    '''Execute the given recipe, ignores existing config unless save=True'''
    # Do some checks
    if not env.host_string:
        abort('no node specified\nUsage: cook node:MYNODE recipe:MYRECIPE')
    
    print "\n== Executing recipe %s on node %s ==" % (recipe, env.host_string)
    
    if not os.path.exists('cookbooks/' + recipe.split('::')[0]):
        abort('Cookbook "%s" not found' % recipe)
    
    # Now create configuration and sync node
    data = { "run_list": [ "recipe[%s]" % recipe ] }
    filepath = _save_config(save, data, env.host_string)
    _sync_node(filepath)

def role(role, save=False):
    '''Execute the given role, ignores existing config unless save=True'''
    # Do some checks
    if not env.host_string:
        abort('no node specified\nUsage: cook node:MYNODE role:MYROLE')
    
    print "\n== Applying role %s to node %s ==" % (role, env.host_string)
    if not os.path.exists('roles/' + role + '.json'):
        if os.path.exists('roles/' + role + '.rb'):
            abort("Role '%s' only found as '%s.rb'. It should be in json format." % (role, role))
        else:
            abort("Role '%s' not found" % role)
    
    # Now create configuration and sync node
    data = { "run_list": [ "role[%s]" % role ] }
    filepath = _save_config(save, data, env.host_string)
    _sync_node(filepath)

def configure():
    '''Configure node using existing config file'''
    # Do some checks
    if not env.host_string:
        msg = 'no node specified\n'
        msg += 'Usage:\n  cook node:MYNODE configure\n  cook node:all configure'
        abort(msg)
    
    print "\n== Configuring %s ==" % env.host_string
    
    configfile = env.host_string + ".json"
    if not os.path.exists(NODEPATH + configfile):
        print "Warning: No config file found for %s" % env.host_string
        print "Warning: Chef run aborted"
        return
    
    # Configure node
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
        if recipe in _get_recipes_in_node(node):
            _print_node(node)
        else:
            for role in _get_roles_in_node(node):
                with open('roles/' + role + '.json', 'r') as f:
                    roles = json.loads(f.read())
                    # Reuse _get_recipes_in_node to extract recipes in a role
                    if recipe in _get_recipes_in_node(roles):
                        _print_node(node)
                        break

@hosts('api')
def list_nodes_with_role(role):
    '''Show all nodes which have asigned a given recipe'''
    for node in _get_nodes():
        recipename = 'role[' + role + ']'
        if recipename in node.get('run_list'):
            _print_node(node)

@hosts('api')
def list_recipes():
    '''Show a list of all available recipes'''
    for recipe in _get_recipes():
        margin_left = _get_margin(len(recipe['name']))
        print("{0}:{1}{2}".format(
            recipe['name'], margin_left, recipe['description']))

@hosts('api')
def list_recipes_detailed():
    '''Show a list of all available recipes'''
    for recipe in _get_recipes():
        _print_recipe(recipe)

@hosts('api')
def list_roles():
    '''Show a list of all available roles'''
    for role in _get_roles():
        margin_left = _get_margin(len(role['fullname']))
        print("{0}:{1}{2}".format(
            role['fullname'], margin_left, role['description']))

@hosts('api')
def list_roles_detailed():
    '''Show a list of all available roles'''
    for role in _get_roles():
        _print_role(role)

# Check that user is cooking inside a kitchen and configure authentication #
def _readconfig():
    '''Configure environment'''
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
        env.key_filename = config.get('userinfo','keypair-file')
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

def _get_margin(length):
    '''Add enough tabs to align in two columns'''
    margin_left = "\t"
    numtabs = 3 - (length + 1)/8
    if numtabs < 0:
        numtabs = 0
    for i in range(numtabs):
        margin_left += "\t"
    return margin_left

############################
### Chef Solo deployment ###
############################
def _check_distro():
    '''Check that the given distro is supported and return the distro type'''
    debian_distros = ['sid', 'squeeze', 'lenny']
    ubuntu_distros = ['maverik', 'lucid', 'karmic', 'jaunty', 'hardy']
    rpm_distros = ['centos', 'rhel', 'sl']
    
    with settings(
        hide('warnings', 'running', 'stdout', 'stderr'),
        warn_only=True
        ):
        
        output = sudo('cat /etc/issue', pty=True)
        if 'Debian GNU/Linux 5.0' in output:
            distro = "lenny"
            distro_type = 'debian'
        elif 'Debian GNU/Linux 6.0' in output:
            distro = "squeeze"
            distro_type = 'debian'
        elif 'Ubuntu' in output:
            distro = sudo('lsb_release -c', pty=True).split('\t')[-1]
            distro_type = 'debian'
        elif 'CentOS' in output:
            distro = "CentOS"
            distro_type = 'rpm'
        elif 'Red Hat Enterprise Linux' in output:
            distro = "Red Hat"
            distro_type = 'rpm'
        elif 'Scientific Linux SL' in output:
            distro = "Scientific Linux"
            distro_type = 'rpm'
        else:
            print "Currently supported distros are:"
            print "  Debian: " + ", ".join(debian_distros)
            print "  Ubuntu: " + ", ".join(ubuntu_distros)
            print "  RHEL: " + ", ".join(rpm_distros)
            abort("Unsupported distro " + run('cat /etc/issue', pty=True))
    return distro_type, distro

def _gem_install():
    '''Install Chef from gems'''
    run(
        'wget http://production.cf.rubygems.org/rubygems/rubygems-1.3.7.tgz',
        pty=True
    )
    run('tar zxf rubygems-1.3.7.tgz', pty=True)
    with cd("rubygems-1.3.7"):
        sudo('ruby setup.rb --no-format-executable', pty=True)
    sudo('rm -rf rubygems-1.3.7 rubygems-1.3.7.tgz')
    sudo('gem install --no-rdoc --no-ri chef', pty=True)

def _gem_apt_install():
    '''Install Chef from gems for apt based distros'''
    sudo("DEBIAN_FRONTEND=noninteractive apt-get --yes install ruby ruby-dev libopenssl-ruby irb build-essential wget ssl-cert", pty=True)
    _gem_install()

def _gem_rpm_install():
    '''Install chef from gems for rpm based distros'''
    _add_rpm_repos()
    with show('running'):
        sudo('yum -y install ruby ruby-shadow gcc gcc-c++ ruby-devel wget', pty=True)
    _gem_install()

def _apt_install(distro):
    '''Install chef for debian based distros'''
    sudo('apt-get --yes install wget', pty=True)
    append('deb http://apt.opscode.com/ %s main' % distro, 'opscode.list')
    sudo('mv opscode.list /etc/apt/sources.list.d/', pty=True)
    gpg_key = "http://apt.opscode.com/packages@opscode.com.gpg.key"
    sudo('wget -qO - %s | sudo apt-key add -' % gpg_key, pty=True)
    with hide('stdout'):
        sudo('apt-get update', pty=True)
    with show('running'):
        sudo('DEBIAN_FRONTEND=noninteractive apt-get --yes install chef', pty=True)
    
    # We only want chef-solo, kill chef-client and remove it from init process
    sudo('update-rc.d -f chef-client remove', pty=True)
    with settings(hide('warnings'), warn_only=True):
        sudo('pkill chef-client', pty=True)

def _add_rpm_repos():
    '''Add EPEL and ELFF'''
    with show('running'):
        # Install the EPEL Yum Repository.
        with settings(hide('warnings'), warn_only=True):
            output = sudo('rpm -Uvh http://download.fedora.redhat.com/pub/epel/5/i386/epel-release-5-4.noarch.rpm', pty=True)
            installed = "package epel-release-5-4.noarch is already installed"
            if output.failed and installed not in output:
                abort(output)
        # Install the ELFF Yum Repository.
        with settings(hide('warnings'), warn_only=True):
            output = sudo('rpm -Uvh http://download.elff.bravenet.com/5/i386/elff-release-5-3.noarch.rpm', pty=True)
            
            installed = "package elff-release-5-3.noarch is already installed"
            if output.failed and installed not in output:
                abort(output)

def _rpm_install():
    '''Install chef for rpm based distros'''
    _add_rpm_repos()
    with show('running'):
        # Install Chef Solo
        sudo('yum -y install chef', pty=True)

######################################
### Node configuration and syncing ###
######################################
def _save_config(save, data, hostname):
    '''Saves node configuration either to tmp_node.json or to hostname.json'''
    filepath = NODEPATH + hostname + ".json"
    if os.path.exists(filepath) and not save:
        filepath = 'tmp_node.json'
    
    with open(filepath, 'w') as f:
        f.write(json.dumps(data, indent=4))
        f.write('\n')
    return filepath

def _sync_node(filepath):
    '''Uploads cookbooks and configures a node'''
    _update_cookbooks(filepath)
    _configure_node(filepath)

def _configure_node(configfile):
    '''Exectutes chef-solo to apply roles and recipes to a node'''
    print "Uploading node.json..."
    with hide('running'):
        put(configfile, configfile.split("/")[-1])
        sudo('mv %s /etc/chef/node.json' % configfile.split("/")[-1], pty=True),
        
        print "\n== Cooking... ==\n"
        with settings(hide('warnings'), warn_only=True):
            output = sudo(
                'chef-solo -l %s -j /etc/chef/node.json' % env.loglevel,
                pty=True
            )
            if "ERROR:" in output:
                abort("A problem occurred while executing chef-solo")
            else:
                print "\nSUCCESS: Node correctly configured"

def _update_cookbooks(configfile):
    '''Uploads needed cookbooks and all roles to a node'''
    # Clean up node
    sudo('rm -rf /tmp/chef-solo/cookbooks', pty=True)
    sudo('rm -rf /tmp/chef-solo/roles', pty=True)
    
    cookbooks = []
    with open(configfile, 'r') as f:
        try:
            node = json.loads(f.read())
        except json.decoder.JSONDecodeError as e:
            msg = 'Little Chef found the following error in'
            msg += ' "%s":\n                %s' % (configfile, str(e))
            abort(msg)
    # Fetch cookbooks needed for recipes
    for recipe in _get_recipes_in_node(node):
        recipe = recipe.split('::')[0]
        if recipe not in cookbooks:
            cookbooks.append(recipe)
    
    # Fetch cookbooks needed for role recipes
    for role in _get_roles_in_node(node):
        with open('roles/' + role + '.json', 'r') as f:
            try:
                roles = json.loads(f.read())
            except json.decoder.JSONDecodeError as e:
                msg = 'Little Chef found the following error in your'
                msg += ' "%s" role file:\n                %s' % (role, str(e))
                abort(msg)
            # Reuse _get_recipes_in_node to extract recipes in a role
            for recipe in _get_recipes_in_node(roles):
                recipe = recipe.split('::')[0]
                if recipe not in cookbooks:
                    cookbooks.append(recipe)
    
    # Fetch dependencies
    warnings = []
    for cookbook in cookbooks:
        for recipe in _get_recipes_in_cookbook(cookbook):
            for dep in recipe['dependencies']:
                if dep not in cookbooks:
                    if os.path.exists('cookbooks/' + dep):
                        cookbooks.append(dep)
                    else:
                        if dep not in warnings:
                            warnings.append(dep)
                            print "Warning: Possible error because of missing",
                            print "dependency for cookbook %s" % recipe['name']
                            print "         Cookbook '%s' not found" % dep
                            import time
                            time.sleep(1)
    
    print "Uploading cookbooks... (%s)" % ", ".join(cookbooks)
    _upload_and_unpack(['cookbooks/' + f for f in cookbooks])
    
    print "Uploading roles..."
    _upload_and_unpack(['roles'])

def _upload_and_unpack(source):
    '''Packs the given directory, uploads it to the node
    and unpacks it in the /tmp/chef-solo/ directory'''
    with hide('running'):
        local('tar czf temp.tar.gz %s' % " ".join(source))
        put('temp.tar.gz', 'temp.tar.gz')
        if not exists('/tmp/chef-solo/'):
            msg = "the /tmp/chef-solo/ directory was not found at the node."
            msg += " Is Chef correctly installed?"
            abort(msg)
        sudo('mv temp.tar.gz /tmp/chef-solo/', pty=True)
        local('rm temp.tar.gz')
        with cd('/tmp/chef-solo/'):
            sudo('tar -xzf temp.tar.gz', pty=True)
            sudo('rm temp.tar.gz', pty=True)

###########
### API ###
###########
def _get_nodes():
    '''Gets all nodes found in the nodes/ directory'''
    if not os.path.exists(NODEPATH):
        return []
    nodes = []
    for filename in sorted(
        [f for f in os.listdir(NODEPATH) if not os.path.isdir(f) and ".json" in f]):
        with open(NODEPATH + filename, 'r') as f:
            try:
                node = json.loads(f.read())
                # Don't append "nodename" to the root namespace
                # because it could colide with some cookbook's attribute
                node[APPNAME] = {'nodename': ".".join(filename.split('.')[:-1])}
                nodes.append(node)
            except json.decoder.JSONDecodeError as e:
                msg = "Little Chef found the following error in your"
                msg += " %s file:\n  %s" % (filename, str(e))
                abort(msg)
    return nodes

def _print_node(node):
    '''Pretty prints the given node'''
    nodename = node[APPNAME]['nodename']
    print "\n" + nodename
    for recipe in _get_recipes_in_node(node):
        print "  Recipe:", recipe
        print "    attributes: " + str(node.get(recipe, ""))
    for role in _get_roles_in_node(node):
        _print_role(_get_role(role))
    
    print "  Node attributes:"
    for attribute in node.keys():
        if attribute == "run_list" or attribute == "littlechef":
            continue
        print "    %s: %s" % (attribute, node[attribute])

def _get_recipes_in_cookbook(name):
    '''Gets the name of all recipes present in a cookbook'''
    recipes = []
    if not os.path.exists('cookbooks/' + name):
        abort('Cookbook "%s" not found' % name)
    path = 'cookbooks/' + name + '/metadata.json'
    try:
        with open(path, 'r') as f:
            try:
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
            except json.decoder.JSONDecodeError as e:
                msg = "Little Chef found the following error in your"
                msg += " %s file:\n  %s" % (path, str(e))
                abort(msg)
    except IOError:
        abort('The cookbook "%s" contains no metadata.json' % name)
    return recipes

def _get_recipes_in_node(node):
    '''Gets the name of all recipes present in the run_list of a node'''
    recipes = []
    for elem in node.get('run_list'):
        if elem.startswith("recipe"):
            recipe = elem.split('[')[1].split(']')[0]
            recipes.append(recipe)
    return recipes

def _get_recipes():
    '''Gets all recipes found in the cookbooks/ directory'''
    recipes = []
    for dirname in sorted(
        [d for d in os.listdir('cookbooks') if not d.startswith('.')]):
        recipes.extend(_get_recipes_in_cookbook(dirname))
    return recipes

def _print_recipe(recipe):
    '''Pretty prints the given recipe'''
    print "\nRecipe: " + recipe['name']
    print "  description:", recipe['description']
    print "  dependencies:", ", ".join(recipe['dependencies'])
    print "  attributes:", ", ".join(recipe['attributes'])

def _get_roles_in_node(node):
    '''Gets the name of all roles found in the run_list of a node'''
    roles = []
    for elem in node.get('run_list'):
        if elem.startswith("role"):
            role = elem.split('[')[1].split(']')[0]
            roles.append(role)
    return roles

def _get_role(rolename):
    '''Reads and parses a file containing a role'''
    path = 'roles/' + rolename + '.json'
    if not os.path.exists(path):
        abort("Couldn't read role file %s" % path)
    with open(path, 'r') as f:
        try:
            role = json.loads(f.read())
        except json.decoder.JSONDecodeError as e:
            msg = "Little Chef found the following error in your"
            msg += " %s file:\n  %s" % (rolename, str(e))
            abort(msg)
        role['fullname'] = rolename
        return role

def _get_roles():
    '''Gets all roles found in the roles/ directory'''
    roles = []
    for root, subfolders, files in os.walk('roles/'):
        for filename in files:
            if filename.endswith(".json"):
                path = os.path.join(
                    root[len('roles/'):], filename[:-len('.json')])
                roles.append(_get_role(path))
    return roles

def _print_role(role):
    '''Pretty prints the given role'''
    print "Role: %s" % role.get('fullname')
    print "    description: {0}".format(role.get('description'))
    print "    default_attributes:"
    _pprint(role.get('default_attributes'))
    print "    override_attributes:"
    _pprint(role.get('override_attributes'))
    print ""

def _pprint(dic):
    '''Prints a dictionary with one indentation level'''
    for key, value in dic.items():
        print "        %s: %s" % (key, value)
