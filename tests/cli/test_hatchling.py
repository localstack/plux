"""
These tests are currently running in a completely different way than setuptools. Currently, setuptools is part of the
sys path when running plux from the source repo (setuptools is in the dev extras), but hatchling is not. To make sure
we test plux without setuptools on hatchling projects, we copy the test projects into temporary folders, install a new
venv, and run all necessary commands with subprocess from this process. Unfortunately, this means it's not possible to
easily use the debugger when running these tests.

TODO: as soon as we want to test a build-hook mode, where plux sits in the build system, we need a different way
 to reference the local plux version, since `pip install -e .` doesn't work for build system dependencies.
"""

import os.path
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def isolate_project(tmp_path):
    """
    Creates a factory fixture that copies the given project directory into a temporary directory and prepares it for
    running a plux test (installing a venv, and installing plux with editable install).
    """

    def _isolate(project_name: str) -> Path:
        project = os.path.join(os.path.dirname(__file__), "projects", "hatchling", project_name)
        tmp_dir = tmp_path / f"{project_name}.{str(uuid.uuid4())[-8:]}"
        shutil.copytree(project, tmp_dir)

        prepare_project(tmp_dir)

        return tmp_dir

    yield _isolate


def _find_project_root() -> Path:
    """
    Returns the path of the plux source root from the test file.
    """
    path = Path(__file__)
    while path != path.parent:
        if (path / "pyproject.toml").exists():
            return path
        path = path.parent

    raise ValueError("no project root found")


def prepare_project(project_directory: Path):
    """
    Prepares the project directory for testing by creating a new venv and installing plux with editable install.
    """
    # create a new venv in the project directory (bootstrapped using the python binary running pytest)
    subprocess.check_output([sys.executable, "-m", "venv", ".venv"], cwd=project_directory)

    # install the package into its own venv (using the python binary from the venv)
    python_bin = project_directory / ".venv/bin/python"
    subprocess.check_output([python_bin, "-m", "pip", "install", "-e", "."], cwd=project_directory)

    # overwrite plux with the local version
    plux_root = _find_project_root()
    subprocess.check_output([python_bin, "-m", "pip", "install", "-e", plux_root], cwd=project_directory)


def test_discover_with_ini_output(isolate_project):
    project = isolate_project("manual_build_mode")
    out_path = project / "my_plux.ini"

    python_bin = project / ".venv/bin/python"
    subprocess.check_output(
        [python_bin, "-m", "plux", "--workdir", project, "discover", "--format", "ini", "--output", out_path]
    )

    lines = out_path.read_text().strip().splitlines()
    assert lines == [
        "[plux.test.plugins]",
        "mynestedplugin = test_project.subpkg.plugins:MyNestedPlugin",
        "myplugin = test_project.plugins:MyPlugin",
    ]


def test_discover_with_ini_output_namespace_package(isolate_project):
    project = isolate_project("namespace_package")
    out_path = project / "my_plux.ini"

    python_bin = project / ".venv/bin/python"
    subprocess.check_output(
        [python_bin, "-m", "plux", "--workdir", project, "discover", "--format", "ini", "--output", out_path]
    )

    lines = out_path.read_text().strip().splitlines()
    assert lines == [
        "[plux.test.plugins]",
        "mynestedplugin = test_project.subpkg.plugins:MyNestedPlugin",
        "myplugin = test_project.plugins:MyPlugin",
    ]


def test_entrypoints_manual_build_mode(isolate_project):
    project = isolate_project("namespace_package")
    index_file = project / "plux.ini"

    index_file.unlink(missing_ok=True)

    python_bin = project / ".venv/bin/python"

    subprocess.check_output([python_bin, "-m", "plux", "--workdir", project, "entrypoints"])

    assert index_file.exists()

    lines = index_file.read_text().strip().splitlines()
    assert lines == [
        "[plux.test.plugins]",
        "mynestedplugin = test_project.subpkg.plugins:MyNestedPlugin",
        "myplugin = test_project.plugins:MyPlugin",
    ]
