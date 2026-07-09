PluginLifecycleListener
=====================

The ``PluginLifecycleListener`` interface allows you to monitor and react to plugin lifecycle events. This guide explains how to create and use lifecycle listeners to track plugin loading, handle errors, and customize the plugin lifecycle.

Understanding the Plugin Lifecycle
-------------------------------

A plugin managed by a ``PluginManager`` goes through several lifecycle phases:

1. **Resolution**: The entry point pointing to the ``PluginSpec`` is imported and the ``PluginSpec`` instance is created.
2. **Initialization**: The ``PluginFactory`` of the ``PluginSpec`` is invoked to create a ``Plugin`` instance.
3. **Loading**: The ``load`` method of the ``Plugin`` is invoked.

At each phase, events are triggered that can be captured by a ``PluginLifecycleListener``.

Creating a PluginLifecycleListener
-------------------------------

To create a lifecycle listener, implement the ``PluginLifecycleListener`` interface:

.. code-block:: python

    from plux import PluginLifecycleListener, PluginSpec, Plugin
    
    class MyLifecycleListener(PluginLifecycleListener):
        # Override the methods you're interested in
        pass

The interface provides several methods that you can override to handle different lifecycle events.

Resolution Phase Events
--------------------

Events related to the resolution phase:

.. code-block:: python

    def on_resolve_after(self, plugin_spec: PluginSpec):
        """
        Called after a PluginSpec is successfully resolved from an entry point.
        
        :param plugin_spec: The resolved PluginSpec
        """
        print(f"Resolved plugin: {plugin_spec.namespace}:{plugin_spec.name}")
        
    def on_resolve_exception(self, namespace: str, entrypoint, exception: Exception):
        """
        Called when an exception occurs during plugin resolution.
        
        :param namespace: The namespace of the plugin being resolved
        :param entrypoint: The entry point that was being resolved
        :param exception: The exception that occurred
        """
        print(f"Error resolving plugin in namespace {namespace}: {exception}")

Initialization Phase Events
------------------------

Events related to the initialization phase:

.. code-block:: python

    def on_init_after(self, plugin_spec: PluginSpec, plugin: Plugin):
        """
        Called after a Plugin is successfully initialized.
        
        :param plugin_spec: The PluginSpec used to create the plugin
        :param plugin: The newly created Plugin instance
        """
        print(f"Initialized plugin: {plugin_spec.name}")
        
    def on_init_exception(self, plugin_spec: PluginSpec, exception: Exception):
        """
        Called when an exception occurs during plugin initialization.
        
        :param plugin_spec: The PluginSpec that was being used
        :param exception: The exception that occurred
        """
        print(f"Error initializing plugin {plugin_spec.name}: {exception}")

Loading Phase Events
-----------------

Events related to the loading phase:

.. code-block:: python

    def on_load_before(self, plugin_spec: PluginSpec, plugin: Plugin, load_args: list | tuple, load_kwargs: dict):
        """
        Called just before a plugin's load method is invoked.
        
        :param plugin_spec: The PluginSpec of the plugin
        :param plugin: The Plugin instance
        :param load_args: Positional arguments that will be passed to load()
        :param load_kwargs: Keyword arguments that will be passed to load()
        """
        print(f"About to load plugin: {plugin_spec.name} with args: {load_args}, kwargs: {load_kwargs}")
        
    def on_load_after(self, plugin_spec: PluginSpec, plugin: Plugin, load_result: any = None):
        """
        Called after a plugin's load method is successfully invoked.
        
        :param plugin_spec: The PluginSpec of the plugin
        :param plugin: The Plugin instance
        :param load_result: The value returned by the plugin's load method
        """
        print(f"Loaded plugin: {plugin_spec.name}, result: {load_result}")
        
    def on_load_exception(self, plugin_spec: PluginSpec, plugin: Plugin, exception: Exception):
        """
        Called when an exception occurs during plugin loading.
        
        :param plugin_spec: The PluginSpec of the plugin
        :param plugin: The Plugin instance
        :param exception: The exception that occurred
        """
        print(f"Error loading plugin {plugin_spec.name}: {exception}")

Using a PluginLifecycleListener
----------------------------

To use a lifecycle listener, pass it to the ``PluginManager`` constructor:

.. code-block:: python

    from plux import PluginManager
    
    # Create a listener
    listener = MyLifecycleListener()
    
    # Create a manager with the listener
    manager = PluginManager(
        namespace="my.plugins",
        listener=listener
    )

You can also add a listener to an existing manager:

.. code-block:: python

    manager = PluginManager("my.plugins")
    manager.add_listener(MyLifecycleListener())

Using Multiple Listeners
---------------------

You can use multiple listeners with a single ``PluginManager``:

.. code-block:: python

    # Create listeners for different purposes
    logging_listener = LoggingListener()
    metrics_listener = MetricsListener()
    
    # Add them to the manager
    manager = PluginManager(
        namespace="my.plugins",
        listener=[logging_listener, metrics_listener]
    )
    
    # Or add them individually
    manager.add_listener(ErrorHandlingListener())

Practical Examples
---------------

Here are some practical examples of how to use lifecycle listeners:

Logging Listener
~~~~~~~~~~~~~~

A listener that logs all plugin lifecycle events:

.. code-block:: python

    import logging
    from plux import PluginLifecycleListener
    
    class LoggingListener(PluginLifecycleListener):
        def __init__(self, logger=None):
            self.logger = logger or logging.getLogger("plux.plugins")
            
        def on_resolve_after(self, plugin_spec):
            self.logger.debug(f"Resolved plugin: {plugin_spec.namespace}:{plugin_spec.name}")
            
        def on_init_after(self, plugin_spec, plugin):
            self.logger.debug(f"Initialized plugin: {plugin_spec.name}")
            
        def on_load_before(self, plugin_spec, plugin, load_args, load_kwargs):
            self.logger.debug(f"Loading plugin: {plugin_spec.name}")
            
        def on_load_after(self, plugin_spec, plugin, load_result):
            self.logger.info(f"Loaded plugin: {plugin_spec.name}")
            
        def on_load_exception(self, plugin_spec, plugin, exception):
            self.logger.error(f"Error loading plugin {plugin_spec.name}: {exception}", exc_info=True)

Metrics Listener
~~~~~~~~~~~~~

A listener that collects metrics about plugin loading:

.. code-block:: python

    import time
    from plux import PluginLifecycleListener
    
    class MetricsListener(PluginLifecycleListener):
        def __init__(self):
            self.load_times = {}
            self.error_count = 0
            
        def on_load_before(self, plugin_spec, plugin, load_args, load_kwargs):
            self.load_times[plugin_spec.name] = {"start": time.time()}
            
        def on_load_after(self, plugin_spec, plugin, load_result):
            if plugin_spec.name in self.load_times:
                start = self.load_times[plugin_spec.name]["start"]
                self.load_times[plugin_spec.name]["duration"] = time.time() - start
                
        def on_load_exception(self, plugin_spec, plugin, exception):
            self.error_count += 1
            
        def get_metrics(self):
            return {
                "load_times": self.load_times,
                "error_count": self.error_count,
                "total_plugins": len(self.load_times),
                "avg_load_time": sum(data.get("duration", 0) for data in self.load_times.values()) / len(self.load_times) if self.load_times else 0
            }

Dependency Injection Listener
~~~~~~~~~~~~~~~~~~~~~~~~~~

A listener that injects dependencies into plugins:

.. code-block:: python

    from plux import PluginLifecycleListener
    
    class DependencyInjectionListener(PluginLifecycleListener):
        def __init__(self, dependencies):
            self.dependencies = dependencies
            
        def on_init_after(self, plugin_spec, plugin):
            # Inject dependencies into the plugin
            if hasattr(plugin, "set_dependencies"):
                plugin.set_dependencies(self.dependencies)
            
            # Or set attributes directly
            for name, dependency in self.dependencies.items():
                if hasattr(plugin, name) and getattr(plugin, name) is None:
                    setattr(plugin, name, dependency)

Advanced Usage: Modifying the Plugin Lifecycle
-------------------------------------------

Lifecycle listeners can also modify the plugin lifecycle by raising exceptions:

.. code-block:: python

    from plux import PluginLifecycleListener, PluginDisabled
    
    class FeatureFlagListener(PluginLifecycleListener):
        def __init__(self, feature_flags):
            self.feature_flags = feature_flags
            
        def on_resolve_after(self, plugin_spec):
            # Check if this plugin is enabled by feature flags
            feature_name = f"plugin.{plugin_spec.namespace}.{plugin_spec.name}"
            if feature_name in self.feature_flags and not self.feature_flags[feature_name]:
                # Disable the plugin
                raise PluginDisabled(
                    plugin_spec.namespace, 
                    plugin_spec.name, 
                    "Disabled by feature flag"
                )

When a ``PluginDisabled`` exception is raised, the ``PluginManager`` will mark the plugin as disabled and skip it during loading.

Best Practices
-----------

Here are some best practices for using lifecycle listeners:

1. **Keep listeners focused**: Each listener should have a specific purpose.

2. **Handle exceptions gracefully**: Especially in the exception handling methods.

3. **Avoid heavy processing**: Listeners are called synchronously during plugin loading, so keep them lightweight.

4. **Use composition**: Combine multiple listeners for different aspects of plugin management.

5. **Log important events**: Use listeners to create a clear audit trail of plugin activity.

Summary
------

The ``PluginLifecycleListener`` interface provides a powerful way to monitor and customize the plugin lifecycle. By implementing the various lifecycle methods, you can track plugin loading, handle errors, collect metrics, and even modify the plugin loading process.