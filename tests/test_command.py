import unittest
import subprocess
import os
import platform
import shutil
from os.path import join, normpath, abspath, split

import sys
env_path = "/".join(os.path.dirname(os.path.abspath(__file__)).split('/')[:-1])
sys.path.insert(0, env_path)

import littlechef


# Set some convenience variables
test_path = split(normpath(abspath(__file__)))[0]
littlechef_top = normpath(join(test_path, '..'))

if platform.system() == 'Windows':
    fix = join(littlechef_top, 'fix.cmd')
    WIN32 = True
else:
    fix = join(littlechef_top, 'fix')
    WIN32 = False


class BaseTest(unittest.TestCase):
    def setUp(self):
        """Change to the test directory"""
        self.set_location()

    def set_location(self, location=test_path):
        """Change directories to a known location"""
        os.chdir(location)

    def execute(self, call):
        """Executes a command and returns stdout and stderr"""
        if WIN32:
            proc = subprocess.Popen(call,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        else:
            proc = subprocess.Popen(call,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        return proc.communicate()


class TestConfig(BaseTest):

    def tearDown(self):
        self.set_location()

    def test_not_a_kitchen(self):
        """Should exit with error when not a kitchen directory"""
        # Change to parent dir, which has no nodes/cookbooks/roles dir
        self.set_location(littlechef_top)
        # Call fix from the current directory above "tests/"
        resp, error = self.execute([fix, 'node:a'])
        self.assertTrue("Fatal error" in error, resp)
        self.assertTrue(
            'No {0} file found'.format(littlechef.CONFIGFILE) in error, error)
        self.assertEquals(resp, "", resp)

    def test_version(self):
        """Should output the correct Little Chef version"""
        resp, error = self.execute([fix, '-v'])
        self.assertEquals(resp, "",
                          "Response should be empty, version should be in stderr")
        self.assertTrue(
            'LittleChef {0}'.format(littlechef.__version__) in error)

    def test_list_commands(self):
        """Should output a list of available commands"""
        resp, error = self.execute([fix, '-l'])
        self.assertEquals(error, "")
        expected = "Starts a Chef Solo configuration run"
        self.assertTrue(expected in resp)
        commands = resp.split('\nAvailable commands:\n')[-1]
        commands = filter(None, commands.split('\n'))
        self.assertEquals(len(commands), 21)

    def test_verbose(self):
        """Should turn on verbose output"""
        resp, error = self.execute([fix, '--verbose', 'list_nodes'])
        self.assertEquals(error, "", error)
        self.assertTrue('Verbose output on' in resp, resp)

    def test_debug(self):
        """Should turn on debug loglevel"""
        resp, error = self.execute([fix, '--debug', 'list_nodes'])
        self.assertEquals(error, "", error)
        self.assertTrue('Debug level on' in resp, resp)


class TestEnvironment(BaseTest):
    def test_no_valid_value(self):
        """Should error out when the env value is empty or is a fabric task"""
        resp, error = self.execute([fix, 'list_nodes', '--env'])
        self.assertEquals(resp, "")
        self.assertTrue(
            "error: argument -e/--env: expected one argument" in error, error)

        resp, error = self.execute([fix, '--env', 'list_nodes'])
        self.assertEquals(resp, "")
        self.assertTrue("error: No value given for --env" in error, error)

        cmd = [fix, '--env', 'nodes_with_role:base', 'role:base']
        resp, error = self.execute(cmd)
        self.assertEquals(resp, "")
        self.assertTrue("error: No value given for --env" in error, error)

    def test_valid_environment(self):
        """Should set the chef_environment value when one is given"""
        resp, error = self.execute([fix, 'list_nodes', '--env', 'staging'])
        self.assertEquals(error, "", error)
        self.assertTrue("Environment: staging" in resp, resp)


class TestRunner(BaseTest):
    def test_no_node_given(self):
        """Should abort when no node is given"""
        resp, error = self.execute([fix, 'node:'])
        self.assertTrue("Fatal error: No node was given" in error)

    def test_plugin(self):
        """Should execute the given plugin"""
        resp, error = self.execute([fix, 'node:testnode1', 'plugin:notthere'])
        expected = ", could not find 'notthere.py' in the plugin directory"
        self.assertTrue(expected in error, resp + error)

        resp, error = self.execute([fix, 'node:testnode1', 'plugin:bad'])
        expected = "Found plugin 'bad', but it seems to have a syntax error:"
        expected += " invalid syntax (bad.py, line 6)"
        self.assertTrue(expected in error, resp + error)

        resp, error = self.execute([fix, 'node:testnode1', 'plugin:dummy'])
        expected = "Executing plugin '{0}' on {1}".format("dummy", "testnode1")
        self.assertTrue(expected in resp, resp + error)

    def test_list_plugins(self):
        """Should print a list of available plugins"""
        resp, error = self.execute([fix, 'list_plugins'])
        self.assertTrue("List of available plugins:" in resp, resp)
        self.assertTrue("bad: Plugin has a syntax error" in resp, resp)
        self.assertTrue("dummy: Dummy LittleChef plugin" in resp, resp)


class TestCookbooks(BaseTest):
    def test_list_recipes(self):
        """Should list available recipes"""
        resp, error = self.execute([fix, 'list_recipes'])
        self.assertEquals(error, "")
        self.assertTrue('subversion::client' in resp)
        self.assertTrue('subversion::server' in resp)

    def test_list_recipes_site_cookbooks(self):
        """Should give priority to site-cookbooks information"""
        resp, error = self.execute([fix, 'list_recipes'])
        self.assertTrue('Modified by site-cookbooks' in resp)

    def test_list_recipes_detailed(self):
        """Should show a detailed list of available recipes"""
        resp, error = self.execute([fix, 'list_recipes_detailed'])
        self.assertTrue('subversion::client' in resp)
        for field in ['description', 'version', 'dependencies', 'attributes']:
            self.assertTrue(field in resp)

    def test_list_recipes_detailed_site_cookbooks(self):
        """Should show a detailed list of available recipes with site-cookbook
        priority

        """
        resp, error = self.execute([fix, 'list_recipes_detailed'])
        self.assertTrue('0.8.4' in resp)

    def test_no_metadata(self):
        """Should abort if cookbook has no metadata.json"""
        bad_cookbook = join(test_path, 'cookbooks', 'bad_cookbook')
        os.mkdir(bad_cookbook)
        try:
            resp, error = self.execute([fix, 'list_recipes'])
        except OSError:
            self.fail("Couldn't execute {0}".format(fix))
        finally:
            os.rmdir(bad_cookbook)
        expected = 'Fatal error: Cookbook "bad_cookbook" has no metadata.json'
        self.assertTrue(expected in error)


class TestListRoles(BaseTest):
    def test_list_roles(self):
        """Should list all roles"""
        resp, error = self.execute([fix, 'list_roles'])
        self.assertTrue('base' in resp and 'example aplication' in resp)

    def test_list_roles_detailed(self):
        """Should show a detailed list of all roles"""
        resp, error = self.execute([fix, 'list_roles_detailed'])
        self.assertTrue('base' in resp and 'example aplication' in resp)


class TestListNodes(BaseTest):
    def test_list_nodes(self):
        """Should list all nodes"""
        resp, error = self.execute([fix, 'list_nodes'])
        for node in ['testnode1', 'testnode2', 'testnode3.mydomain.com']:
            self.assertTrue(node in resp)
        self.assertTrue('Recipes: subversion' in resp)

    def test_list_nodes_in_env(self):
        """Should list all nodes in an environment"""
        resp, error = self.execute([fix, '--env', 'staging', 'list_nodes'])
        self.assertTrue('testnode2' in resp)
        self.assertFalse('testnode1' in resp)
        self.assertFalse('testnode3.mydomain.com' in resp)

    def test_list_nodes_detailed(self):
        """Should show a detailed list of all nodes"""
        resp, error = self.execute([fix, 'list_nodes_detailed'])
        self.assertTrue('testnode1' in resp)
        self.assertTrue('Recipe: subversion' in resp)

    def test_list_nodes_with_recipe(self):
        """Should list all nodes with a recipe in the run list"""
        resp, error = self.execute([fix, 'list_nodes_with_recipe:subversion'])
        self.assertTrue('testnode1' in resp)
        self.assertTrue('Recipes: subversion' in resp)

        resp, error = self.execute([fix, 'list_nodes_with_recipe:apache2'])
        self.assertFalse('testnode1' in resp)


class TestNewKitchen(BaseTest):

    def setUp(self):
        self.new_kitchen = join(test_path, 'test_new_kitchen')
        os.mkdir(self.new_kitchen)
        self.set_location(self.new_kitchen)

    def tearDown(self):
        shutil.rmtree(self.new_kitchen)
        self.set_location()

    def test_new_kitchen_creates_required_directories(self):
        resp, error = self.execute([fix, 'new_kitchen'])
        kitchen_contents = os.listdir(os.getcwd())

        self.assertTrue('roles' in kitchen_contents)
        self.assertTrue('cookbooks' in kitchen_contents)
        self.assertTrue('site-cookbooks' in kitchen_contents)
        self.assertTrue('data_bags' in kitchen_contents)
        self.assertTrue('nodes' in kitchen_contents)
        self.assertTrue('environments' in kitchen_contents)
        self.assertTrue(littlechef.CONFIGFILE in kitchen_contents)

    def test_new_kitchen_can_list_nodes(self):
        self.execute([fix, 'new_kitchen'])

        with open(littlechef.CONFIGFILE, "w") as configfh:
            print >> configfh, "[userinfo]"
            print >> configfh, "user = testuser"
            print >> configfh, "password = testpassword"

        resp, error = self.execute([fix, 'list_nodes'])
        self.assertFalse(error)
        self.assertTrue('Found 0 nodes' in resp)
        self.assertEqual('', error)
