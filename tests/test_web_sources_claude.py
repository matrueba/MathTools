import json
import os
import time

import pytest

from web.sources import claude
from web.sources.claude import parse_claude_sessions

CWD = "/home/dev/my_repo"


def _write(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _assistant(msg_id, block, usage, model="claude-opus-4.6"):
    return {
        "type": "assistant",
        "cwd": CWD,
        "message": {"id": msg_id, "model": model, "content": [block], "usage": usage},
    }


USAGE = {
    "input_tokens": 10,
    "output_tokens": 20,
    "cache_read_input_tokens": 100,
    "cache_creation_input_tokens": 5,
}


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    claude._cache.clear()
    # Never read the real live-process registry.
    monkeypatch.setattr(claude, "LIVE_SESSIONS_DIR", str(tmp_path / "live"))


@pytest.fixture
def base(tmp_path):
    root = tmp_path / "projects"
    project = root / "-home-dev-my-repo"  # lossy encoding: "_" became "-"
    _write(project / "s1.jsonl", [
        {"type": "user", "cwd": CWD, "message": {"role": "user", "content": "fix the bug"}},
        # One message split across two records, each repeating the usage.
        _assistant("m1", {"type": "thinking"}, USAGE),
        _assistant("m1", {"type": "tool_use", "name": "Bash"}, USAGE),
        {"type": "user", "cwd": CWD, "message": {"content": [{"type": "tool_result"}]}},
        _assistant("m2", {"type": "text"}, USAGE),
        {"type": "ai-title", "aiTitle": "Fix\nthe bug"},
        "not json at all",
    ])
    return root


def test_parses_session_in_the_monitoring_contract(base):
    sessions, totals = parse_claude_sessions(base_dir=base)

    assert len(sessions) == 1
    s = sessions[0]
    assert s["AI"] == "CL"
    assert s["SessionId"] == "s1"
    # The real cwd, not the lossy folder name.
    assert s["ProjectPath"] == CWD
    assert s["Project"] == "my_repo"
    assert s["Summary"] == "Fix the bug"
    assert s["Model"] == "claude-opus-4.6"
    # A model missing from MODEL_CONTEXT_WINDOW["claude"] gets the default.
    assert s["ContextWindow"] == claude.DEFAULT_CONTEXT_WINDOW
    # Tool results are not turns.
    assert s["TurnCount"] == 1
    assert s["Status"] == "Work"  # just written


def test_usage_is_counted_once_per_message(base):
    sessions, totals = parse_claude_sessions(base_dir=base)
    s = sessions[0]

    # m1 appears twice but counts once: 2 messages, not 3.
    assert s["InputTokens"] == 20
    assert s["OutputTokens"] == 40
    assert s["CacheR"] == 200
    assert s["CacheW"] == 10
    assert s["TotalTokens"] == 270
    assert s["LastContext"] == 115
    assert totals == {"input": 20, "output": 40, "cacheR": 200, "cacheW": 10}


def test_old_transcripts_are_waiting(base):
    transcript = base / "-home-dev-my-repo" / "s1.jsonl"
    old = time.time() - 3600
    os.utime(transcript, (old, old))

    s = parse_claude_sessions(base_dir=base)[0][0]
    assert s["Status"] == "Wait"
    assert s["mtime"] == pytest.approx(old)


def test_subagents_are_listed_and_added_to_the_session(base):
    folder = base / "-home-dev-my-repo" / "s1" / "subagents"
    _write(folder / "agent-abc.jsonl", [_assistant("x1", {"type": "text"}, USAGE)])
    (folder / "agent-abc.meta.json").write_text(
        json.dumps({"agentType": "Explore", "description": "Find the routes"})
    )

    s = parse_claude_sessions(base_dir=base)[0][0]
    assert s["Subagents"] == [
        {"label": "Find the routes", "type": "Explore", "status": "work", "tokens": 135}
    ]
    assert s["TotalTokens"] == 270 + 135


def test_summary_falls_back_to_the_first_prompt(tmp_path):
    root = tmp_path / "projects"
    _write(root / "p" / "s.jsonl", [
        {"type": "user", "cwd": CWD, "message": {"content": [{"type": "text", "text": "hello  there"}]}},
    ])
    s = parse_claude_sessions(base_dir=root)[0][0]
    assert s["Summary"] == "hello there"
    assert s["Model"] == "-"
    assert s["TotalTokens"] == 0


def test_transcripts_without_cwd_are_skipped(tmp_path):
    root = tmp_path / "projects"
    _write(root / "p" / "s.jsonl", [{"type": "queue-operation"}])
    assert parse_claude_sessions(base_dir=root) == ([], {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0})


def test_missing_base_dir_is_empty(tmp_path):
    sessions, totals = parse_claude_sessions(base_dir=tmp_path / "nope")
    assert sessions == []


def _register(tmp_path, pid, session_id, **extra):
    live = tmp_path / "live"
    live.mkdir(exist_ok=True)
    (live / f"{pid}.json").write_text(json.dumps({"pid": pid, "sessionId": session_id, **extra}))


def test_live_pids_come_from_the_registry(base, tmp_path, monkeypatch):
    _register(tmp_path, 123, "s1", entrypoint="claude-vscode")
    _register(tmp_path, 456, "other")
    _register(tmp_path, 789, "s1")  # registry file outlived its process
    monkeypatch.setattr(claude, "_process_alive", lambda pid, start: pid in ("123", "456"))

    s = parse_claude_sessions(base_dir=base)[0][0]
    assert s["PIDs"] == ["123"]
    assert s["LiveIn"] == ["claude-vscode"]


def test_processes_the_dashboard_spawned_do_not_count_as_live(base, tmp_path, monkeypatch):
    _register(tmp_path, 123, "s1", entrypoint="cli")
    monkeypatch.setattr(claude, "_process_alive", lambda pid, start: True)
    monkeypatch.setattr(claude, "DASHBOARD_PIDS", {"123"})

    s = parse_claude_sessions(base_dir=base)[0][0]
    assert s["PIDs"] == [] and s["LiveIn"] == []


def test_a_reused_pid_is_not_the_registered_process(monkeypatch):
    pid = str(os.getpid())
    with open(f"/proc/{pid}/stat") as f:
        start = f.read().rpartition(")")[2].split()[19]

    assert claude._process_alive(pid, start)
    assert claude._process_alive(pid, None)  # older registry entries
    assert not claude._process_alive(pid, str(int(start) + 1))
    assert not claude._process_alive("999999999", None)


def test_read_transcript_finds_the_session_in_any_project_folder(base):
    records = claude.read_transcript("s1", base_dir=base)
    assert records[0]["message"]["content"] == "fix the bug"
    assert claude.read_transcript("missing", base_dir=base) == []
    assert claude.read_transcript("../s1", base_dir=base) == []


def test_unchanged_transcripts_are_served_from_cache(base, monkeypatch):
    parse_claude_sessions(base_dir=base)

    def boom(*a, **k):
        raise AssertionError("re-read an unchanged transcript")

    monkeypatch.setattr("builtins.open", boom)
    assert parse_claude_sessions(base_dir=base)[0][0]["SessionId"] == "s1"


def test_project_path_keeps_only_that_projects_sessions(base):
    assert len(parse_claude_sessions(CWD, base_dir=base)[0]) == 1
    sessions, totals = parse_claude_sessions("/somewhere/else", base_dir=base)
    assert sessions == []
    assert totals == {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}


def test_context_window_is_looked_up_by_the_recorded_api_id(tmp_path, monkeypatch):
    monkeypatch.setattr("web.sources.models.MODEL_CONTEXT_WINDOW", {"claude": {"haiku-4.5": 200_000}})
    _write(tmp_path / "p" / "s.jsonl", [
        {"type": "user", "cwd": CWD, "message": {"content": "hi"}},
        _assistant("m1", {"type": "text"}, USAGE, model="claude-haiku-4-5-20251001"),
    ])
    assert parse_claude_sessions(base_dir=tmp_path)[0][0]["ContextWindow"] == 200_000
