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

* **Plugin**: An object that has a namespace a name and exposes ``should_load`` and ``load`` methods
* **PluginManager**: Manages the runtime lifecycle of plugins in a specific namespace

Simple Plugin Example
---------------------

Let's create a simple plugin and load it using a ``PluginManager`` instance.

1. Define a Plugin
~~~~~~~~~~~~~~~~~~

First, create a plugin by subclassing the ``Plugin`` class:

.. code-block:: python

    from plux import Plugin

    class GreetingPlugin(Plugin):
        namespace = "my.plugins.greetings" # <- groups plugins together
        name = "hello" # <- has to be unique within the namespace
        
        def load(self):
            print("loading the plugin ...")

        def greet(self):
            return "Hello World!"

2. Load the Plugin
~~~~~~~~~~~~~~~~~~

Now, let's use the ``PluginManager`` to load our plugin:

.. code-block:: python

    from plux import PluginManager
    
    # Create a plugin manager for our namespace
    manager = PluginManager("my.plugins.greetings")
    
    # Load the plugin by name
    plugin: GreetingPlugin = manager.load("hello")
    
    # The result is the return value of the plugin's load method
    print(plugin.greet())  # Output: Hello, World!


What's special about this is that the ``GreetingPlugin`` and the ``PluginManager`` can live in two separate python distributions.

Function Plugin Example
-----------------------

You can also create plugins from functions using the ``@plugin`` decorator:

.. code-block:: python

    from plux import plugin

    @plugin(namespace="my.greeters")
    def say_hallo():
        print("hallo")

    @plugin(namespace="my.greeters")
    def say_hello():
        print("hello")


This defines two function plugins in the namespace ``my.greeters``, that can be loaded individually by their name, or in bulk.

.. code-block:: python

    # Load the function plugin
    manager = PluginManager("my.configurators")

    doc = dict()

    # load a single plugin
    greeter = manager.load("say_hello")
    greeter() # prints "hello"

    # load all of them
    for greeter in manager.load_all():
        greeter()



Building and Discovering Plugins
--------------------------------

For plux to discover your plugins at runtime, you need to build entry points.
The simplest way is to use the plux CLI:

.. code-block:: bash

    # Generate entry points for your project
    python -m plux entrypoints

This will scan your project for plugins and generate the necessary entry points.
Then, when you run

.. code-block:: bash

    python -m build

to build your distribution, it will contain the generated plugins.

Next Steps
----------

This quickstart guide covered the basics of defining and loading plugins with plux. For more detailed information, check out:

* :doc:`defining_loading_plugins` - Learn more about different ways to define plugins
* :doc:`plugin_manager` - Explore the PluginManager API in depth
* :doc:`build_integration` - Understand how to integrate plux with your build system
