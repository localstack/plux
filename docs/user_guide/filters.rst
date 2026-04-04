Filters
======

Filters in plux allow you to control which plugins are loaded at runtime. This guide explains how to use filters to include or exclude plugins based on various criteria.

Understanding Plugin Filters
--------------------------

A plugin filter is a callable that takes a ``PluginSpec`` and returns a boolean value:

* ``True`` means the plugin should be filtered out (disabled)
* ``False`` means the plugin should be included (enabled)

Plux provides the ``MatchingPluginFilter`` class, which makes it easy to create filters based on plugin attributes.

Using MatchingPluginFilter
------------------------

The ``MatchingPluginFilter`` class allows you to exclude plugins based on their namespace, name, or entry point value:

.. code-block:: python

    from plux.runtime.filter import MatchingPluginFilter
    
    # Create a filter
    my_filter = MatchingPluginFilter()
    
    # Add exclusion rules
    my_filter.add_exclusion(namespace="my.plugins.experimental")  # Exclude a specific namespace
    my_filter.add_exclusion(name="legacy_plugin")                # Exclude a specific plugin name
    my_filter.add_exclusion(value="my.package.deprecated.*")     # Exclude plugins from a package

Wildcard Patterns
--------------

Filters support wildcard patterns using ``fnmatch``:

.. code-block:: python

    # Exclude all plugins in experimental namespaces
    my_filter.add_exclusion(namespace="*.experimental.*")
    
    # Exclude all plugins with names starting with "test_"
    my_filter.add_exclusion(name="test_*")
    
    # Exclude all plugins from test modules
    my_filter.add_exclusion(value="*.tests.*")

Combining Criteria
---------------

You can combine multiple criteria in a single exclusion rule to create an AND condition:

.. code-block:: python

    # Exclude plugins that match ALL of these criteria
    my_filter.add_exclusion(
        namespace="my.plugins.services",
        name="legacy_*"
    )

This will only exclude plugins that are both in the "my.plugins.services" namespace AND have a name starting with "legacy_".

Applying Filters to PluginManager
------------------------------

To use filters with a ``PluginManager``, pass them when creating the manager:

.. code-block:: python

    from plux import PluginManager
    from plux.runtime.filter import MatchingPluginFilter
    
    # Create a filter
    my_filter = MatchingPluginFilter()
    my_filter.add_exclusion(namespace="my.plugins.experimental.*")
    
    # Create a manager with the filter
    manager = PluginManager(
        namespace="my.plugins.services",
        filters=[my_filter]
    )
    
    # Now when you call load_all(), experimental plugins will be excluded
    plugins = manager.load_all()

You can pass multiple filters to a PluginManager:

.. code-block:: python

    # Create filters for different purposes
    dev_filter = MatchingPluginFilter()
    dev_filter.add_exclusion(namespace="*.production.*")
    
    performance_filter = MatchingPluginFilter()
    performance_filter.add_exclusion(name="*_slow")
    
    # Apply both filters
    manager = PluginManager(
        namespace="my.plugins",
        filters=[dev_filter, performance_filter]
    )

Global Plugin Filter
-----------------

Plux provides a global plugin filter that affects all PluginManagers:

.. code-block:: python

    from plux.runtime.filter import global_plugin_filter
    
    # Configure the global filter
    global_plugin_filter.add_exclusion(namespace="*.deprecated.*")
    global_plugin_filter.add_exclusion(name="legacy_*")
    
    # All PluginManagers will now apply these filters
    manager1 = PluginManager("namespace1")
    manager2 = PluginManager("namespace2")
    
    # Both managers will exclude deprecated plugins

Creating Custom Filters
--------------------

You can create custom filters by implementing the ``PluginFilter`` protocol:

.. code-block:: python

    from plux.runtime.filter import PluginFilter
    from plux.core.plugin import PluginSpec
    
    class EnvironmentFilter:
        def __init__(self, env):
            self.env = env
            
        def __call__(self, spec: PluginSpec) -> bool:
            # Filter out plugins not meant for this environment
            if hasattr(spec.factory, "environments"):
                return self.env not in spec.factory.environments
            return False
    
    # Use the custom filter
    prod_filter = EnvironmentFilter("production")
    manager = PluginManager("my.plugins", filters=[prod_filter])

Filter Execution Order
-------------------

When multiple filters are applied, they are executed in order. If any filter returns ``True`` (meaning the plugin should be disabled), the plugin is excluded without checking the remaining filters.

Best Practices
-----------

Here are some best practices for using filters:

1. **Use specific filters**: Target specific plugins or namespaces rather than using broad patterns.

2. **Document your filters**: Make it clear which plugins are being excluded and why.

3. **Use environment-specific filters**: Create different filters for development, testing, and production environments.

4. **Be cautious with global filters**: The global filter affects all PluginManagers, which might have unintended consequences.

5. **Test your filters**: Verify that the right plugins are being included or excluded.

Summary
------

Filters provide a powerful way to control which plugins are loaded at runtime. The ``MatchingPluginFilter`` class makes it easy to exclude plugins based on their namespace, name, or entry point value. You can apply filters to specific PluginManagers or use the global filter to affect all managers.