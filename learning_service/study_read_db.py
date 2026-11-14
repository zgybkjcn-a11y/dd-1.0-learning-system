"""One fresh autocommit connection per synchronous study read, never a pool.

Each SELECT still observes current committed state. The facade cannot start a
transaction, write, cross a worker thread or escape the enclosing operation.
"""
from contextlib import contextmanager
import sqlite3
import threading
import time

from .study_deadline import CURRENT_DEADLINE, check_deadline


_READ_SCOPE_LOCK = threading.RLock()


@contextmanager
def _read_turn():
    operation = CURRENT_DEADLINE.get()
    ends = time.monotonic() + 12
    while True:
        check_deadline()
        remaining = operation.remaining() if operation is not None else ends - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('study read queue')
        if _READ_SCOPE_LOCK.acquire(timeout=min(.05, remaining)):
            break
    try:
        check_deadline()
        yield
    finally:
        _READ_SCOPE_LOCK.release()


class ReadDatabase:
    def __init__(self, connection):
        self.connection = connection
        self.thread = threading.get_ident()
        self.active = True

    @contextmanager
    def session(self, write=False):
        if write:
            raise RuntimeError('study read cannot write')
        if not self.active or threading.get_ident() != self.thread:
            raise RuntimeError('study read connection outside operation')
        check_deadline()
        yield self.connection
        check_deadline()


@contextmanager
def share_study_reads(database):
    with _read_turn():
        with _share_study_reads(database) as reads:
            yield reads


@contextmanager
def _share_study_reads(database):
    check_deadline()
    with database.session() as connection:
        if connection.in_transaction or connection.isolation_level is not None:
            raise RuntimeError('study reads require autocommit')
        connection.execute('PRAGMA query_only = ON')
        # Explicit BEGIN/SAVEPOINT would pin stale authorization data. Also
        # prevent a future reader from disabling the write restriction.
        def authorize(action, name, value, db_name, trigger):
            if action in (sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT):
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_PRAGMA and value is not None:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        connection.set_authorizer(authorize)
        reads = ReadDatabase(connection)
        try:
            yield reads
        finally:
            reads.active = False
