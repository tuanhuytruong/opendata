"""Read-only dataset profiling and chart API for OpenData report runs."""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import duckdb
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook
from pydantic import BaseModel, Field

from database_adapters import read_registered_source
from planning import evidence_for_chart, narrative_from_evidence, parse_filter, propose_charts
from source_registry import public_source, registered_sources

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_PROFILE_ROWS = 600_000
DATA_DIR = Path(__file__).resolve().parents[2] / "var" / "uploads"
VALID_CHARTS = {"bar", "line", "area", "scatter"}

app = FastAPI(title="OpenData Report API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:5174"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])


class ColumnProfile(BaseModel):
    name: str
    kind: Literal["time", "num", "cat", "id", "unknown"]
    null_count: int
    null_ratio: float
    distinct_count: int
    description: str


class DatasetProfile(BaseModel):
    run_id: str
    file_name: str
    row_count: int
    column_count: int
    usable_column_count: int
    columns: list[ColumnProfile]
    warnings: list[str]
    preview: list[dict[str, str]]


class FilterSpec(BaseModel):
    column: str
    operator: Literal["equals", "not_equals", "greater_than", "greater_or_equal", "less_than", "less_or_equal"] = "equals"
    value: str = Field(min_length=1, max_length=500)


class ChartRequest(BaseModel):
    dimension: str
    metric: str
    aggregation: Literal["sum", "avg", "count"] = "sum"
    chart_type: Literal["bar", "line", "area", "scatter", "pareto", "stacked_bar", "heatmap"] = "bar"
    secondary_dimension: str | None = None
    limit: int = Field(default=12, ge=1, le=30)
    filters: list[FilterSpec] = Field(default_factory=list, max_length=10)


class ReportRequest(BaseModel):
    title: str = Field(default="OpenData Analytics Report", min_length=1, max_length=120)
    charts: list[ChartRequest] = Field(min_length=1, max_length=12)


class TextFilterRequest(BaseModel):
    text: str = Field(min_length=3, max_length=600)


class ChartResult(BaseModel):
    dimension: str
    metric: str
    aggregation: str
    chart_type: str
    title: str
    secondary_dimension: str | None = None
    filters: list[FilterSpec] = Field(default_factory=list)
    rows: list[dict[str, str | float | int]]
    warnings: list[str]


def safe_name(name: str) -> str:
    return Path(name).name


def is_number(value: str) -> bool:
    try:
        float(value.replace(",", ""))
        return True
    except ValueError:
        return False


def is_date(value: str) -> bool:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def infer_kind(name: str, values: list[str]) -> str:
    observed = [value.strip() for value in values if value.strip()]
    if not observed:
        return "unknown"
    lower = name.lower()
    numeric_ratio = sum(is_number(value) for value in observed) / len(observed)
    date_ratio = sum(is_date(value) for value in observed) / len(observed)
    distinct = len(set(observed))
    if date_ratio >= .9 or (any(token in lower for token in ("date", "day", "month", "year", "period")) and date_ratio >= .5):
        return "time"
    if numeric_ratio >= .95:
        return "num"
    if ("id" in lower or "code" in lower) and distinct / len(observed) >= .9:
        return "id"
    return "cat"


def column_description(name: str, kind: str) -> str:
    hints = {"sale date": "Date on which the sales transaction was recorded.", "net sales": "Sales revenue after discounts and deductions.", "quantity": "Quantity recorded for the transaction.", "gross margin": "Difference between sales revenue and cost of goods sold."}
    return hints.get(name.lower().replace("_", " "), f"Inferred {kind} field from column name and observed values.")


def validate_headers(headers: list[str]) -> list[str]:
    clean = [str(header or "").strip() for header in headers]
    if len(clean) < 2 or any(not header for header in clean) or len(clean) != len(set(clean)):
        raise HTTPException(422, "Dataset must have at least two present, unique column headers.")
    return clean


def csv_rows(raw: bytes) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    headers = validate_headers(reader.fieldnames or [])
    rows = [{header: (row.get(header) or "").strip() for header in headers} for row in reader]
    return headers, rows


def xlsx_rows(raw: bytes) -> tuple[list[str], list[dict[str, str]]]:
    try:
        book = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_vba=False)
    except Exception as error:
        raise HTTPException(422, "Workbook could not be read. Password-protected or malformed XLSX files are not supported.") from error
    sheet = book.active
    iterator = sheet.iter_rows(values_only=True)
    try:
        headers = validate_headers([str(value or "") for value in next(iterator)])
    except StopIteration as error:
        raise HTTPException(422, "Workbook has no header row.") from error
    rows: list[dict[str, str]] = []
    for row_index, values in enumerate(iterator, start=1):
        if row_index > MAX_PROFILE_ROWS:
            raise HTTPException(422, f"Dataset exceeds the {MAX_PROFILE_ROWS:,}-row first-release limit.")
        row = {headers[index]: "" if index >= len(values) or values[index] is None else str(values[index]).strip() for index in range(len(headers))}
        if any(row.values()):
            rows.append(row)
    return headers, rows


def persist(run_id: str, headers: list[str], rows: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / f"{run_id}.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader(); writer.writerows(rows)


def load_run(run_id: str) -> tuple[list[str], list[dict[str, str]]]:
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise HTTPException(404, "Report run was not found.")
    path = DATA_DIR / f"{run_id}.csv"
    if not path.exists():
        raise HTTPException(404, "Report run was not found or has expired.")
    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        return validate_headers(reader.fieldnames or []), list(reader)


def profile(file_name: str, headers: list[str], rows: list[dict[str, str]], persist_run: bool = True, run_id: str | None = None) -> DatasetProfile:
    if not rows:
        raise HTTPException(422, "Dataset does not contain data rows.")
    if len(rows) > MAX_PROFILE_ROWS:
        raise HTTPException(422, f"Dataset exceeds the {MAX_PROFILE_ROWS:,}-row first-release limit.")
    profiles: list[ColumnProfile] = []
    warnings: list[str] = []
    for header in headers:
        values = [(row.get(header) or "").strip() for row in rows]
        null_count = sum(not value for value in values)
        kind = infer_kind(header, values)
        profiles.append(ColumnProfile(name=header, kind=cast(Literal["time", "num", "cat", "id", "unknown"], kind), null_count=null_count, null_ratio=round(null_count / len(rows), 4), distinct_count=len({value for value in values if value}), description=column_description(header, kind)))
        if null_count / len(rows) >= .95:
            warnings.append(f"{header} is {null_count / len(rows):.1%} empty and may not be useful for charts.")
    units = next((item for item in profiles if item.name.lower() in {"unit_of_measure", "uom"}), None)
    quantity = next((item for item in profiles if item.name.lower() == "quantity"), None)
    if units and quantity and units.distinct_count > 1:
        warnings.append("Quantity has multiple units of measure; do not sum it until a compatible unit filter is applied.")
    resolved_run_id = run_id or uuid4().hex
    if persist_run:
        persist(resolved_run_id, headers, rows)
    return DatasetProfile(run_id=resolved_run_id, file_name=file_name, row_count=len(rows), column_count=len(headers), usable_column_count=sum(item.kind != "unknown" for item in profiles), columns=profiles, warnings=warnings, preview=rows[:20])


def quote_identifier(name: str, headers: list[str]) -> str:
    if name not in headers:
        raise HTTPException(422, f"Unknown column: {name}")
    return '"' + name.replace('"', '""') + '"'


@app.get("/api/health")
def health() -> dict[str, str]: return {"status": "ok"}


@app.get("/api/sources")
def list_sources() -> dict[str, list[dict[str, object]]]:
    """Expose only operator-registered source metadata; never connection material."""
    return {"sources": [public_source(source) for source in registered_sources().values()]}


@app.post("/api/sources/{source_id}/runs", response_model=DatasetProfile, status_code=201)
def stage_registered_source(source_id: str) -> DatasetProfile:
    sources = registered_sources()
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(404, "Registered source was not found.")
    headers, rows = read_registered_source(source)
    headers = validate_headers(headers)
    normalized = [{header: (row.get(header) or "").strip() for header in headers} for row in rows]
    if len(normalized) >= source.max_rows:
        raise HTTPException(422, f"Registered source reached its {source.max_rows:,}-row scan cap; narrow its operator configuration.")
    return profile(f"{source.display_name} ({source.locator})", headers, normalized)


def ingest_dataset(file_name: str, raw: bytes) -> DatasetProfile:
    """Validate and profile a file payload from either web or Telegram transport."""
    name = safe_name(file_name or "upload")
    if not re.fullmatch(r"[\w .()\-]+\.(csv|xlsx)", name, flags=re.IGNORECASE):
        raise HTTPException(415, "Upload a CSV or XLSX file with a safe file name.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES // 1024 // 1024} MB upload limit.")
    headers, rows = xlsx_rows(raw) if name.lower().endswith(".xlsx") else csv_rows(raw)
    return profile(name, headers, rows)


@app.post("/api/runs/upload", response_model=DatasetProfile, status_code=201)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetProfile:
    return ingest_dataset(file.filename or "upload", await file.read(MAX_UPLOAD_BYTES + 1))


@app.get("/api/runs/{run_id}/plan")
def suggested_plan(run_id: str, limit: int = 8) -> dict[str, object]:
    headers, rows = load_run(run_id)
    profile_data = profile("existing-run", headers, rows, persist_run=False, run_id=run_id)
    return {"charts": propose_charts(profile_data.columns, max(1, min(limit, 12))), "note": "Candidates are deterministic suggestions; review and approve before report generation."}


@app.post("/api/runs/{run_id}/parse-filter")
def parse_text_filter(run_id: str, request: TextFilterRequest) -> dict[str, object]:
    headers, _ = load_run(run_id)
    try:
        parsed = parse_filter(request.text, headers)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {"filter": {"column": parsed.column, "operator": parsed.operator, "value": parsed.value}, "confirmation": f"Apply {parsed.column} {parsed.operator.replace('_', ' ')} {parsed.value}?"}


@app.get("/api/runs/{run_id}/values/{column}")
def values(run_id: str, column: str) -> dict[str, str | list[str]]:
    headers, rows = load_run(run_id)
    quote_identifier(column, headers)
    result = sorted({(row.get(column) or "").strip() for row in rows if (row.get(column) or "").strip()})[:100]
    return {"column": column, "values": result}


@app.post("/api/runs/{run_id}/chart", response_model=ChartResult)
def build_chart(run_id: str, request: ChartRequest) -> ChartResult:
    headers, rows = load_run(run_id)
    dimension = quote_identifier(request.dimension, headers)
    metric = quote_identifier(request.metric, headers)
    secondary = quote_identifier(request.secondary_dimension, headers) if request.secondary_dimension else None
    if request.chart_type in {"stacked_bar", "heatmap"} and not secondary:
        raise HTTPException(422, f"{request.chart_type} requires a secondary_dimension.")
    if request.aggregation == "count": expression = "COUNT(*)"
    else: expression = f"{request.aggregation.upper()}(TRY_CAST(REPLACE({metric}, ',', '') AS DOUBLE))"
    filter_clauses = [f"{dimension} IS NOT NULL", f"TRIM({dimension}) <> ''"]
    if secondary:
        filter_clauses.extend([f"{secondary} IS NOT NULL", f"TRIM({secondary}) <> ''"])
    parameters: list[str | int | float] = []
    for item in request.filters:
        field = quote_identifier(item.column, headers)
        operators = {"equals": "=", "not_equals": "<>", "greater_than": ">", "greater_or_equal": ">=", "less_than": "<", "less_or_equal": "<="}
        operator = operators[item.operator]
        if item.operator in {"greater_than", "greater_or_equal", "less_than", "less_or_equal"}:
            if not is_number(item.value):
                raise HTTPException(422, f"Numeric comparison requires a numeric value for {item.column}.")
            filter_clauses.append(f"TRY_CAST(REPLACE({field}, ',', '') AS DOUBLE) {operator} ?")
            parameters.append(float(item.value.replace(",", "")))
        else:
            filter_clauses.append(f"{field} {operator} ?")
            parameters.append(item.value)
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("CREATE TABLE dataset AS SELECT * FROM read_csv_auto(?, all_varchar=true)", [str(DATA_DIR / f"{run_id}.csv")])
        where_clause = " AND ".join(filter_clauses)
        if secondary:
            query = f"SELECT {dimension} AS label, {secondary} AS secondary_label, {expression} AS value FROM dataset WHERE {where_clause} GROUP BY 1, 2 ORDER BY value DESC NULLS LAST LIMIT ?"
        else:
            query = f"SELECT {dimension} AS label, {expression} AS value FROM dataset WHERE {where_clause} GROUP BY 1 ORDER BY value DESC NULLS LAST LIMIT ?"
        records = connection.execute(query, [*parameters, request.limit]).fetchall()
    finally:
        connection.close()
    warnings: list[str] = []
    if not records: warnings.append("This chart has no matching values.")
    if request.metric.lower() == "quantity" and request.aggregation == "sum": warnings.append("Verify a compatible unit filter before interpreting summed quantity.")
    if secondary:
        chart_rows = [{"label": str(label), "secondary_label": str(second), "value": 0 if value is None else float(value)} for label, second, value in records]
    else:
        chart_rows = [{"label": str(label), "value": 0 if value is None else float(value)} for label, value in records]
    if request.chart_type == "pareto":
        total = sum(float(row["value"]) for row in chart_rows)
        running = 0.0
        for row in chart_rows:
            running += float(row["value"])
            row["cumulative_pct"] = 0 if total == 0 else round(running / total * 100, 2)
    title = f"{request.aggregation.upper()} {request.metric} by {request.dimension}" + (f" × {request.secondary_dimension}" if secondary else "")
    return ChartResult(dimension=request.dimension, metric=request.metric, aggregation=request.aggregation, chart_type=request.chart_type, title=title, secondary_dimension=request.secondary_dimension, filters=request.filters, rows=chart_rows, warnings=warnings)


@app.get("/api/runs/{run_id}/manifest")
def get_manifest(run_id: str) -> dict[str, object]:
    load_run(run_id)
    path = DATA_DIR / f"{run_id}.manifest.json"
    if not path.exists():
        raise HTTPException(404, "Report manifest is not available until a report is generated.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/runs/{run_id}/report", response_class=HTMLResponse)
def build_report(run_id: str, request: ReportRequest) -> HTMLResponse:
    """Render a portable HTML artifact from validated, server-calculated charts."""
    charts = [build_chart(run_id, item) for item in request.charts]
    payload = [chart.model_dump() for chart in charts]
    evidence = [fact for chart in charts for fact in evidence_for_chart(chart)]
    narratives = narrative_from_evidence(evidence)
    manifest = {"run_id": run_id, "generated_at": datetime.now(timezone.utc).isoformat(), "dataset_sha256": hashlib.sha256((DATA_DIR / f"{run_id}.csv").read_bytes()).hexdigest(), "chart_specs": [item.model_dump() for item in request.charts], "chart_count": len(charts), "evidence": evidence}
    (DATA_DIR / f"{run_id}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    safe_title = html.escape(request.title)
    artifact = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title><style>body{{font:15px system-ui;margin:0;background:#f8fafc;color:#172554}}main{{max-width:1100px;margin:auto;padding:36px}}.meta,.card{{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:20px;margin:16px 0}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #e2e8f0;text-align:left}}th{{color:#475569}}.warning{{color:#92400e;background:#fffbeb;padding:10px;border-radius:8px}}</style></head><body><main><h1>{safe_title}</h1><p>Generated from validated report run <code>{run_id[:8]}</code>. Values below are deterministic server-side aggregates.</p><section class="meta"><h2>Evidence-bound highlights</h2><ul>{''.join(f'<li>{html.escape(item)}</li>' for item in narratives) or '<li>No narrative evidence was available.</li>'}</ul></section><section class="meta"><h2>Provenance</h2><p>Dataset checksum: <code>{manifest['dataset_sha256']}</code>. Filter scope and chart specifications are retained in the run manifest.</p></section><div id="charts"></div></main><script>const charts={json.dumps(payload)};const e=s=>String(s).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));document.querySelector('#charts').innerHTML=charts.map(c=>`<section class="card"><h2>${{e(c.title)}}</h2>${{c.warnings.map(w=>`<p class="warning">${{e(w)}}</p>`).join('')}}<table><thead><tr><th>${{e(c.dimension)}}</th>${{c.secondary_dimension?`<th>${{e(c.secondary_dimension)}}</th>`:''}}<th>${{e(c.aggregation)}} ${{e(c.metric)}}</th></tr></thead><tbody>${{c.rows.map(r=>`<tr><td>${{e(r.label)}}</td>${{c.secondary_dimension?`<td>${{e(r.secondary_label ?? '')}}</td>`:''}}<td>${{r.value.toLocaleString()}}</td></tr>`).join('')}}</tbody></table></section>`).join('');</script></body></html>'''
    return HTMLResponse(artifact, headers={"Content-Disposition": 'attachment; filename="opendata-report.html"'})
