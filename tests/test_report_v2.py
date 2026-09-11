from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from main import app  # noqa: E402
from report_models import ReportDocumentV2  # noqa: E402
from report_service import add_artifact, apply_template_cas, empty_document, get_document  # noqa: E402
from run_store import RunStore  # noqa: E402


def _store(tmp_path: Path) -> RunStore:
    store = RunStore(tmp_path)
    store.save_dataset("a" * 32, ["dimension", "metric"], [{"dimension": "North", "metric": "10"}], file_name="fixture.csv")
    return store


def test_v2_document_has_strict_schema_and_twelve_column_placements(tmp_path: Path) -> None:
    document = empty_document("a" * 32)
    assert document.schema_version == 2
    assert document.page_settings.columns == 12
    assert document.pages[0].page_id == "page-1"
    assert all(0 <= placement.x < 12 for placement in document.placements)


def test_artifact_library_is_owner_scoped_and_cas(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = "a" * 32
    first = get_document(store, run_id)
    chart = {"dimension": "dimension", "metric": "metric", "chart_type": "bar", "aggregation": "sum"}
    result = {"title": "Revenue", "rows": []}
    saved = add_artifact(store, run_id, first.revision, "chart-1", chart, result, origin="executive_hub")
    assert saved.revision == 1
    assert saved.artifact_library[0].origin == "executive_hub"
    with pytest.raises(HTTPException, match="changed elsewhere"):
        add_artifact(store, run_id, first.revision, "chart-2", chart, result, origin="data_copilot")
    current = get_document(store, run_id)
    same = add_artifact(store, run_id, current.revision, "chart-1", chart, result, origin="data_copilot")
    assert same.revision == current.revision


def test_templates_change_real_hierarchy_and_placements(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = "a" * 32
    compact = apply_template_cas(store, run_id, 0, "executive_briefing")
    analytical = apply_template_cas(store, run_id, 1, "sales_performance_review")
    assert [page.title for page in compact.pages] != [page.title for page in analytical.pages]
    assert [(item.block_id, item.x, item.y, item.w, item.h) for item in compact.placements] != [
        (item.block_id, item.x, item.y, item.w, item.h) for item in analytical.placements
    ]


def test_v2_routes_migrate_legacy_and_reject_stale_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import main

    monkeypatch.setattr(main, "RUN_STORE", _store(tmp_path))
    client = TestClient(app)
    run_id = "a" * 32
    current = client.get(f"/api/runs/{run_id}/custom-report/v2")
    assert current.status_code == 200
    payload = current.json()
    assert payload["schema_version"] == 2
    stale = client.put(f"/api/runs/{run_id}/custom-report/v2", json={"expected_revision": 9, "document": payload})
    assert stale.status_code == 409
