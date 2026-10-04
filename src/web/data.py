"""
Central data access for the web backend.

Every `load_*` method is a seam: swap its body for a real implementation and
every router built on `DataStore` goes live, with no other code to touch.
Sessions are already live for Claude Code (`get_claude_sessions`); chat and
harness are still mock-backed.
"""

import re
import time
from pathlib import Path

from constants.web import AGENT_PROVIDERS, GIT_REFRESH_SECONDS

from .db import ProjectStore
from .git import is_git_repo, run_git
from .mock_data import get_mock_chat, get_mock_harness
from .serializers import serialize_project, serialize_session, summarize_sessions
from .sources.claude import parse_claude_sessions


class InvalidProjectError(ValueError):
    """The path given for a new project is not a usable git repository."""


def _slugify(name: str) -> str:
    """URL-safe project id, e.g. "My Repo" -> "my-repo"."""
    return re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower()).strip("-")


class DataStore:
    """Loads and joins session, repository, chat and harness data."""

    def __init__(self, projects: ProjectStore):
        self.projects = projects
        # path -> (expires_at, .git signature, git fields); see `_git_state`.
        self._git_cache: dict[str, tuple[float, tuple, dict]] = {}

    def register_project(self, path: str, name: str | None = None) -> dict:
        """
        Persist a git repository as a tracked project.

        The path is normalised (`~` expanded, made absolute, symlinks resolved)
        so the same repo cannot be registered twice under different spellings,
        and so it compares equal to a session's `ProjectPath`. Raises
        InvalidProjectError for a bad path and DuplicateProjectError (from the
        store) when the id or path is already taken.
        """
        repo = Path(path).expanduser().resolve()
        if not repo.is_dir():
            raise InvalidProjectError(f"{repo} is not a directory")
        if not is_git_repo(repo):
            raise InvalidProjectError(f"{repo} is not a git repository")

        name = (name or "").strip() or repo.name
        project_id = _slugify(name)
        if not project_id:
            raise InvalidProjectError(f"Cannot derive a project id from {name!r}")

        return self.projects.create(project_id, name, str(repo))

    def load_agent_sessions(self, project: dict,  agent: str | None = None) -> tuple[list[dict], dict]:
        """
        Single source of session data for every route.

        `agent` is an AGENT_PROVIDERS id; None means every agent, which is what
        the project listing and /agents need. Agents without a reader yet
        report no sessions.
        """
        match agent:
            case "claude":
                return self.get_claude_sessions(project['path'])
            case "codex" | "opencode":
                return [], {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}  
            case _:
                return [], {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}


    def get_claude_sessions(self, path: str) -> tuple[list[dict], dict]:
        """
        Claude Code sessions from ~/.claude/projects, in the monitoring contract.

        See `sources/claude.py` for how transcripts are read and why it does
        not reuse the CLI's `ClaudeSource`.
        """
        return parse_claude_sessions(path)

    def load_repositories(self) -> list[dict]:
        """
        Git repositories backing the tracked projects.

        The projects registered in the DB, each enriched with its live git
        state by `get_repo_info`.
        """
        return [self.get_repo_info(project) for project in self.projects.list()]

    def load_chat(self, session_id: str) -> list[dict]:
        """
        Transcript for one session.

        Swap this body for a per-provider transcript reader (Claude's JSONL, the
        Opencode SQLite `message` table, …) normalised to the same shape.
        """
        return get_mock_chat(session_id)

    def load_harness(self, project_path: str) -> dict:
        """
        Harness installed in a project, per provider id.

        Swap this body for a walk of `<project>/<target_dir>/<dest_subpath>` using
        the installer's own ENVIRONMENTS entries.
        """
        return get_mock_harness(project_path)

    def find_agent(self, agent_id: str) -> dict | None:
        """One AGENT_PROVIDERS entry by id, or None."""
        return next((a for a in AGENT_PROVIDERS if a["id"] == agent_id), None)

    def project_sessions(self, project: dict) -> tuple[list[dict], dict]:
        """
        Raw sessions that belong to `project`, from every enabled agent, with
        their summed token totals.

        A session belongs to a project when its ProjectPath is the project's
        path; this is the only place that join is made for session routes.
        """
        sessions, totals = [], {"input": 0, "output": 0, "cacheR": 0, "cacheW": 0}
        for provider in AGENT_PROVIDERS:
            if not provider["enabled"]:
                continue
            agent_sessions, agent_sessions_totals = self.load_agent_sessions(project, provider["id"])
            sessions += agent_sessions
            for k in totals:
                totals[k] += agent_sessions_totals.get(k, 0)
        return sessions, totals

    def all_sessions(self) -> list[dict]:
        """Raw sessions of every registered project, for cross-project metrics."""
        sessions = []
        for project in self.projects.list():
            sessions += self.project_sessions(project)[0]
        return sessions

    def group_by_provider(self, sessions: list[dict]) -> list[dict]:
        """
        Bucket sessions under their provider, in AGENT_PROVIDERS order.

        Providers with no sessions in this project are omitted.
        """
        groups = []
        for provider in AGENT_PROVIDERS:
            owned = [s for s in sessions if s.get("AI") == provider["tag"]]
            if not owned:
                continue

            owned.sort(key=lambda s: s.get("mtime", 0), reverse=True)
            groups.append({
                "id": provider["id"],
                "label": provider["label"],
                "tag": provider["tag"],
                "accent": provider["accent"],
                "stats": summarize_sessions(owned),
                "sessions": [serialize_session(s) for s in owned],
            })
        return groups

    def get_projects(self) -> list[dict]:
        """Join repositories with the sessions running inside them."""
        projects = []
        repos = self.load_repositories()
        for repo in repos:
            sessions, _ = self.project_sessions(repo)
            projects.append(serialize_project(repo, sessions))
        return sorted(projects, key=lambda p: p["updatedAt"], reverse=True)

    def project_detail(self, project: dict) -> dict:
        """
        One project with its sessions nested under the agent that ran them.

        `project` is a `get_projects` entry. Served by GET /projects/{id} and
        pushed as the live `project` event, so both carry the same shape.
        """
        sessions, _ = self.project_sessions(project)
        return {**project, "agents": self.group_by_provider(sessions)}

    def agents_overview(self, sessions: list[dict] | None = None) -> dict:
        """
        Every provider with its own dashboard-style metrics.

        A provider with no sessions still reports a zeroed stats block, so the
        UI renders the same layout for every card. `sessions` defaults to
        those of every registered project.
        """
        if sessions is None:
            sessions = self.all_sessions()
        agents = []
        for provider in AGENT_PROVIDERS:
            owned = [s for s in sessions if s.get("AI") == provider["tag"]]
            agents.append({
                **provider,
                "sessionCount": len(owned),
                "stats": summarize_sessions(owned),
            })
        return {"agents": agents}

    def live_snapshot(self) -> dict[str, tuple[str, dict]]:
        """
        Everything the live stream publishes, computed in a single pass.

        Maps a stable key to (event name, payload): "projects" and "agents"
        carry the same bodies as GET /projects and GET /agents, and one
        "project:<id>" entry per project carries its GET /projects/{id} body.
        The EventHub diffs consecutive snapshots by key and only sends what
        changed.
        """
        snapshot = {}
        projects, every_session = [], []
        for repo in self.load_repositories():
            sessions, _ = self.project_sessions(repo)
            every_session += sessions
            project = serialize_project(repo, sessions)
            projects.append(project)
            snapshot[f"project:{project['id']}"] = (
                "project",
                {**project, "agents": self.group_by_provider(sessions)},
            )
        projects.sort(key=lambda p: p["updatedAt"], reverse=True)
        snapshot["projects"] = ("projects", {"projects": projects})
        snapshot["agents"] = ("agents", self.agents_overview(every_session))
        return snapshot

    def get_repo_info(self, project: dict) -> dict:
        """
        Live git state of a registered project, in the `get_mock_repositories` shape.

        `project` is a ProjectStore row. Every field degrades to a neutral
        default (None / 0 / False) when git cannot answer — repo deleted, no
        commits yet, no upstream — so one broken repo never fails the listing.
        """
        return {
            "id": project["id"],
            "path": project["path"],
            "name": project["name"],
            "createdAt": project.get("createdAt"),
            **self._git_state(project["path"]),
        }

    @staticmethod
    def _git_signature(path: str) -> tuple:
        """
        mtimes of the files a commit, checkout, stage or fetch rewrites.

        Edits to tracked files change none of them, which is why the cache in
        `_git_state` also expires on a timer.
        """
        signature = []
        for name in ("HEAD", "index", "FETCH_HEAD", "ORIG_HEAD"):
            try:
                signature.append((Path(path) / ".git" / name).stat().st_mtime_ns)
            except OSError:
                signature.append(None)
        return tuple(signature)

    def _git_state(self, path: str) -> dict:
        """
        Git fields of one repository, cached.

        Every project costs five git subprocesses, and the live stream asks for
        all of them every second. A cached answer is reused until a git
        operation touches `.git` (see `_git_signature`) or GIT_REFRESH_SECONDS
        pass — the latter catches plain edits to the working tree.
        """
        now = time.monotonic()
        signature = self._git_signature(path)
        cached = self._git_cache.get(path)
        if cached and cached[0] > now and cached[1] == signature:
            return cached[2]

        info = {
            "branch": None,
            "defaultBranch": None,
            "remote": None,
            "dirty": False,
            "changedFiles": 0,
            "ahead": 0,
            "behind": 0,
            "lastCommit": None,
        }

        # One call for branch, divergence and working-tree state: porcelain v2
        # puts `# branch.*` headers before one line per changed path.
        status = run_git(path, "status", "--porcelain=v2", "--branch")
        if status is not None:
            changed = 0
            for line in status.splitlines():
                if line.startswith("# branch.head "):
                    head = line.split(" ", 2)[2]
                    # "(detached)" is git's placeholder, not a branch name.
                    info["branch"] = None if head == "(detached)" else head
                elif line.startswith("# branch.ab "):
                    ahead, behind = line.split()[2:4]  # "+N", "-M"
                    info["ahead"], info["behind"] = int(ahead[1:]), int(behind[1:])
                elif not line.startswith("#"):
                    changed += 1
            info["changedFiles"] = changed
            info["dirty"] = changed > 0

        if info["branch"] is None:
            info["branch"] = run_git(path, "rev-parse", "--short", "HEAD")

        info["remote"] = run_git(path, "remote", "get-url", "origin")

        # origin/HEAD only exists for clones (or after `git remote set-head`).
        origin_head = run_git(path, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        if origin_head:
            info["defaultBranch"] = origin_head.removeprefix("origin/")

        # \x1f (unit separator) cannot appear in a commit subject or author.
        log = run_git(path, "log", "-1", "--format=%h%x1f%s%x1f%an%x1f%ct")
        if log:
            commit_hash, message, author, at = log.split("\x1f")
            info["lastCommit"] = {
                "hash": commit_hash,
                "message": message,
                "author": author,
                "at": float(at),
            }

        # Re-read after the fact: `git status` may itself rewrite the index to
        # refresh its stat cache, and the stored signature must not count that
        # as a change on the next lookup.
        self._git_cache[path] = (now + GIT_REFRESH_SECONDS, self._git_signature(path), info)
        return info

    def find_project(self, project_id: str) -> dict | None:
        """One project by id, or None. Shared by every /projects/{id}* route."""
        return next((p for p in self.get_projects() if p["id"] == project_id), None)
