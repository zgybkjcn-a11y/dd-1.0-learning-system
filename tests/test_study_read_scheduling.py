"""Bounded read scheduling must preserve freshness and release on all exits."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import threading
import time

import pytest

from learning_service.db import Database
from learning_service.study_deadline import CURRENT_DEADLINE, StudyDeadline
from learning_service.study_read_db import share_study_reads


@pytest.fixture
def database(tmp_path):
    return Database(tmp_path/'queue.db')


@pytest.mark.parametrize('cancel', [False, True])
def test_waiting_read_respects_deadline_before_open_and_releases(database, monkeypatch, cancel):
    opened=[];original=database.connect
    def connect():
        opened.append(threading.get_ident())
        return original()
    monkeypatch.setattr(database,'connect',connect)
    started=threading.Event()
    budget=StudyDeadline(.12 if not cancel else 2)
    def waiting():
        token=CURRENT_DEADLINE.set(budget)
        begin=time.monotonic()
        try:
            started.set()
            with pytest.raises(TimeoutError):
                with share_study_reads(database):
                    raise AssertionError('queued read executed after deadline/cancellation')
            return time.monotonic()-begin
        finally:
            CURRENT_DEADLINE.reset(token)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with share_study_reads(database):
            future=executor.submit(waiting)
            assert started.wait(1)
            if cancel:budget.cancel()
            elapsed=future.result(timeout=.5)
            assert elapsed<.3
            assert len(opened)==1  # The waiting operation has not opened a DB.
        assert executor.submit(lambda: read_one(database)).result(timeout=1)==1


def read_one(database):
    with share_study_reads(database) as reads:
        with reads.session() as conn:
            return conn.execute('SELECT 1').fetchone()[0]


@pytest.mark.parametrize('fault', ['connect', 'body', 'base_exception'])
def test_failed_read_releases_slot_for_other_thread(database, monkeypatch, fault):
    original=database.connect
    if fault=='connect':
        def fail():raise OSError('synthetic open failure')
        monkeypatch.setattr(database,'connect',fail)
    expected=OSError if fault=='connect' else KeyboardInterrupt if fault=='base_exception' else ValueError
    with pytest.raises(expected):
        with share_study_reads(database):
            raise expected('synthetic scope failure')
    monkeypatch.setattr(database,'connect',original)
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(lambda: read_one(database)).result(timeout=1)==1


def test_nested_same_thread_scope_and_concurrent_writer_are_supported(database):
    with database.session(write=True) as connection:
        connection.execute('CREATE TABLE synthetic(value INTEGER)')
        connection.execute('INSERT INTO synthetic VALUES(1)')
    with share_study_reads(database) as outer:
        with outer.session() as conn:
            assert conn.execute('SELECT value FROM synthetic').fetchone()[0]==1
        assert read_one(database)==1
        def commit():
            with database.session(write=True) as writer:
                writer.execute('UPDATE synthetic SET value=2')
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(commit).result(timeout=1)
        with outer.session() as conn:
            assert not conn.in_transaction
            assert conn.execute('SELECT value FROM synthetic').fetchone()[0]==2
