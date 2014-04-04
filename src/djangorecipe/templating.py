"""
Carry out template-based replacements in project files
"""

import os, sys
from string import Template

script_template = {
    'wsgi': """

%(relative_paths_setup)s
import sys
sys.path[0:0] = [
  %(path)s,
  ]
%(initialization)s
import %(module_name)s

application = %(module_name)s.%(attrs)s(%(arguments)s)
""",
}

def replace_name(path, mapping):
    """
    Handles replacement strings in the file or directory name
    """

    # look for replacement strings in filename
    f_split = list(os.path.split(path))
    name = f_split[1]
    if '${' in name:
        new_name = Template(name).substitute(mapping)
        new_path = os.path.join(f_split[0], new_name)
        os.rename(path, new_path)
    else:
        new_path = path

    return new_path


def replace_ctnt(f, mapping):
    """
    Handles replacement strings in the file content
    """
    if not os.path.isfile(f):
        return
    try:
        # look for replacement strings in file
        t_file = open(f, 'r+')
        t = Template(t_file.read())
        t_file.seek(0)
        t_file.write(t.substitute(mapping))
        t_file.truncate()
        t_file.close()
    except Exception as e:
        sys.stderr.write("""

ERROR: while running template engine on file %s

""" % f)
        raise e


def process(path, mapping):
    """
    Performs all templating operations on the given path
    """
    replace_ctnt(replace_name(path, mapping), mapping)


def process_tree(directory, mapping):
    """
    Performs all templating operations on the directory and its children
    """
    for dirpath, dirnames, filenames in os.walk(directory):
        for f in filenames:
            process(os.path.join(dirpath, f), mapping)
        for d in dirnames:
            replace_name(os.path.join(dirpath, d), mapping)
