from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from report_models import ReportDocumentV2  # noqa: E402
from report_renderer import render_report_html  # noqa: E402


def test_legacy_text_is_normalized_to_structured_rich_text() -> None:
    document = ReportDocumentV2.model_validate({
        "run_id": "a" * 32,
        "blocks": [{"type": "header", "block_id": "header-1", "text": "Quarterly & review", "level": 1}],
        "placements": [{"block_id": "header-1", "page_id": "page-1", "x": 0, "y": 0, "w": 12, "h": 3}],
    })
    assert document.blocks[0].rich_text.content[0]["type"] == "heading"
    assert document.blocks[0].rich_text.content[0]["content"][0]["text"] == "Quarterly & review"


def test_rich_text_rejects_unsupported_nodes_marks_and_excessive_text() -> None:
    base = {"run_id": "b" * 32, "blocks": [{"type": "text", "block_id": "text-1", "text": "ok"}], "placements": [{"block_id": "text-1", "page_id": "page-1", "x": 0, "y": 0, "w": 12, "h": 3}]}
    with pytest.raises(ValidationError):
        ReportDocumentV2.model_validate({**base, "blocks": [{"type": "text", "block_id": "text-1", "rich_text": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "bad", "marks": [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}]}]}]}}]})
    with pytest.raises(ValidationError):
        ReportDocumentV2.model_validate({**base, "blocks": [{"type": "text", "block_id": "text-1", "rich_text": {"type": "doc", "content": [{"type": "unsupported"}]}}]})


def test_rich_text_is_escaped_and_formatting_is_reader_facing() -> None:
    document = ReportDocumentV2.model_validate({
        "run_id": "c" * 32,
        "blocks": [{"type": "text", "block_id": "text-1", "rich_text": {"type": "doc", "content": [{"type": "paragraph", "attrs": {"textAlign": "center"}, "content": [{"type": "text", "text": "Safe & sound", "marks": [{"type": "bold"}, {"type": "fontSize", "attrs": {"size": "lg"}}]}]}]}}],
        "placements": [{"block_id": "text-1", "page_id": "page-1", "x": 0, "y": 0, "w": 12, "h": 3}],
    })
    output = render_report_html(document, lambda _: "")
    assert "Safe &amp; sound" in output
    assert "font-size" in output or "report-rich-size-lg" in output
    assert "text-align:center" in output
    assert "<strong>Safe &amp; sound</strong>" in output or "<span class='report-rich-size-lg'><strong>Safe &amp; sound</strong></span>" in output

    assert "Authored report" not in output
    assert "<script" not in output.lower()
