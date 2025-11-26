import os

from plux.build.discovery import ModuleScanningPluginFinder
from plux.build.setuptools import PackagePathPluginFinder

from .plugins import sample_plugins


class TestModuleScanningPluginFinder:
    def test_find_plugins(self):
        finder = ModuleScanningPluginFinder(modules=[sample_plugins])

        plugins = finder.find_plugins()
        assert len(plugins) == 7

        plugins = [(spec.namespace, spec.name) for spec in plugins]

        # update when adding plugins to sample_plugins
        assert ("namespace_2", "simple") in plugins
        assert ("namespace_1", "plugin_1") in plugins
        assert ("namespace_1", "plugin_2") in plugins
        assert ("namespace_3", "plugin_3") in plugins
        assert ("namespace_3", "plugin_4") in plugins
        assert ("namespace_4", "plugin_5") in plugins
        assert ("namespace_4", "plugin_6") in plugins


class TestPackagePathPluginFinder:
    def test_find_plugins(self):
        where = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        finder = PackagePathPluginFinder(where=where, include=("tests.plugins",))

        plugins = finder.find_plugins()
        assert len(plugins) == 7

        plugins = [(spec.namespace, spec.name) for spec in plugins]

        # update when adding plugins to sample_plugins
        assert ("namespace_2", "simple") in plugins
        assert ("namespace_1", "plugin_1") in plugins
        assert ("namespace_1", "plugin_2") in plugins
        assert ("namespace_3", "plugin_3") in plugins
        assert ("namespace_3", "plugin_4") in plugins
        assert ("namespace_4", "plugin_5") in plugins
        assert ("namespace_4", "plugin_6") in plugins
