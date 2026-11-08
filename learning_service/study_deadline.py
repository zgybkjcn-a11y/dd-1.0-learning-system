"""One monotonic budget for a read operation; no automatic retries.

The standalone WebUI Tool embeds this small helper verbatim (checked in tests).
"""
from contextvars import ContextVar
import math
import re
import socket
import threading
import time

STUDY_TOTAL_SECONDS = 12.0
STUDY_BUDGET_HEADER = 'X-DD-Study-Budget-Ms'
CURRENT_DEADLINE = ContextVar('dd_study_deadline', default=None)


class StudyDeadline:
    def __init__(self, seconds=STUDY_TOTAL_SECONDS):
        self.ends = time.monotonic() + max(0, min(STUDY_TOTAL_SECONDS, seconds))
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.sockets = set()

    def remaining(self):
        value = self.ends - time.monotonic()
        if self.stopped.is_set() or value <= 0:
            raise TimeoutError('study deadline')
        return value

    def header(self):
        return str(max(0, math.floor(self.remaining() * 1000)))

    def attach(self, sock):
        with self.lock:
            self.remaining()
            self.sockets.add(sock)

    def detach(self, sock):
        with self.lock:
            self.sockets.discard(sock)

    def cancel(self):
        with self.lock:
            self.stopped.set()
            for sock in self.sockets:
                try: sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass


def budget_seconds(value):
    if value is None:
        return STUDY_TOTAL_SECONDS
    if not re.fullmatch(r'[0-9]{1,6}', value):
        raise ValueError('invalid study budget')
    return min(STUDY_TOTAL_SECONDS, int(value) / 1000)


def check_deadline():
    current = CURRENT_DEADLINE.get()
    if current is not None:
        current.remaining()


def is_study_path(path):
    return (path in {'/api/v1/textbooks', '/api/v1/textbooks/search',
                     '/api/v1/math-references', '/api/v1/study-support'}
            or path.startswith('/api/v1/textbooks/'))
