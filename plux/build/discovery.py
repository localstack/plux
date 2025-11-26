"""
Buildtool independent utils to discover plugins from the project's source code.
"""

import importlib
import inspect
import logging
import typing as t
from fnmatch import fnmatchcase
from types import ModuleType
import os
import pkgutil

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
