"""Read-only dataset profiling and chart API for OpenData report runs."""
from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import hmac
import html
import io
import json
import math
import os
from collections import Counter
import urllib.error
import urllib.request
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import duckdb
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from openpyxl import load_workbook
from pydantic import BaseModel, Field

from database_adapters import read_registered_source
from formatting import compact_number, format_display_date, parse_date_value, percent
from planning import analyst_proposals, evidence_for_chart, is_starter_analysis_request, narrative_from_evidence, parse_filter, propose_charts
from source_registry import public_source, registered_sources
from run_store import DurableJobQueue, RunStore

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_PROFILE_ROWS = 600_000
MAX_REQUESTS_PER_MINUTE = 240
MAX_EDA_COLUMNS = 100
MAX_EDA_TOP_CATEGORIES = 10
# Attach profiles inspect a bounded, deterministic sample. Full profiles are computed
# only when a caller explicitly asks for one of the richer analysis endpoints.
ATTACH_PROFILE_SAMPLE_ROWS = 1_000
DATA_DIR = Path(__file__).resolve().parents[2] / "var" / "uploads"
JOB_DIR = Path(__file__).resolve().parents[2] / "var" / "jobs"
STATIC_DIR = Path(os.getenv("OPENDATA_STATIC_DIR", str(Path(__file__).resolve().parents[2] / "dist")))
RUN_STORE = RunStore(DATA_DIR)
JOB_QUEUE = DurableJobQueue(JOB_DIR)
PROFILE_CACHE: dict[str, DatasetProfile] = {}
VALID_CHARTS = {"bar", "line", "area", "scatter"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Optional pilot-only HTTP Basic Auth, configured exclusively by environment."""

    async def dispatch(self, request: Request, call_next):
        username = os.getenv("OPENDATA_BASIC_AUTH_USER", "").strip()
        password = os.getenv("OPENDATA_BASIC_AUTH_PASSWORD", "")
        if not username and not password:
            return await call_next(request)
        if not username or not password:
            return JSONResponse({"detail": "Basic Auth configuration is invalid."}, status_code=503)
        authorization = request.headers.get("authorization", "")
        valid = False
        if authorization.startswith("Basic "):
            try:
                decoded = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
                supplied_user, supplied_password = decoded.split(":", 1)
                valid = hmac.compare_digest(supplied_user, username) and hmac.compare_digest(supplied_password, password)
            except (ValueError, UnicodeDecodeError, binascii.Error):
                valid = False
        if not valid:
            return JSONResponse(
                {"detail": "Authentication required."},
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="OpenData pilot", charset="UTF-8"'},
            )
        return await call_next(request)


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Conservative pilot safeguard; replace with shared rate limiting before scale-out."""
    buckets: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/api/health", "/api/readiness"}:
            return await call_next(request)
        now = datetime.now(timezone.utc).timestamp()
        client = request.client.host if request.client else "unknown"
        active = [stamp for stamp in self.buckets.get(client, []) if stamp > now - 60]
        if len(active) >= MAX_REQUESTS_PER_MINUTE:
            return JSONResponse({"detail": "Request rate limit exceeded. Try again shortly."}, status_code=429)
        self.buckets[client] = [*active, now]
        return await call_next(request)


app = FastAPI(title="OpenData Report API", version="0.3.0")
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware)
app.add_middleware(BasicAuthMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:5174"], allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["content-type"])


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
    # "sampled" is safe to render immediately after attach; "complete" means the
    # retained dataset has received the full, cached profile.
    profile_status: Literal["sampled", "complete"] = "complete"
    profiled_row_count: int = 0


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


class JobRequest(BaseModel):
    run_id: str
    kind: Literal["profile", "report"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    context: str = Field(default="", max_length=1000)
    language: Literal["en", "vi"] = "en"


class ClarificationOption(BaseModel):
    column: str
    label: str
    reason: str
    role: Literal["metric", "dimension"]


class SemanticSelectionRequest(BaseModel):
    """A user-confirmed schema choice, retained only with its report run."""
    column: str = Field(min_length=1, max_length=160)
    role: Literal["metric", "dimension"]
    language: str = Field(default="en", min_length=2, max_length=12)


class SemanticSelection(BaseModel):
    column: str
    role: Literal["metric", "dimension"]


class ChatResponse(BaseModel):
    answer: str
    insight: str
    scope: str
    title: str = ""
    chart: "ChartResult | None" = None
    table: list[dict[str, str | float | int]] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    clarification_options: list[ClarificationOption] = Field(default_factory=list)
    proposals: list[dict[str, object]] = Field(default_factory=list)
    mode: Literal["analysis", "clarification"]
    planner: Literal["llm", "deterministic"] = "deterministic"


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
    sort_mode: Literal["chronological", "ranking"] = "ranking"
    result_count: int = 0
    insight_headline: str = ""
    evidence: list[str] = Field(default_factory=list)


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


SENSITIVE_COLUMN_TOKENS = {"email", "e-mail", "phone", "mobile", "address", "password", "token", "secret", "ssn", "passport", "national_id", "credit_card"}


def is_sensitive_column(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return any(token in normalized for token in SENSITIVE_COLUMN_TOKENS)


def csv_rows(raw: bytes) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    headers = validate_headers(reader.fieldnames or [])
    rows: list[dict[str, str]] = []
    for row_index, row in enumerate(reader, start=1):
        if row_index > MAX_PROFILE_ROWS:
            raise HTTPException(422, f"Dataset exceeds the {MAX_PROFILE_ROWS:,}-row first-release limit.")
        rows.append({header: (row.get(header) or "").strip() for header in headers})
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


def persist(run_id: str, headers: list[str], rows: list[dict[str, str]], *, file_name: str, source_type: str = "file", source_label: str | None = None) -> None:
    RUN_STORE.save_dataset(run_id, headers, rows, file_name=file_name, source_type=source_type, source_label=source_label)


def load_run(run_id: str) -> tuple[list[str], list[dict[str, str]]]:
    headers, rows = RUN_STORE.load_dataset(run_id)
    return validate_headers(headers), rows


def build_profile(file_name: str, headers: list[str], rows: list[dict[str, str]], *, run_id: str, sample_limit: int | None = None) -> DatasetProfile:
    """Build a safe profile from all rows or a deterministic bounded prefix."""
    if not rows:
        raise HTTPException(422, "Dataset does not contain data rows.")
    if len(rows) > MAX_PROFILE_ROWS:
        raise HTTPException(422, f"Dataset exceeds the {MAX_PROFILE_ROWS:,}-row first-release limit.")
    profiled_rows = rows if sample_limit is None else rows[:sample_limit]
    profiles: list[ColumnProfile] = []
    warnings: list[str] = []
    for header in headers:
        values = [(row.get(header) or "").strip() for row in profiled_rows]
        null_count = sum(not value for value in values)
        kind = "id" if is_sensitive_column(header) else infer_kind(header, values)
        description = "Sensitive field; values are masked and cannot be used in analysis." if is_sensitive_column(header) else column_description(header, kind)
        profiles.append(ColumnProfile(name=header, kind=cast(Literal["time", "num", "cat", "id", "unknown"], kind), null_count=null_count, null_ratio=round(null_count / len(profiled_rows), 4), distinct_count=len({value for value in values if value}), description=description))
        if null_count / len(profiled_rows) >= .95:
            warnings.append(f"{header} is {null_count / len(profiled_rows):.1%} empty and may not be useful for charts.")
    units = next((item for item in profiles if item.name.lower() in {"unit_of_measure", "uom"}), None)
    quantity = next((item for item in profiles if item.name.lower() == "quantity"), None)
    if units and quantity and units.distinct_count > 1:
        warnings.append("Quantity has multiple units of measure; do not sum it until a compatible unit filter is applied.")
    sampled = len(profiled_rows) < len(rows)
    if sampled:
        warnings.append(f"Column metadata is sampled from the first {len(profiled_rows):,} rows; request full analysis for complete statistics.")
    return DatasetProfile(run_id=run_id, file_name=file_name, row_count=len(rows), column_count=len(headers), usable_column_count=sum(item.kind != "unknown" for item in profiles), columns=profiles, warnings=warnings, preview=safe_preview(rows), profile_status="sampled" if sampled else "complete", profiled_row_count=len(profiled_rows))


def profile_for_run(run_id: str, headers: list[str], rows: list[dict[str, str]]) -> DatasetProfile:
    """Compute the full profile only on demand, then retain it per API process."""
    cached = PROFILE_CACHE.get(run_id)
    if cached is not None:
        return cached
    metadata = RUN_STORE.metadata(run_id)
    result = build_profile(str(metadata["file_name"]), headers, rows, run_id=run_id)
    PROFILE_CACHE[run_id] = result
    return result


def profile(file_name: str, headers: list[str], rows: list[dict[str, str]], persist_run: bool = True, run_id: str | None = None, source_type: str = "file", source_label: str | None = None) -> DatasetProfile:
    """Create a complete profile for callers that already require rich metadata."""
    resolved_run_id = run_id or uuid4().hex
    if persist_run:
        persist(resolved_run_id, headers, rows, file_name=file_name, source_type=source_type, source_label=source_label)
    result = build_profile(file_name, headers, rows, run_id=resolved_run_id)
    PROFILE_CACHE[resolved_run_id] = result
    return result


def attach_profile(file_name: str, headers: list[str], rows: list[dict[str, str]], *, source_type: str = "file", source_label: str | None = None) -> DatasetProfile:
    """Persist a validated run first, then return only its bounded attach profile."""
    if not rows:
        raise HTTPException(422, "Dataset does not contain data rows.")
    if len(rows) > MAX_PROFILE_ROWS:
        raise HTTPException(422, f"Dataset exceeds the {MAX_PROFILE_ROWS:,}-row first-release limit.")
    run_id = uuid4().hex
    persist(run_id, headers, rows, file_name=file_name, source_type=source_type, source_label=source_label)
    return build_profile(file_name, headers, rows, run_id=run_id, sample_limit=ATTACH_PROFILE_SAMPLE_ROWS)


def safe_preview(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{column: "[masked]" if is_sensitive_column(column) and value else value for column, value in row.items()} for row in rows[:20]]


def _finite_number(value: str) -> float | None:
    """Return a JSON-safe numeric value, without accepting NaN or infinity."""
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _numeric_summary(values: list[str]) -> dict[str, float | int]:
    numbers = sorted(number for value in values if (number := _finite_number(value)) is not None)
    count = len(numbers)
    if not count:
        return {"valid_count": 0, "invalid_count": len(values)}
    midpoint = count // 2
    median = numbers[midpoint] if count % 2 else (numbers[midpoint - 1] + numbers[midpoint]) / 2
    return {
        "valid_count": count,
        "invalid_count": len(values) - count,
        "min": numbers[0],
        "max": numbers[-1],
        "mean": round(sum(numbers) / count, 6),
        "median": round(median, 6),
    }


def _time_coverage(values: list[str]) -> dict[str, str | int]:
    parsed = sorted(value for value in (parse_date_value(item) for item in values) if value is not None)
    if not parsed:
        return {"valid_count": 0, "invalid_count": len(values)}
    return {
        "valid_count": len(parsed),
        "invalid_count": len(values) - len(parsed),
        "start": parsed[0].isoformat(),
        "end": parsed[-1].isoformat(),
    }


def _top_categories(values: list[str]) -> list[dict[str, str | int]]:
    counts = Counter(values)
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:MAX_EDA_TOP_CATEGORIES]
    ]


def exploratory_data_analysis(run_id: str, headers: list[str], rows: list[dict[str, str]]) -> dict[str, object]:
    """Produce a bounded, deterministic run-scoped EDA summary.

    This deliberately avoids database query input and skips all value-level output
    for sensitive columns. Category values are capped and only returned for fields
    whose names pass the existing sensitive-column guard.
    """
    metadata = RUN_STORE.metadata(run_id)
    profile_data = profile_for_run(run_id, headers, rows)
    profiles = {item.name: item for item in profile_data.columns}
    visible_headers = [header for header in headers if not is_sensitive_column(header)][:MAX_EDA_COLUMNS]
    columns: list[dict[str, object]] = []
    for header in visible_headers:
        values = [(row.get(header) or "").strip() for row in rows]
        observed = [value for value in values if value]
        column = profiles[header]
        quality: dict[str, object] = {
            "non_null_count": len(observed),
            "null_count": column.null_count,
            "null_ratio": column.null_ratio,
            "distinct_count": column.distinct_count,
            "distinct_ratio": round(column.distinct_count / len(observed), 4) if observed else 0.0,
        }
        detail: dict[str, object] = {}
        if column.kind == "num":
            detail["numeric_summary"] = _numeric_summary(observed)
        elif column.kind == "time":
            detail["time_coverage"] = _time_coverage(observed)
        elif column.kind == "cat":
            detail["top_categories"] = _top_categories(observed)
        columns.append({"name": header, "kind": column.kind, "quality": quality, **detail})
    sensitive_column_count = sum(is_sensitive_column(header) for header in headers)
    return {
        "run_id": run_id,
        "coverage": {
            "row_count": len(rows),
            "column_count": len(headers),
            "analyzed_column_count": len(columns),
            "suppressed_sensitive_column_count": sensitive_column_count,
            "suppressed_column_count": len(headers) - len(columns) - sensitive_column_count,
        },
        "columns": columns,
        "provenance": {
            "dataset_sha256": hashlib.sha256(RUN_STORE.dataset_path(run_id).read_bytes()).hexdigest(),
            "source_type": metadata["source_type"],
            "source_label": metadata["source_label"],
            "analysis": "deterministic, bounded run-scoped summary",
            "top_category_limit": MAX_EDA_TOP_CATEGORIES,
        },
        "guardrails": [
            "Sensitive columns are excluded from value-level EDA.",
            f"Top categories are limited to {MAX_EDA_TOP_CATEGORIES} per non-sensitive categorical column.",
            f"At most {MAX_EDA_COLUMNS} non-sensitive columns are analyzed.",
        ],
    }


def quote_identifier(name: str, headers: list[str]) -> str:
    if name not in headers:
        raise HTTPException(422, f"Unknown column: {name}")
    if is_sensitive_column(name):
        raise HTTPException(422, "Sensitive columns cannot be used in filters, previews, or charts.")
    return '"' + name.replace('"', '""') + '"'


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/readiness")
def readiness() -> dict[str, object]:
    """Readiness is intentionally dependency-light: sources are checked on use."""
    try:
        RUN_STORE.root.mkdir(parents=True, exist_ok=True)
        JOB_QUEUE.root.mkdir(parents=True, exist_ok=True)
        RUN_STORE.cleanup_expired()
    except OSError as error:
        raise HTTPException(503, "Artifact storage is not writable.") from error
    return {"status": "ready", "registered_source_count": len(registered_sources())}


@app.delete("/api/runs/{run_id}", status_code=204)
def delete_run(run_id: str) -> None:
    """Explicitly delete a run and every retained artifact; idempotency is not assumed."""
    RUN_STORE.metadata(run_id)
    import shutil
    shutil.rmtree(RUN_STORE._dir(run_id), ignore_errors=True)
    PROFILE_CACHE.pop(run_id, None)


@app.post("/api/maintenance/cleanup")
def cleanup_expired_runs(request: Request) -> dict[str, int]:
    """Internal scheduler hook; disabled unless an operator configures its key."""
    key = os.getenv("OPENDATA_MAINTENANCE_KEY", "")
    provided = request.headers.get("X-OpenData-Maintenance-Key", "")
    if not key or not secrets.compare_digest(provided, key):
        raise HTTPException(404, "Not found.")
    return {"removed_runs": RUN_STORE.cleanup_expired()}


@app.post("/api/jobs", status_code=202)
def enqueue_job(request: JobRequest) -> dict[str, object]:
    RUN_STORE.metadata(request.run_id)
    job_id = uuid4().hex
    return JOB_QUEUE.create(job_id, request.run_id, request.kind)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, object]:
    return JOB_QUEUE.get(job_id)


@app.delete("/api/jobs/{job_id}")
def cancel_job(job_id: str) -> dict[str, object]:
    return JOB_QUEUE.cancel(job_id)


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
    return profile(f"{source.display_name} ({source.locator})", headers, normalized, source_type=source.engine, source_label=f"{source.display_name} ({source.locator})")


def ingest_dataset(file_name: str, raw: bytes) -> DatasetProfile:
    """Validate and persist a file, returning a bounded profile for immediate attach."""
    name = safe_name(file_name or "upload")
    if not re.fullmatch(r"[\w .()\-]+\.(csv|xlsx)", name, flags=re.IGNORECASE):
        raise HTTPException(415, "Upload a CSV or XLSX file with a safe file name.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES // 1024 // 1024} MB upload limit.")
    headers, rows = xlsx_rows(raw) if name.lower().endswith(".xlsx") else csv_rows(raw)
    return attach_profile(name, headers, rows)


@app.post("/api/runs/upload", response_model=DatasetProfile, status_code=201)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetProfile:
    return ingest_dataset(file.filename or "upload", await file.read(MAX_UPLOAD_BYTES + 1))


@app.get("/api/runs/{run_id}/profile/status", response_model=DatasetProfile)
def profile_status(run_id: str) -> DatasetProfile:
    """Lazily materialize the complete profile; later requests use the process cache."""
    cached = PROFILE_CACHE.get(run_id)
    if cached is not None:
        return cached
    headers, rows = load_run(run_id)
    return profile_for_run(run_id, headers, rows)


@app.get("/api/runs/{run_id}/plan")
def suggested_plan(run_id: str, limit: int = 8) -> dict[str, object]:
    headers, rows = load_run(run_id)
    profile_data = profile_for_run(run_id, headers, rows)
    return {"charts": propose_charts(profile_data.columns, max(1, min(limit, 12))), "note": "Candidates are deterministic suggestions; review and approve before report generation."}


def starter_views_payload(run_id: str, language: Literal["en", "vi"] = "en") -> dict[str, object]:
    """Return safe, selectable views from profile metadata only; never execute a chart."""
    headers, rows = load_run(run_id)
    profile_data = profile_for_run(run_id, headers, rows)
    proposals = analyst_proposals(profile_data.columns, language=language)
    for proposal in proposals:
        request = cast(dict[str, object], proposal["request"])
        proposal["question"] = (f"{request['metric']} thay đổi theo {request['dimension']} như thế nào?" if language == "vi" else f"How does {request['metric']} vary by {request['dimension']}?")

    return {
        "summary": f"Run này có {profile_data.row_count:,} dòng, {profile_data.usable_column_count} cột có thể dùng, {sum(item.kind == 'num' for item in profile_data.columns)} chỉ tiêu số và {sum(item.kind in {'cat', 'time'} for item in profile_data.columns)} trường phân tích." if language == "vi" else f"This run has {profile_data.row_count:,} rows, {profile_data.usable_column_count} usable columns, {sum(item.kind == 'num' for item in profile_data.columns)} metrics and {sum(item.kind in {'cat', 'time'} for item in profile_data.columns)} dimensions/time fields.",
        "proposals": proposals,
        "guardrail": "Gợi ý chỉ dùng vai trò cột suy luận và số liệu profile. Chart chỉ chạy sau khi bạn phê duyệt và luôn dùng aggregate đã xác thực trên server." if language == "vi" else "Suggestions use inferred column roles and profile counts only. Charts run only after your approval and always use validated server-side aggregates.",
    }


@app.get("/api/runs/{run_id}/analyst-proposals")
def analyst_plan(run_id: str, language: Literal["en", "vi"] = "en") -> dict[str, object]:
    return starter_views_payload(run_id, language)


@app.get("/api/runs/{run_id}/starter-views")
def starter_views(run_id: str, language: Literal["en", "vi"] = "en") -> dict[str, object]:
    return starter_views_payload(run_id, language)


@app.get("/api/runs/{run_id}/eda")
def eda_for_run(run_id: str) -> dict[str, object]:
    """Return deterministic, bounded EDA for one retained report run."""
    headers, rows = load_run(run_id)
    return exploratory_data_analysis(run_id, headers, rows)


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
def build_chart(run_id: str, request: ChartRequest, language: Literal["en", "vi"] = "vi") -> ChartResult:
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
    profile_data = profile_for_run(run_id, headers, rows)
    dimension_profile = next(item for item in profile_data.columns if item.name == request.dimension)
    chronological = request.chart_type in {"line", "area"} and dimension_profile.kind == "time" and not secondary
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("CREATE TABLE dataset AS SELECT * FROM read_csv_auto(?, all_varchar=true)", [str(RUN_STORE.dataset_path(run_id))])
        where_clause = " AND ".join(filter_clauses)
        if secondary:
            query = f"SELECT {dimension} AS label, {secondary} AS secondary_label, {expression} AS value FROM dataset WHERE {where_clause} GROUP BY 1, 2 ORDER BY value DESC NULLS LAST LIMIT ?"
        elif chronological:
            query = f"SELECT {dimension} AS label, {expression} AS value FROM dataset WHERE {where_clause} GROUP BY 1 ORDER BY TRY_CAST({dimension} AS TIMESTAMP) ASC NULLS LAST LIMIT ?"
        else:
            query = f"SELECT {dimension} AS label, {expression} AS value FROM dataset WHERE {where_clause} GROUP BY 1 ORDER BY value DESC NULLS LAST LIMIT ?"
        records = connection.execute(query, [*parameters, request.limit]).fetchall()
    finally:
        connection.close()
    warnings: list[str] = []
    if not records: warnings.append("Không có giá trị phù hợp với phạm vi hiện tại." if language == "vi" else "No values match the current scope.")
    if request.metric.lower() == "quantity" and request.aggregation == "sum": warnings.append("Cần lọc theo đơn vị tương thích trước khi diễn giải tổng quantity." if language == "vi" else "Filter to compatible units before interpreting a total quantity.")
    if request.chart_type in {"line", "area"} and not chronological:
        warnings.append("Trục đang không phải trường thời gian đã xác nhận; kết quả được xếp hạng theo giá trị thay vì diễn giải như xu hướng." if language == "vi" else "The axis is not a confirmed time field; results are ranked by value rather than interpreted as a trend.")
    if secondary:
        chart_rows = [{"label": str(label), "display_label": format_display_date(str(label)) if dimension_profile.kind == "time" else str(label), "secondary_label": str(second), "value": 0 if value is None else float(value), "formatted_value": compact_number(0 if value is None else float(value))} for label, second, value in records]
    else:
        chart_rows = [{"label": str(label), "display_label": format_display_date(str(label)) if dimension_profile.kind == "time" else str(label), "value": 0 if value is None else float(value), "formatted_value": compact_number(0 if value is None else float(value))} for label, value in records]
    if request.chart_type == "pareto":
        total = sum(float(row["value"]) for row in chart_rows)
        running = 0.0
        for row in chart_rows:
            running += float(row["value"])
            row["cumulative_pct"] = 0 if total == 0 else round(running / total * 100, 2)
    insight_headline, evidence = chart_insight(chart_rows, chronological, language)
    label = ("Xu hướng" if chronological else f"Top {len(chart_rows)}") if language == "vi" else ("Trend" if chronological else f"Top {len(chart_rows)}")
    title = (f"{label} {request.metric} theo {request.dimension}" if language == "vi" else f"{label} {request.metric} by {request.dimension}") + (f" × {request.secondary_dimension}" if secondary else "")
    return ChartResult(dimension=request.dimension, metric=request.metric, aggregation=request.aggregation, chart_type=request.chart_type, title=title, secondary_dimension=request.secondary_dimension, filters=request.filters, rows=chart_rows, warnings=warnings, sort_mode="chronological" if chronological else "ranking", result_count=len(chart_rows), insight_headline=insight_headline, evidence=evidence)


@app.get("/api/runs/{run_id}/manifest")
def get_manifest(run_id: str) -> dict[str, object]:
    return RUN_STORE.artifact_json(run_id, "report.manifest.json")


@app.post("/api/runs/{run_id}/report", response_class=HTMLResponse)
def build_report(run_id: str, request: ReportRequest) -> HTMLResponse:
    """Render a portable HTML artifact from validated, server-calculated charts."""
    charts = [build_chart(run_id, item) for item in request.charts]
    payload = [chart.model_dump() for chart in charts]
    evidence = [fact for chart in charts for fact in evidence_for_chart(chart)]
    narratives = narrative_from_evidence(evidence)
    metadata = RUN_STORE.metadata(run_id)
    manifest = {"run_id": run_id, "generated_at": datetime.now(timezone.utc).isoformat(), "dataset_sha256": hashlib.sha256(RUN_STORE.dataset_path(run_id).read_bytes()).hexdigest(), "source_type": metadata["source_type"], "source_label": metadata["source_label"], "chart_specs": [item.model_dump() for item in request.charts], "chart_count": len(charts), "evidence": evidence}
    RUN_STORE.save_artifact_json(run_id, "report.manifest.json", manifest)
    safe_title = html.escape(request.title)
    safe_chart_payload = json.dumps(payload).replace("</", "<\\/")
    artifact = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title><style>body{{font:15px system-ui;margin:0;background:#f8fafc;color:#172554}}main{{max-width:1100px;margin:auto;padding:36px}}.meta,.card{{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:20px;margin:16px 0}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #e2e8f0;text-align:left}}th{{color:#475569}}.warning{{color:#92400e;background:#fffbeb;padding:10px;border-radius:8px}}</style></head><body><main><h1>{safe_title}</h1><p>Generated from validated report run <code>{run_id[:8]}</code>. Values below are deterministic server-side aggregates.</p><section class="meta"><h2>Evidence-bound highlights</h2><ul>{''.join(f'<li>{html.escape(item)}</li>' for item in narratives) or '<li>No narrative evidence was available.</li>'}</ul></section><section class="meta"><h2>Provenance</h2><p>Dataset checksum: <code>{manifest['dataset_sha256']}</code>. Filter scope and chart specifications are retained in the run manifest.</p></section><div id="charts"></div></main><script>const charts={safe_chart_payload};const e=s=>String(s).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));document.querySelector('#charts').innerHTML=charts.map(c=>`<section class="card"><h2>${{e(c.title)}}</h2>${{c.warnings.map(w=>`<p class="warning">${{e(w)}}</p>`).join('')}}<table><thead><tr><th>${{e(c.dimension)}}</th>${{c.secondary_dimension?`<th>${{e(c.secondary_dimension)}}</th>`:''}}<th>${{e(c.aggregation)}} ${{e(c.metric)}}</th></tr></thead><tbody>${{c.rows.map(r=>`<tr><td>${{e(r.label)}}</td>${{c.secondary_dimension?`<td>${{e(r.secondary_label ?? '')}}</td>`:''}}<td>${{r.value.toLocaleString()}}</td></tr>`).join('')}}</tbody></table></section>`).join('');</script></body></html>'''
    return HTMLResponse(artifact, headers={"Content-Disposition": 'attachment; filename="opendata-report.html"'})


def _llm_chart_request(columns: list[ColumnProfile], request: ChatRequest) -> tuple[ChartRequest | None, str | None]:
    """Ask the configured LLM for JSON intent only; never disclose rows or execute its SQL."""
    base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "")
    safe_columns = [{"name": item.name, "kind": item.kind, "description": item.description, "distinct_count": item.distinct_count} for item in columns if item.kind != "id"]
    if not base_url or not api_key or not model or not safe_columns:
        return None, None
    prompt = {"role": "system", "content": "You are a read-only data intent parser. Return ONLY JSON: {dimension,metric,aggregation,chart_type,limit,clarification}. Select dimension and metric only from schema. Never return SQL. chart_type must be bar or line; aggregation must be sum, avg, or count. If ambiguous, set clarification."}
    user = {"role": "user", "content": json.dumps({"question": request.message, "prior_context": request.context[-1000:], "schema": safe_columns}, ensure_ascii=False)}
    payload = json.dumps({"model": model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [prompt, user]}).encode()
    try:
        http_request = urllib.request.Request(f"{base_url}/chat/completions", data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        decoder = json.JSONDecoder()
        with urllib.request.urlopen(http_request, timeout=8) as response:
            # A compatible gateway may concatenate JSON response objects. Read only
            # the first complete response object; the intent itself is independently validated below.
            outer, _ = decoder.raw_decode(response.read().decode().lstrip())
            if not isinstance(outer, dict):
                return None, None
            content = outer["choices"][0]["message"]["content"]
        # Some compatible gateways append a second JSON fragment despite JSON mode.
        # Accept only the first complete object; validation below still rejects unsafe intent.
        parsed: object | None = None
        for offset, character in enumerate(content):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(content[offset:])
                if isinstance(candidate, dict):
                    parsed = candidate
                    break
            except json.JSONDecodeError:
                continue
        if not isinstance(parsed, dict):
            return None, None
        if parsed.get("clarification"):
            return None, str(parsed["clarification"])[:400]
        aggregation = str(parsed.get("aggregation", "sum"))
        chart_type = str(parsed.get("chart_type", "bar"))
        if aggregation not in {"sum", "avg", "count"} or chart_type not in {"bar", "line"}:
            return None, None
        chart = ChartRequest(dimension=str(parsed["dimension"]), metric=str(parsed["metric"]), aggregation=cast(Literal["sum", "avg", "count"], aggregation), chart_type=cast(Literal["bar", "line"], chart_type), limit=min(30, max(1, int(parsed.get("limit", 12)))), filters=[])
        known = {item.name: item for item in columns}
        if chart.dimension not in known or chart.metric not in known or known[chart.dimension].kind not in {"time", "cat"} or known[chart.metric].kind != "num":
            return None, None
        if any(token in chart.metric.lower() for token in {"_id", "code", "key"}):
            return None, None
        if chart.chart_type == "line" and known[chart.dimension].kind != "time":
            chart.chart_type = "bar"
        return chart, None
    except (KeyError, ValueError, TypeError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None, None


def _selection_artifact(run_id: str) -> dict[str, object]:
    """Return schema-only user selections for this run; no selections are global."""
    path = RUN_STORE._dir(run_id) / "semantic-selection.json"
    if not path.exists():
        return {"selections": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data.get("selections"), list) else {"selections": []}
    except (OSError, json.JSONDecodeError):
        return {"selections": []}


def _named_columns(columns: list[ColumnProfile], message: str) -> set[str]:
    """Find explicit schema names, treating underscore/hyphen/space as equivalent."""
    normalized = re.sub(r"[^a-z0-9]+", " ", message.casefold()).strip()
    return {
        item.name for item in columns
        if re.search(rf"(?<![a-z0-9]){re.escape(re.sub(r'[^a-z0-9]+', ' ', item.name.casefold()).strip())}(?![a-z0-9])", normalized)
    }


def _semantic_clarification(columns: list[ColumnProfile], message: str, selections: list[dict[str, object]], language: Literal["en", "vi"] = "en") -> list[ClarificationOption]:
    """Ask only for roles not explicitly named in the schema or confirmed by this run's user."""
    normalized = message.lower()
    requested_measure = any(word in normalized for word in {"doanh thu", "revenue", "sales", "lợi nhuận", "profit", "margin", "chi phí", "cost", "số lượng", "quantity"})
    requested_dimension = any(word in normalized for word in {"theo", "by", "trend", "xu hướng", "tháng", "month", "ngày", "day"})
    named = _named_columns(columns, message)
    selected = {str(item.get("column")): str(item.get("role")) for item in selections}
    metric_named = any(item.kind == "num" and (item.name in named or selected.get(item.name) == "metric") for item in columns)
    dimension_named = any(item.kind in {"time", "cat"} and (item.name in named or selected.get(item.name) == "dimension") for item in columns)
    metrics = [item for item in columns if item.kind == "num" and not any(token in item.name.lower() for token in {"_id", "code", "key"})]
    dimensions = [item for item in columns if item.kind in {"time", "cat"}]
    if not requested_measure and not metric_named and len(metrics) > 1:
        return [ClarificationOption(column=item.name, label=item.name, reason="Ứng viên chỉ tiêu số — hãy xác nhận ý nghĩa nghiệp vụ." if language == "vi" else "Numeric measure candidate — please confirm its business meaning.", role="metric") for item in metrics[:4]]
    if requested_measure and not requested_dimension and not dimension_named and len(dimensions) > 1:
        return [ClarificationOption(column=item.name, label=item.name, reason="Trường thời gian hoặc phân tách có thể phù hợp — hãy xác nhận." if language == "vi" else "Possible time or breakdown dimension — please confirm.", role="dimension") for item in dimensions[:4]]
    return []


def _chat_metric(columns: list[ColumnProfile], message: str, selections: list[dict[str, object]]) -> ColumnProfile | None:
    normalized = message.lower()
    metrics = [item for item in columns if item.kind == "num" and not any(token in item.name.lower() for token in {"_id", "code", "key"})]
    selected = {str(item.get("column")) for item in selections if item.get("role") == "metric"}
    named = _named_columns(columns, message)
    direct = next((item for item in metrics if item.name in named or item.name in selected), None)
    if direct:
        return direct
    priorities = (("doanh thu", "revenue", "sales"), ("lợi nhuận", "profit", "margin"), ("số lượng", "quantity", "volume"), ("chi phí", "cost"))
    for words in priorities:
        if any(word in normalized for word in words):
            found = next((item for item in metrics if any(word in item.name.lower().replace("_", " ") for word in words)), None)
            if found:
                return found
    return metrics[0] if metrics else None


def _chat_dimension(columns: list[ColumnProfile], message: str, selections: list[dict[str, object]]) -> ColumnProfile | None:
    normalized = message.lower()
    fields = [item for item in columns if item.kind in {"time", "cat"}]
    selected = {str(item.get("column")) for item in selections if item.get("role") == "dimension"}
    named = _named_columns(columns, message)
    direct = next((item for item in fields if item.name in named or item.name in selected), None)
    if direct:
        return direct
    if any(word in normalized for word in {"tháng", "month", "ngày", "day", "trend", "xu hướng", "6 tháng", "năm"}):
        timed = next((item for item in fields if item.kind == "time"), None)
        if timed:
            return timed
    for item in fields:
        words = item.name.lower().replace("_", " ").split()
        if any(word in normalized for word in words if len(word) > 2):
            return item
    return next((item for item in fields if item.kind == "time"), fields[0] if fields else None)


def _output_intent(message: str) -> Literal["table", "chart"]:
    normalized = message.casefold()
    table_words = ("table", "tabular", "rows", "bảng", "dang bang", "dạng bảng")
    return "table" if any(word in normalized for word in table_words) else "chart"


def _starter_analysis_response(columns: list[ColumnProfile], message: str, language: Literal["en", "vi"] = "en") -> ChatResponse:
    """Return selectable, profile-only views without running a chart or calling an LLM."""
    proposals = analyst_proposals(columns, max_charts=5, language=language)
    english = language == "en"
    if english:
        answer = "Here are safe starter analysis views based on this dataset profile. Select a card to run its validated aggregate."
        insight = f"Prepared {len(proposals)} deterministic view{'s' if len(proposals) != 1 else ''}; no raw rows or chart query were sent to an LLM."
        scope = "Profile metadata only; no aggregate has run"
        caveat = "Cards exclude identifier and sensitive fields and require explicit approval before a chart runs."
    else:
        answer = "Đây là các góc nhìn phân tích khởi đầu an toàn từ profile dataset. Hãy chọn một thẻ để chạy aggregate đã được xác thực."
        insight = f"Đã chuẩn bị {len(proposals)} góc nhìn xác định; không gửi raw rows hoặc chart query tới LLM."
        scope = "Chỉ dùng metadata của profile; chưa chạy aggregate"
        caveat = "Các thẻ loại trừ trường định danh và nhạy cảm; chỉ chạy chart sau khi anh/chị phê duyệt."
    return ChatResponse(answer=answer, insight=insight, scope=scope, proposals=proposals, caveats=[caveat], mode="analysis", planner="deterministic")


def chart_insight(rows: list[dict[str, str | float | int]], chronological: bool, language: Literal["en", "vi"] = "en") -> tuple[str, list[str]]:
    if not rows:
        return ("Không có dữ liệu trong phạm vi đã chọn.", ["Không có aggregate nào phù hợp với filter và cột đã chọn."]) if language == "vi" else ("No data is available in the selected scope.", ["No aggregate matched the selected filters and columns."])
    values = [float(row["value"]) for row in rows]
    if chronological and len(rows) >= 2:
        first, last = values[0], values[-1]; delta = last - first; change = 0 if first == 0 else delta / abs(first) * 100; peak_index, trough_index = values.index(max(values)), values.index(min(values))
        if language == "vi":
            direction = "tăng" if delta >= 0 else "giảm"
            return (f"Giá trị cuối kỳ {direction} {percent(abs(change))} so với đầu kỳ.", [f"Từ {rows[0]['display_label']}: {compact_number(first)} đến {rows[-1]['display_label']}: {compact_number(last)} ({direction} {compact_number(abs(delta))}).", f"Đỉnh: {rows[peak_index]['display_label']} với {compact_number(values[peak_index])}; thấp nhất: {rows[trough_index]['display_label']} với {compact_number(values[trough_index])}."])
        direction = "increased" if delta >= 0 else "decreased"
        return (f"The final period {direction} by {percent(abs(change))} from the first period.", [f"From {rows[0]['display_label']}: {compact_number(first)} to {rows[-1]['display_label']}: {compact_number(last)} ({direction} by {compact_number(abs(delta))}).", f"Peak: {rows[peak_index]['display_label']} at {compact_number(values[peak_index])}; low: {rows[trough_index]['display_label']} at {compact_number(values[trough_index])}."])
    total = sum(values); top = rows[0]; share = 0 if total == 0 else float(top["value"]) / total * 100; second = values[1] if len(values) > 1 else None
    if language == "vi":
        bullets = [f"Dẫn đầu: {top['display_label']} với {compact_number(float(top['value']))}, chiếm {percent(share)} trong phần kết quả hiển thị."]
        if second is not None: bullets.append(f"Chênh lệch với hạng hai: {compact_number(float(top['value']) - second)}.")
        return f"{top['display_label']} đang dẫn đầu với {compact_number(float(top['value']))}.", bullets
    bullets = [f"Leader: {top['display_label']} at {compact_number(float(top['value']))}, representing {percent(share)} of the displayed total."]
    if second is not None: bullets.append(f"Gap to the runner-up: {compact_number(float(top['value']) - second)}.")
    return f"{top['display_label']} leads at {compact_number(float(top['value']))}.", bullets


@app.post("/api/runs/{run_id}/semantic-selection", response_model=ChatResponse)
def select_semantic_column(run_id: str, request: SemanticSelectionRequest) -> ChatResponse:
    """Persist a user choice inside one run, then resume only that run's pending question."""
    headers, rows = load_run(run_id)
    profile_data = profile_for_run(run_id, headers, rows)
    column = next((item for item in profile_data.columns if item.name == request.column), None)
    if column is None or is_sensitive_column(request.column):
        raise HTTPException(422, "Selected column is not available for semantic analysis.")
    if request.role == "metric" and column.kind != "num":
        raise HTTPException(422, "Selected metric must be a numeric schema column.")
    if request.role == "dimension" and column.kind not in {"time", "cat"}:
        raise HTTPException(422, "Selected dimension must be a time or categorical schema column.")
    state = _selection_artifact(run_id)
    selections = [item for item in cast(list[dict[str, object]], state["selections"]) if item.get("role") != request.role]
    selections.append({"column": column.name, "role": request.role, "provenance": "User"})
    pending_message = state.get("pending_message")
    RUN_STORE.save_artifact_json(run_id, "semantic-selection.json", {"selections": selections})
    if not isinstance(pending_message, str) or not pending_message:
        raise HTTPException(409, "No pending question is available to resume.")
    return chat_about_run(run_id, ChatRequest(message=pending_message, language=cast(Literal["en", "vi"], request.language)), allow_llm=False)


@app.post("/api/runs/{run_id}/chat", response_model=ChatResponse)
def chat_about_run(run_id: str, request: ChatRequest, *, allow_llm: bool = True) -> ChatResponse:
    """Constrained data conversation: natural language maps only to a validated aggregate."""
    headers, rows = load_run(run_id)
    profile_data = profile_for_run(run_id, headers, rows)
    if is_starter_analysis_request(request.message):
        return _starter_analysis_response(profile_data.columns, request.message, request.language)
    state = _selection_artifact(run_id)
    selections = cast(list[dict[str, object]], state["selections"])
    clarification_options = _semantic_clarification(profile_data.columns, request.message, selections, request.language)
    if clarification_options:
        RUN_STORE.save_artifact_json(run_id, "semantic-selection.json", {"selections": selections, "pending_message": request.message})
        if request.language == "vi":
            return ChatResponse(answer="Có hơn một cột phù hợp nhưng chưa đủ chắc về ý nghĩa nghiệp vụ hoặc phạm vi. Hãy xác nhận cột muốn dùng.", insight="Chưa chạy aggregate để tránh tự suy diễn chỉ tiêu hoặc phạm vi.", scope="Chờ xác nhận semantic", caveats=["Lựa chọn chỉ áp dụng cho dataset/run hiện tại và được gắn provenance User."], clarification_options=clarification_options, mode="clarification")
        return ChatResponse(answer="More than one column could fit, but its business meaning or scope is not yet certain. Please confirm the column to use.", insight="No aggregate has run, to avoid inferring a metric or scope.", scope="Awaiting semantic confirmation", caveats=["Your selection applies only to this dataset/run and is recorded with User provenance."], clarification_options=clarification_options, mode="clarification")
    llm_request, clarification = _llm_chart_request(profile_data.columns, request) if allow_llm else (None, None)
    if clarification:
        return ChatResponse(answer=clarification, insight="AI cần xác nhận phạm vi trước khi chạy aggregate." if request.language == "vi" else "AI needs scope confirmation before running an aggregate.", scope="Chưa chạy phân tích" if request.language == "vi" else "No analysis has run", caveats=[], mode="clarification", planner="llm")
    planner = "llm" if llm_request else "deterministic"
    if llm_request:
        chart_request = llm_request
    else:
        metric = _chat_metric(profile_data.columns, request.message, selections)
        dimension = _chat_dimension(profile_data.columns, request.message, selections)
        if metric is None or dimension is None:
            return ChatResponse(answer="Cần một metric số và một trường thời gian hoặc dimension để phân tích. Có thể hỏi ‘Doanh thu theo tháng’ hoặc ‘Doanh thu theo kênh’." if request.language == "vi" else "I need a numeric metric and a time or categorical dimension to analyze. Try a question such as ‘Revenue by month’ or ‘Revenue by channel’.", insight="Chưa tìm được cặp metric/dimension an toàn trong dataset này." if request.language == "vi" else "No safe metric/dimension pair was found in this dataset.", scope="Chưa chạy phân tích" if request.language == "vi" else "No analysis has run", caveats=[], mode="clarification")
        chart_request = ChartRequest(dimension=dimension.name, metric=metric.name, aggregation="sum", chart_type="line" if dimension.kind == "time" else "bar", limit=12)
    output_intent = _output_intent(request.message)
    chart = build_chart(run_id, chart_request, request.language)
    metric = next(item for item in profile_data.columns if item.name == chart_request.metric)
    dimension = next(item for item in profile_data.columns if item.name == chart_request.dimension)
    scope = (f"{chart.aggregation.upper()} {metric.name} theo {dimension.name}; {chart.result_count} kết quả, xếp {chart.sort_mode}" if request.language == "vi" else f"{chart.aggregation.upper()} {metric.name} by {dimension.name}; {chart.result_count} results, sorted {chart.sort_mode}")
    insight = chart.insight_headline
    caveats = list(chart.warnings)
    if any(word in request.message.lower() for word in {"cùng kỳ", "year over year", "yoy", "năm ngoái"}):
        caveats.append("So sánh cùng kỳ cần một trường thời gian được chuẩn hoá theo tháng/năm; bản chat hiện trả xu hướng tổng hợp trước để bạn review phạm vi." if request.language == "vi" else "A year-over-year comparison needs a time field normalized by month/year; this response returns an aggregate trend for you to review the scope first.")
    answer = f"Đã chuẩn bị bảng {metric.name} theo {dimension.name}." if output_intent == "table" and request.language == "vi" else f"I prepared a table of {metric.name} by {dimension.name}." if output_intent == "table" else f"Đã phân tích {metric.name} theo {dimension.name}." if request.language == "vi" else f"I analyzed {metric.name} by {dimension.name}."
    return ChatResponse(answer=answer, insight=insight, scope=scope, title=chart.title, chart=None if output_intent == "table" else chart, table=chart.rows, caveats=caveats, mode="analysis", planner=cast(Literal["llm", "deterministic"], planner))


@app.post("/api/runs/{run_id}/chat/stream")
def stream_chat_about_run(run_id: str, request: ChatRequest) -> StreamingResponse:
    """Stream safe, user-meaningful progress states—not private model reasoning."""
    labels = {
        "en": {"received": "Question received", "planning": "Understanding the question against the dataset schema", "validating": "Checking safe columns and scope", "fallback": "Using the safe analysis planner for a fast response", "clarification": "A confirmation is needed before analysis", "aggregating": "Aggregating data on the server", "insights": "Forming insight from verified aggregates", "completed": "Analysis complete"},
        "vi": {"received": "Đã nhận câu hỏi", "planning": "Đang hiểu câu hỏi theo schema dataset", "validating": "Đang kiểm tra cột và phạm vi an toàn", "fallback": "Đang dùng bộ phân tích an toàn để phản hồi nhanh", "clarification": "Cần xác nhận thêm trước khi chạy phân tích", "aggregating": "Đã tổng hợp dữ liệu trên server", "insights": "Đang tạo insight từ aggregate đã xác thực", "completed": "Hoàn tất phân tích"},
    }[request.language]
    def event(name: str, payload: dict[str, object]) -> str:
        return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def generate():
        yield event("received", {"label": labels["received"]})
        yield event("planning", {"label": labels["planning"]})
        yield event("validating", {"label": labels["validating"]})
        try:
            # The synchronous LLM client cannot yield while waiting. Stream stays responsive
            # by using the deterministic, schema-validated planner for this transport.
            yield event("fallback_planning", {"label": labels["fallback"]})
            response = chat_about_run(run_id, request, allow_llm=False)
            if response.mode == "clarification":
                yield event("clarification", {"label": labels["clarification"], "response": response.model_dump()})
            else:
                yield event("aggregating", {"label": labels["aggregating"]})
                yield event("insights", {"label": labels["insights"]})
                yield event("completed", {"label": labels["completed"], "response": response.model_dump()})
        except HTTPException as error:
            yield event("error", {"label": str(error.detail) if error.status_code < 500 else "Không thể hoàn tất phân tích lúc này."})
        except Exception:
            yield event("error", {"label": "Không thể hoàn tất phân tích lúc này."})
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
