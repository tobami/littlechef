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
import os
import json

from fabric.api import env
from mock import patch
from nose.tools import raises

import sys
env_path = "/".join(os.path.dirname(os.path.abspath(__file__)).split('/')[:-1])
sys.path.insert(0, env_path)

from littlechef import chef, lib, solo, exceptions
from test_base import BaseTest

littlechef_src = os.path.split(os.path.normpath(os.path.abspath(__file__)))[0]
littlechef_top = os.path.normpath(os.path.join(littlechef_src, '..'))


class TestSolo(BaseTest):
    def test_configure_no_sudo_rights(self):
        """Should abort when user has no sudo rights"""
        env.host_string = "extranode"
        with patch.object(solo, 'exists') as mock_exists:
            mock_exists.return_value = False
            with patch.object(solo, 'sudo') as mock_sudo:
                mock_sudo.failed = True
                self.assertRaises(SystemExit, solo.configure)

    @raises(SystemExit)
    @patch('littlechef.solo.exists')
    def test_configure_bad_credentials(self, mock_exists):
        """Should return True when node has been synced"""
        mock_exists.side_effect = EOFError(
            '/usr/lib64/python2.6/getpass.py:83: GetPassWarning: '
            'Can not control echo on the terminal.')
        solo.configure()


class TestLib(BaseTest):

    def test_get_node_not_found(self):
        """Should get empty template when node is not found"""
        name = 'Idon"texist'
        expected = {'chef_environment': '_default', 'name': name, 'run_list': []}
        self.assertEqual(lib.get_node(name), expected)

    def test_get_node_found(self):
        """Should get node data when node is found"""
        expected = {
            'chef_environment': 'production',
            'name': 'testnode1',
            'run_list': ['recipe[subversion]'],
        }
        self.assertEqual(lib.get_node('testnode1'), expected)

    def test_get_node_default_env(self):
        """Should set env to _default when node sets no chef_environment"""
        expected = {
            'chef_environment': '_default',
            'name': 'nestedroles1',
            'run_list': ['role[top_level_role]'],
            'tags': ['top'],
        }
        self.assertEqual(lib.get_node('nestedroles1'), expected)

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
        self.assertEqual(len(nodes), 2)
        expected_nodes = ['nestedroles1', 'testnode2']
        for node in nodes:
            self.assertTrue(node['name'] in expected_nodes)
            expected_nodes.remove(node['name'])

        # Find node regardless of recursion level of role sought
        for role in ['top_level_role', 'sub_role', 'sub_sub_role']:
            nodes = list(lib.get_nodes_with_role(role))
            self.assertEqual(len(nodes), 1)
            self.assertTrue(nodes[0]['name'], 'nestedroles1')

    def test_nodes_with_role_wildcard(self):
        """Should return node when wildcard is given and role is asigned"""
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
        """Should return node when role is asigned and environment matches"""
        nodes = list(lib.get_nodes_with_role('all_you_can_eat', 'staging'))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]['name'], 'testnode2')
        # No nodes in production with this role
        nodes = list(lib.get_nodes_with_role('all_you_can_eat', 'production'))
        self.assertFalse(len(nodes))

    def test_nodes_with_recipe(self):
        """Should return node when recipe is in the explicit run_list"""
        nodes = list(lib.get_nodes_with_recipe('vim'))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]['name'], 'testnode3.mydomain.com')

    def test_nodes_with_recipe_expanded(self):
        """Should return node when recipe is in the expanded run_list"""
        # 'subversion' is in the 'base' role
        nodes = list(lib.get_nodes_with_recipe('subversion'))
        self.assertEqual(len(nodes), 4)

        # man recipe inside role "all_you_can_eat" and in testnode4
        nodes = list(lib.get_nodes_with_recipe('man'))
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0]['name'], 'testnode2')

    def test_nodes_with_recipe_wildcard(self):
        """Should return node when wildcard is given and role is asigned"""
        nodes = list(lib.get_nodes_with_recipe('sub*'))
        self.assertEqual(len(nodes), 4)

        # Get node with at least one recipe
        nodes = list(lib.get_nodes_with_recipe('*'))
        self.assertEqual(len(nodes), 5)
        nodes = list(lib.get_nodes_with_role(''))
        self.assertEqual(len(nodes), 0)

    def test_nodes_with_recipe_in_env(self):
        """Should return all nodes with a given recipe and in the given env"""
        nodes = list(lib.get_nodes_with_recipe('subversion', 'production'))
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0]['name'], 'testnode1')
        nodes = list(lib.get_nodes_with_recipe('subversion', 'staging'))
        self.assertEqual(len(nodes), 1)
        # No nodes in staging with this role
        nodes = list(lib.get_nodes_with_recipe('vim', 'staging'))
        self.assertFalse(len(nodes))

    def test_get_nodes_with_tag(self):
        """Should list all nodes with tag 'top'"""
        nodes = list(lib.get_nodes_with_tag('top'))
        self.assertEqual(len(nodes), 1)

    def test_get_nodes_with_tag_in_env(self):
        """Should list all nodes with tag 'top' in the given environment"""
        nodes = list(lib.get_nodes_with_tag('top', 'production'))
        self.assertEqual(len(nodes), 0)
        nodes = list(lib.get_nodes_with_tag('top', '_default'))
        self.assertEqual(len(nodes), 1)

    def test_list_recipes(self):
        recipes = lib.get_recipes()
        self.assertEqual(len(recipes), 6)
        self.assertEqual(recipes[1]['name'], 'subversion')
        self.assertEqual(recipes[1]['description'],
                         'Includes the client recipe. Modified by site-cookbooks')
        self.assertEqual(recipes[2]['name'], 'subversion::client')
        self.assertEqual(recipes[2]['description'],
                         'Subversion Client installs subversion and some extra svn libs')
        self.assertEqual(recipes[3]['name'], 'subversion::server')
        self.assertIn('subversion::testrecipe', [r['name'] for r in recipes])

    def test_import_plugin(self):
        """Should import the given plugin"""
        plugin = lib.import_plugin("dummy")
        expected = "Dummy LittleChef plugin"
        self.assertEqual(plugin.__doc__, expected)

        # Should fail to import a bad plugin module
        self.assertRaises(SystemExit, lib.import_plugin, "bad")

    def test_get_plugins(self):
        """Should get a list of available plugins"""
        plugins = [p for p in lib.get_plugins()]
        self.assertEqual(len(plugins), 2)
        self.assertEqual(plugins[0]['bad'], "Plugin has a syntax error")

    def test_get_environments(self):
        """Should get a list of all environments"""
        environments = lib.get_environments()
        self.assertEqual(sorted(env['name'] for env in environments),
                         ['production', 'staging'])

    def test_get_existing_environment(self):
        """Should return an existing environment object from the kitchen"""
        environment = lib.get_environment('production')
        self.assertTrue('subversion' in environment['default_attributes'])
        self.assertEqual(environment['default_attributes']['subversion']['user'], 'tom')

    def test_get__default_environment(self):
        """Should return empty env when name is '_default'"""
        expected = {
            "name": "_default",
            "default_attributes": {},
            "json_class": "Chef::Environment",
            "chef_type": "environment",
            "description": "",
            "cookbook_versions": {}
        }
        self.assertEqual(lib.get_environment('_default'), expected)

    @raises(exceptions.FileNotFoundError)
    def test_get_nonexisting_environment(self):
        """Should raise FileNotFoundError when environment does not exist"""
        lib.get_environment('not-exists')


class TestChef(BaseTest):
    def tearDown(self):
        chef.remove_local_node_data_bag()
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
        self.assertEqual(data['run_list'], run_list)

        # It should't overwrite existing config files
        env.host_string = 'testnode1'  # This node exists
        run_list = ["role[base]"]
        chef.save_config({"run_list": run_list})
        with open(os.path.join('nodes', 'testnode1.json'), 'r') as f:
            data = json.loads(f.read())
            # It should *NOT* have "base" assigned
            self.assertEqual(data['run_list'], ["recipe[subversion]"])

    def test_get_ipaddress(self):
        """Should add ipaddress attribute when ohai returns correct IP address
        """
        class MockSudoReturnValue(str):
            succeeded = True

        node = {}
        fake_ip = "1.1.1.2"
        with patch.object(chef, 'sudo') as mock_method:
            mocked_ohai_response = '["{0}"]'.format(fake_ip)
            mock_method.return_value = MockSudoReturnValue(mocked_ohai_response)
            response = chef._get_ipaddress(node)
        self.assertTrue(response)
        self.assertEqual(node['ipaddress'], fake_ip)

    def test_get_ipaddress_attribute_exists(self):
        """Should not save ipaddress when attribute exists"""
        class MockSudoReturnValue(str):
            succeeded = True

        node = {'ipaddress': '1.1.1.1'}
        with patch.object(chef, 'sudo') as mock_method:
            mocked_ohai_response = '["{0}"]'.format("1.1.1.2")
            mock_method.return_value = MockSudoReturnValue(mocked_ohai_response)
            response = chef._get_ipaddress(node)
        self.assertFalse(response)
        self.assertEqual(node['ipaddress'], '1.1.1.1')

    def test_get_ipaddress_bad_ohai_output(self):
        """Should abort when ohai's output cannot be parsed"""
        class MockSudoReturnValue(str):
            succeeded = True

        with patch.object(chef, 'sudo') as mock_method:
            mocked_ohai_response = ('Invalid gemspec '
                                    '["{0}"]'.format("1.1.1.2"))
            mock_method.return_value = MockSudoReturnValue(mocked_ohai_response)
            self.assertRaises(SystemExit, chef._get_ipaddress, {})

    def test_build_node_data_bag(self):
        """Should create a node data bag with one item per node"""
        chef.build_node_data_bag()
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
        self.assertEqual(data['recipes'], [u'subversion', u'man'])
        self.assertTrue('recipes' in data)
        self.assertEqual(data['role'], [u'all_you_can_eat'])
        self.assertEqual(data['roles'], [u'base', u'all_you_can_eat'])

    def test_build_node_data_bag_nonalphanumeric(self):
        """Should create a node data bag when node name contains invalid chars
        """
        chef.build_node_data_bag()
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
        chef.build_node_data_bag()
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
        self.assertRaises(SystemExit, chef.build_node_data_bag)

    def test_attribute_merge_cookbook_default(self):
        """Should have the value found in recipe/attributes/default.rb"""
        chef.build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertTrue(data['subversion']['repo_name'] == 'repo')

    def test_attribute_merge_environment_default(self):
        """Should have the value found in environment/ENV.json"""
        chef.build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode1.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertEqual(data['subversion']['user'], 'tom')

    def test_attribute_merge_cookbook_boolean(self):
        """Should have real boolean values for default cookbook attributes"""
        chef.build_node_data_bag()
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
        chef.build_node_data_bag()
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
        self.assertRaises(SystemExit, chef.build_node_data_bag)

    def test_attribute_merge_role_default(self):
        """Should have the value found in the roles default attributes"""
        chef.build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertEqual(
            data['subversion']['repo_server'], 'role_default_repo_server')
        self.assertTrue('other_attr' in data)
        self.assertEqual(data['other_attr']['other_key'], 'nada')

    def test_attribute_merge_node_normal(self):
        """Should have the value found in the node attributes"""
        chef.build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertEqual(data['subversion']['user'], 'node_user')

    def test_attribute_merge_role_override(self):
        """Should have the value found in the roles override attributes"""
        chef.build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode2.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertEqual(data['subversion']['password'], 'role_override_pass')

    def test_attribute_merge_environment_override(self):
        """Should have the value found in the environment override attributes"""
        chef.build_node_data_bag()
        item_path = os.path.join('data_bags', 'node', 'testnode1.json')
        with open(item_path, 'r') as f:
            data = json.loads(f.read())
        self.assertTrue('subversion' in data)
        self.assertEqual(data['subversion']['password'], 'env_override_pass')

    def test_attribute_merge_deep_dict(self):
        """Should deep-merge a dict when it is defined in two different places
        """
        chef.build_node_data_bag()
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

    def test_sync_node_dummy_attr(self):
        """Should return False when node has a dummy tag or dummy=true"""
        self.assertFalse(chef.sync_node({'name': 'extranode', 'dummy': True}))
        self.assertFalse(chef.sync_node({'name': 'extranode', 'tags': ['dummy']}))

    @patch('littlechef.chef.solo.configure')
    @patch('littlechef.chef._get_ipaddress')
    @patch('littlechef.chef._synchronize_node')
    @patch('littlechef.chef._configure_node')
    @patch('littlechef.chef._node_cleanup')
    def test_sync_node(self, mock_method1, mock_ipaddress, mock_method3,
                       mock_method4, mock_method5):
        """Should return True when node has been synced"""
        env.host_string = 'extranode'
        mock_ipaddress.return_value = False
        test_node = {'name': 'extranode', 'dummy': False, 'run_list': []}
        self.assertTrue(chef.sync_node(test_node))
