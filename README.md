# DD-1.0 Learning Service

2026-11-08: A09 [static packet and rollback validation](docs/verification/A09-static-samples-2026-11-08.md) passed 30 targeted checks and 4 candidate / 3 rollback routes in isolated nginx. [Delivery and device checklist](docs/open-webui-reuse/static-samples-delivery.md) is ready; deployment and parent feedback remain pending. Next local task: B01, chapter coverage. Earlier entries below are historical.

A08: the [existing Tool upgrade and rollback workflow](docs/open-webui-reuse/tool-upgrade-rollback.md) is a local candidate; [54 checks and native WebUI validation passed](docs/verification/A08-tool-lifecycle-2026-11-07.md). The formal Tool was not read or upgraded. Next: A09, static samples and device feedback.

2026-11-07: A07 [local excerpt integration](docs/verification/A07-runtime-passages-2026-11-07.md) is ready as an uncommitted candidate. Tool 1.2.0 retains six methods; excerpts are disabled by default and have not been deployed. [Runtime contract](docs/open-webui-reuse/textbook-passages-runtime.md). Next: A08, existing Tool upgrade and rollback in temporary data.

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
python -m pip install --require-hashes -r requirements-dev.lock
python -m playwright install --with-deps --no-shell chromium
python -m compileall -q learning_service tests scripts
python -m pytest -q
```

The default suite uses synthetic PDFs and temporary data. Chromium is pinned by Playwright; browser dependency failures and skipped required tests fail the run. See [portable tests and opt-in local material checks](docs/TESTING.md) for test groups, browser configuration, and Linux font requirements.

See [the design and development documents](docs/README.md) for the API contract, migrations, verification evidence, backup/restore procedure, known limitations, and task status.

## Safety and validation boundary

- Defaults use deterministic mock providers. They do not establish real OCR accuracy or real learning outcomes.
- Production cutover, paid provider calls, and export of real learner materials require separate authorization and verification.
- The included browser reports use synthetic accounts and materials. T23 real-user trials have not started; T24–T26 are deferred.
- Set unique secrets through a local `.env`; never commit `.env`, databases, attachments, backups, exports, or learner materials.
