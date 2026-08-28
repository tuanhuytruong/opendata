"""Constrained parsing, deterministic chart proposals, and evidence selection.

No function accepts raw SQL; every returned field is later checked against a run schema.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ParsedFilter:
    column: str
    operator: str
    value: str


_FILTER = re.compile(r"^\s*([\w .-]+?)\s*(=|!=|>=|<=|>|<)\s*(.+?)\s*$")


def parse_filter(text: str, allowed_columns: Iterable[str]) -> ParsedFilter:
    """Parse only a single explicit comparison against an existing non-sensitive column."""
    match = _FILTER.fullmatch(text)
    if not match:
        raise ValueError("Use an explicit filter such as `channel = Online` or `net_sales >= 1000`.")
    column, operator, value = (part.strip() for part in match.groups())
    if column not in set(allowed_columns):
        raise ValueError(f"Unknown column: {column}")
    normalized = re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_")
    if any(token in normalized for token in {"email", "phone", "mobile", "address", "password", "token", "secret", "ssn", "passport", "national_id", "credit_card"}):
        raise ValueError("Sensitive columns cannot be used in filters.")
    if len(value) > 500 or not value:
        raise ValueError("Filter value must be between 1 and 500 characters.")
    mapping = {"=": "equals", "!=": "not_equals", ">": "greater_than", ">=": "greater_or_equal", "<": "less_than", "<=": "less_or_equal"}
    return ParsedFilter(column, mapping[operator], value.strip("'\""))


def propose_charts(columns: Iterable[object], max_charts: int = 8) -> list[dict[str, str]]:
    """Build transparent, supported candidates from inferred profile roles."""
    dimensions = [getattr(item, "name") for item in columns if getattr(item, "kind") in {"cat", "time"}]
    metrics = [getattr(item, "name") for item in columns if getattr(item, "kind") == "num"]
    proposals: list[dict[str, str]] = []
    for metric in metrics:
        for dimension in dimensions:
            chart_type = "line" if "date" in dimension.lower() or "month" in dimension.lower() else "bar"
            proposals.append({"dimension": dimension, "metric": metric, "aggregation": "sum", "chart_type": chart_type, "rationale": f"Validated {chart_type} aggregate of {metric} by {dimension}."})
            if len(proposals) >= max_charts:
                return proposals
    return proposals


def analyst_proposals(columns: Iterable[object], max_charts: int = 5) -> list[dict[str, object]]:
    """Return explainable, deterministic analyst proposals from profile metadata only."""
    safe_columns = [item for item in columns if getattr(item, "kind", "") != "id"]
    dimensions = [item for item in safe_columns if getattr(item, "kind", "") == "cat" and getattr(item, "null_ratio", 1) < .95]
    time_fields = [item for item in safe_columns if getattr(item, "kind", "") == "time" and getattr(item, "null_ratio", 1) < .95]
    metrics = [item for item in safe_columns if getattr(item, "kind", "") == "num" and getattr(item, "null_ratio", 1) < .95]
    proposals: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, dimension: object, metric: object, chart_type: str, title: str, rationale: str) -> None:
        key = (getattr(dimension, "name"), getattr(metric, "name"))
        if key in seen or len(proposals) >= max_charts:
            return
        seen.add(key)
        proposals.append({
            "id": f"{kind}-{len(proposals) + 1}",
            "title": title,
            "rationale": rationale,
            "confidence": "profile-based",
            "request": {"dimension": key[0], "metric": key[1], "aggregation": "sum", "chart_type": chart_type, "limit": 12, "filters": []},
        })

    for metric in metrics:
        for field in time_fields:
            add("trend", field, metric, "line", f"Trend of {getattr(metric, 'name')} over {getattr(field, 'name')}", f"{getattr(field, 'name')} is a time field and {getattr(metric, 'name')} is numeric, so a time trend can reveal changes and spikes.")
        for field in dimensions:
            name = getattr(field, "name")
            lower = name.lower()
            kind = "mix" if any(token in lower for token in {"channel", "type", "segment", "group", "b2b", "b2c"}) else "ranking"
            title = f"{getattr(metric, 'name')} by {name}"
            rationale = f"{name} is a categorical dimension with {getattr(field, 'distinct_count')} observed values; this ranks its contribution to {getattr(metric, 'name')}."
            add(kind, field, metric, "bar", title, rationale)
    return proposals


def evidence_for_chart(chart: object) -> list[dict[str, str | float]]:
    rows = getattr(chart, "rows", [])
    title = getattr(chart, "title", "chart")
    if not rows:
        return [{"chart": title, "kind": "no_data", "text": "No matching values were available for this chart."}]
    total = sum(float(row["value"]) for row in rows)
    top = rows[0]
    share = 0 if total == 0 else round(float(top["value"]) / total * 100, 1)
    return [{"chart": title, "kind": "top_segment", "label": str(top["label"]), "value": float(top["value"]), "share_pct": share, "text": f"{top['label']} is the leading segment at {float(top['value']):,.2f} ({share}% of displayed total)."}]


def narrative_from_evidence(evidence: list[dict[str, str | float]]) -> list[str]:
    """Always-available narrative only from deterministic evidence records."""
    return [str(item["text"]) for item in evidence]
