import logging
import os
import sys
import typing as t
from pathlib import Path

from hatchling.builders.config import BuilderConfig
from hatchling.builders.wheel import WheelBuilder

from plux.build.config import EntrypointBuildMode
from plux.build.discovery import PackageFinder, Filter, MatchAllFilter, SimplePackageFinder
from plux.build.project import Project

LOG = logging.getLogger(__name__)


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


class HatchlingProject(Project):
    def __init__(self, workdir: str = None):
        super().__init__(workdir)

        if self.config.entrypoint_build_mode != EntrypointBuildMode.MANUAL:
            raise NotImplementedError(
                "Hatchling integration currently only works with entrypoint_build_mode=manual"
            )

        # we assume that a wheel will be the source of truth for the packages finally ending up in the distribution.
        # therefore we care foremost about the wheel configuration. this also builds on the assumption that building
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
