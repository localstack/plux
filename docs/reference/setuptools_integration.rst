Setuptools Integration
===================

This reference guide explains how plux integrates with setuptools. Understanding this integration is helpful for troubleshooting build issues and for extending plux to support custom build processes.

Overview
-------

Plux integrates with setuptools to discover plugins at build time and generate entry points. This integration involves several components:

1. **Custom setuptools commands**: The ``plugins`` command for discovering plugins
2. **Build process hooks**: Patches to setuptools commands like ``egg_info`` and ``editable_wheel``
3. **Entry point writers**: Hooks into setuptools' entry point generation process
4. **Project configuration**: Integration with ``pyproject.toml`` and ``setup.py``

The Integration Process
--------------------

The setuptools integration process follows these steps:

1. Plux registers a custom setuptools command ``plugins``
2. When the command is run, it discovers plugins and writes them to a ``plux.json`` file
3. Plux patches the ``egg_info`` command to read the ``plux.json`` file and update entry points
4. Plux also patches the ``editable_wheel`` command to support editable installs
5. The generated entry points are included in the distribution metadata

Custom Setuptools Command
----------------------

Plux provides a custom setuptools command ``plugins``:

.. code-block:: python

    class plugins(InfoCommon, setuptools.Command):
        """
        Setuptools command that discovers plugins and writes them into the egg_info 
        directory to a ``plux.json`` file.
        """
        
        description = "Discover plux plugins and store them in .egg_info"
        
        user_options = [
            (
                "exclude=",
                "e",
                "a sequence of paths to exclude; '*' can be used as a wildcard in the names.",
            ),
            (
                "include=",
                "i",
                "a sequence of paths to include; If it's specified, only the named items will be included.",
            ),
        ]
        
        def initialize_options(self) -> None:
            self.plux_json_path = None
            self.exclude = None
            self.include = None
            self.plux_config = None
            
        def finalize_options(self) -> None:
            self.plux_json_path = get_plux_json_path(self.distribution)
            self.ensure_string_list("exclude")
            self.ensure_string_list("include")
            
            # Merge CLI arguments with pyproject.toml configuration
            self.plux_config = read_plux_configuration(self.distribution)
            self.plux_config = self.plux_config.merge(
                exclude=self.exclude,
                include=self.include,
            )
            
        def run(self) -> None:
            # Create a plugin index builder
            index_builder = create_plugin_index_builder(self.plux_config, self.distribution)
            
            # Write discovered plugins to plux.json
            self.mkpath(os.path.dirname(self.plux_json_path))
            with open(self.plux_json_path, "w") as fp:
                ep = index_builder.write(fp)
                
            # Update distribution entry points
            update_entrypoints(self.distribution, ep)

This command:

1. Reads configuration from ``pyproject.toml`` and command-line arguments
2. Creates a plugin index builder
3. Discovers plugins and writes them to a ``plux.json`` file
4. Updates the distribution's entry points

Build Process Hooks
----------------

Plux patches several setuptools commands to integrate with the build process:

Patching the egg_info Command
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``egg_info`` command is patched to read the ``plux.json`` file and update entry points:

.. code-block:: python

    def patch_egg_info_command():
        _run_orig = egg_info.run
        
        def _run(self):
            # Check if we're in manual mode
            cfg = read_plux_configuration(self.distribution)
            if cfg.entrypoint_build_mode == EntrypointBuildMode.MANUAL:
                return _run_orig(self)
                
            # Check if we should read from an existing egg_info directory
            should_read, meta_dir = _should_read_existing_egg_info()
            
            if should_read:
                # Copy plux.json from the existing egg_info directory
                plux_json = os.path.join(meta_dir, "plux.json")
                if os.path.exists(plux_json):
                    self.mkpath(self.egg_info)
                    if not os.path.exists(os.path.join(self.egg_info, "plux.json")):
                        shutil.copy(plux_json, self.egg_info)
                        
            return _run_orig(self)
            
        egg_info.run = _run

This patch:

1. Checks if plux is in manual mode
2. Checks if there's an existing egg_info directory with a ``plux.json`` file
3. If found, copies the ``plux.json`` file to the new egg_info directory
4. Calls the original ``egg_info.run`` method

Patching the editable_wheel Command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``editable_wheel`` command is patched to support editable installs:

.. code-block:: python

    def patch_editable_wheel_command():
        _ensure_dist_info_orig = editable_wheel._ensure_dist_info
        
        def _ensure_dist_info(self):
            _ensure_dist_info_orig(self)
            
            # Create a link to the original entry points
            target = Path(self.dist_info_dir, "entry_points_editable.txt")
            target.write_text(os.path.join(find_egg_info_dir(), "entry_points.txt"))
            
        editable_wheel._ensure_dist_info = _ensure_dist_info

This patch:

1. Calls the original ``_ensure_dist_info`` method
2. Creates a link from the dist-info directory to the egg-info directory
3. This link is used at runtime to find entry points in editable installs

Entry Point Writers
---------------

Plux hooks into setuptools' entry point generation process:

.. code-block:: python

    def load_plux_entrypoints(cmd, file_name, file_path):
        """
        This method is called indirectly by setuptools through the ``egg_info.writers`` plugin.
        """
        if not os.path.exists(file_path):
            return
            
        # Check if we're in manual mode
        cfg = read_plux_configuration(cmd.distribution)
        if cfg.entrypoint_build_mode == EntrypointBuildMode.MANUAL:
            return
            
        # Read plux.json and update entry points
        with open(file_path, "r") as fd:
            ep = json.load(fd)
            
        update_entrypoints(cmd.distribution, ep)
        
        # Write the updated entry points
        ep_file = "entry_points.txt"
        ep_path = os.path.join(os.path.dirname(file_path), ep_file)
        write_entries(cmd, ep_file, ep_path)

This function:

1. Checks if the ``plux.json`` file exists
2. Checks if plux is in manual mode
3. Reads the ``plux.json`` file and updates the distribution's entry points
4. Writes the updated entry points to ``entry_points.txt``

This function is registered as an entry point in plux's own ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."egg_info.writers"]
    "plux.json" = "plux.build.setuptools:load_plux_entrypoints"

Project Configuration
------------------

Plux integrates with project configuration in several ways:

Reading Configuration from pyproject.toml
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Plux reads configuration from the ``[tool.plux]`` section of ``pyproject.toml``:

.. code-block:: python

    def read_plux_configuration(distribution: setuptools.Distribution) -> config.PluxConfiguration:
        dirs = distribution.package_dir
        pyproject_base = (dirs or {}).get("", os.curdir)
        return config.read_plux_config_from_workdir(pyproject_base)

This function:

1. Gets the package directory from the distribution
2. Reads the ``pyproject.toml`` file from that directory
3. Parses the ``[tool.plux]`` section into a ``PluxConfiguration`` object

Direct Integration in setup.py
~~~~~~~~~~~~~~~~~~~~~~~~~~

For older projects using ``setup.py``, plux provides direct integration:

.. code-block:: python

    from setuptools import setup
    from plux.build.setuptools import find_plugins
    
    setup(
        name="my-project",
        # ...
        entry_points=find_plugins()
    )

The ``find_plugins`` function:

1. Discovers plugins in the project
2. Returns a dictionary of entry points
3. This dictionary can be passed directly to ``setup()``

SetuptoolsProject Class
--------------------

Plux provides a ``SetuptoolsProject`` class that implements the ``Project`` interface for setuptools:

.. code-block:: python

    class SetuptoolsProject(Project):
        def __init__(self, workdir: str = None):
            super().__init__(workdir)
            self.distribution = get_distribution_from_workdir(str(self.workdir))
            
        def find_entry_point_file(self) -> Path:
            if egg_info_dir := find_egg_info_dir():
                return Path(egg_info_dir, "entry_points.txt")
            raise FileNotFoundError("No .egg-info directory found.")
            
        def find_plux_index_file(self) -> Path:
            if self.config.entrypoint_build_mode == EntrypointBuildMode.MANUAL:
                return self.workdir / self.config.entrypoint_static_file
            return Path(get_plux_json_path(self.distribution))
            
        def create_plugin_index_builder(self) -> PluginIndexBuilder:
            return create_plugin_index_builder(self.config, self.distribution)
            
        def create_package_finder(self) -> PackageFinder:
            exclude = [_path_to_module(item) for item in self.config.exclude]
            include = [_path_to_module(item) for item in self.config.include]
            return DistributionPackageFinder(self.distribution, exclude=exclude, include=include)
            
        def build_entrypoints(self):
            dist = self.distribution
            
            # Run the plugins command
            dist.command_options["plugins"] = {
                "exclude": ("command line", ",".join(self.config.exclude) or None),
                "include": ("command line", ",".join(self.config.include) or None),
            }
            dist.run_command("plugins")
            
            # Run the egg_info command
            dist.run_command("egg_info")

This class:

1. Wraps a setuptools ``Distribution`` object
2. Provides methods for finding entry point files and plugin index files
3. Creates plugin index builders and package finders
4. Builds entry points by running setuptools commands

Package Finders
------------

Plux provides several package finders for setuptools:

DistributionPackageFinder
~~~~~~~~~~~~~~~~~~~~~

The ``DistributionPackageFinder`` finds packages in a setuptools distribution:

.. code-block:: python

    class DistributionPackageFinder(PackageFinder):
        def __init__(
            self,
            distribution: setuptools.Distribution,
            exclude: t.Iterable[str] | None = None,
            include: t.Iterable[str] | None = None,
        ):
            self.distribution = distribution
            self.exclude = Filter(exclude or [])
            self.include = Filter(include) if include else MatchAllFilter()
            
        def find_packages(self) -> t.Iterable[str]:
            if self.distribution.packages is None:
                raise ValueError(
                    "No packages found in setuptools distribution. Is your project configured correctly?"
                )
            return self.filter_packages(self.distribution.packages)
            
        @property
        def path(self) -> str:
            if not self.distribution.package_dir:
                where = "."
            else:
                if self.distribution.package_dir[""]:
                    where = self.distribution.package_dir[""]
                else:
                    where = "."
            return where
            
        def filter_packages(self, packages: t.Iterable[str]) -> t.Iterable[str]:
            return [item for item in packages if not self.exclude(item) and self.include(item)]

This class:

1. Gets packages from the distribution
2. Filters packages based on include/exclude patterns
3. Returns the path to the packages

SetuptoolsPackageFinder
~~~~~~~~~~~~~~~~~~~

The ``SetuptoolsPackageFinder`` uses setuptools directly to find packages:

.. code-block:: python

    class SetuptoolsPackageFinder(PackageFinder):
        def __init__(self, where=".", exclude=(), include=("*",), namespace=True) -> None:
            self.where = where
            self.exclude = exclude
            self.include = include
            self.namespace = namespace
            
        def find_packages(self) -> t.Iterable[str]:
            if self.namespace:
                return setuptools.find_namespace_packages(self.where, self.exclude, self.include)
            else:
                return setuptools.find_packages(self.where, self.exclude, self.include)
                
        @property
        def path(self) -> str:
            return self.where

This class:

1. Uses ``setuptools.find_packages`` or ``setuptools.find_namespace_packages``
2. Returns the packages found by setuptools
3. Returns the path to the packages

Troubleshooting
------------

Common issues with setuptools integration:

1. **Entry points not being generated**:
   - Check that plux is included in your build dependencies
   - Verify that your ``pyproject.toml`` configuration is correct
   - Try running ``python setup.py plugins`` manually to see if plugins are discovered

2. **Plugins not being discovered**:
   - Check that your plugins correctly define ``namespace`` and ``name`` attributes
   - Verify that your include/exclude patterns aren't filtering out your plugins
   - Try running with verbose logging: ``python setup.py -v plugins``

3. **Editable install issues**:
   - Make sure you're using a recent version of pip and setuptools
   - Try reinstalling with ``pip install -e . --no-build-isolation``
   - Check that the ``entry_points_editable.txt`` file is created in the dist-info directory

Summary
------

Plux's setuptools integration involves:

1. A custom setuptools command ``plugins`` for discovering plugins
2. Patches to setuptools commands like ``egg_info`` and ``editable_wheel``
3. Hooks into setuptools' entry point generation process
4. Integration with ``pyproject.toml`` and ``setup.py``
5. Package finders for discovering packages in setuptools distributions

This integration allows plux to discover plugins at build time and generate entry points that can be used at runtime to load plugins.