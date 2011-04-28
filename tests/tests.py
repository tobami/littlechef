import unittest
import subprocess
import os


class BaseTest(unittest.TestCase):
    def execute(self, call):
        """Executes a command and returns stdout and stderr"""
        proc = subprocess.Popen(call,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.communicate()


class ConfigTest(BaseTest):
    def test_not_a_kitchen(self):
        """Should exit with error when not a kitchen directory"""
        cwd = os.getcwd()
        # Change to parent dir, which has no nodes/cookbooks/roles dir
        os.chdir("/".join(cwd.split('/')[:-1]))
        resp, error = self.execute(['./cook', '-l'])
        self.assertTrue("Fatal error" in error)
        self.assertTrue("outside of a deployment directory" in error)
        self.assertEquals(resp, "")
        # Return to test dir
        os.chdir(cwd)
    
    def test_version(self):
        """Should output the correct Little Chef version"""
        resp, error = self.execute(['../cook', '-v'])
        self.assertEquals(error, "")
        self.assertTrue('LittleChef 0.5.' in resp)
    
    def test_list_commands(self):
        """Should output a list of available commands"""
        resp, error = self.execute(['../cook', '-l'])
        self.assertEquals(error, "")
        self.assertTrue('using Chef without a Chef Server' in resp)
        self.assertEquals(len(resp.split('\n')), 19)


class CookbookTest(BaseTest):
    def test_list_recipes(self):
        """Should list available recipes"""
        resp, error = self.execute(['../cook', 'list_recipes'])
        self.assertEquals(error, "")
        self.assertTrue('subversion::client' in resp)
        self.assertTrue('subversion::server' in resp)
    
    def test_list_recipes_site_cookbooks(self):
        """Should give priority to site-cookbooks information"""
        resp, error = self.execute(['../cook', 'list_recipes'])
        self.assertTrue('Modified by site-cookbooks' in resp)
    
    def test_list_recipes_detailed(self):
        """Should show a detailed list of available recipes"""
        resp, error = self.execute(['../cook', 'list_recipes_detailed'])
        self.assertTrue('subversion::client' in resp)
        for field in ['description', 'version', 'dependencies', 'attributes']:
            self.assertTrue(field in resp)
    
    def test_list_recipes_detailed_site_cookbooks(self):
        """Should show a detailed list of available recipes with site-cookbook priority"""
        resp, error = self.execute(['../cook', 'list_recipes_detailed'])
        self.assertTrue('0.8.4' in resp)


if __name__ == "__main__":
    unittest.main()
