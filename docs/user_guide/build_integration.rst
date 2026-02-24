Build System Integration
=====================

Plux integrates with your build system to discover plugins at build time and generate entry points. This guide explains how to integrate plux with your build system, focusing on setuptools which is currently the primary supported build backend.

Understanding Build Modes
----------------------

Plux supports two modes for building entry points:

1. **Build-hooks mode** (default): Plux automatically hooks into the build process to generate entry points
2. **Manual mode**: You manually control when and how entry points are generated

Configuring Plux in pyproject.toml
-------------------------------

You can configure plux in the ``[tool.plux]`` section of your ``pyproject.toml`` file:

.. code-block:: toml

    [tool.plux]
    # The build mode for entry points: "build-hooks" (default) or "manual"
    entrypoint_build_mode = "build-hooks"
    
    # The file path to scan for plugins (optional)
    path = "src"
    
    # Python packages to exclude during discovery (optional)
    exclude = ["**/database/alembic*", "tests*"]
    
    # Python packages to include during discovery (optional)
    # Setting this will ignore all other paths
    include = ["**/plugins*"]

Build-hooks Mode (Default)
-----------------------

In build-hooks mode, plux automatically hooks into the setuptools build process to discover plugins and generate entry points.

Setting Up Your Project
~~~~~~~~~~~~~~~~~~~~~

1. Add plux as a build dependency in your ``pyproject.toml``:

.. code-block:: toml

    [build-system]
    requires = ["setuptools>=42", "wheel", "plux>=1.3.1"]
    build-backend = "setuptools.build_meta"

2. Build your project as usual:

.. code-block:: bash

    # Using pip
    pip install -e .
    
    # Or using setuptools directly
    python setup.py develop
    
    # Or building a distribution
    python -m build

How Build-hooks Mode Works
~~~~~~~~~~~~~~~~~~~~~~~

When you build your project:

1. Plux scans your codebase for plugins
2. It creates a ``plux.json`` file in the ``.egg-info`` directory
3. It extends the entry points in ``entry_points.txt``
4. These entry points are then included in your distribution

Manual Mode
---------

Manual mode gives you more control over when and how entry points are generated. This is useful for isolated build environments or when build hooks don't fit your build process.

Setting Up Manual Mode
~~~~~~~~~~~~~~~~~~~

1. Enable manual mode in your ``pyproject.toml``:

.. code-block:: toml

    [tool.plux]
    entrypoint_build_mode = "manual"

2. Configure your project to use the generated entry points:

.. code-block:: toml

    [project]
    dynamic = ["entry-points"]
    
    [tool.setuptools.package-data]
    "*" = ["plux.ini"]
    
    [tool.setuptools.dynamic]
    entry-points = {file = ["plux.ini"]}

3. Generate entry points manually:

.. code-block:: bash

    python -m plux entrypoints

This creates a ``plux.ini`` file in your working directory with the discovered plugins.

Customizing Plugin Discovery
-------------------------

You can customize which parts of your codebase are scanned for plugins:

Excluding Packages
~~~~~~~~~~~~~~~

To exclude specific packages from plugin discovery:

.. code-block:: bash

    # Exclude database migration scripts
    python -m plux entrypoints --exclude "**/database/alembic*"
    
    # Exclude multiple patterns (comma-separated)
    python -m plux discover --exclude "tests*,docs*" --format ini

You can also specify these in your ``pyproject.toml``:

.. code-block:: toml

    [tool.plux]
    exclude = ["**/database/alembic*", "tests*"]

Including Specific Packages
~~~~~~~~~~~~~~~~~~~~~~~~

To only include specific packages:

.. code-block:: bash

    # Include only specific patterns
    python -m plux discover --include "myapp/plugins*,myapp/extensions*" --format ini

Or in your ``pyproject.toml``:

.. code-block:: toml

    [tool.plux]
    include = ["myapp/plugins*", "myapp/extensions*"]

When ``include`` is specified, plux ignores all other paths.

Using the Plux CLI
---------------

The plux CLI provides several commands for working with plugins and entry points:

Generating Entry Points
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Generate entry points based on your pyproject.toml configuration
    python -m plux entrypoints
    
    # With custom include/exclude patterns
    python -m plux entrypoints --include "myapp/plugins*" --exclude "tests*"

Discovering Plugins
~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Discover plugins and output in JSON format
    python -m plux discover --format json
    
    # Discover plugins and save to a file
    python -m plux discover --format ini --output plux.ini
    
    # Discover plugins in a specific path
    python -m plux discover --path src/myapp

Showing Generated Entry Points
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Show the generated entry points
    python -m plux show

Resolving Plugins
~~~~~~~~~~~~~~

.. code-block:: bash

    # Resolve plugins in a specific namespace
    python -m plux resolve --namespace my.plugins.services

Integration with setuptools
------------------------

Plux integrates with setuptools in several ways:

Custom setuptools Command
~~~~~~~~~~~~~~~~~~~~~

Plux provides a custom setuptools command ``plugins`` that you can use in your ``setup.py``:

.. code-block:: bash

    python setup.py plugins

This command discovers plugins and writes them to a ``plux.json`` file in the ``.egg-info`` directory.

Setuptools Build Process Hooks
~~~~~~~~~~~~~~~~~~~~~~~~~~

Plux hooks into the setuptools build process to:

1. Generate entry points during the ``egg_info`` command
2. Handle editable installs with ``pip install -e .``
3. Support building wheels from source distributions

Direct Integration in setup.py
~~~~~~~~~~~~~~~~~~~~~~~~~~

For older projects using ``setup.py``, you can directly integrate plux:

.. code-block:: python

    from setuptools import setup
    from plux.build.setuptools import find_plugins
    
    setup(
        name="my-project",
        # ...
        entry_points=find_plugins()
    )

Troubleshooting
------------

Common issues and solutions:

Plugins Not Being Discovered
~~~~~~~~~~~~~~~~~~~~~~~~~

If your plugins aren't being discovered:

1. Check that your plugins correctly define ``namespace`` and ``name`` attributes
2. Verify that your include/exclude patterns aren't filtering out your plugins
3. Try running with verbose logging: ``python -m plux entrypoints -v``

Entry Points Not Being Generated
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If entry points aren't being generated:

1. Check your ``pyproject.toml`` configuration
2. Verify that plux is included in your build dependencies
3. Try manual mode to see if it resolves the issue

Editable Install Issues
~~~~~~~~~~~~~~~~~~~

For issues with editable installs:

1. Make sure you're using a recent version of pip and setuptools
2. Try reinstalling with ``pip install -e . --no-build-isolation``

Summary
------

Plux provides flexible integration with build systems, particularly setuptools. You can choose between automatic build-hooks mode or more controlled manual mode. The plux CLI offers commands for discovering plugins, generating entry points, and troubleshooting your setup.

For most projects, the default build-hooks mode with minimal configuration in ``pyproject.toml`` will work well. For more complex scenarios, manual mode and the CLI provide additional control.