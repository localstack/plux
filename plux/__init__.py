# TODO: should start to migrate things from the plugin package to plux
from plugin import __version__ as _version
from plugin.core import (
    FunctionPlugin,
    Plugin,
    PluginDisabled,
    PluginException,
    PluginFinder,
    PluginLifecycleListener,
    PluginSpec,
    PluginType,
    plugin,
)
from plugin.manager import PluginManager, PluginSpecResolver

name = "plux"

__version__ = _version

__all__ = [
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
