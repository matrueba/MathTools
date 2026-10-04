"""
Tests for src/web/installer.py — harness listing, extraction and downloads.

Zips are built in memory by the conftest fixtures with the exact GitHub
prefixes, so extraction runs end to end without touching the network.
"""

import os
from unittest.mock import MagicMock, patch

from web.installer import (
    download_repo_zips,
    extract_environment,
    get_available_items,
    get_existing_folders,
)

GEMINI_ALL = {"src/agents": "all", "src/commands": "all", "skills": "all"}


class TestGetAvailableItems:
    def test_lists_items_from_framework(self, framework_zip):
        items = get_available_items({"framework": framework_zip}, "framework", "src/agents")
        assert items == ["agent1", "agent2"]

    def test_lists_items_from_skills(self, skills_zip):
        items = get_available_items({"skills": skills_zip}, "skills", "skills")
        assert items == ["skill1", "skill2"]

    def test_commands_listing(self, framework_zip):
        items = get_available_items({"framework": framework_zip}, "framework", "src/commands")
        assert items == ["cmd1", "cmd2"]

    def test_nonexistent_path_returns_empty(self, framework_zip):
        assert get_available_items({"framework": framework_zip}, "framework", "src/nope") == []


class TestExtractEnvironment:
    def test_extract_local_all(self, tmp_path, framework_zip, skills_zip):
        zips = {"framework": framework_zip, "skills": skills_zip}

        written, location = extract_environment(zips, "gemini", "local", GEMINI_ALL, str(tmp_path))

        assert location == ".gemini"
        assert os.path.join(".gemini", "agents", "agent1", "config.yaml") in written
        assert (tmp_path / ".gemini" / "agents" / "agent1" / "config.yaml").exists()
        assert (tmp_path / ".gemini" / "agents" / "agent2" / "config.yaml").exists()
        assert (tmp_path / ".gemini" / "skills" / "skill1" / "SKILL.md").exists()

    def test_extract_local_selected_items(self, tmp_path, framework_zip, skills_zip):
        zips = {"framework": framework_zip, "skills": skills_zip}
        selections = {"src/agents": ["agent1"], "src/commands": "all", "skills": ["skill2"]}

        extract_environment(zips, "gemini", "local", selections, str(tmp_path))

        assert (tmp_path / ".gemini" / "agents" / "agent1" / "config.yaml").exists()
        assert not (tmp_path / ".gemini" / "agents" / "agent2").exists()
        assert (tmp_path / ".gemini" / "skills" / "skill2" / "SKILL.md").exists()
        assert not (tmp_path / ".gemini" / "skills" / "skill1").exists()

    def test_missing_selection_installs_everything(self, tmp_path, framework_zip, skills_zip):
        zips = {"framework": framework_zip, "skills": skills_zip}
        written, _ = extract_environment(zips, "gemini", "local", {}, str(tmp_path))
        full, _ = extract_environment(zips, "gemini", "local", GEMINI_ALL, str(tmp_path))
        assert written == full

    def test_extract_global(self, tmp_path, framework_zip, skills_zip):
        zips = {"framework": framework_zip, "skills": skills_zip}
        home = str(tmp_path / "home")

        with patch("web.installer.os.path.expanduser", side_effect=lambda p: p.replace("~", home)):
            written, location = extract_environment(zips, "gemini", "global", GEMINI_ALL, str(tmp_path))

        assert location == "Global (~/)"
        assert written
        # Global paths are reported unexpanded, the way the user would type them.
        assert all(path.startswith("~") for path in written)
        assert not (tmp_path / ".gemini").exists()

    def test_extract_agents_environment(self, tmp_path, framework_zip, skills_zip):
        zips = {"framework": framework_zip, "skills": skills_zip}
        selections = {"src/rules": "all", "skills": "all", "src/workflow": "all"}

        written, location = extract_environment(zips, "agents", "local", selections, str(tmp_path))
        assert location == ".agents"
        assert written

    def test_extract_with_empty_zip(self, tmp_path, sample_zip_bytes):
        zips = {
            "framework": sample_zip_bytes("matrueba-AI-development-framework-main/", {}),
            "skills": sample_zip_bytes("matrueba-skills-framework-main/", {}),
        }
        written, _ = extract_environment(zips, "gemini", "local", GEMINI_ALL, str(tmp_path))
        assert written == []


class TestGetExistingFolders:
    def test_local_folder_exists(self, tmp_path):
        (tmp_path / ".gemini").mkdir()
        assert get_existing_folders(["gemini"], {"gemini": "local"}, str(tmp_path)) == [".gemini"]

    def test_local_folder_not_exists(self, tmp_path):
        assert get_existing_folders(["gemini"], {"gemini": "local"}, str(tmp_path)) == []

    def test_global_folder_exists(self, tmp_path):
        with patch("web.installer.os.path.exists", return_value=True):
            result = get_existing_folders(["gemini"], {"gemini": "global"}, str(tmp_path))
        assert result and all(path.startswith("~") for path in result)

    def test_global_folder_not_exists(self, tmp_path):
        with patch("web.installer.os.path.expanduser", return_value="/nonexistent/path"):
            assert get_existing_folders(["gemini"], {"gemini": "global"}, str(tmp_path)) == []

    def test_multiple_envs_mixed(self, tmp_path):
        (tmp_path / ".gemini").mkdir()
        modes = {"gemini": "local", "agents": "local"}
        assert get_existing_folders(["gemini", "agents"], modes, str(tmp_path)) == [".gemini"]

    def test_empty_selection(self, tmp_path):
        assert get_existing_folders([], {}, str(tmp_path)) == []


class TestDownloadRepoZips:
    def test_downloads_every_repository(self):
        response = MagicMock(content=b"zip-bytes")

        with patch("web.installer.requests.get", return_value=response) as get:
            result = download_repo_zips()

        assert result == {"framework": b"zip-bytes", "skills": b"zip-bytes"}
        assert get.call_count == 2
        response.raise_for_status.assert_called()
