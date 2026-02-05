"""
Unit tests for hatchling metadata hook plugin.
"""

import configparser
from pathlib import Path

import pytest


class TestParsePluginIni:
    """Tests for _parse_plux_ini helper function."""

    def test_parse_simple_ini(self, tmp_path):
        """Test parsing a simple plux.ini file."""
        from plux.build.hatchling import _parse_plux_ini

        plux_ini = tmp_path / "plux.ini"
        plux_ini.write_text(
            """[plux.test.plugins]
            myplugin = mysrc.plugins:MyPlugin
            """
        )

        result = _parse_plux_ini(str(plux_ini))

        assert result == {"plux.test.plugins": {"myplugin": "mysrc.plugins:MyPlugin"}}

    def test_parse_multiple_groups(self, tmp_path):
        """Test parsing plux.ini with multiple entry point groups."""
        from plux.build.hatchling import _parse_plux_ini

        plux_ini = tmp_path / "plux.ini"
        plux_ini.write_text(
            """[plux.test.plugins]
            plugin1 = pkg.module:Plugin1
            plugin2 = pkg.module:Plugin2
            
            [console_scripts]
            mycli = pkg.cli:main
            """
        )

        result = _parse_plux_ini(str(plux_ini))

        assert result == {
            "plux.test.plugins": {
                "plugin1": "pkg.module:Plugin1",
                "plugin2": "pkg.module:Plugin2",
            },
            "console_scripts": {"mycli": "pkg.cli:main"},
        }

    def test_parse_plugin_name_with_colon(self, tmp_path):
        """Test that plugin names containing colons are parsed correctly."""
        from plux.build.hatchling import _parse_plux_ini

        plux_ini = tmp_path / "plux.ini"
        plux_ini.write_text(
            """[plux.test.plugins]
            aws:s3 = pkg.aws.s3:S3Plugin
            db:postgres = pkg.db.postgres:PostgresPlugin
            """
        )

        result = _parse_plux_ini(str(plux_ini))

        assert result == {
            "plux.test.plugins": {
                "aws:s3": "pkg.aws.s3:S3Plugin",
                "db:postgres": "pkg.db.postgres:PostgresPlugin",
            }
        }

    def test_parse_missing_file(self, tmp_path):
        """Test that FileNotFoundError is raised for missing file."""
        from plux.build.hatchling import _parse_plux_ini

        nonexistent = tmp_path / "nonexistent.ini"

        with pytest.raises(FileNotFoundError):
            _parse_plux_ini(str(nonexistent))

    def test_parse_invalid_ini_syntax(self, tmp_path):
        """Test that configparser.Error is raised for invalid INI syntax."""
        from plux.build.hatchling import _parse_plux_ini

        plux_ini = tmp_path / "plux.ini"
        plux_ini.write_text(
            """[plux.test.plugins]
            invalid syntax here without equals sign
            """
        )

        with pytest.raises(configparser.Error):
            _parse_plux_ini(str(plux_ini))

    def test_parse_empty_file(self, tmp_path):
        """Test parsing an empty plux.ini file."""
        from plux.build.hatchling import _parse_plux_ini

        plux_ini = tmp_path / "plux.ini"
        plux_ini.write_text("")

        result = _parse_plux_ini(str(plux_ini))

        assert result == {}


class TestMergeEntryPoints:
    """Tests for _merge_entry_points helper function."""

    def test_merge_into_empty_target(self):
        """Test merging into an empty target dictionary."""
        from plux.build.hatchling import _merge_entry_points

        target = {}
        source = {
            "plux.plugins": {"p1": "pkg:P1", "p2": "pkg:P2"},
            "console_scripts": {"cli": "pkg:main"},
        }

        _merge_entry_points(target, source)

        assert target == source

    def test_merge_new_groups(self):
        """Test merging adds new groups that don't exist in target."""
        from plux.build.hatchling import _merge_entry_points

        target = {"console_scripts": {"app": "module:main"}}
        source = {"plux.plugins": {"p1": "pkg:P1"}}

        _merge_entry_points(target, source)

        assert target == {
            "console_scripts": {"app": "module:main"},
            "plux.plugins": {"p1": "pkg:P1"},
        }

    def test_merge_existing_groups(self):
        """Test merging into existing groups combines entries."""
        from plux.build.hatchling import _merge_entry_points

        target = {"console_scripts": {"app": "module:main"}}
        source = {"console_scripts": {"tool": "module:cli"}}

        _merge_entry_points(target, source)

        assert target == {"console_scripts": {"app": "module:main", "tool": "module:cli"}}

    def test_merge_overwrites_duplicate_names(self):
        """Test that source entries overwrite target entries with same name."""
        from plux.build.hatchling import _merge_entry_points

        target = {"plux.plugins": {"p1": "old.module:OldPlugin"}}
        source = {"plux.plugins": {"p1": "new.module:NewPlugin"}}

        _merge_entry_points(target, source)

        # Source should overwrite target
        assert target == {"plux.plugins": {"p1": "new.module:NewPlugin"}}

    def test_merge_preserves_other_entries(self):
        """Test that merging preserves entries not in source."""
        from plux.build.hatchling import _merge_entry_points

        target = {"plux.plugins": {"p1": "pkg:P1", "p2": "pkg:P2"}}
        source = {"plux.plugins": {"p1": "pkg:NewP1", "p3": "pkg:P3"}}

        _merge_entry_points(target, source)

        assert target == {"plux.plugins": {"p1": "pkg:NewP1", "p2": "pkg:P2", "p3": "pkg:P3"}}


class TestPluxMetadataHook:
    """Tests for PluxMetadataHook class."""

    def test_hook_raises_in_build_hook_mode(self, tmp_path):
        """Test that hook is no-op when entrypoint_build_mode is not manual."""
        pytest.importorskip("hatchling")
        from plux.build.hatchling import PluxMetadataHook

        # Create a temporary pyproject.toml with build-hook mode
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.plux]
            entrypoint_build_mode = "build-hook"
            """
        )

        # Create hook instance
        hook = PluxMetadataHook(str(tmp_path), {})
        metadata = {"name": "test-project"}

        # expect to fail for non-manual build hook for now
        with pytest.raises(RuntimeError, match="only supported for `entrypoint_build_mode=manual`"):
            hook.update(metadata)

    def test_hook_activates_in_manual_mode(self, tmp_path):
        """Test that hook processes plux.ini in manual mode."""
        pytest.importorskip("hatchling")
        from plux.build.hatchling import PluxMetadataHook

        # Create pyproject.toml with manual mode
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.plux]
            entrypoint_build_mode = "manual"
            """
        )

        # Create plux.ini
        plux_ini = tmp_path / "plux.ini"
        plux_ini.write_text(
            """[plux.test.plugins]
            myplugin = mysrc.plugins:MyPlugin
            """
        )

        # Create hook instance
        hook = PluxMetadataHook(str(tmp_path), {})

        # Create metadata
        metadata = {"name": "test-project"}

        # Call update
        hook.update(metadata)

        # Entry points should be added
        assert "entry-points" in metadata
        assert metadata["entry-points"] == {
            "plux.test.plugins": {"myplugin": "mysrc.plugins:MyPlugin"}
        }

    def test_hook_uses_custom_static_file_name(self, tmp_path):
        """Test that hook uses custom entrypoint_static_file setting."""
        pytest.importorskip("hatchling")
        from plux.build.hatchling import PluxMetadataHook

        # Create pyproject.toml with custom file name
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.plux]
            entrypoint_build_mode = "manual"
            entrypoint_static_file = "custom.ini"
            """
        )

        # Create custom.ini
        custom_ini = tmp_path / "custom.ini"
        custom_ini.write_text(
            """[plux.plugins]
            p1 = pkg:P1
            """
        )

        # Create hook instance
        hook = PluxMetadataHook(str(tmp_path), {})

        # Create metadata
        metadata = {}

        # Call update
        hook.update(metadata)

        # Entry points should be loaded from custom.ini
        assert metadata["entry-points"] == {"plux.plugins": {"p1": "pkg:P1"}}

    def test_hook_merges_with_existing_entry_points(self, tmp_path):
        """Test that hook merges plux.ini entries with existing entry-points."""
        pytest.importorskip("hatchling")
        from plux.build.hatchling import PluxMetadataHook

        # Create config
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.plux]
            entrypoint_build_mode = "manual"
            """
        )

        # Create plux.ini
        plux_ini = tmp_path / "plux.ini"
        plux_ini.write_text(
            """[plux.plugins]
            p1 = pkg:P1
            """
        )

        # Create hook instance
        hook = PluxMetadataHook(str(tmp_path), {})

        # Create metadata with existing entry points
        metadata = {"entry-points": {"console_scripts": {"app": "module:main"}}}

        # Call update
        hook.update(metadata)

        # Both entry point groups should be present
        assert metadata["entry-points"] == {
            "console_scripts": {"app": "module:main"},
            "plux.plugins": {"p1": "pkg:P1"},
        }

    def test_hook_handles_missing_plux_ini_gracefully(self, tmp_path):
        """Test that hook doesn't fail build when plux.ini is missing."""
        pytest.importorskip("hatchling")
        from plux.build.hatchling import PluxMetadataHook

        # Create pyproject.toml but no plux.ini
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.plux]
            entrypoint_build_mode = "manual"
            """
        )

        # Create hook instance
        hook = PluxMetadataHook(str(tmp_path), {})

        # Create metadata
        metadata = {}

        # Call update - should not raise exception
        hook.update(metadata)

        # No entry points should be added
        assert "entry-points" not in metadata

    def test_hook_fails_on_invalid_ini_syntax(self, tmp_path):
        """Test that hook raises ValueError for invalid INI syntax."""
        pytest.importorskip("hatchling")
        from plux.build.hatchling import PluxMetadataHook

        # Create pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.plux]
            entrypoint_build_mode = "manual"
            """
        )

        # Create invalid plux.ini
        plux_ini = tmp_path / "plux.ini"
        plux_ini.write_text(
            """[plux.plugins]
            invalid line without equals
            """
        )

        # Create hook instance
        hook = PluxMetadataHook(str(tmp_path), {})

        # Create metadata
        metadata = {}

        # Call update - should raise ValueError
        with pytest.raises(ValueError, match="Failed to parse plux.ini"):
            hook.update(metadata)

    def test_plugin_name_attribute(self):
        """Test that PLUGIN_NAME attribute is set correctly."""
        pytest.importorskip("hatchling")
        from plux.build.hatchling import PluxMetadataHook

        assert PluxMetadataHook.PLUGIN_NAME == "plux"


def test_hatch_register_metadata_hook():
    """Test that the hook registration function returns the correct class."""
    pytest.importorskip("hatchling")
    from plux.build.hatchling import PluxMetadataHook, hatch_register_metadata_hook

    hook_class = hatch_register_metadata_hook()

    assert hook_class is PluxMetadataHook
