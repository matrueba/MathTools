"""
SQLite connection and schema for the web backend.

One short-lived connection per unit of work rather than a shared one: FastAPI
runs sync handlers on a thread pool, and sqlite3 connections must not cross
threads. Opening a local SQLite file is cheap enough that pooling buys nothing.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Every statement is idempotent, so `init_schema()` runs on each start-up.
# A column added later needs an explicit migration — CREATE TABLE IF NOT
# EXISTS will not alter a table that already exists.
SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    path       TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);
"""


class Database:
    """Owns the SQLite file: where it lives, its schema, and connections to it."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def init_schema(self) -> None:
        """Create the parent folder and any missing tables."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """
        A connection that commits on success, rolls back on error, and always
        closes — `with sqlite3.connect()` alone commits but never closes.
        """
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()
