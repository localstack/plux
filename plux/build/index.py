"""
Code to manage the plux plugin index file. The index file contains all discovered plugins, which later is used to
generate entry points.
"""

import configparser
import json
import sys
import typing as t

from plux.core.plugin import PluginFinder
from plux.core.entrypoint import EntryPointDict, discover_entry_points

if t.TYPE_CHECKING:
    from _typeshed import SupportsWrite


class PluginIndexBuilder:
    """
    Builds an index file containing all discovered plugins. The index file can be written to stdout, or to a file.
    The writer supports two formats: json and ini.
    """

    def __init__(
        self,
        plugin_finder: PluginFinder,
    ):
        self.plugin_finder = plugin_finder

    def write(
        self,
        fp: "SupportsWrite[str]" = sys.stdout,
        output_format: t.Literal["json", "ini"] = "json",
    ) -> EntryPointDict:
        """
        Discover entry points using the configured ``PluginFinder``, and write the entry points into a file.

        :param fp: The file-like object to write to.
        :param output_format: The format to write the entry points in. Can be either "json" or "ini".
        :return: The discovered entry points that were written into the file.
        """
        ep = discover_entry_points(self.plugin_finder)

        # sort entrypoints alphabetically in each group first
        for group in ep:
            ep[group].sort()

        if output_format == "json":
            json.dump(ep, fp, sort_keys=True, indent=2)
        elif output_format == "ini":
            cfg = configparser.ConfigParser()
            cfg.read_dict(self.convert_to_nested_entry_point_dict(ep))
            cfg.write(fp)
        else:
            raise ValueError(f"unknown plugin index output format {output_format}")

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
