from plux import __version__ as _version
from plux.core.plugin import (
    FunctionPlugin,
    Plugin,
    PluginDisabled,
    PluginException,
    PluginFinder,
    PluginLifecycleListener,
    PluginSpec,
    PluginSpecResolver,
    PluginType,
    plugin,
)
from plux.runtime.manager import PluginManager

name = "plugin"

__version__ = _version

__all__ = [
    "__version__",
    "FunctionPlugin",
    "Plugin",
    "PluginSpec",
    "PluginType",
    "PluginLifecycleListener",
    "PluginFinder",
    "PluginManager",
    "PluginSpecResolver",
    "PluginException",
    "PluginDisabled",
    "plugin",
]
