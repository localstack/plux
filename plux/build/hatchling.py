"""
Hatchling build backend integration for plux.

This module provides integration with hatchling's build system, including a metadata hook plugin
that enriches project entry-points with data from plux.ini in manual build mode.
"""

import configparser
import logging
import os
import sys
import typing as t
from pathlib import Path

from hatchling.builders.config import BuilderConfig
from hatchling.builders.wheel import WheelBuilder
from hatchling.metadata.plugin.interface import MetadataHookInterface
from hatchling.plugin import hookimpl

from plux.build.config import EntrypointBuildMode, read_plux_config_from_workdir
from plux.build.discovery import PackageFinder, Filter, MatchAllFilter, SimplePackageFinder
from plux.build.project import Project

LOG = logging.getLogger(__name__)


class HatchlingProject(Project):
    def __init__(self, workdir: str = None):
        super().__init__(workdir)

        if self.config.entrypoint_build_mode != EntrypointBuildMode.MANUAL:
            raise NotImplementedError(
                "Hatchling integration currently only works with entrypoint_build_mode=manual"
            )

        # we assume that a wheel will be the source of truth for the packages finally ending up in the distribution.
        # therefore, we care foremost about the wheel configuration. this also builds on the assumption that building
        # the wheel from the local sources, and the sdist, will be the same.
        self.builder = WheelBuilder(workdir)

    @property
    def hatchling_config(self) -> BuilderConfig:
        return self.builder.config

    def create_package_finder(self) -> PackageFinder:
        return HatchlingPackageFinder(
            self.hatchling_config,
            exclude=self.config.exclude,
            include=self.config.include,
        )

    def find_plux_index_file(self) -> Path:
        # TODO: extend as soon as we support EntryPointBuildMode = build-hook
        return Path(self.hatchling_config.root, self.config.entrypoint_static_file)

    def find_entry_point_file(self) -> Path:
        # we assume that `pip install -e .` is used, and therefore the entrypoints file used during local execution
        # will be in the .dist-info metadata directory in the sys path
        metadata_dir = f"{self.builder.artifact_project_id}.dist-info"

        for path in sys.path:
            metadata_path = os.path.join(path, metadata_dir)
            if not os.path.exists(metadata_path):
                continue

            return Path(metadata_path) / "entry_points.txt"

        raise FileNotFoundError(f"No metadata found for {self.builder.artifact_project_id} in sys path")

    def build_entrypoints(self):
        # TODO: currently this just replicates the manual build mode.
        path = os.path.join(os.getcwd(), self.config.entrypoint_static_file)
        print(f"discovering plugins and writing to {path} ...")
        builder = self.create_plugin_index_builder()
        with open(path, "w") as fd:
            builder.write(fd, output_format="ini")


class HatchlingPackageFinder(PackageFinder):
    """
    Uses hatchling's BuilderConfig abstraction to enumerate packages.

    TODO: include/exclude configuration of packages in hatch needs more thorough testing with different scenarios.
    """

    builder_config: BuilderConfig
    exclude: Filter
    include: Filter

    def __init__(
        self,
        builder_config: BuilderConfig,
        exclude: list[str] | None = None,
        include: list[str] | None = None,
    ):
        self.builder_config = builder_config
        self.exclude = Filter(exclude or [])
        self.include = Filter(include) if include else MatchAllFilter()

    def find_packages(self) -> t.Iterable[str]:
        """
        Hatchling-specific algorithm to find packages. Unlike setuptools, hatchling does not provide a package discovery
        and only provides a config, so this implements our own heuristic to detect packages and namespace packages.

        :return: An Iterable of Packages
        """
        # packages in hatch are defined as file system paths, whereas find_packages expects modules
        package_paths = list(self.builder_config.packages)

        # unlike setuptools, hatch does not return all subpackages by default. instead, these are
        # top-level package paths, so we need to recurse and use the ``__init__.py`` heuristic to find
        # packages.
        all_packages = []
        for relative_package_path in package_paths:
            package_name = os.path.basename(relative_package_path)

            package_path = os.path.join(
                self.path, relative_package_path
            )  # build package path within sources root
            if not os.path.isdir(package_path):
                continue

            is_namespace_package = not os.path.exists(os.path.join(package_path, "__init__.py"))
            found_packages = SimplePackageFinder(package_path).find_packages()

            if is_namespace_package:
                # If it's a namespace package, we need to do two things. First, we include it explicitly as a
                # top-level package to the list of found packages. Second, since``SimplePackageFinder`` will not
                # consider it a package, it will only return subpackages, so we need to prepend the namespace package
                # as a namespace to the package names.
                all_packages.append(package_name)
                found_packages = [f"{package_name}.{found_package}" for found_package in found_packages]

            all_packages.extend(found_packages)

        # now do the filtering like the plux PackageFinder API expects
        packages = self.filter_packages(all_packages)

        # de-duplicate and sort
        return sorted(set(packages))

    @property
    def path(self) -> str:
        if not self.builder_config.sources:
            where = self.builder_config.root
        else:
            if self.builder_config.sources[""]:
                where = self.builder_config.sources[""]
            else:
                LOG.warning("plux doesn't know how to resolve multiple sources directories")
                where = self.builder_config.root

        return where

    def filter_packages(self, packages: t.Iterable[str]) -> t.Iterable[str]:
        return [item for item in packages if not self.exclude(item) and self.include(item)]


def _parse_plux_ini(path: str) -> dict[str, dict[str, str]]:
    """Parse a plux.ini file and return entry points as a nested dictionary.

    The parser uses ``delimiters=('=',)`` to ensure that only the equals sign is treated as a delimiter.
    This is critical because plugin names may contain colons, which are the default delimiter in
    configparser along with equals.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"plux.ini file not found at {path}")

    # Use delimiters=('=',) to prevent colons in plugin names from being treated as delimiters
    parser = configparser.ConfigParser(delimiters=("=",))
    parser.read(path)

    # Convert ConfigParser to nested dict format
    result = {}
    for section in parser.sections():
        result[section] = dict(parser.items(section))

    return result


def _merge_entry_points(target: dict, source: dict) -> None:
    """Merge entry points from source into target dictionary.

    For each group in source:
    - If the group doesn't exist in target, it's added
    - If the group exists, entries are merged (source entries overwrite target entries with same name)
    """
    for group, entries in source.items():
        if group not in target:
            target[group] = {}
        target[group].update(entries)


class PluxMetadataHook(MetadataHookInterface):
    """Hatchling metadata hook that enriches entry-points with data from plux.ini.

    This hook only activates when ``entrypoint_build_mode = "manual"`` is set in the ``[tool.plux]``
    section of pyproject.toml. When active, it reads the plux.ini file (default location or as
    specified by ``entrypoint_static_file``) and merges the discovered entry points into the
    project metadata.

    Configuration in consumer projects::

        [tool.plux]
        entrypoint_build_mode = "manual"
        entrypoint_static_file = "plux.ini"  # optional, defaults to "plux.ini"

        [tool.hatch.metadata.hooks.plux]
        # Empty section is sufficient to activate the hook

    The plux.ini file format::

        [entry.point.group]
        entry_name = module.path:object
        another_entry = module.path:AnotherObject

    When parsing plux.ini, the hook uses ``ConfigParser(delimiters=('=',))`` to ensure that only
    the equals sign is treated as a delimiter. This is critical because plugin names may contain
    colons.
    """

    PLUGIN_NAME = "plux"

    def update(self, metadata: dict) -> None:
        """Update project metadata by enriching entry-points with data from plux.ini.

        This method performs the following steps:

        1. Reads the plux configuration from ``[tool.plux]`` in pyproject.toml
        2. Checks if ``entrypoint_build_mode`` is ``"manual"``
        3. If not manual mode, raises an exception
        4. Reads and parses the plux.ini file
        5. Merges the parsed entry points into ``metadata["entry-points"]``

        :param metadata: The project metadata dictionary to update in-place. Entry points are
                       stored in ``metadata["entry-points"]`` as a nested dict where keys are
                       entry point groups and values are dicts of entry name -> value.
        :type metadata: dict
        :raises RuntimeError: If the build mode is not ``"manual"``
        :raises ValueError: If plux.ini has invalid syntax
        """
        # Read plux configuration from pyproject.toml
        try:
            cfg = read_plux_config_from_workdir(self.root)
        except Exception as e:
            # If we can't read config, use defaults and log warning
            LOG.warning(f"Failed to read plux configuration, using defaults: {e}")
            from plux.build.config import PluxConfiguration

            cfg = PluxConfiguration()

        # Only activate hook in manual mode
        if cfg.entrypoint_build_mode != EntrypointBuildMode.MANUAL:
            raise RuntimeError(
                "The Hatchling metadata build hook is currently only supported for "
                "`entrypoint_build_mode=manual`"
            )

        # Construct path to plux.ini
        plux_ini_path = os.path.join(self.root, cfg.entrypoint_static_file)

        # Parse plux.ini
        try:
            entry_points = _parse_plux_ini(plux_ini_path)
        except FileNotFoundError:
            # Log warning but don't fail build - allows incremental adoption
            LOG.warning(
                f"plux.ini not found at {plux_ini_path}. "
                f"In manual mode, you should generate it with: python -m plux entrypoints"
            )
            return
        except configparser.Error as e:
            # Invalid format is a user error - fail the build with clear message
            raise ValueError(
                f"Failed to parse plux.ini at {plux_ini_path}. "
                f"Please check the file format. Error: {e}"
            ) from e

        if not entry_points:
            LOG.info(f"No entry points found in {plux_ini_path}")
            return

        # Initialize entry-points in metadata if not present
        if "entry-points" not in metadata:
            metadata["entry-points"] = {}

        # Merge entry points from plux.ini
        _merge_entry_points(metadata["entry-points"], entry_points)

        LOG.info(
            f"Enriched entry-points from {plux_ini_path}: "
            f"added {sum(len(v) for v in entry_points.values())} entry points "
            f"across {len(entry_points)} groups"
        )

@hookimpl
def hatch_register_metadata_hook():
    """Register the PluxMetadataHook with hatchling.

    This function is called by hatchling's plugin system to discover and register
    the metadata hook. The hook is registered via the entry point::

        [project.entry-points.hatch]
        plux = "plux.build.hatchling"

    :return: The PluxMetadataHook class
    :rtype: type[PluxMetadataHook]
    """
    return PluxMetadataHook
