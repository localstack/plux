"""
Module for our config wrapper. Currently, this only supports ``pyproject.toml`` files but could be extended in the
future to support ``tox.ini``, ``setup.cfg``, etc.
"""
import dataclasses
import os
from importlib.util import find_spec
import typing as t


@dataclasses.dataclass
class PluxConfiguration:
    """
    Configuration object with sane default values.
    """
    exclude: t.List[str] = dataclasses.field(default_factory=list)


def parse_pyproject_toml(path: str | os.PathLike[str]) -> PluxConfiguration:
    """
    Parses a pyproject.toml file and searches for the ``[tool.plux]`` section. It then creates a ``Configuration``
    object from the found values. Uses tomli or tomllib to parse the file.

    :param path: Path to the pyproject.toml file.
    :return: A ``Configuration`` object containing the parsed values.
    :raises FileNotFoundError: If the file does not exist.
    """
    if find_spec("tomllib"):
        from tomllib import load as load_toml
    elif find_spec("tomli"):
        from tomli import load as load_toml
    else:
        raise ImportError("Could not find a TOML parser. Please install either tomllib or tomli.")

    if not os.path.exists(path):
        raise FileNotFoundError(f"No pyproject.toml found at {path}")

    with open(path, "rb") as file:
        pyproject_config = load_toml(file)

    tool_table = pyproject_config.get("tool", {})
    tool_config = tool_table.get("plux", {})

    return PluxConfiguration(**tool_config)
