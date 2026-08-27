"""Operator-managed allow-list for database sources.

Configuration comes only from an ignored environment variable. There is deliberately
no API for submitting connection strings, schemas or SQL.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from fastapi import HTTPException

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")
_SOURCE_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


@dataclass(frozen=True)
class RegisteredSource:
    source_id: str
    engine: str
    schema: str
    table: str
    connection_env: str
    display_name: str
    max_rows: int = 100_000
    statement_timeout_ms: int = 30_000

    @property
    def locator(self) -> str:
        return f"{self.schema}.{self.table}"


def _identifier(value: object, label: str) -> str:
    text = str(value or "")
    if not _IDENTIFIER.fullmatch(text):
        raise ValueError(f"{label} must be a simple database identifier.")
    return text


def _positive(value: object, label: str, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer.") from error
    if not 1 <= number <= maximum:
        raise ValueError(f"{label} must be between 1 and {maximum:,}.")
    return number


def parse_registry(raw: str) -> dict[str, RegisteredSource]:
    if not raw.strip():
        return {}
    try:
        records = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("OPENDATA_SOURCES_JSON must contain valid JSON.") from error
    if not isinstance(records, list):
        raise ValueError("OPENDATA_SOURCES_JSON must be a JSON array.")
    sources: dict[str, RegisteredSource] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each registered source must be an object.")
        source_id = str(record.get("id", ""))
        if not _SOURCE_ID.fullmatch(source_id) or source_id in sources:
            raise ValueError("Each source needs a unique lowercase id.")
        engine = str(record.get("engine", "")).lower()
        if engine not in {"postgres", "oracle"}:
            raise ValueError("Registered engine must be postgres or oracle.")
        connection_env = str(record.get("connection_env", ""))
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", connection_env):
            raise ValueError("connection_env must name an uppercase environment variable.")
        sources[source_id] = RegisteredSource(
            source_id=source_id,
            engine=engine,
            schema=_identifier(record.get("schema"), "schema"),
            table=_identifier(record.get("table"), "table"),
            connection_env=connection_env,
            display_name=str(record.get("display_name") or source_id)[:120],
            max_rows=_positive(record.get("max_rows", 100_000), "max_rows", 600_000),
            statement_timeout_ms=_positive(record.get("statement_timeout_ms", 30_000), "statement_timeout_ms", 120_000),
        )
    return sources


def registered_sources() -> dict[str, RegisteredSource]:
    try:
        return parse_registry(os.getenv("OPENDATA_SOURCES_JSON", ""))
    except ValueError as error:
        raise HTTPException(503, f"Registered source configuration is invalid: {error}") from error


def source_connection_secret(source: RegisteredSource) -> str:
    secret = os.getenv(source.connection_env, "").strip()
    if not secret:
        raise HTTPException(503, f"Registered source {source.source_id} is unavailable.")
    return secret


def public_source(source: RegisteredSource) -> dict[str, object]:
    return {"id": source.source_id, "engine": source.engine, "display_name": source.display_name, "schema": source.schema, "table": source.table, "max_rows": source.max_rows}
