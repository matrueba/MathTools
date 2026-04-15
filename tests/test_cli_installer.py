"""
Tests for src/cli/installer.py
Covers: FrameworkInstaller (init, get_available_items, extract_environment,
        show_environments_menu, gather_selections, print_summary,
        download_repos_zips, run_installer)
"""

import io
import os
import zipfile
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


class TestFrameworkInstallerInit:
    def test_default_state(self):
        """Newly created installer should have empty state."""
        from cli.installer import FrameworkInstaller
        fi = FrameworkInstaller()
        assert fi.selected_modes == {}
        assert fi.existing_folders == []
        assert fi.selected_envs == []
        assert fi.selections == {}
        assert fi.results == {}

    def test_has_installer_utils(self):
        """Should have an InstallerUtils instance."""
        from cli.installer import FrameworkInstaller
        from utils.installer_utils import InstallerUtils
        fi = FrameworkInstaller()
        assert isinstance(fi.installerUtils, InstallerUtils)


class TestGetAvailableItems:
    def test_lists_items_from_framework(self, framework_zip):
        """Should list top-level item names under a given source path."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip}
        items = FrameworkInstaller.get_available_items(zips, "framework", "src/agents")
        assert "agent1" in items
        assert "agent2" in items
        assert len(items) == 2

    def test_lists_items_from_skills(self, skills_zip):
        """Should list skill names from the skills repo."""
        from cli.installer import FrameworkInstaller

        zips = {"skills": skills_zip}
        items = FrameworkInstaller.get_available_items(zips, "skills", "skills")
        assert "skill1" in items
        assert "skill2" in items

    def test_items_are_sorted(self, framework_zip):
        """Returned items should be alphabetically sorted."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip}
        items = FrameworkInstaller.get_available_items(zips, "framework", "src/agents")
        assert items == sorted(items)

    def test_nonexistent_path_returns_empty(self, framework_zip):
        """Non-existent source path should return empty list."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip}
        items = FrameworkInstaller.get_available_items(zips, "framework", "src/nonexistent")
        assert items == []

    def test_commands_listing(self, framework_zip):
        """Should list commands from the framework repo."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip}
        items = FrameworkInstaller.get_available_items(zips, "framework", "src/commands")
        assert "cmd1" in items
        assert "cmd2" in items


class TestExtractEnvironment:
    def test_extract_local_all(self, tmp_dir, framework_zip, skills_zip):
        """Extracting with 'all' selection should write all matching files."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip, "skills": skills_zip}

        fi = FrameworkInstaller()
        fi.selected_modes = {"gemini": "local"}
        fi.selections = {"gemini": {
            "src/agents": "all",
            "src/commands": "all",
            "skills": "all",
        }}

        written, location = fi.extract_environment(zips, "gemini")
        assert len(written) > 0
        assert location == ".gemini"

        # Check that files were actually written
        assert os.path.exists(os.path.join(str(tmp_dir), ".gemini", "agents", "agent1", "config.yaml"))
        assert os.path.exists(os.path.join(str(tmp_dir), ".gemini", "agents", "agent2", "config.yaml"))
        assert os.path.exists(os.path.join(str(tmp_dir), ".gemini", "skills", "skill1", "SKILL.md"))

    def test_extract_local_selected_items(self, tmp_dir, framework_zip, skills_zip):
        """Extracting with specific selections should only copy those items."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip, "skills": skills_zip}

        fi = FrameworkInstaller()
        fi.selected_modes = {"gemini": "local"}
        fi.selections = {"gemini": {
            "src/agents": ["agent1"],  # Only agent1
            "src/commands": "all",
            "skills": ["skill2"],  # Only skill2
        }}

        written, location = fi.extract_environment(zips, "gemini")

        # agent1 should exist, agent2 should not
        assert os.path.exists(os.path.join(str(tmp_dir), ".gemini", "agents", "agent1", "config.yaml"))
        assert not os.path.exists(os.path.join(str(tmp_dir), ".gemini", "agents", "agent2"))

        # skill2 should exist, skill1 should not
        assert os.path.exists(os.path.join(str(tmp_dir), ".gemini", "skills", "skill2", "SKILL.md"))
        assert not os.path.exists(os.path.join(str(tmp_dir), ".gemini", "skills", "skill1"))

    def test_extract_global(self, tmp_dir, framework_zip, skills_zip):
        """Extracting in global mode should use expanduser paths."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip, "skills": skills_zip}
        global_base = str(tmp_dir / "global_home")

        fi = FrameworkInstaller()
        fi.selected_modes = {"gemini": "global"}
        fi.selections = {"gemini": {
            "src/agents": "all",
            "src/commands": "all",
            "skills": "all",
        }}

        with patch("cli.installer.os.path.expanduser") as mock_expand:
            def expand_side_effect(path):
                if path == "~":
                    return global_base
                return path.replace("~", global_base)
            mock_expand.side_effect = expand_side_effect

            written, location = fi.extract_environment(zips, "gemini")

        assert location == "Global (~/)"
        assert len(written) > 0

    def test_extract_agents_environment(self, tmp_dir, framework_zip, skills_zip):
        """Should correctly extract the 'agents' environment with its different sources."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip, "skills": skills_zip}

        fi = FrameworkInstaller()
        fi.selected_modes = {"agents": "local"}
        fi.selections = {"agents": {
            "src/rules": "all",
            "skills": "all",
            "src/workflow": "all",
        }}

        written, location = fi.extract_environment(zips, "agents")
        assert location == ".agents"
        assert len(written) > 0

    def test_extract_with_empty_zip(self, tmp_dir, sample_zip_bytes):
        """Extracting from an empty ZIP should write no files."""
        from cli.installer import FrameworkInstaller

        empty_zip = sample_zip_bytes("matrueba-AI-development-framework-main/", {})
        skills_empty = sample_zip_bytes("matrueba-skills-framework-main/", {})
        zips = {"framework": empty_zip, "skills": skills_empty}

        fi = FrameworkInstaller()
        fi.selected_modes = {"gemini": "local"}
        fi.selections = {"gemini": {
            "src/agents": "all",
            "src/commands": "all",
            "skills": "all",
        }}

        written, location = fi.extract_environment(zips, "gemini")
        assert written == []


class TestShowEnvironmentsMenu:
    def test_returns_selected_environments(self):
        """Should return the list of selected environment keys."""
        from cli.installer import FrameworkInstaller

        with patch("cli.installer.console"):
            with patch("cli.installer.questionary.checkbox") as mock_checkbox:
                mock_checkbox.return_value.ask.return_value = ["gemini", "agents"]
                result = FrameworkInstaller.show_environments_menu()
                assert result == ["gemini", "agents"]

    def test_exits_on_empty_selection(self):
        """Should call sys.exit when no environments are selected."""
        from cli.installer import FrameworkInstaller

        with patch("cli.installer.console"):
            with patch("cli.installer.questionary.checkbox") as mock_checkbox:
                mock_checkbox.return_value.ask.return_value = []
                with pytest.raises(SystemExit):
                    FrameworkInstaller.show_environments_menu()

    def test_displays_table(self):
        """Should print a table showing available environments."""
        from cli.installer import FrameworkInstaller

        with patch("cli.installer.console") as mock_console:
            with patch("cli.installer.questionary.checkbox") as mock_checkbox:
                mock_checkbox.return_value.ask.return_value = ["gemini"]
                FrameworkInstaller.show_environments_menu()

        # console.print should have been called with a Table
        from rich.table import Table
        table_calls = [
            c for c in mock_console.print.call_args_list
            if c[0] and isinstance(c[0][0], Table)
        ]
        assert len(table_calls) >= 1


class TestGatherSelections:
    def test_install_all(self, framework_zip, skills_zip):
        """When user chooses 'install all', selection should be 'all'."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip, "skills": skills_zip}

        fi = FrameworkInstaller()
        fi.selected_envs = ["gemini"]

        with patch("cli.installer.console"):
            with patch("cli.installer.questionary.confirm") as mock_confirm:
                mock_confirm.return_value.ask.return_value = True
                fi.gather_selections(zips)

        # All sources should be "all"
        for src_key, sel in fi.selections["gemini"].items():
            assert sel == "all"

    def test_install_selected(self, framework_zip, skills_zip):
        """When user selects specific items, they should be stored."""
        from cli.installer import FrameworkInstaller

        zips = {"framework": framework_zip, "skills": skills_zip}

        fi = FrameworkInstaller()
        fi.selected_envs = ["gemini"]

        confirm_returns = [False, False, False]  # Not "all" for any source
        checkbox_returns = [["agent1"], ["cmd1"], ["skill1"]]

        with patch("cli.installer.console"):
            with patch("cli.installer.questionary.confirm") as mock_confirm:
                mock_confirm.return_value.ask.side_effect = confirm_returns
                with patch("cli.installer.questionary.checkbox") as mock_checkbox:
                    mock_checkbox.return_value.ask.side_effect = checkbox_returns
                    fi.gather_selections(zips)

        assert fi.selections["gemini"]["src/agents"] == ["agent1"]
        assert fi.selections["gemini"]["src/commands"] == ["cmd1"]
        assert fi.selections["gemini"]["skills"] == ["skill1"]


class TestPrintSummary:
    def test_prints_summary_table(self):
        """Should print a summary table with installed file counts."""
        from cli.installer import FrameworkInstaller

        fi = FrameworkInstaller()
        fi.results = {
            "gemini": (["f1", "f2", "f3"], ".gemini"),
            "agents": (["f4", "f5"], ".agents"),
        }

        with patch("cli.installer.console") as mock_console:
            fi.print_summary()

        # Should have been called with a Table and a summary line
        assert mock_console.print.call_count >= 2


class TestDownloadReposZips:
    def test_downloads_all_repos(self):
        """Should download all repositories and return bytes."""
        from cli.installer import FrameworkInstaller

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"x" * 100]
        mock_response.raise_for_status = MagicMock()

        with patch("cli.installer.console"):
            with patch("cli.installer.requests.get", return_value=mock_response):
                result = FrameworkInstaller.download_repos_zips()

        assert "framework" in result
        assert "skills" in result
        assert isinstance(result["framework"], bytes)
        assert isinstance(result["skills"], bytes)

    def test_handles_no_content_length(self):
        """Should work when content-length header is not provided."""
        from cli.installer import FrameworkInstaller

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"data"]
        mock_response.raise_for_status = MagicMock()

        with patch("cli.installer.console"):
            with patch("cli.installer.requests.get", return_value=mock_response):
                result = FrameworkInstaller.download_repos_zips()

        assert len(result) == 2


class TestRunInstaller:
    def test_cancelled_at_confirmation(self):
        """If user declines confirmation, installer should return early."""
        from cli.installer import FrameworkInstaller

        fi = FrameworkInstaller()

        with patch("cli.installer.console"):
            with patch.object(fi, "show_environments_menu", return_value=["gemini"]):
                with patch("cli.installer.Confirm.ask", return_value=False):
                    fi.run_installer()

        # Should not have proceeded to download
        assert fi.results == {}

    def test_cancelled_at_overwrite(self, tmp_dir):
        """If user declines overwrite, installer should return early."""
        from cli.installer import FrameworkInstaller

        # Create pre-existing folder
        (tmp_dir / ".gemini").mkdir()

        fi = FrameworkInstaller()

        confirm_calls = [True, False]  # Yes to install, No to overwrite

        with patch("cli.installer.console"):
            with patch.object(fi, "show_environments_menu", return_value=["gemini"]):
                with patch("cli.installer.Confirm.ask", side_effect=confirm_calls):
                    with patch.object(fi.installerUtils, "get_modes", return_value={"gemini": "local"}):
                        with patch.object(fi.installerUtils, "get_existing_folders", return_value=[".gemini"]):
                            fi.run_installer()

        assert fi.results == {}

    def test_full_flow(self, tmp_dir, framework_zip, skills_zip):
        """Full installer flow should download, select, extract, and summarize."""
        from cli.installer import FrameworkInstaller

        fi = FrameworkInstaller()
        zips = {"framework": framework_zip, "skills": skills_zip}

        with patch("cli.installer.console"):
            with patch.object(fi, "show_environments_menu", return_value=["gemini"]):
                with patch("cli.installer.Confirm.ask", return_value=True):
                    with patch.object(fi.installerUtils, "get_modes", return_value={"gemini": "local"}):
                        with patch.object(fi.installerUtils, "get_existing_folders", return_value=[]):
                            with patch.object(FrameworkInstaller, "download_repos_zips", return_value=zips):
                                with patch("cli.installer.questionary.confirm") as mock_confirm:
                                    mock_confirm.return_value.ask.return_value = True
                                    fi.run_installer()

        assert "gemini" in fi.results
        written, location = fi.results["gemini"]
        assert len(written) > 0
        assert location == ".gemini"
