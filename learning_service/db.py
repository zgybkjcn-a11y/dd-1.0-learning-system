from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class WriteContextChanged(Exception):
    pass


# Set only for an authenticated shared-context request. Every write transaction
# rechecks while holding SQLite's write lock, including uploads and challenges.
write_context: ContextVar[tuple | None] = ContextVar("learning_write_context", default=None)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str = "id") -> str:
    import secrets
    return f"{prefix}_{secrets.token_urlsafe(16)}"


class Database:
    def __init__(self, path: Path, migration_dir: Path | None = None):
        self.path = path
        self.migration_dir = migration_dir or Path(__file__).parent / "migrations"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        # Apply the wait policy before WAL negotiation. On a fresh database,
        # two processes can concurrently open the file and both issue the
        # journal_mode pragma; setting busy_timeout first prevents the second
        # opener from failing during that short startup lock window.
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA foreign_keys = ON")
        deadline = time.monotonic() + 15
        while True:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
                break
            except sqlite3.OperationalError as exc:
                # SQLite may return SQLITE_BUSY immediately for journal-mode
                # negotiation even when a busy handler is installed. Retry
                # this startup-only pragma within the same bounded window.
                if "locked" not in str(exc).lower() or time.monotonic() >= deadline:
                    conn.close()
                    raise
                time.sleep(0.05)
        return conn

    def migrate(self) -> None:
        conn = self.connect()
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            for path in sorted(self.migration_dir.glob("*.sql")):
                version = int(path.name.split("_", 1)[0])
                # Serialize competing app starts and recheck the version only
                # after taking the write lock. Otherwise two processes can
                # both observe a missing migration and the second can fail on
                # an ALTER TABLE already applied by the first.
                conn.execute("BEGIN IMMEDIATE")
                try:
                    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
                        conn.rollback()
                        continue
                    self._execute_migration(conn, path.read_text(encoding="utf-8"))
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, utc_now()),
                    )
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise
        finally:
            conn.close()

    @staticmethod
    def _execute_migration(conn: sqlite3.Connection, script: str) -> None:
        """Execute a SQL script without ``executescript``'s implicit commit.

        Migration DDL and its schema version must share one transaction so a
        failed or interrupted upgrade can be retried from the previous
        revision. ``sqlite3.complete_statement`` keeps semicolons inside SQL
        strings and trigger bodies from splitting statements prematurely.
        """
        statement = ""
        for character in script:
            statement += character
            if character == ";" and sqlite3.complete_statement(statement):
                if statement.strip():
                    conn.execute(statement)
                statement = ""
        if statement.strip():
            raise ValueError("incomplete SQL migration")

    @contextmanager
    def session(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            if write:
                conn.execute("BEGIN IMMEDIATE")
                fence = write_context.get()
                if fence and self.path.resolve() == fence[0]:
                    _, account_id, learner_id, version = fence
                    current = conn.execute("SELECT learner_id,revision FROM account_contexts WHERE account_id=?", (account_id,)).fetchone()
                    access = conn.execute("SELECT 1 FROM learner_access a JOIN learners l ON l.id=a.learner_id WHERE a.account_id=? AND a.learner_id=? AND a.active=1 AND l.active=1", (account_id, learner_id)).fetchone()
                    if not current or current["learner_id"] != learner_id or current["revision"] != version or not access:
                        raise WriteContextChanged()
            yield conn
            if write:
                conn.commit()
        except Exception:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
