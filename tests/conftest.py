"""
Shared pytest fixtures for the MathTools test suite.
"""

import sys
import os

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


# Mock projects that the web fixture registers as real repositories.
MOCK_PROJECTS = ("mathtools", "dotfiles")


@pytest.fixture
def web_client(tmp_path, monkeypatch):
    """
    API client with `mathtools` and `dotfiles` registered, backed by mock data.

    The mock sessions are keyed by paths like /root/mathtools; those are
    re-homed onto real git repositories under tmp_path (on branch `develop`)
    so registration and the ProjectPath join both work. Sessions of mock
    projects that are not registered simply belong to no project.

    The harness is real (read from disk), so HOME points into tmp_path too:
    global harness paths like ~/.claude/agents must never reach the real home.
    """
    import subprocess

    from fastapi.testclient import TestClient

    import web.data
    from constants.web import AGENT_PROVIDERS
    from web.mock_data import get_mock_sessions
    from web.server import create_app

    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    rehome = {}
    for name in MOCK_PROJECTS:
        repo = tmp_path / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "develop", str(repo)], check=True)
        rehome[f"/root/{name}"] = str(repo.resolve())

    sessions, _ = get_mock_sessions()
    for s in sessions:
        s["ProjectPath"] = rehome.get(s["ProjectPath"], s["ProjectPath"])
    tags = {a["id"]: a["tag"] for a in AGENT_PROVIDERS}

    def load_agent_sessions(self, project, agent=None):
        owned = [
            s for s in sessions
            if s["ProjectPath"] == project["path"]
            and (agent is None or s["AI"] == tags.get(agent))
        ]
        totals = {
            "input": sum(s["InputTokens"] or 0 for s in owned),
            "output": sum(s["OutputTokens"] or 0 for s in owned),
            "cacheR": sum(s["CacheR"] or 0 for s in owned),
            "cacheW": sum(s["CacheW"] or 0 for s in owned),
        }
        return owned, totals

    monkeypatch.setattr(web.data.DataStore, "load_agent_sessions", load_agent_sessions)

    client = TestClient(create_app(db_path=tmp_path / "mathtools.db"))
    for repo_path in rehome.values():
        assert client.post("/api/projects", json={"path": repo_path}).status_code == 201
    client.repo_paths = {name: rehome[f"/root/{name}"] for name in MOCK_PROJECTS}
    return client
