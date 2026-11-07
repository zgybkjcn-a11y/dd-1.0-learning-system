"""Read explicitly named container secrets without logging their contents."""
from __future__ import annotations

import os
import stat


def env_secret(name: str) -> str:
    value, filename = os.getenv(name, ""), os.getenv(name + "_FILE", "")
    if not filename:
        return value
    if value:
        raise ValueError(name + ": choose either the value or its secret file")
    try:
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("not a regular file")
            data = stream.read(16385)
        if len(data) > 16384:
            raise ValueError("oversized secret")
        value = data.decode("utf-8").removesuffix("\n")
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("empty or multiline secret")
        return value
    except (OSError, UnicodeError, ValueError):
        raise ValueError(name + ": secret file is unavailable or invalid") from None
