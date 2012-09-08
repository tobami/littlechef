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


runner.__testing__ = True
littlechef_src = os.path.split(os.path.normpath(os.path.abspath(__file__)))[0]
littlechef_top = os.path.normpath(os.path.join(littlechef_src, '..'))


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            'nestedroles1',
            'testnode1',
            'testnode2',
            'testnode3.mydomain.com',
            'testnode4'
        ]

    def tearDown(self):
        for nodename in self.nodes + ["extranode"]:
            filename = 'tmp_' + nodename + '.json'
            if os.path.exists(filename):
                os.remove(filename)
        extra_node = os.path.join("nodes", "extranode" + '.json')
        if os.path.exists(extra_node):
            os.remove(extra_node)
        runner.env.chef_environment = None
        runner.env.hosts = []
        runner.env.all_hosts = []


class TestRunner(BaseTest):
    def test_not_a_kitchen(self):
        """Should exit with error when not a kitchen directory"""
        # Change to a directory which is not a kitchen
        # NOTE: We need absolute paths for the kitchen
        os.chdir(littlechef_top)
        self.assertRaises(SystemExit, runner._readconfig)

    def test_nodes_with_role(self):
        """Should return a list of nodes with the given role in the run_list"""
        runner.nodes_with_role("all_you_can_eat")
        self.assertEquals(runner.env.hosts, ['testnode2'])

    def test_nodes_with_role_in_env(self):
        """Should return a filtered list of nodes when an env is given"""
        runner.env.chef_environment = "staging"
        runner.nodes_with_role("all_you_can_eat")
        self.assertEquals(runner.env.hosts, ['testnode2'])

    def test_nodes_with_role_in_env_empty(self):
        runner.env.chef_environment = "production"
        self.assertRaises(
            SystemExit, runner.nodes_with_role, "all_you_can_eat")
        self.assertEquals(runner.env.hosts, [])

    def test_nodes_one(self):
        """Should configure one node when an existing node name is given"""
        runner.node('testnode1')
        self.assertEquals(runner.env.hosts, ['testnode1'])

    def test_nodes_several(self):
        """Should configure several nodes"""
        runner.node('testnode1', 'testnode2')
        self.assertEquals(runner.env.hosts, ['testnode1', 'testnode2'])

    def test_nodes_all(self):
        """Should configure all nodes when 'all' is given"""
        runner.node('all')
        self.assertEqual(runner.env.hosts, self.nodes)

    def test_nodes_all_in_env(self):
        """Should configure all nodes in a given environment when 'all' is
        given and evironment is set"""
        runner.env.chef_environment = "staging"
        runner.node('all')
        self.assertEqual(runner.env.hosts, ['testnode2'])


class TestLib(BaseTest):
    def test_get_node(self):
        """Should get data for a given node, empty when it doesn't exist"""
        # Unexisting node
        expected = {'run_list': []}
        self.assertEqual(lib.get_node('Idon"texist'), expected)
        # Existing node
        expected = {
            'chef_environment': 'production',
            'name': 'testnode1',
            'run_list': ['recipe[subversion]'],
        }
        self.assertEqual(lib.get_node('testnode1'), expected)

    def test_get_nodes(self):
        """Should return all configured nodes when no environment is given"""
        found_nodes = lib.get_nodes()
        self.assertEqual(len(found_nodes), len(self.nodes))
        expected_keys = ['name', 'chef_environment', 'run_list']
        for node in found_nodes:
            self.assertTrue(all([key in node for key in expected_keys]))

    def test_get_nodes_in_env(self):
        """Should list all nodes in the given environment"""
        self.assertEqual(len(lib.get_nodes("production")), 3)
        self.assertEqual(len(lib.get_nodes("staging")), 1)

    def test_nodes_with_role(self):
        """Should return nodes when role is present in the explicit run_list"""
        nodes = list(lib.get_nodes_with_role('all_you_can_eat'))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]['name'], 'testnode2')
        self.assertTrue('role[all_you_can_eat]' in nodes[0]['run_list'])
        
    def test_nodes_with_role_expanded(self):
        """Should return nodes when role is present in the expanded run_list"""
        # nested role 'base'
        nodes = list(lib.get_nodes_with_role('base'))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]['name'], 'testnode2')

        # Find node regardless of recursion level of role sought
        for role in ['top_level_role', 'sub_role', 'sub_sub_role', 'base']:
            nodes = list(lib.get_nodes_with_role(role))
            self.assertEqual(len(nodes), 1)
            self.assertTrue(nodes[0]['name'], 'nestedroles1')

    def test_nodes_with_role_wildcard(self):
        """Should return nodes when wildcard is given and role is asigned"""
        nodes = list(lib.get_nodes_with_role('all_*'))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]['name'], 'testnode2')
        # Prefix with no wildcard
        nodes = list(lib.get_nodes_with_role('all_'))
        self.assertEqual(len(nodes), 0)
        # Nodes with at least one role
        nodes = list(lib.get_nodes_with_role('*'))

        self.assertEqual(len(nodes), 2)
        nodes = list(lib.get_nodes_with_role(''))
        self.assertEqual(len(nodes), 0)

    def test_nodes_with_role_in_env(self):
        """Should return all nodes with a given role and in the given env"""
        nodes = list(lib.get_nodes_with_role('all_you_can_eat', 'staging'))
        self.assertEquals(len(nodes), 1)
        self.assertEquals(nodes[0]['name'], 'testnode2')
        # No nodes in production with this role
        nodes = list(lib.get_nodes_with_role('all_you_can_eat', 'production'))
        self.assertFalse(len(nodes))

    def test_nodes_with_recipe(self):
        """Should return all nodes with a given recipe"""
        # All nodes have the subversion recipe in the expanded run_list
        nodes = list(lib.get_nodes_with_recipe('subversion'))
        self.assertEquals(len(nodes), 3)
        nodes = list(lib.get_nodes_with_recipe('sub*'))
        self.assertEquals(len(nodes), 3)
        nodes = list(lib.get_nodes_with_recipe('vim'))
        self.assertEquals(len(nodes), 1)
        self.assertEquals(nodes[0]['name'], 'testnode3.mydomain.com')
        # man recipe inside role "all_you_can_eat" and in testnode4
        nodes = list(lib.get_nodes_with_recipe('man'))
        self.assertEquals(len(nodes), 2)
        self.assertEquals(nodes[0]['name'], 'testnode2')
        # Get node with at least one recipe
        nodes = list(lib.get_nodes_with_recipe('*'))
        self.assertEquals(len(nodes), 4)
        nodes = list(lib.get_nodes_with_role(''))
        self.assertEquals(len(nodes), 0)

    def test_nodes_with_recipe_in_env(self):
        """Should return all nodes with a given recipe and in the given env"""
        nodes = list(lib.get_nodes_with_recipe('subversion', 'production'))
        self.assertEquals(len(nodes), 2)
        self.assertEquals(nodes[0]['name'], 'testnode1')
        nodes = list(lib.get_nodes_with_recipe('subversion', 'staging'))
        self.assertEquals(len(nodes), 1)
        # No nodes in staging with this role
        nodes = list(lib.get_nodes_with_recipe('vim', 'staging'))
        self.assertFalse(len(nodes))

    def test_list_recipes(self):
        recipes = lib.get_recipes()
        self.assertEquals(len(recipes), 6)
        self.assertEquals(recipes[1]['name'], 'subversion')
        self.assertEquals(recipes[1]['description'],
            'Includes the client recipe. Modified by site-cookbooks')
        self.assertEquals(recipes[2]['name'], 'subversion::client')
        self.assertEquals(recipes[2]['description'],
            'Subversion Client installs subversion and some extra svn libs')
        self.assertEquals(recipes[3]['name'], 'subversion::server')
        self.assertIn('subversion::testrecipe', [r['name'] for r in recipes])

    def test_import_plugin(self):
        """Should import the given plugin"""
        plugin = lib.import_plugin("dummy")
        expected = "Dummy LittleChef plugin"
        self.assertEquals(plugin.__doc__, expected)

        # Should fail to import a bad plugin module
        self.assertRaises(SystemExit, lib.import_plugin, "bad")

    def test_get_plugins(self):
        """Should get a list of available plugins"""
        plugins = [p for p in lib.get_plugins()]
        self.assertEquals(len(plugins), 2)
        self.assertEquals(plugins[0]['bad'], "Plugin has a syntax error")


class TestChef(BaseTest):
    def tearDown(self):
        chef._remove_local_node_data_bag()
        super(TestChef, self).tearDown()

    def test_save_config(self):
        """Should create a tmp_extranode.json and a nodes/extranode.json config
        file

        """
        # Save a new node
        env.host_string = 'extranode'
        run_list = ["role[base]"]
        chef.save_config({"run_list": run_list})
        file_path = os.path.join('nodes', 'extranode.json')
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, 'r') as f:
            data = json.loads(f.read())
        self.assertEquals(data['run_list'], run_list)

        # It should't overwrite existing config files
        env.host_string = 'testnode1'  # This node exists
        run_list = ["role[base]"]
        chef.save_config({"run_list": run_list})
        with open(os.path.join('nodes', 'testnode1.json'), 'r') as f:
            data = json.loads(f.read())
            # It should *NOT* have "base" assigned
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
        self.assertTrue(
            'recipes' in data and data['recipes'] == ['subversion'])
        self.assertTrue(
            'recipes' in data and data['role'] == [])
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        self.assertTrue(os.path.exists(item_path))
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('id' in data and data['id'] == 'testnode2')
        self.assertTrue('recipes' in data)
        self.assertEquals(data['recipes'], [u'subversion', u'man', u'vim'])
        self.assertTrue('recipes' in data)
        self.assertEquals(data['role'], [u'all_you_can_eat'])
        self.assertEquals(data['roles'], [u'base', u'all_you_can_eat'])

    def test_build_node_data_bag_nonalphanumeric(self):
        """Should create a node data bag when node name contains invalid chars
        """
        chef._build_node_data_bag()
        # A node called testnode3.mydomain.com will have the data bag id
        # 'testnode3', because dots are not allowed.
        filename = 'testnode3_mydomain_com'
        nodename = filename.replace("_", ".")
        item_path = os.path.join('data_bags', 'node', filename + '.json')
        self.assertTrue(os.path.exists(item_path), "node file does not exist")
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('id' in data and data['id'] == filename)
        self.assertTrue('name' in data and data['name'] == nodename)

    def test_automatic_attributes(self):
        """Should add Chef's automatic attributes"""
        chef._build_node_data_bag()
        # Check node with single word fqdn
        testnode1_path = os.path.join('data_bags', 'node', 'testnode1.json')
        with open(testnode1_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('fqdn' in data and data['fqdn'] == 'testnode1')
        self.assertTrue('hostname' in data and data['hostname'] == 'testnode1')
        self.assertTrue('domain' in data and data['domain'] == '')

        # Check node with complex fqdn
        testnode3_path = os.path.join(
            'data_bags', 'node', 'testnode3_mydomain_com.json')
        with open(testnode3_path, 'r') as f:
            print testnode3_path
            data = json.loads(f.read())
        self.assertTrue(
            'fqdn' in data and data['fqdn'] == 'testnode3.mydomain.com')
        self.assertTrue('hostname' in data and data['hostname'] == 'testnode3')
        self.assertTrue('domain' in data and data['domain'] == 'mydomain.com')

    def test_attribute_merge_cookbook_not_found(self):
        """Should print a warning when merging a node and a cookbook is not
        found

        """
        # Save new node with a non-existing cookbook assigned
        env.host_string = 'extranode'
        chef.save_config({"run_list": ["recipe[phantom_cookbook]"]})
        self.assertRaises(SystemExit, chef._build_node_data_bag)

    def test_attribute_merge_cookbook_default(self):
        """Should have the value found in recipe/attributes/default.rb"""
        chef._build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertTrue(data['subversion']['repo_name'] == 'repo')

    def test_attribute_merge_cookbook_boolean(self):
        """Should have real boolean values for default cookbook attributes"""
        chef._build_node_data_bag()
        item_path = os.path.join(
            'data_bags', 'node', 'testnode3_mydomain_com.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('vim' in data)
        self.assertTrue(data['vim']['sucks'] is True)

    def test_attribute_merge_site_cookbook_default(self):
        """Should have the value found in
        site_cookbooks/xx/recipe/attributes/default.rb

        """
        chef._build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertTrue(data['subversion']['repo_dir'] == '/srv/svn2')

    def test_attribute_merge_role_not_found(self):
        """Should print a warning when an assigned role if not found"""
        # Save new node with a non-existing cookbook assigned
        env.host_string = 'extranode'
        chef.save_config({"run_list": ["role[phantom_role]"]})
        self.assertRaises(SystemExit, chef._build_node_data_bag)

    def test_attribute_merge_role_default(self):
        """Should have the value found in the roles default attributes"""
        chef._build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertEquals(
            data['subversion']['repo_server'], 'role_default_repo_server')
        self.assertTrue('other_attr' in data)
        self.assertEquals(data['other_attr']['other_key'], 'nada')

    def test_attribute_merge_node_normal(self):
        """Should have the value found in the node attributes"""
        chef._build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertEquals(data['subversion']['user'], 'node_user')

    def test_attribute_merge_role_override(self):
        """Should have the value found in the roles override attributes"""
        chef._build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertEquals(data['subversion']['password'], 'role_override_pass')

    def test_attribute_merge_deep_dict(self):
        """Should deep-merge a dict when it is defined in two different places
        """
        chef._build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('other_attr' in data)
        expected = {
            "deep_dict": {
                "deep_key1": "node_value1",
                "deep_key2": "role_value2"
            }
        }
        self.assertTrue(data['other_attr']['deep_dict'], expected)

if __name__ == "__main__":
    unittest.main()
