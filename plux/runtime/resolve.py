"""Tools to resolve PluginSpec instances from entry points at runtime. The primary mechanism we use to do
that is ``importlib.metadata`` and a bit of caching."""

import logging
import typing as t
from importlib.metadata import EntryPoint

from plux.core.plugin import PluginFinder, PluginSpec, PluginSpecResolver

from .cache import EntryPointsCache
from .metadata import EntryPointsResolver

LOG = logging.getLogger(__name__)


class MetadataPluginFinder(PluginFinder):
    """
    This is a simple implementation of a PluginFinder that uses by default the ``EntryPointsCache`` singleton.
    """

    def __init__(
        self,
        namespace: str,
        on_resolve_exception_callback: t.Callable[[str, t.Any, Exception], None] = None,
        spec_resolver: PluginSpecResolver = None,
        entry_points_resolver: EntryPointsResolver = None,
    ) -> None:
        super().__init__()
        self.namespace = namespace
        self.on_resolve_exception_callback = on_resolve_exception_callback
        self.spec_resolver = spec_resolver or PluginSpecResolver()
        self.entry_points_resolver = entry_points_resolver or EntryPointsCache.instance()

    def find_plugins(self) -> t.List[PluginSpec]:
        specs = []
        finds = self.entry_points_resolver.get_entry_points().get(self.namespace, [])
        for ep in finds:
            spec = self.to_plugin_spec(ep)
            if spec:
                specs.append(spec)
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

            if self.on_resolve_exception_callback:
                self.on_resolve_exception_callback(self.namespace, entry_point, e)
