Defining and Loading Plugins
============================

This guide covers the different ways to define plugins in plux and how to load them at runtime.

Plugin Basics
-------------

In plux, a plugin is an object that implements the ``Plugin`` interface, which requires two methods:

* ``should_load()``: Determines whether the plugin should be loaded
* ``load(*args, **kwargs)``: Performs the actual loading of the plugin

The Plugin Class
----------------

The most basic way to define a plugin is by subclassing the ``Plugin`` class:

.. code-block:: python

    from plux import Plugin

    class MyPlugin(Plugin):
        namespace = "my.plugins"
        name = "my_plugin"
        
        def should_load(self):
            # Optional: Override to add custom logic
            # By default, returns True
            return True
            
        def load(self, *args, **kwargs):
            # Implement your plugin's loading logic
            # Can return any value, which will be passed back to the caller
            return "Plugin loaded successfully"

Plugin Namespaces and Names
-------------------------

Every plugin must have:

* A ``namespace``: A dot-separated string that groups related plugins (e.g., "my.plugins.services")
* A ``name``: A unique identifier within that namespace (e.g., "s3")

These attributes are used by the ``PluginManager`` to locate and load plugins.

Different Ways to Define Plugins
------------------------------

Plux offers several approaches to define plugins:

1. One Class Per Plugin
~~~~~~~~~~~~~~~~~~~~~

This is the most straightforward approach, where each plugin is a separate class:

.. code-block:: python

    class S3Plugin(Plugin):
        namespace = "my.plugins.services"
        name = "s3"
        
        def load(self, config):
            # Initialize S3 service
            pass
            
    class DynamoDBPlugin(Plugin):
        namespace = "my.plugins.services"
        name = "dynamodb"
        
        def load(self, config):
            # Initialize DynamoDB service
            pass

2. Re-usable Plugins
~~~~~~~~~~~~~~~~~~

When you have many similar plugins, you can use a single plugin class with different instances:

.. code-block:: python

    from plux import Plugin, PluginFactory, PluginSpec
    import importlib
    
    class ServicePlugin(Plugin):
        def __init__(self, service_name):
            self.service_name = service_name
            self.service = None
            
        def should_load(self):
            # Check if this service is enabled in config
            return self.service_name in config.SERVICES
            
        def load(self):
            # Import and initialize the service
            module = importlib.import_module(f"my.services.{self.service_name}")
            self.service = module.Service()
            return self.service
            
    def service_plugin_factory(name) -> PluginFactory:
        def create():
            return ServicePlugin(name)
        return create
        
    # Define plugin specs that will be discovered at build time
    s3 = PluginSpec("my.plugins.services", "s3", service_plugin_factory("s3"))
    dynamodb = PluginSpec("my.plugins.services", "dynamodb", service_plugin_factory("dynamodb"))

3. Function Plugins
~~~~~~~~~~~~~~~~

For simple plugins, you can use the ``@plugin`` decorator to turn functions into plugins:

.. code-block:: python

    from plux import plugin
    
    @plugin(namespace="my.plugins.initializers")
    def setup_logging(config):
        # Configure logging based on config
        pass
        
    @plugin(namespace="my.plugins.initializers", 
            should_load=lambda: config.DEBUG_MODE)
    def setup_debug_tools(config):
        # Initialize debug tools
        pass

The ``@plugin`` decorator wraps the function in a ``FunctionPlugin`` that implements the ``Plugin`` interface.

Loading Plugins
-------------

Once plugins are defined, you can load them using the ``PluginManager``:

.. code-block:: python

    from plux import PluginManager
    
    # Create a manager for a specific namespace
    manager = PluginManager("my.plugins.services")
    
    # Load a specific plugin by name
    s3_service = manager.load("s3")
    
    # Load all plugins in the namespace
    all_services = manager.load_all()
    
    # Check if a plugin exists
    if manager.exists("dynamodb"):
        # Load it only if it exists
        dynamodb = manager.load("dynamodb")
        
    # Check if a plugin is already loaded
    if manager.is_loaded("s3"):
        # Get the loaded plugin
        s3 = manager.get_container("s3").plugin

Passing Arguments to Plugins
--------------------------

You can pass arguments to plugins when loading them:

.. code-block:: python

    # Pass arguments to all plugins loaded by this manager
    manager = PluginManager("my.plugins.services", 
                           load_args=(config,))
    
    # Pass arguments to a specific plugin
    s3 = manager.load("s3", additional_arg="value")
    
    # For function plugins, you can call them with arguments
    @plugin(namespace="my.plugins.handlers")
    def process_event(event, context):
        # Process the event
        return result
        
    # Load and call the function plugin
    handler = manager.load("process_event")
    result = handler(event, context)

Plugin Load Return Values
-----------------------

The ``load`` method of a plugin can return any value, which is passed back to the caller:

.. code-block:: python

    class ConfigPlugin(Plugin):
        namespace = "my.plugins.config"
        name = "database"
        
        def load(self):
            # Return a configuration dictionary
            return {
                "host": "localhost",
                "port": 5432,
                "username": "user",
                "password": "password"
            }
            
    # The return value is passed back to the caller
    db_config = manager.load("database")
    
    # Use the configuration
    connection = connect_to_db(**db_config)

Summary
------

Plux provides flexible ways to define plugins:

* Subclass ``Plugin`` for full control
* Use ``PluginSpec`` with factories for reusable plugins
* Use the ``@plugin`` decorator for function-based plugins

The ``PluginManager`` makes it easy to load plugins at runtime, with support for passing arguments and handling return values.