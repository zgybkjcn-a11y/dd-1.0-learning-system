"""Install the 2026-11-18 cross-checked gap-candidate batches, additively.

Reads the sha256-pinned batch files from the image, validates every question,
and adds only missing versions. It never deletes, replaces or rewrites rows and
never touches attempts, review cards or other learning data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:  # also works when piped into `python -` inside the image
    ROOT = Path(__file__).resolve().parents[1]
except NameError:
    ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from learning_service import chapter_practice as chapter
from learning_service.db import Database

BATCHES = ['upper_gap_candidates', 'lower_gap_candidates'] + [
    'lower_gap_candidates_batch%d' % index for index in range(2, 9)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=None, help='learning.db path; defaults to LEARNING_DB_PATH')
    parser.add_argument('--batch', action='append', choices=BATCHES,
                        help='limit to one batch; repeatable; defaults to all nine')
    parser.add_argument('--dry-run', action='store_true', help='validate banks without writing')
    args = parser.parse_args()
    batches = args.batch or BATCHES
    if args.dry_run:
        loaded = {batch: len(chapter.bank(batch)) for batch in batches}
        print(json.dumps({'dry_run': True, 'questions': loaded}, ensure_ascii=False, indent=1))
        return
    db_path = args.db or os.environ.get('LEARNING_DB_PATH')
    if not db_path:
        raise SystemExit('pass --db or set LEARNING_DB_PATH')
    db = Database(Path(db_path))
    results = [chapter.install(db, batch) for batch in batches]
    print(json.dumps({'installed': results, 'added': sum(item['added'] for item in results)},
                     ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
