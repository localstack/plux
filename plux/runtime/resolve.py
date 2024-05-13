"""Tools to resolve PluginSpec instances from entry points at runtime. Currently, stevedore does most of the heavy
lifting for us here (it caches entrypoints and can load them quickly)."""
import logging
import os.path
import time
import typing as t
from importlib.metadata import EntryPoint, EntryPoints, distributions

from plux.core.plugin import PluginFinder, PluginSpec, PluginSpecResolver

LOG = logging.getLogger(__name__)


class MetadataPluginFinder(PluginFinder):
    """
    This is a simple implementation of a PluginFinder that uses ``importlib.metadata`` directly, without caching, to resolve plugins. It also automatically follows `entry_point
    """

    def __init__(
        self,
        namespace: str,
        on_resolve_exception_callback: t.Callable[[str, t.Any, Exception], None] = None,
        spec_resolver: PluginSpecResolver = None,
    ) -> None:
        super().__init__()
        self.namespace = namespace
        self.on_resolve_exception_callback = on_resolve_exception_callback
        self.spec_resolver = spec_resolver or PluginSpecResolver()

    def unique_entry_points(self, group: str) -> t.List[EntryPoint]:
        """
        Resolves the entrypoints using importlib.metadata, and also adds entry points from
        ``entry_points_editable.txt`` created by plux on editable installs.

        :param group: the entrypoint group to filter by
        :return: a list of entry points
        """
        eps = []

        for dist in distributions():
            # this is a distribution that was installed as editable, therefore we follow the link created by plux
            entry_points_path = dist.read_text("entry_points_editable.txt")

            if entry_points_path and os.path.exists(entry_points_path):
                with open(entry_points_path, "r") as fd:
                    editable_eps = EntryPoints._from_text(fd.read())
                    eps.extend(editable_eps)
            else:
                eps.extend(dist.entry_points)

        unique = []
        seen = set()

        for ep in eps:
            if ep.group != group:
                continue
            key = f"{ep.name}={ep.value}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(ep)

        return unique

    def find_plugins(self) -> t.List[PluginSpec]:
        specs = []
        then = time.time()
        finds = self.unique_entry_points(self.namespace)
        print(f"took {time.time() - then:.4f}s to resolve {len(finds)} plugins")
        for ep in finds:
            specs.append(self.to_plugin_spec(ep))
        return specs

    def to_plugin_spec(self, entry_point: EntryPoint) -> PluginSpec:
        """
        Convert a stevedore extension into a PluginSpec by using a spec_resolver.
        """
        try:
            source = entry_point.load()
            return self.spec_resolver.resolve(source)
        except Exception as e:
            if LOG.isEnabledFor(logging.DEBUG):
                LOG.exception(
                    "error resolving PluginSpec for plugin %s.%s", self.namespace, entry_point.name
                )

            self.on_resolve_exception_callback(self.namespace, entry_point, e)


class StevedorePluginFinder(PluginFinder):
    """
    Uses a stevedore.Extension manager to resolve PluginSpec instances from entry points.
    """

    def __init__(
        self,
        namespace: str,
        on_resolve_exception_callback: t.Callable[[str, t.Any, Exception], None] = None,
        spec_resolver: PluginSpecResolver = None,
    ) -> None:
        super().__init__()
        self.namespace = namespace
        self.on_resolve_exception_callback = on_resolve_exception_callback
        self.spec_resolver = spec_resolver or PluginSpecResolver()

    def find_plugins(self) -> t.List[PluginSpec]:
        from stevedore import ExtensionManager
        from stevedore.exception import NoMatches

        manager = ExtensionManager(
            self.namespace,
            invoke_on_load=False,
            on_load_failure_callback=self._on_load_failure_callback,
        )

        # creates for each loadable stevedore extension a PluginSpec
        try:
            return manager.map(self.to_plugin_spec)
        except NoMatches:
            LOG.debug("no extensions found in namespace %s", self.namespace)
            return []

    def to_plugin_spec(self, ext) -> PluginSpec:
        """
        Convert a stevedore extension into a PluginSpec by using a spec_resolver.
        """
        try:
            return self.spec_resolver.resolve(ext.plugin)
        except Exception as e:
            if LOG.isEnabledFor(logging.DEBUG):
                LOG.exception(
                    "error resolving PluginSpec for plugin %s.%s", self.namespace, ext.name
                )

            self.on_resolve_exception_callback(self.namespace, ext.entry_point, e)

    def _on_load_failure_callback(self, _mgr, entrypoint, exception):
        if LOG.isEnabledFor(logging.DEBUG):
            LOG.error("error importing entrypoint %s: %s", entrypoint, exception)
        self.on_resolve_exception_callback(self.namespace, entrypoint, exception)
