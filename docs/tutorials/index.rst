Tutorials
========

This section will contain tutorials on how to use plux for more complex end-to-end scenarios. These tutorials will be added in future updates.

Coming Soon
---------

* **Building a Plugin-based Application**: A tutorial on how to design and build an application that uses plugins for extensibility.

* **Creating a Plugin Ecosystem**: How to create a plugin ecosystem for your application, including guidelines for plugin developers.

* **Advanced Plugin Patterns**: Advanced patterns for plugin development, including dependency injection, plugin composition, and more.

* **Testing Plugins**: Strategies for testing plugins and plugin-based applications.

* **Performance Optimization**: Tips and tricks for optimizing plugin discovery and loading performance.

Placeholder Examples
-----------------

While detailed tutorials are being developed, here are some simple examples to get you started:

Example: Building a Simple Plugin-based CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # app.py
    from plux import Plugin, PluginManager
    import argparse
    
    class CommandPlugin(Plugin):
        namespace = "my.app.commands"
        
        def get_command_name(self):
            return self.name
            
        def add_arguments(self, parser):
            pass
            
        def execute(self, args):
            pass
    
    def main():
        # Create the main parser
        parser = argparse.ArgumentParser(description="My Plugin-based CLI")
        subparsers = parser.add_subparsers(dest="command")
        
        # Load command plugins
        manager = PluginManager("my.app.commands")
        commands = {}
        
        for command in manager.load_all():
            command_name = command.get_command_name()
            command_parser = subparsers.add_parser(command_name)
            command.add_arguments(command_parser)
            commands[command_name] = command
            
        # Parse arguments and execute command
        args = parser.parse_args()
        
        if args.command and args.command in commands:
            commands[args.command].execute(args)
        else:
            parser.print_help()
            
    if __name__ == "__main__":
        main()

Example: Implementing a Command Plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # plugins/hello.py
    from app import CommandPlugin
    
    class HelloCommand(CommandPlugin):
        name = "hello"
        
        def add_arguments(self, parser):
            parser.add_argument("--name", default="World", help="Name to greet")
            
        def execute(self, args):
            print(f"Hello, {args.name}!")

Example: Using Plugin Lifecycle Listeners
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # listeners.py
    from plux import PluginLifecycleListener
    import logging
    
    class LoggingListener(PluginLifecycleListener):
        def __init__(self):
            self.logger = logging.getLogger("plugin.lifecycle")
            
        def on_resolve_after(self, plugin_spec):
            self.logger.info(f"Resolved plugin: {plugin_spec.namespace}:{plugin_spec.name}")
            
        def on_init_after(self, plugin_spec, plugin):
            self.logger.info(f"Initialized plugin: {plugin_spec.name}")
            
        def on_load_after(self, plugin_spec, plugin, load_result):
            self.logger.info(f"Loaded plugin: {plugin_spec.name}")
            
        def on_load_exception(self, plugin_spec, plugin, exception):
            self.logger.error(f"Error loading plugin {plugin_spec.name}: {exception}")
    
    # Using the listener
    manager = PluginManager("my.plugins", listener=LoggingListener())
    plugins = manager.load_all()

Stay Tuned
--------

More detailed tutorials will be added in future updates. In the meantime, check out the User Guide and Reference sections for comprehensive documentation on plux's features and APIs.