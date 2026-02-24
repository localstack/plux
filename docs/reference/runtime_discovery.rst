Plugin Discovery at Run Time
=========================

This reference guide explains how plux discovers plugins at runtime. Understanding this process is helpful for troubleshooting runtime plugin discovery issues and for extending plux to support custom runtime plugin discovery mechanisms.

Overview
-------

At runtime, plux uses Python's entry point mechanism to discover plugins. This is done through a series of abstractions that handle different aspects of the discovery process:

1. **PluginFinder**: Finds plugins from entry points
2. **PluginManager**: Manages the lifecycle of discovered plugins
3. **PluginFilter**: Filters which plugins should be loaded

The Discovery Process
------------------

The runtime discovery process follows these steps:

1. A **PluginManager** is created for a specific namespace
2. The manager uses a **MetadataPluginFinder** to find plugins in that namespace
3. The finder uses Python's ``importlib.metadata`` to discover entry points
4. Entry points are loaded and resolved to **PluginSpec** instances
5. The manager creates **PluginContainer** instances for each spec
6. When requested, the manager initializes and loads plugins from their containers

Entry Point Discovery
-----------------

The ``MetadataPluginFinder`` class discovers plugins from entry points:

.. code-block:: python

    from importlib.metadata import entry_points
    from plux import PluginFinder, PluginSpec, PluginSpecResolver
    
    class MetadataPluginFinder(PluginFinder):
        def __init__(self, namespace: str, resolver: PluginSpecResolver = None):
            self.namespace = namespace
            self.resolver = resolver or PluginSpecResolver()
            
        def find_plugins(self) -> list[PluginSpec]:
            plugins = []
            
            # Get all entry points in the namespace
            for entry_point in entry_points(group=self.namespace):
                try:
                    # Load the entry point
                    obj = entry_point.load()
                    
                    # Resolve the plugin specification
                    spec = self.resolver.resolve(obj)
                    plugins.append(spec)
                except Exception as e:
                    # Handle errors
                    pass
                    
            return plugins

This class:

1. Gets all entry points in the specified namespace using ``importlib.metadata.entry_points()``
2. Loads each entry point using ``entry_point.load()``
3. Resolves the loaded object to a ``PluginSpec`` using a ``PluginSpecResolver``
4. Returns a list of all successfully resolved plugin specifications

Plugin Resolution
--------------

The ``PluginSpecResolver`` class resolves plugin specifications from entry points:

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

Plugin Container Management
------------------------

The ``PluginManager`` creates and manages ``PluginContainer`` instances for each discovered plugin:

.. code-block:: python

    class PluginContainer(t.Generic[P]):
        def __init__(self, plugin_spec: PluginSpec):
            self.plugin_spec = plugin_spec
            self.plugin = None
            self.loaded = False
            self.disabled = False
            self.disabled_reason = None
            self._distribution = None
            
        @property
        def distribution(self) -> Distribution | None:
            if self._distribution is None:
                self._distribution = resolve_distribution_information(self.plugin_spec)
            return self._distribution

A ``PluginContainer`` holds:

1. The ``PluginSpec`` for the plugin
2. The plugin instance (once initialized)
3. The loading status of the plugin
4. Whether the plugin is disabled
5. Distribution information for the plugin

Plugin Initialization and Loading
------------------------------

The ``PluginManager`` handles plugin initialization and loading:

.. code-block:: python

    def _load_plugin(self, container: PluginContainer) -> t.Any:
        # Check if already loaded
        if container.loaded:
            return container.load_result
            
        # Check if disabled
        if container.disabled:
            raise PluginDisabled(
                container.plugin_spec.namespace,
                container.plugin_spec.name,
                container.disabled_reason,
            )
            
        # Initialize plugin if not already initialized
        if container.plugin is None:
            container.plugin = self._plugin_from_spec(container.plugin_spec)
            
        plugin = container.plugin
        
        # Check if plugin should be loaded
        if not plugin.should_load():
            return None
            
        # Prepare load arguments
        load_args = list(self.load_args) if self.load_args else []
        load_kwargs = dict(self.load_kwargs) if self.load_kwargs else {}
        
        # Fire lifecycle event
        self._fire_on_load_before(container.plugin_spec, plugin, load_args, load_kwargs)
        
        # Load the plugin
        result = plugin.load(*load_args, **load_kwargs)
        
        # Update container state
        container.loaded = True
        container.load_result = result
        
        # Fire lifecycle event
        self._fire_on_load_after(container.plugin_spec, plugin, result)
        
        return result

This method:

1. Checks if the plugin is already loaded or disabled
2. Initializes the plugin if needed
3. Checks if the plugin should be loaded
4. Prepares load arguments
5. Fires lifecycle events before loading
6. Loads the plugin
7. Updates the container state
8. Fires lifecycle events after loading
9. Returns the load result

Plugin Filtering
-------------

The ``PluginManager`` applies filters to control which plugins are loaded:

.. code-block:: python

    def _init_plugin_index(self):
        # Find plugins
        plugin_specs = self.finder.find_plugins()
        
        # Apply filters
        for spec in plugin_specs:
            # Check global filter
            if global_plugin_filter(spec):
                continue
                
            # Check manager-specific filters
            if any(f(spec) for f in self.filters):
                continue
                
            # Create container for the plugin
            container = self._create_container(spec)
            self._plugins_by_name[spec.name] = container

This method:

1. Finds plugins using the ``PluginFinder``
2. Applies the global plugin filter
3. Applies manager-specific filters
4. Creates containers for plugins that pass all filters

Distribution Information
---------------------

Plux can resolve distribution information for plugins:

.. code-block:: python

    def resolve_distribution_information(plugin_spec: PluginSpec) -> Distribution | None:
        try:
            # Get the module of the plugin factory
            module = inspect.getmodule(plugin_spec.factory)
            if not module:
                return None
                
            # Get the distribution for the module
            return Distribution.from_module(module)
        except Exception:
            return None

This function:

1. Gets the module of the plugin factory
2. Resolves the distribution information for that module
3. Returns a ``Distribution`` object with name, version, and other metadata

Editable Installs Support
----------------------

Plux has special support for editable installs:

1. When using ``pip install -e .``, plux creates a link from the installed dist-info directory to the source egg-info directory
2. This link is stored in ``entry_points_editable.txt`` in the dist-info directory
3. At runtime, plux checks for this file and follows the link to find entry points

.. code-block:: python

    def entry_points_from_metadata_path(path: str) -> EntryPointDict:
        # Check for editable install link
        editable_link = os.path.join(path, "entry_points_editable.txt")
        if os.path.exists(editable_link):
            with open(editable_link, "r") as fd:
                path = fd.read().strip()
                
        # Read entry points from the path
        entry_points_file = os.path.join(path, "entry_points.txt")
        if os.path.exists(entry_points_file):
            return read_entry_points(entry_points_file)
            
        return {}

This function:

1. Checks for an editable install link
2. If found, follows the link to the source egg-info directory
3. Reads entry points from the entry_points.txt file

Extending Runtime Discovery
------------------------

You can extend plux's runtime discovery mechanism by implementing custom finders:

Custom Plugin Finder
~~~~~~~~~~~~~~~~~

To customize how plugins are discovered at runtime:

.. code-block:: python

    from plux import PluginFinder, PluginSpec
    
    class MyPluginFinder(PluginFinder):
        def __init__(self, namespace: str):
            self.namespace = namespace
            
        def find_plugins(self) -> list[PluginSpec]:
            # Custom plugin discovery logic
            return discovered_plugins
            
    # Use the custom finder with a PluginManager
    manager = PluginManager("my.plugins", finder=MyPluginFinder("my.plugins"))

Custom Plugin Filter
~~~~~~~~~~~~~~~~

To customize how plugins are filtered:

.. code-block:: python

    from plux.runtime.filter import PluginFilter
    from plux.core.plugin import PluginSpec
    
    class MyPluginFilter:
        def __call__(self, spec: PluginSpec) -> bool:
            # Return True to filter out (disable) the plugin
            # Return False to include the plugin
            return should_filter_plugin(spec)
            
    # Use the custom filter with a PluginManager
    manager = PluginManager("my.plugins", filters=[MyPluginFilter()])

Troubleshooting
------------

Common issues with runtime plugin discovery:

1. **Plugins not being discovered**:
   - Check that entry points were correctly generated during the build
   - Verify that the package is correctly installed
   - Check that you're using the correct namespace

2. **Entry points not being found**:
   - For editable installs, make sure you're using a recent version of pip and setuptools
   - Try reinstalling with ``pip install -e . --no-build-isolation``

3. **Plugin loading errors**:
   - Use a ``PluginLifecycleListener`` to debug plugin loading issues
   - Check that plugins correctly implement the ``Plugin`` interface

Summary
------

Plux's runtime plugin discovery process involves:

1. Finding entry points in a specific namespace
2. Loading entry points and resolving them to plugin specifications
3. Creating containers for each plugin specification
4. Initializing and loading plugins when requested
5. Applying filters to control which plugins are loaded

This process is highly customizable through the ``PluginFinder`` and ``PluginFilter`` abstractions, and includes special support for editable installs to make development easier.