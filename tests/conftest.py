import pytest

from plugin.discovery import ModuleScanningPluginFinder
from tests.plugins import sample_plugins


@pytest.fixture
def sample_plugin_finder():
    finder = ModuleScanningPluginFinder(modules=[sample_plugins])
    yield finder
