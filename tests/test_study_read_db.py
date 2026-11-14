"""Real SQLite freshness and cleanup for the narrow study read facade."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import sqlite3

import pytest

from learning_service.db import Database
from learning_service.study_deadline import CURRENT_DEADLINE, StudyDeadline
from learning_service.study_read_db import share_study_reads
from learning_service import study_routes
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools
from test_runtime_passages import stack, runtime_bundle, search


@pytest.fixture
def database(tmp_path):
    db=Database(tmp_path/'synthetic.db')
    with db.session(write=True) as conn:
        conn.execute('CREATE TABLE synthetic_state (value INTEGER)')
        conn.execute('INSERT INTO synthetic_state VALUES (1)')
    return db


def test_each_select_sees_external_commit_without_reopening(database,monkeypatch):
    calls=[];original=database.connect
    def connect():calls.append(1);return original()
    monkeypatch.setattr(database,'connect',connect)
    with share_study_reads(database) as reads:
        with reads.session() as first:
            assert first.execute('SELECT value FROM synthetic_state').fetchone()[0]==1
        with original() as writer:
            writer.execute('UPDATE synthetic_state SET value=2')
        writer.close()
        with reads.session() as second:
            assert second is first
            assert second.execute('SELECT value FROM synthetic_state').fetchone()[0]==2
            assert not second.in_transaction
    assert len(calls)==1
    with pytest.raises(sqlite3.ProgrammingError):first.execute('SELECT 1')
    with pytest.raises(RuntimeError):
        with reads.session():pass


@pytest.mark.parametrize('sql',['UPDATE synthetic_state SET value=2','BEGIN','SAVEPOINT stale','PRAGMA query_only=OFF','PRAGMA journal_mode=DELETE'])
def test_read_facade_cannot_write_or_pin_a_stale_snapshot(database,sql):
    with share_study_reads(database) as reads:
        with reads.session() as conn:
            with pytest.raises(sqlite3.DatabaseError):conn.execute(sql)
            assert not conn.in_transaction
            assert conn.execute('SELECT value FROM synthetic_state').fetchone()[0]==1
        with pytest.raises(RuntimeError):
            with reads.session(write=True):pass


@pytest.mark.parametrize('exception',[ValueError,KeyboardInterrupt])
def test_scope_closes_connection_on_any_exception(database,exception):
    with pytest.raises(exception):
        with share_study_reads(database) as reads:
            with reads.session() as conn:raise exception()
    assert not reads.active
    with pytest.raises(sqlite3.ProgrammingError):conn.execute('SELECT 1')


def test_thread_and_database_scopes_cannot_mix(database,tmp_path):
    other=Database(tmp_path/'other.db')
    with share_study_reads(database) as reads,share_study_reads(other) as second:
        with second.session() as conn:
            assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name='synthetic_state'").fetchone()[0]==0
        def wrong_thread():
            with pytest.raises(RuntimeError):
                with reads.session():pass
        with ThreadPoolExecutor(max_workers=1) as pool:pool.submit(copy_context().run,wrong_thread).result()
    with database.session(write=True) as conn:conn.execute('UPDATE synthetic_state SET value=3')


def test_cancelled_read_scope_closes_and_will_not_issue_next_query(database):
    deadline=StudyDeadline();token=CURRENT_DEADLINE.set(deadline)
    try:
        with pytest.raises(TimeoutError):
            with share_study_reads(database) as reads:
                with reads.session() as conn:conn.execute('SELECT 1').fetchone()
                deadline.cancel()
                with reads.session():raise AssertionError('late query allowed')
        with pytest.raises(sqlite3.ProgrammingError):conn.execute('SELECT 1')
    finally:CURRENT_DEADLINE.reset(token)


@pytest.mark.parametrize('mutation',['switch','revoke'])
def test_reused_read_observes_concurrent_external_authorization_change(stack,monkeypatch,mutation):
    original=study_routes.render_textbook_page
    def changing(*args):
        image=original(*args)
        # Commit through a distinct connection/thread during the held read scope.
        def change():
            with stack['db'].session(write=True) as conn:
                if mutation=='switch':conn.execute('UPDATE account_contexts SET revision=revision+1')
                else:conn.execute("UPDATE learner_access SET active=0 WHERE learner_id='family-g7'")
        with ThreadPoolExecutor(max_workers=1) as pool:pool.submit(change).result(timeout=2)
        return image
    monkeypatch.setattr(study_routes,'render_textbook_page',changing)
    response=stack['gateway'].get('/learning/api/v1/textbooks/math-g7-upper/pages/31/image',headers=stack['headers'])
    assert response.status_code==(409 if mutation=='switch' else 404)
    assert not response.content.startswith(b'\x89PNG')


def test_context_resolution_still_rejects_expired_and_revoked_sessions(stack):
    assert search(stack).status_code==200
    with stack['db'].session(write=True) as conn:
        conn.execute("UPDATE browser_sessions SET revoked_at='2026-11-08'")
    assert search(stack).status_code==401
