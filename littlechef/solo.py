#Copyright 2010-2012 Miquel Torres <tobami@gmail.com>
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
import re

from fabric.api import *
from fabric import colors
from fabric.contrib.files import append, exists, upload_template
from fabric.utils import abort

from littlechef import cookbook_paths
from littlechef.lib import credentials
from littlechef import LOGFILE as logging_path


# Path to local patch
BASEDIR = os.path.abspath(os.path.dirname(__file__).replace('\\', '/'))


def install(distro_type, distro, gems, version, stop_client):
    """Calls the appropriate installation function for the given distro"""
    with credentials():
        if distro_type == "debian":
            if gems == "yes":
                _gem_apt_install()
            else:
                _apt_install(distro, version, stop_client)
        elif distro_type == "rpm":
            if gems == "yes":
                _gem_rpm_install()
            else:
                _rpm_install()
        elif distro_type == "gentoo":
            _emerge_install()
        elif distro_type == "pacman":
            _gem_pacman_install()
        else:
            abort('wrong distro type: {0}'.format(distro_type))


def configure(current_node=None):
    """Deploy chef-solo specific files"""
    current_node = current_node or {}
    with credentials():
        # Ensure that the /tmp/chef-solo/cache directory exist
        cache_dir = "{0}/cache".format(env.node_work_path)
        if not exists(cache_dir):
            with settings(hide('running', 'stdout'), warn_only=True):
                output = sudo('mkdir -p {0}'.format(cache_dir))
            if output.failed:
                error = "Could not create {0} dir. ".format(env.node_work_path)
                error += "Do you have sudo rights?"
                abort(error)
        # Change ownership of /tmp/chef-solo/ so that we can rsync
        with hide('running', 'stdout'):
            with settings(warn_only=True):
                output = sudo(
                    'chown -R {0} {1}'.format(env.user, env.node_work_path))
            if output.failed:
                error = "Could not modify {0} dir. ".format(env.node_work_path)
                error += "Do you have sudo rights?"
                abort(error)
        # Set up chef solo configuration
        if not exists(logging_path):
            sudo('mkdir -p {0}'.format(logging_path))
        if not exists('/etc/chef'):
            sudo('mkdir -p /etc/chef')
        # Set parameters and upload solo.rb template
        reversed_cookbook_paths = cookbook_paths[:]
        reversed_cookbook_paths.reverse()
        cookbook_paths_list = '[{0}]'.format(', '.join(
            ['"{0}/{1}"'.format(env.node_work_path, x) \
                for x in reversed_cookbook_paths]))
        data = {
            'node_work_path': env.node_work_path,
            'cookbook_paths_list': cookbook_paths_list,
            'environment': current_node.get('chef_environment', '_default'),
            'verbose': "true" if env.verbose else "false"
        }
        with settings(hide('everything')):
            try:
                upload_template(os.path.join(BASEDIR, 'solo.rb'), '/etc/chef/',
                    context=data, use_sudo=True, backup=False, mode=0400)
            except SystemExit:
                error = ("Failed to upload '/etc/chef/solo.rb'\n"
                "This can happen when the deployment user does not have a "
                "home directory, which is needed as a temporary location")
                abort(error)
        with hide('stdout'):
            sudo('chown root:root {0}'.format('/etc/chef/solo.rb'))


def check_distro():
    """Check that the given distro is supported and return the distro type"""
    debian_distros = ['wheezy', 'squeeze', 'lenny']
    ubuntu_distros = ['natty', 'maverick', 'lucid', 'karmic']
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
        elif 'Arch Linux \\r  (\\n) (\\l)' in output:
            distro = "Arch Linux"
            distro_type = "pacman"
        else:
            print "Currently supported distros are:"
            print "  Debian: " + ", ".join(debian_distros)
            print "  Ubuntu: " + ", ".join(ubuntu_distros)
            print "  RHEL: " + ", ".join(rpm_distros)
            print "  Gentoo"
            print "  Arch Linux"
            abort("Unsupported distro '{0}'".format(output))
    return distro_type, distro


def _gem_install():
    """Install Chef from gems"""
    # Install RubyGems from Source
    rubygems_version = "1.8.10"
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
    packages += " ssl-cert rsync"
    sudo('{0} apt-get --yes install {1}'.format(prefix, packages))
    _gem_install()


def _gem_rpm_install():
    """Install Chef from gems for rpm based distros"""
    _add_rpm_repos()
    needed_packages = "make ruby ruby-shadow gcc gcc-c++ ruby-devel wget rsync"
    with show('running'):
        sudo('yum -y install {0}'.format(needed_packages))
    _gem_install()


def _gem_pacman_install():
    """Install Chef from gems for pacman based distros"""
    with hide('stdout', 'running'):
        sudo('pacman -Syu --noconfirm')
    with show('running'):
        sudo('pacman -S --noconfirm ruby base-devel wget rsync')
    sudo('gem install --no-rdoc --no-ri chef')


def _apt_install(distro, version, stop_client='yes'):
    """Install Chef for debian based distros"""
    with settings(hide('stdout', 'running')):
        with settings(hide('warnings'), warn_only=True):
            wget_is_installed = sudo('which wget')
            if wget_is_installed.failed:
                # Install wget
                print "Installing wget..."
                # we may not be able to install wget without updating first
                sudo('apt-get update')
                output = sudo('apt-get --yes install wget')
                if output.failed:
                    print(colors.red("Error while installing wget:"))
                    abort(output.lstrip("\\n"))
            rsync_is_installed = sudo('which rsync')
            if rsync_is_installed.failed:
                # Install rsync
                print "Installing rsync..."
                # we may not be able to install rsync without updating first
                sudo('apt-get update')
                output = sudo('apt-get --yes install rsync')
                if output.failed:
                    print(colors.red("Error while installing rsync:"))
                    abort(output.lstrip("\\n"))
        # Add Opscode Debian repo
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
        # Load package list from new repository
        with settings(hide('warnings'), warn_only=True):
            output = sudo('apt-get update')
            if output.failed:
                print(colors.red(
                    "Error while executing 'apt-get install chef':"))
                abort(output)
        # Install Chef Solo
        print("Installing Chef Solo")
        # Ensure we don't get asked for the Chef Server
        command = "echo chef chef/chef_server_url select ''"
        command += " | debconf-set-selections"
        sudo(command)
        # Install package
        with settings(hide('warnings'), warn_only=True):
            output = sudo('apt-get --yes install ucf chef')
            if output.failed:
                print(colors.red(
                    "Error while executing 'apt-get install chef':"))
                abort(output)
        if stop_client == 'yes':
            # We only want chef-solo, stop chef-client and remove it from init
            sudo('update-rc.d -f chef-client remove')
            with settings(hide('warnings'), warn_only=True):
                # The logrotate entry will force restart of chef-client
                sudo('rm /etc/logrotate.d/chef')
            with settings(hide('warnings'), warn_only=True):
                output = sudo('service chef-client stop')
            if output.failed:
                # Probably an older distro without the newer "service" command
                sudo('/etc/init.d/chef-client stop')


def _add_rpm_repos():
    """Add RPM repositories for Chef
    Opscode doesn't officially support an ELFF resporitory any longer:
    http://wiki.opscode.com/display/chef/Installation+on+RHEL+and+CentOS+5+with
    +RPMs

    Using http://rbel.frameos.org/

    """
    version_string = sudo('cat /etc/redhat-release')
    try:
        rhel_version = re.findall("\d[\d.]*", version_string)[0].split('.')[0]
    except IndexError:
        print "Warning: could not correctly detect the Red Hat version"
        print "Defaulting to 5 packages"
        rhel_version = "5"

    epel_release = "epel-release-5-4.noarch"
    if rhel_version == "6":
        epel_release = "epel-release-6-7.noarch"
    with show('running'):
        # Install the EPEL Yum Repository.
        with settings(hide('warnings', 'running'), warn_only=True):
            repo_url = "http://dl.fedoraproject.org"
            repo_path = "/pub/epel/{0}/i386/".format(rhel_version)
            repo_path += "{0}.rpm".format(epel_release)
            output = sudo('rpm -Uvh {0}{1}'.format(repo_url, repo_path))
            installed = "package {0} is already installed".format(epel_release)
            if output.failed and installed not in output:
                abort(output)
        # Install the FrameOS RBEL Yum Repository.
        with settings(hide('warnings', 'running'), warn_only=True):
            repo_url = "http://rbel.co"
            repo_path = "/rbel{0}".format(rhel_version)
            output = sudo('rpm -Uvh {0}{1}'.format(repo_url, repo_path))
            installed = "package rbel{0}-release-1.0-2.el{0}".format(
                        rhel_version)
            installed += ".noarch is already installed"
            if output.failed and installed not in output:
                abort(output)


def _rpm_install():
    """Install Chef for rpm based distros"""
    _add_rpm_repos()
    with show('running'):
        # Ensure we have an up-to-date ruby, as we need >=1.8.7
        sudo('yum -y upgrade ruby*')
        # Install Chef
        sudo('yum -y install rubygem-chef')


def _emerge_install():
    """Install Chef for Gentoo"""
    with show('running'):
        sudo("USE='-test' ACCEPT_KEYWORDS='~amd64' emerge -u chef")
