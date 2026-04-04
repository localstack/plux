Command Line Interface (CLI)
=========================

Plux provides a command-line interface (CLI) that makes it easy to work with plugins from the terminal. This guide explains how to use the plux CLI for discovering plugins, generating entry points, and more.

Overview
-------

The plux CLI is accessible through the ``python -m plux`` command. It provides several subcommands:

* ``entrypoints``: Discover plugins and generate entry points
* ``discover``: Discover plugins and output them in various formats
* ``show``: Show the generated entry points
* ``resolve``: Resolve plugins in a specific namespace

Common Options
-----------

All plux commands support these common options:

.. code-block:: bash

    # Specify a working directory (defaults to current directory)
    python -m plux --workdir /path/to/project <command>
    
    # Enable verbose logging
    python -m plux -v <command>
    python -m plux --verbose <command>

Generating Entry Points
--------------------

The ``entrypoints`` command discovers plugins in your project and generates entry points:

.. code-block:: bash

    # Generate entry points based on your pyproject.toml configuration
    python -m plux entrypoints
    
    # Exclude specific packages
    python -m plux entrypoints --exclude "tests*,docs*"
    
    # Include only specific packages
    python -m plux entrypoints --include "myapp/plugins*"

This command respects your ``pyproject.toml`` configuration, including the build mode:

* In **build-hooks mode** (default), it runs the setuptools build process to generate entry points
* In **manual mode**, it creates a ``plux.ini`` file in your working directory

Discovering Plugins
----------------

The ``discover`` command finds plugins and outputs them without modifying your project:

.. code-block:: bash

    # Discover plugins and output in JSON format (default)
    python -m plux discover
    
    # Output in INI format
    python -m plux discover --format ini
    
    # Save to a file instead of stdout
    python -m plux discover --format json --output plugins.json
    
    # Discover plugins in a specific path
    python -m plux discover --path src/myapp
    
    # Filter packages
    python -m plux discover --exclude "tests*" --include "myapp/plugins*"

This is useful for:

* Debugging plugin discovery issues
* Generating custom entry point files
* Checking which plugins would be discovered without modifying your project

Showing Entry Points
-----------------

The ``show`` command displays the generated entry points:

.. code-block:: bash

    # Show the generated entry points
    python -m plux show

This command looks for the entry points file in your project's metadata directory (e.g., ``.egg-info/entry_points.txt``) and displays its contents.

Resolving Plugins
--------------

The ``resolve`` command finds plugins in a specific namespace at runtime:

.. code-block:: bash

    # Resolve plugins in a namespace
    python -m plux resolve --namespace my.plugins.services

This command:

1. Creates a ``PluginManager`` for the specified namespace
2. Lists all plugin specifications found in that namespace
3. Displays the module and name of each plugin's factory

This is useful for debugging runtime plugin discovery issues.

Examples
-------

Here are some common use cases for the plux CLI:

Initial Project Setup
~~~~~~~~~~~~~~~~~~

When setting up a new project with plux:

.. code-block:: bash

    # Add plux to your project
    pip install plux
    
    # Generate entry points
    python -m plux entrypoints
    
    # Check that plugins were discovered
    python -m plux show

Debugging Plugin Discovery
~~~~~~~~~~~~~~~~~~~~~~~

If you're having trouble with plugin discovery:

.. code-block:: bash

    # Enable verbose logging
    python -m plux -v entrypoints
    
    # Check which plugins would be discovered
    python -m plux discover
    
    # Check if plugins are resolved at runtime
    python -m plux resolve --namespace my.plugins

Customizing Entry Point Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For more control over entry point generation:

.. code-block:: bash

    # Discover plugins with custom filters
    python -m plux discover --include "myapp/plugins*" --exclude "myapp/plugins/experimental*" --format ini --output custom_plugins.ini
    
    # Use the custom file in your pyproject.toml
    # [tool.setuptools.dynamic]
    # entry-points = {file = ["custom_plugins.ini"]}

Continuous Integration
~~~~~~~~~~~~~~~~~~~

In CI environments:

.. code-block:: bash

    # Generate entry points in manual mode
    python -m plux entrypoints
    
    # Build your project
    python -m build

CLI Reference
-----------

Here's a complete reference of all CLI commands and options:

entrypoints
~~~~~~~~~~

.. code-block:: bash

    python -m plux entrypoints [options]
    
    Options:
      -e, --exclude EXCLUDE  Comma-separated list of paths to exclude
      -i, --include INCLUDE  Comma-separated list of paths to include

discover
~~~~~~~

.. code-block:: bash

    python -m plux discover [options]
    
    Options:
      -p, --path PATH        The file path where to look for plugins
      -e, --exclude EXCLUDE  Comma-separated list of paths to exclude
      -i, --include INCLUDE  Comma-separated list of paths to include
      -f, --format FORMAT    Output format: 'json' or 'ini' (default: 'json')
      -o, --output OUTPUT    Output file path (default: stdout)

show
~~~~

.. code-block:: bash

    python -m plux show

resolve
~~~~~~

.. code-block:: bash

    python -m plux resolve [options]
    
    Options:
      --namespace NAMESPACE  The plugin namespace (required)

Best Practices
-----------

Here are some best practices for using the plux CLI:

1. **Use version control**: Run ``python -m plux entrypoints`` before committing changes to ensure entry points are up to date.

2. **Automate in CI/CD**: Include entry point generation in your CI/CD pipeline to catch plugin discovery issues early.

3. **Be specific with include/exclude**: Use specific patterns to avoid scanning unnecessary code.

4. **Check your configuration**: Use ``python -m plux discover`` to verify that your include/exclude patterns work as expected.

5. **Use verbose mode for debugging**: The ``-v`` flag provides detailed information about what plux is doing.

Summary
------

The plux CLI provides powerful tools for working with plugins from the command line. Whether you're setting up a new project, debugging plugin discovery issues, or customizing entry point generation, the CLI offers the flexibility you need.

For most projects, the ``entrypoints`` command with your ``pyproject.toml`` configuration will be sufficient. For more complex scenarios, the ``discover`` and ``resolve`` commands provide additional control and debugging capabilities.