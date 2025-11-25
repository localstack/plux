"""
Buildtool independent utils to discover plugins from the codebase, and write index files.
"""

import configparser
import inspect
import json
import logging
import sys
import typing as t
from types import ModuleType

from plux import PluginFinder, PluginSpecResolver, PluginSpec
from plux.core.entrypoint import discover_entry_points, EntryPointDict

if t.TYPE_CHECKING:
    from _typeshed import SupportsWrite

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


class PluginIndexBuilder:
    """
    Builds an index file containing all discovered plugins. The index file can be written to stdout, or to a file.
    The writer supports two formats: json and ini.
    """

    def __init__(
        self,
        plugin_finder: PluginFinder,
        output_format: t.Literal["json", "ini"] = "json",
    ):
        self.plugin_finder = plugin_finder
        self.output_format = output_format

    def write(self, fp: "SupportsWrite[str]" = sys.stdout) -> EntryPointDict:
        """
        Discover entry points using the configured ``PluginFinder``, and write the entry points into a file.

        :param fp: The file-like object to write to.
        :return: The discovered entry points that were written into the file.
        """
        ep = discover_entry_points(self.plugin_finder)

        # sort entrypoints alphabetically in each group first
        for group in ep:
            ep[group].sort()

        if self.output_format == "json":
            json.dump(ep, fp, sort_keys=True, indent=2)
        elif self.output_format == "ini":
            cfg = configparser.ConfigParser()
            cfg.read_dict(self.convert_to_nested_entry_point_dict(ep))
            cfg.write(fp)
        else:
            raise ValueError(f"unknown plugin index output format {self.output_format}")

        return ep

    @staticmethod
    def convert_to_nested_entry_point_dict(ep: EntryPointDict) -> dict[str, dict[str, str]]:
        """
        Converts and ``EntryPointDict`` to a nested dict, where the keys are the section names and values are
        dictionaries. Each dictionary maps entry point names to their values. It also sorts the output alphabetically.

        Example:
            Input EntryPointDict:
            {
                'console_scripts': ['app=module:main', 'tool=module:cli'],
                'plux.plugins': ['plugin1=pkg.module:Plugin1']
            }

            Output nested dict:
            {
                'console_scripts': {
                    'app': 'module:main',
                    'tool': 'module:cli'
                },
                'plux.plugins': {
                    'plugin1': 'pkg.module:Plugin1'
                }
            }
        """
        result = {}
        for section_name in sorted(ep.keys()):
            result[section_name] = {}
            for entry_point in sorted(ep[section_name]):
                name, value = entry_point.split("=")
                result[section_name][name] = value
        return result
