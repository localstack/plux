"""
Module to provide easier high-level access to ``importlib.metadata`` in the context of plugins.
"""
import collections
import inspect
import sys
import typing as t
from functools import lru_cache
from importlib import metadata

if sys.version_info >= (3, 10):
    from importlib.metadata import packages_distributions as metadata_packages_distributions
else:

    def metadata_packages_distributions() -> t.Mapping[str, t.List[str]]:
        """Copied from Pyton 3.10 stdlib."""
        pkg_to_dist = collections.defaultdict(list)
        for dist in metadata.distributions():
            for pkg in (dist.read_text("top_level.txt") or "").split():
                pkg_to_dist[pkg].append(dist.metadata["Name"])
        return dict(pkg_to_dist)


from plux.core.plugin import PluginSpec

Distribution = metadata.Distribution


@lru_cache()
def packages_distributions() -> t.Mapping[str, t.List[str]]:
    """
    Cache wrapper around metadata.packages_distributions, which returns a mapping of top-level packages to
    their distributions.

    :return: package to distribution mapping
    """
    return metadata_packages_distributions()


def resolve_distribution_information(plugin_spec: PluginSpec) -> t.Optional[Distribution]:
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
