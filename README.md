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
