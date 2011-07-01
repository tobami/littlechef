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
"""Chef Solo deployment"""
import os

from fabric.api import *
from fabric import colors
from fabric.contrib.files import append, exists, upload_template
from fabric.utils import abort

from littlechef.lib import credentials
from littlechef.settings import node_work_path, cookbook_paths


# Path to local patch
BASEDIR = os.path.abspath(os.path.dirname(__file__).replace('\\', '/'))

def install(distro_type, distro, gems, version):
    with credentials():
        if distro_type == "debian":
            if gems == "yes":
                _gem_apt_install()
            else:
                _apt_install(distro, version)
        elif distro_type == "rpm":
            if gems == "yes":
                _gem_rpm_install()
            else:
                _rpm_install()
        elif distro_type == "gentoo":
            _emerge_install()
        else:
            abort('wrong distro type: {0}'.format(distro_type))


def configure():
    """Deploy chef-solo specific files"""
    with credentials():
        # Ensure that config directories exist
        cache_dir = "{0}/cache".format(node_work_path)
        if not exists(cache_dir):
            sudo('mkdir -p {0}'.format(cache_dir))
        if not exists('/etc/chef'):
            sudo('mkdir -p /etc/chef')
        # Set parameters and upload solo.rb template
        reversed_cookbook_paths = cookbook_paths[:]
        reversed_cookbook_paths.reverse()
        cookbook_paths_list = '[{0}]'.format(', '.join(
            ['"{0}/{1}"'.format(node_work_path, x) \
                for x in reversed_cookbook_paths]))
        data = {'node_work_path': node_work_path,
            'cookbook_paths_list': cookbook_paths_list}
        upload_template(os.path.join(BASEDIR, 'solo.rb'), '/etc/chef/',
            context=data, use_sudo=True, mode=0400)
        sudo('chown root:root {0}'.format('/etc/chef/solo.rb'))


def check_distro():
    """Check that the given distro is supported and return the distro type"""
    debian_distros = ['wheezy', 'squeeze', 'lenny']
    ubuntu_distros = ['maverick', 'lucid', 'karmic', 'jaunty', 'hardy']
    rpm_distros = ['centos', 'rhel', 'sl']

    with credentials(
        hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
        output = sudo('cat /etc/issue')
        if 'Debian GNU/Linux 5.0' in output:
            distro = "lenny"
            distro_type = "debian"
        elif 'Debian GNU/Linux 6.0' in output:
            distro = "squeeze"
            distro_type = "debian"
        elif 'Debian GNU/Linux wheezy' in output:
            distro = "wheezy"
            distro_type = "debian"
        elif 'Ubuntu' in output:
            distro = sudo('lsb_release -cs')
            distro_type = "debian"
        elif 'CentOS' in output:
            distro = "CentOS"
            distro_type = "rpm"
        elif 'Red Hat Enterprise Linux' in output:
            distro = "Red Hat"
            distro_type = "rpm"
        elif 'Scientific Linux SL' in output:
            distro = "Scientific Linux"
            distro_type = "rpm"
        elif 'This is \\n.\\O (\\s \\m \\r) \\t' in output:
            distro = "Gentoo"
            distro_type = "gentoo"
        else:
            print "Currently supported distros are:"
            print "  Debian: " + ", ".join(debian_distros)
            print "  Ubuntu: " + ", ".join(ubuntu_distros)
            print "  RHEL: " + ", ".join(rpm_distros)
            print "  Gentoo"
            abort("Unsupported distro '{0}'".format(output))
    return distro_type, distro


def _gem_install():
    """Install Chef from gems"""
    # Install RubyGems from Source
    rubygems_version = "1.7.2"
    run('wget http://production.cf.rubygems.org/rubygems/rubygems-{0}.tgz'
        .format(rubygems_version))
    run('tar zxf rubygems-{0}.tgz'.format(rubygems_version))
    with cd('rubygems-{0}'.format(rubygems_version)):
        sudo('ruby setup.rb --no-format-executable'.format(rubygems_version))
    sudo('rm -rf rubygems-{0} rubygems-{0}.tgz'.format(rubygems_version))
    sudo('gem install --no-rdoc --no-ri chef')


def _gem_apt_install():
    """Install Chef from gems for apt based distros"""
    with hide('stdout', 'running'):
        sudo('apt-get update')
    prefix = "DEBIAN_FRONTEND=noninteractive"
    packages = "ruby ruby-dev libopenssl-ruby irb build-essential wget"
    packages += " ssl-cert"
    sudo('{0} apt-get --yes install {1}'.format(prefix, packages))
    _gem_install()


def _gem_rpm_install():
    """Install Chef from gems for rpm based distros"""
    _add_rpm_repos()
    with show('running'):
        sudo('yum -y install ruby ruby-shadow gcc gcc-c++ ruby-devel wget')
    _gem_install()


def _apt_install(distro, version):
    """Install Chef for debian based distros"""
    with settings(hide('stdout', 'running')):
        with settings(hide('warnings'), warn_only=True):
            wget_is_installed = sudo('which wget')
            if wget_is_installed.failed:
                # Install wget
                print "Installing wget..."
                # we may not be able to install wget withtout 'apt-get update' first
                sudo('apt-get update')
                output = sudo('apt-get --yes install wget')
                if output.failed:
                    print(colors.red("Error while installing wget:"))
                    abort(output.lstrip("\\n"))
        # Add Opscode debia repo
        print("Setting up Opscode repository...")
        if version == "0.9":
            version = ""
        else:
            version = "-" + version
        append('opscode.list',
            'deb http://apt.opscode.com/ {0}{1} main'.format(distro, version),
                use_sudo=True)
        sudo('mv opscode.list /etc/apt/sources.list.d/')
        # Add repository GPG key
        gpg_key = "http://apt.opscode.com/packages@opscode.com.gpg.key"
        sudo('wget -qO - {0} | sudo apt-key add -'.format(gpg_key))
        # Load packages from new repository
        with settings(hide('warnings'), warn_only=True):
            output = sudo('apt-get update')
            if output.failed:
                print(colors.red("Error while executing apt-get install chef:"))
                abort(output)
        # Install Chef Solo
        print("Installing Chef Solo")
        # Ensure we don't get asked for the Chef Server
        command = "echo chef chef/chef_server_url select ''"
        command += " | debconf-set-selections"
        sudo(command)
        with settings(hide('warnings'), warn_only=True):
            output = sudo('apt-get --yes install chef')
            if output.failed:
                print(colors.red("Error while executing 'apt-get install chef':"))
                abort(output)

        # We only want chef-solo, kill chef-client and remove it from init process
        sudo('update-rc.d -f chef-client remove')
        with settings(hide('warnings'), warn_only=True):
            output = sudo('service chef-client stop')
        if output.failed:
            # Probably an older distro
            sudo('/etc/init.d/chef-client stop')


def _add_rpm_repos():
    """Add EPEL and ELFF"""
    with show('running'):
        # Install the EPEL Yum Repository.
        with settings(hide('warnings', 'running'), warn_only=True):
            repo_url = "http://download.fedora.redhat.com"
            repo_path = "/pub/epel/5/i386/epel-release-5-4.noarch.rpm"
            output = sudo('rpm -Uvh {0}{1}'.format(repo_url, repo_path))
            installed = "package epel-release-5-4.noarch is already installed"
            if output.failed and installed not in output:
                abort(output)
        # Install the ELFF Yum Repository.
        with settings(hide('warnings', 'running'), warn_only=True):
            repo_url = "http://download.elff.bravenet.com"
            repo_path = "/5/i386/elff-release-5-3.noarch.rpm"
            output = sudo('rpm -Uvh {0}{1}'.format(repo_url, repo_path))
            installed = "package elff-release-5-3.noarch is already installed"
            if output.failed and installed not in output:
                abort(output)


def _rpm_install():
    """Install Chef for rpm based distros"""
    _add_rpm_repos()
    with show('running'):
        # Install Chef Solo
        sudo('yum -y install chef')


def _emerge_install():
    """Install Chef for Gentoo"""
    with show('running'):
        sudo("USE='-test' ACCEPT_KEYWORDS='~amd64' emerge -u chef")
