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
import json

from fabric.api import env

import sys
env_path = "/".join(os.path.dirname(os.path.abspath(__file__)).split('/')[:-1])
sys.path.insert(0, env_path)

from littlechef import runner, chef, lib


littlechef_src = os.path.split(os.path.normpath(os.path.abspath(__file__)))[0]
littlechef_top = os.path.normpath(os.path.join(littlechef_src, '..'))


class BaseTest(unittest.TestCase):
    def tearDown(self):
        if os.path.exists('tmp_node.json'):
            os.remove('tmp_node.json')


class TestRunner(BaseTest):
    def test_not_a_kitchen(self):
        """Should exit with error when not a kitchen directory"""
        # Change to a directory which is not a kitchen
        # NOTE: when used as a library chdir has no effect anyway
        # We need absolute paths for the kitchen
        os.chdir(littlechef_top)
        self.assertRaises(SystemExit, runner._readconfig)


class TestLib(unittest.TestCase):
    def test_get_node(self):
        """Should get data for a given node, empty when it doesn't exist"""
        expected = {'run_list': []}
        self.assertEquals(lib.get_node('Idon"texist'), expected)
        expected = {'run_list': ['recipe[subversion]']}
        self.assertEquals(lib.get_node('testnode1'), expected)

    def test_list_nodes(self):
        """Should list all configured nodes"""
        expected = [{'name': 'testnode1', 'run_list': ['recipe[subversion]']}]
        self.assertEquals(lib.get_nodes(), expected)

    def test_list_recipes(self):
        recipes = lib.get_recipes()
        self.assertEquals(len(recipes), 3)
        self.assertEquals(recipes[1]['description'],
            'Subversion Client installs subversion and some extra svn libs')
        self.assertEquals(recipes[2]['name'], 'subversion::server')


class TestChef(BaseTest):
    def test_save_config(self):
        """Should create a tmp_node.json and a nodes/testnode2.json config file
        """
        # Save a new node
        env.host_string = 'testnode3'
        run_list = ["role[testrole]"]
        chef._save_config({"run_list": run_list})
        file_path = os.path.join('nodes', 'testnode3.json')
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, 'r') as f:
            data = json.loads(f.read())
        os.remove(file_path)  # Clean up
        self.assertEquals(data['run_list'], run_list)

        # It should't overwrite existing config files
        env.host_string = 'testnode1'  # This node exists
        run_list = ["role[testrole]"]
        chef._save_config({"run_list": run_list})
        with open(os.path.join('nodes', 'testnode1.json'), 'r') as f:
            data = json.loads(f.read())
            # It should *NOT* have "testrole" assigned
            self.assertEquals(data['run_list'], ["recipe[subversion]"])

    def test_build_node_data_bag(self):
        """Should create a node data bag with one item per node"""
        chef._build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode1.json')
        self.assertTrue(os.path.exists(item_path))
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
            self.assertTrue('id' in data and data['id'] == 'testnode1')
            self.assertTrue('name' in data and data['name'] == 'testnode1')

        # Clean up
        chef._remove_node_data_bag()
        self.assertFalse(os.path.exists(item_path))


if __name__ == "__main__":
    unittest.main()
