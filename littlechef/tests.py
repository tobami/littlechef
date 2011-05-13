import unittest
import os
import shutil

from fabric.api import *

import littlechef
import chef


class BaseTest(unittest.TestCase):
    def setUp(self):
        """Simulate we are inside a kitchen"""
        if os.path.exists('nodes'):
            shutil.rmtree('nodes')
        os.mkdir('nodes')

    def tearDown(self):
        shutil.rmtree('nodes')
        os.remove('tmp_node.json')


class TestChef(BaseTest):
    def test_save_config(self):
        """Should create tmp_node.json and a nodes/node.json config file"""
        env.host_string = 'testnode'
        chef._save_config({"run_list": ["role[testrole]"]})
        self.assertTrue(os.path.exists(os.path.join('nodes/', 'testnode.json')))

    #def test_build_node(self):
        #"""Should build cookbooks dependencies"""
        #env.host_string = 'testnode'
        #chef._save_config({"run_list": ["role[testrole]"]})
        #nodedata = {"run_list": ["role[testrole]"]}
        #chef._build_node(nodedata,
            #littlechef.cookbook_paths, littlechef.node_work_path)


if __name__ == "__main__":
    unittest.main()
