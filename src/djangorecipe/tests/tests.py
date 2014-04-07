import os
import shutil
import sys
import tempfile
import unittest
from distutils.version import StrictVersion

import mock

from djangorecipe.recipe import Recipe

is_win32 = sys.platform == 'win32'


def script_path(dir, *names):
    """Gets the path to a script, adding the -script.py suffix if necessary"""
    path = os.path.join(dir, *names)
    if is_win32 and not os.path.exists(path):
        path_win = path + '-script.py'
        if os.path.exists(path_win):
            path = path_win
    return path


def script_cat(dir, *names):
    """Reads a script file, adding the -script.py suffix if necessary"""
    path = script_path(dir, *names)
    return open(path).read()


class BaseTestRecipe(unittest.TestCase):

    def setUp(self):
        # Create a directory for our buildout files created by the recipe
        self.buildout_dir = tempfile.mkdtemp('djangorecipe')

        self.bin_dir = os.path.join(self.buildout_dir, 'bin')
        self.develop_eggs_dir = os.path.join(self.buildout_dir,
                                             'develop-eggs')
        self.eggs_dir = os.path.join(self.buildout_dir, 'eggs')
        self.parts_dir = os.path.join(self.buildout_dir, 'parts')

        # We need to create the bin dir since the recipe should be able to
        # expect it exists
        os.mkdir(self.bin_dir)

        self.recipe_initialisation = [
            {'buildout': {
                'eggs-directory': self.eggs_dir,
                'develop-eggs-directory': self.develop_eggs_dir,
                'bin-directory': self.bin_dir,
                'parts-directory': self.parts_dir,
                'directory': self.buildout_dir,
                'python': 'buildout',
                'executable': sys.executable,
                'find-links': '',
                'allow-hosts': ''},
             },
            'django',
            {'recipe': 'djangorecipe'}]

        self.recipe = Recipe(*self.recipe_initialisation)

    def tearDown(self):
        # Remove our test dir
        shutil.rmtree(self.buildout_dir)


class TestRecipe(BaseTestRecipe):

    def test_consistent_options(self):
        # Buildout is pretty clever in detecting changing options. If
        # the recipe modifies it's options during initialisation it
        # will store this to determine wheter it needs to update or do
        # a uninstall & install. We need to make sure that we normally
        # do not trigger this. That means running the recipe with the
        # same options should give us the same results.
        self.assertEqual(Recipe(*self.recipe_initialisation).options,
                         Recipe(*self.recipe_initialisation).options)


    def test_generate_secret(self):
        # To create a basic skeleton the recipe also generates a
        # random secret for the settings file. Since it should very
        # unlikely that it will generate the same key a few times in a
        # row we will test it with letting it generate a few keys.
        secrets = []
        for i in range(10):
            s = self.recipe.generate_secret()
            for sp in secrets:
                self.assertNotEqual(sp, s)
            secrets.append(s)

    def test_version_option_deprecation(self):
        from zc.buildout import UserError
        options = {'recipe': 'djangorecipe',
                   'version': 'trunk',
                   'wsgi': 'true'}
        self.assertRaises(UserError, Recipe, *('buildout', 'test', options))

    @mock.patch('zc.recipe.egg.egg.Scripts.working_set',
                return_value=(None, []))
    @mock.patch('djangorecipe.recipe.Recipe.create_manage_script')
    def test_extra_paths(self, manage, working_set):

        # The recipe allows extra-paths to be specified. It uses these to
        # extend the Python path within it's generated scripts.
        self.recipe.options['version'] = '1.0'
        self.recipe.options['extra-paths'] = 'somepackage\nanotherpackage'

        self.recipe.install()
        self.assertEqual(manage.call_args[0][0][-2:],
                         ['somepackage', 'anotherpackage'])

    @mock.patch('zc.recipe.egg.egg.Scripts.working_set',
                return_value=(None, []))
    @mock.patch('site.addsitedir', return_value=['extra', 'dirs'])
    def test_pth_files(self, addsitedir, working_set):

        # When a pth-files option is set the recipe will use that to add more
        # paths to extra-paths.
        self.recipe.options['version'] = '1.0'

        # The mock values needed to demonstrate the pth-files option.
        self.recipe.options['pth-files'] = 'somedir'
        self.recipe.install()

        self.assertEqual(addsitedir.call_args, (('somedir', set([])), {}))
        # The extra-paths option has been extended.
        self.assertEqual(self.recipe.options['extra-paths'], '\nextra\ndirs')

    def test_settings_option(self):
        # The settings option can be used to specify the settings file
        # for Django to use. By default it uses `development`.
        self.assertEqual(self.recipe.options['settings'], 'development')
        # When we change it an generate a manage script it will use
        # this var.
        self.recipe.options['settings'] = 'spameggs'
        self.recipe.create_manage_script([], [])
        manage = os.path.join(self.bin_dir, 'django')
        self.assertTrue("djangorecipe.manage.main('project.spameggs')"
                        in script_cat(manage))

    def test_create_project(self):
        # If a project does not exist already the recipe will create
        # one.
        project_dir = os.path.join(self.buildout_dir, 'project')
        self.recipe.create_project(project_dir)

        # This should have created a project directory
        self.assertTrue(os.path.exists(project_dir))

        # In this directory, we should find the same files as in the latest
        # version default template directory
        temp_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        av_versions = os.listdir(temp_path)
        av_versions.sort(key=StrictVersion)
        version = av_versions[-1]
        temp_path = os.path.join(temp_path, version)

        self.assertTrue(set(os.listdir(temp_path)). \
            issubset(os.listdir(project_dir)))


    @mock.patch('zc.recipe.egg.egg.Scripts.working_set',
                return_value=(None, []))
    def test_project_at_root(self, working_set):
        # If project = ., the project is created at the root
        self.recipe.options['project'] = '.'
        self.recipe.get_root_pkg()
        self.recipe.options['settings'] = 'spameggs'

        self.recipe.install()

        # Check that the files have been created
        temp_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
        av_versions = os.listdir(temp_path)
        av_versions.sort(key=StrictVersion)
        version = av_versions[-1]
        temp_path = os.path.join(temp_path, version)
        self.assertTrue(set(os.listdir(temp_path)). \
            issubset(os.listdir(self.buildout_dir)))

        # check that the management script refers to the settings module
        # specified in recipe.options, unchanged (no parent package)
        self.assertTrue("djangorecipe.manage.main('spameggs')"
                        in script_cat(self.bin_dir, 'django'))


class TestRecipeScripts(BaseTestRecipe):

    def test_make_protocol_script_wsgi(self):
        # To ease deployment a WSGI script can be generated. The
        # script adds any paths from the `extra_paths` option to the
        # Python path.
        self.recipe.options['wsgi'] = 'true'
        self.recipe.make_scripts([], [])
        # This should have created a script in the bin dir

        wsgi_script = script_path(self.bin_dir, 'django.wsgi')
        self.assertTrue(os.path.exists(wsgi_script))

    def test_contents_protocol_script_wsgi(self):
        self.recipe.options['wsgi'] = 'true'
        self.recipe.make_scripts([], [])

        # The contents should list our paths
        contents = script_cat(self.bin_dir, 'django.wsgi')
        # It should also have a reference to our settings module
        self.assertTrue('project.development' in contents)
        # and a line which set's up the WSGI app
        self.assertTrue("application = "
                        "djangorecipe.wsgi.main('project.development', "
                        "logfile='')"
                        in contents)
        self.assertTrue("class logger(object)" not in contents)

    def test_contents_protocol_script_wsgi_with_initialization(self):
        self.recipe.options['wsgi'] = 'true'
        self.recipe.options['initialization'] = 'import os\nassert True'
        self.recipe.make_scripts([], [])
        self.assertTrue('import os\nassert True\n\nimport djangorecipe'
                        in script_cat(self.bin_dir, 'django.wsgi'))

    def test_contents_log_protocol_script_wsgi(self):
        self.recipe.options['wsgi'] = 'true'
        self.recipe.options['logfile'] = '/foo'
        self.recipe.make_scripts([], [])

        contents = script_cat(self.bin_dir, 'django.wsgi')

        self.assertTrue("logfile='/foo'" in contents)

    def test_make_protocol_named_script_wsgi(self):
        # A wsgi-script name option is specified
        self.recipe.options['wsgi'] = 'true'
        self.recipe.options['wsgi-script'] = 'foo-wsgi.py'
        self.recipe.make_scripts([], [])
        wsgi_script = script_path(self.bin_dir, 'foo-wsgi.py')
        self.assertTrue(os.path.exists(wsgi_script))

    @mock.patch('zc.buildout.easy_install.scripts',
                return_value=['some-path'])
    def test_make_protocol_scripts_return_value(self, scripts):
        # The return value of make scripts lists the generated scripts.
        self.recipe.options['wsgi'] = 'true'
        self.assertEqual(self.recipe.make_scripts([], []),
                         ['some-path'])

    def test_create_manage_script(self):
        # This buildout recipe creates a alternative for the standard
        # manage.py script. It has all the same functionality as the
        # original one but it sits in the bin dir instead of within
        # the project.
        self.recipe.create_manage_script([], [])
        self.assertTrue(os.path.exists(script_path(self.bin_dir, 'django')))

    def test_create_manage_script_projectegg(self):
        # When a projectegg is specified, then the egg specified
        # should get used as the project file.
        self.recipe.options['projectegg'] = 'spameggs'
        self.recipe.get_root_pkg()
        self.recipe.create_manage_script([], [])
        manage = script_path(self.bin_dir, 'django')
        self.assertTrue(os.path.exists(manage))
        # Check that we have 'spameggs' as the project
        self.assertTrue("djangorecipe.manage.main('spameggs.development')"
                        in script_cat(manage))

    def test_create_manage_script_with_initialization(self):
        self.recipe.options['initialization'] = 'import os\nassert True'
        self.recipe.create_manage_script([], [])
        self.assertTrue('import os\nassert True\n\nimport djangorecipe'
                        in script_cat(self.bin_dir, 'django'))

    def test_create_wsgi_script_projectegg(self):
        # When a projectegg is specified, then the egg specified
        # should get used as the project in the wsgi script.
        recipe_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..'))
        self.recipe.options['projectegg'] = 'spameggs'
        self.recipe.options['wsgi'] = 'true'
        self.recipe.get_root_pkg()
        self.recipe.make_scripts([recipe_dir], [])

        wsgi_script = script_path(self.bin_dir, 'django.wsgi')
        self.assertTrue(os.path.exists(wsgi_script))
        # Check that we have 'spameggs' as the project
        self.assertTrue('spameggs.development' in
                        script_cat(wsgi_script))


class TestTesTRunner(BaseTestRecipe):

    def test_create_test_runner(self):
        # An executable script can be generated which will make it
        # possible to execute the Django test runner. This options
        # only works if we specify one or apps to test.

        # This first argument sets extra_paths, we will use this to
        # make sure the script can find this recipe
        recipe_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..'))

        # When we specify an app to test it should create the the
        # testrunner
        self.recipe.options['test'] = 'knight'
        self.recipe.create_test_runner([recipe_dir], [])
        self.assertTrue(os.path.exists(script_path(self.bin_dir, 'test')))

    def test_not_create_test_runner(self):
        recipe_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..'))
        self.recipe.create_test_runner([recipe_dir], [])

        testrunner = os.path.join(self.bin_dir, 'test')

        # Show it does not create a test runner by default
        self.assertFalse(os.path.exists(testrunner))

    def test_create_test_runner_with_initialization(self):
        recipe_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..'))

        # When we specify an app to test it should create the the
        # testrunner
        self.recipe.options['test'] = 'knight'
        self.recipe.options['initialization'] = 'import os\nassert True'
        self.recipe.create_test_runner([recipe_dir], [])
        self.assertTrue('import os\nassert True\n\nimport djangorecipe'
                        in script_cat(self.bin_dir, 'test'))

