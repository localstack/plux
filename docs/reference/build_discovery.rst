Plugin Discovery at Build Time
===========================

This reference guide explains how plux discovers plugins at build time. Understanding this process is helpful for troubleshooting plugin discovery issues and for extending plux to support custom plugin discovery mechanisms.

Overview
-------

At build time, plux scans your project's source code to find plugins. This is done through a series of abstractions that handle different aspects of the discovery process:

1. **PackageFinder**: Finds Python packages to scan
2. **PluginFinder**: Finds plugins within those packages
3. **PluginSpecResolver**: Resolves plugin specifications from various sources

The Discovery Process
------------------

The build-time discovery process follows these steps:

1. A **PackageFinder** implementation (e.g., ``DistributionPackageFinder``) identifies Python packages to scan
2. A **PluginFromPackageFinder** uses the PackageFinder to load modules from those packages
3. A **ModuleScanningPluginFinder** scans the loaded modules for plugin specifications
4. A **PluginSpecResolver** resolves plugin specifications from various sources (classes, functions, etc.)
5. The discovered plugin specifications are written to a plugin index file (``plux.json``)
6. The plugin index is used to generate entry points in ``entry_points.txt``

Package Discovery
--------------

The ``PackageFinder`` abstraction is responsible for finding Python packages to scan for plugins:

.. code-block:: python

    class PackageFinder:
        def find_packages(self) -> t.Iterable[str]:
            """
            Returns an Iterable of Python packages. Each item is a string-representation 
            of a Python package (for example, ``plux.core``, ``myproject.mypackage.utils``, ...)
            """
            raise NotImplementedError
            
        @property
        def path(self) -> str:
            """
            The root file path under which the packages are located.
            """
            raise NotImplementedError

Plux provides several implementations:

1. **DistributionPackageFinder**: Uses setuptools to find packages in a distribution
2. **SetuptoolsPackageFinder**: Uses setuptools directly to find packages

Module Loading
-----------

The ``PluginFromPackageFinder`` class loads modules from the packages found by the ``PackageFinder``:

.. code-block:: python

    class PluginFromPackageFinder(PluginFinder):
        def __init__(self, finder: PackageFinder):
            self.finder = finder
            
        def find_plugins(self) -> list[PluginSpec]:
            collector = ModuleScanningPluginFinder(self._load_modules())
            return collector.find_plugins()
            
        def _load_modules(self) -> t.Generator[ModuleType, None, None]:
            # Load modules from packages
            ...

This class:

1. Gets a list of package names from the ``PackageFinder``
2. Converts package names to module names
3. Imports each module using ``importlib.import_module()``
4. Passes the loaded modules to a ``ModuleScanningPluginFinder``

Module Scanning
------------

The ``ModuleScanningPluginFinder`` class scans loaded modules for plugin specifications:

.. code-block:: python

    class ModuleScanningPluginFinder(PluginFinder):
        def __init__(self, modules: t.Iterable[ModuleType], resolver: PluginSpecResolver = None) -> None:
            self.modules = modules
            self.resolver = resolver or PluginSpecResolver()
            
        def find_plugins(self) -> list[PluginSpec]:
            plugins = list()
            
            for module in self.modules:
                members = inspect.getmembers(module)
                
                for member in members:
                    if type(member) is tuple:
                        try:
                            spec = self.resolver.resolve(member[1])
                            plugins.append(spec)
                        except Exception:
                            pass
                            
            return plugins

This class:

1. Iterates through each module
2. Gets all members of the module using ``inspect.getmembers()``
3. Tries to resolve each member as a plugin specification
4. Collects all successfully resolved plugin specifications

Plugin Specification Resolution
----------------------------

The ``PluginSpecResolver`` class resolves plugin specifications from various sources:

.. code-block:: python

    class PluginSpecResolver:
        def resolve(self, source: t.Any) -> PluginSpec:
            if isinstance(source, PluginSpec):
                return source
                
            if inspect.isclass(source):
                if issubclass(source, Plugin):
                    return PluginSpec(source.namespace, source.name, source)
                    
            if inspect.isfunction(source):
                spec = getattr(source, "__pluginspec__", None)
                if spec and isinstance(spec, PluginSpec):
                    return spec
                    
            raise ValueError("cannot resolve plugin specification from %s" % source)

This class can resolve plugin specifications from:

1. Existing ``PluginSpec`` instances
2. Plugin classes (subclasses of ``Plugin`` with ``namespace`` and ``name`` attributes)
3. Functions decorated with ``@plugin`` (which have a ``__pluginspec__`` attribute)

Filtering Packages
---------------

Plux provides filtering capabilities to include or exclude specific packages during discovery:

.. code-block:: python

    class Filter:
        def __init__(self, patterns: t.Iterable[str]):
            self._patterns = patterns
            
        def __call__(self, item: str):
            return any(fnmatchcase(item, pat) for pat in self._patterns)

Filters can be configured in ``pyproject.toml`` or via command-line arguments:

.. code-block:: toml

    [tool.plux]
    exclude = ["**/database/alembic*", "tests*"]
    include = ["myapp/plugins*"]

Plugin Index Building
------------------

The ``PluginIndexBuilder`` class builds a plugin index from discovered plugins:

.. code-block:: python

    class PluginIndexBuilder:
        def __init__(self, finder: PluginFinder):
            self.finder = finder
            
        def write(self, fp, output_format="json") -> EntryPointDict:
            plugins = self.finder.find_plugins()
            entry_points = discover_entry_points(plugins)
            
            if output_format == "json":
                json.dump(entry_points, fp, indent=2)
            elif output_format == "ini":
                write_ini(entry_points, fp)
                
            return entry_points

This class:

1. Uses a ``PluginFinder`` to discover plugins
2. Converts the discovered plugins to entry points
3. Writes the entry points to a file in the specified format (JSON or INI)

Entry Point Generation
-------------------

The final step is generating entry points from the plugin index:

1. In **build-hooks mode**, plux hooks into the setuptools build process:
   - The ``plugins`` command writes discovered plugins to ``plux.json``
   - The ``egg_info`` command reads ``plux.json`` and updates ``entry_points.txt``

2. In **manual mode**, plux writes entry points to ``plux.ini``, which you include in your build configuration:

   .. code-block:: toml

       [project]
       dynamic = ["entry-points"]
       
       [tool.setuptools.dynamic]
       entry-points = {file = ["plux.ini"]}

Extending Plugin Discovery
-----------------------

You can extend plux's plugin discovery mechanism by implementing custom finders:

Custom Package Finder
~~~~~~~~~~~~~~~~~~

To customize how packages are discovered:

.. code-block:: python

    from plux.build.discovery import PackageFinder
    
    class MyPackageFinder(PackageFinder):
        def __init__(self, custom_packages):
            self.custom_packages = custom_packages
            
        def find_packages(self) -> t.Iterable[str]:
            return self.custom_packages
            
        @property
        def path(self) -> str:
            return "."

Custom Plugin Finder
~~~~~~~~~~~~~~~~~

To customize how plugins are discovered:

.. code-block:: python

    from plux import PluginFinder, PluginSpec
    
    class MyPluginFinder(PluginFinder):
        def find_plugins(self) -> list[PluginSpec]:
            # Custom plugin discovery logic
            return discovered_plugins

Troubleshooting
------------

Common issues with build-time plugin discovery:

1. **Plugins not being discovered**:
   - Check that your plugins correctly define ``namespace`` and ``name`` attributes
   - Verify that your include/exclude patterns aren't filtering out your plugins
   - Try running with verbose logging: ``python -m plux entrypoints -v``

2. **Import errors during discovery**:
   - Plux imports modules to discover plugins, which can cause issues if modules have side effects
   - Use exclude patterns to skip problematic modules: ``exclude = ["**/problematic_module*"]``

3. **Performance issues**:
   - Scanning large codebases can be slow
   - Use include patterns to focus on specific packages: ``include = ["myapp/plugins*"]``

Summary
------

Plux's build-time plugin discovery process involves:

1. Finding Python packages to scan
2. Loading modules from those packages
3. Scanning modules for plugin specifications
4. Resolving plugin specifications from various sources
5. Building a plugin index
6. Generating entry points from the plugin index

This process is highly customizable through the ``PackageFinder`` and ``PluginFinder`` abstractions, and can be configured using include/exclude patterns in ``pyproject.toml`` or via command-line arguments.