"""Constrained parsing, deterministic chart proposals, and evidence selection.

No function accepts raw SQL; every returned field is later checked against a run schema.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


_SENSITIVE_FIELD_TOKENS = {"email", "phone", "mobile", "address", "password", "token", "secret", "ssn", "passport", "national_id", "credit_card"}
_STARTER_ANALYSIS_PATTERNS = ("5 goc nhin", "nam goc nhin", "goc nhin du lieu", "goi y phan tich", "danh gia du lieu", "phan tich du lieu", "analysis suggestions", "analysis suggestion", "suggest analyses", "suggest analysis", "data assessment", "assess the data", "evaluate the data", "evaluate data", "data evaluation", "5 perspectives", "five perspectives", "starter analysis", "starter analyses")


def _normalized_text(value: str) -> str:
    """Case- and accent-insensitive matching without changing returned labels."""
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn").replace("đ", "d")


def canonical_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalized_text(value)).strip("_")


def is_starter_analysis_request(message: str) -> bool:
    return any(pattern in _normalized_text(message) for pattern in _STARTER_ANALYSIS_PATTERNS)


def _is_safe_analytic_field(item: object) -> bool:
    normalized = canonical_field_name(getattr(item, "name", ""))
    return getattr(item, "kind", "") != "id" and not any(token in normalized for token in _SENSITIVE_FIELD_TOKENS)


@dataclass(frozen=True)
class ParsedFilter:
    column: str
    operator: str
    value: str


@dataclass(frozen=True)
class ComparisonTarget:
    """A schema-backed categorical field requested for an explicit comparison."""
    column: str


def comparison_target(columns: Iterable[object], message: str) -> ComparisonTarget | None:
    """Resolve B2B/B2C-style requests only; never substitute a time trend."""
    normalized = canonical_field_name(message).replace("_", " ")
    wants_comparison = bool(re.search(r"\b(compare|comparison|vs|versus|so sanh)\b", normalized))
    wants_models = bool(re.search(r"\bb2b\b", normalized) and re.search(r"\bb2c\b", normalized))
    if not (wants_comparison and wants_models):
        return None
    aliases = ("business_model", "business_type", "customer_type", "customer_segment", "channel", "sales_channel", "segment")
    fields = tuple(columns)
    for alias in aliases:
        candidate = next((item for item in fields if getattr(item, "kind", "") == "cat" and canonical_field_name(getattr(item, "name", "")) == alias and _is_safe_analytic_field(item)), None)
        if candidate:
            return ComparisonTarget(getattr(candidate, "name"))
    return None


@dataclass(frozen=True)
class BusinessSemanticCatalog:
    sales_metrics: tuple[object, ...]
    profit_metrics: tuple[object, ...]
    cost_metrics: tuple[object, ...]
    quantity_metrics: tuple[object, ...]
    locations: tuple[object, ...]
    time_fields: tuple[object, ...]

    def metric(self, intent: str) -> object | None:
        return {"sales": self.sales_metrics, "revenue": self.sales_metrics, "profit": self.profit_metrics, "cost": self.cost_metrics, "quantity": self.quantity_metrics}.get(intent, ())[0] if {"sales": self.sales_metrics, "revenue": self.sales_metrics, "profit": self.profit_metrics, "cost": self.cost_metrics, "quantity": self.quantity_metrics}.get(intent, ()) else None

    def location(self) -> object | None: return self.locations[0] if self.locations else None
    def time(self) -> object | None: return self.time_fields[0] if self.time_fields else None


def business_semantic_catalog(columns: Iterable[object]) -> BusinessSemanticCatalog:
    fields = tuple(columns)
    def matching(kind: str, aliases: tuple[str, ...]) -> tuple[object, ...]:
        return tuple(item for alias in aliases for item in fields if getattr(item, "kind", "") == kind and canonical_field_name(getattr(item, "name", "")) == alias)
    return BusinessSemanticCatalog(
        sales_metrics=matching("num", ("net_sales", "sale_excl_vat", "sales_excl_vat", "excl_vat", "revenue_excl_vat", "total_net_sales", "total_sales", "sales", "revenue", "gross_sales")),
        profit_metrics=matching("num", ("gross_profit", "net_profit", "profit", "margin")),
        cost_metrics=matching("num", ("cost", "cogs", "cost_of_goods_sold", "total_cost")),
        quantity_metrics=matching("num", ("quantity", "qty", "units", "unit_quantity", "volume")),
        locations=matching("cat", ("store_name", "site_name", "store", "site", "location_name", "location")),
        time_fields=matching("time", ("sale_date", "sales_date", "transaction_date", "order_date", "date", "event_date")),
    )


_FILTER = re.compile(r"^\s*([\w .-]+?)\s*(=|!=|>=|<=|>|<)\s*(.+?)\s*$")
def parse_filter(text: str, allowed_columns: Iterable[str]) -> ParsedFilter:
    match = _FILTER.fullmatch(text)
    if not match: raise ValueError("Use an explicit filter such as `channel = Online` or `net_sales >= 1000`.")
    column, operator, value = (part.strip() for part in match.groups())
    if column not in set(allowed_columns): raise ValueError(f"Unknown column: {column}")
    if any(token in canonical_field_name(column) for token in _SENSITIVE_FIELD_TOKENS): raise ValueError("Sensitive columns cannot be used in filters.")
    if len(value) > 500 or not value: raise ValueError("Filter value must be between 1 and 500 characters.")
    return ParsedFilter(column, {"=":"equals", "!=":"not_equals", ">":"greater_than", ">=":"greater_or_equal", "<":"less_than", "<=":"less_or_equal"}[operator], value.strip("'\""))


def display_label(name: str) -> str:
    aliases = {"net_sales":"Net Sales", "gross_sales":"Gross Sales", "gross_profit":"Gross Profit", "sale_date":"Sale Date", "cogs":"Cost of Goods Sold", "uom":"Unit of Measure"}
    normalized = canonical_field_name(name)
    if normalized in aliases: return aliases[normalized]
    return " ".join(part.upper() if len(part) <= 4 and part.isalpha() else part.capitalize() for part in re.split(r"[_\s-]+", name) if part)


def executive_overview_proposals(columns: Iterable[object]) -> tuple[list[dict[str, object]], list[str]]:
    """Return at most one safe request for each overview visual contract.

    This is schema-only: it never invents metric values and callers still execute every
    proposal as a server-validated aggregate.
    """
    safe = [item for item in columns if _is_safe_analytic_field(item) and getattr(item, "null_ratio", 1) < .95]
    metrics = [item for item in safe if getattr(item, "kind", "") == "num" and not any(token in canonical_field_name(getattr(item, "name", "")) for token in ("id", "code", "key"))]
    cats = [item for item in safe if getattr(item, "kind", "") == "cat"]
    times = [item for item in safe if getattr(item, "kind", "") == "time"]
    catalog = business_semantic_catalog(safe)
    def unique(items: list[object]) -> list[object]:
        seen: set[str] = set()
        return [item for item in items if not (getattr(item, "name", "") in seen or seen.add(getattr(item, "name", "")))]
    ordered_metrics = unique([*catalog.sales_metrics, *catalog.quantity_metrics, *catalog.cost_metrics, *catalog.profit_metrics, *metrics])
    ordered_cats = unique([*catalog.locations, *cats])
    ordered_times = unique([*([catalog.time()] if catalog.time() else []), *times])
    proposals: list[dict[str, object]] = []; omissions: list[str] = []; used: set[tuple[str, str]] = set()
    def add(chart_type: str, dimension: object | None, metric: object | None, role: str, reason: str) -> None:
        if not dimension or not metric:
            omissions.append(reason); return
        pair=(getattr(dimension,"name"), getattr(metric,"name"))
        # A visual must provide a distinct analytic pairing where possible.
        alternatives=[(d,m) for d in ([*ordered_times] if chart_type in {"line","area"} else [*ordered_cats]) for m in ordered_metrics if (getattr(d,"name"),getattr(m,"name")) not in used]
        if pair in used and alternatives: dimension, metric = alternatives[0]; pair=(getattr(dimension,"name"),getattr(metric,"name"))
        if pair in used: omissions.append(reason); return
        used.add(pair)
        proposals.append({"role":role,"request":{"dimension":pair[0],"metric":pair[1],"aggregation":"sum","chart_type":chart_type,"limit":12,"filters":[]}})
    first_time = ordered_times[0] if ordered_times else None
    first_cat = ordered_cats[0] if ordered_cats else None
    pie_cat = next((item for item in ordered_cats if 1 < getattr(item,"distinct_count",0) <= 12), None)
    add("line", first_time, ordered_metrics[0] if ordered_metrics else None, "trend", "Line trend omitted: no safe time field and numeric metric.")
    add("bar", first_cat, ordered_metrics[1] if len(ordered_metrics)>1 else (ordered_metrics[0] if ordered_metrics else None), "comparison", "Vertical bar omitted: no safe category and numeric metric.")
    add("bar", ordered_cats[1] if len(ordered_cats)>1 else first_cat, ordered_metrics[2] if len(ordered_metrics)>2 else (ordered_metrics[0] if ordered_metrics else None), "ranking", "Ranking bar omitted: no safe category and numeric metric.")
    add("donut", pie_cat, ordered_metrics[3] if len(ordered_metrics)>3 else (ordered_metrics[0] if ordered_metrics else None), "mix", "Pie/donut omitted: no categorical field with 2–12 values and numeric metric.")
    add("area", first_time, ordered_metrics[4] if len(ordered_metrics)>4 else (ordered_metrics[-1] if ordered_metrics else None), "area", "Area trend omitted: no additional safe time/metric pairing.")
    return proposals, omissions


def presentation_title(metric: str, dimension: str, chart_type: str, *, language: str = "en", limit: int | None = None, secondary_dimension: str | None = None) -> str:
    """Business-facing title template; schema identifiers stay in scope metadata."""
    metric_label = display_label(metric)
    dimension_label = display_label(dimension)
    sales = canonical_field_name(metric) in {"net_sales", "sale_excl_vat", "sales_excl_vat", "excl_vat", "revenue", "gross_sales", "total_sales"}
    if language == "vi":
        if chart_type in {"line", "area"}: return f"Hiệu suất {metric_label} theo thời gian"
        if chart_type in {"pie", "donut"}: return f"Cơ cấu {metric_label} theo {dimension_label}"
        if secondary_dimension: return f"So sánh {metric_label} theo {dimension_label} và {display_label(secondary_dimension)}"
        return f"Top {limit or ''} {dimension_label} theo {metric_label}".replace("Top  ", "")
    noun = "Sales" if sales else metric_label
    if chart_type in {"line", "area"}: return f"{noun} Performance Over Time"
    if chart_type in {"pie", "donut"}: return f"{noun} Contribution by {dimension_label}"
    if secondary_dimension: return f"{noun} by {dimension_label} and {display_label(secondary_dimension)}"
    return f"Top {limit or ''} {dimension_label} by {noun}".replace("Top  ", "")


def propose_charts(columns: Iterable[object], max_charts: int = 8) -> list[dict[str, str]]:
    proposals, _ = executive_overview_proposals(columns)
    return [{**item["request"], "rationale": f"Validated {item['request']['chart_type']} aggregate for the {item['role']} overview view."} for item in proposals[:max_charts]]


def analyst_proposals(columns: Iterable[object], max_charts: int = 5, language: str = "en") -> list[dict[str, object]]:
    safe_columns = [item for item in columns if _is_safe_analytic_field(item)]
    dimensions = [item for item in safe_columns if getattr(item,"kind","") == "cat" and getattr(item,"null_ratio",1)<.95]
    time_fields = [item for item in safe_columns if getattr(item,"kind","") == "time" and getattr(item,"null_ratio",1)<.95]
    metrics = [item for item in safe_columns if getattr(item,"kind","") == "num" and getattr(item,"null_ratio",1)<.95 and not any(token in canonical_field_name(getattr(item,"name","")) for token in ("id","code","key"))]
    catalog=business_semantic_catalog(safe_columns)
    def unique(items: list[object]) -> list[object]:
        seen: set[str] = set()
        return [item for item in items if not (getattr(item, "name", "") in seen or seen.add(getattr(item, "name", "")))]
    metrics = unique([*catalog.sales_metrics, *metrics])
    dimensions = unique([*catalog.locations, *dimensions])
    time_fields = unique([*([catalog.time()] if catalog.time() else []), *time_fields])
    proposals=[]; seen=set()
    def add(kind, dimension, metric, chart_type):
        if not dimension or not metric or len(proposals)>=max(0,min(max_charts,5)): return
        key=(dimension.name,metric.name)
        if key in seen:return
        seen.add(key); title=(f"{display_label(metric.name)} theo {display_label(dimension.name)}" if language=="vi" else f"{display_label(metric.name)} by {display_label(dimension.name)}")
        proposals.append({"id":f"{kind}-{len(proposals)+1}","title":title,"rationale":f"Validated {chart_type} aggregate from schema-profiled fields.","confidence":"profile-based","request":{"dimension":dimension.name,"metric":metric.name,"aggregation":"sum","chart_type":chart_type,"limit":12,"filters":[]},"prompt":f"Show sum of {metric.name} by {dimension.name}"})
    for field in time_fields:
        for metric in metrics: add("trend",field,metric,"line")
    for field in dimensions:
        for metric in metrics: add("ranking",field,metric,"bar")
    return proposals


def evidence_for_chart(chart: object) -> list[dict[str, str | float]]:
    rows=getattr(chart,"rows",[]); title=getattr(chart,"title","chart")
    if not rows:return [{"chart":title,"kind":"no_data","text":"No matching values were available for this chart."}]
    total=sum(float(row["value"]) for row in rows); top=rows[0]; share=0 if total==0 else round(float(top["value"])/total*100,1)
    return [{"chart":title,"kind":"top_segment","label":str(top["label"]),"value":float(top["value"]),"share_pct":share,"text":f"{top['label']} is the leading segment at {float(top['value']):,.2f} ({share}% of displayed total)."}]

def narrative_from_evidence(evidence: list[dict[str, str | float]]) -> list[str]: return [str(item["text"]) for item in evidence]
