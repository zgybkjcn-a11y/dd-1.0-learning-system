"""Shared human-selected context; switching invalidates outstanding challenges."""
from __future__ import annotations

import sqlite3

from .db import utc_now


class ContextConflict(Exception):
    pass


def read_context(conn: sqlite3.Connection, account_id: str) -> dict:
    row = conn.execute("SELECT learner_id,revision FROM account_contexts WHERE account_id=?", (account_id,)).fetchone()
    return {"learner_id": row["learner_id"] if row else None, "context_version": row["revision"] if row else 0}


def select_context(conn: sqlite3.Connection, account_id: str, learner_id: str, expected: int) -> dict:
    current = read_context(conn, account_id)
    if type(expected) is not int or expected < 0 or expected != current["context_version"]:
        raise ContextConflict()
    if current["learner_id"] == learner_id:
        return current
    revision, now = current["context_version"] + 1, utc_now()
    conn.execute("INSERT INTO account_contexts(account_id,learner_id,revision,updated_at) VALUES (?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET learner_id=excluded.learner_id,revision=excluded.revision,updated_at=excluded.updated_at",
                 (account_id, learner_id, revision, now))
    conn.execute("UPDATE browser_sessions SET learner_id=? WHERE account_id=? AND revoked_at IS NULL", (learner_id, account_id))
    conn.execute("UPDATE interaction_challenges SET consumed_at=? WHERE actor_account_id=? AND consumed_at IS NULL", (now, account_id))
    return {"learner_id": learner_id, "context_version": revision}


def invalidate_context(conn: sqlite3.Connection, account_id: str) -> None:
    now = utc_now()
    conn.execute("UPDATE account_contexts SET learner_id=NULL,revision=revision+1,updated_at=? WHERE account_id=?", (now, account_id))
    conn.execute("UPDATE browser_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE account_id=?", (now, account_id))
    conn.execute("UPDATE interaction_challenges SET consumed_at=? WHERE actor_account_id=? AND consumed_at IS NULL", (now, account_id))
