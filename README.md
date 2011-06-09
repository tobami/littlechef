# LittleChef

With LittleChef you will be able to get started more quickly cooking with [Chef][], the excellent Configuration Management System.

## Overview

You may think of this like a pocket Chef. No need to worry about installation, repository syncing, nor Chef Server authentication. You also won't have to remotely edit cookbooks, or commit little changes just to test things.

Installing LittleChef to your work computer is all you need to get you started.

### How it all works

It all starts in the **kitchen**, which you should keep under version control:

* `auth.cfg`: Authentication information needed to be able to connect to the nodes
* `nodes/`: After recipes are run on [Nodes][], their configuration is stored here. You can manually   edit them or even add new ones. Note that LittleChef will use the file name as the hostname or IP to connect to the node
* `cookbooks/`: This will be your [Cookbooks][] repository
* `site-cookbooks/`: Here you can override upstream cookbooks (Opscode's, for example)
* `roles/`: Where Chef [Roles][] are defined
* `data_bags/`: Chef [Data Bags][]. Note that search for data bags doesn't work yet with Chef Solo

Whenever you apply a recipe to a node, all needed cookbooks (including dependencies), all roles and all databags are gzipped and uploaded to that node, to the `/var/chef-solo/` directory. A node.json file gets created on the fly and uploaded, and Chef Solo gets executed at the remote node, using node.json as the node configuration and the pre-installed solo.rb for Chef Solo configuration.

The result is that you can play as often with your recipes and nodes as you want, without having to worry about a central Chef repository, Chef server nor anything else. You can make small changes to your cookbooks and test them again and again without having to commit the changes. You commit to your repo only when you want. LittleChef brings sanity to cookbook development.

## Installation

### Desktop support

LittleChef is fully tested on all three major desktops:  
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

Note: your distribution may have a `cook` package that also provides a `cook` executable. If you have installed it, you need to remove it to avoid collisions with LittleChef's executable.

## Usage

### Disclaimer

Careful what you do with your nodes!:

> A certain famous Chef: What do I always say? Anyone can cook.  
> LittleChef: Yeah. Anyone can, that doesn't mean that anyone should.

### Local Setup

`cook new_kitchen` will create inside the current directory a few files and directories for LittleChef to be able to cook: `auth.cfg`, `roles/`, `data_bags/`, `nodes/`, `cookbooks/` and `site-cookbooks/`. You can create and have as many kitchens as you like on your computer.

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
`cook node:MYNODE deploy_chef`

LittleChef will try to autodetect the distro type and version of that node, and will use the appropriate installation method and packages.

You can also install Chef Solo with gems and/or without asking for confirmation:  
`cook node:MYNODE deploy_chef:gems=yes,ask=no`

Currently supported Linux distributions include Ubuntu, Debian, CentOS, RHEL, Scientific Linux and Gentoo.

Note that if you already have Chef Solo installed on your nodes, you won't need this. Also, if you previously installed Chef using the Gem procedure, please don't use the deploy_chef package installation method. Installing Opscode's packages on top of it could be a mess.

### Cooking

Note: Don't cook outside of a kitchen!

* `cook -l`: Show a list of all available orders
* `cook node:MYNODE recipe:MYRECIPE`: Cook a recipe on a particular node by giving its hostname or IP. "Subrecipes" like `nginx::source` are supported. Note that the first time this is run for a node, a configuration file will be created at `nodes/myhostname.json`. You can then edit this file to override recipe attributes, for example. Further runs of this command will not overwrite this configuration file
* `cook node:MYNODE role:MYROLE`: The same as above but role-based
* `cook node:MYNODE configure`: Configures a pre-configured node
* `cook node:all configure`: It will apply all roles, recipes and attributes defined for each and every node in `nodes/`
* `cook debug node:MYNODE configure`: You can start all your commands with `cook debug` to see all Chef Solo debugging information

Once a node has a config file, the command you will be using most often is `cook node:MYNODE configure`, which allows you to repeatedly tweak the recipes and attributes for a node and rerun the configuration.

### Consulting the inventory

* `cook list_nodes`: Lists all configured nodes, showing its associated recipes and roles
* `cook list_nodes_detailed`: Same as above, but it also shows allattributes
* `cook list_nodes_with_recipe:MYRECIPE`: The same as above but itonly lists nodes which have associated the recipe `MYRECIPE`
* `cook list_nodes_with_role:MYROLE`: The same as above but it onlylists nodes which have associated the role `MYROLE`
* `cook list_recipes`: Lists all available recipes
* `cook list_recipes_detailed`: Same as above, but shows description,version, dependencies and attributes
* `cook list_roles`: Lists all available roles
* `cook list_roles_detailed`: Same as above, but shows description and attributes

### Using LittleChef as a library

You can import littlechef.py into your own Python project. The following
script is equivalent to using the `cook` orders:

```python
from littlechef import runner as lc
lc.env.user = 'MyUsername'
lc.env.password = 'MyPassword'
lc.env.host_string = 'MyHostnameOrIP'
lc.deploy_chef(gems='yes', ask='no')
lc.recipe('MYRECIPE')#Applies <MYRECIPE> to <MyHostnameOrIP>
lc.configure()#Applies the saved nodes/MyHostnameOrIP.json configuration
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
  [Opscode repository]: http://wiki.opscode.com/display/chef/Installation#Installation-InstallingChefClientandChefSolo:
  [Automated Deployments with LittleChef]: http://sysadvent.blogspot.com/2010/12/day-9-automated-deployments-with.html
  [discussion group]: http://groups.google.com/group/littlechef
  [https://github.com/tobami/littlechef/issues]: https://github.com/tobami/littlechef/issues
