"""
Bindings to integrate plux into setuptools build processes.
"""
import importlib
import json
import logging
import os
import re
import sys
import typing as t

import setuptools
from setuptools.command.egg_info import InfoCommon, write_entries

from plux.core.entrypoint import EntryPointDict, to_entry_point_dict, discover_entry_points
from plux.core.plugin import PluginFinder, PluginSpec
from plux.runtime.metadata import Distribution  # FIXME
from .discovery import ModuleScanningPluginFinder

LOG = logging.getLogger(__name__)


class plugins(InfoCommon, setuptools.Command):
    description = "Discover plux plugins and store them in .egg_info"

    user_options = [
        # TODO
    ]

    egg_info: str

    def initialize_options(self) -> None:
        self.plux_json_path = None

    def finalize_options(self) -> None:
        self.plux_json_path = get_plux_json_path(self.distribution)

    def run(self) -> None:
        self.debug_print("finding plugins...")
        ep = find_plugins(exclude=("tests", "tests.*"))  # TODO: options

        self.debug_print(f"writing discovered plugins into {self.plux_json_path}")
        self.mkpath(os.path.dirname(self.plux_json_path))
        with open(self.plux_json_path, "w") as fd:
            json.dump(ep, fd)

        update_entrypoints(self.distribution, ep)


def find_plugins(where=".", exclude=(), include=("*",)) -> EntryPointDict:
    """
    Utility for setup.py that collects all plugins from the specified path, and creates a dictionary for entry_points.

    For example:

    setup(
        entry_points=find_plugins()
    )
    """

    return discover_entry_points(
        PackagePathPluginFinder(where=where, exclude=exclude, include=include)
    )


def load_plux_entrypoints(cmd, file_name, file_path):
    if not os.path.exists(file_path):
        return

    cmd.debug_print(f"extend entrypoints with plux plugins from {file_path}")
    with open(file_path, "r") as fd:
        ep = json.load(fd)

    update_entrypoints(cmd.distribution, ep)

    # this is kind of a hack, but we cannot rely on load_plux_entrypoints being called before the regular
    # entry_points.txt egg_info.writers plugin to write the updated entry points
    ep_file = "entry_points.txt"
    ep_path = os.path.join(os.path.dirname(file_path), ep_file)
    write_entries(cmd, ep_file, ep_path)


def get_plux_json_path(distribution):
    dirs = distribution.package_dir
    egg_base = (dirs or {}).get("", os.curdir)
    egg_info_dir = _to_filename(_safe_name(distribution.get_name())) + ".egg-info"
    egg_info_dir = os.path.join(egg_base, egg_info_dir)
    return os.path.join(egg_info_dir, "plux.json")


def update_entrypoints(distribution, ep: EntryPointDict):
    if distribution.entry_points is None:
        distribution.entry_points = {}

    # TODO: merge entry point groups
    distribution.entry_points.update(ep)


def load_entry_points(
    where=".", exclude=(), include=("*",), merge: EntryPointDict = None
) -> EntryPointDict:
    """
    Finds plugins and builds and entry point map. This is to be used in a setup.py in the setup call:

    setup(
        entry_points=load_entry_points(exclude=("tests", "tests.*"), merge={
            "my.static.entrypoint": [
                "foo=bar"
            ]
        })
        ...
    )

    This is a hack for installing from source distributions. When running pip install on a source distribution,
    the egg_info directory is always re-built, even though it comes with the source distribution package data. This
    also means the entry points are resolved, and in extent, `find_plugins` is called, which is problematic at this
    point, because find_plugins will scan the code, and that will fail if requirements aren't yet installed,
    which they aren't when running pip install. However, since source distributions package the .egg-info directory,
    we can read the entry points from there instead, acting as sort of a cache.

    :param where: the file path to look for plugins (default, the current working dir)
    :param exclude: the glob patterns to exclude
    :param include: the glob patterns to include
    :param merge: a map of entry points that are always added
    """
    should_read, meta_dir = _should_read_existing_egg_info()
    if should_read:
        print("reading entry points from existing meta dir", meta_dir)
        eps = entry_points_from_egg_info(meta_dir)
    else:
        print("resolving plugin entry points")
        eps = find_plugins(where, exclude, include)

    if merge:
        # TODO: merge the dicts instead of overwriting (will involve de-duplicating entry points)
        eps.update(merge)

    return eps


def entry_points_from_egg_info(egg_info_dir: str) -> EntryPointDict:
    """
    Reads the entry_points.txt from a distribution meta dir (e.g., the .egg-info directory).
    """
    dist = Distribution.at(egg_info_dir)
    return to_entry_point_dict(dist.entry_points)


def _has_entry_points_cache() -> bool:
    egg_info_dir = _get_egg_info_dir()
    if not egg_info_dir:
        return False

    if not os.path.isfile(os.path.join(egg_info_dir, "entry_points.txt")):
        return False

    return True


def _should_read_existing_egg_info() -> t.Tuple[bool, t.Optional[str]]:
    # we want to read the .egg-info dir only if it exists, and if we are creating the egg_info or installing it with
    # pip install -e (which calls 'setup.py develop')

    if not (_is_pip_build_context() or _is_local_build_context()):
        return False, None

    egg_info_dir = _get_egg_info_dir()
    if not egg_info_dir:
        return False, None

    if not os.path.isfile(os.path.join(egg_info_dir, "entry_points.txt")):
        return False, None

    return True, egg_info_dir


def _is_pip_build_context():
    # when pip builds packages or wheels from source distributions, it creates a temporary directory with a marker
    # file that we can use to determine whether we are in such a build context.
    for f in os.listdir(os.getcwd()):
        if f == "pip-delete-this-directory.txt":
            return True

    return False


def _is_local_build_context():
    # when installing with `pip install -e` pip also tries to create a "modern-metadata" (dist-info) directory.
    if "dist_info" in sys.argv:
        try:
            i = sys.argv.index("--egg-base")
        except ValueError:
            return False

        if "pip-modern-metadata" in sys.argv[i + 1]:
            return True

    # it's unfortunately not really distinguishable whether or not a user calls `python setup.py develop` in the
    # project, or calls `pip install -e ..` to install the project from somewhere else.
    if len(sys.argv) > 1 and sys.argv[1] in ["egg_info", "develop"]:
        return True

    return False


def _get_egg_info_dir() -> t.Optional[str]:
    """
    Heuristic to find the .egg-info dir of the current build context.
    """
    cwd = os.getcwd()
    for d in os.listdir(cwd):
        if d.endswith(".egg-info"):
            return os.path.join(cwd, d)

    return None


def get_distribution_from_workdir(workdir: str) -> setuptools.Distribution:
    """
    Reads from the current workdir the available project configs and parses them to create a
    ``setuptools.Distribution`` object, which can later be used to invoke distutils commands.

    :param workdir: the workdir containing the project files
    :return: a distribution object
    """
    config_files = ["pyproject.toml", "setup.cfg"]
    config_files = [os.path.join(workdir, file) for file in config_files]
    config_files = [file for file in config_files if os.path.exists(file)]

    if not config_files:
        raise ValueError(f"no distribution config files found in {workdir}")

    dist = setuptools.Distribution()
    dist.parse_config_files(config_files)
    if os.path.exists("setup.py"):
        # use setup.py script if available
        dist.script_name = os.path.join(workdir, "setup.py")
    else:
        # else use a bogus file (seems to work regardless)
        dist.script_name = config_files[0]

    return dist


def _safe_name(name):
    """Convert an arbitrary string to a standard distribution name. Copied from pkg_resources.

    Any runs of non-alphanumeric/. characters are replaced with a single '-'.
    """
    return re.sub("[^A-Za-z0-9.]+", "-", name)


def _to_filename(name):
    """Convert a project or version name to its filename-escaped form. Copied from pkg_resources.

    Any '-' characters are currently replaced with '_'.
    """
    return name.replace("-", "_")


class PackagePathPluginFinder(PluginFinder):
    """
    Uses setuptools and pkgutil to find and import modules within a given path and then uses a
    ModuleScanningPluginFinder to resolve the available plugins. The constructor has the same signature as
    setuptools.find_packages(where, exclude, include).
    """

    def __init__(self, where=".", exclude=(), include=("*",)) -> None:
        self.where = where
        self.exclude = exclude
        self.include = include

    def find_plugins(self) -> t.List[PluginSpec]:
        collector = ModuleScanningPluginFinder(self.load_modules())
        return collector.find_plugins()

    def load_modules(self):
        for module_name in self.list_module_names():
            try:
                yield importlib.import_module(module_name)
            except Exception as e:
                LOG.error("error importing module %s: %s", module_name, e)

    def list_module_names(self):
        # adapted from https://stackoverflow.com/a/54323162/804840
        from pkgutil import iter_modules

        from setuptools import find_packages

        modules = set()

        for pkg in find_packages(self.where, self.exclude, self.include):
            modules.add(pkg)
            pkgpath = self.where + os.sep + pkg.replace(".", os.sep)
            for info in iter_modules([pkgpath]):
                if not info.ispkg:
                    modules.add(pkg + "." + info.name)

        return modules
