"""Canonical, strict Custom Report v2 document contract.

This module owns the report editor's durable shape.  Analytical values remain
server-owned snapshots; presentation blocks only reference artifact IDs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REPORT_TEMPLATES = (
    "executive_briefing",
    "sales_performance_review",
    "category_division_deep_dive",
    "weekly_monthly_business_review",
)


def _safe_text(value: str, maximum: int, field_name: str) -> str:
    if len(value) > maximum:
        raise ValueError(f"{field_name} exceeds the maximum length.")
    lowered = value.lower()
    if any(token in lowered for token in ("<script", "javascript:", "<style", "onerror=", "onload=")):
        raise ValueError(f"{field_name} contains unsupported markup.")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReportPageSettings(StrictModel):
    width: Literal["desktop"] = "desktop"
    columns: Literal[12] = 12
    row_height: int = Field(default=24, ge=12, le=80)
    gap: int = Field(default=16, ge=0, le=48)


class ReportPage(StrictModel):
    page_id: str = Field(min_length=1, max_length=80)
    title: str = Field(default="Page 1", min_length=1, max_length=160)
    order: int = Field(default=0, ge=0, le=100)

    @field_validator("page_id", "title")
    @classmethod
    def safe_values(cls, value: str, info):
        return _safe_text(value, 160, info.field_name)


class HeaderBlock(StrictModel):
    type: Literal["header"]
    block_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=2_000)
    level: Literal[1, 2, 3] = 1


class TextBlock(StrictModel):
    type: Literal["text"]
    block_id: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=8_000)


class NoteBlock(StrictModel):
    type: Literal["note"]
    block_id: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=4_000)
    tone: Literal["neutral", "info", "warning", "success"] = "neutral"


class DividerBlock(StrictModel):
    type: Literal["divider"]
    block_id: str = Field(min_length=1, max_length=80)


class KpiStripBlock(StrictModel):
    type: Literal["kpi_strip"]
    block_id: str = Field(min_length=1, max_length=80)
    artifact_ids: list[str] = Field(default_factory=list, max_length=12)


class ActionTableBlock(StrictModel):
    type: Literal["action_table"]
    block_id: str = Field(min_length=1, max_length=80)
    rows: list[dict[str, str]] = Field(default_factory=list, max_length=30)

    @field_validator("rows")
    @classmethod
    def safe_rows(cls, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        for row in rows:
            if set(row) - {"owner", "action", "deadline", "status"}:
                raise ValueError("Action rows contain an unsupported field.")
            for value in row.values():
                _safe_text(value, 500, "action row")
        return rows


class ChartBlock(StrictModel):
    type: Literal["chart"]
    block_id: str = Field(min_length=1, max_length=80)
    artifact_id: str = Field(min_length=1, max_length=120)
    view: Literal["chart"] = "chart"
    title: str = Field(default="", max_length=160)


class DataTableBlock(StrictModel):
    type: Literal["data_table"]
    block_id: str = Field(min_length=1, max_length=80)
    artifact_id: str = Field(min_length=1, max_length=120)
    view: Literal["table"] = "table"
    title: str = Field(default="", max_length=160)


class GlossaryBlock(StrictModel):
    type: Literal["glossary"]
    block_id: str = Field(min_length=1, max_length=80)
    artifact_ids: list[str] = Field(default_factory=list, max_length=24)
    manual_note_ids: list[str] = Field(default_factory=list, max_length=30)


ReportBlock = Annotated[
    HeaderBlock
    | TextBlock
    | NoteBlock
    | DividerBlock
    | KpiStripBlock
    | ActionTableBlock
    | ChartBlock
    | DataTableBlock
    | GlossaryBlock,
    Field(discriminator="type"),
]


class ReportPlacement(StrictModel):
    block_id: str = Field(min_length=1, max_length=80)
    page_id: str = Field(min_length=1, max_length=80)
    x: int = Field(default=0, ge=0, lt=12)
    y: int = Field(default=0, ge=0, le=10_000)
    w: int = Field(default=12, ge=1, le=12)
    h: int = Field(default=4, ge=1, le=500)

    @model_validator(mode="after")
    def stays_inside_grid(self) -> "ReportPlacement":
        if self.x + self.w > 12:
            raise ValueError("Placement exceeds the 12-column report grid.")
        return self


class ReportArtifactSnapshot(StrictModel):
    artifact_id: str = Field(min_length=1, max_length=120)
    origin: Literal["executive_hub", "data_copilot", "legacy", "unknown"] = "unknown"
    chart: dict[str, Any]
    result: dict[str, Any] | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    artifact_hash: str = ""

    @field_validator("chart")
    @classmethod
    def chart_is_a_spec(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value or not isinstance(value.get("dimension"), str) or not isinstance(value.get("metric"), str):
            raise ValueError("Artifact chart must contain a validated dimension and metric.")
        if any(key in value for key in ("html", "raw_html", "sql", "rows", "evidence")):
            raise ValueError("Artifact chart may not contain client-owned result content.")
        return value


class ReportDocumentV2(StrictModel):
    schema_version: Literal[2] = 2
    run_id: str = Field(min_length=1, max_length=80)
    title: str = Field(default="Custom Report", min_length=1, max_length=120)
    locale: Literal["en", "vi"] = "en"
    page_settings: ReportPageSettings = Field(default_factory=ReportPageSettings)
    pages: list[ReportPage] = Field(default_factory=lambda: [ReportPage(page_id="page-1", title="Page 1")], max_length=20)
    blocks: list[ReportBlock] = Field(default_factory=list, max_length=200)
    placements: list[ReportPlacement] = Field(default_factory=list, max_length=500)
    artifact_library: list[ReportArtifactSnapshot] = Field(default_factory=list, max_length=100)
    updated_at: str = ""
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_references(self) -> "ReportDocumentV2":
        page_ids = [page.page_id for page in self.pages]
        block_ids = [block.block_id for block in self.blocks]
        artifact_ids = [artifact.artifact_id for artifact in self.artifact_library]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("Report page IDs must be unique.")
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("Report block IDs must be unique.")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("Report artifact IDs must be unique.")
        if len({(item.page_id, item.block_id) for item in self.placements}) != len(self.placements):
            raise ValueError("A block may have only one placement per page.")
        valid_pages = set(page_ids)
        valid_blocks = set(block_ids)
        valid_artifacts = set(artifact_ids)
        for placement in self.placements:
            if placement.page_id not in valid_pages or placement.block_id not in valid_blocks:
                raise ValueError("Placement references a missing page or block.")
        for block in self.blocks:
            refs = []
            if isinstance(block, (ChartBlock, DataTableBlock)):
                refs = [block.artifact_id]
            elif isinstance(block, (KpiStripBlock, GlossaryBlock)):
                refs = [*block.artifact_ids]
            if any(ref not in valid_artifacts for ref in refs):
                raise ValueError("Report block references an artifact outside the Library.")
        return self


def _placement(block_id: str, page_id: str, x: int, y: int, w: int, h: int) -> dict[str, Any]:
    return {"block_id": block_id, "page_id": page_id, "x": x, "y": y, "w": w, "h": h}


def build_v2_from_legacy(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic v2 document from the existing authored shape."""
    if payload.get("schema_version") == 2:
        canonical = {key: payload[key] for key in ("schema_version", "run_id", "title", "locale", "page_settings", "pages", "blocks", "placements", "artifact_library", "updated_at", "revision") if key in payload}
        return ReportDocumentV2.model_validate(canonical).model_dump(mode="json")
    template = ((payload.get("layout_blueprint") or {}).get("template") or "executive_briefing")
    if template == "executive":
        template = "executive_briefing"
    run_id = str(payload.get("run_id", ""))
    pages = [{"page_id": "page-1", "title": "Page 1", "order": 0}]
    blocks: list[dict[str, Any]] = [{"type": "header", "block_id": "header-1", "text": str(payload.get("title") or "Custom Report"), "level": 1}]
    placements = [_placement("header-1", "page-1", 0, 0, 12, 3)]
    summary = str(payload.get("executive_summary") or "")
    if summary:
        blocks.append({"type": "text", "block_id": "summary-1", "text": summary})
        placements.append(_placement("summary-1", "page-1", 0, 3, 12, 4))
    library: list[dict[str, Any]] = []
    for index, artifact in enumerate(payload.get("pinned_artifacts") or []):
        artifact_id = str(artifact.get("artifact_id") or f"legacy-artifact-{index}")
        library.append({
            "artifact_id": artifact_id,
            "origin": "legacy",
            "chart": artifact.get("chart") or {},
            "result": artifact.get("result"),
            "provenance": {"scope": artifact.get("scope", ""), "title": artifact.get("title", "")},
            "created_at": payload.get("updated_at", ""),
        })
        block_type = "data_table" if template == "category_division_deep_dive" and index % 3 == 2 else "chart"
        block_id = f"artifact-{index + 1}"
        blocks.append({"type": block_type, "block_id": block_id, "artifact_id": artifact_id, "view": "table" if block_type == "data_table" else "chart", "title": artifact.get("title", "")})
        if template == "sales_performance_review":
            x, y, w, h = ((0, 7, 8, 14) if index == 0 else (8, 7, 4, 10))
        elif template == "category_division_deep_dive":
            x, y, w, h = ((0, 7, 7, 12) if index == 0 else (7, 7, 5, 12))
        elif template == "weekly_monthly_business_review":
            x, y, w, h = ((0, 7, 8, 10) if index == 0 else (8, 7, 4, 10))
        else:
            x, y, w, h = (0, 7 + index * 10, 12, 10 if index == 0 else 8)
        placements.append(_placement(block_id, "page-1", x, y, w, h))
    for index, section in enumerate(payload.get("sections") or []):
        block_id = f"section-{section.get('section_id') or index}"
        blocks.append({"type": "text", "block_id": block_id, "text": f"{section.get('heading', '')}\n{section.get('commentary', '')}".strip()})
        placements.append(_placement(block_id, "page-1", 0, 20 + index * 5, 12, 4))
    if payload.get("manual_glossary_notes"):
        blocks.append({"type": "glossary", "block_id": "glossary-1", "artifact_ids": [item["artifact_id"] for item in library], "manual_note_ids": [item.get("note_id", "") for item in payload["manual_glossary_notes"]]})
        placements.append(_placement("glossary-1", "page-1", 0, 80, 12, 6))
    document = {
        "schema_version": 2,
        "run_id": run_id,
        "title": payload.get("title") or "Custom Report",
        "locale": payload.get("locale") or "en",
        "page_settings": {"width": "desktop", "columns": 12, "row_height": 24, "gap": 16},
        "pages": pages,
        "blocks": blocks,
        "placements": placements,
        "artifact_library": library,
        "updated_at": payload.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        "revision": int(payload.get("revision") or 0),
    }
    return ReportDocumentV2.model_validate(document).model_dump(mode="json")


def validate_report_v2(payload: dict[str, Any]) -> ReportDocumentV2:
    return ReportDocumentV2.model_validate(payload)
