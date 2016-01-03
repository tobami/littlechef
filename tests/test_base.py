import os
import unittest

from littlechef import runner


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            'nestedroles1',
            'testnode1',
            'testnode2',
            'testnode3.mydomain.com',
            'testnode4'
        ]
        runner.__testing__ = True
        runner.env.kitchen_path = os.getcwd()

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
        runner.env.ssh_config = None
        runner.env.key_filename = None
        runner.env.node_work_path = None
        runner.env.encrypted_data_bag_secret = None
