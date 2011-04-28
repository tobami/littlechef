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
from fabric.api import *
from fabric.contrib.files import append, exists


def configure_chef_solo(node_work_path, cookbook_paths):
    """Deploy chef-solo specific files."""
    sudo('mkdir -p {0}'.format(node_work_path))
    sudo('mkdir -p {0}/cache'.format(node_work_path))
    sudo('umask 0377; touch solo.rb')
    append('solo.rb', 'file_cache_path "{0}/cache"'.format(
        node_work_path), use_sudo=True)
    reversed_cookbook_paths = cookbook_paths[:]
    reversed_cookbook_paths.reverse()
    cookbook_paths_line = 'cookbook_path [{0}]'.format(
        ', '.join(['''"{0}/{1}"'''.format(node_work_path, x) \
            for x in reversed_cookbook_paths]))
    append('solo.rb', cookbook_paths_line, use_sudo=True)
    append('solo.rb', 'role_path "{0}/roles"'.format(node_work_path),
        use_sudo=True)
    sudo('mkdir -p /etc/chef')
    sudo('mv solo.rb /etc/chef/')


def check_distro():
    """Check that the given distro is supported and return the distro type"""
    debian_distros = ['sid', 'squeeze', 'lenny']
    ubuntu_distros = ['maverick', 'lucid', 'karmic', 'jaunty', 'hardy']
    rpm_distros = ['centos', 'rhel', 'sl']

    with settings(
        hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
        output = sudo('cat /etc/issue')
        if 'Debian GNU/Linux 5.0' in output:
            distro = "lenny"
            distro_type = "debian"
        elif 'Debian GNU/Linux 6.0' in output:
            distro = "squeeze"
            distro_type = "debian"
        elif 'Ubuntu' in output:
            distro = sudo('lsb_release -c').split('\t')[-1]
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
            abort("Unsupported distro " + run('cat /etc/issue'))
    return distro_type, distro


def _gem_install():
    """Install Chef from gems"""
    # Install RubyGems from Source
    run('wget http://production.cf.rubygems.org/rubygems/rubygems-1.3.7.tgz')
    run('tar zxf rubygems-1.3.7.tgz')
    with cd("rubygems-1.3.7"):
        sudo('ruby setup.rb --no-format-executable')
    sudo('rm -rf rubygems-1.3.7 rubygems-1.3.7.tgz')
    sudo('gem install --no-rdoc --no-ri chef')


def gem_apt_install():
    """Install Chef from gems for apt based distros"""
    sudo("DEBIAN_FRONTEND=noninteractive apt-get --yes install ruby ruby-dev libopenssl-ruby irb build-essential wget ssl-cert")
    _gem_install()


def gem_rpm_install():
    """Install Chef from gems for rpm based distros"""
    _add_rpm_repos()
    with show('running'):
        sudo('yum -y install ruby ruby-shadow gcc gcc-c++ ruby-devel wget')
    _gem_install()


def apt_install(distro):
    """Install Chef for debian based distros"""
    sudo('apt-get --yes install wget')
    append('opscode.list', 'deb http://apt.opscode.com/ {0} main'.format(distro), use_sudo=True)
    sudo('mv opscode.list /etc/apt/sources.list.d/')
    gpg_key = "http://apt.opscode.com/packages@opscode.com.gpg.key"
    sudo('wget -qO - {0} | sudo apt-key add -'.format(gpg_key))
    with hide('stdout'):
        sudo('apt-get update')
    with show('running'):
        sudo('DEBIAN_FRONTEND=noninteractive apt-get --yes install chef')

    # We only want chef-solo, kill chef-client and remove it from init process
    sudo('update-rc.d -f chef-client remove')
    import time
    time.sleep(0.5)
    with settings(hide('warnings'), warn_only=True):
        sudo('pkill chef-client')


def _add_rpm_repos():
    """Add EPEL and ELFF"""
    with show('running'):
        # Install the EPEL Yum Repository.
        with settings(hide('warnings'), warn_only=True):
            output = sudo('rpm -Uvh http://download.fedora.redhat.com/pub/epel/5/i386/epel-release-5-4.noarch.rpm')
            installed = "package epel-release-5-4.noarch is already installed"
            if output.failed and installed not in output:
                abort(output)
        # Install the ELFF Yum Repository.
        with settings(hide('warnings'), warn_only=True):
            output = sudo('rpm -Uvh http://download.elff.bravenet.com/5/i386/elff-release-5-3.noarch.rpm')
            installed = "package elff-release-5-3.noarch is already installed"
            if output.failed and installed not in output:
                abort(output)


def rpm_install():
    """Install Chef for rpm based distros"""
    _add_rpm_repos()
    with show('running'):
        # Install Chef Solo
        sudo('yum -y install chef')


def emerge_install():
    """Install Chef for Gentoo"""
    with show('running'):
        sudo("USE='-test' ACCEPT_KEYWORDS='~amd64' emerge -u chef")

