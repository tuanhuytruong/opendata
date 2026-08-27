"""Local, read-only profile API for the OpenData report workspace.

This first vertical slice intentionally accepts CSV only. XLSX is rejected explicitly
until the ingestion worker and its workbook safety checks land.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_PROFILE_ROWS = 200_000
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "var" / "uploads"

app = FastAPI(title="OpenData Report API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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


def is_number(value: str) -> bool:
    try:
        float(value.replace(",", ""))
        return True
    except ValueError:
        return False


def is_date(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            pass
    return False


def column_description(name: str, kind: str) -> str:
    normalized = name.lower().replace("_", " ")
    hints = {
        "sale date": "Date on which the sales transaction was recorded.",
        "net sales": "Sales revenue after discounts and deductions.",
        "quantity": "Quantity recorded for the transaction.",
        "gross margin": "Difference between sales revenue and cost of goods sold.",
    }
    return hints.get(normalized, f"Inferred {kind} field from column name and observed values.")


def infer_kind(name: str, values: list[str], row_count: int) -> str:
    observed = [value.strip() for value in values if value.strip()]
    if not observed:
        return "unknown"
    lower_name = name.lower()
    numeric_ratio = sum(is_number(value) for value in observed) / len(observed)
    date_ratio = sum(is_date(value) for value in observed) / len(observed)
    distinct = len(set(observed))
    if date_ratio >= 0.9 or any(token in lower_name for token in ("date", "day", "month", "year", "period")) and date_ratio >= 0.5:
        return "time"
    if numeric_ratio >= 0.95:
        return "num"
    if ("id" in lower_name or "code" in lower_name) and distinct / max(1, len(observed)) >= 0.9:
        return "id"
    return "cat"


def profile_csv(file_name: str, raw: bytes) -> DatasetProfile:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or len(reader.fieldnames) < 2:
        raise HTTPException(422, "CSV must have a header and at least two columns.")
    headers = [header.strip() for header in reader.fieldnames]
    if len(headers) != len(set(headers)) or any(not header for header in headers):
        raise HTTPException(422, "CSV headers must be present and unique.")
    rows = []
    values_by_column: dict[str, list[str]] = {header: [] for header in headers}
    for index, row in enumerate(reader, start=1):
        if index > MAX_PROFILE_ROWS:
            raise HTTPException(422, f"CSV exceeds the first-release limit of {MAX_PROFILE_ROWS:,} rows.")
        clean = {header: (row.get(header) or "").strip() for header in headers}
        rows.append(clean)
        for header, value in clean.items():
            values_by_column[header].append(value)
    if not rows:
        raise HTTPException(422, "CSV does not contain any data rows.")
    profiles: list[ColumnProfile] = []
    warnings: list[str] = []
    for header in headers:
        values = values_by_column[header]
        null_count = sum(not value for value in values)
        kind = infer_kind(header, values, len(rows))
        distinct = len(set(value for value in values if value))
        profiles.append(ColumnProfile(
            name=header,
            kind=cast(Literal["time", "num", "cat", "id", "unknown"], kind),
            null_count=null_count,
            null_ratio=round(null_count / len(rows), 4),
            distinct_count=distinct,
            description=column_description(header, kind),
        ))
        if null_count / len(rows) >= 0.95:
            warnings.append(f"{header} is {null_count / len(rows):.1%} empty and may not be useful for charts.")
    units = next((profile for profile in profiles if profile.name.lower() in {"unit_of_measure", "uom"}), None)
    quantity = next((profile for profile in profiles if profile.name.lower() == "quantity"), None)
    if units and quantity and units.distinct_count > 1:
        warnings.append("Quantity has multiple units of measure; do not sum it until a compatible unit filter is applied.")
    run_id = uuid4().hex
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / f"{run_id}.csv").write_bytes(raw)
    return DatasetProfile(
        run_id=run_id,
        file_name=file_name,
        row_count=len(rows),
        column_count=len(headers),
        usable_column_count=sum(profile.kind != "unknown" for profile in profiles),
        columns=profiles,
        warnings=warnings,
        preview=rows[:20],
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/runs/upload", response_model=DatasetProfile, status_code=201)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetProfile:
    name = Path(file.filename or "upload").name
    if not re.fullmatch(r"[\w .()\-]+\.csv", name, flags=re.IGNORECASE):
        raise HTTPException(415, "First release accepts a .csv file with a safe file name. XLSX support is next.")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds the 50 MB first-release upload limit.")
    return profile_csv(name, raw)
