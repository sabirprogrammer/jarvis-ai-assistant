Welcome to Jarvis AI Assistant's documentation!
============================================

.. image:: _static/logo.png
   :align: center
   :alt: Jarvis AI Assistant Logo

Jarvis AI Assistant is a modern, extensible AI assistant with voice recognition, natural language processing, and system automation capabilities.

Features
--------

* 🎙️ **Voice Interaction**: Natural voice commands and responses
* 🧠 **AI-Powered**: Intelligent responses using OpenAI's GPT models
* 🔌 **Plugin System**: Extensible architecture for new features
* 📅 **Google Integration**: Calendar, Gmail, and YouTube integration
* ⛅ **Weather Updates**: Real-time weather information
* 📰 **News Feed**: Latest news from various sources
* 💻 **System Monitoring**: CPU, memory, and resource tracking
* 🎨 **Modern UI**: Clean, responsive interface with PyQt6

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   configuration
   plugins
   services
   ui
   api
   development
   contributing
   changelog

Getting Started
-------------

Installation
~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/yourusername/jarvis-assistant.git
   cd jarvis-assistant
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt

Quick Start
~~~~~~~~~~

1. Configure your API keys in ``config/config.yaml``
2. Run the assistant:

   .. code-block:: bash

      python main.py

3. Start interacting with voice commands or text input!

Architecture Overview
------------------

.. graphviz::

   digraph architecture {
      rankdir=TB;
      node [shape=box, style=rounded, fontname="Arial"];
      
      user [label="User Interface\n(PyQt6)"];
      assistant [label="Assistant Core"];
      plugins [label="Plugin System"];
      services [label="Services"];
      db [label="Database"];
      
      user -> assistant [label="Commands"];
      assistant -> user [label="Responses"];
      assistant -> plugins [label="Plugin Management"];
      assistant -> services [label="Service Requests"];
      plugins -> services [label="Service Usage"];
      services -> db [label="Data Storage"];
      
      subgraph cluster_services {
         label = "Available Services";
         style = dashed;
         weather [label="Weather Service"];
         news [label="News Service"];
         openai [label="OpenAI Service"];
         google [label="Google Service"];
         speech [label="Speech Service"];
         system [label="System Monitor"];
      }
      
      services -> {weather news openai google speech system};
   }

Components
---------

Core
~~~~

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :recursive:

   core.assistant
   core.command_parser

Services
~~~~~~~~

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :recursive:

   services.weather_service
   services.news_service
   services.openai_service
   services.google_service
   services.speech
   services.system_monitor

UI Components
~~~~~~~~~~~

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :recursive:

   ui.main_window
   ui.settings_dialog
   ui.plugin_manager_dialog

Plugin System
~~~~~~~~~~~

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :recursive:

   plugins.base_plugin
   plugins.example_plugin

Utilities
~~~~~~~~

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :recursive:

   utils.logger
   utils.db_manager

Development
---------

Contributing
~~~~~~~~~~

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create a feature branch
3. Write your changes
4. Write tests for your changes
5. Run the tests
6. Submit a pull request

For more details, see :doc:`contributing`.

Testing
~~~~~~~

Run the test suite:

.. code-block:: bash

   pytest tests/

Generate test coverage report:

.. code-block:: bash

   pytest --cov=. tests/

Code Style
~~~~~~~~~

We use:

- Black for code formatting
- Flake8 for linting
- MyPy for type checking
- Pre-commit hooks for validation

Docker Support
~~~~~~~~~~~~

Build and run with Docker:

.. code-block:: bash

   docker-compose up --build

API Reference
-----------

For detailed API documentation, see :doc:`api`.

Changelog
--------

See :doc:`changelog` for a list of changes in each release.

Indices and tables
----------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

License
------

This project is licensed under the MIT License - see the :doc:`license` file for details.
