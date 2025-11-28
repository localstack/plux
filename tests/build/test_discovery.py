import os
import shutil
from pathlib import Path

import pytest

from plux.build.discovery import SimplePackageFinder


@pytest.fixture
def chdir():
    """Change the working directory to the given path temporarily for the test."""
    prev = os.getcwd()
    yield os.chdir
    os.chdir(prev)


class TestSimplePackageFinder:
    @pytest.fixture
    def nested_package_tree(self, tmp_path) -> Path:
        # nested directory structure
        dirs = [
            tmp_path / "src" / "mypkg" / "subpkg1",
            tmp_path / "src" / "mypkg" / "subpkg2",
            tmp_path / "src" / "mypkg" / "subpkg1" / "nested_subpkg1",
            tmp_path / "src" / "mypkg_sibling",
            tmp_path / "src" / "notapkg",
            tmp_path / "src" / "not.a.pkg",  # this is an invalid package name and will break imports
        ]
        files = [
            tmp_path / "src" / "mypkg" / "__init__.py",
            tmp_path / "src" / "mypkg" / "subpkg1" / "__init__.py",
            tmp_path / "src" / "mypkg" / "subpkg2" / "__init__.py",
            tmp_path / "src" / "mypkg" / "subpkg1" / "nested_subpkg1" / "__init__.py",
            tmp_path / "src" / "mypkg_sibling" / "__init__.py",
            tmp_path / "src" / "notapkg" / "__init__.txt",
            tmp_path / "src" / "not.a.pkg" / "__init__.py",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        for f in files:
            f.touch(exist_ok=True)

        return tmp_path

    def test_package_discovery(self, nested_package_tree, chdir):
        # change into the directory for the test
        chdir(nested_package_tree / "src")

        # this emulates what a typical hatchling src-tree config would look like
        finder = SimplePackageFinder("mypkg")

        assert finder.find_packages() == [
            "mypkg",
            "mypkg.subpkg1",
            "mypkg.subpkg1.nested_subpkg1",
            "mypkg.subpkg2",
        ]

    def test_package_discovery_in_current_dir(self, nested_package_tree, chdir):
        # change into the actual package directory, so the path just becomes "."
        chdir(nested_package_tree / "src" / "mypkg")

        # this might be equivalent to os.curdir
        finder = SimplePackageFinder(".")

        assert finder.find_packages() == [
            "mypkg",
            "mypkg.subpkg1",
            "mypkg.subpkg1.nested_subpkg1",
            "mypkg.subpkg2",
        ]

    def test_package_discovery_with_src_folder(self, nested_package_tree, chdir):
        # change into the directory for the test
        chdir(nested_package_tree)

        # this emulates what a typical hatchling src-tree config would look like
        finder = SimplePackageFinder("src")

        assert finder.find_packages() == [
            "mypkg",
            "mypkg.subpkg1",
            "mypkg.subpkg1.nested_subpkg1",
            "mypkg.subpkg2",
            "mypkg_sibling",
        ]

    def test_package_discovery_with_src_folder_unconventional(self, nested_package_tree, chdir):
        # change into the directory for the test
        chdir(nested_package_tree)

        # make sure there's no special consideration of "src" as a convention
        shutil.move(nested_package_tree / "src", nested_package_tree / "sources")

        # this emulates what a typical hatchling src-tree config would look like
        finder = SimplePackageFinder("sources")

        assert finder.find_packages() == [
            "mypkg",
            "mypkg.subpkg1",
            "mypkg.subpkg1.nested_subpkg1",
            "mypkg.subpkg2",
            "mypkg_sibling",
        ]

    def test_package_discovery_with_nested_src_dir(self, nested_package_tree, chdir):
        chdir(nested_package_tree)

        # create a root path
        root = nested_package_tree / "root"
        root.mkdir(parents=True, exist_ok=True)

        # move everything s.t. the path is now "root/src/"
        shutil.move(nested_package_tree / "src", root)

        # should still work in the same way
        finder = SimplePackageFinder("root/src/mypkg")

        assert finder.find_packages() == [
            "mypkg",
            "mypkg.subpkg1",
            "mypkg.subpkg1.nested_subpkg1",
            "mypkg.subpkg2",
        ]

        # make sure it finds the sibling if not pointed to the pkg dir directly
        finder = SimplePackageFinder("root/src")

        assert finder.find_packages() == [
            "mypkg",
            "mypkg.subpkg1",
            "mypkg.subpkg1.nested_subpkg1",
            "mypkg.subpkg2",
            "mypkg_sibling",
        ]

    def test_package_discovery_in_empty_dir(self, tmp_path, chdir):
        path = tmp_path / "empty"
        path.mkdir()
        chdir(tmp_path)

        finder = SimplePackageFinder("empty")

        assert finder.find_packages() == []
