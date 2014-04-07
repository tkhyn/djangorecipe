from random import choice
import os
import logging
import re
import sys
import shutil
from datetime import date
from distutils.version import StrictVersion

from zc.buildout import UserError
import zc.recipe.egg

from djangorecipe.templating import process, process_tree, script_template


class Recipe(object):
    def __init__(self, buildout, name, options):
        # The use of version is deprecated.
        if 'version' in options:
            raise UserError('The version option is deprecated. '
                            'Read about the change on '
                            'http://pypi.python.org/pypi/djangorecipe/0.99')
        self.log = logging.getLogger(name)
        self.egg = zc.recipe.egg.Egg(buildout, options['recipe'], options)

        self.buildout, self.name, self.options = buildout, name, options
        options['location'] = os.path.join(
            buildout['buildout']['parts-directory'], name)
        options['bin-directory'] = buildout['buildout']['bin-directory']

        options.setdefault('project', 'project')
        options.setdefault('settings', 'development')

        # gets the root package path
        self.get_root_pkg()

        options.setdefault('urlconf', self.root_pkg + 'urls')
        options.setdefault(
            'media_root',
            "os.path.join(os.path.dirname(__file__), 'media')")
        # Set this so the rest of the recipe can expect the values to be
        # there. We need to make sure that both pythonpath and extra-paths are
        # set for BBB.
        if 'extra-paths' in options:
            options['pythonpath'] = options['extra-paths']
        else:
            options.setdefault('extra-paths', options.get('pythonpath', ''))

        options.setdefault('initialization', '')

        # mod_wsgi support script
        options.setdefault('wsgi', 'false')
        options.setdefault('wsgilog', '')
        options.setdefault('logfile', '')

    def install(self):
        base_dir = self.buildout['buildout']['directory']

        if self.root_pkg:
            project_dir = os.path.join(base_dir, self.options['project'])
        else:
            project_dir = base_dir

        extra_paths = self.get_extra_paths()
        requirements, ws = self.egg.working_set(['djangorecipe'])

        script_paths = []
        # Create the Django management script
        script_paths.extend(self.create_manage_script(extra_paths, ws))

        # Create the test runner
        script_paths.extend(self.create_test_runner(extra_paths, ws))

        # Make the wsgi and fastcgi scripts if enabled
        script_paths.extend(self.make_scripts(extra_paths, ws))

        # Create default project files if we haven't got a project
        # egg specified, and if the settings don't already exist
        if not self.options.get('projectegg'):
            settings_path = \
                os.path.join(project_dir, *self.options['settings'].split('.'))
            if not (os.path.exists(settings_path + '.py')):
                self.create_project(project_dir)
            else:
                self.log.debug(
                    'Skipping creating project files for %(project)s since '
                    'its main settings module exists' % self.options)

        return script_paths

    def create_manage_script(self, extra_paths, ws):
        return zc.buildout.easy_install.scripts(
            [(self.options.get('control-script', self.name),
              'djangorecipe.manage', 'main')],
            ws, sys.executable, self.options['bin-directory'],
            extra_paths=extra_paths,
            arguments="'%s%s'" % (self.root_pkg, self.options['settings']),
            initialization=self.options['initialization'])

    def create_test_runner(self, extra_paths, working_set):
        apps = self.options.get('test', '').split()
        # Only create the testrunner if the user requests it
        if apps:
            return zc.buildout.easy_install.scripts(
                [(self.options.get('testrunner', 'test'),
                  'djangorecipe.test', 'main')],
                working_set, sys.executable,
                self.options['bin-directory'],
                extra_paths=extra_paths,
                arguments="'%s%s', %s" % (
                    self.root_pkg,
                    self.options['settings'],
                    ', '.join(["'%s'" % app for app in apps])),
                initialization=self.options['initialization'])
        else:
            return []

    def create_project(self, project_dir):
        # create the project directory if it does not exist
        if not os.path.exists(project_dir):
            os.makedirs(project_dir)

        # retrieve user-provided template directories
        template_dirs = self.buildout['djangorecipe'] \
                            .get('template-dirs', '') \
                            .splitlines()

        # retrieve template name
        template_name = self.options.get('template', None)

        if template_name and template_dirs:
            # the user provided a template to load

            # look for a template in the template directories provided
            # in reverse so that the last setting is prioritary
            for d in reversed(template_dirs):
                d = os.path.abspath(d)
                if template_name in os.listdir(d):
                    # we have a template candidate, load it
                    temp_path = os.path.join(d, template_name)
                    break

        else:
            # no template name was provided
            temp_path = os.path.join(os.path.dirname(__file__),
                                     'templates')

            # Find the current Django versions in the buildout versions.
            version = None
            b_versions = self.buildout.get('versions')
            if b_versions:
                django_version = (
                    b_versions.get('django') or
                    b_versions.get('Django')
                )
                if django_version:
                    version_re = re.compile("\d+\.\d+")
                    match = version_re.match(django_version)
                    version = match and match.group()

                if version not in os.listdir(temp_path):
                    # the version is invalid (no template)
                    version = None

            # if the version could not be found, gets the latest one from the
            # default templates names
            if not version:
                av_versions = os.listdir(temp_path)
                av_versions.sort(key=StrictVersion)
                version = av_versions[-1]

            temp_path = os.path.join(temp_path, version)

        # prepare templating engine
        template_vars = self.get_template_vars()

        # copy files and run templating engine
        for sub in os.listdir(temp_path):
            src_path = os.path.join(temp_path, sub)
            tgt_path = os.path.join(project_dir, sub)
            if os.path.exists(tgt_path):
                sys.stderr.write('ERROR: %s already exists in %s and ' \
                    'cannot be overwritten by djangorecipe\'s template ' \
                    'engine.\n' % (sub, project_dir))
            else:
                if os.path.isdir(src_path):
                    # copy the subdirectory tree
                    shutil.copytree(src_path, tgt_path)
                    process_tree(tgt_path, template_vars)
                else:
                    # copy the file and run templating engine
                    shutil.copy(src_path, tgt_path)
                    process(tgt_path, template_vars)

    def make_scripts(self, extra_paths, ws):
        scripts = []
        protocol = 'wsgi'

        if self.options.get(protocol, '').lower() == 'true':
            _script_template = zc.buildout.easy_install.script_template
            protocol = 'wsgi'
            zc.buildout.easy_install.script_template = \
                zc.buildout.easy_install.script_header + \
                script_template[protocol]

            scripts.extend(
                zc.buildout.easy_install.scripts(
                    [(self.options.get('wsgi-script') or
                      '%s.%s' % (self.options.get('control-script',
                                                  self.name),
                                 protocol),
                      'djangorecipe.%s' % protocol, 'main')],
                    ws,
                    sys.executable,
                    self.options['bin-directory'],
                    extra_paths=extra_paths,
                    arguments="'%s%s', logfile='%s'" % (
                        self.root_pkg, self.options['settings'],
                        self.options.get('logfile')),
                    initialization=self.options['initialization']))
            zc.buildout.easy_install.script_template = _script_template

        return scripts

    def get_template_vars(self):
        today = date.today()
        t_vars = {
            'secret': self.generate_secret(),
            'project_name': self.project_name,
            'root_pkg': self.root_pkg,
            'year': today.year,
            'month': today.month,
            'day': today.day
        }
        t_vars.update(self.options)
        t_vars.update(self.buildout.get('djangorecipe', {}))
        return t_vars

    def get_root_pkg(self):
        project = self.options.get('projectegg', self.options['project'])
        if project == '.':
            self.root_pkg = ''
            self.project_name = os.path.basename(
                os.path.dirname(self.buildout['buildout']['directory'])
            )
        else:
            self.root_pkg = project + '.'
            self.project_name = project

    def get_extra_paths(self):
        extra_paths = [self.buildout['buildout']['directory']]

        # Add libraries found by a site .pth files to our extra-paths.
        if 'pth-files' in self.options:
            import site
            for pth_file in self.options['pth-files'].splitlines():
                pth_libs = site.addsitedir(pth_file, set())
                if not pth_libs:
                    self.log.warning(
                        "No site *.pth libraries found for pth_file=%s" % (
                            pth_file,))
                else:
                    self.log.info("Adding *.pth libraries=%s" % pth_libs)
                    self.options['extra-paths'] += '\n' + '\n'.join(pth_libs)

        pythonpath = [p.replace('/', os.path.sep) for p in
                      self.options['extra-paths'].splitlines() if p.strip()]

        extra_paths.extend(pythonpath)
        return extra_paths

    def update(self):
        extra_paths = self.get_extra_paths()
        requirements, ws = self.egg.working_set(['djangorecipe'])
        # Create the Django management script
        self.create_manage_script(extra_paths, ws)

        # Create the test runner
        self.create_test_runner(extra_paths, ws)

        # Make the wsgi and fastcgi scripts if enabled
        self.make_scripts(extra_paths, ws)

    def generate_secret(self):
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
        return ''.join([choice(chars) for i in range(50)])
