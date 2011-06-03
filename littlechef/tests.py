import unittest
import os
import shutil
import json

from fabric.api import *

import chef
import lib


class BaseTest(unittest.TestCase):
    def setUp(self):
        """Simulate we are inside a kitchen"""
        for d in ['nodes', 'roles', 'cookbooks']:
            shutil.copytree('../tests/{0}'.format(d), d)

    def tearDown(self):
        for d in ['nodes', 'roles', 'cookbooks']:
            shutil.rmtree(d)
        if os.path.exists('tmp_node.json'):
            os.remove('tmp_node.json')


class TestChef(BaseTest):
    def test_save_config(self):
        """Should create tmp_node.json and a nodes/testnode2.json config file"""
        env.host_string = 'testnode2'
        run_list = ["role[testrole]"]
        chef._save_config({"run_list": run_list})
        self.assertTrue(os.path.exists(os.path.join('nodes/', 'testnode2.json')))
        with open('nodes/' + 'testnode2.json', 'r') as f:
            data = json.loads(f.read())
            self.assertEquals(data['run_list'], run_list)
        # It should't overwrite existing config files
        env.host_string = 'testnode'# This node exists
        run_list = ["role[testrole]"]
        chef._save_config({"run_list": run_list})
        with open('nodes/' + 'testnode.json', 'r') as f:
            data = json.loads(f.read())
            # It should *NOT* have "testrole" assigned
            self.assertEquals(data['run_list'], ["recipe[subversion]"])

    def test_build_node(self):
        """Should build cookbooks dependencies"""
        env.host_string = 'testnode'
        cookbooks = chef._build_node(lib.get_node(env.host_string))
        self.assertEquals(cookbooks, ['subversion'])
        #TODO: add


if __name__ == "__main__":
    unittest.main()
