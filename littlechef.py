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
    if not os.path.exists('roles/' + role):
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

#########################
### Private functions ###
#########################
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
    for filename in sorted([f for f in os.listdir(NODEPATH) if not os.path.isdir(f) and ".json" in f]):
        with open(NODEPATH + filename, 'r') as f:
            try:
                nodes.append(json.loads(f.read()))
            except json.decoder.JSONDecodeError:
                print "Warning: file %s contains no JSON" % filename
    return nodes

def _sync_node(filepath):
    _update_cookbooks()
    _configure_node(filepath)

def _print_node(node):
    print "\n" + node[APPNAME]['nodename']
    for a in node.get('run_list'):
        if a.startswith("recipe"):
            recipe = a.split('[')[1].split(']')[0]
            recipe = a.lstrip('recipe[').rstrip(']')
            print "  Recipe:", recipe
            print "    attributes: " + str(node.get(recipe))
        elif a.startswith("role"):
            role = a.split('[')[1].split(']')[0]
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
        sudo('chef-solo -l %s -j /etc/chef/node.json' % env.loglevel)

def _update_cookbooks():
    print "Uploading cookbooks..."
    _upload_and_unpack('cookbooks')
    print "Uploading roles..."
    _upload_and_unpack('roles')

def _upload_and_unpack(source):
    target = '/tmp/chef-solo/'
    with hide('running'):
        local('tar czf temp.tar.gz %s' % source)
        put('temp.tar.gz', 'temp.tar.gz')
        local('rm temp.tar.gz')
        sudo('rm -rf %s/%s' % (target, source))
        run('tar -xzf temp.tar.gz')
        run('rm temp.tar.gz')
        sudo('mv %s %s' % (source, target))
