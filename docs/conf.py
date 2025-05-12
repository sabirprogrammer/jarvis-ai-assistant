"""
Sphinx configuration file for Jarvis AI Assistant documentation.
"""
import os
import sys
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, os.path.abspath('..'))

# Project information
project = 'Jarvis AI Assistant'
copyright = f'{datetime.now().year}, Jarvis Team'
author = 'Jarvis Team'
version = '1.0.0'
release = '1.0.0'

# General configuration
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx_rtd_theme',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.graphviz',
    'sphinx.ext.inheritance_diagram',
]

# Add any paths that contain templates
templates_path = ['_templates']

# Source file parsers
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# The master toctree document
master_doc = 'index'

# List of patterns to ignore when looking for source files
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'venv']

# The name of the Pygments (syntax highlighting) style to use
pygments_style = 'sphinx'

# HTML output options
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_logo = '_static/logo.png'
html_favicon = '_static/favicon.ico'

html_theme_options = {
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': True,
    'style_nav_header_background': '#2980B9',
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}

# Custom sidebar templates
html_sidebars = {
    '**': [
        'relations.html',
        'searchbox.html',
        'navigation.html',
    ]
}

# LaTeX output options
latex_elements = {
    'papersize': 'letterpaper',
    'pointsize': '10pt',
    'figure_align': 'htbp',
    'preamble': '',
}

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'PyQt6': ('https://www.riverbankcomputing.com/static/Docs/PyQt6/', None),
}

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_type_aliases = None

# AutoDoc settings
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
}

# Todo settings
todo_include_todos = True
todo_emit_warnings = True

# Coverage settings
coverage_show_missing_items = True

# GraphViz settings
graphviz_output_format = 'svg'
