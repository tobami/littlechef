# -*- coding: utf-8 -*-
# LittleChef: Configuration management using Chef Solo
# in a push based system using Python and Fabric
import fabric
from fabric.api import *
from fabric.contrib.files import upload_template, append
import ConfigParser, os
import simplejson as json


NODEPATH = "nodes/"
APPNAME  = "littlechef"

def _readconfig():
    '''Read main fabric configuration'''
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
        abort('No section "userinfo" found in auth.cfg. Refer to the README for help')
    env.loglevel = "info"

_readconfig()

def _get_nodes():
    nodes = []
    for filename in sorted([f for f in os.listdir(NODEPATH) if not os.path.isdir(f) and ".json" in f]):
        with open(NODEPATH + filename, 'r') as f:
            try:
                nodes.append(json.loads(f.read()))
            except json.decoder.JSONDecodeError:
                print "Warning: file %s contains no JSON" % filename
    return nodes

env.hosts = [node[APPNAME]['nodeid'] for node in _get_nodes()]
fabric.state.output['running'] = False

@hosts('setup')
def node(host):
    '''Select a node'''
    env.hosts = [host]

@hosts('setup')
def debug():
    '''Sets logging level to debug'''
    print "Setting logging level to 'debug'..."
    env.loglevel = 'debug'

def recipe(recipe, save=False):
    '''Execute the given recipe,ignores existing config'''
    with hide('stdout', 'running'): hostname = run('hostname')
    print "\n== Executing recipe %s on node %s ==" % (recipe, hostname)
    configfile = hostname + ".json"
    if not os.path.exists('cookbooks/' + recipe):
        abort("Recipe '%s' not found" % recipe)
    data = {
        APPNAME: {'nodename': hostname, 'nodeid': env.host_string},
        "run_list": [ "recipe[%s]" % recipe ],
    }
    filepath = _save_config(save, data)
    _sync_node(filepath)

def role(role, save=False):
    '''Execute the given role, ignores existing config'''
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
    '''Configures all nodes using existing config files'''
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

def deploy_chef(server):
    '''Install Chef-solo on a node'''
    env.host_string = server
    append('deb http://apt.opscode.com/ lenny main',
        '/etc/apt/sources.list.d/opscode.list', use_sudo=True)
    sudo('wget -qO - http://apt.opscode.com/packages@opscode.com.gpg.key | sudo apt-key add -')
    sudo('apt-get update')
    with hide('stdout'):
        sudo('DEBIAN_FRONTEND=noninteractive apt-get --yes install chef')
    
    # We only want chef-solo
    sudo('update-rc.d -f chef-client remove')
    with settings(hide('warnings'), warn_only=True): sudo('pkill chef-client')
    
    # Setup
    put('chef-solo.rb', 'solo.rb')
    sudo('mv solo.rb /etc/chef/')
    sudo('mkdir -p /tmp/chef-solo/roles')
    
    # Copy cookbooks
    _update_cookbooks()

#########################
### Private functions ###
#########################
def _save_config(save, data):
    filepath = NODEPATH + data[APPNAME]['nodename'] + ".json"
    if os.path.exists(filepath) and not save:
        filepath = 'tmp_node.json'
    with open(filepath, 'w') as f:
        f.write(json.dumps(data))
        f.write('\n')
    return filepath

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
