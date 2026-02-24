PluginManager: Managing Plugins
=============================

The ``PluginManager`` is the central component in plux for managing plugins at runtime. This guide covers how to use the PluginManager API to load, lookup, and manage plugins.

Creating a PluginManager
----------------------

To create a PluginManager, you need to specify the namespace of plugins you want to manage:

.. code-block:: python

    from plux import PluginManager
    
    # Create a manager for a specific namespace
    manager = PluginManager("my.plugins.services")

You can also provide default arguments that will be passed to all plugins when they are loaded:

.. code-block:: python

    # Create a manager with default load arguments
    config = load_configuration()
    manager = PluginManager(
        namespace="my.plugins.services",
        load_args=(config,),  # Positional arguments
        load_kwargs={"debug": True}  # Keyword arguments
    )

Loading Plugins
-------------

The PluginManager provides several methods for loading plugins:

Loading a Single Plugin
~~~~~~~~~~~~~~~~~~~~~

To load a specific plugin by name:

.. code-block:: python

    # Load a plugin by name
    s3_service = manager.load("s3")
    
    # Load a plugin with additional arguments
    dynamodb = manager.load("dynamodb", additional_arg="value")

The ``load`` method:

1. Resolves the plugin specification
2. Initializes the plugin instance
3. Calls the plugin's ``should_load()`` method to check if it should be loaded
4. If ``should_load()`` returns True, calls the plugin's ``load()`` method
5. Returns the result of the ``load()`` method

Loading All Plugins
~~~~~~~~~~~~~~~~~

To load all plugins in a namespace:

.. code-block:: python

    # Load all plugins in the namespace
    all_services = manager.load_all()
    
    # By default, exceptions in one plugin won't stop others from loading
    # Set propagate_exceptions=True to change this behavior
    all_services = manager.load_all(propagate_exceptions=True)

The ``load_all`` method returns a list of successfully loaded plugins.

Checking Plugin Status
-------------------

The PluginManager provides methods to check the status of plugins:

.. code-block:: python

    # Check if a plugin exists (is discoverable)
    if manager.exists("s3"):
        # Plugin exists
        pass
        
    # Check if a plugin is already loaded
    if manager.is_loaded("s3"):
        # Plugin is loaded
        pass

Listing Plugins
------------

You can list available plugins in several ways:

.. code-block:: python

    # List all plugin specifications in the namespace
    specs = manager.list_plugin_specs()
    
    # List just the names of available plugins
    names = manager.list_names()
    
    # List plugin containers (which include metadata about the plugins)
    containers = manager.list_containers()

Accessing Plugin Containers
------------------------

A ``PluginContainer`` holds metadata about a plugin, including its specification, instance, and loading status:

.. code-block:: python

    # Get a container for a specific plugin
    container = manager.get_container("s3")
    
    # Access container properties
    spec = container.plugin_spec  # The plugin specification
    plugin = container.plugin     # The plugin instance (if initialized)
    is_loaded = container.loaded  # Whether the plugin has been loaded
    
    # Get distribution information
    dist = container.distribution
    if dist:
        print(f"Plugin from package: {dist.name} {dist.version}")

Error Handling
-----------

The PluginManager handles errors that occur during plugin loading:

.. code-block:: python

    try:
        plugin = manager.load("non_existent")
    except KeyError:
        # Plugin not found
        pass
        
    try:
        plugin = manager.load("problematic")
    except Exception as e:
        # Error during plugin loading
        print(f"Failed to load plugin: {e}")

For ``load_all()``, by default, exceptions are caught and logged, but loading continues for other plugins. Set ``propagate_exceptions=True`` to raise exceptions immediately.

Working with Plugin Lifecycle Listeners
------------------------------------

You can add lifecycle listeners to a PluginManager to monitor and react to plugin lifecycle events:

.. code-block:: python

    from plux import PluginLifecycleListener, PluginManager
    
    class MyListener(PluginLifecycleListener):
        def on_load_before(self, plugin_spec, plugin, load_args, load_kwargs):
            print(f"About to load plugin: {plugin_spec.name}")
            
        def on_load_after(self, plugin_spec, plugin, load_result):
            print(f"Plugin loaded: {plugin_spec.name}, result: {load_result}")
            
        def on_load_exception(self, plugin_spec, plugin, exception):
            print(f"Error loading plugin {plugin_spec.name}: {exception}")
    
    # Create a manager with a listener
    manager = PluginManager(
        namespace="my.plugins.services",
        listener=MyListener()
    )
    
    # Or add a listener to an existing manager
    manager.add_listener(MyListener())

You can add multiple listeners to a single manager.

Using Filters with PluginManager
-----------------------------

You can apply filters to control which plugins are loaded:

.. code-block:: python

    from plux import PluginManager
    from plux.runtime.filter import MatchingPluginFilter
    
    # Create a filter
    my_filter = MatchingPluginFilter()
    
    # Exclude specific plugins
    my_filter.add_exclusion(name="legacy_plugin")
    my_filter.add_exclusion(namespace="my.plugins.experimental.*")
    
    # Create a manager with the filter
    manager = PluginManager(
        namespace="my.plugins.services",
        filters=[my_filter]
    )

Generic Type Support
-----------------

The PluginManager supports generic typing to help with type checking:

.. code-block:: python

    from plux import Plugin, PluginManager
    
    class ServicePlugin(Plugin):
        def load(self) -> "Service":
            pass
    
    # Use the generic type parameter to specify the plugin type
    manager: PluginManager[ServicePlugin] = PluginManager("my.plugins.services")
    
    # Now IDE and type checkers know the type of loaded plugins
    service = manager.load("s3")  # Type is inferred as Service

Best Practices
-----------

Here are some best practices for using PluginManager:

1. **Create managers for specific namespaces**: Keep your plugin namespaces organized by functionality.

2. **Use lifecycle listeners for monitoring**: Implement listeners to track plugin loading and handle errors.

3. **Handle errors gracefully**: Always handle potential exceptions when loading plugins.

4. **Use filters for control**: Apply filters to exclude plugins in certain environments or configurations.

5. **Leverage generic typing**: Use type hints to improve code quality and IDE support.

6. **Reuse managers**: Create managers once and reuse them throughout your application.

Summary
------

The PluginManager is a powerful tool for managing plugins at runtime. It provides methods for loading plugins, checking their status, and accessing metadata. With lifecycle listeners and filters, you can customize the plugin loading process to suit your application's needs.