Djangorecipe: easy install of Django with buildout
==================================================


Description
-----------

.. image:: https://secure.travis-ci.org/rvanlaar/djangorecipe.png?branch=master
   :target: http://travis-ci.org/rvanlaar/djangorecipe/

This buildout recipe can be used to create a setup for Django. It will
automatically download Django and install it in the buildout's
sandbox.

You can see an example of how to use the recipe below::

  [buildout]
  parts = satchmo django
  eggs =
    ipython
  versions = versions

  [versions]
  Django = 1.5.5

  [satchmo]
  recipe = gocept.download
  url = http://www.satchmoproject.com/snapshots/satchmo-0.6.tar.gz
  md5sum = 659a4845c1c731be5cfe29bfcc5d14b1

  [django]
  recipe = djangorecipe
  settings = development
  eggs = ${buildout:eggs}
  extra-paths =
    ${satchmo:location}
  project = dummyshop


Supported options
-----------------

The recipe supports the following options.

project
  This option sets the name for your project. The recipe will create a
  basic structure if the project settings module does not already exist.
  If this option is set to '.', the project root is understood to be the
  buildout root.

projectegg
  Use this instead of the project option when you want to use an egg
  as the project. This disables the generation of the project
  structure.

settings
  You can set the name of the settings file which is to be used with
  this option. This is useful if you want to have a different
  production setup from your development setup. It defaults to
  `development`.

template
  The name of the template folder that should be used when creating a new
  project. By default, the recipe creates a django project exactly like the
  django-admin.py startproject command, matching the major django version you
  are using. For this option to be taken into account, the
  {buildout:django_template_dirs} must contain at least one entry.

extra-paths
  All paths specified here will be used to extend the default Python
  path for the `bin/*` scripts.

pth-files
  Adds paths found from a site `.pth` file to the extra-paths.
  Useful for things like Pinax which maintains its own external_libs dir.

control-script
  The name of the script created in the bin folder. This script is the
  equivalent of the `manage.py` Django normally creates. By default it
  uses the name of the section (the part between the `[ ]`).

initialization
  Specify some Python initialization code to be inserted into the
  `control-script`. This is very limited. In particular, be aware that
  leading whitespace is stripped from the code given.

wsgi
  An extra script is generated in the bin folder when this is set to
  `true`. This can be used with mod_wsgi to deploy the project. The
  name of the script is `control-script.wsgi`.

wsgi-script
  The name of the wsgi-script that is generated. This can be useful for
  gunicorn.

wsgilog
  In case the WSGI server you're using does not allow printing to stdout,
  you can set this variable to a filesystem path - all stdout/stderr data
  is redirected to the log instead of printed

test
  If you want a script in the bin folder to run all the tests for a
  specific set of apps this is the option you would use. Set this to
  the list of app labels which you want to be tested.

testrunner
  This is the name of the testrunner which will be created. It
  defaults to `test`.

All following options only have effect when the project specified by
the project option has not been created already.

urlconf
  You can set this to a specific url conf. It will use project.urls by
  default.

secret
  The secret to use for the `settings.py`, it generates a random
  string by default.


Dedicated buildout options
--------------------------

The recipe can optionally use an option from the buildout section to get the
directories where template folders lie.

django_template_dirs
   This is a list of directories where project template folders can be found
   The template is defined by the above option 'template'


Another example
---------------

The next example shows you how to use some more of the options::

  [buildout]
  parts = django extras
  eggs =
    hashlib

  [extras]
  recipe = iw.recipe.subversion
  urls =
    http://django-command-extensions.googlecode.com/svn/trunk/ django-command-extensions
    http://django-mptt.googlecode.com/svn/trunk/ django-mptt

  [django]
  recipe = djangorecipe
  settings = development
  project = exampleproject
  wsgi = true
  eggs =
    ${buildout:eggs}
  test =
    someapp
    anotherapp

Example using .pth files
------------------------

Pinax uses a .pth file to add a bunch of libraries to its path; we can
specify it's directory to get the libraries it specified added to our
path::

  [buildout]
  parts	= PIL
	  svncode
	  myproject
  versions=versions

  [versions]
  django	= 1.3

  [PIL]
  recipe	= zc.recipe.egg:custom
  egg		= PIL
  find-links	= http://dist.repoze.org/

  [svncode]
  recipe	= iw.recipe.subversion
  urls		= http://svn.pinaxproject.com/pinax/tags/0.5.1rc1	pinax

  [myproject]
  recipe	= djangorecipe
  eggs		=
    PIL
  project	= myproject
  settings	= settings
  extra-paths	= ${buildout:directory}/myproject/apps
		  ${svncode:location}/pinax/apps/external_apps
		  ${svncode:location}/pinax/apps/local_apps
  pth-files	= ${svncode:location}/pinax/libs/external_libs
  wsgi		= true

Above, we use stock Pinax for pth-files and extra-paths paths for
apps, and our own project for the path that will be found first in the
list.  Note that we expect our project to be checked out (e.g., by
svn:external) directly under this directory in to 'myproject'.


Example with a Django version from a repository
-----------------------------------------------

If you want to use a specific Django version from a source
repository you could use mr.developer: http://pypi.python.org/pypi/mr.developer
Here is an example for using the Django development version::

  [buildout]
  parts = django
  extensions = mr.developer
  auto-checkout = *

  [sources]
  django = git https://github.com/django/django.git

  [django]
  recipe = djangorecipe
  settings = settings
  project = project

Example configuration for mod_wsgi
----------------------------------

If you want to deploy a project using mod_wsgi you could use this
example as a starting point::

  <Directory /path/to/buildout>
         Order deny,allow
         Allow from all
  </Directory>
  <VirtualHost 1.2.3.4:80>
         ServerName      my.rocking.server
         CustomLog       /var/log/apache2/my.rocking.server/access.log combined
         ErrorLog        /var/log/apache2/my.rocking.server/error.log
         WSGIScriptAlias / /path/to/buildout/bin/django.wsgi
  </VirtualHost>

Generating a control script for PyDev
-------------------------------------

Running Django with auto-reload in PyDev requires adding a small snippet
of code::

  import pydevd
  pydevd.patch_django_autoreload(patch_remote_debugger=False, patch_show_console=True)

just before the `if __name__ == "__main__":` in the `manage.py` module
(or in this case the control script that is generated). This example
buildout generates two control scripts: one for command-line usage and
one for PyDev, with the required snippet, using the recipe's
`initialization` option::

  [buildout]
  parts = django pydev
  eggs =
    mock

  [django]
  recipe = djangorecipe
  eggs = ${buildout:eggs}
  project = dummyshop

  [pydev]
  <= django
  initialization =
    import pydevd
    pydevd.patch_django_autoreload(patch_remote_debugger=False, patch_show_console=True)

Several wsgi scripts for one Apache virtual host instance
---------------------------------------------------------

There is a problem when several wsgi scripts are combined in a single virtual
host instance of Apache. This is due to the fact that Django uses the
environment variable DJANGO_SETTINGS_MODULE. This variable  gets set once when
the first wsgi script loads. The rest of the wsgi scripts will fail, because
they need a different settings modules. However the environment variable
DJANGO_SETTINGS_MODULE is only set once. The new `initialization` option that has
been added to djangorecipe can be used to remedy this problem as shown below::

    [django]
    settings = acceptance
    initialization =
        import os
        os.environ['DJANGO_SETTINGS_MODULE'] = '${django:project}.${django:settings}'

Example usage of django-configurations
--------------------------------------

django-configurations (http://django-configurations.readthedocs.org/en/latest/)
is an application that helps you organize your Django settings into classes.
Using it requires modifying the manage.py file.  This is done easily using the
recipe's `initialization` option::

    [buildout]
    parts = django
    eggs =
        hashlib

    [django]
    recipe = djangorecipe
    eggs = ${buildout:eggs}
    project = myproject
    initialization =
        # Patch the manage file for django-configurations
        import os
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
        os.environ.setdefault('DJANGO_CONFIGURATION', 'Development')
        from configurations.management import execute_from_command_line
        import django
        django.core.management.execute_from_command_line = execute_from_command_line


Templating
----------

The template engine is as simple as it can be and relies upon pythons's
string.Template. A variable can be inserted in any file or directory name or
file content using the syntax ${variable}.

The following variables are available:

- all the recipe options from the configuration file
- secret: the secret key for django settings
- project_name: the project name (project or the buildout directory name if
  project == '.')
- root_pkg: the root package (empty string if project == '.')
- year: the current year
- month: the current month
- day: the current day of the month

You may use these variables in any file of the template directory.

For example, for a copyright notice in a module's docstring, you may use::

   (c) ${year} Me

Example:
........

In ~/.buildout/default.cfg::

    [buildout]
    django_template_dirs =
      /my/project/template/directory
      /my/project/template/directory2

In buildout.cfg::

    [buildout]
    parts = django
    # relative to the buildout directory
    django_template_dirs +=
      templates
    eggs =
      egg1
      egg2

    [django]
    recipe = djangorecipe
    eggs = ${buildout:eggs}
    project = myproject
    template = mytemplate

The template directories are explored in this order (reverse of the order in
which they are defined to enable overriding):

1. buildout/directory/templates
2. /my/project/template/directory2
3. /my/project/template/directory

