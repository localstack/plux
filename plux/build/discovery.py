"""
Buildtool independent utils to discover plugins from the project's source code.
"""

import importlib
import inspect
import logging
import os
import pkgutil
import typing as t
from fnmatch import fnmatchcase
from pathlib import Path
from types import ModuleType

from plux import PluginFinder, PluginSpecResolver, PluginSpec

LOG = logging.getLogger(__name__)


class PackageFinder:
    """
    Generate a list of Python packages. How these are generated depends on the implementation.

    Why this abstraction? The naive way to find packages is to list all directories with an ``__init__.py`` file.
    However, this approach does not work for distributions that have namespace packages. How do we know whether
    something is a namespace package or just a directory? Typically, the build configuration will tell us. For example,
    setuptools has the following directives for ``pyproject.toml``::

        [tool.setuptools]
        packages = ["mypkg", "mypkg.subpkg1", "mypkg.subpkg2"]

    Or in hatch::

        [tool.hatch.build.targets.wheel]
        packages = ["src/foo"]

    So this abstraction allows us to use the build tool internals to generate a list of packages that we should be
    scanning for plugins.
    """

    def find_packages(self) -> t.Iterable[str]:
        """
        Returns an Iterable of Python packages. Each item is a string-representation of a Python package (for example,
        ``plux.core``, ``myproject.mypackage.utils``, ...)

        :return: An Iterable of Packages
        """
        raise NotImplementedError

    @property
    def path(self) -> str:
        """
        The root file path under which the packages are located.

        :return: A file path
        """
        raise NotImplementedError


class SimplePackageFinder(PackageFinder):
    """
    A package finder that uses a heuristic to find python packages within a given path. It iterates over all
    subdirectories in the path and returns every directory that contains a ``__init__.py`` file. It will include the
    root package in the list of results, so if your tree looks like this::

        mypkg
        ├── __init__.py
        ├── subpkg1
        │   ├── __init__.py
        │   └── nested_subpkg1
        │       └── __init__.py
        └── subpkg2
            └── __init__.py

    and you instantiate SimplePackageFinder("mypkg"), it will return::

        [
            "mypkg",
            "mypkg.subpkg1",
            "mypkg.subpkg2",
            "mypkg.subpkg1.nested_subpkg1,
        ]

    If the root is not a package, say if you have a ``src/`` layout, and you pass "src/mypkg" as ``path`` it will omit
    everything in the preceding path that's not a package.
    """

    DEFAULT_EXCLUDES = "__pycache__"

    def __init__(self, path: str):
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    def find_packages(self) -> t.Iterable[str]:
        """
        Find all Python packages in the given path.

        Returns a list of package names in the format "pkg", "pkg.subpkg", etc.
        """
        path = self.path
        if not os.path.isdir(path):
            return []

        result = []

        # Get the absolute path to handle relative paths correctly
        abs_path = os.path.abspath(path)

        # Check if the root directory is a package
        root_is_package = self._looks_like_package(abs_path)

        # Walk through the directory tree
        for root, dirs, files in os.walk(abs_path):
            # Skip directories that don't look like packages
            if not self._looks_like_package(root):
                continue

            # Determine the base directory for relative path calculation
            # If the root is not a package, we use the root directory itself as the base
            # This ensures we don't include the root directory name in the package names
            if root_is_package:
                base_dir = os.path.dirname(abs_path)
            else:
                base_dir = abs_path

            # Convert the path to a module name
            rel_path = os.path.relpath(root, base_dir)
            if rel_path == ".":
                # If we're at the root and it's a package, use the directory name
                rel_path = os.path.basename(abs_path)

            # skip excludes TODO: should re-use Filter API
            if os.path.basename(rel_path).strip(os.pathsep) in self.DEFAULT_EXCLUDES:
                continue

            # Skip invalid package names (those containing dots in the path)
            if "." in os.path.basename(rel_path):
                continue

            module_name = self._path_to_module(rel_path)
            result.append(module_name)

        # Sort the results for consistent output
        return sorted(result)

    def _looks_like_package(self, path: str) -> bool:
        return os.path.exists(os.path.join(path, "__init__.py"))

    @staticmethod
    def _path_to_module(path: str):
        """
        Convert a path to a Python module to its module representation
        Example: plux/core/test -> plux.core.test
        """
        return ".".join(Path(path).with_suffix("").parts)


class PluginFromPackageFinder(PluginFinder):
    """
    Finds Plugins from packages that are resolved by the given ``PackageFinder``. Under the hood this uses a
    ``ModuleScanningPluginFinder``, which, for each package returned by the ``PackageFinder``, imports the package using
    ``importlib``, and scans the module for plugins.
    """

    finder: PackageFinder

    def __init__(self, finder: PackageFinder):
        self.finder = finder

    def find_plugins(self) -> list[PluginSpec]:
        collector = ModuleScanningPluginFinder(self._load_modules())
        return collector.find_plugins()

    def _load_modules(self) -> t.Generator[ModuleType, None, None]:
        """
        Generator to load all imported modules that are part of the packages returned by the ``PackageFinder``.

        :return: A generator of python modules
        """
        for module_name in self._list_module_names():
            try:
                yield importlib.import_module(module_name)
            except Exception as e:
                LOG.error("error importing module %s: %s", module_name, e)

    def _list_module_names(self) -> set[str]:
        """
        This method creates a set of module names by iterating over the packages detected by the ``PackageFinder``. It
        includes top-level packages, as well as submodules found within those packages.

        :return: A set of strings where each string represents a module name.
        """
        # adapted from https://stackoverflow.com/a/54323162/804840

        modules = set()

        for pkg in self.finder.find_packages():
            modules.add(pkg)
            pkgpath = self.finder.path.rstrip(os.sep) + os.sep + pkg.replace(".", os.sep)
            for info in pkgutil.iter_modules([pkgpath]):
                if not info.ispkg:
                    modules.add(pkg + "." + info.name)

        return modules


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

    def find_plugins(self) -> list[PluginSpec]:
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


class Filter:
    """
    Given a list of patterns, create a callable that will be true only if
    the input matches at least one of the patterns.
    This is from `setuptools.discovery._Filter`
    """

    def __init__(self, patterns: t.Iterable[str]):
        self._patterns = patterns

    def __call__(self, item: str):
        return any(fnmatchcase(item, pat) for pat in self._patterns)


class MatchAllFilter(Filter):
    """
    Filter that is equivalent to ``_Filter(["*"])``.
    """

    def __init__(self):
        super().__init__([])

    def __call__(self, item: str):
        return True
