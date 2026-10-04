"""Persistence for registered projects: the repository paths the dashboard tracks."""

import sqlite3
import time

from .database import Database


class DuplicateProjectError(Exception):
    """A project with the same id or path is already registered."""


class ProjectStore:
    """CRUD over the `projects` table. Rows come back as plain dicts."""

    def __init__(self, db: Database):
        self.db = db

    def list(self) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, name, path, created_at FROM projects ORDER BY created_at"
            ).fetchall()
        return [self._to_dict(row) for row in rows]

    def get(self, project_id: str) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, name, path, created_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return self._to_dict(row) if row else None

    def create(self, project_id: str, name: str, path: str) -> dict:
        """Insert a project; raises DuplicateProjectError if id or path is taken."""
        created_at = time.time()
        try:
            with self.db.connect() as conn:
                conn.execute(
                    "INSERT INTO projects (id, name, path, created_at) VALUES (?, ?, ?, ?)",
                    (project_id, name, path, created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateProjectError(str(exc)) from exc

        return {"id": project_id, "name": name, "path": path, "createdAt": created_at}

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "path": row["path"],
            "createdAt": row["created_at"],
        }
