from plux import PluginSpec
from plux.runtime.metadata import resolve_distribution_information


def test_resolve_distribution_information():
    import pytest

    # fake a plugin spec and use pytest as test object
    fake_plugin_spec = PluginSpec("foo", "bar", pytest.fixture)
    dist = resolve_distribution_information(fake_plugin_spec)
    assert dist.metadata["Name"] == "pytest"
    assert dist.metadata["License"] == "MIT"
