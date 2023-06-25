import os
import re
import sys


aiotus_path = os.path.join(os.path.dirname(__file__), '../..')
aiotus_path = os.path.abspath(aiotus_path)
sys.path.insert(0, aiotus_path)


def get_version():
    """Return package version from the bumpversion configuration file (hacky)."""

    try:
        filename = os.path.join(os.path.dirname(__file__), '../../.bumpversion.cfg')
        with open(filename, 'r') as fd:
            setup_py = fd.read()

        m = re.search(r'current_version\s*=\s*(\d+\.\d+\.\d+)', setup_py)
        return m.group(1)
    except:
        sys.exit('Unable to get package version from configuration file.')


project = 'aiotus'
copyright = '2020, Jens Steinhauser'
author = 'Jens Steinhauser'
release = get_version()

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'aiohttp': ('https://aiohttp.readthedocs.io/en/stable/', None),
    'yarl': ('https://yarl.readthedocs.io/en/stable/', None),
}

exclude_patterns = []
html_static_path = ['_static']
html_theme = 'alabaster'
html_theme_options = {
    'description': 'Asynchronous client-side implementation of the tus protocol for Python.',
    'sidebar_collapse': False,
    'page_width': '80%',
    'body_max_width': '80%',
}
templates_path = ['_templates']
