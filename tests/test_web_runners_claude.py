"""Driving a Claude Code session: event translation, history and the routes."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import web.data
import web.routes.sessions
from web.runners.claude import ClaudeRunner, SessionBusyError, history_events, translate_event
from web.sources.claude import DASHBOARD_PIDS
from web.server import create_app

SESSION_ID = "abc-123"


# ── translate_event ─────────────────────────────────────────────────────────

def test_init_becomes_start():
    events = translate_event({"type": "system", "subtype": "init", "session_id": "s", "model": "m"})
    assert events == [{"type": "start", "sessionId": "s", "model": "m"}]


def test_only_text_deltas_are_forwarded_not_the_whole_message():
    delta = {
        "type": "stream_event",
        "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}},
    }
    whole = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hi"}]}}
    thinking = {
        "type": "stream_event",
        "event": {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "x"}},
    }

    assert translate_event(delta) == [{"type": "text", "text": "Hi"}]
    assert translate_event(whole) == []
    assert translate_event(thinking) == []


def test_tool_use_and_its_result():
    call = {
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls  -la"}},
        ]},
    }
    result = {
        "type": "user",
        "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
             "content": [{"type": "text", "text": "boom"}]},
        ]},
    }

    assert translate_event(call) == [{"type": "tool", "id": "t1", "name": "Bash", "summary": "ls -la"}]
    assert translate_event(result) == [
        {"type": "tool_result", "id": "t1", "isError": True, "text": "boom"}
    ]


def test_subagent_traffic_is_dropped():
    record = {
        "type": "assistant",
        "parent_tool_use_id": "t1",
        "message": {"content": [{"type": "tool_use", "id": "t2", "name": "Read", "input": {}}]},
    }
    assert translate_event(record) == []


def test_result_reports_cost_and_denials():
    (done,) = translate_event({
        "type": "result",
        "is_error": False,
        "result": "final text",
        "total_cost_usd": 0.02,
        "duration_ms": 1500,
        "num_turns": 3,
        "permission_denials": [{"tool_name": "Edit"}],
    })
    assert done == {
        "type": "done",
        "isError": False,
        "result": None,
        "costUsd": 0.02,
        "durationMs": 1500,
        "turns": 3,
        "denied": ["Edit"],
    }


def test_unknown_and_malformed_records_are_ignored():
    assert translate_event({"type": "rate_limit_event"}) == []
    assert translate_event({"type": "user", "message": {"content": "plain"}}) == []
    assert translate_event("nope") == []


# ── history_events ──────────────────────────────────────────────────────────

def _user(content, **extra):
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


def _assistant(*blocks, **extra):
    return {"type": "assistant", "message": {"content": list(blocks)}, **extra}


def test_history_replays_a_turn_in_the_chat_vocabulary():
    events = history_events([
        _user("fix the bug", timestamp="2026-10-05T00:00:00Z"),
        _assistant({"type": "thinking", "thinking": "hmm"}),
        _assistant({"type": "text", "text": "Looking."}),
        _assistant({"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}),
        _user([{"type": "tool_result", "tool_use_id": "t1", "content": "a.py"}]),
        _assistant({"type": "text", "text": "Done."}),
        {"type": "ai-title", "aiTitle": "x"},
    ])
    assert events == [
        {"type": "prompt", "text": "fix the bug", "at": "2026-10-05T00:00:00Z"},
        {"type": "text", "text": "Looking.", "block": True},
        {"type": "tool", "id": "t1", "name": "Bash", "summary": "ls"},
        {"type": "tool_result", "id": "t1", "isError": False, "text": "a.py"},
        {"type": "text", "text": "Done.", "block": True},
    ]


def test_history_keeps_only_what_the_user_typed():
    (event,) = history_events([_user([
        {"type": "text", "text": "<ide_opened_file>The user opened x.py</ide_opened_file>"},
        {"type": "text", "text": "<ide_selection>lines 1-2</ide_selection>"},
        {"type": "image", "source": {"type": "base64", "data": "..."}},
        {"type": "text", "text": "why <b>this</b>?\n<system-reminder>be nice</system-reminder>"},
    ])])
    assert event["text"] == "[image]\n\nwhy <b>this</b>?"


def test_history_shows_slash_commands_and_unwraps_pastes():
    command = _user("<command-message>review</command-message>\n"
                    "<command-name>/review</command-name>\n<command-args>high</command-args>")
    paste = _user('look:\n<pasted_content id="1">Traceback</pasted_content>')
    assert [e["text"] for e in history_events([command, paste])] == [
        "/review high", "look:\nTraceback",
    ]


def test_history_skips_meta_sidechains_and_empty_context_only_messages():
    events = history_events([
        _user("caveat", isMeta=True),
        _user("subagent prompt", isSidechain=True),
        _assistant({"type": "text", "text": "subagent reply"}, isSidechain=True),
        _user([{"type": "text", "text": "<ide_opened_file>x</ide_opened_file>"}]),
    ])
    assert events == []


def test_history_turns_system_messages_into_notes():
    events = history_events([
        _user("summary of earlier work", isCompactSummary=True),
        _user("<task-notification><task-id>1</task-id></task-notification>"),
    ])
    assert [e["type"] for e in events] == ["note", "note"]


# ── ClaudeRunner against a fake binary ──────────────────────────────────────

@pytest.fixture
def fake_claude(tmp_path):
    """A stand-in CLI that echoes its stdin back as a stream-json turn."""
    script = tmp_path / "claude"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "prompt = sys.stdin.read()\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init', 'session_id': 's', 'model': 'm'}))\n"
        "print('not json')\n"
        "print(json.dumps({'type': 'stream_event', 'event': {'type': 'content_block_delta',\n"
        "    'delta': {'type': 'text_delta', 'text': 'echo: ' + prompt}}}))\n"
        "print(json.dumps({'type': 'result', 'is_error': False, 'num_turns': 1}))\n"
    )
    script.chmod(0o755)
    return str(script)


async def _collect(runner, *args):
    return [e async for e in runner.stream(*args)]


def test_runner_streams_translated_events(fake_claude, tmp_path):
    events = asyncio.run(_collect(ClaudeRunner(fake_claude), SESSION_ID, str(tmp_path), "-hello"))

    assert [e["type"] for e in events] == ["start", "text", "done"]
    # Sent over stdin, so a leading "-" is not parsed as a flag.
    assert events[1]["text"] == "echo: -hello"


def test_runner_marks_its_process_as_the_dashboards_while_it_runs(fake_claude, tmp_path):
    async def scenario():
        stream = ClaudeRunner(fake_claude).stream(SESSION_ID, str(tmp_path), "hi")
        await stream.__anext__()
        during = set(DASHBOARD_PIDS)
        rest = [e async for e in stream]
        return during, rest

    during, _ = asyncio.run(scenario())
    assert len(during) == 1
    assert DASHBOARD_PIDS == set()


def test_runner_reports_a_crash_as_an_error_event(tmp_path):
    script = tmp_path / "claude"
    script.write_text("#!/bin/sh\necho 'No conversation found' >&2\nexit 1\n")
    script.chmod(0o755)

    events = asyncio.run(_collect(ClaudeRunner(str(script)), SESSION_ID, str(tmp_path), "hi"))
    assert events == [{"type": "error", "message": "No conversation found"}]


def test_runner_survives_a_process_that_never_reads_its_prompt(tmp_path):
    script = tmp_path / "claude"
    script.write_text("#!/bin/sh\nexec 0<&-\necho 'bad flag' >&2\nexit 2\n")
    script.chmod(0o755)

    # Big enough to overflow the pipe buffer, so the write itself fails.
    events = asyncio.run(_collect(ClaudeRunner(str(script)), SESSION_ID, str(tmp_path), "x" * 1_000_000))
    assert events == [{"type": "error", "message": "bad flag"}]


def test_runner_refuses_a_second_turn_on_a_busy_session(tmp_path):
    runner = ClaudeRunner("unused")
    runner._running.add(SESSION_ID)
    with pytest.raises(SessionBusyError):
        asyncio.run(_collect(runner, SESSION_ID, str(tmp_path), "hi"))


# ── POST …/sessions/{id}/prompt ─────────────────────────────────────────────

class FakeRunner:
    def __init__(self):
        self.calls = []
        self.busy = False

    def is_running(self, session_id):
        return self.busy

    async def stream(self, session_id, cwd, prompt, permission_mode):
        self.calls.append((session_id, cwd, prompt, permission_mode))
        yield {"type": "text", "text": "ok"}
        yield {"type": "done", "isError": False}


@pytest.fixture
def runner(monkeypatch):
    fake = FakeRunner()
    monkeypatch.setattr(web.routes.sessions, "ClaudeRunner", lambda: fake)
    return fake


@pytest.fixture
def client(tmp_path, monkeypatch, runner):
    repo = tmp_path / "mathtools"
    (repo / ".git").mkdir(parents=True)
    path = str(repo.resolve())

    session = {"AI": "CL", "SessionId": SESSION_ID, "ProjectPath": path, "Status": "Wait", "mtime": 1}

    def load(self, project, agent=None):
        empty = {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}
        if agent == "claude" and project["path"] == path:
            return [session], empty
        return [], empty

    monkeypatch.setattr(web.data.DataStore, "load_agent_sessions", load)
    client = TestClient(create_app(db_path=tmp_path / "mathtools.db"))
    assert client.post("/api/projects", json={"path": path}).status_code == 201
    client.session = session  # tests flip PIDs on it to make it live
    return client


URL = f"/api/projects/mathtools/agents/claude/sessions/{SESSION_ID}/prompt"


def test_prompt_streams_ndjson(client, runner, tmp_path):
    res = client.post(URL, json={"prompt": "  do it  ", "permissionMode": "acceptEdits"})

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/x-ndjson")
    assert [json.loads(line) for line in res.text.splitlines()] == [
        {"type": "text", "text": "ok"},
        {"type": "done", "isError": False},
    ]
    assert runner.calls == [
        (SESSION_ID, str((tmp_path / "mathtools").resolve()), "do it", "acceptEdits")
    ]


def test_prompt_defaults_to_the_safest_mode(client, runner):
    client.post(URL, json={"prompt": "hi"})
    assert runner.calls[0][3] == "manual"


@pytest.mark.parametrize("body", [
    {"prompt": "   "},
    {"prompt": "hi", "permissionMode": "bypassPermissions"},
])
def test_prompt_rejects_bad_input(client, runner, body):
    assert client.post(URL, json=body).status_code == 400
    assert runner.calls == []


def test_prompt_on_a_busy_session_is_409(client, runner):
    runner.busy = True
    assert client.post(URL, json={"prompt": "hi"}).status_code == 409


def test_prompt_on_an_unknown_session_is_404(client, runner):
    url = "/api/projects/mathtools/agents/claude/sessions/nope/prompt"
    assert client.post(url, json={"prompt": "hi"}).status_code == 404


def test_prompt_on_a_session_open_elsewhere_is_409(client, runner):
    client.session["PIDs"] = ["4242"]
    res = client.post(URL, json={"prompt": "hi"})
    assert res.status_code == 409
    assert "another Claude Code client" in res.json()["detail"]
    assert runner.calls == []


# ── GET …/sessions/{id}/history ─────────────────────────────────────────────

HISTORY = f"/api/projects/mathtools/agents/claude/sessions/{SESSION_ID}/history"


def test_history_route_returns_events_and_liveness(client, monkeypatch):
    read = []
    monkeypatch.setattr(web.data, "read_transcript", lambda sid: read.append(sid) or [_user("hello")])

    body = client.get(HISTORY).json()
    assert body == {
        "sessionId": SESSION_ID,
        "live": False,
        "events": [{"type": "prompt", "text": "hello", "at": None}],
    }
    assert read == [SESSION_ID]

    client.session["PIDs"] = ["4242"]
    assert client.get(HISTORY).json()["live"] is True


def test_history_of_an_unknown_session_is_404(client):
    url = "/api/projects/mathtools/agents/claude/sessions/nope/history"
    assert client.get(url).status_code == 404


def test_project_payload_flags_live_sessions(client):
    client.session.update({"PIDs": ["4242"], "LiveIn": ["claude-vscode"]})
    (agent,) = client.get("/api/projects/mathtools").json()["agents"]
    assert agent["sessions"][0]["live"] is True
    assert agent["sessions"][0]["liveIn"] == ["claude-vscode"]
