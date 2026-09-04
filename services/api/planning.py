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


def canonical_field_name(value: str) -> str:
    """Normalize a schema name for matching only; requests retain the original name."""
    return re.sub(r"[^a-z0-9]+", "_", _normalized_text(value)).strip("_")


def is_starter_analysis_request(message: str) -> bool:
    """Identify requests for suggested views, rather than a single aggregate chart."""
    normalized = _normalized_text(message)
    return any(pattern in normalized for pattern in _STARTER_ANALYSIS_PATTERNS)


def _is_safe_analytic_field(item: object) -> bool:
    name = getattr(item, "name", "")
    normalized = canonical_field_name(name)
    return getattr(item, "kind", "") != "id" and not any(token in normalized for token in _SENSITIVE_FIELD_TOKENS)


@dataclass(frozen=True)
class ParsedFilter:
    column: str
    operator: str
    value: str


@dataclass(frozen=True)
class BusinessSemanticCatalog:
    """Profile-derived business roles, with schema order as deterministic tie-breaker.

    Aliases are deliberately conservative: an intent resolves only to a field that
    is present in the current run profile and has the appropriate inferred kind.
    """
    sales_metrics: tuple[object, ...]
    profit_metrics: tuple[object, ...]
    cost_metrics: tuple[object, ...]
    quantity_metrics: tuple[object, ...]
    locations: tuple[object, ...]
    time_fields: tuple[object, ...]

    def metric(self, intent: str) -> object | None:
        candidates = {
            "sales": self.sales_metrics,
            "revenue": self.sales_metrics,
            "profit": self.profit_metrics,
            "cost": self.cost_metrics,
            "quantity": self.quantity_metrics,
        }.get(intent, ())
        return candidates[0] if candidates else None

    def location(self) -> object | None:
        return self.locations[0] if self.locations else None

    def time(self) -> object | None:
        return self.time_fields[0] if self.time_fields else None


def business_semantic_catalog(columns: Iterable[object]) -> BusinessSemanticCatalog:
    """Derive canonical business aliases from a run's validated profile fields."""
    fields = tuple(columns)

    def matching(kind: str, aliases: tuple[str, ...]) -> tuple[object, ...]:
        # Alias precedence is the semantic contract; profile ordering breaks ties.
        return tuple(
            item for alias in aliases for item in fields
            if getattr(item, "kind", "") == kind and canonical_field_name(getattr(item, "name", "")) == alias
        )

    return BusinessSemanticCatalog(
        sales_metrics=matching("num", (
            "net_sales", "sale_excl_vat", "sales_excl_vat", "excl_vat", "revenue_excl_vat",
            "total_net_sales", "total_sales", "sales", "revenue", "gross_sales",
        )),
        profit_metrics=matching("num", ("gross_profit", "net_profit", "profit", "margin")),
        cost_metrics=matching("num", ("cost", "cogs", "cost_of_goods_sold", "total_cost")),
        quantity_metrics=matching("num", ("quantity", "qty", "units", "unit_quantity", "volume")),
        locations=matching("cat", ("store_name", "site_name", "store", "site", "location_name", "location")),
        time_fields=matching("time", ("sale_date", "sales_date", "transaction_date", "order_date", "date", "event_date")),
    )


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
    if any(token in normalized for token in _SENSITIVE_FIELD_TOKENS):
        raise ValueError("Sensitive columns cannot be used in filters.")
    if len(value) > 500 or not value:
        raise ValueError("Filter value must be between 1 and 500 characters.")
    mapping = {"=": "equals", "!=": "not_equals", ">": "greater_than", ">=": "greater_or_equal", "<": "less_than", "<=": "less_or_equal"}
    return ParsedFilter(column, mapping[operator], value.strip("'\""))


def display_label(name: str) -> str:
    """Presentation label for a schema field; never use this in API requests."""
    aliases = {
        "net_sales": "Net Sales", "gross_sales": "Gross Sales",
        "gross_profit": "Gross Profit", "sale_date": "Sale Date",
        "cogs": "Cost of Goods Sold", "uom": "Unit of Measure",
    }
    normalized = canonical_field_name(name)
    if normalized in aliases:
        return aliases[normalized]
    return " ".join(part.upper() if len(part) <= 4 and part.isalpha() else part.capitalize() for part in re.split(r"[_\s-]+", name) if part)


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
    """Return stable, executable starter views from safe profile metadata only."""
    max_charts = max(0, min(max_charts, 5))
    safe_columns = [item for item in columns if _is_safe_analytic_field(item)]
    dimensions = [item for item in safe_columns if getattr(item, "kind", "") == "cat" and getattr(item, "null_ratio", 1) < .95]
    time_fields = [item for item in safe_columns if getattr(item, "kind", "") == "time" and getattr(item, "null_ratio", 1) < .95]
    metrics = [item for item in safe_columns if getattr(item, "kind", "") == "num" and getattr(item, "null_ratio", 1) < .95 and not any(token in _normalized_text(getattr(item, "name", "")) for token in {"_id", " id", "code", "key"})]
    catalog = business_semantic_catalog(safe_columns)
    # Lead with the validated sales metric where available, then preserve profile order.
    preferred = list(catalog.sales_metrics) + [item for item in metrics if item not in catalog.sales_metrics]
    metrics = preferred
    if catalog.time() in time_fields:
        time_fields = [catalog.time()] + [item for item in time_fields if item != catalog.time()]
    if catalog.location() in dimensions:
        dimensions = [catalog.location()] + [item for item in dimensions if item != catalog.location()]
    proposals: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, dimension: object, metric: object, chart_type: str, title: str, rationale: str) -> None:
        key = (getattr(dimension, "name"), getattr(metric, "name"))
        if key in seen or len(proposals) >= max_charts:
            return
        seen.add(key)
        request = {"dimension": key[0], "metric": key[1], "aggregation": "sum", "chart_type": chart_type, "limit": 12, "filters": []}
        proposals.append({
            "id": f"{kind}-{len(proposals) + 1}", "title": title, "rationale": rationale,
            "confidence": "profile-based", "request": request,
            "prompt": f"Show sum of {key[1]} by {key[0]}",
        })

    vietnamese = language == "vi"
    for field in time_fields:
        for metric in metrics:
            title = f"Xu hướng {display_label(getattr(metric, 'name'))} theo {display_label(getattr(field, 'name'))}" if vietnamese else f"{display_label(getattr(metric, 'name'))} trend by {display_label(getattr(field, 'name'))}"
            rationale = (f"{getattr(field, 'name')} là trường thời gian và {getattr(metric, 'name')} là chỉ tiêu số; biểu đồ xu hướng giúp nhận diện biến động và điểm đột biến." if vietnamese else f"{getattr(field, 'name')} is a time field and {getattr(metric, 'name')} is numeric; this trend view surfaces movement and potential outliers.")
            add("trend", field, metric, "line", title, rationale)
    for field in dimensions:
        name = getattr(field, "name")
        lower = _normalized_text(name)
        kind = "mix" if any(token in lower for token in {"channel", "type", "segment", "group", "b2b", "b2c"}) else "ranking"
        for metric in metrics:
            title = f"{display_label(getattr(metric, 'name'))} theo {display_label(name)}" if vietnamese else f"{display_label(getattr(metric, 'name'))} by {display_label(name)}"
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
