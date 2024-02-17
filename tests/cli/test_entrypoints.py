import os.path
import sys

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
        assert f.readlines() == ["[plux.test.plugins]\n", "myplugin = mysrc.plugins:MyPlugin\n"]
