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
import unittest
import os
import shutil
import json
from os.path import join, split, sep, normpath, abspath, exists

from fabric.api import *

import chef
import lib
import runner


# Set paths
littlechef_src = split(normpath(abspath(__file__)))[0]
littlechef_top = normpath(join(littlechef_src, '..'))
littlechef_tests = join(littlechef_top, 'tests')


class BaseTest(unittest.TestCase):
    def setUp(self):
        """Simulate we are inside a kitchen"""
        # Orient ourselves
        os.chdir(littlechef_src)
        for d in ['nodes', 'roles', 'cookbooks', 'data_bags']:
            shutil.copytree(join(littlechef_tests, '{0}'.format(d)), d)
        shutil.copy(join(littlechef_tests, 'auth.cfg'), littlechef_src)

    def tearDown(self):
        os.chdir(littlechef_src)
        for d in ['nodes', 'roles', 'cookbooks', 'data_bags']:
            shutil.rmtree(d)
        if exists('tmp_node.json'):
            os.remove('tmp_node.json')
        os.remove('auth.cfg')


class TestRunner(BaseTest):
    def test_not_a_kitchen(self):
        """Should exit with error when not a kitchen directory"""
        # Change to a directory which is not a kitchen
        os.chdir(littlechef_top)
        self.assertRaises(SystemExit, runner._readconfig)

    def test_readconfig(self):
        """Should read auth.cfg and properly configure variables"""
        runner._readconfig()
        self.assertEquals(env.password, 'testpass')


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
