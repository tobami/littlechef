import unittest
import subprocess
import os
import platform
from os.path import join, sep, normpath, abspath, split


# Set some convenience variables
test_path = split(normpath(abspath(__file__)))[0]
littlechef_top = normpath(join(test_path, '..'))

if platform.system() == 'Windows':
    cook = join(littlechef_top, 'cook.cmd')
    WIN32 = True
else:
    cook = join(littlechef_top,'cook')
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
        # Call cook from the current directory above "tests/"
        resp, error = self.execute([cook, '-l'])
        self.assertTrue("Fatal error" in error)
        self.assertTrue("outside of a kitchen" in error)
        self.assertEquals(resp, "")
        # Return to test dir
        self.set_location()

    def test_version(self):
        """Should output the correct Little Chef version"""
        resp, error = self.execute([cook, '-v'])
        self.assertEquals(error, "")
        self.assertTrue('LittleChef 0.6.' in resp)

    def test_list_commands(self):
        """Should output a list of available commands"""
        resp, error = self.execute([cook, '-l'])
        self.assertEquals(error, "")
        self.assertTrue('using Chef without a Chef Server' in resp)
        self.assertEquals(len(resp.split('\n')), 20)


class TestCookbook(BaseTest):
    def test_list_recipes(self):
        """Should list available recipes"""
        resp, error = self.execute([cook, 'list_recipes'])
        self.assertEquals(error, "")
        self.assertTrue('subversion::client' in resp)
        self.assertTrue('subversion::server' in resp)

    def test_list_recipes_site_cookbooks(self):
        """Should give priority to site-cookbooks information"""
        resp, error = self.execute([cook, 'list_recipes'])
        self.assertTrue('Modified by site-cookbooks' in resp)

    def test_list_recipes_detailed(self):
        """Should show a detailed list of available recipes"""
        resp, error = self.execute([cook, 'list_recipes_detailed'])
        self.assertTrue('subversion::client' in resp)
        for field in ['description', 'version', 'dependencies', 'attributes']:
            self.assertTrue(field in resp)

    def test_list_recipes_detailed_site_cookbooks(self):
        """Should show a detailed list of available recipes with site-cookbook priority"""
        resp, error = self.execute([cook, 'list_recipes_detailed'])
        self.assertTrue('0.8.4' in resp)

    def test_no_metadata(self):
        """Should abort if cookbook has no metadata.json"""
        bad_cookbook = join(test_path, 'cookbooks', 'bad_cookbook')
        os.mkdir(bad_cookbook)
        try:
            resp, error = self.execute([cook, 'list_recipes'])
        except OSError:
            self.fail("Couldn't execute {0}".format(cook))
        finally:
            os.rmdir(bad_cookbook)
        expected = 'Fatal error: Cookbook "bad_cookbook" has no metadata.json'
        self.assertTrue(expected in error)


class TestRole(BaseTest):
    def test_list_roles(self):
        """Should list all roles"""
        resp, error = self.execute([cook, 'list_roles'])
        self.assertTrue('base' in resp and 'example aplication' in resp)


class TestNode(BaseTest):
    def test_list_nodes(self):
        """Should list all nodes"""
        resp, error = self.execute([cook, 'list_nodes'])
        self.assertTrue('testnode' in resp)
        self.assertTrue('Recipes: subversion' in resp)

    def test_list_nodes_detailed(self):
        """Should show a detailed list of all nodes"""
        resp, error = self.execute([cook, 'list_nodes_detailed'])
        self.assertTrue('testnode' in resp)
        self.assertTrue('Recipe: subversion' in resp)

    def test_list_nodes_with_recipe(self):
        """Should list all nodes with a recipe in the run list"""
        resp, error = self.execute([cook, 'list_nodes_with_recipe:subversion'])
        self.assertTrue('testnode' in resp)
        self.assertTrue('Recipes: subversion' in resp)

        resp, error = self.execute([cook, 'list_nodes_with_recipe:apache2'])
        self.assertFalse('testnode' in resp)


if __name__ == "__main__":
    unittest.main()
