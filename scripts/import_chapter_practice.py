#!/usr/bin/env python3
"""Install one frozen chapter batch into an explicitly selected existing database."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.chapter_practice import BATCHES, install
from learning_service.db import Database

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--batch', choices=BATCHES, required=True)
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit('existing database required')
    print(json.dumps(install(Database(args.database), args.batch), ensure_ascii=False))
