from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from database_adapters import oracle_rows, postgres_rows  # noqa: E402
from main import app  # noqa: E402
from source_registry import RegisteredSource, parse_registry  # noqa: E402
from fastapi.testclient import TestClient

client = TestClient(app)


def source(engine: str) -> RegisteredSource:
    return RegisteredSource("sales-db", engine, "REPORTING", "SALES", "SALES_DB_URL", "Sales source", 100, 15000)


def test_sources_endpoint_exposes_no_connection_secret(monkeypatch) -> None:
    monkeypatch.setenv("OPENDATA_SOURCES_JSON", '[{"id":"sales-db","engine":"postgres","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL","display_name":"Sales"}]')
    payload = client.get("/api/sources").json()
    assert payload == {"sources": [{"id": "sales-db", "engine": "postgres", "display_name": "Sales", "schema": "REPORTING", "table": "SALES", "max_rows": 100000}]}
    assert "connection_env" not in str(payload)


def test_registered_source_stages_as_standard_run(monkeypatch) -> None:
    monkeypatch.setenv("OPENDATA_SOURCES_JSON", '[{"id":"sales-db","engine":"postgres","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL","display_name":"Sales"}]')
    monkeypatch.setattr("main.read_registered_source", lambda source: (["CHANNEL", "NET_SALES"], [{"CHANNEL": "Online", "NET_SALES": "100"}]))
    response = client.post("/api/sources/sales-db/runs")
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["file_name"] == "Sales (REPORTING.SALES)"
    assert payload["row_count"] == 1


def test_registry_rejects_unsafe_and_duplicate_sources() -> None:
    sources = parse_registry('[{"id":"sales-db","engine":"postgres","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL"}]')
    assert sources["sales-db"].locator == "REPORTING.SALES"
    with pytest.raises(ValueError, match="unique"):
        parse_registry('[{"id":"sales-db","engine":"postgres","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL"},{"id":"sales-db","engine":"oracle","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL"}]')
    with pytest.raises(ValueError, match="identifier"):
        parse_registry('[{"id":"sales-db","engine":"postgres","schema":"public;DROP","table":"SALES","connection_env":"SALES_DB_URL"}]')


class FakeCursor:
    description = [type("Column", (), {"name": "CHANNEL"})(), type("Column", (), {"name": "NET_SALES"})()]

    def __init__(self): self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def execute(self, query, params=None): self.calls.append((query, params))
    def fetchall(self): return [("Online", 100)]
    def close(self): return None


class FakeConnection:
    def __init__(self): self.cursor_instance = FakeCursor(); self.rolled_back = False; self.closed = False
    def cursor(self): return self.cursor_instance
    def rollback(self): self.rolled_back = True
    def close(self): self.closed = True


def test_postgres_adapter_enforces_read_only_timeout_and_bound(monkeypatch) -> None:
    monkeypatch.setenv("SALES_DB_URL", "postgresql://secret")
    connection = FakeConnection()
    headers, rows = postgres_rows(source("postgres"), lambda *args, **kwargs: connection)
    assert headers == ["CHANNEL", "NET_SALES"]
    assert rows == [{"CHANNEL": "Online", "NET_SALES": "100"}]
    calls = connection.cursor_instance.calls
    assert calls[0] == ("BEGIN READ ONLY", None)
    assert calls[1] == ("SET LOCAL statement_timeout = %s", (15000,))
    assert calls[2][0] == 'SELECT * FROM "REPORTING"."SALES" LIMIT %s'
    assert calls[2][1] == (100,)
    assert connection.rolled_back and connection.closed


def test_oracle_adapter_enforces_read_only_and_bound(monkeypatch) -> None:
    monkeypatch.setenv("SALES_DB_URL", "oracle://secret")
    connection = FakeConnection()
    connection.cursor_instance.description = [("CHANNEL",), ("NET_SALES",)]
    headers, rows = oracle_rows(source("oracle"), lambda *args, **kwargs: connection)
    assert headers == ["CHANNEL", "NET_SALES"]
    assert rows == [{"CHANNEL": "Online", "NET_SALES": "100"}]
    assert connection.call_timeout == 15000
    calls = connection.cursor_instance.calls
    assert calls[0] == ("SET TRANSACTION READ ONLY", None)
    assert calls[1][0] == 'SELECT * FROM "REPORTING"."SALES" FETCH FIRST :limit ROWS ONLY'
    assert calls[1][1] == {"limit": 100}


def test_adapter_hides_database_error(monkeypatch) -> None:
    monkeypatch.setenv("SALES_DB_URL", "postgresql://secret")
    class BrokenConnection:
        def cursor(self): raise RuntimeError("sensitive internal host")
        def rollback(self): return None
        def close(self): return None
    with pytest.raises(HTTPException) as error:
        postgres_rows(source("postgres"), lambda *args, **kwargs: BrokenConnection())
    assert error.value.status_code == 502
    assert "internal host" not in error.value.detail
