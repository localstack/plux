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


def _call_safe(func: t.Callable, args: t.Tuple, exception_message: str):
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
        raise
    except Exception as e:
        if LOG.isEnabledFor(logging.DEBUG):
            LOG.exception(exception_message)
        else:
            LOG.error("%s: %s", exception_message, e)


class PluginLifecycleNotifierMixin:
    """
    Mixin that provides functions to dispatch calls to a PluginLifecycleListener in a safe way.
    """

    listeners: t.List[PluginLifecycleListener]

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
    load_value: t.Any = None

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

        :return: the importlib.metadata.Distribution object
        """
        return resolve_distribution_information(self.plugin_spec)


class PluginManager(PluginLifecycleNotifierMixin, t.Generic[P]):
    """
    Manages Plugins within a namespace discovered by a PluginFinder. The default mechanism is to resolve plugins from
    entry points using a ImportlibPluginFinder.

    A Plugin that is managed by a PluginManager can be in three states:
        * resolved: the entrypoint pointing to the PluginSpec was imported and the PluginSpec instance was created
        * init: the PluginFactory of the PluginSpec was successfully invoked
        * loaded: the load method of the Plugin was successfully invoked

    Internally, the PluginManager uses PluginContainer instances to keep the state of Plugin instances.
    """

    namespace: str

    load_args: t.Union[t.List, t.Tuple]
    load_kwargs: t.Dict[str, t.Any]
    listeners: t.List[PluginLifecycleListener]
    filters: t.List[PluginFilter]

    def __init__(
        self,
        namespace: str,
        load_args: t.Union[t.List, t.Tuple] = None,
        load_kwargs: t.Dict = None,
        listener: t.Union[PluginLifecycleListener, t.Iterable[PluginLifecycleListener]] = None,
        finder: PluginFinder = None,
        filters: t.List[PluginFilter] = None,
    ):
        """
        Create a new PluginManager.

        :param namespace: the namespace (entry point group) that will be managed
        :param load_args: positional arguments passed to ``Plugin.load()``
        :param load_kwargs: keyword arguments passed to ``Plugin.load()``
        :param listener: plugin lifecycle listeners, can either be a single listener or a list
        :param finder: the plugin finder to be used, by default it uses a ``MetadataPluginFinder`
        :param filters: filters exclude specific plugins. when no filters are provided, a list is created
            and ``global_plugin_filter`` is added to it. filters can later be modified via
            ``plugin_manager.filters``.
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

        self.finder = finder or MetadataPluginFinder(
            self.namespace, self._fire_on_resolve_exception
        )

        self._plugin_index = None
        self._init_mutex = threading.RLock()

    def add_listener(self, listener: PluginLifecycleListener):
        self.listeners.append(listener)

    def load(self, name: str) -> P:
        """
        Loads the Plugin with the given name using the load args and kwargs set in the plugin manager constructor.
        If at any point in the lifecycle the plugin loading fails, the load method will raise the respective exception.

        Load is idempotent, so once the plugin is loaded, load will return the same instance again.
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
            raise PluginException(
                "plugin did not load correctly", namespace=self.namespace, name=name
            )

        return container.plugin

    def load_all(self, propagate_exceptions=False) -> t.List[P]:
        """
        Attempts to load all plugins found in the namespace, and returns those that were loaded successfully. If
        propagate_exception is set to True, then the method will re-raise any errors as soon as it encouters them.
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

    def list_plugin_specs(self) -> t.List[PluginSpec]:
        return [container.plugin_spec for container in self._plugins.values()]

    def list_names(self) -> t.List[str]:
        return [spec.name for spec in self.list_plugin_specs()]

    def list_containers(self) -> t.List[PluginContainer[P]]:
        return list(self._plugins.values())

    def get_container(self, name: str) -> PluginContainer[P]:
        return self._require_plugin(name)

    def exists(self, name: str) -> bool:
        return name in self._plugins

    def is_loaded(self, name: str) -> bool:
        return self._require_plugin(name).is_loaded

    @property
    def _plugins(self) -> t.Dict[str, PluginContainer[P]]:
        if self._plugin_index is None:
            with self._init_mutex:
                if self._plugin_index is None:
                    self._plugin_index = self._init_plugin_index()

        return self._plugin_index

    def _require_plugin(self, name: str) -> PluginContainer[P]:
        if name not in self._plugins:
            raise ValueError("no plugin named %s in namespace %s" % (name, self.namespace))

        return self._plugins[name]

    def _load_plugin(self, container: PluginContainer):
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
        factory = plugin_spec.factory

        # functional decorators can overwrite the spec factory (pointing to the decorator) with a custom factory
        spec = getattr(factory, "__pluginspec__", None)
        if spec:
            factory = spec.factory

        return factory()

    def _init_plugin_index(self) -> t.Dict[str, PluginContainer]:
        return {plugin.name: plugin for plugin in self._import_plugins() if plugin}

    def _import_plugins(self) -> t.Iterable[PluginContainer]:
        for spec in self.finder.find_plugins():
            self._fire_on_resolve_after(spec)

            if spec.namespace != self.namespace:
                continue

            yield self._create_container(spec)

    def _create_container(self, plugin_spec: PluginSpec) -> PluginContainer:
        container = PluginContainer()
        container.lock = threading.RLock()
        container.name = plugin_spec.name
        container.plugin_spec = plugin_spec
        return container
