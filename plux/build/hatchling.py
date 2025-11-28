import logging
import os
import typing as t
from pathlib import Path

from hatchling.builders.config import BuilderConfig
from hatchling.builders.wheel import WheelBuilder

from plux.build.config import EntrypointBuildMode
from plux.build.discovery import PackageFinder, Filter, MatchAllFilter, SimplePackageFinder
from plux.build.project import Project

LOG = logging.getLogger(__name__)


def _path_to_module(path):
    """
    Convert a path to a Python module to its module representation.

    Example: plux/core/test -> plux.core.test
    """
    return ".".join(Path(path).with_suffix("").parts)


class HatchlingPackageFinder(PackageFinder):
    """
    Uses hatchling's BuilderConfig abstraction to enumerate packages.

    TODO: this might not be 100% correct and needs more thorough testing with different scenarios.
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

        # FIXME it's unclear whether this will really hold for all configs. most configs we assume will build a wheel,
        #  and any associated package configuration will come from there. so currently we make the wheel build config
        #  the source of truth, but we should revisit this once we know more about hatch build configurations.
        self.builder = WheelBuilder(workdir)

    def create_package_finder(self) -> PackageFinder:
        return HatchlingPackageFinder(
            self.hatchling_config,
            exclude=self.config.exclude,
            include=self.config.include,
        )

    @property
    def hatchling_config(self) -> BuilderConfig:
        return self.builder.config

    def find_plux_index_file(self) -> Path:
        # TODO: extend as soon as we support EntryPointBuildMode = build-hook
        return Path(self.hatchling_config.root, self.config.entrypoint_static_file)

    def find_entry_point_file(self) -> Path:
        # TODO: we'll assume that `pip install -e .` is used, and therefore the entrypoints file will be in the
        #  .dist-info metadata directory
        raise NotImplementedError
