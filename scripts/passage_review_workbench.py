#!/usr/bin/env python3
"""Prepare/serve an isolated local passage review workspace, never deploy it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--workspace', type=Path, required=True)
    prepare.add_argument('--bundle', type=Path, required=True)
    prepare.add_argument('--manifest-sha256', required=True)
    prepare.add_argument('--textbook-dir', type=Path, required=True)
    prepare.add_argument('--passage-id', required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--workspace', type=Path, required=True)
    serve.add_argument('--reviewer-type', choices=('assistant', 'human'), required=True)
    serve.add_argument('--reviewer-label', required=True)
    serve.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if args.command == 'prepare':
        from learning_service.passage_review import prepare as prepare_workspace
        result = prepare_workspace(args.workspace, args.bundle, args.manifest_sha256, args.textbook_dir, args.passage_id)
        print(json.dumps({k: result[k] for k in ('seq', 'revision', 'available', 'blockers')}, ensure_ascii=False))
    else:
        import uvicorn
        from learning_service.passage_review_web import create_app
        if not 1024 <= args.port <= 65535:
            parser.error('port must be between 1024 and 65535')
        app = create_app(args.workspace, actor={'type': args.reviewer_type, 'label': args.reviewer_label},
                         origin=f'http://127.0.0.1:{args.port}')
        uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
