# OpenData Report Workspace

A safe, file-first analytics workspace that turns CSV/XLSX uploads into validated chart plans and portable HTML reports.

## What it does

- Profiles CSV/XLSX files server-side (up to **100 MB** / **600,000 rows**).
- Classifies columns and highlights data-quality risks, including mixed quantity units.
- Builds only server-calculated DuckDB aggregates from schema-validated dimensions, metrics and exact-value filters.
- Exports a self-contained HTML report with table fallbacks.
- Includes a transport-neutral Telegram conversation service and an optional polling runtime for the guided `/report` flow.

Raw rows, database credentials and unrestricted SQL are never sent to an AI model or accepted as chat commands.

## Local development

```bash
uv venv .venv
uv pip install -r services/api/requirements.txt

# Terminal 1: API
cd services/api
../../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8020

# Terminal 2: web workspace
npm install
npm run dev
```

Open the Vite URL (normally `http://127.0.0.1:5173`).

## Registered PostgreSQL & Oracle sources

Database analysis is **operator-registered only**. The service has no endpoint or Telegram command that accepts a connection string, schema/table name, or SQL.

In ignored `.env.local`, define `OPENDATA_SOURCES_JSON` and keep each connection value in the environment variable named by `connection_env` (see `.env.example`). Each entry is restricted to one pre-approved `schema.table`, with a maximum scan and statement-timeout value.

Required operational controls before enabling a live source:

- A dedicated database account with `SELECT` only on exactly the registered table/view; no DDL/DML permissions.
- PostgreSQL: connection timeout, `BEGIN READ ONLY`, and transaction-local `statement_timeout` are enforced by the adapter.
- Oracle: `SET TRANSACTION READ ONLY` and a configured `FETCH FIRST … ROWS ONLY` cap are enforced by the adapter.
- Public metadata: `GET /api/sources`; staging a selected source: `POST /api/sources/{source_id}/runs`.

The connector intentionally does not implement arbitrary SQL, cross-schema browsing, joins, or credential collection. Test doubles cover both adapters. A real connection smoke test remains pending until a non-production allow-listed source is configured.

## Telegram polling runtime (optional)

1. Create a bot with BotFather and place its token only in ignored `.env.local` or the process environment.
2. Export the token for the process; do not commit or paste it in reports:

```bash
export TELEGRAM_BOT_TOKEN='...'
cd services/api
../../.venv/bin/python -m telegram_runtime
```

The Telegram flow supports both **This machine** uploads and an operator-registered database source. It never accepts a connection string, table name or SQL from a chat message.

## Phase 7 pilot operations

- Each run is stored in its own `var/uploads/<run_id>/` directory with durable metadata and a **24-hour default retention**. `DELETE /api/runs/{run_id}` immediately removes it and its artifacts.
- `POST /api/jobs` creates a durable pilot job; `GET`/`DELETE /api/jobs/{job_id}` exposes status/cancellation. Run `python -m worker` as a separate internal process for bounded job validation/retry handling.
- `GET /api/health` is liveness; `GET /api/readiness` verifies writable artifact/job storage and performs expiry cleanup.
- `POST /api/maintenance/cleanup` is disabled unless `OPENDATA_MAINTENANCE_KEY` is configured, and requires the matching `X-OpenData-Maintenance-Key` header. Prefer an internal scheduler/network path.
- API requests are rate-limited in-process to 60/min/IP for the pilot. Before multiple API replicas, replace it with a shared reverse-proxy or Redis limiter.
- Common PII/secrets-like column names are masked in previews and rejected from values, filters, and charts. Configure database service accounts/views to exclude sensitive columns as a stronger upstream control.
- The app emits no raw rows, credentials or database driver errors in public responses. Put API + worker behind HTTPS, keep database/worker ports private, and do not expose the maintenance hook publicly.

## Verification

```bash
.venv/bin/python -m pytest tests -v
npm run lint
npm run build
```

## Product scope

The present pilot supports CSV/XLSX plus operator-registered PostgreSQL and Oracle sources, constrained filters/chart plans, durable local run artifacts, and evidence-bound offline HTML reports. It does not restore or depend on the hidden NomaData repository.
