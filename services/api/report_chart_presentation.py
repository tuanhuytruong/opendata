"""Canonical presentation contract shared by report editor and HTML export.

The analytical result remains the source of truth for rows.  This module only
normalizes visual semantics (orientation, density, domains, ticks and labels)
so a report cannot silently render a different chart in the browser and in an
offline export.
"""
from __future__ import annotations

import math
from typing import Any

from formatting import compact_number, format_number


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _nice_ceiling(value: float) -> float:
    value = max(1.0, abs(value))
    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude
    step = 1 if normalized <= 1 else 2 if normalized <= 2 else 2.5 if normalized <= 2.5 else 4 if normalized <= 4 else 5 if normalized <= 5 else 10
    return step * magnitude


def _domain(values: list[float]) -> list[float]:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return [0.0, 1.0]
    minimum, maximum = min(finite), max(finite)
    if minimum >= 0:
        return [0.0, _nice_ceiling(maximum * 1.08) if maximum else 1.0]
    if maximum <= 0:
        return [-_nice_ceiling(abs(minimum) * 1.08), 0.0]
    bound = max(abs(minimum), abs(maximum))
    ceiling = _nice_ceiling(bound * 1.08)
    return [-ceiling, ceiling]


def _ticks(domain: list[float], count: int = 5) -> list[dict[str, Any]]:
    minimum, maximum = domain
    if maximum <= minimum:
        return [{"value": minimum, "label": compact_number(minimum)}]
    step = (maximum - minimum) / max(1, count - 1)
    return [
        {"value": round(minimum + step * index, 6), "label": compact_number(minimum + step * index)}
        for index in range(count)
    ]


def build_report_chart_presentation(result: dict[str, Any], locale: str = "en") -> dict[str, Any]:
    """Return a JSON-safe, deterministic presentation spec for a ChartResult."""
    existing = result.get("presentation")
    if isinstance(existing, dict) and existing.get("rows") and existing.get("domain"):
        # A server snapshot is immutable.  Preserve it when rebuilding an
        # export from a persisted artifact, while still accepting old snapshots.
        return existing

    raw_rows = result.get("rows") or []
    requested_limit = int(result.get("requested_limit") or result.get("limit") or len(raw_rows) or 1)
    requested_limit = max(1, min(30, requested_limit))
    rows: list[dict[str, Any]] = []
    for raw in raw_rows[:requested_limit]:
        if not isinstance(raw, dict):
            continue
        value = _number(raw.get("value"))
        secondary_value = raw.get("secondary_value")
        row = {
            "label": str(raw.get("label") or ""),
            "value": value,
            # Display strings are derived from server-owned canonical values.
            # Never trust a stale/client raw-format string in an export snapshot.
            "formattedValue": format_number(value),
            "compactFormattedValue": compact_number(value),
        }
        display_label = raw.get("display_label")
        if display_label is not None:
            row["displayLabel"] = str(display_label)
        if raw.get("secondary_label") is not None:
            row["secondaryLabel"] = str(raw.get("secondary_label"))
        if secondary_value is not None:
            normalized_secondary = _number(secondary_value)
            row["secondaryValue"] = normalized_secondary
            row["secondaryFormattedValue"] = format_number(normalized_secondary)
            row["secondaryCompactFormattedValue"] = compact_number(normalized_secondary)
        if raw.get("x_value") is not None:
            row["xValue"] = _number(raw.get("x_value"))
        rows.append(row)

    chart_type = str(result.get("chart_type") or "bar")
    labels = [str(row.get("displayLabel") or row.get("label") or "") for row in rows]
    sort_mode = str(result.get("sort_mode") or "ranking")
    horizontal = chart_type in {"bar", "pareto", "stacked_bar"} and (
        any(len(label) > 16 for label in labels) or (sort_mode == "ranking" and len(rows) > 7)
    )
    values = [float(row["value"]) for row in rows]
    domain = _domain(values)
    metric = str(result.get("metric_display_name") or result.get("metric") or "Value")
    dimension = str(result.get("dimension_display_name") or result.get("dimension") or "Category")
    palette_mode = "single-series"
    if chart_type in {"pie", "donut"} or any(row.get("secondaryLabel") for row in rows):
        palette_mode = "categorical" if chart_type in {"pie", "donut"} else "grouped"
    return {
        "title": str(result.get("title") or "Validated chart"),
        "chartType": chart_type,
        "orientation": "horizontal" if horizontal else "vertical",
        "metricLabel": metric,
        "dimensionLabel": dimension,
        "rows": rows,
        "requestedLimit": requested_limit,
        "returnedCount": int(result.get("result_count") or len(rows)),
        "domain": domain,
        "ticks": _ticks(domain),
        "paletteMode": palette_mode,
        "locale": "vi" if locale == "vi" else "en",
    }
