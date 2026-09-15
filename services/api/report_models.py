"""Canonical, strict Custom Report v2 document contract.

This module owns the report editor's durable shape. Analytical values remain
server-owned snapshots; presentation blocks reference immutable artifact IDs.
Authored text is stored as a small, allowlisted structured document rather than
HTML so editor, preview and export can safely share it.
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


class RichTextDocument(StrictModel):
    """Allowlisted ProseMirror-compatible JSON without arbitrary HTML."""

    type: Literal["doc"] = "doc"
    content: list[dict[str, Any]] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def validate_content(self) -> "RichTextDocument":
        total = 0
        for node in self.content:
            total += _validate_rich_node(node, depth=0)
        if total > 16_000:
            raise ValueError("Rich text exceeds the maximum total length.")
        return self


def _validate_rich_node(node: Any, depth: int) -> int:
    if depth > 8 or not isinstance(node, dict):
        raise ValueError("Rich text nesting is invalid or too deep.")
    kind = node.get("type")
    if not isinstance(kind, str):
        raise ValueError("Rich text nodes require a type.")
    if kind == "hardBreak":
        if set(node) != {"type"}:
            raise ValueError("Hard breaks do not accept attributes.")
        return 1
    if kind in {"paragraph", "heading"}:
        allowed = {"type", "attrs", "content"}
        if set(node) - allowed:
            raise ValueError("Rich text paragraph contains an unsupported field.")
        attrs = node.get("attrs") or {}
        if not isinstance(attrs, dict) or set(attrs) - {"textAlign", "level"}:
            raise ValueError("Rich text paragraph attributes are unsupported.")
        if attrs.get("textAlign") not in {None, "left", "center", "right"}:
            raise ValueError("Rich text alignment is unsupported.")
        if kind == "heading" and attrs.get("level") not in {1, 2, 3}:
            raise ValueError("Heading level must be 1, 2, or 3.")
        content = node.get("content") or []
        if not isinstance(content, list) or len(content) > 200:
            raise ValueError("Rich text inline content is invalid.")
        return sum(_validate_rich_inline(item) for item in content)
    if kind in {"bulletList", "orderedList", "listItem"}:
        if set(node) - {"type", "content"}:
            raise ValueError("Rich text list contains an unsupported field.")
        content = node.get("content") or []
        if not isinstance(content, list) or len(content) > 40:
            raise ValueError("Rich text list content is invalid.")
        if kind in {"bulletList", "orderedList"} and any(not isinstance(item, dict) or item.get("type") != "listItem" for item in content):
            raise ValueError("Rich text lists must contain list items.")
        if kind == "listItem" and any(not isinstance(item, dict) or item.get("type") not in {"paragraph", "heading", "bulletList", "orderedList"} for item in content):
            raise ValueError("Rich text list items contain an unsupported node.")
        return sum(_validate_rich_node(item, depth + 1) for item in content)
    raise ValueError(f"Rich text node type '{kind}' is unsupported.")


def _validate_rich_inline(value: Any) -> int:
    if not isinstance(value, dict) or set(value) - {"type", "text", "marks"} or value.get("type") != "text":
        raise ValueError("Rich text inline content is invalid.")
    text = value.get("text")
    if not isinstance(text, str):
        raise ValueError("Rich text inline text must be a string.")
    _safe_text(text, 2_000, "rich text")
    marks = value.get("marks") or []
    if not isinstance(marks, list) or len(marks) > 5:
        raise ValueError("Rich text marks are invalid.")
    for mark in marks:
        if not isinstance(mark, dict) or set(mark) - {"type", "attrs"}:
            raise ValueError("Rich text mark is invalid.")
        mark_type = mark.get("type")
        if mark_type not in {"bold", "italic", "underline", "fontSize"}:
            raise ValueError("Rich text mark is unsupported.")
        attrs = mark.get("attrs")
        if mark_type == "fontSize":
            if not isinstance(attrs, dict) or set(attrs) != {"size"} or attrs.get("size") not in {"sm", "base", "lg", "xl"}:
                raise ValueError("Rich text font size is unsupported.")
        elif attrs is not None:
            raise ValueError("This rich text mark does not accept attributes.")
    return len(text)


def rich_text_from_text(value: str, *, heading_level: int | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "heading" if heading_level else "paragraph", "content": [{"type": "text", "text": value}] if value else []}
    if heading_level:
        node["attrs"] = {"level": heading_level, "textAlign": "left"}
    return {"type": "doc", "content": [node]}


def plain_text_from_rich_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    pieces: list[str] = []

    def visit(node: Any) -> None:
        if not isinstance(node, dict):
            return
        kind = node.get("type")
        if kind == "text":
            pieces.append(str(node.get("text") or ""))
        elif kind == "hardBreak":
            pieces.append("\n")
        else:
            for child in node.get("content") or []:
                visit(child)
            if kind in {"paragraph", "heading", "listItem"}:
                pieces.append("\n")

    for child in value.get("content") or []:
        visit(child)
    return "".join(pieces).strip()


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
    text: str = Field(default="Untitled section", min_length=1, max_length=2_000)
    rich_text: RichTextDocument = Field(default_factory=lambda: RichTextDocument.model_validate(rich_text_from_text("Untitled section", heading_level=1)))
    level: Literal[1, 2, 3] = 1

    @model_validator(mode="before")
    @classmethod
    def normalize_rich_text(cls, value: Any) -> Any:
        data = dict(value or {})
        level = int(data.get("level") or 1)
        if not data.get("rich_text"):
            data["rich_text"] = rich_text_from_text(str(data.get("text") or "Untitled section"), heading_level=level)
        if not data.get("text"):
            data["text"] = plain_text_from_rich_text(data["rich_text"]) or "Untitled section"
        return data


class TextBlock(StrictModel):
    type: Literal["text"]
    block_id: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=8_000)
    rich_text: RichTextDocument = Field(default_factory=RichTextDocument)

    @model_validator(mode="before")
    @classmethod
    def normalize_rich_text(cls, value: Any) -> Any:
        data = dict(value or {})
        if not data.get("rich_text"):
            data["rich_text"] = rich_text_from_text(str(data.get("text") or ""))
        if "text" not in data:
            data["text"] = plain_text_from_rich_text(data["rich_text"])
        return data


class NoteBlock(StrictModel):
    type: Literal["note"]
    block_id: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=4_000)
    rich_text: RichTextDocument = Field(default_factory=RichTextDocument)
    tone: Literal["neutral", "info", "warning", "success"] = "neutral"

    @model_validator(mode="before")
    @classmethod
    def normalize_rich_text(cls, value: Any) -> Any:
        data = dict(value or {})
        if not data.get("rich_text"):
            data["rich_text"] = rich_text_from_text(str(data.get("text") or ""))
        if "text" not in data:
            data["text"] = plain_text_from_rich_text(data["rich_text"])
        return data


class DividerBlock(StrictModel):
    type: Literal["divider"]
    block_id: str = Field(min_length=1, max_length=80)
    style: Literal["solid", "dashed", "dotted"] = "solid"
    thickness: Literal[1, 2, 3] = 1
    color: Literal["slate", "indigo", "amber"] = "slate"


class KpiItem(StrictModel):
    artifact_id: str = Field(min_length=1, max_length=120)
    row_label: str = Field(default="", max_length=240)
    label_override: str = Field(default="", max_length=160)

    @field_validator("row_label", "label_override")
    @classmethod
    def safe_labels(cls, value: str, info):
        return _safe_text(value, 240, info.field_name)


class KpiStripBlock(StrictModel):
    type: Literal["kpi_strip"]
    block_id: str = Field(min_length=1, max_length=80)
    artifact_ids: list[str] = Field(default_factory=list, max_length=12)
    items: list[KpiItem] = Field(default_factory=list, max_length=12)

    @model_validator(mode="before")
    @classmethod
    def normalize_items(cls, value: Any) -> Any:
        data = dict(value or {})
        if not data.get("items"):
            data["items"] = [{"artifact_id": item} for item in data.get("artifact_ids") or []]
        if not data.get("artifact_ids"):
            data["artifact_ids"] = [item.get("artifact_id") for item in data.get("items") or [] if isinstance(item, dict) and item.get("artifact_id")]
        return data


class ActionRow(StrictModel):
    owner: str = Field(default="", max_length=160)
    action: str = Field(default="", max_length=500)
    deadline: str = Field(default="", max_length=30)
    status: Literal["not_started", "in_progress", "blocked", "done"] = "not_started"

    @model_validator(mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> Any:
        data = dict(value or {})
        aliases = {"todo": "not_started", "planned": "not_started", "open": "not_started", "pending": "not_started", "in progress": "in_progress", "complete": "done"}
        if isinstance(data.get("status"), str):
            data["status"] = aliases.get(data["status"].strip().lower(), data["status"].strip().lower())
        return data

    @field_validator("owner", "action", "deadline")
    @classmethod
    def safe_values(cls, value: str, info):
        return _safe_text(value, 500, info.field_name)

    @field_validator("deadline")
    @classmethod
    def valid_deadline(cls, value: str) -> str:
        if value:
            try:
                datetime.fromisoformat(value)
            except ValueError as error:
                raise ValueError("Action deadline must be an ISO date or datetime.") from error
        return value


class ActionTableBlock(StrictModel):
    type: Literal["action_table"]
    block_id: str = Field(min_length=1, max_length=80)
    rows: list[ActionRow] = Field(default_factory=list, max_length=30)


class ChartBlock(StrictModel):
    type: Literal["chart"]
    block_id: str = Field(min_length=1, max_length=80)
    artifact_id: str = Field(min_length=1, max_length=120)
    view: Literal["chart"] = "chart"
    title: str = Field(default="", max_length=160)

    @field_validator("title")
    @classmethod
    def safe_title(cls, value: str) -> str:
        return _safe_text(value, 160, "title")


class DataTableBlock(StrictModel):
    type: Literal["data_table"]
    block_id: str = Field(min_length=1, max_length=80)
    artifact_id: str = Field(min_length=1, max_length=120)
    view: Literal["table"] = "table"
    title: str = Field(default="", max_length=160)
    visible_rows: int = Field(default=30, ge=1, le=100)

    @field_validator("title")
    @classmethod
    def safe_title(cls, value: str) -> str:
        return _safe_text(value, 160, "title")


class GlossaryNote(StrictModel):
    note_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1_000)

    @field_validator("text")
    @classmethod
    def safe_text(cls, value: str) -> str:
        return _safe_text(value, 1_000, "glossary note")


class GlossaryBlock(StrictModel):
    type: Literal["glossary"]
    block_id: str = Field(min_length=1, max_length=80)
    artifact_ids: list[str] = Field(default_factory=list, max_length=24)
    manual_note_ids: list[str] = Field(default_factory=list, max_length=30)
    authored_notes: list[GlossaryNote] = Field(default_factory=list, max_length=30)


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
    presentation: dict[str, Any] | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    artifact_hash: str = ""
    dataset_sha256: str = Field(default="", max_length=128)
    view_capabilities: list[Literal["chart", "table"]] = Field(default_factory=lambda: ["chart", "table"], max_length=2)

    @model_validator(mode="before")
    @classmethod
    def normalize_chart_snapshot(cls, value: Any) -> Any:
        data = dict(value or {})
        result = data.get("result")
        if not data.get("presentation") and isinstance(result, dict) and result.get("rows"):
            try:
                from report_chart_presentation import build_report_chart_presentation
                data["presentation"] = build_report_chart_presentation(result)
            except (ImportError, TypeError, ValueError):
                # The normalizer remains usable in migration/unit contexts where
                # optional chart modules are not importable yet.
                pass
        return data

    @field_validator("provenance")
    @classmethod
    def provenance_is_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = {"rows", "evidence", "warnings", "html", "raw_html", "sql"}
        if forbidden.intersection(value):
            raise ValueError("Artifact provenance may only contain metadata.")
        return value

    @field_validator("chart")
    @classmethod
    def chart_is_a_spec(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value or not isinstance(value.get("dimension"), str) or not isinstance(value.get("metric"), str):
            raise ValueError("Artifact chart must contain a validated dimension and metric.")
        if any(key in value for key in ("html", "raw_html", "sql", "rows", "evidence")):
            raise ValueError("Artifact chart may not contain client-owned result content.")
        return value

    @field_validator("result", "presentation")
    @classmethod
    def result_is_json_safe(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        try:
            import json
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Artifact result must contain JSON-safe values.") from error
        return value


class ReportLayoutBlueprint(StrictModel):
    template: Literal[
        "executive_briefing",
        "sales_performance_review",
        "category_division_deep_dive",
        "weekly_monthly_business_review",
    ] = "executive_briefing"


class ReportDocumentV2(StrictModel):
    schema_version: Literal[2] = 2
    run_id: str = Field(min_length=1, max_length=80)
    title: str = Field(default="Custom Report", min_length=1, max_length=120)
    locale: Literal["en", "vi"] = "en"
    layout_blueprint: ReportLayoutBlueprint = Field(default_factory=ReportLayoutBlueprint)
    page_settings: ReportPageSettings = Field(default_factory=ReportPageSettings)
    pages: list[ReportPage] = Field(default_factory=lambda: [ReportPage(page_id="page-1", title="Page 1")], max_length=20)
    blocks: list[ReportBlock] = Field(default_factory=list, max_length=200)
    placements: list[ReportPlacement] = Field(default_factory=list, max_length=500)
    artifact_library: list[ReportArtifactSnapshot] = Field(default_factory=list, max_length=100)
    updated_at: str = ""
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_references(self) -> "ReportDocumentV2":
        self.title = _safe_text(self.title, 120, "title")
        page_ids = [page.page_id for page in self.pages]
        block_ids = [block.block_id for block in self.blocks]
        artifact_ids = [artifact.artifact_id for artifact in self.artifact_library]
        if not page_ids:
            raise ValueError("A report must contain at least one page.")
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("Report page IDs must be unique.")
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("Report block IDs must be unique.")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("Report artifact IDs must be unique.")
        ordered = sorted(self.pages, key=lambda page: (page.order, page.page_id))
        for index, page in enumerate(ordered):
            object.__setattr__(page, "order", index)
        if len({(item.page_id, item.block_id) for item in self.placements}) != len(self.placements):
            raise ValueError("A block may have only one placement per page.")
        valid_pages = set(page_ids)
        valid_blocks = set(block_ids)
        valid_artifacts = set(artifact_ids)
        for placement in self.placements:
            if placement.page_id not in valid_pages or placement.block_id not in valid_blocks:
                raise ValueError("Placement references a missing page or block.")
        for block in self.blocks:
            refs: list[str] = []
            if isinstance(block, (ChartBlock, DataTableBlock)):
                refs = [block.artifact_id]
            elif isinstance(block, KpiStripBlock):
                refs = [*block.artifact_ids, *(item.artifact_id for item in block.items)]
            elif isinstance(block, GlossaryBlock):
                refs = [*block.artifact_ids]
            if any(ref not in valid_artifacts for ref in refs):
                raise ValueError("Report block references an artifact outside the Library.")
        return self


def _placement(block_id: str, page_id: str, x: int, y: int, w: int, h: int) -> dict[str, Any]:
    return {"block_id": block_id, "page_id": page_id, "x": x, "y": y, "w": w, "h": h}


def build_v2_from_legacy(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic v2 document from the existing authored shape."""
    if payload.get("schema_version") == 2:
        canonical = {key: payload[key] for key in ("schema_version", "run_id", "title", "locale", "layout_blueprint", "page_settings", "pages", "blocks", "placements", "artifact_library", "updated_at", "revision") if key in payload}
        return ReportDocumentV2.model_validate(canonical).model_dump(mode="json")
    template = ((payload.get("layout_blueprint") or {}).get("template") or "executive_briefing")
    if template not in REPORT_TEMPLATES:
        template = "executive_briefing"
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
        blocks.append({"type": "glossary", "block_id": "glossary-1", "artifact_ids": [item["artifact_id"] for item in library], "manual_note_ids": [item.get("note_id", "") for item in payload["manual_glossary_notes"]], "authored_notes": payload["manual_glossary_notes"]})
        placements.append(_placement("glossary-1", "page-1", 0, 80, 12, 6))
    document = {
        "schema_version": 2,
        "run_id": run_id,
        "title": payload.get("title") or "Custom Report",
        "locale": payload.get("locale") or "en",
        "layout_blueprint": {"template": template},
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
