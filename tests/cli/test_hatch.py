import os.path
import sys


def test_discover_with_ini_output(tmp_path):
    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", "hatch_manual_build_mode")
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
        "mynestedplugin = test_project.subpkg.plugins:MyNestedPlugin",
        "myplugin = test_project.plugins:MyPlugin",
    ]


def test_discover_with_ini_output_namespace_Package(tmp_path):
    from plux.__main__ import main

    project = os.path.join(os.path.dirname(__file__), "projects", "hatch", "namespace_package")
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
        "mynestedplugin = test_project.subpkg.plugins:MyNestedPlugin",
        "myplugin = test_project.plugins:MyPlugin",
    ]
