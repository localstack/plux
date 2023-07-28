import inspect
from functools import lru_cache
from importlib import metadata
from typing import Mapping, Optional

from .core import PluginSpec


@lru_cache()
def packages_distributions() -> Mapping[str, list[str]]:
    """
    Cache wrapper around metadata.packages_distributions, which returns a mapping of top-level packages to
    their distributions.

    :return: package to distribution mapping
    """
    return metadata.packages_distributions()


def resolve_distribution_information(plugin_spec: PluginSpec) -> Optional[metadata.Distribution]:
    """
    Resolves for a PluginSpec the python distribution package it comes from. Currently, this raises an
    error for plugins that come from a namespace package (i.e., when a package is part of multiple
    distributions).

    :param plugin_spec: the plugin spec to resolve
    :return: the Distribution metadata if it exists
    """
    package = inspect.getmodule(plugin_spec.factory).__name__
    root_package = package.split(".")[0]
    distributions = packages_distributions().get(root_package)
    if not distributions:
        return None
    if len(distributions) > 1:
        raise ValueError("cannot deal with plugins that are part of namespace packages")

    return metadata.distribution(distributions[0])
