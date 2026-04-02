from plux import PluginSpec
from plux.runtime.metadata import resolve_distribution_information


def test_resolve_distribution_information():
    import pytest

    # fake a plugin spec and use pytest as test object
    fake_plugin_spec = PluginSpec("foo", "bar", pytest.fixture)
    dist = resolve_distribution_information(fake_plugin_spec)
    assert dist.metadata["Name"] == "pytest"
    # Support both legacy License field and PEP 639 License-Expression
    license_value = dist.metadata.get("License-Expression") or dist.metadata.get("License")
    assert license_value == "MIT"
