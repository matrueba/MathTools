"""
Mock data for the web dashboard.

Session dicts follow the exact same contract as the monitoring source adapters
(see `cli/monitoring/claude_source.py`), so replacing them with a real
`ClaudeSource().parse_claude_sessions()` call is a one-line change in
`server.py` — nothing downstream needs to know the difference.

Repositories are a separate concern: the monitoring contract only carries a
`ProjectPath`, so git metadata lives in its own mock and the server joins the
two on that path. The real implementation will shell out to git in each
`ProjectPath` instead.
"""

import time


def _ago(seconds: float) -> float:
    """Epoch timestamp `seconds` in the past."""
    return time.time() - seconds


def get_mock_repositories() -> list[dict]:
    """
    Git repositories backing the tracked projects, keyed by absolute path.

    `path` is the join key against a session's `ProjectPath`.
    """
    return [
        {
            "path": "/root/mathtools",
            "name": "mathtools",
            "branch": "develop",
            "defaultBranch": "main",
            "remote": "https://github.com/matrueba/mathtools.git",
            "dirty": True,
            "changedFiles": 6,
            "ahead": 2,
            "behind": 0,
            "lastCommit": {
                "hash": "8904f76",
                "message": "add gemini to monitoring",
                "author": "matrueba",
                "at": _ago(9_400),
            },
        },
        {
            "path": "/root/matrueba-skills-framework",
            "name": "matrueba-skills-framework",
            "branch": "main",
            "defaultBranch": "main",
            "remote": "https://github.com/matrueba/matrueba-skills-framework.git",
            "dirty": False,
            "changedFiles": 0,
            "ahead": 0,
            "behind": 3,
            "lastCommit": {
                "hash": "1c40ba2",
                "message": "add memory management skill",
                "author": "matrueba",
                "at": _ago(86_400),
            },
        },
        {
            "path": "/root/matrueba-AI-development-framework",
            "name": "matrueba-AI-development-framework",
            "branch": "main",
            "defaultBranch": "main",
            "remote": "https://github.com/matrueba/matrueba-AI-development-framework.git",
            "dirty": True,
            "changedFiles": 2,
            "ahead": 0,
            "behind": 0,
            "lastCommit": {
                "hash": "9ee1f30",
                "message": "document the reviewer agent contract",
                "author": "matrueba",
                "at": _ago(172_800),
            },
        },
        {
            "path": "/root/dotfiles",
            "name": "dotfiles",
            "branch": "main",
            "defaultBranch": "main",
            "remote": None,
            "dirty": False,
            "changedFiles": 0,
            "ahead": 0,
            "behind": 0,
            "lastCommit": {
                "hash": "5b7c118",
                "message": "tweak zsh prompt colours",
                "author": "matrueba",
                "at": _ago(604_800),
            },
        },
    ]


def get_mock_sessions() -> tuple[list[dict], dict]:
    """Return (sessions, totals) mirroring the monitoring adapter contract."""
    sessions = [
        {
            "AI": "CL",
            "Project": "mathtools",
            "SessionId": "f28159ce-5777-4830-b530-08f5df62605e",
            "Summary": "Add a web UI to control agents with a left navbar",
            "Model": "claude-opus-4.6",
            "Status": "Work",
            "TurnCount": 42,
            "LastContext": 128_400,
            "ContextWindow": 200_000,
            "TotalTokens": 1_284_500,
            "InputTokens": 84_200,
            "OutputTokens": 31_800,
            "CacheR": 1_098_500,
            "CacheW": 70_000,
            "Quota": {"five_hour_pct": 34.2, "seven_day_pct": 61.8},
            "mtime": _ago(4),
            "Children": [
                {"pid": "48213", "name": "npm run dev", "mem": "142M"},
                {"pid": "48277", "name": "pytest -q", "mem": "64M"},
            ],
            "Subagents": [
                {"label": "Explore frontend conventions", "status": "done", "tokens": "12.4k"},
                {"label": "Draft FastAPI routes", "status": "work", "tokens": "5.4k"},
            ],
            "PIDs": ["48120", "48213", "48277"],
            "ProjectPath": "/root/mathtools",
        },
        {
            "AI": "CL",
            "Project": "matrueba-skills-framework",
            "SessionId": "a71b93de-2c04-4f19-9e88-1d6b0aa4c221",
            "Summary": "Refactor the memory skill to support nested vaults",
            "Model": "claude-sonnet-4.6",
            "Status": "Wait",
            "TurnCount": 18,
            "LastContext": 47_900,
            "ContextWindow": 200_000,
            "TotalTokens": 412_300,
            "InputTokens": 38_100,
            "OutputTokens": 12_400,
            "CacheR": 341_800,
            "CacheW": 20_000,
            "Quota": None,
            "mtime": _ago(320),
            "Children": [],
            "Subagents": [
                {"label": "Audit skill manifests", "status": "done", "tokens": "8.1k"},
            ],
            "PIDs": ["47021"],
            "ProjectPath": "/root/matrueba-skills-framework",
        },
        {
            "AI": "CL",
            "Project": "matrueba-AI-development-framework",
            "SessionId": "3f5c81a0-9db7-4c66-b3a2-77e0c4915de3",
            "Summary": "Write the agent specification for the reviewer role",
            "Model": "claude-opus-4.6",
            "Status": "Wait",
            "TurnCount": 7,
            "LastContext": 172_600,
            "ContextWindow": 200_000,
            "TotalTokens": 688_900,
            "InputTokens": 52_700,
            "OutputTokens": 19_300,
            "CacheR": 586_900,
            "CacheW": 30_000,
            "Quota": None,
            "mtime": _ago(1_840),
            "Children": [],
            "Subagents": [],
            "PIDs": [],
            "ProjectPath": "/root/matrueba-AI-development-framework",
        },
        {
            "AI": "CL",
            "Project": "dotfiles",
            "SessionId": "c904e7b1-6a55-4f2d-8c31-2b9f7d0e4a18",
            "Summary": "Fix the zsh prompt so it shows the active venv",
            "Model": "claude-sonnet-4.6",
            "Status": "Wait",
            "TurnCount": 3,
            "LastContext": 18_200,
            "ContextWindow": 200_000,
            "TotalTokens": 96_400,
            "InputTokens": 14_900,
            "OutputTokens": 4_100,
            "CacheR": 71_400,
            "CacheW": 6_000,
            "Quota": None,
            "mtime": _ago(7_200),
            "Children": [],
            "Subagents": [],
            "PIDs": [],
            "ProjectPath": "/root/dotfiles",
        },
        # A second session in an already-tracked project, so the Projects view
        # has something to group.
        {
            "AI": "CL",
            "Project": "mathtools",
            "SessionId": "b1d4770e-8e13-42aa-9c05-6f2a1e8b3c47",
            "Summary": "Document the monitoring adapter contract in CLAUDE.md",
            "Model": "claude-sonnet-4.6",
            "Status": "Wait",
            "TurnCount": 11,
            "LastContext": 61_300,
            "ContextWindow": 200_000,
            "TotalTokens": 238_700,
            "InputTokens": 21_400,
            "OutputTokens": 8_900,
            "CacheR": 196_400,
            "CacheW": 12_000,
            "Quota": None,
            "mtime": _ago(2_650),
            "Children": [],
            "Subagents": [],
            "PIDs": [],
            "ProjectPath": "/root/mathtools",
        },
        {
            "AI": "CL",
            "Project": "matrueba-skills-framework",
            "SessionId": "d5e0c318-7b92-4a01-8f6d-3c9e5a2b7104",
            "Summary": "Add a changelog generator skill",
            "Model": "claude-opus-4.6",
            "Status": "Wait",
            "TurnCount": 24,
            "LastContext": 94_100,
            "ContextWindow": 200_000,
            "TotalTokens": 521_600,
            "InputTokens": 44_800,
            "OutputTokens": 16_200,
            "CacheR": 434_600,
            "CacheW": 26_000,
            "Quota": None,
            "mtime": _ago(11_500),
            "Children": [],
            "Subagents": [],
            "PIDs": [],
            "ProjectPath": "/root/matrueba-skills-framework",
        },
        # ── Other providers ────────────────────────────────────────────────
        # Deliberately uneven: Opencode reports no quota, Codex reports neither
        # quota nor cache tokens and cannot report a turn count. The UI must
        # render "—" for what a provider does not expose rather than a zero.
        {
            "AI": "OC",
            "Project": "mathtools",
            "SessionId": "0f7a2c94-51de-4b83-a7c2-9e1d40b5f386",
            "Summary": "Port the installer tests to pytest fixtures",
            "Model": "minimax-m2.5-free",
            "Status": "Work",
            "TurnCount": 9,
            "LastContext": 42_800,
            "ContextWindow": 200_000,
            "TotalTokens": 187_300,
            "InputTokens": 26_500,
            "OutputTokens": 9_800,
            "CacheR": 143_000,
            "CacheW": 8_000,
            "Quota": None,
            "mtime": _ago(38),
            "Children": [],
            "Subagents": [],
            "PIDs": ["49233"],
            "ProjectPath": "/root/mathtools",
        },
        {
            "AI": "CX",
            "Project": "mathtools",
            "SessionId": "6c1e8b70-3a44-4d92-b015-8f27c9a3e5d1",
            "Summary": "Generate type stubs for the monitoring adapters",
            "Model": "gpt-5-codex",
            "Status": "Wait",
            "TurnCount": None,
            "LastContext": 31_500,
            "ContextWindow": 128_000,
            "TotalTokens": 74_200,
            "InputTokens": 58_900,
            "OutputTokens": 15_300,
            # None, not 0: Codex does not report cache usage at all, and the UI
            # must show "—" rather than a zero it would read as "no cache hits".
            "CacheR": None,
            "CacheW": None,
            "Quota": None,
            "mtime": _ago(5_400),
            "Children": [],
            "Subagents": [],
            "PIDs": [],
            "ProjectPath": "/root/mathtools",
        },
        {
            "AI": "OC",
            "Project": "matrueba-AI-development-framework",
            "SessionId": "e83f5a26-9c17-4b60-8d34-2a7e6f019b45",
            "Summary": "Align the command templates across environments",
            "Model": "minimax-m2.5-free",
            "Status": "Wait",
            "TurnCount": 6,
            "LastContext": 22_400,
            "ContextWindow": 200_000,
            "TotalTokens": 98_100,
            "InputTokens": 17_300,
            "OutputTokens": 6_200,
            "CacheR": 70_600,
            "CacheW": 4_000,
            "Quota": None,
            "mtime": _ago(21_600),
            "Children": [],
            "Subagents": [],
            "PIDs": [],
            "ProjectPath": "/root/matrueba-AI-development-framework",
        },
    ]

    # `or 0` because a provider may report a field as None (unavailable).
    totals = {
        "input": sum(s["InputTokens"] or 0 for s in sessions),
        "output": sum(s["OutputTokens"] or 0 for s in sessions),
        "cacheR": sum(s["CacheR"] or 0 for s in sessions),
        "cacheW": sum(s["CacheW"] or 0 for s in sessions),
    }

    return sessions, totals


# ── Chat history ────────────────────────────────────────────────────────────
# Real transcripts come from each provider's own store (Claude's JSONL, the
# Opencode SQLite `message` table, …). The shape here is the normalised one the
# UI consumes, so each adapter only has to map into it.

_CHAT_BY_SESSION = {
    "f28159ce-5777-4830-b530-08f5df62605e": [
        {
            "role": "user",
            "text": "En src/frontend quiero añadir una nueva funcionalidad para "
                    "controlar los agentes a través de una ui web.",
            "at": _ago(920),
        },
        {
            "role": "assistant",
            "text": "El repo es Python puro y `src/frontend` está vacío. La elección "
                    "de stack condiciona el instalador, así que te pregunto antes de "
                    "escribir código.",
            "at": _ago(900),
            "tokens": {"input": 12_400, "output": 380},
        },
        {
            "role": "tool",
            "text": "Read(src/constants/environments.py)",
            "at": _ago(880),
            "tool": {"name": "Read", "status": "ok"},
        },
        {
            "role": "user",
            "text": "React + Vite, y añade un fastapi a python con datos mock.",
            "at": _ago(700),
        },
        {
            "role": "assistant",
            "text": "Perfecto. Empiezo por el backend, que define el contrato de la API.",
            "at": _ago(690),
            "tokens": {"input": 18_900, "output": 1_240},
        },
        {
            "role": "tool",
            "text": "Bash(npm run build)",
            "at": _ago(320),
            "tool": {"name": "Bash", "status": "ok"},
        },
        {
            "role": "assistant",
            "text": "El build compila. Al capturar la vista he encontrado un bug real: "
                    "la tarjeta Token usage se solapaba con la tabla.",
            "at": _ago(60),
            "tokens": {"input": 31_200, "output": 2_100},
        },
    ],
    "0f7a2c94-51de-4b83-a7c2-9e1d40b5f386": [
        {"role": "user", "text": "Migra los tests del installer a fixtures de pytest.", "at": _ago(400)},
        {
            "role": "assistant",
            "text": "Voy a mover los ZIP de ejemplo a conftest.py para que "
                    "test_cli_installer los reutilice.",
            "at": _ago(380),
            "tokens": {"input": 8_100, "output": 640},
        },
        {
            "role": "tool",
            "text": "Edit(tests/conftest.py)",
            "at": _ago(200),
            "tool": {"name": "Edit", "status": "ok"},
        },
        {"role": "user", "text": "Añade también un fixture para el vault.", "at": _ago(60)},
    ],
    "6c1e8b70-3a44-4d92-b015-8f27c9a3e5d1": [
        {"role": "user", "text": "Genera type stubs para los adaptadores de monitoring.", "at": _ago(5_600)},
        {
            "role": "assistant",
            "text": "He generado .pyi para claude_source y opencode_source. "
                    "gemini_source usa dicts heterogéneos, lo dejo fuera.",
            "at": _ago(5_400),
            "tokens": {"input": 58_900, "output": 15_300},
        },
    ],
}


def get_mock_chat(session_id: str) -> list[dict]:
    """
    Normalised chat transcript for a session.

    Sessions with no scripted transcript return a short placeholder rather than
    an empty list, so the UI always has something to render.
    """
    if session_id in _CHAT_BY_SESSION:
        return _CHAT_BY_SESSION[session_id]

    return [
        {
            "role": "user",
            "text": "No transcript captured for this session yet.",
            "at": _ago(3_600),
        },
    ]


# ── Harness ─────────────────────────────────────────────────────────────────
# What each provider's framework folder contains inside a project — the output
# of the installer, read back. Keyed by project path, then by provider id.
# Providers absent from a project's entry are simply not installed there.

_HARNESS_BY_PROJECT = {
    "/root/mathtools": {
        "claude": {
            "scope": "local",
            "installedAt": _ago(86_400 * 3),
            "updateAvailable": True,
            "components": {
                "agents": [
                    {"name": "reviewer", "description": "Reviews diffs for correctness"},
                    {"name": "planner", "description": "Breaks work into ordered steps"},
                ],
                "commands": [
                    {"name": "commit", "description": "Conventional commit with a summary"},
                    {"name": "review", "description": "Review the current branch"},
                    {"name": "changelog", "description": "Draft release notes"},
                ],
                "skills": [
                    {"name": "memory-management", "description": "Obsidian vault access"},
                    {"name": "spec-driven-dev", "description": "Spec-first workflow"},
                ],
            },
        },
        "opencode": {
            "scope": "global",
            "installedAt": _ago(86_400 * 12),
            "updateAvailable": False,
            "components": {
                "agents": [{"name": "reviewer", "description": "Reviews diffs for correctness"}],
                "commands": [{"name": "commit", "description": "Conventional commit with a summary"}],
                "skills": [{"name": "memory-management", "description": "Obsidian vault access"}],
            },
        },
    },
    "/root/matrueba-skills-framework": {
        "claude": {
            "scope": "local",
            "installedAt": _ago(86_400 * 20),
            "updateAvailable": True,
            "components": {
                "agents": [{"name": "planner", "description": "Breaks work into ordered steps"}],
                "commands": [],
                "skills": [
                    {"name": "memory-management", "description": "Obsidian vault access"},
                    {"name": "changelog-generator", "description": "Release notes from git log"},
                    {"name": "spec-driven-dev", "description": "Spec-first workflow"},
                ],
            },
        },
    },
    "/root/matrueba-AI-development-framework": {
        "gemini": {
            "scope": "local",
            "installedAt": _ago(86_400 * 5),
            "updateAvailable": False,
            "components": {
                "agents": [{"name": "reviewer", "description": "Reviews diffs for correctness"}],
                "commands": [{"name": "review", "description": "Review the current branch"}],
                "skills": [],
            },
        },
    },
}


def get_mock_harness(project_path: str) -> dict:
    """Installed harness per provider id for one project. Empty if none."""
    return _HARNESS_BY_PROJECT.get(project_path, {})
