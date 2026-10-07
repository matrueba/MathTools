"""
Claude Code sessions, read straight from its transcripts.

Layout under ~/.claude/projects (one folder per working directory):

    <encoded-cwd>/<session-id>.jsonl                      main transcript
    <encoded-cwd>/<session-id>/subagents/agent-<id>.jsonl  one per subagent
    <encoded-cwd>/<session-id>/subagents/agent-<id>.meta.json

Unlike `cli/monitoring/claude_source.py` this does not depend on a
`sessions-index.json` (current Claude Code versions do not write one) nor on
`~/.claude/sessions/<id>.json` for the project path: every transcript record
carries its own `cwd`, which is exactly the path a registered project is
matched against.

It also fixes a double count the CLI adapter has: an assistant message is
written as one record *per content block*, each repeating the full `usage` of
the message, so usage is summed once per `message.id`.

Like the monitoring adapters, this reads another tool's private and
undocumented state, so every parse is defensive: a malformed line is skipped
and an unreadable file yields no session, never an exception.
"""

import json
import re
import time
from pathlib import Path

from constants.source_files import CLAUDE_BASE_DIR

from .models import context_window

DEFAULT_CONTEXT_WINDOW = 1_000_000

# A transcript written to this recently means the agent is mid-turn.
WORK_THRESHOLD_SECONDS = 30

# Claude Code's live-process registry: <pid>.json → {"sessionId", "cwd", …}.
LIVE_SESSIONS_DIR = "~/.claude/sessions"

# PIDs of the `claude` processes the dashboard itself is running (see
# runners/claude.py, which adds and removes them). Not "someone else".
DASHBOARD_PIDS: set[str] = set()

# Session ids are UUIDs; anything else is refused before touching the disk.
_SESSION_ID = re.compile(r"^[A-Za-z0-9-]+$")

# Parsed transcripts keyed by path, reused while (mtime, size) is unchanged.
# The dashboard polls every 3s and transcripts run to megabytes, so only the
# files that actually changed get re-read.
_cache: dict[str, tuple[tuple[int, int], dict]] = {}


def _empty_usage() -> dict:
    return {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}


def _text_of(content) -> str | None:
    """Plain text of a user message, or None for tool results and the like."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(texts) if texts else None
    return None


def _parse_transcript(path: Path) -> dict | None:
    """
    Aggregate one JSONL transcript. Cached on (mtime, size).

    Returns None when the file cannot be read.
    """
    try:
        stat = path.stat()
    except OSError:
        return None

    key = (stat.st_mtime_ns, stat.st_size)
    cached = _cache.get(str(path))
    if cached and cached[0] == key:
        return cached[1]

    info = {
        "cwd": None,
        "title": None,
        "lastPrompt": None,
        "firstPrompt": None,
        "model": None,
        "turns": 0,
        "usage": _empty_usage(),
        "lastContext": 0,
        "mtime": stat.st_mtime,
    }
    # message.id -> usage, so each message counts once however many records
    # it was split across. Insertion order tracks the latest message.
    messages: dict[str, dict] = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(record, dict):
                    continue

                kind = record.get("type")
                if info["cwd"] is None and record.get("cwd"):
                    info["cwd"] = record["cwd"]

                if kind == "ai-title" and record.get("aiTitle"):
                    info["title"] = record["aiTitle"]
                elif kind == "last-prompt" and record.get("lastPrompt"):
                    info["lastPrompt"] = record["lastPrompt"]
                elif kind == "user":
                    text = _text_of((record.get("message") or {}).get("content"))
                    if text and text.strip():
                        info["turns"] += 1
                        info["firstPrompt"] = info["firstPrompt"] or text
                elif kind == "assistant":
                    message = record.get("message") or {}
                    model = message.get("model")
                    # "<synthetic>" marks locally generated messages, not a model.
                    if model and not model.startswith("<"):
                        info["model"] = model
                    usage = message.get("usage")
                    if isinstance(usage, dict):
                        messages[message.get("id") or record.get("uuid")] = usage
    except OSError:
        return None

    for usage in messages.values():
        info["usage"]["input"] += usage.get("input_tokens") or 0
        info["usage"]["output"] += usage.get("output_tokens") or 0
        info["usage"]["cacheR"] += usage.get("cache_read_input_tokens") or 0
        info["usage"]["cacheW"] += usage.get("cache_creation_input_tokens") or 0

    if messages:
        # Everything the model read on its latest call: fresh input plus both
        # cached reads and cache writes.
        last = list(messages.values())[-1]
        info["lastContext"] = sum(
            last.get(k) or 0
            for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        )

    _cache[str(path)] = (key, info)
    return info


def _subagents(session_dir: Path, now: float) -> list[dict]:
    """Subagents spawned by one session, oldest first."""
    folder = session_dir / "subagents"
    if not folder.is_dir():
        return []

    result = []
    for transcript in sorted(folder.glob("agent-*.jsonl"), key=lambda p: p.stat().st_mtime):
        info = _parse_transcript(transcript)
        if info is None:
            continue

        meta = {}
        try:
            meta = json.loads(transcript.with_suffix(".meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

        result.append({
            "label": meta.get("description") or meta.get("agentType") or transcript.stem,
            "type": meta.get("agentType"),
            "status": "work" if now - info["mtime"] < WORK_THRESHOLD_SECONDS else "done",
            "tokens": sum(info["usage"].values()),
            "usage": info["usage"],
        })
    return result


def _process_alive(pid: str, proc_start: str | None) -> bool:
    """
    True when `pid` is running and is still the process the registry meant.

    A registry file can outlive its process (a crash skips the cleanup), and
    the kernel reuses PIDs, so existence alone is not enough: Claude Code
    records the process start time (`procStart`, field 22 of /proc/<pid>/stat)
    and a different value means another program now owns that PID. Entries
    without `procStart` fall back to the existence check.
    """
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            stat = f.read()
    except OSError:
        return False
    if not proc_start:
        return True
    # The command name (field 2) may hold spaces or parentheses, so split
    # after its closing paren; what follows starts at field 3.
    fields = stat.rpartition(")")[2].split()
    return len(fields) > 19 and fields[19] == str(proc_start)


def _live_processes() -> dict[str, list[dict]]:
    """
    sessionId -> Claude Code processes running it outside the dashboard.

    Each item is {"pid", "entrypoint"}; the entrypoint says where the session
    is open ("cli" for a terminal, "claude-vscode" for the VS Code extension,
    …). Processes the dashboard spawned itself (DASHBOARD_PIDS) are left out:
    they register like any other, and would otherwise make every session look
    taken by someone else while the dashboard drives it.

    Linux-only (/proc); anywhere else, or on any read error, simply empty.
    """
    live: dict[str, list[dict]] = {}
    folder = Path(LIVE_SESSIONS_DIR).expanduser()
    try:
        entries = list(folder.glob("*.json"))
    except OSError:
        return live

    for entry in entries:
        try:
            data = json.loads(entry.read_text(encoding="utf-8"))
            pid, session_id = str(data["pid"]), data["sessionId"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if pid in DASHBOARD_PIDS or not _process_alive(pid, data.get("procStart")):
            continue
        live.setdefault(session_id, []).append(
            {"pid": pid, "entrypoint": data.get("entrypoint") or "unknown"}
        )
    return live


def parse_claude_sessions(project_path: str = None, base_dir: str | Path = CLAUDE_BASE_DIR) -> tuple[list[dict], dict]:
    """
    Every Claude Code session on disk, in the monitoring-adapter contract.

    Returns `(sessions, totals)` like `ClaudeSource().parse_claude_sessions()`.
    Subagent usage is folded into its session's token counts — it is spend the
    session caused — and also itemised under `Subagents`.
    """
    sessions: list[dict] = []
    totals = _empty_usage()

    root = Path(base_dir).expanduser()
    try:
        transcripts = list(root.glob("*/*.jsonl"))
    except OSError:
        return sessions, totals

    now = time.time()
    live = _live_processes()

    for transcript in transcripts:
        info = _parse_transcript(transcript)
        # No cwd means no record ever ran in a directory (an empty or
        # half-written file): nothing to attach the session to.
        if info is None or not info["cwd"]:
            continue
        if project_path is not None and info["cwd"] != project_path:
            continue

        session_id = transcript.stem
        subagents = _subagents(transcript.with_suffix(""), now)

        usage = dict(info["usage"])
        for sub in subagents:
            for k in usage:
                usage[k] += sub["usage"][k]
        for k in totals:
            totals[k] += usage[k]

        model = info["model"] or "-"
        working = now - info["mtime"] < WORK_THRESHOLD_SECONDS or any(
            s["status"] == "work" for s in subagents
        )
        summary = info["title"] or info["lastPrompt"] or info["firstPrompt"] or "No summary"

        sessions.append({
            "AI": "CL",
            "Project": Path(info["cwd"]).name,
            "SessionId": session_id,
            "Summary": " ".join(summary.split()),
            "Model": model,
            "Status": "Work" if working else "Wait",
            "TurnCount": info["turns"],
            "LastContext": info["lastContext"],
            "ContextWindow": context_window("claude", model, DEFAULT_CONTEXT_WINDOW),
            "TotalTokens": sum(usage.values()),
            "InputTokens": usage["input"],
            "OutputTokens": usage["output"],
            "CacheR": usage["cacheR"],
            "CacheW": usage["cacheW"],
            "Quota": None,
            "mtime": info["mtime"],
            "Children": [],
            "Subagents": [
                {k: s[k] for k in ("label", "type", "status", "tokens")} for s in subagents
            ],
            # Processes running this session outside the dashboard; non-empty
            # means it is open elsewhere and must not be driven from here.
            "PIDs": [p["pid"] for p in live.get(session_id, [])],
            "LiveIn": sorted({p["entrypoint"] for p in live.get(session_id, [])}),
            "ProjectPath": info["cwd"],
        })

    return sessions, totals


def read_transcript(session_id: str, base_dir: str | Path = CLAUDE_BASE_DIR) -> list[dict]:
    """
    Every JSON record of one session's main transcript, in file order.

    The transcript lives in a folder named after the session's cwd with a lossy
    encoding, so it is found by id across all of them. Malformed lines are
    skipped; a missing or unreadable file reads as no records.
    """
    if not _SESSION_ID.match(session_id or ""):
        return []
    root = Path(base_dir).expanduser()
    try:
        path = next(root.glob(f"*/{session_id}.jsonl"), None)
    except OSError:
        return []
    if path is None:
        return []

    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError:
        return []
    return records
