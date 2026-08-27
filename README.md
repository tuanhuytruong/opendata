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

The current Telegram slice supports the file-backed flow:

`/report` → **This machine** → upload CSV/XLSX → `columns` / `values <column>` → `/skip` → chart count → `add <dimension> by <metric>` → `/ok`.

Database selection is intentionally blocked until the read-only registered-source phase; it does not accept credentials through Telegram.

## Verification

```bash
.venv/bin/python -m pytest tests -v
npm run lint
npm run build
```

## Product scope

The present MVP supports CSV/XLSX and local DuckDB only. Planned work includes confirmed filter parsing in Telegram, richer chart families/evidence, durable run storage, and registered read-only PostgreSQL sources. This project does not restore or depend on the hidden NomaData repository.
