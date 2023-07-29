import abc
import functools
import inspect
from typing import Any, Callable, Dict, List, Tuple, Type, Union


class PluginException(Exception):
    def __init__(self, message, namespace: str = None, name: str = None) -> None:
        super().__init__(message)
        self.namespace = namespace
        self.name = name


class PluginDisabled(PluginException):
    def __init__(self, namespace: str, name: str):
        super(PluginDisabled, self).__init__("plugin %s:%s is disabled" % (namespace, name))
        self.namespace = namespace
        self.name = name


class Plugin(abc.ABC):
    """A generic LocalStack plugin.

    A Plugin's purpose is to be loaded dynamically at runtime and defer code imports into the Plugin::load method.
    Abstract subtypes of plugins (e.g., a LocalstackCliPlugin) may overwrite the load method with concrete call
    arguments that they agree upon with the PluginManager. In other words, a Plugin and a PluginManager for that
    particular Plugin have an informal contracts to use the same argument types when load is invoked.
    """

    namespace: str
    name: str
    requirements: List[str]

    def should_load(self) -> bool:
        return True

    def load(self, *args, **kwargs):
        """
        Called by a PluginLoader when it loads the Plugin.
        """
        return None


PluginType = Type[Plugin]
PluginFactory = Callable[[], Plugin]


class PluginSpec:
    """
    A PluginSpec describes a plugin through a namespace and its unique name within in that namespace, and holds the
    imported code that can instantiate the plugin (a PluginFactory). In the simplest case, the PluginFactory that can
    just be the Plugin's class.

    Internally a PluginSpec is essentially a wrapper around an importlib EntryPoint. An entrypoint is a tuple: (
    "name", "module:object") inside a namespace that can be loaded. The entrypoint object of a Plugin can point to a
    PluginSpec, or a Plugin that defines its own namespace and name, in which case the PluginSpec will be instantiated
    dynamically by, e.g., a PluginSpecResolver.
    """

    namespace: str
    name: str
    factory: PluginFactory

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
        return (
            self.namespace == other.namespace
            and self.name == other.name
            and self.factory == other.factory
        )


class PluginFinder(abc.ABC):
    """
    Basic abstractions to find plugins, either at build time (e.g., using the PackagePathPluginFinder) or at run time
    (e.g., using StevedorePluginFinder that finds plugins from entrypoints)
    """

    def find_plugins(self) -> List[PluginSpec]:
        raise NotImplementedError  # pragma: no cover


class PluginSpecResolver:
    """
    A PluginSpecResolver finds or creates PluginSpec instances from sources, e.g., from analyzing a Plugin class.
    """

    def resolve(self, source: Any) -> PluginSpec:
        """
        Tries to create a PluginSpec from the given source.

        :param source: anything that can produce a PluginSpec (Plugin class, ...)
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
    Listener that can be attached to a PluginManager to react to plugin lifecycle events.
    """

    def on_resolve_exception(self, namespace: str, entrypoint, exception: Exception):
        pass

    def on_resolve_after(self, plugin_spec: PluginSpec):
        pass

    def on_init_exception(self, plugin_spec: PluginSpec, exception: Exception):
        pass

    def on_init_after(self, plugin_spec: PluginSpec, plugin: Plugin):
        pass

    def on_load_before(
        self,
        plugin_spec: PluginSpec,
        plugin: Plugin,
        load_args: Union[List, Tuple],
        load_kwargs: Dict,
    ):
        pass

    def on_load_after(self, plugin_spec: PluginSpec, plugin: Plugin, load_result: Any = None):
        pass

    def on_load_exception(self, plugin_spec: PluginSpec, plugin: Plugin, exception: Exception):
        pass


class FunctionPlugin(Plugin):
    """
    Exposes a function as a Plugin.
    """

    fn: Callable

    def __init__(
        self,
        fn: Callable,
        should_load: Union[bool, Callable[[], bool]] = None,
        load: Callable = None,
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
            if type(self._should_load) == bool:
                return self._should_load
            else:
                return self._should_load()

        return True


def plugin(
    namespace, name=None, should_load: Union[bool, Callable[[], bool]] = None, load: Callable = None
):
    """
    Expose a function as discoverable and loadable FunctionPlugin.

    :param namespace: the plugin namespace
    :param name: the name of the plugin (by default the function name will be used)
    :param should_load: optional either a boolean value or a callable returning a boolean
    :param load: optional load function
    :return: plugin decorator
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
