import unittest
import os
import shutil
import json
from os.path import join, split, sep, normpath, abspath, exists
from fabric.api import *

import littlechef
import chef
import lib

# Set some convenience variables
littlechef_src = split(normpath(abspath(littlechef.__file__)))[0]
littlechef_top = normpath(join(littlechef_src, '..'))
littlechef_tests = join(littlechef_top, 'tests')

class BaseTest(unittest.TestCase):
    def setUp(self):
        """Simulate we are inside a kitchen"""
        # Orient ourselves
        os.chdir(littlechef_src)
        for d in ['nodes', 'roles', 'cookbooks', 'data_bags']:
            shutil.copytree(join(littlechef_tests, '{0}'.format(d)), d)

    def tearDown(self):
        for d in ['nodes', 'roles', 'cookbooks', 'data_bags']:
            shutil.rmtree(d)
        if exists('tmp_node.json'):
            os.remove('tmp_node.json')


class TestLib(BaseTest):
    def test_get_node(self):
        """Should get data for a given node, empty when it doesn't exist"""
        expected = {'run_list': []}
        self.assertEquals(lib.get_node('Idon"texist'), expected)
        expected = {'run_list': ['recipe[subversion]']}
        self.assertEquals(lib.get_node('testnode'), expected)

    def test_list_nodes(self):
        """Should list all configured nodes"""
        expected = [{'name': 'testnode', 'run_list': ['recipe[subversion]']}]
        self.assertEquals(lib.get_nodes(), expected)

    def test_list_recipes(self):
        recipes = lib.get_recipes()
        self.assertEquals(len(recipes), 3)
        self.assertEquals(recipes[1]['description'],
            'Subversion Client installs subversion and some extra svn libs')
        self.assertEquals(recipes[2]['name'], 'subversion::server')


class TestChef(BaseTest):
    def test_save_config(self):
        """Should create tmp_node.json and a nodes/testnode2.json config file"""
        env.host_string = 'testnode2'
        run_list = ["role[testrole]"]
        chef._save_config({"run_list": run_list})
        self.assertTrue(exists(join('nodes', 'testnode2.json')))
        with open(join('nodes','testnode2.json'), 'r') as f:
            data = json.loads(f.read())
            self.assertEquals(data['run_list'], run_list)
        # It should't overwrite existing config files
        env.host_string = 'testnode'# This node exists
        run_list = ["role[testrole]"]
        chef._save_config({"run_list": run_list})
        with open(join('nodes','testnode.json'), 'r') as f:
            data = json.loads(f.read())
            # It should *NOT* have "testrole" assigned
            self.assertEquals(data['run_list'], ["recipe[subversion]"])

    def test_build_node(self):
        """Should build cookbooks dependencies"""
        env.host_string = 'testnode'
        cookbooks = chef._build_node(lib.get_node(env.host_string))
        self.assertEquals(cookbooks, ['subversion'])
        #TODO: add more cookbooks with dependencies, add apache2


if __name__ == "__main__":
    unittest.main()
