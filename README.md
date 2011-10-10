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

* `auth.cfg`: Authentication information needed to be able to connect to the nodes
* `nodes/`: After recipes are run on [Nodes][], their configuration is stored here in
JSON format. You can manually edit them or even add new ones. The name of a node
should be its FQDN
* `cookbooks/`: This will be your [Cookbooks][] repository
* `site-cookbooks/`: Here you can override upstream cookbooks (Opscode's, for example)
* `roles/`: Where Chef [Roles][] are defined in JSON
* `data_bags/`: Chef [Data Bags][]. JSON databag items. Search is supported

Whenever you start a Chef Solo configuration run with the local `fix` command, all
cookbooks, roles and databags are rsynced to the `/tmp/chef-solo/` directory, together
with the `/etc/chef/node.json` and `/etc/chef/solo.rb` files, and chef-solo is executed
at the remote node.

The result is that you can configure your nodes exactly when and how you want, all
without needing a Chef Server. And all your infrastructure, including your nodes, will
be in code, revision controlled.

#### Data bag Search ####

Chef Solo does not currently (as of 0.10.4) support data bag search. LittleChef adds search support by automatically adding to your node cookbooks a
[cookbook library that implements search][].

Thus, most examples in the [search wiki page][] are now possible, including the
following example: `search(:users, "married:true AND age:35")`

#### Environments ####

Chef Solo does not support Environments, but, similarly to the search case, LittleChef will automatically add a cookbook library that will let you define `chef_environment`
in a role or node.

#### Node Search ####

Node search is achieved by creating a "node" data bag on the fly for every run,
with the data from each node defined in nodes/, but with the attribute values being the
result from merging cookbook, node and role attributes, following the standard
[Chef attribute preference rules][]. Some [automatic attributes][] are also added.

```ruby
munin_servers = search(:node, "role:#{node['munin']['server_role']} AND chef_environment:node.chef_environment']}")`
```

## Installation

### Desktop support

Tested on all three major desktops:  
  Linux, Mac OS X, and Windows

### Requirements

* Python 2.6+
* Fabric 1.0.1+

The best way to install LittleChef is using pip. Required packages are installed by typing:  
`sudo apt-get install python-pip python-dev` for Debian and Ubuntu  
or  
`yum install python-pip python-devel` for RHEL and CentOS

pip will then take care of the extra Python dependencies

### Installation

You can install LittleChef directly from the PyPI:  
`pip install littlechef`

## Usage

### Disclaimer

Careful what you do with your nodes!:

> A certain famous Chef: What do I always say? Anyone can cook.  
> LittleChef: Yeah. Anyone can, that doesn't mean that anyone should.

### Local Setup

`fix new_kitchen` will create inside the current directory a few files and directories for LittleChef to be able to cook: `auth.cfg`, `roles/`, `data_bags/`, `nodes/`, `cookbooks/` and `site-cookbooks/`. You can create and have as many kitchens as you like on your computer.

### Authentication

To be able to issue commands to remote nodes, you need to enter a user and a password with sudo rights. `new_kitchen` will have created a file named `auth.cfg`. You can edit it now to enter needed authentication data. There are several possibilities:

* username and password
* username, password and keypair-file
* A reference to an ssh-config file

The last one allows the most flexibility, as it allows you to define different usernames, passwords and/or keypair-files per hostname. LittleChef will look at `~/.ssh/config` by default, but you can always specify another path in `auth.cfg`:

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

### Deploying

For convenience, there is a command that allows you to deploy chef-solo
to a node.

The best way is to use the packages from the [Opscode repository][]:  
`fix node:MYNODE deploy_chef`

LittleChef will try to autodetect the distro type and version of that node, and will use the appropriate installation method and packages.

You can also install Chef Solo with gems and/or without asking for confirmation:  
`fix node:MYNODE deploy_chef:gems=yes,ask=no`

Currently supported Linux distributions include Ubuntu, Debian, CentOS, RHEL, Scientific Linux, Gentoo, and Arch Linux.

When using the Debian repository, you need to take into account that Opscode has separated Chef versions in different repos. Current default is Chef 0.10, but you can install Chef 0.9 by typing:
`fix node:MYNODE deploy_chef:version=0.9`

Also, if you still want to keep the chef-client around in debian, use the `stop_client`
option: `fix node:MYNODE deploy_chef:stop_client=no`

Note that if you already have Chef Solo installed on your nodes, you won't need this. Also, if you previously installed Chef using the Gem procedure, please don't use the deploy_chef package installation method, removing the gem first might be a good idea.

### Cooking

Note: Don't cook outside of a kitchen!

* `fix -l`: Show a list of all available orders
* `fix node:MYNODE recipe:MYRECIPE`: Cook a recipe on a particular node by giving its hostname or IP. "Subrecipes" like `nginx::source` are supported. Note that the first time this is run for a node, a configuration file will be created at `nodes/myhostname.json`. You can then edit this file to override recipe attributes, for example. Further runs of this command will not overwrite this configuration file
* `fix node:MYNODE role:MYROLE`: The same as above but role-based
* `fix node:MYNODE1,MYNODE2`: Configures several pre-configured nodes, in order
* `fix node:all`: It will apply all roles, recipes and attributes defined for each and every node in `nodes/`
* `fix node:all env:MYENV`: Configures all nodes which have the attribute `chef_environment` set to `MYENV`
* `fix nodes_with_role:ROLE1`: Configures all nodes which have a certain role in their run_list.
* `fix nodes_with_role:ROL*`: Configures all nodes which have at least one role which starts with 'ROL' in their run_list.
* `fix nodes_with_role:ROLE1 env:MYENV`: Configures all nodes in the environment MYENV which have a certain role in their run_list.
* `fix debug node:MYNODE`: You can start all your commands with `fix debug` to see all Chef Solo debugging information

Once a node has a config file, the command you will be using most often is `fix node:MYNODE`, which allows you to repeatedly tweak the recipes and attributes for a node and rerun the configuration.

### Consulting the inventory

* `fix list_nodes`: Lists all configured nodes, showing its associated recipes and roles
* `fix list_nodes_detailed`: Same as above, but it also shows all attributes
* `fix list_nodes_with_recipe:MYRECIPE`: Lists nodes which have associated the recipe `MYRECIPE`
* `fix list_nodes_with_role:MYROLE`: Shows nodes which have associated the role `MYROLE`
* `fix list_recipes`: Lists all available recipes
* `fix list_recipes_detailed`: Same as above, but shows description, version, dependencies and attributes
* `fix list_roles`: Lists all available roles
* `fix list_roles_detailed`: Same as above, but shows description and attributes

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

### Other tutorial material

* [Automated Deployments with LittleChef][], nice introduction to Chef
    using LittleChef

### Getting help

For help regarding the use of LittleChef, or to share any ideas or suggestions you may have, please post on LittleChef's [discussion group][]

### Reporting bugs

If you find bugs please report it on [https://github.com/tobami/littlechef/issues](https://github.com/tobami/littlechef/issues)

Happy cooking!

  [Chef]: http://www.opscode.com/chef
  [Nodes]: http://wiki.opscode.com/display/chef/Nodes
  [Cookbooks]: http://wiki.opscode.com/display/chef/Cookbooks
  [Roles]: http://wiki.opscode.com/display/chef/Roles
  [Data Bags]: http://wiki.opscode.com/display/chef/Data+Bags
  [cookbook library that implements search]: https://github.com/edelight/chef-solo-search
  [Chef attribute preference rules]: http://wiki.opscode.com/display/chef/Attributes#Attributes-SettingAttributes
  [automatic attributes]: http://wiki.opscode.com/display/chef/Recipes#Recipes-CommonAutomaticAttributes
  [search wiki page]: http://wiki.opscode.com/display/chef/Search
  [Opscode repository]: http://wiki.opscode.com/display/chef/Installation#Installation-InstallingChefClientandChefSolo
  [Automated Deployments with LittleChef]: http://sysadvent.blogspot.com/2010/12/day-9-automated-deployments-with.html
  [discussion group]: http://groups.google.com/group/littlechef
  [https://github.com/tobami/littlechef/issues]: https://github.com/tobami/littlechef/issues
