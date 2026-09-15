"""Deterministic reader-facing HTML renderer for canonical report v2."""
from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from report_chart_presentation import build_report_chart_presentation
from report_models import ReportDocumentV2


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _rich_text_markup(value: Any, *, heading_fallback: int | None = None) -> str:
    """Render the allowlisted rich-text JSON; never accept authored HTML."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, dict):
        return ""

    def inline(node: Any) -> str:
        if not isinstance(node, dict):
            return ""
        if node.get("type") == "hardBreak":
            return "<br>"
        if node.get("type") != "text":
            return ""
        rendered = _esc(node.get("text", ""))
        for mark in node.get("marks") or []:
            if not isinstance(mark, dict):
                continue
            mark_type = mark.get("type")
            if mark_type == "bold":
                rendered = f"<strong>{rendered}</strong>"
            elif mark_type == "italic":
                rendered = f"<em>{rendered}</em>"
            elif mark_type == "underline":
                rendered = f"<u>{rendered}</u>"
            elif mark_type == "fontSize":
                size = (mark.get("attrs") or {}).get("size", "base")
                if size in {"sm", "base", "lg", "xl"}:
                    rendered = f"<span class='report-rich-size-{size}'>{rendered}</span>"
        return rendered

    def node(node_value: Any) -> str:
        if not isinstance(node_value, dict):
            return ""
        node_type = node_value.get("type")
        if node_type == "hardBreak" or node_type == "text":
            return inline(node_value)
        children = "".join(node(child) for child in node_value.get("content") or [])
        attrs = node_value.get("attrs") or {}
        alignment = attrs.get("textAlign") if attrs.get("textAlign") in {"left", "center", "right"} else "left"
        if node_type == "heading":
            level = attrs.get("level") if attrs.get("level") in {1, 2, 3} else heading_fallback or 2
            return f"<h{level} style='text-align:{alignment}'>{children}</h{level}>"
        if node_type == "paragraph":
            return f"<p style='text-align:{alignment}'>{children or '<br>'}</p>"
        if node_type == "bulletList":
            return f"<ul>{children}</ul>"
        if node_type == "orderedList":
            return f"<ol>{children}</ol>"
        if node_type == "listItem":
            return f"<li>{children}</li>"
        return ""

    return "".join(node(child) for child in value.get("content") or [])


def _text_markup(block: Any) -> str:
    rendered = _rich_text_markup(getattr(block, "rich_text", None), heading_fallback=getattr(block, "level", None))
    if rendered:
        return rendered
    text = _esc(getattr(block, "text", ""))
    if block.type == "header":
        level = getattr(block, "level", 2)
        return f"<h{level}>{text}</h{level}>"
    return f"<p>{text}</p>"


def _artifact_result(artifact: Any) -> dict[str, Any] | None:
    result = artifact.get("result") if isinstance(artifact, dict) else getattr(artifact, "result", None)
    return result if isinstance(result, dict) else None


def _artifact_presentation(artifact: Any, document: ReportDocumentV2) -> dict[str, Any] | None:
    presentation = artifact.get("presentation") if isinstance(artifact, dict) else getattr(artifact, "presentation", None)
    if isinstance(presentation, dict) and presentation.get("rows"):
        return presentation
    result = _artifact_result(artifact)
    return build_report_chart_presentation(result, locale=document.locale) if result else None


def _chart_markup(artifact: Any, document: ReportDocumentV2, chart_svg: Callable[[dict[str, Any]], str]) -> str:
    presentation = _artifact_presentation(artifact, document)
    if not isinstance(presentation, dict) or not presentation.get("rows"):
        return "<p class='empty-block'>Validated artifact is unavailable.</p>"
    return chart_svg(presentation)


def _display_label(row: dict[str, Any]) -> str:
    return str(row.get("display_label") or row.get("label") or "")


def _format_value(row: dict[str, Any]) -> str:
    """Use canonical numeric formatting; exports must never reveal raw floats."""
    from formatting import format_number
    try:
        return format_number(float(row.get("value")))
    except (TypeError, ValueError):
        return "—"


def _render_table(result: dict[str, Any], title: str, visible_rows: int = 100) -> str:
    rows = [row for row in result.get("rows") or [] if isinstance(row, dict)][:visible_rows]
    dimension = str(result.get("dimension_display_name") or result.get("dimension") or "Label")
    metric = str(result.get("metric_display_name") or result.get("metric") or "Value")
    has_secondary = any(row.get("secondary_label") is not None for row in rows)
    headers = [dimension] + ([str(result.get("secondary_dimension_display_name") or result.get("secondary_dimension") or "Group")] if has_secondary else []) + [metric]
    header_markup = "".join(f"<th>{_esc(header)}</th>" for header in headers)
    body = []
    for row in rows:
        cells = [_display_label(row)]
        if has_secondary:
            cells.append(str(row.get("secondary_label") or ""))
        cells.append(_format_value(row))
        body.append("<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in cells) + "</tr>")
    return f"<table class='report-table'><caption>{_esc(title)}</caption><thead><tr>{header_markup}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _render_kpis(block: Any, artifacts: dict[str, Any]) -> str:
    items = getattr(block, "items", None) or [{"artifact_id": item} for item in getattr(block, "artifact_ids", [])]
    rendered: list[str] = []
    for item in items:
        if isinstance(item, dict):
            artifact_id = str(item.get("artifact_id", ""))
            label_override = str(item.get("label_override", ""))
        else:
            artifact_id = str(item.artifact_id)
            label_override = str(item.label_override)
        artifact = artifacts.get(artifact_id)
        result = _artifact_result(artifact) if artifact else None
        if not result:
            continue
        label = label_override or str(result.get("metric_display_name") or result.get("metric") or artifact_id)
        raw_value = result.get("scope_total_value")
        if isinstance(raw_value, (int, float)):
            from formatting import compact_number, format_number
            value, detail = compact_number(raw_value), format_number(raw_value)
        elif result.get("rows"):
            value = _format_value(result["rows"][0])
            detail = value
        else:
            value = detail = "—"
        rendered.append(f"<article class='report-kpi' title='{_esc(detail)}'><span>{_esc(label)}</span><strong>{_esc(value)}</strong></article>")
    return "<div class='report-kpis'>" + "".join(rendered) + "</div>" if rendered else "<p class='empty-block'>No validated KPI evidence is attached.</p>"


def _render_actions(block: Any) -> str:
    rows = list(getattr(block, "rows", []) or [])
    if not rows:
        return "<p class='empty-block'>No actions have been added.</p>"
    headers = (("Owner", "owner"), ("Action", "action"), ("Deadline", "deadline"), ("Status", "status"))
    body = "".join("<tr>" + "".join(f"<td>{_esc(getattr(row, key, ''))}</td>" for _, key in headers) + "</tr>" for row in rows)
    return "<table class='report-actions'><caption>Action tracker</caption><thead><tr>" + "".join(f"<th>{label}</th>" for label, _ in headers) + f"</tr></thead><tbody>{body}</tbody></table>"


def _render_glossary(block: Any, artifacts: dict[str, Any]) -> str:
    entries: list[str] = []
    seen: set[tuple[str, str]] = set()
    for artifact_id in getattr(block, "artifact_ids", []) or []:
        result = _artifact_result(artifacts.get(artifact_id))
        if not result:
            continue
        dimension = str(result.get("dimension_display_name") or result.get("dimension") or "Dimension")
        metric = str(result.get("metric_display_name") or result.get("metric") or "Metric")
        key = (dimension, metric)
        if key in seen:
            continue
        seen.add(key)
        entries.append(f"<dt>{_esc(dimension)}</dt><dd>Grouped by {_esc(dimension)}; measure: {_esc(metric)}.</dd>")
    for note in getattr(block, "authored_notes", []) or []:
        entries.append(f"<dt>Author note</dt><dd class='authored-note'>{_esc(note.text)}</dd>")
    return "<div class='report-glossary'><h3>Glossary</h3><dl>" + "".join(entries) + "</dl></div>" if entries else "<p class='empty-block'>No glossary definitions have been added.</p>"


def render_block(block: Any, document: ReportDocumentV2, artifacts: dict[str, Any], chart_svg: Callable[[dict[str, Any]], str]) -> str:
    if block.type in {"header", "text", "note"}:
        tone = f" report-note--{block.tone}" if block.type == "note" else ""
        appearance = getattr(block, "appearance", None)
        background = getattr(appearance, "background", "default")
        foreground = getattr(appearance, "foreground", "default")
        return f"<div class='report-authored report-appearance-bg-{_esc(background)} report-appearance-fg-{_esc(foreground)}{tone}'>{_text_markup(block)}</div>"
    if block.type == "divider":
        color = {"slate": "#94a3b8", "indigo": "#6366f1", "amber": "#f59e0b"}.get(block.color, "#94a3b8")
        return f"<hr class='report-divider' style='border-top-style:{_esc(block.style)};border-top-width:{int(block.thickness)}px;border-top-color:{color}'>"
    if block.type == "kpi_strip":
        return _render_kpis(block, artifacts)
    if block.type == "action_table":
        return _render_actions(block)
    if block.type == "glossary":
        return _render_glossary(block, artifacts)
    artifact = artifacts.get(block.artifact_id)
    result = _artifact_result(artifact) if artifact else None
    if not result:
        return "<p class='empty-block'>Validated artifact is unavailable.</p>"
    title = getattr(block, "title", "") or result.get("title") or block.artifact_id
    if block.type == "chart":
        return f"<h3>{_esc(title)}</h3>{_chart_markup(artifact, document, chart_svg)}{_render_table(result, f'Accessible data table for {title}', 100)}"
    return _render_table(result, str(title), getattr(block, "visible_rows", 100))


def render_report_html(document: ReportDocumentV2, chart_svg: Callable[[dict[str, Any]], str]) -> str:
    artifacts = {item.artifact_id: item for item in document.artifact_library}
    blocks = {item.block_id: item for item in document.blocks}
    pages: list[str] = []
    for page in sorted(document.pages, key=lambda item: (item.order, item.page_id)):
        page_items = [(placement, blocks[placement.block_id]) for placement in document.placements if placement.page_id == page.page_id and placement.block_id in blocks]
        page_items.sort(key=lambda value: (value[0].y, value[0].x, value[0].block_id))
        markup: list[str] = []
        for placement, block in page_items:
            body = render_block(block, document, artifacts, chart_svg)
            if body:
                # Preserve the authored grid geometry without leaking internal block/page
                # identifiers or CSS custom properties into the deliverable.
                x = max(0, min(11, int(placement.x)))
                y = max(0, int(placement.y))
                width = max(1, min(12 - x, int(placement.w)))
                height = max(1, int(placement.h))
                style = f"grid-column:{x + 1} / span {width};grid-row:{y + 1} / span {height}"
                markup.append(f"<article class='report-block report-block--{_esc(block.type)}' style='{style}'>{body}</article>")
        content = "".join(markup) or "<p class='empty-page'>No authored blocks on this page.</p>"
        pages.append(f"<section class='report-page'><h2 class='page-title'>{_esc(page.title)}</h2><div class='report-grid'>{content}</div></section>")

    title = _esc(document.title)
    template = """<!doctype html><html lang='__LOCALE__'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>__TITLE__</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#eef2f7;color:#172033;font:15px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1180px;margin:auto;padding:32px 36px}h1{margin:0 0 24px;color:#172554;font-size:32px;line-height:1.15}.report-page{margin:0 0 28px;padding:24px;background:#f8fafc;border:1px solid #dbe3ef;border-radius:16px;break-after:page}.report-page:last-child{break-after:auto}.page-title{margin:0 0 14px;color:#475569;font-size:13px;text-transform:uppercase;letter-spacing:.08em}.report-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));grid-auto-rows:24px;gap:16px;align-items:stretch}.report-block{min-width:0;overflow:visible;padding:18px;background:#fff;border:1px solid #dbe3ef;border-radius:14px;box-shadow:0 1px 3px rgb(15 23 42 / .05);break-inside:avoid}.report-block--chart{min-height:360px}.report-block--divider{padding-block:6px}.report-block--data_table{overflow:auto}.report-authored h1,.report-authored h2,.report-authored h3{margin:0 0 8px;color:#172554}.report-authored h1{font-size:27px}.report-authored h2{font-size:22px}.report-authored h3{font-size:17px}.report-authored p{margin:0 0 8px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6;color:#475569}.report-authored ul,.report-authored ol{margin:5px 0 8px;padding-left:22px;color:#475569}.report-note--neutral{background:#fff}.report-appearance-bg-indigo-pastel{background:#e0e7ff}.report-appearance-bg-violet-pastel{background:#ede9fe}.report-appearance-bg-teal-pastel{background:#ccfbf1}.report-appearance-bg-amber-pastel{background:#fef3c7}.report-appearance-bg-rose-pastel{background:#ffe4e6}.report-appearance-fg-indigo-strong,.report-appearance-fg-indigo-strong *{color:#3730a3!important}.report-appearance-fg-violet-strong,.report-appearance-fg-violet-strong *{color:#5b21b6!important}.report-appearance-fg-teal-strong,.report-appearance-fg-teal-strong *{color:#115e59!important}.report-appearance-fg-amber-strong,.report-appearance-fg-amber-strong *{color:#92400e!important}.report-appearance-fg-rose-strong,.report-appearance-fg-rose-strong *{color:#9f1239!important}.report-note--info{padding-left:14px;border-left:4px solid #2563eb}.report-note--warning{padding:12px 14px;background:#fffbeb;border-radius:8px;border-left:4px solid #f59e0b}.report-note--success{padding:12px 14px;background:#ecfdf5;border-radius:8px;border-left:4px solid #10b981}.report-rich-size-sm{font-size:11px}.report-rich-size-base{font-size:15px}.report-rich-size-lg{font-size:18px}.report-rich-size-xl{font-size:22px}.report-divider{display:block;width:100%;margin:12px 0}.report-chart{display:block;width:100%;height:auto;max-width:100%;margin:8px 0}.report-table{width:100%;border-collapse:collapse;margin-top:12px;font-size:12px}.report-table th,.report-table td,.report-actions th,.report-actions td{padding:8px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top;overflow-wrap:anywhere}.report-table th,.report-actions th{color:#475569;background:#f8fafc}.report-table caption,.report-actions caption{padding-bottom:8px;text-align:left;font-weight:700}.report-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.report-kpi{display:grid;gap:5px;padding:12px;border-radius:10px;background:#eef2ff;color:#3730a3}.report-kpi span{font-size:11px}.report-kpi strong{font-size:20px}.report-kpi small{color:#64748b;font-size:10px}.report-actions{border-collapse:collapse;width:100%;font-size:12px}.report-glossary h3{margin:0 0 8px;color:#172554}.report-glossary dl{margin:0}.report-glossary dt{margin-top:8px;color:#334155;font-weight:700}.report-glossary dd{margin:2px 0;color:#475569}.authored-note{color:#6d28d9}.empty-block,.empty-page{color:#64748b}.report-block--data_table{overflow:auto}@media(max-width:720px){main{padding:20px 12px}.report-page{padding:14px}.report-grid{display:block}.report-block{margin:12px 0;min-height:0!important;overflow:visible}.report-chart{min-width:0}.report-table{font-size:11px}}@media print{body{background:#fff}main{max-width:none;padding:0}.report-page{margin:0;padding:0;border:0;border-radius:0;background:#fff}.report-block{box-shadow:none;border-color:#dbe3ef;break-inside:avoid}.report-grid{gap:10px}.report-block--chart{min-height:0}.report-chart{page-break-inside:avoid}}
</style></head><body><main><h1>__TITLE__</h1>__PAGES__</main></body></html>"""
    return template.replace("__LOCALE__", _esc(document.locale)).replace("__TITLE__", title).replace("__PAGES__", "".join(pages))
