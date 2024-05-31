import fnmatch
import logging
import typing as t

from plux.core.entrypoint import spec_to_entry_point
from plux.core.plugin import PluginSpec

LOG = logging.getLogger(__name__)


class PluginFilter(t.Protocol):
    def __call__(self, spec: PluginSpec) -> bool:
        """
        Returns True if the plugin should be filtered (disabled), or False otherwise.

        :param spec: the spec to check
        :return: True if the plugin should be disabled
        """
        ...


class PluginSpecMatcher:
    namespace: str = None
    name: str = None
    value: str = None

    def __init__(self, namespace: str = None, name: str = None, value: str = None):
        self.namespace = namespace
        self.name = name
        self.value = value

    def matches(self, spec: PluginSpec) -> bool:
        if self.namespace:
            if not fnmatch.fnmatch(spec.namespace, self.namespace):
                return False

        if self.name:
            if not fnmatch.fnmatch(spec.name, self.name):
                return False

        if self.value:
            ep = spec_to_entry_point(spec)
            if not fnmatch.fnmatch(ep.value, self.value):
                return False

        return True


class MatchingPluginFilter:
    matchers: t.List[PluginSpecMatcher]

    def __init__(self):
        self.matchers = []

    def add_pattern(self, namespace: str = None, name: str = None, value: str = None):
        """
        Adds a pattern of plugins that should be excluded. The patterns use ``fnmatch``. For example::

            # filters all plugins with a namespace "some.namespace.a", "some.namespace.b", ...
            add_pattern(namespace = "some.namespace.*")

            # filters all plugins that come from a specific package tree
            add_pattern(value = "my.package.*")

        Combining parameters will create an `AND` clause.

        :param namespace:
        :param name:
        :param value:
        :return:
        """
        self.matchers.append(PluginSpecMatcher(namespace=namespace, name=name, value=value))

    def __call__(self, spec: PluginSpec) -> bool:
        for matcher in self.matchers:
            if matcher.matches(spec):
                # do not load the plugin if it matches the spec
                LOG.debug("Filter rule %s matched %s", matcher, spec)
                return True
        return False


global_plugin_filter = MatchingPluginFilter()
