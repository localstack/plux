"""
Module for our config wrapper. Currently, this only supports ``pyproject.toml`` files but could be extended in the
future to support ``tox.ini``, ``setup.cfg``, etc.
"""

import dataclasses
import enum
import os
import sys
from importlib.util import find_spec
from typing import Any


class EntrypointBuildMode(enum.Enum):
    """
    The build mode for entrypoints. When ``build-hook`` is used, plux hooks into the build backend's build process using
    various extension points. Currently, we only support setuptools, where plux generates a plugin index and adds it to
    the .egg-info directory, which is later used to generate entry points.

    The alternative is ``manual``, where build hooks are disabled and the user is responsible for generating and
    referencing entry points.
    """

    MANUAL = "manual"
    BUILD_HOOK = "build-hook"


class BuildBackend(enum.Enum):
    """
    The build backend integration to use. Currently, we support setuptools and hatchling. If set to ``auto``, there
    is an algorithm to detect the build backend automatically from the config.
    """

    AUTO = "auto"
    SETUPTOOLS = "setuptools"
    HATCHLING = "hatchling"


@dataclasses.dataclass
class PluxConfiguration:
    """
    Configuration object with sane default values.
    """

    path: str = "."
    """The path to scan for plugins."""

    exclude: list[str] = dataclasses.field(default_factory=list)
    """A list of paths to exclude from scanning."""

    include: list[str] = dataclasses.field(default_factory=list)
    """A list of paths to include in scanning. If it's specified, only the named items will be included. If it's not
    specified, all found items will be included. ``include`` can contain shell style wildcard patterns just like
    ``exclude``."""

    entrypoint_build_mode: EntrypointBuildMode = EntrypointBuildMode.BUILD_HOOK
    """The point in the build process path plugins should be discovered and entrypoints generated."""

    entrypoint_static_file: str = "plux.ini"
    """The name of the entrypoint ini file if entrypoint_build_mode is set to MANUAL."""

    bild_backend: BuildBackend = BuildBackend.AUTO
    """The build backend to use. If set to ``auto``, the build backend will be detected automatically from the config."""

    def merge(
        self,
        path: str = None,
        exclude: list[str] = None,
        include: list[str] = None,
        entrypoint_build_mode: EntrypointBuildMode = None,
        entrypoint_static_file: str = None,
        bild_backend: BuildBackend = None,
    ) -> "PluxConfiguration":
        """
        Merges or overwrites the given values into the current configuration and returns a new configuration object.
        If the passed values are None, they are not changed.
        """
        return PluxConfiguration(
            path=path if path is not None else self.path,
            exclude=list(set((exclude if exclude is not None else []) + self.exclude)),
            include=list(set((include if include is not None else []) + self.include)),
            entrypoint_build_mode=entrypoint_build_mode
            if entrypoint_build_mode is not None
            else self.entrypoint_build_mode,
            entrypoint_static_file=entrypoint_static_file
            if entrypoint_static_file is not None
            else self.entrypoint_static_file,
            bild_backend=bild_backend if bild_backend is not None else self.bild_backend,
        )


def read_plux_config_from_workdir(workdir: str = None) -> PluxConfiguration:
    """
    Reads the plux configuration from the specified workdir. Currently, it only checks for a ``pyproject.toml`` to
    parse. If no pyproject.toml is found, a default configuration is returned.

    :param workdir: The workdir which defaults to the current working directory.
    :return: A plux configuration object
    """
    try:
        return parse_pyproject_toml(workdir or os.getcwd())
    except FileNotFoundError:
        return PluxConfiguration()


def parse_pyproject_toml(path: str | os.PathLike[str]) -> PluxConfiguration:
    """
    Parses a pyproject.toml file and searches for the ``[tool.plux]`` section. It then creates a ``Configuration``
    object from the found values. Uses tomli or tomllib to parse the file.

    :param path: Path to the pyproject.toml file.
    :return: A plux configuration object containing the parsed values.
    :raises FileNotFoundError: If the file does not exist.
    """
    pyproject_config = load_pyproject_toml(path)

    # find the [tool.plux] section
    tool_table = pyproject_config.get("tool", {})
    tool_config = tool_table.get("plux", {})

    # filter out all keys that are not available in the config object
    kwargs = {}
    for key, value in tool_config.items():
        if key not in PluxConfiguration.__annotations__:
            print(f"Warning: ignoring unknown key {key} in [tool.plux] section of {path}", file=sys.stderr)
            continue

        kwargs[key] = value

    # parse entrypoint_build_mode enum
    if mode := kwargs.get("entrypoint_build_mode"):
        # will raise a ValueError exception if the mode is invalid
        kwargs["entrypoint_build_mode"] = EntrypointBuildMode(mode)

    # parse build_backend
    if build_backend := kwargs.get("build_backend"):
        # will raise a ValueError exception if the build backend is invalid
        kwargs["build_backend"] = BuildBackend(build_backend)

    return PluxConfiguration(**kwargs)


def determine_build_backend_from_pyproject_config(pyproject_config: dict[str, Any]) -> BuildBackend | None:
    """
    Determine the build backend to use based on the pyproject.toml configuration.
    """
    build_backend = pyproject_config.get("build-system", {}).get("build-backend", "")
    if build_backend.startswith("setuptools."):
        return BuildBackend.SETUPTOOLS
    if build_backend.startswith("hatchling."):
        return BuildBackend.HATCHLING
    else:
        return None


def load_pyproject_toml(pyproject_file_or_workdir: str | os.PathLike[str] = None) -> dict[str, Any]:
    """
    Loads a pyproject.toml file from the given path or the current working directory. Uses tomli or tomllib to parse.

    :param pyproject_file_or_workdir: Path to the pyproject.toml file or the directory containing it. Defaults to the current working directory.
    :return: The parsed pyproject.toml file as a dictionary.
    """
    if pyproject_file_or_workdir is None:
        pyproject_file_or_workdir = os.getcwd()
    if os.path.isfile(pyproject_file_or_workdir):
        pyproject_file = pyproject_file_or_workdir
    else:
        pyproject_file = os.path.join(pyproject_file_or_workdir, "pyproject.toml")

    if find_spec("tomllib"):
        from tomllib import load as load_toml
    elif find_spec("tomli"):
        from tomli import load as load_toml
    else:
        raise ImportError("Could not find a TOML parser. Please install either tomllib or tomli.")

    # read the file
    if not os.path.exists(pyproject_file):
        raise FileNotFoundError(f"No .toml file found at {pyproject_file}")
    with open(pyproject_file, "rb") as file:
        pyproject_config = load_toml(file)

    return pyproject_config


def determine_build_backend_from_config(workdir: str) -> BuildBackend:
    """
    Algorithm to determine the build backend to use based on the given workdir. First, it checks the pyproject.toml to
    see whether there's a [tool.plux] build_backend =... is configured directly. If not found, it checks the
    ``build-backend`` attribute in the pyproject.toml. Then, as a fallback, it tries to import both setuptools and
    hatchling, and uses the first one that works
    """
    # parse config to get build backend
    plux_config = read_plux_config_from_workdir(workdir)

    if plux_config.bild_backend != BuildBackend.AUTO:
        # first, check if the user configured one
        return plux_config.bild_backend

    # otherwise, try to determine it from the build-backend attribute in the pyproject.toml
    try:
        backend = determine_build_backend_from_pyproject_config(load_pyproject_toml(workdir))
        if backend is not None:
            return backend
    except FileNotFoundError:
        pass

    # if that also fails, just try to import both build backends and return the first one that works
    try:
        import setuptools  # noqa

        return BuildBackend.SETUPTOOLS
    except ImportError:
        pass

    try:
        import hatchling  # noqa

        return BuildBackend.HATCHLING
    except ImportError:
        pass

    raise ValueError("No supported build backend found. Plux needs either setuptools or hatchling to work.")
