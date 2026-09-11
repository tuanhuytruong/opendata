from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from report_exports import create_export  # noqa: E402
from report_models import ReportDocumentV2  # noqa: E402
from report_models import HeaderBlock, ReportPlacement, ReportPage  # noqa: E402
from report_renderer import render_report_html  # noqa: E402
from run_store import RunStore  # noqa: E402


def test_export_is_exact_revision_and_keeps_immutable_manifest(tmp_path: Path) -> None:
    run_id = "b" * 32
    store = RunStore(tmp_path)
    store.save_dataset(run_id, ["dimension", "metric"], [{"dimension": "North", "metric": "10"}], file_name="fixture.csv")
    export_id, manifest = create_export(store, run_id, 0, lambda payload: "<svg role='img'><title>Validated</title></svg>")
    assert manifest["revision"] == 0
    assert hashlib.sha256(store.export_text(run_id, export_id).encode()).hexdigest() == manifest["html_sha256"]
    assert store.export_manifest(run_id, export_id)["report_sha256"] == manifest["report_sha256"]
    try:
        create_export(store, run_id, 1, lambda payload: "")
    except HTTPException as error:
        assert error.status_code == 409
    else:
        raise AssertionError("stale export must be rejected")


def test_export_escapes_authored_text(tmp_path: Path) -> None:
    document = ReportDocumentV2(
        run_id="c" * 32,
        title="Safe report",
        pages=[ReportPage(page_id="page-1", title="Page 1")],
        blocks=[HeaderBlock(type="header", block_id="header-1", text="Revenue & margin")],
        placements=[ReportPlacement(block_id="header-1", page_id="page-1", x=0, y=0, w=12, h=2)],
    )
    output = render_report_html(document, lambda payload: "")
    assert "Revenue &amp; margin" in output
    assert "<script" not in output.lower()
