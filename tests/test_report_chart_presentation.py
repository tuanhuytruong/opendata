from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from report_chart_presentation import build_report_chart_presentation  # noqa: E402
from report_chart_svg import render_report_chart_svg  # noqa: E402


def _result(rows: list[dict[str, object]], **overrides: object) -> dict[str, object]:
    return {
        "title": "Top 12 Site Name by Quantity",
        "chart_type": "bar",
        "dimension": "site_name",
        "metric": "quantity",
        "metric_display_name": "Quantity",
        "sort_mode": "ranking",
        "requested_limit": 12,
        "result_count": len(rows),
        "rows": rows,
        **overrides,
    }


def test_ranking_presentation_preserves_all_rows_and_selects_horizontal_layout() -> None:
    rows = [{"label": f"SITE-{index}", "display_label": f"Long Site Name {index}", "value": index * 1000 + 1, "formatted_value": f"{index * 1000 + 1:,}"} for index in range(12)]
    presentation = build_report_chart_presentation(_result(rows))
    assert presentation["orientation"] == "horizontal"
    assert presentation["requestedLimit"] == 12
    assert presentation["returnedCount"] == 12
    assert len(presentation["rows"]) == 12
    assert presentation["paletteMode"] == "single-series"
    svg = render_report_chart_svg(presentation)
    assert svg.count("<rect") >= 13  # background plus one bar for every returned row
    assert all(f"Long Site Name {index}" in svg for index in range(12))
    assert "1,001" in svg


def test_presentation_uses_nice_ticks_and_preserves_existing_snapshot() -> None:
    rows = [{"label": "North", "value": 2_218_351.45, "formatted_value": "2,218,351.45"}]
    presentation = build_report_chart_presentation(_result(rows, requested_limit=1))
    assert presentation["domain"][0] == 0
    assert presentation["domain"][1] >= 2_218_351.45
    assert len(presentation["ticks"]) == 5
    assert build_report_chart_presentation({**_result(rows), "presentation": presentation}) is presentation


def test_presentation_derives_detail_and_compact_values_from_canonical_numbers() -> None:
    presentation = build_report_chart_presentation(_result([
        {"label": "<bad>", "display_label": "<bad>", "value": 12_434_891.95, "formatted_value": "unsafe raw string"},
        {"label": "negative", "value": -1_200},
    ], requested_limit=2))
    first, second = presentation["rows"]
    assert first["formattedValue"] == "12,434,891.95"
    assert first["compactFormattedValue"] == "12.4M"
    assert second["formattedValue"] == "-1,200"
    assert second["compactFormattedValue"] == "-1.2K"
    svg = render_report_chart_svg(presentation)
    assert "&lt;bad&gt;" in svg
    assert "unsafe raw string" not in svg
    assert "<bad>" not in svg
