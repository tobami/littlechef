"""LittleChef's setup.py"""
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import platform


scripts = ['fix']
if platform.system() == 'Windows':
    scripts += ['fix.cmd']

setup(
    name="littlechef",
    version=__import__('littlechef').__version__,
    description="Cook with Chef without a Chef Server",
    author="Miquel Torres",
    author_email="tobami@googlemail.com",
    url="http://github.com/tobami/littlechef",
    download_url="http://github.com/tobami/littlechef/archives/master",
    keywords=["chef", "devops", "operations", "sysadmin"],
    install_requires=['fabric>=1.3.2', 'simplejson>=2.1.0', 'ssh'],
    packages=['littlechef'],
    package_data={
        'littlechef': ['search.rb', 'solo.rb', 'parser.rb', 'environment.rb']
    },
    scripts=['fix'],
    test_suite='nose.collector',
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable ",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        'Topic :: System :: Systems Administration',
        ],
    long_description="""\
Cook with Chef without a Chef Server
-------------------------------------
With LittleChef you will be able to get started more quickly cooking with
Chef_, the excellent Configuration Management System.

You will just need your local (preferably version controled) kitchen with all
your cookbooks, roles data bags and nodes, which will get rsynced to a node
each time you start a Chef Solo configuration run with the bundled 'fix'
command.

It also adds features to Chef Solo that are currently only available for Chef
Server users: data bag search, and node search.

.. _Chef: http://wiki.opscode.com/display/chef/Home
"""
)
