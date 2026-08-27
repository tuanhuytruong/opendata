"""Read-only PostgreSQL and Oracle source adapters.

They accept only a RegisteredSource (operator configured) and construct a fixed,
bounded query. End users and Telegram never provide SQL or connection material.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException

from source_registry import RegisteredSource, source_connection_secret


def quoted(source: RegisteredSource) -> str:
    """Registry validation permits only simple identifiers, never request data."""
    return f'"{source.schema}"."{source.table}"'


def _safe_rollback(connection: Any | None) -> None:
    if connection is None:
        return
    try:
        connection.rollback()
    except Exception:
        # The original driver error is intentionally hidden from clients.
        return


def postgres_rows(source: RegisteredSource, connect: Callable[..., Any] | None = None) -> tuple[list[str], list[dict[str, str]]]:
    if connect is None:
        try:
            import psycopg
        except ImportError as error:
            raise HTTPException(503, "PostgreSQL adapter is not installed.") from error
        connect = psycopg.connect
    connection = None
    try:
        connection = connect(source_connection_secret(source), connect_timeout=10)
        with connection.cursor() as cursor:
            cursor.execute("BEGIN READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = %s", (source.statement_timeout_ms,))
            cursor.execute(f"SELECT * FROM {quoted(source)} LIMIT %s", (source.max_rows,))
            headers = [str(column.name) for column in cursor.description]
            rows = [{header: "" if value is None else str(value) for header, value in zip(headers, record, strict=True)} for record in cursor.fetchall()]
        _safe_rollback(connection)
        return headers, rows
    except Exception as error:
        _safe_rollback(connection)
        raise HTTPException(502, f"Registered PostgreSQL source {source.source_id} could not be read.") from error
    finally:
        if connection is not None:
            connection.close()


def oracle_rows(source: RegisteredSource, connect: Callable[..., Any] | None = None) -> tuple[list[str], list[dict[str, str]]]:
    if connect is None:
        try:
            import oracledb
        except ImportError as error:
            raise HTTPException(503, "Oracle adapter is not installed.") from error
        connect = oracledb.connect
    connection = None
    try:
        connection = connect(source_connection_secret(source))
        connection.call_timeout = source.statement_timeout_ms
        cursor = connection.cursor()
        try:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(f"SELECT * FROM {quoted(source)} FETCH FIRST :limit ROWS ONLY", {"limit": source.max_rows})
            headers = [str(column[0]) for column in cursor.description]
            rows = [{header: "" if value is None else str(value) for header, value in zip(headers, record, strict=True)} for record in cursor.fetchall()]
        finally:
            cursor.close()
        _safe_rollback(connection)
        return headers, rows
    except Exception as error:
        _safe_rollback(connection)
        raise HTTPException(502, f"Registered Oracle source {source.source_id} could not be read.") from error
    finally:
        if connection is not None:
            connection.close()


def read_registered_source(source: RegisteredSource) -> tuple[list[str], list[dict[str, str]]]:
    if source.engine == "postgres":
        return postgres_rows(source)
    if source.engine == "oracle":
        return oracle_rows(source)
    raise HTTPException(422, "Unsupported registered source engine.")
