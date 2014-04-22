# LittleChef

With LittleChef you will be able to get started more quickly cooking with [Chef][], the excellent Configuration Management System.

## Overview

You may think of this like a pocket Chef that doesn't need a Chef Server. Just your
local kitchen with all your cookbooks, roles data bags and nodes, which will get rsynced
to a node each time you start a Chef Solo configuration run with the bundled `fix`
command.

It also adds features to Chef Solo that are currently only available for Chef Server users: data bag search, and node search.

### How it all works

It all starts in the **kitchen**, which you should keep under version control:

* `littlechef.cfg`: Configuration, including authentication and run-time options.
* `nodes/`: After recipes are run on [Nodes][], their configuration is stored here in
JSON format. You can manually edit them or even add new ones. The name of a node
should be its FQDN
* `cookbooks/`: This will be your [Cookbooks][] repository
* `site-cookbooks/`: Here you can override upstream cookbooks (Opscode's, for example)
* `environments/`: Where Chef [Environments][] are defined in JSON
* `roles/`: Where Chef [Roles][] are defined in JSON
* `data_bags/`: Chef [Data Bags][]. JSON databag items. Search is supported
* `plugins/`: Your plugin tasks

Whenever you start a Chef Solo configuration run with the local `fix` command, all
cookbooks, roles and databags are rsynced to the `/tmp/chef-solo/` directory, together
with the `/etc/chef/node.json` and `/etc/chef/solo.rb` files, and chef-solo is executed
at the remote node.

The result is that you can configure your nodes exactly when and how you want, all
without needing a Chef Server. And all your infrastructure, including your nodes, will
be in code, revision controlled.

#### Environments ####

Chef 10 does not support Environments in Solo mode, but LittleChef will automatically
add a cookbook library that will let you define `chef_environment` in a role or node.

If you use Chef 11, all environment features except cookbook versioning work out of the
box.

#### Data bag Search ####

Chef Solo does not support data bag search. To be able to use search, the [chef-solo-search library][] needs to be present in your cookbooks directory.

Most examples in the [chef search documentation][] are possible, including stuff
like: `search(:users, "married:true AND age:35")`.

#### Node Search ####

Node search is achieved by creating a "node" data bag on the fly for every run,
with the data from each node defined in nodes/, but with the attribute values being the
result from merging cookbook, node and role attributes, following the standard
[Chef attribute preference rules][]. Some [automatic attributes][] are also added.

```ruby
munin_servers = search(:node, "role:#{node['munin']['server_role']} AND chef_environment:#{node.chef_environment}")
```

#### Logs ####

Chef Solo output for a configuration run will be found at the node's
`/var/log/chef/solo.log`, and the previous configuration run will be moved
to `solo.log.1`.

#### metadata.rb and ruby roles ####

LittleChef depends on the JSON versions of the cookbook metadata and roles to properly 
merge attributes. You can still use the ruby versions, and generate the JSON versions
when you make changes. If you have knife locally installed, it will even be done 
automatically on every run if a changed metadata.rb is detected. Ruby roles are not
yet automatically converted, but an implementation is planned.

#### Plugins ####

You can define your own LittleChef tasks as Python plugin modules. They should be located
in the `plugins` directory. The filename will be the plugin name and the module docstring
the description. Each plugin should define an execute funtion, which will then be
executed when applying a plugin on a node (the *Cooking* section describes how to run a
plugins).

You can find example plugins in the [repository plugins directory](https://github.com/tobami/littlechef/blob/master/plugins/)

### Getting Big

Beyond a small number of nodes it becomes more and more difficult to keep track of
everything. To solve that problem we created [Kitchen][], an incredibly useful dashboard
that provies an overview of all nodes and a graphical visualization of role dependencies.

## Installation

### Desktop support

Tested on all major operating systems:
  Linux, Mac OS X, Windows and FreeBSD

### Requirements

* Python 2.6+
* Fabric 1.5+

The best way to install LittleChef is using pip. Required packages are installed by typing:

    $ sudo apt-get install python-pip python-dev

for Debian and Ubuntu, or

    $ yum install python-pip python-devel

for RHEL and CentOS.

### Installation

You can install LittleChef directly from the PyPI:  

    $ pip install littlechef

## Usage

### Disclaimer

Careful what you do with your nodes!:

> A certain famous Chef: What do I always say? Anyone can cook.  
> LittleChef: Yeah. Anyone can, that doesn't mean that anyone should.

### Local Setup

To create a new kitchen, type:

    $ fix new_kitchen

This will create a few files and directories inside the current directory which
LittleChef needs to be able to cook: `littlechef.cfg`, `environments`, `roles/`, `
data_bags/`, `nodes/`, `cookbooks/` and `site-cookbooks/`. You can create and have
as many kitchens as you like on your computer.

### Authentication

To be able to issue commands to remote nodes, you need to enter a user and a password
with sudo rights. `new_kitchen` will have created a file named `littlechef.cfg`. You can
edit it now to enter needed authentication data. There are several possibilities:

* username and password
* username, password and keypair-file
* A reference to an ssh-config file

The last one allows the most flexibility, as it allows you to define different usernames,
passwords and/or keypair-files per hostname. LittleChef will look at `~/.ssh/config` by
default, but you can always specify another path in `littlechef.cfg`:

```ini
[userinfo]
user = myusername
password = mypassword
ssh-config = /path/to/config/file
```

An example `~/.ssh/config` file:

    Host www.cooldomain.com
        HostName www.cooldomain.com
        IdentityFile ~/.ssh/prod_rsa
        User produser
    Host *.devdomain.com
        IdentityFile ~/.ssh/dev_rsa
        User devuser

### Other Configuration Options

You can also optionally override the directory being used on the nodes to sync your
kitchen to:

```ini
[kitchen]
node_work_path = /tmp/chef-solo
```

If you're using encrypted data bags you can specify a path for the encrypted_data_bag_secret file:

```ini
[userinfo]
encrypted_data_bag_secret = ~/path/to/encrypted_data_bag_secret
```

This will put the encrypted_data_bag_secret in `/etc/chef/encrypted_data_bag_secret` with permissions root:root with perms 0600.
Chef-solo will automatically use it wherever you use `Chef::EncryptedDataBagItem.load` in your recipes.
It will also remove the `/etc/chef/encrypted_data_bag_secret` file from the node at the end of the run.

If your nodes are not directly accessible, you might want to specify a gateway host.
The fix command will connect to the host specified and issue all following connections
from this host. All ssh communication will be tunneled through this gateway connection.
This can be used if your nodes are behind a firewall and only one host is accessible
from your current network location.

```ini
[connection]
gateway = hub.example.com
```

After issuing a fix command, this will connect to hub.example.com. All further node connections will be done from
hub.example.com.

The `sync-packages` section allows you to define remote and local directories, which will then be synchronized at every run.

```ini
[sync-packages]
dest-dir = /srv/packages
local-dir = ./packages
```

### Deploying chef-solo

For convenience, there is a command that allows you to deploy chef-solo
to a node.

#### Omnibus method
The best way is to use the omnibus method [getchef][]:
`fix node:MYNODE deploy_chef:method=omnibus,version=11.12`

#### Other methods

The default installation method:
`fix node:MYNODE deploy_chef` uses the packages from the [Opscode repository][], which
are no longer updated, so its use is no longer recommended. LittleChef will try to
autodetect the distro type and version of that node, and will use the appropriate
installation method and packages. LittleChef 2.x will use the omnibus method as default
instead.

You can also install Chef Solo with gems and/or without asking for confirmation:  
`fix node:MYNODE deploy_chef:gems=yes,ask=no`

Currently supported Linux distributions include Ubuntu, Debian, CentOS, RHEL,
Scientific Linux, Gentoo, and Arch Linux.

When using the Debian repository, you need to take into account that Opscode has
separated Chef versions in different repos. Current default is Chef 0.10, but you can install Chef 0.9 by typing:
`fix node:MYNODE deploy_chef:version=0.9`

Also, if you still want to keep the chef-client around in debian, use the `stop_client`
option: `fix node:MYNODE deploy_chef:stop_client=no`

Note that if you already have Chef Solo installed on your nodes, you won't need this. Also, if you previously installed Chef using the Gem procedure, please don't use the deploy_chef package installation method, removing the gem first might be a good idea.

### Cooking

Note: Don't cook outside of a kitchen!

List of commands:

* `fix -v`: Shows the version number
* `fix -l`: Show a list of all available orders
* `fix -y`: Automatic yes to prompts; assume "yes" as answer to all prompts and run non-interactively
* `fix node:MYNODE role:MYROLE`: Full chef-solo configuration run on the given node. Uses ssh_config hostname directives
* `fix node:MYNODE1,MYNODE2`: Configures several nodes. For all "fix node" commands,
nodes with the attribute `dummy` set to `true` will *not* be configured and will be
skipped
* `fix node:all`: It will apply all roles, recipes and attributes defined for each and
every node in `nodes/`
* `fix --env=MYENV node:all`: Configures all nodes which have the attribute `chef_environment` set to `MYENV`
* `fix node:MYNODE role:MYROLE`: Apply the given role on the given nodes
* `fix node:MYNODE recipe:MYRECIPE`: Apply the given recipe on the given nodes
* `fix nodes_with_role:ROLE1`: Configures all nodes which have the given role in
their run_list
* `fix nodes_with_role:ROL*`: Configures all nodes which have at least one role which
starts with 'ROL' in their run_list
* `fix nodes_with_recipe:MYRECIPE`: Configures all nodes which have the given recipe
in their run_list
* `fix nodes_with_tag:MYTAG`: Configures all nodes which have the tag `MYTAG`
  assigned. `--include-guests` will also configure guest nodes belonging to each host
  which has the given tag assigned
* `fix node:MYNODES ssh:"my shell command"`: Executes the given command on the node
* `fix node:MYNODES plugin:save_ip`: Gets the actual IP for this node and saves it in
the `ipaddress` attribute

Options:

* `fix --env=MYENV nodes_with_role:ROLE1`: Configures all nodes in the environment MYENV
which have a certain role in their run_list.
* `fix --verbose node:MYNODE`: Chef 0.10.6 introduced the `verbose_logging` option. When
false, the "processing" messages are not longer shown. That is the new default for
LittleChef, so that you now only see what has changed in this configuration run.
`--verbose` switches this back on.
* `fix --debug node:MYNODE`: You can start all your commands with `fix --debug` to see
all Chef Solo debugging information. Also, the node file and node databag wont't be
deleted from the node, and verbose will also be true
* `fix --no-report node:MYNODE`: will prevent the logging of Chef Solo output to
/var/log/chef/
* `fix --why-run node:MYNODE`: will configure the node in [Whyrun][] mode

Once a node has a config file, the command you will be using most often is
`fix node:MYNODE`, which allows you to repeatedly tweak the recipes and attributes for a
node and rerun the configuration.

### Configuring nodes in parallel

By default LittleChef configures nodes serially however it can also use Fabric's parallel
SSH support to configure multiple nodes in parallel. All commands are supported (node,
nodes_with_role, ssh, role, and recipe)

* `fix --concurrency node:NODELIST`: will configure multiple nodes in parallel
* `fix --concurrency node:NODELIST ssh:COMMAND`: will run an ssh command on multiple nodes in parallel
* `fix --concurrency 5 node:NODELIST`: will configure multiple nodes in parallel but limit to 5 connections

### Consulting the inventory

* `fix list_nodes`: Lists all configured nodes, showing its associated recipes and roles
* `fix list_nodes_detailed`: Same as above, but it also shows all attributes
* `fix list_nodes_with_recipe:MYRECIPE`: Lists nodes which have associated the recipe `MYRECIPE`
* `fix list_nodes_with_role:MYROLE`: Shows nodes which have associated the role `MYROLE`
* `fix list_nodes_with_tag:MYTAG`: Shows nodes which have the tag `MYTAG` assigned.
  `--include-guests` will also display guest nodes belonging to each host which has
  the given tag assigned
* `fix list_envs`: Lists all available environments
* `fix list_recipes`: Lists all available recipes
* `fix list_recipes_detailed`: Same as above, but shows description, version,
  dependencies and attributes
* `fix list_roles`: Lists all available roles
* `fix list_roles_detailed`: Same as above, but shows description and attributes
* `fix list_plugins`: Show a list of available plugins

### Using LittleChef as a library

You can import littlechef.py into your own Python project. The following
script is equivalent to using the `fix` orders:

```python
from littlechef import runner as lc
lc.env.user = 'MyUsername'
lc.env.password = 'MyPassword'
lc.env.host_string = 'MyHostnameOrIP'
lc.deploy_chef(gems='yes', ask='no')

lc.recipe('MYRECIPE') #Applies <MYRECIPE> to <MyHostnameOrIP>
lc.node('MyHostnameOrIP') #Applies the saved nodes/MyHostnameOrIP.json configuration
```

### Performance Tips

You can greatly reduce the SSH connection setup time by reusing existing connections.
On Unix systems, you can do so by adding the `ControlMaster` directive to your ssh config:

    #~/.ssh/config
    Host *
      ControlMaster auto
      ControlPath /tmp/ssh-%r@%h:%p

### Other tutorial material

* [Automated Deployments with LittleChef][], nice introduction to Chef
    using LittleChef

### Getting help

For help regarding the use of LittleChef, or to share any ideas or suggestions you may have, please post on LittleChef's [discussion group][]

### Reporting bugs

[![Build Status](https://travis-ci.org/tobami/littlechef.png?branch=master)](https://travis-ci.org/tobami/littlechef)

If you find bugs please report it on [https://github.com/tobami/littlechef/issues](https://github.com/tobami/littlechef/issues)

Happy cooking!

  [Chef]: http://www.getchef.com/chef/
  [Nodes]: http://docs.opscode.com/essentials_node_object.html
  [Cookbooks]: http://docs.opscode.com/essentials_cookbooks.html
  [Environments]: http://docs.opscode.com/essentials_environments.html
  [Roles]: http://docs.opscode.com/essentials_roles.html
  [Data Bags]: http://docs.opscode.com/essentials_data_bags.html
  [chef-solo-search library]: http://community.opscode.com/cookbooks/chef-solo-search
  [Chef attribute preference rules]: http://docs.opscode.com/essentials_cookbook_attribute_files.html#attribute-precedence
  [automatic attributes]: http://docs.opscode.com/essentials_cookbook_recipes.html#Recipes-CommonAutomaticAttributes
  [Kitchen]: https://github.com/edelight/kitchen/
  [search wiki page]: http://docs.opscode.com/essentials_search.html#query-syntax
  [getchef]: http://www.getchef.com/chef/install/
  [Opscode repository]: http://docs.opscode.com/install_server.html#Installation-InstallingChefClientandChefSolo
  [Whyrun]: https://wiki.opscode.com/display/chef/Whyrun+Testing
  [Automated Deployments with LittleChef]: http://sysadvent.blogspot.com/2010/12/day-9-automated-deployments-with.html
  [discussion group]: http://groups.google.com/group/littlechef
  [https://github.com/tobami/littlechef/issues]: https://github.com/tobami/littlechef/issues
