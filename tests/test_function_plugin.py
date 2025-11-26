import pytest

from plux import PluginDisabled, PluginManager
from tests.plugins import sample_plugins


def test_load_functional_plugins(sample_plugin_finder):
    manager = PluginManager("namespace_3", finder=sample_plugin_finder)

    plugins = manager.load_all()
    assert len(plugins) == 2

    assert plugins[0].name in ["plugin_3", "plugin_4"]
    assert plugins[1].name in ["plugin_3", "plugin_4"]

    if plugins[0].name == "plugin_3":
        plugin_3 = plugins[0]
        plugin_4 = plugins[1]
    else:
        plugin_3 = plugins[1]
        plugin_4 = plugins[0]

    # function plugins are callable directly
    assert plugin_3() == "foobar"
    assert plugin_4() == "another"


def test_load_functional_plugins_with_load_condition_false(sample_plugin_finder):
    manager = PluginManager("namespace_4", finder=sample_plugin_finder)

    plugins = manager.load_all()
    assert len(plugins) == 0

    with pytest.raises(PluginDisabled) as e:
        manager.load("plugin_5")
    e.match("plugin namespace_4:plugin_5 is disabled, reason: Load condition for plugin was false")

    with pytest.raises(PluginDisabled) as e:
        manager.load("plugin_6")
    e.match("plugin namespace_4:plugin_6 is disabled, reason: Load condition for plugin was false")


def test_load_functional_plugins_with_load_condition_patchd(sample_plugin_finder, monkeypatch):
    monkeypatch.setattr(sample_plugins, "load_condition", lambda: True)

    manager = PluginManager("namespace_4", finder=sample_plugin_finder)

    plugins = manager.load_all()
    assert len(plugins) == 1

    manager.load("plugin_5")

    with pytest.raises(PluginDisabled) as e:
        manager.load("plugin_6")
    e.match("plugin namespace_4:plugin_6 is disabled, reason: Load condition for plugin was false")
