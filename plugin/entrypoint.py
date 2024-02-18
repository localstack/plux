"""
Deprecated bindings, use plux imports instead, but you shouldn't use the internals in the first place.
"""
from plux.build.setuptools import find_plugins
from plux.core.entrypoint import (
    EntryPoint,
    EntryPointDict,
    spec_to_entry_point,
    to_entry_point_dict,
)

__all__ = [
    "find_plugins",
    "spec_to_entry_point",
    "EntryPointDict",
    "EntryPoint",
    "to_entry_point_dict",
]
