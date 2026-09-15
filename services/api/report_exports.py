"""Exact-revision export service for canonical report v2."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from fastapi import HTTPException

from report_models import ReportDocumentV2, validate_report_v2
from report_chart_svg import render_report_chart_svg
from report_renderer import render_report_html
from report_service import get_document
from run_store import RunStore


def create_export(store: RunStore, run_id: str, revision: int, chart_svg: Callable[[dict[str, Any]], str] | None = None) -> tuple[str, dict[str, Any]]:
    document = get_document(store, run_id)
    if revision != document.revision:
        raise HTTPException(409, "Export revision is stale. Save or reload the report before exporting.")
    document = validate_report_v2(document.model_dump(mode="json"))
    export_id = str(uuid4())
    html_text = render_report_html(document, chart_svg or render_report_chart_svg)
    manifest = {
        "export_id": export_id,
        "run_id": run_id,
        "revision": document.revision,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_sha256": hashlib.sha256(json.dumps(document.model_dump(mode="json"), sort_keys=True).encode()).hexdigest(),
        "html_sha256": hashlib.sha256(html_text.encode()).hexdigest(),
        "artifact_hashes": [item.artifact_hash for item in document.artifact_library],
    }
    store.save_export(run_id, export_id, html_text, manifest)
    return export_id, manifest
