"""Deterministic reader-facing HTML renderer for canonical report v2."""
from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from report_models import ReportDocumentV2


def render_report_html(document: ReportDocumentV2, chart_svg: Callable[[dict[str, Any]], str]) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    artifacts = {item.artifact_id: item for item in document.artifact_library}
    blocks = {item.block_id: item for item in document.blocks}
    pages: list[str] = []
    for page in sorted(document.pages, key=lambda item: (item.order, item.page_id)):
        page_items = [
            (placement, blocks[placement.block_id])
            for placement in document.placements
            if placement.page_id == page.page_id and placement.block_id in blocks
        ]
        page_items.sort(key=lambda value: (value[0].y, value[0].x, value[0].block_id))
        markup: list[str] = []
        for placement, block in page_items:
            body = render_block(block, artifacts, chart_svg, esc)
            if not body:
                continue
            markup.append(
                f"<article class='report-block report-block--{esc(block.type)}' data-block-id='{esc(block.block_id)}' "
                f"style='--x:{placement.x};--y:{placement.y};--w:{placement.w};--h:{placement.h}'>"
                f"{body}</article>"
            )
        content = "".join(markup) or "<p class='empty-page'>No authored blocks on this page.</p>"
        pages.append(
            f"<section class='report-page' data-page-id='{esc(page.page_id)}'>"
            f"<h2 class='page-title'>{esc(page.title)}</h2><div class='report-grid'>{content}</div></section>"
        )

    template = """<!doctype html><html lang='__LOCALE__'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>__TITLE__</title><style>
body{margin:0;background:#eef2f7;color:#172033;font:15px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1180px;margin:auto;padding:36px}h1{margin:0;color:#172554;font-size:32px}.report-intro{margin:8px 0 24px;color:#64748b}.report-page{margin:0 0 28px;padding:24px;background:#f8fafc;border:1px solid #dbe3ef;border-radius:16px;break-after:page}.report-page:last-child{break-after:auto}.page-title{margin:0 0 14px;color:#475569;font-size:13px;text-transform:uppercase;letter-spacing:.08em}.report-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));grid-auto-rows:24px;gap:16px;align-items:stretch}.report-block{grid-column:calc(var(--x) + 1) / span var(--w);grid-row:calc(var(--y) + 1) / span var(--h);min-width:0;overflow:hidden;padding:18px;background:#fff;border:1px solid #dbe3ef;border-radius:14px;box-shadow:0 1px 3px rgb(15 23 42 / .05);break-inside:avoid}.report-block--header h3{margin:0;color:#172554;font-size:23px}.report-block--text p,.report-block--note p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6;color:#475569}.report-block--note{background:#fffbeb;border-color:#fde68a}.report-block--divider{padding:0;background:transparent;border:0;border-top:1px solid #cbd5e1;border-radius:0;box-shadow:none}.report-block--chart,.report-block--data_table{overflow:visible;min-height:260px}.report-chart{display:block;width:100%;height:auto;max-height:100%;margin-top:8px}.report-table{width:100%;border-collapse:collapse;margin-top:10px;font-size:12px}.report-table th,.report-table td{padding:8px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top}.report-table th{color:#475569;background:#f8fafc}.report-table caption{padding-bottom:8px;text-align:left;font-weight:700}.report-kpis{display:flex;flex-wrap:wrap;gap:10px}.report-kpi{padding:10px 12px;border-radius:10px;background:#eef2ff;color:#3730a3;font-weight:700;font-size:12px}.report-actions{border-collapse:collapse;width:100%;font-size:12px}.report-actions td,.report-actions th{padding:8px;border-bottom:1px solid #e2e8f0;text-align:left}.report-glossary{margin:0;padding-left:20px;line-height:1.6}.empty-page{color:#64748b}@media print{body{background:#fff}main{max-width:none;padding:0}.report-page{padding:0;border:0;background:#fff}}
</style></head><body><main><h1>__TITLE__</h1><p class='report-intro'>Authored report · __LOCALE__</p>__PAGES__</main></body></html>"""
    return (
        template.replace("__LOCALE__", esc(document.locale))
        .replace("__TITLE__", esc(document.title))
        .replace("__PAGES__", "".join(pages))
    )


def render_block(block: Any, artifacts: dict[str, Any], chart_svg: Callable[[dict[str, Any]], str], esc: Callable[[Any], str]) -> str:
    if block.type == "header":
        return f"<h{block.level}>{esc(block.text)}</h{block.level}>"
    if block.type == "text":
        return f"<p>{esc(block.text)}</p>"
    if block.type == "note":
        return f"<p>{esc(block.text)}</p>"
    if block.type == "divider":
        return ""
    if block.type == "kpi_strip":
        labels = [str(artifacts[item].result.get("title", item)) for item in block.artifact_ids if item in artifacts and artifact_result(artifacts[item])]
        return "<div class='report-kpis'>" + "".join(f"<span class='report-kpi'>{esc(label)}</span>" for label in labels) + "</div>" if labels else ""
    if block.type == "action_table":
        if not block.rows:
            return ""
        headers = ["owner", "action", "deadline", "status"]
        rows = "".join("<tr>" + "".join(f"<td>{esc(row.get(header, ''))}</td>" for header in headers) + "</tr>" for row in block.rows)
        return "<table class='report-actions'><thead><tr>" + "".join(f"<th>{header.title()}</th>" for header in headers) + f"</tr></thead><tbody>{rows}</tbody></table>"
    if block.type == "glossary":
        labels = []
        for artifact_id in block.artifact_ids:
            artifact = artifacts.get(artifact_id)
            result = artifact_result(artifact) if artifact else None
            if result:
                labels.append(f"{result.get('dimension', artifact_id)} — {result.get('metric', '')}")
        return "<ul class='report-glossary'>" + "".join(f"<li>{esc(label)}</li>" for label in labels) + "</ul>" if labels else ""
    artifact = artifacts.get(block.artifact_id)
    result = artifact_result(artifact) if artifact else None
    if not result:
        return ""
    title = block.title or result.get("title") or block.artifact_id
    if block.type == "chart":
        return f"<h3>{esc(title)}</h3>{chart_svg(result)}"
    rows = result.get("rows") or []
    body = "".join(
        f"<tr><td>{esc(row.get('display_label') or row.get('label', ''))}</td><td>{esc(row.get('formatted_value', row.get('value', '')))}</td></tr>"
        for row in rows[:100]
        if isinstance(row, dict)
    )
    return f"<table class='report-table'><caption>{esc(title)}</caption><thead><tr><th>Label</th><th>Value</th></tr></thead><tbody>{body}</tbody></table>"


def artifact_result(artifact: Any) -> dict[str, Any] | None:
    result = getattr(artifact, "result", None)
    return result if isinstance(result, dict) else None
