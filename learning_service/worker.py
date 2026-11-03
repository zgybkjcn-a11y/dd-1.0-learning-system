"""Durable worker entry point for the isolated DD-1.0 learning service."""

from __future__ import annotations

import os
import signal
import time

from .app import run_worker_once
from .config import Settings
from .db import Database


def main() -> None:
    settings = Settings.from_env()
    settings.ensure_dirs()
    db = Database(settings.db_path)
    interval = max(0.25, float(os.getenv("LEARNING_WORKER_INTERVAL", "2")))
    stopped = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopped:
        result = run_worker_once(db, settings)
        if result.get("status") == "idle":
            time.sleep(interval)


if __name__ == "__main__":
    main()
