Quickstart
==========

This guide will help you get started with plux by walking through a simple example of defining and loading a plugin.

Installation
------------

First, install plux using pip:

.. code-block:: bash

    pip install plux

Core Concepts
-------------

Before diving into the code, let's understand the core concepts of plux:

* **Plugin**: An object that exposes ``should_load`` and ``load`` methods
* **PluginSpec**: Describes a plugin with a namespace, name, and factory
* **PluginManager**: Manages the runtime lifecycle of plugins
* **PluginFinder**: Finds plugins at build time or runtime

Simple Plugin Example
---------------------

Let's create a simple plugin and load it using the PluginManager.

1. Define a Plugin
~~~~~~~~~~~~~~~~~~

First, create a plugin by subclassing the ``Plugin`` class:

.. code-block:: python

    from plux import Plugin

    class GreetingPlugin(Plugin):
        namespace = "my.plugins.greetings"
        name = "hello"
        
        def load(self):
            return "Hello, World!"

2. Load the Plugin
~~~~~~~~~~~~~~~~~~

Now, let's use the ``PluginManager`` to load our plugin:

.. code-block:: python

    from plux import PluginManager
    
    # Create a plugin manager for our namespace
    manager = PluginManager("my.plugins.greetings")
    
    # Load the plugin by name
    plugin = manager.load("hello")
    
    # The result is the return value of the plugin's load method
    print(plugin)  # Output: Hello, World!

Function Plugin Example
-----------------------

You can also create plugins from functions using the ``@plugin`` decorator:

.. code-block:: python

    from plux import plugin
    
    @plugin(namespace="my.plugins.greetings")
    def say_goodbye():
        return "Goodbye, World!"
    
    # Load the function plugin
    manager = PluginManager("my.plugins.greetings")
    goodbye_plugin = manager.load("say_goodbye")
    
    # Call the function plugin
    print(goodbye_plugin())  # Output: Goodbye, World!

Building and Discovering Plugins
--------------------------------

For plux to discover your plugins at runtime, you need to build entry points. The simplest way is to use the plux CLI:

.. code-block:: bash

    # Generate entry points for your project
    python -m plux entrypoints

This will scan your project for plugins and generate the necessary entry points.

Next Steps
----------

This quickstart guide covered the basics of defining and loading plugins with plux. For more detailed information, check out:

* :doc:`defining_loading_plugins` - Learn more about different ways to define plugins
* :doc:`plugin_manager` - Explore the PluginManager API in depth
* :doc:`build_integration` - Understand how to integrate plux with your build system