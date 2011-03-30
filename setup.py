# LittleChef's setup.py
from distutils.core import setup
setup(
    name = "littlechef",
    version = __import__('littlechef').version,
    description = "Cook with Chef without a Chef Server",
    author = "Miquel Torres",
    author_email = "tobami@googlemail.com",
    url = "http://github.com/tobami/littlechef",
    download_url = "http://github.com/tobami/littlechef/archives/master",
    keywords = ["chef", "devops"],
    install_requires=['fabric>=1.0.1', 'simplejson'],
    py_modules = ['littlechef'],
    scripts = ['cook'],
    zip_safe=False,
    classifiers = [
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        'Topic :: System :: Systems Administration',
        ],
    long_description = """\
Cook with Chef without Chef Server
-------------------------------------
With LittleChef you will get all you need to start cooking with Chef_.

It works as follows: Whenever you apply a recipe to a node, all needed cookbooks and its dependencies are gzipped and uploaded to that node. A node.json file gets created on the fly and uploaded, and Chef Solo gets executed at the remote node, using node.json as the node configuration and the pre-installed solo.rb for Chef Solo configuration. Cookbooks and roles are configured to be found at (/tmp/chef-solo/).

The result is that you can play as often with your recipes and nodes as you want, without having to worry about repositories, central servers nor anything else. Once you are satisfied with a new feature in a cookbook, you can commit the littlechef/cookbook/ directory to your repository. LittleChef brings back sanity to cookbook development.

.. _Chef: http://wiki.opscode.com/display/chef/Home
"""
)
