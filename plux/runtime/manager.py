import logging
import threading
import typing as t

from plux.core.plugin import (
    Plugin,
    PluginDisabled,
    PluginException,
    PluginFinder,
    PluginLifecycleListener,
    PluginSpec,
)

from .filter import PluginFilter, global_plugin_filter
from .metadata import Distribution, resolve_distribution_information
from .resolve import MetadataPluginFinder

LOG = logging.getLogger(__name__)

P = t.TypeVar("P", bound=Plugin)


def _call_safe(func: t.Callable, args: tuple, exception_message: str):
    """
    Call the given function with the given arguments, and if it fails, log the given exception_message. If
    logging.DEBUG is set for the logger, then we also log the traceback. An exception is made for any
    ``PluginException``, which should be handled by the caller.

    :param func: function to call
    :param args: arguments to pass
    :param exception_message: message to log on exception
    :return: whatever the func returns
    """
    try:
        return func(*args)
    except PluginException:
        # re-raise PluginExceptions, since they should be handled by the caller
        raise
    except Exception as e:
        if LOG.isEnabledFor(logging.DEBUG):
            LOG.exception(exception_message)
        else:
            LOG.error("%s: %s", exception_message, e)


class PluginLifecycleNotifierMixin:
    """
    Mixin that provides functions to dispatch calls to a ``PluginLifecycleListener`` safely. Safely means that
    exceptions that happen in lifecycle listeners are not re-raised but logged instead. Exception ``PluginException``,
    which are re-raised to allow the listeners to raise exceptions to the ``PluginManager``.

    Note that this is an internal class used primarily to keep the ``PluginManager`` free from dispatching code.
    """

    listeners: list[PluginLifecycleListener]

    def _fire_on_resolve_after(self, plugin_spec):
        for listener in self.listeners:
            _call_safe(
                listener.on_resolve_after,
                (plugin_spec,),  #
                "error while calling on_resolve_after",
            )

    def _fire_on_resolve_exception(self, namespace, entrypoint, exception):
        for listener in self.listeners:
            _call_safe(
                listener.on_resolve_exception,
                (namespace, entrypoint, exception),
                "error while calling on_resolve_exception",
            )

    def _fire_on_init_after(self, plugin_spec, plugin):
        for listener in self.listeners:
            _call_safe(
                listener.on_init_after,
                (
                    plugin_spec,
                    plugin,
                ),  #
                "error while calling on_init_after",
            )

    def _fire_on_init_exception(self, plugin_spec, exception):
        for listener in self.listeners:
            _call_safe(
                listener.on_init_exception,
                (plugin_spec, exception),
                "error while calling on_init_exception",
            )

    def _fire_on_load_before(self, plugin_spec, plugin, load_args, load_kwargs):
        for listener in self.listeners:
            _call_safe(
                listener.on_load_before,
                (plugin_spec, plugin, load_args, load_kwargs),
                "error while calling on_load_before",
            )

    def _fire_on_load_after(self, plugin_spec, plugin, result):
        for listener in self.listeners:
            _call_safe(
                listener.on_load_after,
                (plugin_spec, plugin, result),
                "error while calling on_load_after",
            )

    def _fire_on_load_exception(self, plugin_spec, plugin, exception):
        for listener in self.listeners:
            _call_safe(
                listener.on_load_exception,
                (plugin_spec, plugin, exception),
                "error while calling on_load_exception",
            )


class PluginContainer(t.Generic[P]):
    """
    Object to pass around the plugin state inside a PluginManager.
    """

    name: str
    lock: threading.RLock

    plugin_spec: PluginSpec
    plugin: P = None
    load_value: t.Any | None = None

    is_init: bool = False
    is_loaded: bool = False

    init_error: Exception = None
    load_error: Exception = None

    is_disabled: bool = False
    disabled_reason = str = None

    @property
    def distribution(self) -> Distribution:
        """
        Uses metadata from importlib to resolve the distribution information for this plugin.

        :return: The importlib.metadata.Distribution object
        """
        return resolve_distribution_information(self.plugin_spec)


class PluginManager(PluginLifecycleNotifierMixin, t.Generic[P]):
    """
    Manages Plugins within a namespace discovered by a PluginFinder. The default mechanism is to resolve plugins from
    entry points using an ``ImportlibPluginFinder``.

    A Plugin managed by a PluginManager can be in three states:
        * resolved: the entrypoint pointing to the PluginSpec was imported and the PluginSpec instance was created
        * init: the PluginFactory of the PluginSpec was successfully invoked
        * loaded: the load method of the Plugin was successfully invoked

    Internally, the ``PluginManager`` uses ``PluginContainer`` instances to keep the state of Plugin instances.
    """

    namespace: str

    load_args: list | tuple
    load_kwargs: dict[str, t.Any]
    listeners: list[PluginLifecycleListener]
    filters: list[PluginFilter]

    def __init__(
        self,
        namespace: str,
        load_args: list | tuple = None,
        load_kwargs: dict = None,
        listener: PluginLifecycleListener | t.Iterable[PluginLifecycleListener] = None,
        finder: PluginFinder = None,
        filters: list[PluginFilter] = None,
    ):
        """
        Create a new ``PluginManager`` that can be used to load plugins. The simplest ``PluginManager`` only needs
        the namespace of plugins to load::

            manager = PluginManager("my_namespace")
            my_plugin = manager.load("my_plugin") # <- Plugin instance


        This manager will look up plugins by querying the available entry points in the distribution, and resolve
        the plugin through the entrypoint named "my_plugin" in the group "my_namespace".

        If your plugins take load arguments, you can pass them to the manager constructor::

            class HypercornServerPlugin(Plugin):
                namespace = "servers"
                name = "hypercorn"

                def load(self, host: str, port: int):
                    ...

            manager = PluginManager("servers", load_args=("localhost", 8080))
            server_plugin = manager.load("hypercorn")


        You can react to Plugin lifecycle events by passing a ``PluginLifecycleListener`` to the constructor::

            class MyListener(PluginLifecycleListener):
                def on_load_before(self, plugin_spec: PluginSpec, plugin: Plugin, load_result: t.Any | None = None):
                    LOG.info("Plugin %s was loaded and returned %s", plugin, load_result)

            manager = PluginManager("servers", listener=MyListener())
            manager.load("...") # will log "Plugin ... was loaded and returned None"

        You can also pass a list of listeners to the constructor. You can read more about the different states in the
        documentation of ``PluginLifecycleListener``.

        Suppose you have multiple plugins that are available in your path, but you want to exclude some. You can pass
        custom filters::

            manager = PluginManager("servers", filters=[lambda spec: spec.name == "hypercorn"])
            plugins = manager.load_all() # will load all server plugins except the one named "hypercorn"


        :param namespace: The namespace (entry point group) that will be managed.
        :param load_args: Positional arguments passed to ``Plugin.load()``.
        :param load_kwargs: Keyword arguments passed to ``Plugin.load()``.
        :param listener: Plugin lifecycle listeners. Can either be a single listener or a list.
        :param finder: The plugin finder to be used, by default it uses a ``MetadataPluginFinder`.
        :param filters: Filters exclude specific plugins. When no filters are provided, a list is created and
            ``global_plugin_filter`` is added to it. Filters can later be modified via ``plugin_manager.filters``.
        """
        self.namespace = namespace

        self.load_args = load_args or list()
        self.load_kwargs = load_kwargs or dict()

        if listener:
            if isinstance(listener, (list, set, tuple)):
                self.listeners = list(listener)
            else:
                self.listeners = [listener]
        else:
            self.listeners = []

        if not filters:
            self.filters = [global_plugin_filter]

        self.finder = finder or MetadataPluginFinder(self.namespace, self._fire_on_resolve_exception)

        self._plugin_index = None
        self._init_mutex = threading.RLock()

    def add_listener(self, listener: PluginLifecycleListener):
        """
        Adds a lifecycle listener to the plugin manager. The listener will be notified of plugin lifecycle events.

        This method allows you to add listeners after the PluginManager has been created, which is useful when
        you want to dynamically add listeners based on certain conditions.

        Example::

            manager = PluginManager("my_namespace")

            # Later in the code
            class MyListener(PluginLifecycleListener):
                def on_load_after(self, plugin_spec, plugin, load_result=None):
                    print(f"Plugin {plugin_spec.name} was loaded")

            manager.add_listener(MyListener())

        :param listener: The lifecycle listener to add
        """
        self.listeners.append(listener)

    def load(self, name: str) -> P:
        """
        Loads the Plugin with the given name using the load args and kwargs set in the plugin manager constructor.
        If at any point in the lifecycle the plugin loading fails, the load method will raise the respective exception.

        This method performs several steps:
        1. Checks if the plugin exists in the namespace
        2. Checks if the plugin is disabled
        3. Initializes the plugin if it's not already initialized
        4. Calls the plugin's ``load()`` method if it's not already loaded

        Load is idempotent, so once the plugin is loaded, subsequent calls will return the same instance
        without calling the plugin's ``load()`` method again. This is useful for plugins that perform
        expensive operations during loading.

        Example::

            manager = PluginManager("my_namespace")

            # Basic usage
            plugin = manager.load("my_plugin")

            # With error handling
            try:
                plugin = manager.load("another_plugin")
            except PluginDisabled as e:
                print(f"Plugin is disabled: {e.reason}")
            except ValueError as e:
                print(f"Plugin doesn't exist: {e}")
            except Exception as e:
                print(f"Error loading plugin: {e}")

        :param name: The name of the plugin to load
        :return: The loaded plugin instance
        :raises ValueError: If no plugin with the given name exists in the namespace
        :raises PluginDisabled: If the plugin is disabled (either by a filter or by its `should_load()` method)
        :raises PluginException: If the plugin failed to load for any other reason
        :raises Exception: Any exception that occurred during plugin initialization or loading
        """
        container = self._require_plugin(name)

        if container.is_disabled:
            raise PluginDisabled(container.plugin_spec.namespace, name, container.disabled_reason)

        if not container.is_loaded:
            try:
                self._load_plugin(container)
            except PluginDisabled as e:
                container.is_disabled = True
                container.disabled_reason = e.reason
                raise

        if container.init_error:
            raise container.init_error

        if container.load_error:
            raise container.load_error

        if not container.is_loaded:
            raise PluginException("plugin did not load correctly", namespace=self.namespace, name=name)

        return container.plugin

    def load_all(self, propagate_exceptions=False) -> list[P]:
        """
        Attempts to load all plugins found in the namespace and returns those that were loaded successfully.

        This method iterates through all plugins in the namespace and:
        1. Skips plugins that are already loaded (adding them to the result list)
        2. Attempts to load each plugin that isn't already loaded
        3. Handles exceptions based on the `propagate_exceptions` parameter

        By default, this method silently skips plugins that are disabled or encounter errors during loading,
        logging the errors but continuing with the next plugin. If `propagate_exceptions` is set to True,
        it will re-raise any exceptions as soon as they are encountered, which can be useful for debugging.

        This method is useful when you want to load all available plugins in a namespace without
        having to handle exceptions for each one individually.

        Example::

            manager = PluginManager("my_namespace")

            # Load all plugins, silently skipping any that fail
            plugins = manager.load_all()
            print(f"Successfully loaded {len(plugins)} plugins")

            # Load all plugins, but stop and raise an exception if any fail
            try:
                plugins = manager.load_all(propagate_exceptions=True)
            except Exception as e:
                print(f"Failed to load all plugins: {e}")

        :param propagate_exceptions: If True, re-raises any exceptions encountered during loading
        :return: A list of successfully loaded plugin instances
        """
        plugins = list()

        for name, container in self._plugins.items():
            if container.is_loaded:
                plugins.append(container.plugin)
                continue

            try:
                plugin = self.load(name)
                plugins.append(plugin)
            except PluginDisabled as e:
                LOG.debug("%s", e)
            except Exception as e:
                if propagate_exceptions:
                    raise
                else:
                    LOG.error("exception while loading plugin %s:%s: %s", self.namespace, name, e)

        return plugins

    def list_plugin_specs(self) -> list[PluginSpec]:
        """
        Returns a list of all plugin specifications (PluginSpec objects) in the namespace.

        This method returns all plugin specs that were found by the plugin finder, regardless of
        whether they have been loaded or not. It does not trigger any loading of plugins.

        Example::

            manager = PluginManager("my_namespace")
            specs = manager.list_plugin_specs()
            for spec in specs:
                print(f"Found plugin: {spec.name} from {spec.value}")

        :return: A list of PluginSpec objects
        """
        return [container.plugin_spec for container in self._plugins.values()]

    def list_names(self) -> list[str]:
        """
        Returns a list of all plugin names in the namespace.

        This is a convenience method that extracts just the names from the plugin specs.
        Like `list_plugin_specs()`, this method does not trigger any loading of plugins.

        Example::

            manager = PluginManager("my_namespace")
            names = manager.list_names()
            print(f"Available plugins: {', '.join(names)}")

            # Check if a specific plugin is available
            if "my_plugin" in names:
                plugin = manager.load("my_plugin")

        :return: A list of plugin names (strings)
        """
        return [spec.name for spec in self.list_plugin_specs()]

    def list_containers(self) -> list[PluginContainer[P]]:
        """
        Returns a list of all plugin containers in the namespace.

        Plugin containers are internal objects that hold the state of plugins, including whether they are
        loaded, disabled, or have encountered errors. This method is useful for advanced use cases where
        you need to inspect the detailed state of plugins.

        This method does not trigger any loading of plugins.

        Example::

            manager = PluginManager("my_namespace")
            containers = manager.list_containers()

            # Find all loaded plugins
            loaded_plugins = [c.plugin for c in containers if c.is_loaded]

            # Find all plugins that had errors during initialization
            error_plugins = [c.name for c in containers if c.init_error]

        :return: A list of PluginContainer objects
        """
        return list(self._plugins.values())

    def get_container(self, name: str) -> PluginContainer[P]:
        """
        Returns the plugin container for a specific plugin by name.

        This method provides access to the internal container object that holds the state of a plugin.
        It's useful when you need to inspect the detailed state of a specific plugin, such as checking
        if it has encountered errors during initialization or loading.

        This method does not trigger loading of the plugin, but it will raise a ValueError if the
        plugin doesn't exist in the namespace.

        Example::

            manager = PluginManager("my_namespace")
            try:
                container = manager.get_container("my_plugin")

                # Check if the plugin is loaded
                if container.is_loaded:
                    print(f"Plugin is loaded: {container.plugin}")

                # Check if there were any errors
                if container.init_error:
                    print(f"Plugin had initialization error: {container.init_error}")
                if container.load_error:
                    print(f"Plugin had loading error: {container.load_error}")
            except ValueError:
                print("Plugin not found")

        :param name: The name of the plugin
        :return: The PluginContainer for the specified plugin
        :raises ValueError: If no plugin with the given name exists in the namespace
        """
        return self._require_plugin(name)

    def exists(self, name: str) -> bool:
        """
        Checks if a plugin with the given name exists in the namespace.

        This method is useful for checking if a plugin is available before attempting to load it.
        It does not trigger any loading of plugins but only returns True if the plugin was successfully resolved.

        Example::

            manager = PluginManager("my_namespace")

            # Check if a plugin exists before trying to load it
            if manager.exists("my_plugin"):
                plugin = manager.load("my_plugin")
            else:
                print("Plugin 'my_plugin' is not available")

            # Alternative to using try/except with get_container or load
            if not manager.exists("another_plugin"):
                print("Plugin 'another_plugin' is not available")

        :param name: The name of the plugin to check
        :return: True if the plugin exists, False otherwise
        """
        return name in self._plugins

    def is_loaded(self, name: str) -> bool:
        """
        Checks if a plugin with the given name is loaded.

        A plugin is considered loaded when its ``load()`` method has been successfully called. This method
        is useful for checking the state of a plugin without triggering its loading.

        Note that this method will raise a ValueError if the plugin doesn't exist in the namespace.

        Example::

            manager = PluginManager("my_namespace")

            # Check if a plugin is already loaded
            if manager.exists("my_plugin") and not manager.is_loaded("my_plugin"):
                print("Plugin exists but is not loaded yet")
                plugin = manager.load("my_plugin")

            # Later in the code, check again
            if manager.is_loaded("my_plugin"):
                print("Plugin is now loaded")

        :param name: The name of the plugin to check
        :return: True if the plugin is loaded, False otherwise
        :raises ValueError: If no plugin with the given name exists in the namespace
        """
        return self._require_plugin(name).is_loaded

    @property
    def _plugins(self) -> dict[str, PluginContainer[P]]:
        if self._plugin_index is None:
            with self._init_mutex:
                if self._plugin_index is None:
                    self._plugin_index = self._init_plugin_index()

        return self._plugin_index

    def _require_plugin(self, name: str) -> PluginContainer[P]:
        if name not in self._plugins:
            raise ValueError("no plugin named %s in namespace %s" % (name, self.namespace))

        return self._plugins[name]

    def _load_plugin(self, container: PluginContainer) -> None:
        """
        Implements the core algorithm to load a plugin from a ``PluginSpec`` (contained in the ``PluginContainer``),
        and stores all relevant results, such as the Plugin instance, load result, or any errors into the passed
        ``PluginContainer``.

        The loading algorithm follows these steps:
        1. Checks if any plugin filters would disable the plugin
        2. If not already initialized, instantiates the plugin using the factory from PluginSpec
        3. Checks if the plugin should be loaded by calling its should_load() method
        4. If loading is allowed, calls the plugin's load() method with configured arguments
        5. Updates the container state with load results or any errors that occurred

        Each step is protected by locks and includes appropriate lifecycle event notifications.

        :param container: The ``PluginContainer`` holding the ``PluginSpec`` that defines the ``Plugin`` to load. The
            ``PluginContainer`` instance will also be populated with the load result or any errors that occurred.
        """
        with container.lock:
            plugin_spec = container.plugin_spec

            if self.filters:
                for filter_ in self.filters:
                    if filter_(plugin_spec):
                        raise PluginDisabled(
                            namespace=self.namespace,
                            name=container.plugin_spec.name,
                            reason="A plugin filter disabled this plugin before it was initialized",
                        )

            # instantiate Plugin from spec if necessary
            if not container.is_init:
                try:
                    LOG.debug("instantiating plugin %s", plugin_spec)
                    container.plugin = self._plugin_from_spec(plugin_spec)
                    container.is_init = True
                    self._fire_on_init_after(plugin_spec, container.plugin)
                except PluginDisabled:
                    raise
                except Exception as e:
                    # TODO: maybe we should move these logging blocks to `load_all`, since this is the only instance
                    #  where exceptions messages may get lost.
                    if LOG.isEnabledFor(logging.DEBUG):
                        LOG.exception("error instantiating plugin %s", plugin_spec)

                    self._fire_on_init_exception(plugin_spec, e)
                    container.init_error = e
                    return

            plugin = container.plugin

            if not plugin.should_load():
                raise PluginDisabled(
                    namespace=self.namespace,
                    name=container.plugin_spec.name,
                    reason="Load condition for plugin was false",
                )

            args = self.load_args
            kwargs = self.load_kwargs

            try:
                self._fire_on_load_before(plugin_spec, plugin, args, kwargs)
                LOG.debug("loading plugin %s:%s", self.namespace, plugin_spec.name)
                result = plugin.load(*args, **kwargs)
                self._fire_on_load_after(plugin_spec, plugin, result)
                container.load_value = result
                container.is_loaded = True
            except PluginDisabled:
                raise
            except Exception as e:
                if LOG.isEnabledFor(logging.DEBUG):
                    LOG.exception("error loading plugin %s", plugin_spec)
                self._fire_on_load_exception(plugin_spec, plugin, e)
                container.load_error = e

    def _plugin_from_spec(self, plugin_spec: PluginSpec) -> P:
        """
        Uses the factory from the ``PluginSpec`` to create a new instance of the Plugin. The factory is invoked
        without any arguments, and currently there is no way to customize the instantiation process.

        :param plugin_spec: the plugin spec to instantiate
        :return: a new instance of the Plugin
        """
        factory = plugin_spec.factory

        # functional decorators can overwrite the spec factory (pointing to the decorator) with a custom factory
        spec = getattr(factory, "__pluginspec__", None)
        if spec:
            factory = spec.factory

        return factory()

    def _init_plugin_index(self) -> dict[str, PluginContainer]:
        """
        Initializes the plugin index, which maps plugin names to plugin containers. This method will *resolve* plugins,
        meaning it loads the entry point object reference, thereby importing all its code.

        :return: A mapping of plugin names to plugin containers.
        """
        return {plugin.name: plugin for plugin in self._import_plugins() if plugin}

    def _import_plugins(self) -> t.Iterable[PluginContainer]:
        """
        Finds all ``PluginSpace`` instances in the namespace, creates a container for each spec, and yields them one
        by one. The plugin finder will typically load the entry point which involves importing the module it lives in.
        Note that loading the entry point does not mean loading the plugin (i.e., calling the ``Plugin.load`` method),
        it just means importing the code that defines the plugin.

        :return: Iterable of ``PluginContainer`` instances``.
        """
        for spec in self.finder.find_plugins():
            self._fire_on_resolve_after(spec)

            if spec.namespace != self.namespace:
                continue

            yield self._create_container(spec)

    def _create_container(self, plugin_spec: PluginSpec) -> PluginContainer:
        """
        Factory method to create a ``PluginContainer`` for the given ``PluginSpec``.

        :param plugin_spec: The ``PluginSpec`` to create a container for.
        :return: A new ``PluginContainer`` with the basic information of the plugin spec.
        """
        container = PluginContainer()
        container.lock = threading.RLock()
        container.name = plugin_spec.name
        container.plugin_spec = plugin_spec
        return container
