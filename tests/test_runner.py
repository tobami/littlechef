from ConfigParser import SafeConfigParser

from mock import patch
from nose.tools import raises

from littlechef import runner
from test_base import BaseTest


class TestConfig(BaseTest):

    def test_get_config(self):
        """Should read configuration from config file when config.cfg is found
        """
        #runner.CONFIGFILE="./tests/littlechef.cfg"
        runner._readconfig()
        self.assertEqual(runner.env.ssh_config_path, None)
        self.assertEqual(runner.env.ssh_config, None)
        self.assertEqual(runner.env.user, "testuser")
        self.assertEqual(runner.env.password, "testpass")
        self.assertEqual(runner.env.key_filename, None)
        self.assertEqual(runner.env.node_work_path, "/tmp/chef-solo")
        self.assertEqual(runner.env.encrypted_data_bag_secret, None)
        self.assertEqual(runner.env.sync_packages_dest_dir, "/srv/repos")
        self.assertEqual(runner.env.sync_packages_local_dir, "./repos")

    def test_not_a_kitchen(self):
        """Should abort when no config file found"""
        with patch.object(SafeConfigParser, 'read') as mock_method:
            mock_method.return_value = []
            self.assertRaises(SystemExit, runner._readconfig)


class TestNode(BaseTest):

    def test_node_one(self):
        """Should configure one node when an existing node name is given"""
        runner.node('testnode1')
        self.assertEqual(runner.env.hosts, ['testnode1'])

    def test_node_several(self):
        """Should configure several nodes"""
        runner.node('testnode1', 'testnode2')
        self.assertEqual(runner.env.hosts, ['testnode1', 'testnode2'])

    def test_node_all(self):
        """Should configure all nodes when 'all' is given"""
        runner.node('all')
        self.assertEqual(runner.env.hosts, self.nodes)

    def test_node_all_in_env(self):
        """Should configure all nodes in a given environment when 'all' is
        given and evironment is set"""
        runner.env.chef_environment = "staging"
        runner.node('all')
        self.assertEqual(runner.env.hosts, ['testnode2'])


class TestNodesWithRole(BaseTest):

    def test_nodes_with_role(self):
        """Should return a list of nodes with the given role in the run_list"""
        runner.nodes_with_role('base')
        self.assertEqual(runner.env.hosts, ['nestedroles1', 'testnode2'])

    def test_nodes_with_role_in_env(self):
        """Should return a filtered list of nodes with role when an env is given
        """
        runner.env.chef_environment = "staging"
        runner.nodes_with_role('base')
        self.assertEqual(runner.env.hosts, ['testnode2'])

    @raises(SystemExit)
    def test_nodes_with_role_in_env_not_found(self):
        """Should abort when no nodes with given role found in the environment
        """
        runner.env.chef_environment = "production"
        runner.nodes_with_role('base')


class TestNodesWithRecipe(BaseTest):

    def test_nodes_with_role(self):
        """Should return a list of nodes with the given recipe in the run_list"""
        runner.nodes_with_recipe('man')
        self.assertEqual(runner.env.hosts, ['testnode2', 'testnode4'])

    def test_nodes_with_role_in_env(self):
        """Should return a filtered list of nodes with recipe when an env is given
        """
        runner.env.chef_environment = "staging"
        runner.nodes_with_recipe('man')
        self.assertEqual(runner.env.hosts, ['testnode2'])

    @raises(SystemExit)
    def test_nodes_with_role_in_env_not_found(self):
        """Should abort when no nodes with given recipe found in the environment
        """
        runner.env.chef_environment = "_default"
        runner.nodes_with_recipe('man')


class TestNodesWithTag(BaseTest):

    def test_nodes_with_tag(self):
        """Should return a list of nodes with the given tag"""
        runner.nodes_with_tag('top')
        self.assertEqual(runner.env.hosts, ['nestedroles1'])

    def test_nodes_with_tag_in_env(self):
        """Should return a filtered list of nodes with tag when an env is given
        """
        runner.env.chef_environment = "production"
        runner.nodes_with_tag('dummy')
        self.assertEqual(runner.env.hosts, ['testnode4'])

    @raises(SystemExit)
    def test_nodes_with_tag_in_env_not_found(self):
        """Should abort when no nodes with given tag found in the environment
        """
        runner.env.chef_environment = "production"
        runner.nodes_with_role('top')
