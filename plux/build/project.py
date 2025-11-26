import os
from pathlib import Path

from plux.build.config import PluxConfiguration, read_plux_config_from_workdir
from plux.build.discovery import PackageFinder, PluginFromPackageFinder
from plux.build.index import PluginIndexBuilder


class Project:
    """
    Abstraction for a python project to hide the details of a build tool from the CLI. A Project provides access to
    the project's configuration, package discovery, and the entrypoint build mechanism.
    """

    workdir: Path
    config: PluxConfiguration

    def __init__(self, workdir: str = None):
        self.workdir = Path(workdir or os.curdir)
        self.config = self.read_static_plux_config()

    def find_entry_point_file(self) -> Path:
        """
        Finds the entry_point.txt file of the current project. In case of setuptools, this may be in the
        ``<package>.egg-info`` directory, in case of hatch, where ``pip install -e .`` has become the standard, the
        entrypoints file lives in the ``.dist-info`` directory of the venv.

        :return: A path pointing to the entrypoints file. The file might not exist.
        """
        raise NotImplementedError

    def find_plux_index_file(self) -> Path:
        """
        Returns the plux index file location. This may depend on the build tool, for similar reasons described in
        ``find_entry_point_file``. For example, in setuptools, the plux index file by default is in
        ``.egg-info/plux.json``.

        :return: A path pointing to the plux index file.
        """
        raise NotImplementedError

    def create_package_finder(self) -> PackageFinder:
        """
        Returns a build tool-specific PackageFinder instance that can be used to discover packages to scan for plugins.

        :return: A PackageFinder instance
        """
        raise NotImplementedError

    def build_entrypoints(self):
        """
        Routine to build the entrypoints file using ``EntryPointBuildMode.BUILD_HOOK``. This is called by the CLI
        frontend. It's build tool-specific since we need to hook into the build process that generates the
        ``entry_points.txt``.
        """
        raise NotImplementedError

    def create_plugin_index_builder(self) -> PluginIndexBuilder:
        """
        Returns a PluginIndexBuilder instance that can be used to build the plugin index.

        The default implementation creates a PluginFromPackageFinder instance using ``create_package_finder``.

        :return: A PluginIndexBuilder instance.
        """
        plugin_finder = PluginFromPackageFinder(self.create_package_finder())
        return PluginIndexBuilder(plugin_finder)

    def read_static_plux_config(self) -> PluxConfiguration:
        """
        Reads the static configuration (``pyproject.toml``) from the Project's working directory using
        ``read_read_plux_config_from_workdir``.

        :return: A PluxConfiguration object
        """
        return read_plux_config_from_workdir(str(self.workdir))
