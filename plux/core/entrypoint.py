import inspect
import typing as t
from collections import defaultdict

from .plugin import PluginFinder, PluginSpec


class EntryPoint(t.NamedTuple):
    name: str
    value: str
    group: str


EntryPointDict = t.Dict[str, t.List[str]]


def discover_entry_points(finder: PluginFinder) -> EntryPointDict:
    """
    Creates a dictionary for the entry_points attribute of setuptools' setup(), where keys are
    stevedore plugin namespaces, and values are lists of "name = module:object" pairs.

    :return: an entry_point dictionary
    """
    return to_entry_point_dict([spec_to_entry_point(spec) for spec in finder.find_plugins()])


def to_entry_point_dict(eps: t.List[EntryPoint]) -> EntryPointDict:
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
