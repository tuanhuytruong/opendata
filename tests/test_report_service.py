from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from report_models import ReportDocumentV2, build_v2_from_legacy  # noqa: E402
from report_templates import TEMPLATE_DEFINITIONS, template_signature  # noqa: E402


def test_legacy_migration_is_deterministic_and_idempotent() -> None:
    legacy = {
        "run_id": "a" * 32,
        "title": "Monthly review",
        "locale": "en",
        "executive_summary": "Validated summary",
        "pinned_artifacts": [{"artifact_id": "chart-1", "chart": {"dimension": "region", "metric": "sales"}, "result": {"title": "Sales"}}],
        "sections": [{"section_id": "s1", "heading": "Actions", "commentary": "Review mix"}],
        "revision": 4,
    }
    first = build_v2_from_legacy(legacy)
    second = build_v2_from_legacy({**legacy, **first})
    assert first == second
    document = ReportDocumentV2.model_validate(first)
    assert document.schema_version == 2
    assert document.artifact_library[0].artifact_id == "chart-1"
    assert any(block.type == "chart" for block in document.blocks)


def test_v2_rejects_unknown_fields_and_invalid_references() -> None:
    with pytest.raises(ValidationError):
        ReportDocumentV2.model_validate({"run_id": "a" * 32, "unknown": True})
    with pytest.raises(ValidationError):
        ReportDocumentV2.model_validate({
            "run_id": "a" * 32,
            "blocks": [{"type": "chart", "block_id": "chart-1", "artifact_id": "missing"}],
            "placements": [{"block_id": "chart-1", "page_id": "page-1", "x": 0, "y": 0, "w": 12, "h": 4}],
        })


def test_template_signatures_are_structurally_distinct() -> None:
    signatures = [template_signature(template_id) for template_id in TEMPLATE_DEFINITIONS]
    assert len(signatures) == 4
    assert len(set(signatures)) == 4
    assert all(len(definition["pages"]) >= 2 for definition in TEMPLATE_DEFINITIONS.values())
    assert all(len(definition["placements"]) >= 6 for definition in TEMPLATE_DEFINITIONS.values())


def test_placement_cannot_escape_twelve_columns() -> None:
    with pytest.raises(ValidationError):
        ReportDocumentV2.model_validate({
            "run_id": "a" * 32,
            "placements": [{"block_id": "header", "page_id": "page-1", "x": 8, "y": 0, "w": 5, "h": 3}],
            "blocks": [{"type": "header", "block_id": "header", "text": "Title"}],
        })
