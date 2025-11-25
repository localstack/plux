import glob
import os.path
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest


@pytest.mark.parametrize("project_name", ["pyproject", "setupcfg"])
def test_entrypoints(project_name):
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


@pytest.mark.parametrize("project_name", ["pyproject", "setupcfg"])
def test_entrypoints_include(project_name):
    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", project_name)
    os.chdir(project)

    sys.path.append(project)
    try:
        try:
            main(["--workdir", project, "entrypoints", "--include", "*/subpkg*"])
        except SystemExit:
            pass
    finally:
        sys.path.remove(project)

    with open(os.path.join(project, "test_project.egg-info", "entry_points.txt"), "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        assert lines == [
            "[plux.test.plugins]",
            "mynestedplugin = mysrc.subpkg.plugins:MyNestedPlugin",
        ]


def test_entrypoints_exclude_from_pyproject_config(tmp_path):
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


def test_entrypoints_with_manual_build_mode():
    from build.__main__ import main as build_main

    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", "manual_build_mode")
    os.chdir(project)

    # remove dist and egg info dir from previous runs
    shutil.rmtree(os.path.join(project, "dist"), ignore_errors=True)
    shutil.rmtree(os.path.join(project, "test_project.egg-info"), ignore_errors=True)

    expected_entry_points = [
        "[plux.test.plugins]",
        "mynestedplugin = mysrc.subpkg.plugins:MyNestedPlugin",
        "myplugin = mysrc.plugins:MyPlugin",
    ]

    sys.path.append(project)
    try:
        try:
            main(["--workdir", project, "entrypoints"])
        except SystemExit:
            pass
    finally:
        sys.path.remove(project)

    # make sure no egg info is created by entrypoints (given manual build mode)
    assert list(glob.glob("*egg-info")) == []

    # instead, it creates a plux.ini
    ini_file = Path(project, "plux.ini")
    assert ini_file.exists()

    lines = ini_file.read_text().strip().splitlines()
    assert lines == expected_entry_points

    # now, build the project, make sure that entrypoints are there
    build_main([])  # python -m build

    # now the egg info should exist (created by setuptools)
    assert list(glob.glob("*egg-info")) == ["test_project.egg-info"]

    # make sure the entry points are in the egg info
    entry_points_txt = Path(project, "test_project.egg-info", "entry_points.txt")
    assert entry_points_txt.exists()

    lines = entry_points_txt.read_text().strip().splitlines()
    assert lines == expected_entry_points

    # also inspect the generated source distribution, make sure the plux ini is created correctly
    with tarfile.open(os.path.join(project, "dist", "test_project-0.1.0.tar.gz")) as tar:
        members = tar.getnames()
        assert "test_project-0.1.0/plux.ini" in members, "plux.ini should be in the archive"
        plux_ini = tar.extractfile("test_project-0.1.0/plux.ini")
        assert plux_ini is not None
        lines = [line.decode().strip() for line in plux_ini.readlines() if line.strip()]
        assert lines == expected_entry_points

    # now inspect the wheel
    wheel_file = glob.glob(os.path.join(project, "dist", "test_project-*.whl"))[0]
    with zipfile.ZipFile(wheel_file, "r") as zip:
        members = zip.namelist()
        # find the entry_points.txt in the .dist-info directory
        entry_points_file = next(m for m in members if m.endswith(".dist-info/entry_points.txt"))
        with zip.open(entry_points_file) as f:
            lines = [line.decode().strip() for line in f.readlines() if line.strip()]
            assert lines == expected_entry_points
