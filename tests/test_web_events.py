"""Live updates: snapshot diffing, fan-out to subscribers, SSE framing."""

import asyncio
import json
import os
import subprocess

from web.data import DataStore
from web.events import EventHub, format_sse


class FakeStore:
    """Serves a scripted sequence of snapshots, repeating the last one."""

    def __init__(self, *snapshots):
        self.snapshots = list(snapshots)
        self.calls = 0

    def live_snapshot(self):
        self.calls += 1
        return self.snapshots[min(self.calls, len(self.snapshots)) - 1]


def _frames(chunks):
    """Parse SSE text into (event, payload) pairs, skipping comments and retry."""
    events = []
    for frame in "".join(chunks).split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in frame.splitlines() if not line.startswith(":") and ": " in line
        )
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


# ── diff ────────────────────────────────────────────────────────────────────

def test_first_snapshot_sends_everything():
    hub = EventHub(FakeStore())
    events = hub.diff({"projects": ("projects", {"n": 1}), "agents": ("agents", {"n": 2})})
    assert events == [("projects", {"n": 1}), ("agents", {"n": 2})]


def test_only_changed_keys_are_sent_again():
    hub = EventHub(FakeStore())
    hub.diff({"projects": ("projects", {"n": 1}), "project:a": ("project", {"id": "a"})})

    events = hub.diff({"projects": ("projects", {"n": 2}), "project:a": ("project", {"id": "a"})})
    assert events == [("projects", {"n": 2})]
    assert hub.diff({"projects": ("projects", {"n": 2}), "project:a": ("project", {"id": "a"})}) == []


def test_key_order_inside_a_payload_is_not_a_change():
    hub = EventHub(FakeStore())
    hub.diff({"agents": ("agents", {"a": 1, "b": 2})})
    assert hub.diff({"agents": ("agents", {"b": 2, "a": 1})}) == []


def test_format_sse_is_one_frame():
    frame = format_sse("project", {"id": "x", "text": "line\nbreak"})
    assert frame.startswith("event: project\ndata: ")
    assert frame.endswith("\n\n")
    assert frame.count("\n") == 3  # the newline in the payload stays escaped


# ── subscribers and the ticking task ────────────────────────────────────────

def test_subscribers_get_changes_and_the_task_stops_with_the_last_one():
    store = FakeStore(
        {"projects": ("projects", {"n": 1})},
        {"projects": ("projects", {"n": 2})},
    )

    async def scenario():
        hub = EventHub(store, interval=0.01)
        queue = hub.subscribe()
        first = await asyncio.wait_for(queue.get(), 1)
        second = await asyncio.wait_for(queue.get(), 1)
        # The third snapshot repeats the second: nothing more is sent.
        await asyncio.sleep(0.05)
        assert queue.empty()

        task = hub._task
        hub.unsubscribe(queue)
        await asyncio.sleep(0)
        return first, second, task.cancelled() or task.done(), hub._task

    first, second, stopped, task = asyncio.run(scenario())
    assert first == ("projects", {"n": 1})
    assert second == ("projects", {"n": 2})
    assert stopped and task is None


def test_a_late_subscriber_starts_from_the_current_snapshot():
    store = FakeStore({"projects": ("projects", {"n": 1}), "agents": ("agents", {})})

    async def scenario():
        hub = EventHub(store, interval=0.01)
        early = hub.subscribe()
        await asyncio.wait_for(early.get(), 1)
        late = hub.subscribe()
        received = [late.get_nowait(), late.get_nowait()]
        hub.unsubscribe(early)
        hub.unsubscribe(late)
        return received

    assert asyncio.run(scenario()) == [("projects", {"n": 1}), ("agents", {})]


def test_a_failing_snapshot_does_not_end_the_stream():
    class Flaky(FakeStore):
        def live_snapshot(self):
            self.calls += 1
            if self.calls == 1:
                raise OSError("repo mid-rewrite")
            return {"projects": ("projects", {"ok": True})}

    async def scenario():
        hub = EventHub(Flaky(), interval=0.01)
        queue = hub.subscribe()
        event = await asyncio.wait_for(queue.get(), 1)
        hub.unsubscribe(queue)
        return event

    assert asyncio.run(scenario()) == ("projects", {"ok": True})


def test_stream_yields_frames_keepalives_and_unsubscribes_on_close():
    store = FakeStore({"projects": ("projects", {"n": 1})})

    async def scenario():
        hub = EventHub(store, interval=0.01, keepalive=0.02)
        stream = hub.stream()
        chunks = [await stream.__anext__() for _ in range(3)]
        await stream.aclose()  # what Starlette does when the client goes away
        return chunks, hub._subscribers

    chunks, subscribers = asyncio.run(scenario())
    assert chunks[0].startswith("retry: ")
    assert _frames(chunks) == [("projects", {"n": 1})]
    assert chunks[2] == ": keepalive\n\n"
    assert subscribers == set()


# ── DataStore.live_snapshot matches the REST routes ─────────────────────────

def test_live_snapshot_payloads_equal_the_rest_bodies(web_client):
    store: DataStore = web_client.app.state.data_store
    snapshot = store.live_snapshot()

    assert set(snapshot) == {"projects", "agents", "project:mathtools", "project:dotfiles"}
    assert snapshot["projects"] == ("projects", web_client.get("/api/projects").json())
    assert snapshot["agents"] == ("agents", web_client.get("/api/agents").json())
    assert snapshot["project:mathtools"] == (
        "project",
        web_client.get("/api/projects/mathtools").json(),
    )


def test_git_state_is_cached_until_git_touches_the_repo(web_client, monkeypatch):
    store: DataStore = web_client.app.state.data_store
    path = web_client.repo_paths["mathtools"]
    store._git_state(path)

    calls = []
    monkeypatch.setattr("web.data.run_git", lambda *args: calls.append(args))
    store._git_state(path)
    assert calls == []  # served from the cache

    monkeypatch.undo()
    identity = {f"GIT_{who}_{field}": value for who in ("AUTHOR", "COMMITTER")
                for field, value in (("NAME", "t"), ("EMAIL", "t@t"))}
    subprocess.run(["git", "-C", path, "commit", "-q", "--allow-empty", "-m", "x"],
                   check=True, env={**os.environ, **identity})
    assert store._git_state(path)["lastCommit"]["message"] == "x"


def test_git_state_expires_on_a_timer(web_client, monkeypatch):
    store: DataStore = web_client.app.state.data_store
    path = web_client.repo_paths["mathtools"]
    store._git_state(path)

    monkeypatch.setattr("web.data.GIT_REFRESH_SECONDS", 0)
    store._git_cache[path] = (0, *store._git_cache[path][1:])  # already expired
    calls = []
    monkeypatch.setattr("web.data.run_git", lambda *args: calls.append(args))
    store._git_state(path)
    assert calls


def test_close_ends_every_open_stream():
    store = FakeStore({"projects": ("projects", {"n": 1})})

    async def scenario():
        hub = EventHub(store, interval=0.01, keepalive=5)
        stream = hub.stream()
        await stream.__anext__()  # retry
        await stream.__anext__()  # snapshot
        hub.close()
        rest = [chunk async for chunk in stream]  # must terminate, not hang
        return rest, hub._subscribers

    rest, subscribers = asyncio.run(asyncio.wait_for(scenario(), 2))
    assert rest == []
    assert subscribers == set()
