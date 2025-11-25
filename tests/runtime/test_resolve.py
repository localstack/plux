from importlib import metadata
from importlib.metadata import EntryPoint
from unittest.mock import MagicMock

import pytest

from plux.runtime.metadata import EntryPointsResolver, build_entry_point_index
from plux.runtime.resolve import MetadataPluginFinder


class DummyEntryPointsResolver(EntryPointsResolver):
    entry_points: dict[str, list[metadata.EntryPoint]]

    def __init__(self, entry_points: list[metadata.EntryPoint]):
        self.entry_points = build_entry_point_index(entry_points)

    def get_entry_points(self) -> dict[str, list[metadata.EntryPoint]]:
        return self.entry_points


@pytest.fixture
def dummy_entry_point_resolver():
    return DummyEntryPointsResolver(
        [
            EntryPoint(
                group="namespace_1",
                name="plugin_1",
                value="tests.plugins.sample_plugins:plugin_spec_1",
            ),
            EntryPoint(
                group="namespace_1",
                name="plugin_2",
                value="tests.plugins.sample_plugins:plugin_spec_2",
            ),
            EntryPoint(
                group="namespace_2",
                name="cannot-be-loaded",
                value="tests.plugins.invalid_module:CannotBeLoadedPlugin",
            ),
            EntryPoint(
                group="namespace_2",
                name="simple",
                value="tests.plugins.sample_plugins:SimplePlugin",
            ),
        ]
    )


def test_resolve_error(dummy_entry_point_resolver):
    mock = MagicMock()
    finder = MetadataPluginFinder(
        "namespace_2",
        on_resolve_exception_callback=mock,
        entry_points_resolver=dummy_entry_point_resolver,
    )
    plugins = finder.find_plugins()
    assert len(plugins) == 1
    assert plugins[0].name == "simple"
    assert mock.call_count == 1
    assert mock.call_args[0][0] == "namespace_2"
    assert mock.call_args[0][1] == EntryPoint(
        "cannot-be-loaded",
        "tests.plugins.invalid_module:CannotBeLoadedPlugin",
        "namespace_2",
    )
    assert str(mock.call_args[0][2]) == "this is an expected exception"
