"""
Module to provide easier high-level access to ``importlib.metadata`` in the context of plugins.
"""

import collections
import inspect
import io
import os
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


from plux.core.entrypoint import EntryPointDict, to_entry_point_dict
from plux.core.plugin import PluginSpec

Distribution = metadata.Distribution


@lru_cache()
def packages_distributions() -> t.Mapping[str, t.List[str]]:
    """
    Cache wrapper around ``metadata.packages_distributions``, which returns a mapping of top-level packages to
    their distributions. This index is created by scanning all ``top_level.txt`` metadata files in the path.

    Unlike ``metadata.packages_distributions``, this implementation will contain a de-duplicated list of
    distribution names per package. With editable installs, ``packages_distributions()`` may return the
    distribution metadata for both the ``.egg-info`` in the linked source directory, and the ``.dist-info``
    in the site-packages directory created by the editable install. Therefore, a distribution name may
    appear twice for the same package, which is unhelpful information, so we deduplicate it here.

    :return: package to distribution mapping
    """
    distributions = dict(metadata_packages_distributions())

    for k in distributions.keys():
        # remove duplicates occurrences of the same distribution name
        distributions[k] = list(set(distributions[k]))

    return distributions


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


def entry_points_from_metadata_path(metadata_path: str) -> EntryPointDict:
    """
    Reads the entry_points.txt from a distribution meta dir (e.g., the .egg-info or .dist-info directory).
    """
    dist = Distribution.at(metadata_path)
    return to_entry_point_dict(dist.entry_points)


def resolve_entry_points(
    distributions: t.Iterable[Distribution] = None,
) -> t.List[metadata.EntryPoint]:
    """
    Resolves all entry points using a combination of ``importlib.metadata``, and also follows entry points
    links in ``entry_points_editable.txt`` created by plux while building editable wheels.

    :return: the list of unique entry points
    """
    entry_points = []
    distributions = distributions or metadata.distributions()

    for dist in distributions:
        # this is a distribution that was installed as editable, therefore we follow the link created
        # by plux during the editable_wheel command
        entry_points_path = dist.read_text("entry_points_editable.txt")

        if entry_points_path and os.path.exists(entry_points_path):
            with open(entry_points_path, "r") as fd:
                editable_eps = parse_entry_points_text(fd.read())
                entry_points.extend(editable_eps)
        else:
            entry_points.extend(dist.entry_points)

    # unique filter but preserving order
    seen = set()
    unique = []
    for ep in entry_points:
        key = (ep.name, ep.value, ep.group)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ep)

    return unique


def build_entry_point_index(
    entry_points: t.Iterable[metadata.EntryPoint],
) -> t.Dict[str, t.List[metadata.EntryPoint]]:
    """
    Organizes the given list of entry points into a dictionary that maps entry point groups to their
    respective entry points, which resembles the data structure of an ``entry_points.txt``.

    :param entry_points:
    :return:
    """
    result = collections.defaultdict(list)
    names = collections.defaultdict(set)  # book-keeping to check duplicates
    for ep in entry_points:
        if ep.name in names[ep.group]:
            continue
        result[ep.group].append(ep)
        names[ep.group].add(ep.name)
    return dict(result)


if sys.version_info >= (3, 10):

    def parse_entry_points_text(text: str) -> t.List[metadata.EntryPoint]:
        """
        Parses the content of an ``entry_points.txt`` into a list of entry point objects.

        :param text: the string to parse
        :return: a list of metadata EntryPoint objects
        """
        return metadata.EntryPoints._from_text(text)

else:

    def parse_entry_points_text(text: str) -> t.List[metadata.EntryPoint]:
        return metadata.EntryPoint._from_text(text)


def serialize_entry_points_text(index: t.Dict[str, t.List[metadata.EntryPoint]]) -> str:
    """
    Serializes an entry point index generated via ``build_entry_point_index`` into a string that can be
    written into an ``entry_point.txt``. Example::

        [console_scripts]
        wheel = wheel.cli:main

        [distutils.commands]
        bdist_egg = setuptools.command.bdist_egg:bdist_egg


    :param index: the index to serialize
    :return: the serialized string
    """

    buffer = io.StringIO()
    groups = sorted(index.keys())
    for group in groups:
        buffer.write(f"[{group}]\n")
        buffer.writelines(f"{ep.name} = {ep.value}\n" for ep in index[group])
        buffer.write("\n")
    return buffer.getvalue()


class EntryPointsResolver:
    """
    Interface for something that builds an entry point index.
    """

    def get_entry_points(self) -> t.Dict[str, t.List[metadata.EntryPoint]]:
        raise NotImplementedError


class MetadataEntryPointsResolver(EntryPointsResolver):
    """
    Implementation that uses regular ``importlib.metadata`` methods to resolve entry points.
    """

    def get_entry_points(self) -> t.Dict[str, t.List[metadata.EntryPoint]]:
        return build_entry_point_index(resolve_entry_points(metadata.distributions()))
