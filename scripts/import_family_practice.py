#!/usr/bin/env python3
"""Incrementally install the frozen, independently checked family practice subset."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.db import Database
from learning_service.practice import install
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    if not args.database.is_file(): raise SystemExit('existing family database required')
    print(json.dumps(install(Database(args.database)), ensure_ascii=False))
