"""
Translation layer between the monitoring session contract and the HTTP API.

The monitoring adapters emit PascalCase dicts shaped for a Rich table; the web
API speaks camelCase JSON. Keeping the mapping in one place means the frontend
never has to know about the CLI's internal key names, and new monitoring
sources become available to the UI as soon as they satisfy the contract.
"""


def serialize_message(message: dict) -> dict:
    """One chat transcript entry, normalised across providers."""
    return {
        "role": message.get("role", "assistant"),
        "text": message.get("text", ""),
        "at": message.get("at"),
        "tokens": message.get("tokens"),
        "tool": message.get("tool"),
    }


def serialize_harness(provider: dict, installed: dict | None, env: dict | None) -> dict:
    """
    One provider's harness state inside a project.

    `installed` is what is on disk (None when absent); `env` is the installer's
    ENVIRONMENTS entry, which says what *could* be installed and from where.
    A provider with no `env` can still have sessions — it just has nothing the
    installer knows how to deploy.
    """
    components = (installed or {}).get("components", {}) or {}

    # Component types this provider supports, taken from the installer's own
    # source tuples rather than a second hardcoded list.
    supported = []
    if env:
        supported = [dest_subpath for _, _, dest_subpath, _ in env.get("sources", [])]

    return {
        "id": provider["id"],
        "label": provider["label"],
        "tag": provider["tag"],
        "accent": provider["accent"],
        "installable": env is not None,
        "targetDir": env.get("target_dir") if env else None,
        "globalDir": env.get("global_dir") if env else None,
        "supportedComponents": supported,
        "installed": installed is not None,
        "scope": (installed or {}).get("scope"),
        "installedAt": (installed or {}).get("installedAt"),
        "updateAvailable": (installed or {}).get("updateAvailable", False),
        "components": {
            name: [
                {"name": item.get("name"), "description": item.get("description", "")}
                for item in items
            ]
            for name, items in components.items()
        },
        "componentCount": sum(len(items) for items in components.values()),
    }


def serialize_session(session: dict) -> dict:
    """Map one monitoring-contract session dict to the API representation."""
    context_window = session.get("ContextWindow", 0) or 0
    last_context = session.get("LastContext", 0) or 0
    context_pct = (last_context / context_window * 100) if context_window else 0.0

    return {
        "id": session.get("SessionId", ""),
        "agent": session.get("AI", "?"),
        "project": session.get("Project", "Unknown"),
        "projectPath": session.get("ProjectPath", ""),
        "summary": session.get("Summary") or "No summary",
        "model": session.get("Model", "-"),
        "status": session.get("Status", "Wait").lower(),
        "turnCount": session.get("TurnCount", 0),
        "updatedAt": session.get("mtime", 0),
        "context": {
            "used": last_context,
            "window": context_window,
            "pct": round(context_pct, 1),
        },
        # None is passed through rather than coerced to 0: it means the
        # provider does not report that metric, which the UI shows as "—".
        "tokens": {
            "total": session.get("TotalTokens", 0),
            "input": session.get("InputTokens", 0),
            "output": session.get("OutputTokens", 0),
            "cacheRead": session.get("CacheR", 0),
            "cacheWrite": session.get("CacheW", 0),
        },
        "quota": session.get("Quota"),
        "pids": session.get("PIDs", []),
        "children": session.get("Children", []),
        "subagents": session.get("Subagents", []),
    }


def summarize_sessions(sessions: list[dict], totals: dict | None = None) -> dict:
    """
    Headline metrics for a set of sessions.

    Used for the whole dashboard, for a single project, and per agent provider,
    so all three surfaces report the same numbers the same way. When `totals`
    is omitted it is derived from the sessions themselves.
    """
    # `or 0` throughout: a provider may report a field as None (unavailable),
    # which must count as zero when aggregating but stays None per session.
    if totals is None:
        totals = {
            "input": sum(s.get("InputTokens") or 0 for s in sessions),
            "output": sum(s.get("OutputTokens") or 0 for s in sessions),
            "cacheR": sum(s.get("CacheR") or 0 for s in sessions),
            "cacheW": sum(s.get("CacheW") or 0 for s in sessions),
        }

    active = sum(1 for s in sessions if s.get("Status") == "Work")
    quota = next((s["Quota"] for s in sessions if s.get("Quota")), None)

    return {
        "tokens": {
            "total": sum(totals.values()),
            "input": totals.get("input", 0),
            "output": totals.get("output", 0),
            "cacheRead": totals.get("cacheR", 0),
            "cacheWrite": totals.get("cacheW", 0),
        },
        "sessions": {
            "total": len(sessions),
            "active": active,
            "idle": len(sessions) - active,
        },
        "projects": len({s.get("Project") for s in sessions}),
        "quota": quota,
    }


# Kept as the dashboard's entry point; `summarize_sessions` is the shared core.
def serialize_totals(totals: dict, sessions: list[dict]) -> dict:
    """Aggregate headline numbers for the dashboard stat row."""
    return summarize_sessions(sessions, totals)


def serialize_project(repo: dict, sessions: list[dict]) -> dict:
    """
    Combine a git repository with the agent sessions running inside it.

    `sessions` must already be filtered to this repo's path.
    """
    last_commit = repo.get("lastCommit") or {}

    return {
        "id": repo.get("name", ""),
        "name": repo.get("name", ""),
        "path": repo.get("path", ""),
        "git": {
            "branch": repo.get("branch"),
            "defaultBranch": repo.get("defaultBranch"),
            "remote": repo.get("remote"),
            "dirty": repo.get("dirty", False),
            "changedFiles": repo.get("changedFiles", 0),
            "ahead": repo.get("ahead", 0),
            "behind": repo.get("behind", 0),
            "lastCommit": {
                "hash": last_commit.get("hash"),
                "message": last_commit.get("message"),
                "author": last_commit.get("author"),
                "at": last_commit.get("at"),
            }
            if last_commit
            else None,
        },
        "stats": summarize_sessions(sessions),
        # Which providers have touched this project, e.g. ["CL"].
        "agents": sorted({s.get("AI", "?") for s in sessions}),
        "updatedAt": max((s.get("mtime", 0) for s in sessions), default=0),
    }
