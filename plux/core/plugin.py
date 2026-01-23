import abc
import functools
import inspect
import typing as t

if t.TYPE_CHECKING:
    from importlib.metadata import EntryPoint


class PluginException(Exception):
    """
    Generic ``PluginException`` that may be raised by the ``PluginManager``.
    """

    def __init__(self, message, namespace: str = None, name: str = None) -> None:
        super().__init__(message)
        self.namespace = namespace
        self.name = name


class PluginDisabled(PluginException):
    """
    Exception that can be raised by a ``Plugin`` or a ``PluginLifecycleListener`` to indicate to the ``PluginManager``
    that this plugin should be disabled. Later calls to ``PluginManager.load(...)``, will then also raise a
    ``PluginDisabled`` exception.
    """

    reason: str

    def __init__(self, namespace: str, name: str, reason: str = None):
        message = f"plugin {namespace}:{name} is disabled"
        if reason:
            message = f"{message}, reason: {reason}"
        super(PluginDisabled, self).__init__(message)
        self.namespace = namespace
        self.name = name
        self.reason = reason


class Plugin(abc.ABC):
    """
    A generic Plugin.

    A Plugin's purpose is to be loaded dynamically at runtime and defer code imports into the ``Plugin.load`` method.
    Abstract subtypes of plugins (e.g., a LocalstackCliPlugin) may overwrite the load method with concrete call
    arguments that they agree upon with the PluginManager. In other words, a Plugin and a PluginManager for that
    particular Plugin have an informal contract to use the same argument types when ``load`` is invoked.

    Note that ``PluginManagers`` will instantiate plugins without constructor args, but can pass arguments to the load
    method.

    Here's an example plugin that lazily imports server code and returns a ``Server`` instance--an example
    abstraction in your application::

        class TwistedServerPlugin(Plugin):
            namespace = "my.server_plugins"
            name = "twisted"

            def load(self, host: str, port: int) -> Server:
                from .twisted import TwistedServer

                return TwistedServer(host, port)

    Later through a plugin manager, this plugin can be loaded as::

        server_name = "twisted"
        pm = PluginManager("my.server_plugins", load_args=("localhost", 8080))
        server = pm.load(server_name)
        server.start()
    """

    namespace: str
    """The namespace of the plugin (e.g., ``cli.commands``). Maps to the ``group`` attribute of an entrypoint."""
    name: str
    """The name of the plugin (e.g., ``my_command``). Maps to the ``name`` attribute of an entrypoint."""
    requirements: list[str]
    """The list of "depends on" clauses of the entry point, which is simply a list of strings and the meaning is up
    to the consumer."""

    def should_load(self) -> bool:
        """
        Whether the ``PluginManager`` should load this plugin. This is called before the ``load`` method. Note that,
        at the point where the ``PluginManager`` calls this function, the plugin has already been *resolved*, which
        means that all ``import`` statements of the module where this plugin lives, have been executed. If you want to
        defer imports, make sure to put them into the ``load`` method.

        By default, this method always returns True.

        :return: True if the plugin should be loaded, False otherwise.
        """
        return True

    def load(self, *args, **kwargs) -> t.Any | None:
        """
        Called by a ``PluginLoader`` when it loads the Plugin. Ideally, any optional imports needed to run the plugin
        are deferred to this method.

        :return: An optional return value of the load method, which is passed to ``PluginManager.load(...)``.
        """
        return None


PluginType = t.Type[Plugin]
PluginFactory = t.Callable[[], Plugin]


class PluginSpec:
    """
    A PluginSpec describes a plugin through a namespace and its unique name within in that namespace, and holds the
    imported code that can instantiate the plugin (a PluginFactory). In the simplest case, the PluginFactory that can
    just be the Plugin's class.

    Internally, a PluginSpec is essentially a wrapper around an importlib EntryPoint. An entrypoint is a tuple:
    ("group", "name", "module:object") inside a namespace that can be loaded. The entrypoint object of a Plugin can
    point to a PluginSpec, or a Plugin that defines its own namespace and name, in which case the PluginSpec will be
    instantiated dynamically by, e.g., a ``PluginSpecResolver``.
    """

    namespace: str
    """The namespace of the plugin (e.g., ``cli.commands``). Maps to the ``group`` attribute of an entrypoint."""
    name: str
    """The name of the plugin (e.g., ``my_command``). Maps to the ``name`` attribute of an entrypoint."""
    factory: PluginFactory
    """The factory that can instantiate the plugin. This is the imported code referenced in the ``value`` attribute of
    the entrypoint."""

    def __init__(
        self,
        namespace: str,
        name: str,
        factory: PluginFactory,
    ) -> None:
        super().__init__()
        self.namespace = namespace
        self.name = name
        self.factory = factory

    def __str__(self):
        return "PluginSpec(%s.%s = %s)" % (self.namespace, self.name, self.factory)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.namespace == other.namespace and self.name == other.name and self.factory == other.factory


class PluginFinder(abc.ABC):
    """
    High-level abstractions to find plugins, either at build time (e.g., using the PackagePathPluginFinder) or at run
    time (e.g., using ``MetadataPluginFinder`` that finds plugins from entrypoints)
    """

    def find_plugins(self) -> list[PluginSpec]:
        """
        Find and return a list of ``PluginSpec`` instances. The implementation will vary drastically depending on the
        context in which the specific ``PluginFinder`` is used.

        :return: A list of ``PluginSpec`` instances.
        """
        raise NotImplementedError  # pragma: no cover


class PluginSpecResolver:
    """
    A PluginSpecResolver finds or creates PluginSpec instances from sources, e.g., from analyzing a Plugin class.
    """

    def resolve(self, source: t.Any) -> PluginSpec:
        """
        Tries to create a PluginSpec from the given source.

        :param source: Anything that can produce a PluginSpec (Plugin class, ...)
        :return: a PluginSpec instance
        """
        if isinstance(source, PluginSpec):
            return source

        if inspect.isclass(source):
            if issubclass(source, Plugin):
                return PluginSpec(source.namespace, source.name, source)

        if inspect.isfunction(source):
            spec = getattr(source, "__pluginspec__", None)
            if spec and isinstance(spec, PluginSpec):
                return spec

        # TODO: add more options to specify plugin specs

        raise ValueError("cannot resolve plugin specification from %s" % source)


class PluginLifecycleListener:  # pragma: no cover
    """
    Listener that can be attached to a ``PluginManager`` to react to plugin lifecycle events.

    A ``Plugin`` managed by a ``PluginManager`` can be in three lifecycle phases:

        * resolved: The entrypoint pointing to the PluginSpec was imported and the PluginSpec instance was created.
          In technical terms, resolution is the process of calling importlib ``EntryPoint.load()`` and creating a
          ``PluginSpec`` instance from the result.
        * init: The ``PluginFactory`` of the ``PluginSpec`` was successfully invoked
        * loaded: The load method of the ``Plugin`` was successfully invoked

    If an exception occurs during any of these steps, the plugin will be in an errored state.

    A lifecycle listener can hook into any of these steps and perform custom actions.
    """

    def on_resolve_exception(self, namespace: str, entrypoint: "EntryPoint", exception: Exception):
        """
        This hook is called when an exception occurs during the resolution of a ``PluginSpec``.  This can happen, for
        example, when the module that holds the plugin raises an import exception, and therefore the ``PluginSpec``
        cannot be created.

        :param namespace: The namespace of the plugin that was being resolved
        :param entrypoint: The importlib EntryPoint that was being used to resolve the plugin
        :param exception: The exception that was raised during resolution
        """
        pass

    def on_resolve_after(self, plugin_spec: PluginSpec):
        """
        This hook is called after the entry point was successfully loaded, and the ``PluginSpec`` instance was created.

        :param plugin_spec: The created ``PluginSpec`` instance.
        """
        pass

    def on_init_exception(self, plugin_spec: PluginSpec, exception: Exception):
        """
        This hook is called when an exception occurs during the construction of a ``Plugin`` instance. A Plugin is
        instantiated by calling the ``PluginFactory`` of the ``PluginSpec``. If that call raises an exception, this
        hook is called.

        :param plugin_spec: The ``PluginSpec`` used to instantiate the plugin..
        :param exception: The exception that was raised during plugin initialization.
        """
        pass

    def on_init_after(self, plugin_spec: PluginSpec, plugin: Plugin):
        """
        This hook is called after a ``Plugin`` instance has been successfully created from a ``PluginSpec``.
        This happens when the ``PluginFactory`` of the ``PluginSpec`` is called and returns a ``Plugin`` instance.

        :param plugin_spec: The ``PluginSpec`` that was used to create the plugin.
        :param plugin: The newly created ``Plugin`` instance.
        """
        pass

    def on_load_before(
        self,
        plugin_spec: PluginSpec,
        plugin: Plugin,
        load_args: list | tuple,
        load_kwargs: dict,
    ):
        """
        This hook is called just before the ``load`` method of a ``Plugin`` is invoked. It provides access to the
        arguments that will be passed to the plugin's load method.

        :param plugin_spec: The ``PluginSpec`` of the plugin being loaded.
        :param plugin: The ``Plugin`` instance that is about to be loaded.
        :param load_args: The positional arguments that will be passed to the plugin's ``load`` method.
        :param load_kwargs: The keyword arguments that will be passed to the plugin's ``load`` method.
        """
        pass

    def on_load_after(self, plugin_spec: PluginSpec, plugin: Plugin, load_result: t.Any | None = None):
        """
        This hook is called after the ``load`` method of a ``Plugin`` has been successfully invoked.
        It provides access to the result returned by the plugin's load method.

        :param plugin_spec: The ``PluginSpec`` of the plugin that was loaded.
        :param plugin: The ``Plugin`` instance that was loaded.
        :param load_result: The value returned by the plugin's ``load`` method, if any.
        """
        pass

    def on_load_exception(self, plugin_spec: PluginSpec, plugin: Plugin, exception: Exception):
        """
        This hook is called when an exception occurs during the loading of a ``Plugin``. This happens when the
        ``load`` method of the plugin raises an exception.

        :param plugin_spec: The ``PluginSpec`` of the plugin that failed to load.
        :param plugin: The ``Plugin`` instance that failed to load.
        :param exception: The exception that was raised during the loading process.
        """
        pass


class CompositePluginLifecycleListener(PluginLifecycleListener):
    """
    A PluginLifecycleListener decorator that dispatches to multiple delegates. This can be used to execute multiple
    listeners into one and pass them as a single listener to a ``PluginManager``.

    TODO: might be a candidate for removal, since a ``PluginManager`` can be configured with multiple listeners.
    """

    listeners: list[PluginLifecycleListener]

    def __init__(self, initial: t.Iterable[PluginLifecycleListener] = None):
        self.listeners = list(initial) if initial else []

    def add_listener(self, listener: PluginLifecycleListener):
        self.listeners.append(listener)

    def on_resolve_exception(self, *args, **kwargs):
        for listener in self.listeners:
            listener.on_resolve_exception(*args, **kwargs)

    def on_resolve_after(self, *args, **kwargs):
        for listener in self.listeners:
            listener.on_resolve_after(*args, **kwargs)

    def on_init_exception(self, *args, **kwargs):
        for listener in self.listeners:
            listener.on_init_exception(*args, **kwargs)

    def on_init_after(self, *args, **kwargs):
        for listener in self.listeners:
            listener.on_init_after(*args, **kwargs)

    def on_load_before(self, *args, **kwargs):
        for listener in self.listeners:
            listener.on_load_before(*args, **kwargs)

    def on_load_after(self, *args, **kwargs):
        for listener in self.listeners:
            listener.on_load_after(*args, **kwargs)

    def on_load_exception(self, *args, **kwargs):
        for listener in self.listeners:
            listener.on_load_exception(*args, **kwargs)


class FunctionPlugin(Plugin):
    """
    This class can be used to create plugins that are not derived from the Plugin class, but are simply functions.
    Plux provides a built-in mechanism for this with the ``@plugin`` decorator. The ``FunctionPlugin`` is primarily an
    internal API, but the class can be extended to customize the behavior of the function plugins, though this is a
    very advanced use case.
    """

    fn: t.Callable

    def __init__(
        self,
        fn: t.Callable,
        should_load: bool | t.Callable[[], bool] = None,
        load: t.Callable = None,
    ) -> None:
        super().__init__()
        self.fn = fn
        self._should_load = should_load
        self._load = load

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    def load(self, *args, **kwargs):
        if self._load:
            return self._load(*args, **kwargs)

    def should_load(self) -> bool:
        if self._should_load is not None:
            if type(self._should_load) is bool:
                return self._should_load
            else:
                return self._should_load()

        return True


def plugin(
    namespace,
    name=None,
    should_load: bool | t.Callable[[], bool] = None,
    load: t.Callable = None,
):
    """
    Expose a function as discoverable and loadable ``Plugin``.

    Here's an example using the ``@plugin`` decorator::

        from plux import plugin

        @plugin(namespace="localstack.configurators")
        def configure_logging(runtime):
            logging.basicConfig(level=runtime.config.loglevel)


        @plugin(namespace="localstack.configurators")
        def configure_somethingelse(runtime):
            # do other stuff with the runtime object
            pass


    :param namespace: The plugin namespace
    :param name: The name of the plugin (by default, the function name will be used)
    :param should_load: Optionally either a boolean value or a callable returning a boolean
    :param load: Optional load function
    :return: Plugin decorator
    """

    def wrapper(fn):
        plugin_name = name or fn.__name__

        # this causes the plugin framework to point the entrypoint to the original function rather than the
        # nested factory function (which would not be resolvable)
        @functools.wraps(fn)
        def factory():
            fn_plugin = FunctionPlugin(fn, should_load=should_load, load=load)
            fn_plugin.namespace = namespace
            fn_plugin.name = plugin_name
            return fn_plugin

        # at discovery-time the factory will point to the method being decorated, and at load-time the factory from
        # this spec instance be used instead of the one being created
        fn.__pluginspec__ = PluginSpec(namespace, plugin_name, factory)

        return fn

    return wrapper
