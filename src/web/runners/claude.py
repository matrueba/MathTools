"""
Drive a Claude Code session from the dashboard.

Each prompt is one headless turn: `claude -p --resume <id>` run in the
project's directory, with `--output-format stream-json` so every step of the
turn arrives as one JSON line while it happens. Claude Code appends the turn to
the same transcript the session reader parses, so the sessions list picks it up
on its next tick with no extra wiring. A session open elsewhere (a terminal,
the VS Code extension) is never driven from here: the route refuses it, since
two writers on one session would fork or interleave it.

The CLI's events are verbose and private (thinking signatures, rate-limit
pings, per-block partials), so `translate_event` reduces them to the handful
the chat UI renders — the same kind of vocabulary boundary `serializers.py`
draws for the monitoring contract:

    {"type": "start",       "sessionId", "model"}
    {"type": "text",        "text"}                    streamed text delta
    {"type": "tool",        "id", "name", "summary"}   the agent called a tool
    {"type": "tool_result", "id", "isError", "text"}
    {"type": "done",        "isError", "result", "costUsd", "durationMs",
                            "turns", "denied"}
    {"type": "error",       "message"}

`history_events` replays a session's transcript in the same vocabulary, so the
chat renders history and live turns with one reducer. It adds:

    {"type": "prompt",      "text", "at"}              what the user typed;
                                                       starts a turn
    {"type": "text",        "text", "block": true}     a whole text block, not
                                                       a delta to append to
    {"type": "note",        "text"}                    something that happened
                                                       between prompts

Subagent traffic (`parent_tool_use_id` set, or `isSidechain` in a transcript)
is dropped: the Task tool call that spawned it already shows in the chat.
"""

import asyncio
import json
import os
import re
import shutil
from collections.abc import AsyncIterator
from pathlib import Path

from ..sources.claude import DASHBOARD_PIDS

# Permission modes the UI may pick. `bypassPermissions` is deliberately left
# out: a browser tab should not be able to switch every safety check off.
# With `--permission-prompts none` nothing can stop to ask, so under
# "manual" any tool that would prompt is denied and reported in `denied`.
PERMISSION_MODES = ("manual", "acceptEdits", "plan", "auto")
DEFAULT_PERMISSION_MODE = "manual"

# Tool results can be whole files; the chat only needs a preview.
RESULT_PREVIEW_CHARS = 2000
SUMMARY_CHARS = 160

# One stream-json line holds a full message, tool results included, so the
# asyncio default of 64 KiB per line is far too small.
LINE_LIMIT = 32 * 1024 * 1024

# Where the official installer puts the binary, for when the dashboard was
# started without ~/.local/bin on PATH.
FALLBACK_BIN = "~/.local/bin/claude"


class SessionBusyError(RuntimeError):
    """A prompt is already running for this session."""


def find_claude_binary() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    fallback = Path(FALLBACK_BIN).expanduser()
    return str(fallback) if fallback.is_file() else None


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _tool_summary(name: str, tool_input) -> str:
    """One line saying what a tool call targets, e.g. the command or path."""
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "file_path", "path", "pattern", "url", "query", "description", "prompt"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return _truncate(" ".join(value.split()), SUMMARY_CHARS)
    return ""


def _result_text(content) -> str:
    """Plain text of a tool_result's content, which is a string or blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def translate_event(record: dict) -> list[dict]:
    """Map one stream-json line from the CLI to zero or more UI events."""
    if not isinstance(record, dict) or record.get("parent_tool_use_id"):
        return []

    kind = record.get("type")

    if kind == "system" and record.get("subtype") == "init":
        return [{
            "type": "start",
            "sessionId": record.get("session_id"),
            "model": record.get("model"),
        }]

    # Text arrives twice: as deltas while it streams and again whole inside
    # the final `assistant` record. Only the deltas are forwarded.
    if kind == "stream_event":
        event = record.get("event") or {}
        delta = event.get("delta") or {}
        if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
            return [{"type": "text", "text": delta.get("text", "")}]
        return []

    if kind == "assistant":
        blocks = (record.get("message") or {}).get("content") or []
        return [
            {
                "type": "tool",
                "id": b.get("id"),
                "name": b.get("name", "?"),
                "summary": _tool_summary(b.get("name", ""), b.get("input")),
            }
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "tool_use"
        ]

    if kind == "user":
        content = (record.get("message") or {}).get("content")
        if not isinstance(content, list):
            return []
        return [
            {
                "type": "tool_result",
                "id": b.get("tool_use_id"),
                "isError": bool(b.get("is_error")),
                "text": _truncate(_result_text(b.get("content")), RESULT_PREVIEW_CHARS),
            }
            for b in content
            if isinstance(b, dict) and b.get("type") == "tool_result"
        ]

    if kind == "result":
        return [{
            "type": "done",
            "isError": bool(record.get("is_error")),
            "result": record.get("result") if record.get("is_error") else None,
            "costUsd": record.get("total_cost_usd"),
            "durationMs": record.get("duration_ms"),
            "turns": record.get("num_turns"),
            "denied": [
                d.get("tool_name", "?")
                for d in record.get("permission_denials") or []
                if isinstance(d, dict)
            ],
        }]

    return []


# Context Claude Code wraps into a user message on the user's behalf (IDE
# state, reminders, slash-command plumbing). A text block that is nothing but
# one of these is not something the user typed.
_INJECTED_TAGS = (
    "ide_opened_file", "ide_selection", "ide_diagnostics", "system-reminder",
    "local-command-stdout", "local-command-stderr", "local-command-caveat",
    "command-message", "user-prompt-submit-hook",
)
_INJECTED = re.compile(
    r"<(" + "|".join(map(re.escape, _INJECTED_TAGS)) + r")\b[^>]*>.*?</\1>", re.S
)
_COMMAND = re.compile(r"<command-name>(.*?)</command-name>", re.S)
_COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
_PASTED = re.compile(r"</?pasted_content\b[^>]*>")


def _prompt_text(content) -> str:
    """
    What the user actually wrote, from a transcript user message.

    Injected context is removed, a slash command is shown as typed
    ("/name args"), pasted text keeps its content but loses its wrapper, and an
    image becomes "[image]". Empty when nothing user-written is left.
    """
    blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
    parts = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "image":
            parts.append("[image]")
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text") or ""
        command = _COMMAND.search(text)
        if command:
            args = _COMMAND_ARGS.search(text)
            text = f"{command.group(1).strip()} {args.group(1).strip() if args else ''}"
        else:
            text = _PASTED.sub("", _INJECTED.sub("", text))
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def history_events(records: list[dict]) -> list[dict]:
    """
    A session transcript as chat events (see the module docstring).

    Transcript `assistant`/`user` records share their message shape with the
    stream-json output, so tool calls and results go through the same helpers
    as a live turn.
    """
    events = []
    for record in records:
        if record.get("isSidechain") or record.get("isMeta"):
            continue
        kind = record.get("type")
        content = (record.get("message") or {}).get("content")

        if kind == "assistant":
            for block in content or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and (block.get("text") or "").strip():
                    events.append({"type": "text", "text": block["text"], "block": True})
                elif block.get("type") == "tool_use":
                    events.append({
                        "type": "tool",
                        "id": block.get("id"),
                        "name": block.get("name", "?"),
                        "summary": _tool_summary(block.get("name", ""), block.get("input")),
                    })

        elif kind == "user":
            if record.get("isCompactSummary"):
                events.append({"type": "note", "text": "Conversation compacted"})
                continue
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                events += translate_event({"type": "user", "message": {"content": content}})
                continue
            text = _prompt_text(content)
            if text.startswith("<task-notification>"):
                events.append({"type": "note", "text": "A background task finished"})
            elif text:
                events.append({"type": "prompt", "text": text, "at": record.get("timestamp")})
    return events


class ClaudeRunner:
    """Runs prompts against Claude Code sessions, one at a time per session."""

    def __init__(self, binary: str | None = None):
        self.binary = binary
        self._running: set[str] = set()

    def is_running(self, session_id: str) -> bool:
        return session_id in self._running

    def build_command(self, binary: str, session_id: str, permission_mode: str) -> list[str]:
        return [
            binary,
            "-p",
            "--resume", session_id,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--permission-mode", permission_mode,
            "--permission-prompts", "none",
        ]

    async def stream(
        self,
        session_id: str,
        cwd: str,
        prompt: str,
        permission_mode: str = DEFAULT_PERMISSION_MODE,
    ) -> AsyncIterator[dict]:
        """
        Run one turn and yield UI events as they happen.

        Never raises for a failed run — failures become an `error` event, so
        the HTTP stream always ends cleanly. If the consumer goes away (the
        browser aborts the request), the generator is closed and the `finally`
        kills the process rather than leaving an orphaned agent running.
        Raises SessionBusyError up front if a turn is already in flight.
        """
        if session_id in self._running:
            raise SessionBusyError(session_id)
        self._running.add(session_id)

        process = None
        try:
            binary = self.binary or find_claude_binary()
            if binary is None:
                yield {"type": "error", "message": "Claude Code CLI not found on PATH"}
                return

            # CLAUDECODE marks a process as running *inside* Claude Code; if the
            # dashboard was started from one, the child would refuse to run.
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
            try:
                process = await asyncio.create_subprocess_exec(
                    *self.build_command(binary, session_id, permission_mode),
                    cwd=cwd,
                    env=env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=LINE_LIMIT,
                )
            except OSError as exc:
                yield {"type": "error", "message": f"Could not start Claude Code: {exc}"}
                return
            # It registers in ~/.claude/sessions like any client; this keeps
            # the session from reading as "open elsewhere" during our turn.
            DASHBOARD_PIDS.add(str(process.pid))

            # The prompt goes over stdin, not argv, so a prompt starting with
            # "-" is never mistaken for a flag.
            # A process that dies at startup closes its stdin first; its exit
            # code and stderr, read below, are what explain the failure.
            try:
                process.stdin.write(prompt.encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass

            # Drained concurrently: a chatty stderr would otherwise fill its
            # pipe and stall the process while stdout is being read.
            stderr_task = asyncio.create_task(process.stderr.read())

            finished = False
            while True:
                try:
                    line = await process.stdout.readline()
                except ValueError:
                    # A single line beyond LINE_LIMIT; skip what is left of it.
                    continue
                if not line:
                    break
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                for event in translate_event(record):
                    finished = finished or event["type"] == "done"
                    yield event

            code = await process.wait()
            stderr = (await stderr_task).decode("utf-8", "replace").strip()
            if not finished:
                message = stderr or f"Claude Code exited with code {code}"
                yield {"type": "error", "message": _truncate(message, RESULT_PREVIEW_CHARS)}
        finally:
            if process is not None:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                DASHBOARD_PIDS.discard(str(process.pid))
            self._running.discard(session_id)
