from plugin import PluginManager


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
