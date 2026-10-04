"""
Central data access for the web backend.

Every `load_*` method is a seam, and mock-backed today: swap its body for a
real implementation and every router built on `DataStore` goes live, with no
other code to touch. `mock_data.py` already emits dicts in the exact
monitoring-adapter contract (see `cli/monitoring/claude_source.py`), so
`load_sessions` is a one-line change to `ClaudeSource().parse_claude_sessions()`.
"""

from constants.web import AGENT_PROVIDERS

from .mock_data import (
    get_mock_chat,
    get_mock_harness,
    get_mock_repositories,
    get_mock_sessions,
)
from .serializers import serialize_project, serialize_session, summarize_sessions


class DataStore:
    """Loads and joins session, repository, chat and harness data."""

    def load_sessions(self) -> tuple[list[dict], dict]:
        """
        Single source of session data for every route.

        Swap this body for `ClaudeSource().parse_claude_sessions()` to go live.
        """
        return get_mock_sessions()

    def load_repositories(self) -> list[dict]:
        """
        Git repositories backing the tracked projects.

        Swap this body for a real `git` inspection of each session's ProjectPath.
        """
        return get_mock_repositories()

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

    def build_projects(self) -> list[dict]:
        """Join repositories with the sessions running inside them."""
        sessions, _ = self.load_sessions()
        repos = self.load_repositories()

        projects = [
            serialize_project(
                repo, [s for s in sessions if s.get("ProjectPath") == repo["path"]]
            )
            for repo in repos
        ]
        return sorted(projects, key=lambda p: p["updatedAt"], reverse=True)

    def find_project(self, project_id: str) -> dict | None:
        """One project by id, or None. Shared by every /projects/{id}* route."""
        return next((p for p in self.build_projects() if p["id"] == project_id), None)
