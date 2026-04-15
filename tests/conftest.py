"""
Shared pytest fixtures for the MathTools test suite.
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure the src directory is in the path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory and change cwd to it for test isolation."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)


@pytest.fixture
def mock_console(monkeypatch):
    """Patch the shared console to suppress output during tests."""
    mock = MagicMock()
    monkeypatch.setattr("utils.ui.console", mock)
    return mock


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample config file and return its path."""
    config_data = {"obsidian_vault_path": str(tmp_path / "vault")}
    config_file = tmp_path / ".mathtools.json"
    config_file.write_text(json.dumps(config_data))
    return config_file


@pytest.fixture
def sample_vault(tmp_path):
    """Create a sample Obsidian vault structure for testing."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create markdown files
    (vault / "note1.md").write_text("# Note 1\nSome content")
    (vault / "note2.md").write_text("# Note 2\nMore content")

    # Create a non-markdown file (should be ignored)
    (vault / "image.png").write_bytes(b"\x89PNG")

    # Create subdirectory with files
    subdir = vault / "subfolder"
    subdir.mkdir()
    (subdir / "nested.md").write_text("# Nested\nNested content")

    # Create ignored directories
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "config.json").write_text("{}")
    (vault / ".git").mkdir()
    (vault / ".git" / "HEAD").write_text("ref: refs/heads/main")

    return vault


@pytest.fixture
def sample_zip_bytes():
    """Create sample ZIP bytes simulating repository downloads."""
    import io
    import zipfile

    def _make_zip(prefix: str, files: dict[str, str]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in files.items():
                zf.writestr(f"{prefix}{path}", content)
        return buf.getvalue()

    return _make_zip


@pytest.fixture
def framework_zip(sample_zip_bytes):
    """Create a mock framework repository ZIP."""
    return sample_zip_bytes(
        "matrueba-AI-development-framework-main/",
        {
            "src/agents/agent1/config.yaml": "name: agent1",
            "src/agents/agent1/prompt.md": "# Agent 1",
            "src/agents/agent2/config.yaml": "name: agent2",
            "src/commands/cmd1/run.sh": "#!/bin/bash",
            "src/commands/cmd2/run.sh": "#!/bin/bash",
            "src/rules/rule1.md": "# Rule 1",
            "src/workflow/wf1.yaml": "name: wf1",
        },
    )


@pytest.fixture
def skills_zip(sample_zip_bytes):
    """Create a mock skills repository ZIP."""
    return sample_zip_bytes(
        "matrueba-skills-framework-main/",
        {
            "skills/skill1/SKILL.md": "# Skill 1",
            "skills/skill1/run.py": "print('skill1')",
            "skills/skill2/SKILL.md": "# Skill 2",
        },
    )
