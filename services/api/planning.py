"""Constrained parsing, deterministic chart proposals, and evidence selection.

No function accepts raw SQL; every returned field is later checked against a run schema.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


_SENSITIVE_FIELD_TOKENS = {
    "email", "phone", "mobile", "address", "password", "token", "secret",
    "ssn", "passport", "national_id", "credit_card",
}
_STARTER_ANALYSIS_PATTERNS = (
    "5 goc nhin", "nam goc nhin", "goc nhin du lieu", "goi y phan tich",
    "danh gia du lieu", "phan tich du lieu", "analysis suggestions",
    "analysis suggestion", "suggest analyses", "suggest analysis", "data assessment",
    "assess the data", "evaluate the data", "evaluate data", "data evaluation",
    "5 perspectives", "five perspectives", "starter analysis", "starter analyses",
)


def _normalized_text(value: str) -> str:
    """Case- and accent-insensitive matching without changing any returned labels."""
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn").replace("đ", "d")


def is_starter_analysis_request(message: str) -> bool:
    """Identify requests for suggested views, rather than a single aggregate chart."""
    normalized = _normalized_text(message)
    return any(pattern in normalized for pattern in _STARTER_ANALYSIS_PATTERNS)


def _is_safe_analytic_field(item: object) -> bool:
    name = getattr(item, "name", "")
    normalized = re.sub(r"[^a-z0-9]+", "_", _normalized_text(name)).strip("_")
    return getattr(item, "kind", "") != "id" and not any(token in normalized for token in _SENSITIVE_FIELD_TOKENS)


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


def analyst_proposals(columns: Iterable[object], max_charts: int = 5, language: str = "en") -> list[dict[str, object]]:
    """Return stable, selectable views from safe profile metadata only.

    Ordering follows the profile column order, so equivalent profiles always produce
    the same cards.  The cards intentionally contain no values or row samples.
    """
    max_charts = max(0, min(max_charts, 5))
    safe_columns = [item for item in columns if _is_safe_analytic_field(item)]
    dimensions = [item for item in safe_columns if getattr(item, "kind", "") == "cat" and getattr(item, "null_ratio", 1) < .95]
    time_fields = [item for item in safe_columns if getattr(item, "kind", "") == "time" and getattr(item, "null_ratio", 1) < .95]
    # Numeric identifiers can be summed syntactically but have no analytical meaning.
    metrics = [item for item in safe_columns if getattr(item, "kind", "") == "num" and getattr(item, "null_ratio", 1) < .95 and not any(token in _normalized_text(getattr(item, "name", "")) for token in {"_id", " id", "code", "key"})]
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

    vietnamese = language == "vi"
    for metric in metrics:
        for field in time_fields:
            title = f"Xu hướng {getattr(metric, 'name')} theo {getattr(field, 'name')}" if vietnamese else f"{getattr(metric, 'name')} trend by {getattr(field, 'name')}"
            rationale = (f"{getattr(field, 'name')} là trường thời gian và {getattr(metric, 'name')} là chỉ tiêu số; biểu đồ xu hướng giúp nhận diện biến động và điểm đột biến." if vietnamese else f"{getattr(field, 'name')} is a time field and {getattr(metric, 'name')} is numeric; this trend view surfaces movement and potential outliers.")
            add("trend", field, metric, "line", title, rationale)
        for field in dimensions:
            name = getattr(field, "name")
            lower = _normalized_text(name)
            kind = "mix" if any(token in lower for token in {"channel", "type", "segment", "group", "b2b", "b2c"}) else "ranking"
            title = f"{getattr(metric, 'name')} theo {name}" if vietnamese else f"{getattr(metric, 'name')} by {name}"
            rationale = (f"{name} là dimension phân loại với {getattr(field, 'distinct_count')} giá trị quan sát; góc nhìn này xếp hạng đóng góp vào {getattr(metric, 'name')}." if vietnamese else f"{name} is a categorical dimension with {getattr(field, 'distinct_count')} observed values; this view ranks contribution to {getattr(metric, 'name')}.")
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
