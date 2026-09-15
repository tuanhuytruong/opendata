"""Server-owned report template metadata and deterministic v2 starters."""
from __future__ import annotations

from typing import Any

from report_models import REPORT_TEMPLATES

TEMPLATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "executive_briefing": {
        "id": "executive_briefing",
        "title": "Executive Briefing",
        "description": "Cover, KPI evidence, synthesis, growth, drivers, risks and actions.",
        "pages": ["Briefing", "Evidence & actions"],
        "block_types": ["header", "kpi_strip", "text", "chart", "note", "action_table", "glossary"],
        "placements": [(0, 0, 12, 3), (0, 3, 12, 4), (0, 7, 12, 12), (0, 19, 6, 10), (6, 19, 6, 10), (0, 29, 5, 8), (5, 29, 7, 8)],
    },
    "sales_performance_review": {
        "id": "sales_performance_review",
        "title": "Sales Performance Review",
        "description": "Period comparison, asymmetric hero trend, drivers, contribution and action plan.",
        "pages": ["Performance", "Evidence & actions"],
        "block_types": ["header", "text", "kpi_strip", "chart", "chart", "data_table", "note", "action_table"],
        "placements": [(0, 0, 12, 3), (0, 3, 8, 4), (8, 3, 4, 4), (0, 7, 8, 16), (8, 7, 4, 16), (0, 23, 12, 14), (0, 37, 6, 8), (6, 37, 6, 8)],
    },
    "category_division_deep_dive": {
        "id": "category_division_deep_dive",
        "title": "Category / Division Deep Dive",
        "description": "Scope banner, segment navigation, ranking, comparison, evidence and segment actions.",
        "pages": ["Deep dive", "Evidence"],
        "block_types": ["header", "note", "chart", "text", "chart", "data_table", "glossary", "action_table"],
        "placements": [(0, 0, 12, 3), (0, 3, 12, 4), (0, 7, 7, 14), (7, 7, 5, 14), (0, 21, 6, 14), (6, 21, 6, 14), (0, 35, 4, 10), (4, 35, 8, 10)],
    },
    "weekly_monthly_business_review": {
        "id": "weekly_monthly_business_review",
        "title": "Weekly / Monthly Business Review",
        "description": "Period snapshot, prior comparison, wins, watchouts, decisions and owner tracker.",
        "pages": ["Operating review", "Decisions & owners"],
        "block_types": ["header", "kpi_strip", "chart", "note", "data_table", "text", "action_table", "glossary"],
        "placements": [(0, 0, 12, 3), (0, 3, 12, 8), (0, 11, 8, 15), (8, 11, 4, 15), (0, 26, 6, 14), (6, 26, 6, 14), (0, 40, 12, 12), (0, 52, 12, 8)],
    },
}


def template_list() -> list[dict[str, Any]]:
    return [{key: value for key, value in definition.items() if key != "placements"} | {"placement_count": len(definition["placements"])} for definition in TEMPLATE_DEFINITIONS.values()]


def template_signature(template_id: str) -> tuple[Any, ...]:
    definition = TEMPLATE_DEFINITIONS[template_id]
    return (tuple(definition["pages"]), tuple(definition["block_types"]), tuple(definition["placements"]))


def apply_template(document: dict[str, Any], template_id: str) -> dict[str, Any]:
    """Apply layout starter while keeping the immutable artifact library."""
    if template_id not in REPORT_TEMPLATES:
        raise ValueError("Unknown report template.")
    definition = TEMPLATE_DEFINITIONS[template_id]
    library = list(document.get("artifact_library") or [])
    pages = [{"page_id": f"{template_id}-page-{index + 1}", "title": title, "order": index} for index, title in enumerate(definition["pages"])]
    blocks: list[dict[str, Any]] = []
    blocks.append({"type": "header", "block_id": "template-header", "text": definition["title"], "level": 1})
    block_types = definition["block_types"][1:]
    for index, block_type in enumerate(block_types):
        block_id = f"template-{block_type}-{index + 1}"
        if block_type == "header":
            block = {"type": "header", "block_id": block_id, "text": definition["title"], "level": 2}
        elif block_type == "text":
            block = {"type": "text", "block_id": block_id, "text": "Add an evidence-grounded narrative."}
        elif block_type == "note":
            block = {"type": "note", "block_id": block_id, "text": "Add a watchout or decision note.", "tone": "neutral"}
        elif block_type == "kpi_strip":
            block = {"type": "kpi_strip", "block_id": block_id, "artifact_ids": [item["artifact_id"] for item in library[:4]]}
        elif block_type in {"chart", "data_table"}:
            artifact = library[index % len(library)] if library else None
            block = {"type": block_type, "block_id": block_id, "artifact_id": artifact["artifact_id"] if artifact else "placeholder-artifact", "view": "table" if block_type == "data_table" else "chart", "title": ""}
            if not artifact:
                # Placeholder blocks are editor-only and are filtered from export until linked.
                continue
        elif block_type == "action_table":
            block = {"type": "action_table", "block_id": block_id, "rows": []}
        elif block_type == "glossary":
            block = {"type": "glossary", "block_id": block_id, "artifact_ids": [item["artifact_id"] for item in library], "manual_note_ids": []}
        else:
            continue
        blocks.append(block)
    placements = []
    for index, block in enumerate(blocks):
        geometry = definition["placements"][min(index, len(definition["placements"]) - 1)]
        page_id = pages[min(index // 4, len(pages) - 1)]["page_id"]
        x, y, w, h = geometry
        placements.append({"block_id": block["block_id"], "page_id": page_id, "x": x, "y": y, "w": w, "h": h})
    result = {
        **document,
        "layout_blueprint": {"template": template_id},
        "pages": pages,
        "blocks": blocks,
        "placements": placements,
    }
    return result
