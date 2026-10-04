"""
Live updates for the dashboard over Server-Sent Events.

The state the dashboard shows lives in files other tools write (Claude Code
transcripts, git repositories), and nothing notifies us when they change. So
the polling does not go away — it moves here, done once for every connected
browser instead of once per browser per view:

    EventHub._run, every LIVE_INTERVAL_SECONDS
        DataStore.live_snapshot()      (in a worker thread: file IO and git)
        diff against the last snapshot, by key
        push each changed (event, payload) to every subscriber's queue

Payloads are the exact bodies of the matching REST routes, so the frontend
loads a view over REST and then simply replaces its data with each event:

    event: projects   ← GET /api/projects
    event: agents     ← GET /api/agents
    event: project    ← GET /api/projects/{id}   (one per project that changed)

A new subscriber is first sent the whole current snapshot, which also makes a
reconnect resynchronise without the client refetching anything. The ticking
task runs only while someone is connected.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from constants.web import LIVE_INTERVAL_SECONDS, LIVE_KEEPALIVE_SECONDS

from .data import DataStore

log = logging.getLogger(__name__)

Event = tuple[str, dict]


def format_sse(event: str, payload: dict) -> str:
    """One SSE frame. JSON never contains a raw newline, so one data line suffices."""
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


class EventHub:
    """Computes live snapshots and fans changes out to SSE subscribers."""

    def __init__(
        self,
        data_store: DataStore,
        interval: float = LIVE_INTERVAL_SECONDS,
        keepalive: float = LIVE_KEEPALIVE_SECONDS,
    ):
        self.data_store = data_store
        self.interval = interval
        self.keepalive = keepalive
        self._subscribers: set[asyncio.Queue] = set()
        # key -> (event, payload, serialized payload) as last sent. The
        # serialized form is what changes are detected on.
        self._last: dict[str, tuple[str, dict, str]] = {}
        self._task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Diffing ────────────────────────────────────────────────────────────
    def diff(self, snapshot: dict[str, Event]) -> list[Event]:
        """
        Events for every key whose payload differs from the last snapshot.

        Updates the remembered snapshot. Keys that disappeared are dropped
        silently: there is no project deletion yet, so nothing to announce.
        """
        changed, current = [], {}
        for key, (event, payload) in snapshot.items():
            serialized = json.dumps(payload, sort_keys=True)
            current[key] = (event, payload, serialized)
            previous = self._last.get(key)
            if previous is None or previous[2] != serialized:
                changed.append((event, payload))
        self._last = current
        return changed

    # ── Subscribers ────────────────────────────────────────────────────────
    def subscribe(self) -> asyncio.Queue:
        """
        Register a subscriber and start ticking if it is the first.

        The queue is pre-filled with the current snapshot. Before the first
        tick has run there is none, and that tick sends everything anyway.
        """
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        for event, payload, _ in self._last.values():
            queue.put_nowait((event, payload))
        self._subscribers.add(queue)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Drop a subscriber; the last one out stops the ticking task."""
        self._subscribers.discard(queue)
        if not self._subscribers and self._task is not None:
            self._task.cancel()
            self._task = None
            # Nobody is watching, so the remembered snapshot would only go
            # stale; the next first subscriber starts from scratch.
            self._last = {}

    def close(self) -> None:
        """
        End every open stream (each gets a `None` sentinel).

        Called on server shutdown: an SSE response never finishes by itself,
        so without this the server would sit out its whole graceful-shutdown
        timeout and then cancel the streams with a traceback. Safe to call
        from a signal handler or another thread.
        """
        if self._loop is None or self._loop.is_closed():
            return

        def end_streams():
            for queue in self._subscribers:
                queue.put_nowait(None)

        self._loop.call_soon_threadsafe(end_streams)

    async def _run(self) -> None:
        while True:
            try:
                snapshot = await asyncio.to_thread(self.data_store.live_snapshot)
            except Exception:
                # One failed read (a repo mid-rewrite, a locked DB) must not
                # end the stream for everyone; try again next tick.
                log.exception("Live snapshot failed")
            else:
                for event in self.diff(snapshot):
                    for queue in self._subscribers:
                        queue.put_nowait(event)
            await asyncio.sleep(self.interval)

    # ── One client's stream ────────────────────────────────────────────────
    async def stream(self) -> AsyncIterator[str]:
        """
        SSE frames for one client, until it disconnects.

        Starlette cancels this generator when the client goes away; the
        `finally` is what unsubscribes it.
        """
        queue = self.subscribe()
        try:
            # Tells EventSource how long to wait before reconnecting.
            yield "retry: 3000\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), self.keepalive)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is None:  # `close()`: the server is shutting down
                    return
                yield format_sse(*item)
        finally:
            self.unsubscribe(queue)
