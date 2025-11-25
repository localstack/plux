"""
Module for our config wrapper. Currently, this only supports ``pyproject.toml`` files but could be extended in the
future to support ``tox.ini``, ``setup.cfg``, etc.
"""

import dataclasses
import enum
import os
import sys
from importlib.util import find_spec


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

    def merge(
        self,
        path: str = None,
        exclude: list[str] = None,
        include: list[str] = None,
        entrypoint_build_mode: EntrypointBuildMode = None,
        entrypoint_static_file: str = None,
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
        )


def read_plux_config_from_workdir(workdir: str = None) -> PluxConfiguration:
    """
    Reads the plux configuration from the specified workdir. Currently, it only checks for a ``pyproject.toml`` to
    parse. If no pyproject.toml is found, a default configuration is returned.

    :param workdir: The workdir which defaults to the current working directory.
    :return: A plux configuration object
    """
    try:
        pyproject_file = os.path.join(workdir or os.getcwd(), "pyproject.toml")
        return parse_pyproject_toml(pyproject_file)
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
    if find_spec("tomllib"):
        from tomllib import load as load_toml
    elif find_spec("tomli"):
        from tomli import load as load_toml
    else:
        raise ImportError("Could not find a TOML parser. Please install either tomllib or tomli.")

    # read the file
    if not os.path.exists(path):
        raise FileNotFoundError(f"No pyproject.toml found at {path}")
    with open(path, "rb") as file:
        pyproject_config = load_toml(file)

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

    return PluxConfiguration(**kwargs)
