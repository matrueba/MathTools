"""
Tests for src/utils/installer_utils.py
Covers: InstallerUtils.get_modes(), InstallerUtils.get_existing_folders()
"""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestGetModes:
    def test_returns_local_for_all(self):
        """When user selects 'local' for every env, get_modes should return all local."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        with patch("utils.installer_utils.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "local"
            result = utils.get_modes(["gemini", "agents"])

        assert result == {"gemini": "local", "agents": "local"}

    def test_returns_global_for_all(self):
        """When user selects 'global' for every env, get_modes should return all global."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        with patch("utils.installer_utils.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "global"
            result = utils.get_modes(["gemini"])

        assert result == {"gemini": "global"}

    def test_returns_mixed_modes(self):
        """Different envs can have different modes."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        with patch("utils.installer_utils.questionary.select") as mock_select:
            mock_select.return_value.ask.side_effect = ["local", "global"]
            result = utils.get_modes(["gemini", "agents"])

        assert result == {"gemini": "local", "agents": "global"}

    def test_returns_none_on_cancel(self):
        """If user cancels (ask returns None), get_modes should return None."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        with patch("utils.installer_utils.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = None
            result = utils.get_modes(["gemini"])

        assert result is None

    def test_empty_selected_list(self):
        """Empty list should return empty dict."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        result = utils.get_modes([])
        assert result == {}

    def test_calls_questionary_for_each_env(self):
        """Should call questionary.select once per selected environment."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        with patch("utils.installer_utils.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "local"
            utils.get_modes(["gemini", "agents", "claude"])

        assert mock_select.call_count == 3


class TestGetExistingFolders:
    def test_local_folder_exists(self, tmp_dir):
        """When a local target dir exists, it should be reported."""
        from utils.installer_utils import InstallerUtils

        (tmp_dir / ".gemini").mkdir()
        utils = InstallerUtils()
        result = utils.get_existing_folders(["gemini"], {"gemini": "local"})
        assert ".gemini" in result

    def test_local_folder_not_exists(self, tmp_dir):
        """When a local target dir does not exist, it should not be reported."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        result = utils.get_existing_folders(["gemini"], {"gemini": "local"})
        assert result == []

    def test_global_folder_exists(self, tmp_dir):
        """When global paths exist, they should be reported."""
        from utils.installer_utils import InstallerUtils

        fake_global = tmp_dir / "fake_global"
        fake_global.mkdir()

        utils = InstallerUtils()
        with patch("utils.installer_utils.os.path.expanduser", return_value=str(fake_global)):
            with patch("utils.installer_utils.os.path.exists", return_value=True):
                result = utils.get_existing_folders(["gemini"], {"gemini": "global"})

        assert len(result) > 0

    def test_global_folder_not_exists(self, tmp_dir):
        """When global paths don't exist, they should not be reported."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        with patch("utils.installer_utils.os.path.expanduser", return_value="/nonexistent/path"):
            with patch("utils.installer_utils.os.path.exists", return_value=False):
                result = utils.get_existing_folders(["gemini"], {"gemini": "global"})

        assert result == []

    def test_multiple_envs_mixed(self, tmp_dir):
        """Multiple environments with mixed local/global modes."""
        from utils.installer_utils import InstallerUtils

        (tmp_dir / ".gemini").mkdir()
        # .agents doesn't exist locally

        utils = InstallerUtils()
        modes = {"gemini": "local", "agents": "local"}
        result = utils.get_existing_folders(["gemini", "agents"], modes)
        assert ".gemini" in result
        assert ".agents" not in result

    def test_returns_list(self, tmp_dir):
        """Return type should always be a list."""
        from utils.installer_utils import InstallerUtils

        utils = InstallerUtils()
        result = utils.get_existing_folders([], {})
        assert isinstance(result, list)
