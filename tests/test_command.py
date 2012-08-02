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
import subprocess
import os
import platform
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
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            proc = subprocess.Popen(call,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.communicate()


class TestConfig(BaseTest):
    def test_not_a_kitchen(self):
        """Should exit with error when not a kitchen directory"""
        # Change to parent dir, which has no nodes/cookbooks/roles dir
        self.set_location(littlechef_top)
        # Call fix from the current directory above "tests/"
        resp, error = self.execute([fix, '-l'])
        self.assertTrue("Fatal error" in error, resp)
        self.assertTrue("outside of a kitchen" in error, error)
        self.assertEquals(resp, "", resp)
        # Return to test dir
        self.set_location()

    def test_version(self):
        """Should output the correct Little Chef version"""
        resp, error = self.execute([fix, '-v'])
        self.assertEquals(error, "", error)
        self.assertTrue(
            'LittleChef {0}'.format(littlechef.__version__) in resp)

    def test_list_commands(self):
        """Should output a list of available commands"""
        resp, error = self.execute([fix, '-l'])
        self.assertEquals(error, "")
        expected = "LittleChef: Configuration Management using Chef Solo"
        self.assertTrue(expected in resp)
        self.assertEquals(len(resp.split('\n')), 22)

    #def test_verbose(self):
        #"""Should turn on verbose output"""
        #resp, error = self.execute([fix, '--verbose', 'node:testnode1'])
        #self.assertEquals(error, "", error)
        #self.assertTrue('Verbose output on' in resp, resp)

    #def test_debug(self):
        #"""Should turn on debug loglevel"""
        #resp, error = self.execute([fix, '--debug', 'node:testnode1'])
        #self.assertEquals(error, "", error)
        #self.assertTrue('Debug on' in resp, resp)


class TestEnvironment(BaseTest):
    def test_no_valid_value(self):
        """Should error out when the env value is empty or is a fabric task"""
        resp, error = self.execute([fix, 'list_nodes', '--env'])
        self.assertEquals(resp, "")
        self.assertTrue(
            "error: --env option requires an argument" in error, error)

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

    def test_one_node(self):
        """Should try to configure the given node"""
        resp, error = self.execute([fix, 'node:testnode2'])
        self.assertTrue("== Configuring testnode2 ==" in resp)
        # Will try to configure testnode2 and will fail DNS lookup
        self.assertTrue("tal error: Name lookup failed for testnode2" in error,
                        error)
    #def test_dummy_node(self): # FIXME: Needs mocking
        """Should *not* configure a node when dummy is set to true"""
        #resp, error = self.execute([fix, 'node:testnode4'])
        #self.assertTrue("== Skipping dummy: testnode4 ==" in resp)

    def test_several_nodes(self):
        """Should try to configure two nodes"""
        resp, error = self.execute([fix, 'node:testnode2,testnode1'])
        self.assertTrue("== Configuring testnode2 ==" in resp)
        # Will try to configure *first* testnode2 and will fail DNS lookup
        self.assertTrue("tal error: Name lookup failed for testnode2" in error)

    def test_recipe(self):
        """Should configure node with the given recipe"""
        resp, error = self.execute(
            [fix, 'node:testnode1', 'recipe:subversion'])
        self.assertTrue("plying recipe 'subversion' on node testnode1" in resp)
        self.assertTrue("tal error: Name lookup failed for testnode1" in error)

    def test_role(self):
        """Should configure node with the given role"""
        resp, error = self.execute([fix, 'node:testnode1', 'role:base'])
        self.assertTrue("== Applying role 'base' to testnode1 ==" in resp)
        self.assertTrue("tal error: Name lookup failed for testnode1" in error)

    def test_ssh(self):
        """Should execute the given ssh command"""
        resp, error = self.execute([fix, 'node:testnode2', 'ssh:"my command"'])
        expected = "Executing the command '\"my command\"' on the node"
        expected += " testnode2..."
        self.assertTrue(expected in resp)
        expected = "tal error: Name lookup failed for testnode2"
        self.assertTrue(expected in error, error)

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


class TestCookbook(BaseTest):
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
        print resp


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

    def test_list_nodes_with_role(self):
        """Should list all nodes with a recipe in the run list"""
        for r in ['top_level_role', 'sub_role', 'sub_sub_role', 'base']:
            resp, error = self.execute([fix, 'list_nodes_with_role:%s' % r])
            self.assertTrue('nestedroles1' in resp, r+": "+resp)
            self.assertTrue(r in resp, r+": "+resp)


if __name__ == "__main__":
    unittest.main()
