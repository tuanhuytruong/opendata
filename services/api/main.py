"""Read-only dataset profiling and chart API for OpenData report runs."""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import duckdb
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook
from pydantic import BaseModel, Field

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_PROFILE_ROWS = 200_000
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


class ChartRequest(BaseModel):
    dimension: str
    metric: str
    aggregation: Literal["sum", "avg", "count"] = "sum"
    chart_type: Literal["bar", "line", "area", "scatter"] = "bar"
    limit: int = Field(default=12, ge=1, le=30)


class ChartResult(BaseModel):
    dimension: str
    metric: str
    aggregation: str
    chart_type: str
    title: str
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


def profile(file_name: str, headers: list[str], rows: list[dict[str, str]]) -> DatasetProfile:
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
    run_id = uuid4().hex
    persist(run_id, headers, rows)
    return DatasetProfile(run_id=run_id, file_name=file_name, row_count=len(rows), column_count=len(headers), usable_column_count=sum(item.kind != "unknown" for item in profiles), columns=profiles, warnings=warnings, preview=rows[:20])


def quote_identifier(name: str, headers: list[str]) -> str:
    if name not in headers:
        raise HTTPException(422, f"Unknown column: {name}")
    return '"' + name.replace('"', '""') + '"'


@app.get("/api/health")
def health() -> dict[str, str]: return {"status": "ok"}


@app.post("/api/runs/upload", response_model=DatasetProfile, status_code=201)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetProfile:
    name = safe_name(file.filename or "upload")
    if not re.fullmatch(r"[\w .()\-]+\.(csv|xlsx)", name, flags=re.IGNORECASE):
        raise HTTPException(415, "Upload a CSV or XLSX file with a safe file name.")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES: raise HTTPException(413, "File exceeds the 50 MB upload limit.")
    headers, rows = xlsx_rows(raw) if name.lower().endswith(".xlsx") else csv_rows(raw)
    return profile(name, headers, rows)


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
    if request.aggregation == "count": expression = "COUNT(*)"
    else: expression = f"{request.aggregation.upper()}(TRY_CAST(REPLACE({metric}, ',', '') AS DOUBLE))"
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("CREATE TABLE dataset AS SELECT * FROM read_csv_auto(?, all_varchar=true)", [str(DATA_DIR / f"{run_id}.csv")])
        query = f"SELECT {dimension} AS label, {expression} AS value FROM dataset WHERE {dimension} IS NOT NULL AND TRIM({dimension}) <> '' GROUP BY 1 ORDER BY value DESC NULLS LAST LIMIT ?"
        records = connection.execute(query, [request.limit]).fetchall()
    finally:
        connection.close()
    warnings: list[str] = []
    if not records: warnings.append("This chart has no matching values.")
    if request.metric.lower() == "quantity" and request.aggregation == "sum": warnings.append("Verify a compatible unit filter before interpreting summed quantity.")
    return ChartResult(dimension=request.dimension, metric=request.metric, aggregation=request.aggregation, chart_type=request.chart_type, title=f"{request.aggregation.upper()} {request.metric} by {request.dimension}", rows=[{"label": str(label), "value": 0 if value is None else float(value)} for label, value in records], warnings=warnings)
