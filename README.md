# DD-1.0 Learning Service

An isolated learning-service prototype for source-material import and review, a mistake notebook, independent practice, server-side grading, review scheduling, and a thin Open WebUI Tools adapter.

The service owns its database and attachments. It does not write to Open WebUI's database or mount Open WebUI's data directory. The current implementation has deterministic mock providers for local development; real OCR/model quality, model-initiated Open WebUI tool calls, and final trusted browser callbacks remain unverified. This repository is not a production-readiness claim.

## Quick start

Requirements: Docker Compose, or Python 3.12 for local development.

```sh
cp .env.example .env
# Replace both example secrets in .env with long random values.
docker compose -f docker-compose.learning.yml -f docker-compose.learning.local-ui.yml up --build -d
curl http://127.0.0.1:31010/health
```

The local overlay binds the API to loopback for development. The base Compose file keeps the API on an internal network without publishing a host port. Do not expose the development overlay to a public network. To stop services while preserving the learning data volume:

```sh
docker compose -f docker-compose.learning.yml -f docker-compose.learning.local-ui.yml down
```

## Development and tests

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m compileall -q learning_service tests scripts
pytest -q
python scripts/verify_goal_consistency.py
```

See [the design and development documents](docs/README.md) for the API contract, migrations, verification evidence, backup/restore procedure, known limitations, and task status.

## Safety and validation boundary

- Defaults use deterministic mock providers. They do not establish real OCR accuracy or real learning outcomes.
- Production cutover, paid provider calls, and export of real learner materials require separate authorization and verification.
- The included browser reports use synthetic accounts and materials. T23 real-user trials have not started; T24–T26 are deferred.
- Set unique secrets through a local `.env`; never commit `.env`, databases, attachments, backups, exports, or learner materials.
