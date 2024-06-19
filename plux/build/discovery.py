"""
Buildtool independent utils to discover plugins from the codebase.
"""
import inspect
import logging
from types import ModuleType
import typing as t

from plux import PluginFinder, PluginSpecResolver, PluginSpec

LOG = logging.getLogger(__name__)


class ModuleScanningPluginFinder(PluginFinder):
    """
    A PluginFinder that scans the members of given modules for available PluginSpecs. Each member is evaluated with a
    PluginSpecResolver, and all successful calls resulting in a PluginSpec are collected and returned. This is used
    at build time to scan all modules that the build tool finds, and is an expensive solution that would not be
    practical at runtime.
    """

    def __init__(self, modules: t.Iterable[ModuleType], resolver: PluginSpecResolver = None) -> None:
        super().__init__()
        self.modules = modules
        self.resolver = resolver or PluginSpecResolver()

    def find_plugins(self) -> t.List[PluginSpec]:
        plugins = list()

        for module in self.modules:
            LOG.debug("scanning module %s, file=%s", module.__name__, module.__file__)
            members = inspect.getmembers(module)

            for member in members:
                if type(member) is tuple:
                    try:
                        spec = self.resolver.resolve(member[1])
                        plugins.append(spec)
                        LOG.debug("found plugin spec in %s:%s %s", module.__name__, member[0], spec)
                    except Exception:
                        pass

        return plugins
