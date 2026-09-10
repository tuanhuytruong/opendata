from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from database_adapters import ReadResult, oracle_rows, postgres_rows  # noqa: E402
from main import app  # noqa: E402
from source_registry import RegisteredSource, parse_registry  # noqa: E402
from fastapi.testclient import TestClient

client = TestClient(app)


def source(engine: str, max_rows: int = 100) -> RegisteredSource:
    return RegisteredSource("sales-db", engine, "REPORTING", "SALES", "SALES_DB_URL", "Sales source", max_rows, 15000)


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


@pytest.mark.parametrize(("truncated", "status_code"), [(False, 201), (True, 422)])
def test_registered_source_uses_explicit_truncation_signal(monkeypatch, truncated, status_code) -> None:
    monkeypatch.setenv("OPENDATA_SOURCES_JSON", '[{"id":"sales-db","engine":"postgres","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL","display_name":"Sales","max_rows":2}]')
    result = ReadResult(
        headers=["CHANNEL", "NET_SALES"],
        rows=[{"CHANNEL": "Online", "NET_SALES": "100"}, {"CHANNEL": "Retail", "NET_SALES": "200"}],
        truncated=truncated,
    )
    monkeypatch.setattr("main.read_registered_source", lambda source: result)
    response = client.post("/api/sources/sales-db/runs")
    assert response.status_code == status_code, response.text
    if truncated:
        assert "exceeds" in response.json()["detail"]
    else:
        assert response.json()["row_count"] == 2


def test_registry_rejects_unsafe_and_duplicate_sources() -> None:
    sources = parse_registry('[{"id":"sales-db","engine":"postgres","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL"}]')
    assert sources["sales-db"].locator == "REPORTING.SALES"
    with pytest.raises(ValueError, match="unique"):
        parse_registry('[{"id":"sales-db","engine":"postgres","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL"},{"id":"sales-db","engine":"oracle","schema":"REPORTING","table":"SALES","connection_env":"SALES_DB_URL"}]')
    with pytest.raises(ValueError, match="identifier"):
        parse_registry('[{"id":"sales-db","engine":"postgres","schema":"public;DROP","table":"SALES","connection_env":"SALES_DB_URL"}]')


class FakeCursor:
    description = [type("Column", (), {"name": "CHANNEL"})(), type("Column", (), {"name": "NET_SALES"})()]

    def __init__(self, records=None):
        self.calls = []
        self.records = records or [("Online", 100)]

    def __enter__(self): return self
    def __exit__(self, *args): return None
    def execute(self, query, params=None): self.calls.append((query, params))
    def fetchall(self): return self.records
    def close(self): return None


class FakeConnection:
    def __init__(self, records=None):
        self.cursor_instance = FakeCursor(records)
        self.rolled_back = False
        self.closed = False
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
    assert calls[1] == ("SET LOCAL statement_timeout = 15000", None)
    assert calls[2][0] == 'SELECT * FROM "REPORTING"."SALES" LIMIT %s'
    assert calls[2][1] == (101,)
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("adapter", "engine", "query_index", "expected_params"),
    [
        (postgres_rows, "postgres", 2, (3,)),
        (oracle_rows, "oracle", 1, {"limit": 3}),
    ],
)
def test_adapter_read_result_distinguishes_exact_limit_from_truncation(
    monkeypatch, adapter, engine, query_index, expected_params
) -> None:
    monkeypatch.setenv("SALES_DB_URL", f"{engine}://secret")
    exact_connection = FakeConnection([("one", 1), ("two", 2)])
    if engine == "oracle":
        exact_connection.cursor_instance.description = [("CHANNEL",), ("NET_SALES",)]
    exact = adapter(source(engine, max_rows=2), lambda *args, **kwargs: exact_connection)

    assert isinstance(exact, ReadResult)
    assert exact.truncated is False
    assert len(exact.rows) == 2
    assert tuple(exact) == (exact.headers, exact.rows)
    assert exact_connection.cursor_instance.calls[query_index][1] == expected_params

    over_connection = FakeConnection([("one", 1), ("two", 2), ("three", 3)])
    if engine == "oracle":
        over_connection.cursor_instance.description = [("CHANNEL",), ("NET_SALES",)]
    over = adapter(source(engine, max_rows=2), lambda *args, **kwargs: over_connection)

    assert over.truncated is True
    assert over.rows == [
        {"CHANNEL": "one", "NET_SALES": "1"},
        {"CHANNEL": "two", "NET_SALES": "2"},
    ]


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
    assert calls[1][1] == {"limit": 101}


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


def test_adapter_hides_connection_error(monkeypatch) -> None:
    monkeypatch.setenv("SALES_DB_URL", "postgresql://secret")
    def broken_connect(*args, **kwargs):
        raise RuntimeError("private database host")
    with pytest.raises(HTTPException) as error:
        postgres_rows(source("postgres"), broken_connect)
    assert error.value.status_code == 502
    assert "private database host" not in error.value.detail
