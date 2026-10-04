"""
Folder browser backing the "Add project" picker.

A browser cannot hand the page an absolute path for a folder the user picks,
so the server lists directories itself and flags which ones are git repos.
The server binds to 127.0.0.1 only, so this exposes nothing beyond what the
user running it can already see.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..git import is_git_repo


class FilesystemRouter:
    """/fs/browse — subdirectories of a path, each flagged as git repo or not."""

    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route("/fs/browse", self.browse, methods=["GET"])

    def browse(self, path: str | None = None) -> dict:
        """
        Subdirectories of `path` (the user's home when omitted), sorted by name.

        Hidden folders are skipped; unreadable ones are listed but cannot be
        opened, which the next browse call reports as 403.
        """
        current = Path(path).expanduser().resolve() if path else Path.home()
        if not current.is_dir():
            raise HTTPException(status_code=404, detail=f"{current} is not a directory")

        try:
            children = sorted(
                (c for c in current.iterdir() if not c.name.startswith(".") and c.is_dir()),
                key=lambda c: c.name.lower(),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=f"Cannot read {current}") from exc

        return {
            "path": str(current),
            "parent": str(current.parent) if current.parent != current else None,
            "isGitRepo": is_git_repo(current),
            "entries": [
                {"name": c.name, "path": str(c), "isGitRepo": is_git_repo(c)}
                for c in children
            ],
        }
