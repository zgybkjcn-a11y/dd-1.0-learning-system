"""Bounded local caches for pinned, immutable material bytes, never authorization.

Local filesystem ctime_ns is part of the identity: restoring mtime and size
cannot conceal a write. Network filesystems with incoherent stat metadata and
privileged manipulation of ctime are outside this cache's trust boundary.
"""
from collections import OrderedDict
import hashlib
import os
from pathlib import Path
import stat
import threading
from .study_deadline import check_deadline


class ByteCache:
    def __init__(self, max_bytes, max_entries):
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self.items = OrderedDict()
        self.byte_size = 0
        self.lock = threading.RLock()

    def get(self, key):
        with self.lock:
            entry = self.items.get(key)
            if entry is None:
                return None
            self.items.move_to_end(key)
            return entry[0]

    def put(self, key, value, size):
        with self.lock:
            previous = self.items.pop(key, None)
            if previous: self.byte_size -= previous[1]
            if size > self.max_bytes: return
            self.items[key] = (value, size)
            self.byte_size += size
            while self.byte_size > self.max_bytes or len(self.items) > self.max_entries:
                _, (_, removed) = self.items.popitem(last=False)
                self.byte_size -= removed

    def clear(self):
        with self.lock:
            self.items.clear()
            self.byte_size = 0


PDF_BYTES = ByteCache(32 * 1024 * 1024, 4)
PAGE_BYTES = ByteCache(32 * 1024 * 1024, 32)
# Fixed stripes bound lock memory even when callers request many page numbers.
PDF_LOCKS = tuple(threading.Lock() for _ in range(16))
PAGE_LOCKS = tuple(threading.Lock() for _ in range(32))


def signature(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def fingerprint(path):
    check_deadline()
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('material symlink')
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('material is not regular')
    return str(path), signature(info)


def verified_pdf(path, expected):
    check_deadline()
    identity = fingerprint(path)
    key = (identity, expected)
    with PDF_LOCKS[hash(key) % len(PDF_LOCKS)]:
        check_deadline()
        cached = PDF_BYTES.get(key)
        if cached is None:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as source:
                if signature(os.fstat(source.fileno())) != identity[1]:
                    raise ValueError('source changed during open')
                cached = source.read()
                if signature(os.fstat(source.fileno())) != identity[1]:
                    raise ValueError('source changed during read')
            if hashlib.sha256(cached).hexdigest() != expected:
                raise ValueError('textbook source changed')
            if fingerprint(path) != identity:
                raise ValueError('source changed during validation')
            PDF_BYTES.put(key, cached, len(cached))
        if fingerprint(path) != identity:
            raise ValueError('source changed during cache lookup')
        return cached, identity


def clear():
    PDF_BYTES.clear()
    PAGE_BYTES.clear()
