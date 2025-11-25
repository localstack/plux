import os.path
import sys

import pytest


@pytest.mark.parametrize("project_name", ["pyproject", "setupcfg"])
def test_discover_with_ini_output(project_name, tmp_path):
    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", project_name)
    os.chdir(project)

    out_path = tmp_path / "plux.ini"

    sys.path.append(project)
    try:
        try:
            main(["--workdir", project, "discover", "--format", "ini", "--output", str(out_path)])
        except SystemExit:
            pass
    finally:
        sys.path.remove(project)

    lines = out_path.read_text().strip().splitlines()
    assert lines == [
        "[plux.test.plugins]",
        "mynestedplugin = mysrc.subpkg.plugins:MyNestedPlugin",
        "myplugin = mysrc.plugins:MyPlugin",
    ]


@pytest.mark.parametrize("project_name", ["pyproject", "setupcfg"])
def test_discover_with_ini_output_exclude(project_name, tmp_path):
    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", project_name)
    os.chdir(project)

    out_path = tmp_path / "plux.ini"

    sys.path.append(project)
    try:
        try:
            main(
                [
                    "--workdir",
                    project,
                    "discover",
                    "--format",
                    "ini",
                    "--output",
                    str(out_path),
                    "--exclude",
                    "*/subpkg*",
                ]
            )
        except SystemExit:
            pass
    finally:
        sys.path.remove(project)

    lines = out_path.read_text().strip().splitlines()
    assert lines == [
        "[plux.test.plugins]",
        "myplugin = mysrc.plugins:MyPlugin",
    ]


@pytest.mark.parametrize("project_name", ["pyproject", "setupcfg"])
def test_discover_with_ini_output_include(project_name, tmp_path):
    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", project_name)
    os.chdir(project)

    out_path = tmp_path / "plux.ini"

    sys.path.append(project)
    try:
        try:
            main(
                [
                    "--workdir",
                    project,
                    "discover",
                    "--format",
                    "ini",
                    "--output",
                    str(out_path),
                    "--include",
                    "*/subpkg*",
                ]
            )
        except SystemExit:
            pass
    finally:
        sys.path.remove(project)

    lines = out_path.read_text().strip().splitlines()
    assert lines == [
        "[plux.test.plugins]",
        "mynestedplugin = mysrc.subpkg.plugins:MyNestedPlugin",
    ]
