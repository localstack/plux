import os
import textwrap
import uuid

import pytest

from plux.build.config import read_plux_config_from_workdir, BuildBackend, determine_build_backend_from_config


@pytest.fixture
def create_config_workdir(tmp_path):
    """
    Factory fixture that creates a temporary directory with a pyproject.toml file in it using the given string.
    When the factory is invoked, it also changes the working directory to that temp directory.
    """
    cur_dir = os.getcwd()

    def _create(config: str):
        tmp_dir = tmp_path / f"project.{str(uuid.uuid4())[-8:]}"
        tmp_dir.mkdir()
        config_path = tmp_dir / "pyproject.toml"
        config_path.write_text(config)

        os.chdir(tmp_dir)

        return config_path

    yield _create

    os.chdir(cur_dir)


@pytest.mark.parametrize("backend", ["setuptools", "hatchling"])
def test_config_with_explicit_build_backend(backend, create_config_workdir):
    config = textwrap.dedent(f"""
    [tool.plux]
    entrypoint_build_mode = "manual"
    build_backend = "{backend}"
    """)

    create_config_workdir(config)

    cfg = read_plux_config_from_workdir()
    assert cfg.build_backend == BuildBackend(backend)


def test_build_backend_is_read_from_config(create_config_workdir):
    # this test makes sure the build-system.build-backend extraction works
    config = textwrap.dedent("""
    [build-system]
    requires = ["hatchling", "wheel"]
    build-backend = "hatchling.build"
    """)

    create_config_workdir(config)

    cfg = read_plux_config_from_workdir()
    assert cfg.build_backend == BuildBackend.AUTO

    assert determine_build_backend_from_config(os.getcwd()) == BuildBackend.HATCHLING
