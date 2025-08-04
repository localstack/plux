import os.path
import shutil
import sys

import pytest


@pytest.mark.parametrize("project_name", ["pyproject", "setupcfg"])
def test_entrypoints(project_name):
    if project_name == "pyproject" and sys.version_info < (3, 10):
        pytest.xfail("reading pyproject.toml requires Python 3.10 or above")

    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", project_name)
    os.chdir(project)

    sys.path.append(project)
    try:
        try:
            main(["--workdir", project, "entrypoints"])
        except SystemExit:
            pass
    finally:
        sys.path.remove(project)

    with open(os.path.join(project, "test_project.egg-info", "entry_points.txt"), "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        assert lines == [
            "[plux.test.plugins]",
            "mynestedplugin = mysrc.subpkg.plugins:MyNestedPlugin",
            "myplugin = mysrc.plugins:MyPlugin",
        ]

    # make sure that SOURCES.txt contain no absolute paths
    with open(os.path.join(project, "test_project.egg-info", "SOURCES.txt"), "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        for line in lines:
            assert not line.startswith("/")


@pytest.mark.parametrize("project_name", ["pyproject", "setupcfg"])
def test_entrypoints_exclude(project_name):
    if project_name == "pyproject" and sys.version_info < (3, 10):
        pytest.xfail("reading pyproject.toml requires Python 3.10 or above")

    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", project_name)
    os.chdir(project)

    sys.path.append(project)
    try:
        try:
            main(["--workdir", project, "entrypoints", "--exclude", "*/subpkg*"])
        except SystemExit:
            pass
    finally:
        sys.path.remove(project)

    with open(os.path.join(project, "test_project.egg-info", "entry_points.txt"), "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        assert lines == [
            "[plux.test.plugins]",
            "myplugin = mysrc.plugins:MyPlugin",
        ]

    # make sure that SOURCES.txt contain no absolute paths
    with open(os.path.join(project, "test_project.egg-info", "SOURCES.txt"), "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        for line in lines:
            assert not line.startswith("/")


def test_entrypoints_exclude_from_pyproject_config(tmp_path):
    if sys.version_info < (3, 10):
        pytest.xfail("reading pyproject.toml requires Python 3.10 or above")

    from plux.__main__ import main

    src_project = os.path.join(os.path.dirname(__file__), "projects", "pyproject")
    dest_project = os.path.join(str(tmp_path), "pyproject")

    shutil.copytree(src_project, dest_project)

    pyproject_toml_path = os.path.join(dest_project, "pyproject.toml")

    with open(pyproject_toml_path, "a") as fp:
        fp.write('\n[tool.plux]\nexclude = ["*.subpkg.*"]\n')

    os.chdir(dest_project)

    sys.path.append(dest_project)
    try:
        try:
            main(["--workdir", dest_project, "entrypoints"])
        except SystemExit:
            pass
    finally:
        sys.path.remove(dest_project)

    with open(os.path.join(dest_project, "test_project.egg-info", "entry_points.txt"), "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        assert lines == [
            "[plux.test.plugins]",
            "myplugin = mysrc.plugins:MyPlugin",
        ]

    # make sure that SOURCES.txt contain no absolute paths
    with open(os.path.join(dest_project, "test_project.egg-info", "SOURCES.txt"), "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        for line in lines:
            assert not line.startswith("/")
