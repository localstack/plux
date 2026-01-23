import inspect
import typing as t
from collections import defaultdict

from .plugin import PluginFinder, PluginSpec


class EntryPoint(t.NamedTuple):
    """
    Lightweight data structure to represent an entry point. You can find out more about the data model here:
    https://packaging.python.org/en/latest/specifications/entry-points/#data-model
    """

    name: str
    """The name identifies this entry point within its group. The precise meaning of this is up to the consumer.
    Within a group, entry point names should be unique."""
    value: str
    """The object reference points to a Python object. It is either in the form ``importable.module``, or
    importable.module:object.attr."""
    group: str
    """The group that an entry point belongs to indicates what sort of object it provides."""


EntryPointDict = dict[str, list[str]]


def discover_entry_points(finder: PluginFinder) -> EntryPointDict:
    """
    Creates a dictionary for the entry_points attribute of setuptools' setup(), where keys are
    stevedore plugin namespaces, and values are lists of "name = module:object" pairs.

    :return: an entry_point dictionary
    """
    return to_entry_point_dict([spec_to_entry_point(spec) for spec in finder.find_plugins()])


def to_entry_point_dict(eps: list[EntryPoint]) -> EntryPointDict:
    """
    Convert the list of EntryPoint objects to a dictionary that maps entry point groups to their respective list of
    ``name=value`` entry points. Each pair is represented as a string.

    :param eps: List of entrypoints to convert
    :return: an entry point dictionary
    :raises ValueError: if there are duplicate entry points in the same group
    """
    result = defaultdict(list)
    names = defaultdict(set)  # book-keeping to check duplicates

    for ep in eps:
        if ep.name in names[ep.group]:
            raise ValueError("Duplicate entry point %s %s" % (ep.group, ep.name))

        result[ep.group].append("%s=%s" % (ep.name, ep.value))
        names[ep.group].add(ep.name)

    return result


def spec_to_entry_point(spec: PluginSpec) -> EntryPoint:
    module = inspect.getmodule(spec.factory).__name__
    name = spec.factory.__name__
    path = f"{module}:{name}"
    return EntryPoint(group=spec.namespace, name=spec.name, value=path)
