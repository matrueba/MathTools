"""
Tests for src/cli/memory.py
Covers: MemoryManager (config I/O, vault detection, tree building)
"""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestMemoryManagerConfig:
    def test_load_config_file_exists(self, tmp_path):
        """Should load JSON config when the file exists."""
        config_data = {"obsidian_vault_path": "/some/path"}
        config_file = tmp_path / ".mathtools.json"
        config_file.write_text(json.dumps(config_data))

        with patch("cli.memory.CONFIG_PATH", config_file):
            from cli.memory import MemoryManager
            mm = MemoryManager()
            assert mm.config == config_data

    def test_load_config_file_not_exists(self, tmp_path):
        """Should return empty dict when config does not exist."""
        config_file = tmp_path / ".mathtools_nonexistent.json"

        with patch("cli.memory.CONFIG_PATH", config_file):
            from cli.memory import MemoryManager
            mm = MemoryManager()
            assert mm.config == {}

    def test_load_config_invalid_json(self, tmp_path):
        """Should return empty dict when config file contains invalid JSON."""
        config_file = tmp_path / ".mathtools.json"
        config_file.write_text("NOT VALID JSON {{{")

        with patch("cli.memory.CONFIG_PATH", config_file):
            from cli.memory import MemoryManager
            mm = MemoryManager()
            assert mm.config == {}

    def test_save_config(self, tmp_path):
        """Should write config dict to JSON file."""
        config_file = tmp_path / ".mathtools.json"

        with patch("cli.memory.CONFIG_PATH", config_file):
            from cli.memory import MemoryManager
            mm = MemoryManager()
            mm.config = {"key": "value"}
            mm._save_config()

        saved = json.loads(config_file.read_text())
        assert saved == {"key": "value"}

    def test_save_config_error(self, tmp_path):
        """Should handle write errors gracefully."""
        config_file = tmp_path / "nonexistent_dir" / "config.json"

        with patch("cli.memory.CONFIG_PATH", config_file):
            with patch("cli.memory.console") as mock_console:
                from cli.memory import MemoryManager
                mm = MemoryManager()
                mm.config = {"key": "value"}
                # Should not raise, just print error
                mm._save_config()
                mock_console.print.assert_called()


class TestMemoryManagerRunManageMemory:
    def test_existing_vault_path(self, tmp_path, sample_vault):
        """With a valid vault in config, should display the tree without prompting."""
        config_file = tmp_path / ".mathtools.json"
        config_data = {"obsidian_vault_path": str(sample_vault)}
        config_file.write_text(json.dumps(config_data))

        with patch("cli.memory.CONFIG_PATH", config_file):
            with patch("cli.memory.console") as mock_console:
                from cli.memory import MemoryManager
                mm = MemoryManager()
                mm.run_manage_memory()

        # Should have printed the tree (at least the vault path header)
        calls = [str(c) for c in mock_console.print.call_args_list]
        any_vault_mention = any("Obsidian Vault" in c for c in calls)
        assert any_vault_mention

    def test_prompts_for_vault_when_not_configured(self, tmp_path, sample_vault):
        """Should prompt for vault path when not in config."""
        config_file = tmp_path / ".mathtools.json"
        config_file.write_text("{}")

        with patch("cli.memory.CONFIG_PATH", config_file):
            with patch("cli.memory.console"):
                with patch("cli.memory.questionary.path") as mock_path:
                    mock_path.return_value.ask.return_value = str(sample_vault)
                    from cli.memory import MemoryManager
                    mm = MemoryManager()
                    mm.run_manage_memory()

                    mock_path.assert_called_once()

    def test_user_cancels_vault_prompt(self, tmp_path):
        """If user cancels the path prompt, should return without error."""
        config_file = tmp_path / ".mathtools.json"
        config_file.write_text("{}")

        with patch("cli.memory.CONFIG_PATH", config_file):
            with patch("cli.memory.console"):
                with patch("cli.memory.questionary.path") as mock_path:
                    mock_path.return_value.ask.return_value = None
                    from cli.memory import MemoryManager
                    mm = MemoryManager()
                    mm.run_manage_memory()  # Should not raise

    def test_vault_path_not_exists(self, tmp_path):
        """Should print error when vault path is in config but doesn't exist on disk."""
        config_file = tmp_path / ".mathtools.json"
        config_data = {"obsidian_vault_path": "/nonexistent/vault/path"}
        config_file.write_text(json.dumps(config_data))

        with patch("cli.memory.CONFIG_PATH", config_file):
            with patch("cli.memory.console") as mock_console:
                from cli.memory import MemoryManager

                # Simulate: path in config doesn't exist, user enters a new bad path
                # that also doesn't exist → first branch is prompting
                mm = MemoryManager()

                with patch("cli.memory.questionary.path") as mock_path:
                    mock_path.return_value.ask.return_value = str(tmp_path / "also_nonexistent")
                    mm.run_manage_memory()

                calls = [str(c) for c in mock_console.print.call_args_list]
                any_error = any("does not exist" in c for c in calls)
                assert any_error


class TestBuildTree:
    def test_builds_tree_with_markdown_files(self, sample_vault):
        """Tree should include .md files."""
        from cli.memory import MemoryManager
        from rich.tree import Tree

        with patch("cli.memory.CONFIG_PATH", Path("/nonexistent")):
            mm = MemoryManager()

        tree = Tree("root")
        mm._build_tree(sample_vault, tree)

        # Collect all labels from the tree
        labels = self._collect_labels(tree)
        assert any("note1.md" in label for label in labels)
        assert any("note2.md" in label for label in labels)

    def test_ignores_dotfolders(self, sample_vault):
        """Tree should not include .obsidian, .git, etc."""
        from cli.memory import MemoryManager
        from rich.tree import Tree

        with patch("cli.memory.CONFIG_PATH", Path("/nonexistent")):
            mm = MemoryManager()

        tree = Tree("root")
        mm._build_tree(sample_vault, tree)

        labels = self._collect_labels(tree)
        assert not any(".obsidian" in label for label in labels)
        assert not any(".git" in label for label in labels)

    def test_ignores_non_markdown_files(self, sample_vault):
        """Tree should not include .png or other non-.md files."""
        from cli.memory import MemoryManager
        from rich.tree import Tree

        with patch("cli.memory.CONFIG_PATH", Path("/nonexistent")):
            mm = MemoryManager()

        tree = Tree("root")
        mm._build_tree(sample_vault, tree)

        labels = self._collect_labels(tree)
        assert not any("image.png" in label for label in labels)

    def test_recurses_into_subdirectories(self, sample_vault):
        """Tree should include nested directories and their .md files."""
        from cli.memory import MemoryManager
        from rich.tree import Tree

        with patch("cli.memory.CONFIG_PATH", Path("/nonexistent")):
            mm = MemoryManager()

        tree = Tree("root")
        mm._build_tree(sample_vault, tree)

        labels = self._collect_labels(tree)
        assert any("subfolder" in label for label in labels)
        assert any("nested.md" in label for label in labels)

    def test_handles_permission_error(self, tmp_path):
        """Should add 'Permission denied' node on PermissionError."""
        from cli.memory import MemoryManager
        from rich.tree import Tree

        with patch("cli.memory.CONFIG_PATH", Path("/nonexistent")):
            mm = MemoryManager()

        tree = Tree("root")
        with patch.object(Path, "iterdir", side_effect=PermissionError("denied")):
            mm._build_tree(tmp_path, tree)

        labels = self._collect_labels(tree)
        assert any("Permission denied" in label for label in labels)

    def test_empty_directory(self, tmp_path):
        """Empty directory should produce tree with no children."""
        from cli.memory import MemoryManager
        from rich.tree import Tree

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with patch("cli.memory.CONFIG_PATH", Path("/nonexistent")):
            mm = MemoryManager()

        tree = Tree("root")
        mm._build_tree(empty_dir, tree)

        # Root should have no children added
        labels = self._collect_labels(tree)
        assert labels == ["root"]

    @staticmethod
    def _collect_labels(tree) -> list[str]:
        """Recursively collect all label strings from a Rich Tree."""
        labels = [str(tree.label)]
        for child in tree.children:
            labels.extend(TestBuildTree._collect_labels(child))
        return labels
