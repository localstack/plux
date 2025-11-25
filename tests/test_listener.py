import typing as t
from typing import Dict, List, Tuple
from unittest.mock import MagicMock

import pytest

from plux import (
    CompositePluginLifecycleListener,
    Plugin,
    PluginDisabled,
    PluginException,
    PluginFinder,
    PluginLifecycleListener,
    PluginManager,
    PluginSpec,
)


class DummyPlugin(Plugin):
    load_calls: List[Tuple[Tuple, Dict]]

    def __init__(self) -> None:
        super().__init__()
        self.load_calls = list()

    def load(self, *args, **kwargs):
        self.load_calls.append((args, kwargs))


class ShouldNotLoadPlugin(DummyPlugin):
    def should_load(self) -> bool:
        return False


class GoodPlugin(DummyPlugin):
    pass


class _DummyPluginFinder(PluginFinder):
    def __init__(self, specs: List[PluginSpec]):
        self.specs = specs

    def find_plugins(self) -> List[PluginSpec]:
        return self.specs


@pytest.fixture
def dummy_plugin_finder():
    return _DummyPluginFinder(
        [
            PluginSpec("test.plugins.dummy", "plugin1", GoodPlugin),
            PluginSpec("test.plugins.dummy", "plugin2", GoodPlugin),
        ]
    )


class TestListener:
    def test_listeners_called(self, dummy_plugin_finder):
        listener = MagicMock()
        listener.on_resolve_after = MagicMock()
        listener.on_init_exception = MagicMock()
        listener.on_init_after = MagicMock()
        listener.on_load_before = MagicMock()
        listener.on_load_after = MagicMock()
        listener.on_load_exception = MagicMock()

        manager = PluginManager(
            "test.plugins.dummy",
            finder=dummy_plugin_finder,
            listener=CompositePluginLifecycleListener([listener]),
        )

        plugins = manager.load_all()
        assert len(plugins) == 2

        assert listener.on_resolve_after.call_count == 2
        assert listener.on_init_exception.call_count == 0
        assert listener.on_init_after.call_count == 2
        assert listener.on_load_before.call_count == 2
        assert listener.on_load_after.call_count == 2
        assert listener.on_load_exception.call_count == 0

    def test_on_init_after_can_disable_plugin(self, dummy_plugin_finder):
        class _DisableListener(PluginLifecycleListener):
            def on_init_after(self, plugin_spec: PluginSpec, plugin: Plugin):
                if plugin_spec.name == "plugin2":
                    raise PluginDisabled(plugin_spec.namespace, plugin_spec.name, "decided during init")

        manager = PluginManager(
            "test.plugins.dummy",
            finder=dummy_plugin_finder,
            listener=_DisableListener(),
        )

        plugins = manager.load_all()
        assert len(plugins) == 1

        with pytest.raises(PluginDisabled) as e:
            manager.load("plugin2")

        assert e.match("decided during init")

    def test_on_load_before_can_disable_plugin(self, dummy_plugin_finder):
        class _DisableListener(PluginLifecycleListener):
            def on_load_before(self, plugin_spec: PluginSpec, _plugin: Plugin, _load_args, _load_kwargs):
                if plugin_spec.name == "plugin2":
                    raise PluginDisabled(plugin_spec.namespace, plugin_spec.name, "decided during load")

        manager = PluginManager(
            "test.plugins.dummy",
            finder=dummy_plugin_finder,
            listener=_DisableListener(),
        )

        plugins = manager.load_all()
        assert len(plugins) == 1

        with pytest.raises(PluginDisabled) as e:
            manager.load("plugin2")

        assert e.match("decided during load")

    def test_on_after_before_with_error(self, dummy_plugin_finder):
        class _DisableListener(PluginLifecycleListener):
            def on_load_after(self, plugin_spec: PluginSpec, plugin: Plugin, load_result: t.Any = None):
                if plugin_spec.name == "plugin2":
                    raise PluginException("error loading plugin 2")

        manager = PluginManager(
            "test.plugins.dummy",
            finder=dummy_plugin_finder,
            listener=_DisableListener(),
        )

        plugins = manager.load_all()
        assert len(plugins) == 1

        with pytest.raises(PluginException) as e:
            manager.load("plugin2")

        assert e.match("error loading plugin 2")
