"""Self-contained SVG renderer for the canonical report chart presentation."""
from __future__ import annotations

import hashlib
import html
import json
import math
from typing import Any

COLORS = ("#4f46e5", "#0f766e", "#c2410c", "#be185d", "#0284c7", "#65a30d", "#9333ea", "#ea580c", "#475569", "#db2777")
PRIMARY = COLORS[0]


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _number(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _row_label(row: dict[str, Any]) -> str:
    return str(row.get("displayLabel") or row.get("display_label") or row.get("label") or "")


def _row_value(row: dict[str, Any], key: str = "value") -> float:
    return _number(row.get(key))


def _row_format(row: dict[str, Any], key: str = "formattedValue") -> str:
    snake_key = "formatted_value" if key == "formattedValue" else "secondary_formatted_value"
    return str(row.get(key) if row.get(key) is not None else row.get(snake_key, row.get("value", "")))


def _domain(spec: dict[str, Any], values: list[float]) -> tuple[float, float]:
    candidate = spec.get("domain")
    if isinstance(candidate, (list, tuple)) and len(candidate) == 2:
        minimum, maximum = _number(candidate[0]), _number(candidate[1])
    else:
        minimum, maximum = min([0.0, *values]) if values else 0.0, max([0.0, *values]) if values else 1.0
    if maximum <= minimum:
        maximum = minimum + 1.0
    return minimum, maximum


def _ticks(spec: dict[str, Any], minimum: float, maximum: float) -> list[tuple[float, str]]:
    source = spec.get("ticks")
    if isinstance(source, list):
        values: list[tuple[float, str]] = []
        for tick in source:
            if not isinstance(tick, dict):
                continue
            value = _number(tick.get("value"))
            if minimum - 1e-9 <= value <= maximum + 1e-9:
                values.append((value, str(tick.get("label", value))))
        if values:
            return values
    count = 5
    step = (maximum - minimum) / (count - 1)
    return [(minimum + step * index, str(round(minimum + step * index, 2))) for index in range(count)]


def _visual_label(label: str, maximum: int = 28) -> str:
    if len(label) <= maximum:
        return label
    return label[: max(1, maximum - 1)].rstrip() + "…"


def _color(spec: dict[str, Any], index: int, row: dict[str, Any]) -> str:
    mode = spec.get("paletteMode") or spec.get("palette_mode")
    if mode == "single-series":
        return PRIMARY
    group = row.get("secondaryLabel") or row.get("secondary_label")
    if group and mode == "grouped":
        groups = spec.get("groups")
        if not isinstance(groups, list):
            groups = []
        if group not in groups:
            groups = [*groups, group]
        return COLORS[groups.index(group) % len(COLORS)]
    return COLORS[index % len(COLORS)]


def _chart_id(spec: dict[str, Any]) -> str:
    encoded = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:10]


def _empty_svg(spec: dict[str, Any]) -> str:
    width, height = 760, 180
    title = _esc(spec.get("title", "Validated chart"))
    chart_id = _chart_id(spec)
    return (f"<svg class='report-chart' viewBox='0 0 {width} {height}' role='img' aria-labelledby='chart-title-{chart_id} chart-desc-{chart_id}' xmlns='http://www.w3.org/2000/svg'>"
            f"<title id='chart-title-{chart_id}'>{title}</title><desc id='chart-desc-{chart_id}'>No validated chart values are available.</desc>"
            f"<rect width='{width}' height='{height}' rx='10' fill='#f8fafc'/><text x='{width / 2}' y='{height / 2}' text-anchor='middle' fill='#64748b'>No validated chart values are available.</text></svg>")


def render_report_chart_svg(presentation: dict[str, Any]) -> str:
    """Render one presentation spec without re-querying or guessing its data."""
    spec = presentation if isinstance(presentation, dict) else {}
    rows = [row for row in spec.get("rows") or [] if isinstance(row, dict)]
    # All dimensions/values have already been bounded by the report schema and
    # presentation builder; this renderer never takes arbitrary SVG attributes
    # from authored content.
    if not rows:
        return _empty_svg(spec)
    title = str(spec.get("title") or "Validated chart")
    chart_type = str(spec.get("chartType") or spec.get("chart_type") or "bar")
    orientation = str(spec.get("orientation") or "vertical")
    metric_label = str(spec.get("metricLabel") or spec.get("metric_display_name") or "Value")
    dimension_label = str(spec.get("dimensionLabel") or spec.get("dimension_display_name") or "Category")
    values = [_row_value(row) for row in rows]
    minimum, maximum = _domain(spec, values)
    ticks = _ticks(spec, minimum, maximum)
    chart_id = _chart_id(spec)
    description = "; ".join(f"{_row_label(row)}: {_row_format(row)}" for row in rows)
    width = 760

    if orientation == "horizontal" and chart_type in {"bar", "pareto", "stacked_bar"}:
        row_height = 34 if len(rows) <= 10 else 29
        top, bottom, left, right = 42, 24, 224, 104
        height = max(190, top + row_height * len(rows) + bottom)
        plot_width = width - left - right
        span = maximum - minimum
        baseline = left + (0 - minimum) / span * plot_width
        svg = [f"<svg class='report-chart report-chart-horizontal' viewBox='0 0 {width} {height}' preserveAspectRatio='xMidYMid meet' role='img' aria-labelledby='chart-title-{chart_id} chart-desc-{chart_id}' xmlns='http://www.w3.org/2000/svg'>",
               f"<title id='chart-title-{chart_id}'>{_esc(title)}</title><desc id='chart-desc-{chart_id}'>{_esc(metric_label)} by {_esc(dimension_label)}. {_esc(description)}</desc>",
               f"<rect width='{width}' height='{height}' rx='10' fill='#f8fafc'/>"]
        for tick_value, tick_label in ticks:
            x = left + (tick_value - minimum) / span * plot_width
            svg.append(f"<path d='M {x:.1f} {top} V {height - bottom}' stroke='#e2e8f0'/><text x='{x:.1f}' y='{height - 7}' text-anchor='middle' font-size='11' fill='#64748b'>{_esc(tick_label)}</text>")
        for index, row in enumerate(rows):
            value = _row_value(row)
            y = top + index * row_height + row_height / 2
            endpoint = left + (value - minimum) / span * plot_width
            x = min(baseline, endpoint)
            bar_width = abs(endpoint - baseline)
            color = _color(spec, index, row)
            label = _visual_label(_row_label(row))
            svg.append(f"<text x='{left - 9}' y='{y + 4:.1f}' text-anchor='end' font-size='11' fill='#334155'><title>{_esc(_row_label(row))}</title>{_esc(label)}</text>")
            svg.append(f"<rect x='{x:.1f}' y='{y - row_height * .30:.1f}' width='{max(1, bar_width):.1f}' height='{row_height * .60:.1f}' rx='3' fill='{color}'><title>{_esc(_row_label(row))}: {_esc(_row_format(row))}</title></rect>")
            value_x = min(width - 5, max(left + 4, endpoint + 7))
            anchor = "end" if endpoint > width - right - 34 else "start"
            if anchor == "end":
                value_x = endpoint - 6
            svg.append(f"<text x='{value_x:.1f}' y='{y + 4:.1f}' text-anchor='{anchor}' font-size='11' font-weight='600' fill='#334155'>{_esc(_row_format(row))}</text>")
        svg.append("</svg>")
        return "".join(svg)

    top, bottom, left, right = 38, 70, 64, 30
    height = 360
    plot_width, plot_height = width - left - right, height - top - bottom
    span = maximum - minimum
    svg = [f"<svg class='report-chart' viewBox='0 0 {width} {height}' preserveAspectRatio='xMidYMid meet' role='img' aria-labelledby='chart-title-{chart_id} chart-desc-{chart_id}' xmlns='http://www.w3.org/2000/svg'>",
           f"<title id='chart-title-{chart_id}'>{_esc(title)}</title><desc id='chart-desc-{chart_id}'>{_esc(metric_label)} by {_esc(dimension_label)}. {_esc(description)}</desc>",
           f"<rect width='{width}' height='{height}' rx='10' fill='#f8fafc'/>"]
    for tick_value, tick_label in ticks:
        y = top + (maximum - tick_value) / span * plot_height
        svg.append(f"<path d='M {left} {y:.1f} H {width - right}' stroke='#e2e8f0'/><text x='{left - 8}' y='{y + 4:.1f}' text-anchor='end' font-size='11' fill='#64748b'>{_esc(tick_label)}</text>")

    if chart_type in {"pie", "donut"}:
        positive = [max(0.0, value) for value in values]
        total = sum(positive)
        center_x, center_y, radius = 235, 174, 118
        if total <= 0:
            svg.append(f"<text x='{center_x}' y='{center_y}' text-anchor='middle' fill='#64748b'>No positive values to chart.</text>")
        else:
            angle = -math.pi / 2
            for index, (row, value) in enumerate(zip(rows, positive)):
                sweep = value / total * math.tau
                end = angle + sweep
                x1, y1 = center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)
                x2, y2 = center_x + radius * math.cos(end), center_y + radius * math.sin(end)
                large = 1 if sweep > math.pi else 0
                path = f"M {center_x:.1f} {center_y:.1f} L {x1:.1f} {y1:.1f} A {radius:.1f} {radius:.1f} 0 {large} 1 {x2:.1f} {y2:.1f} Z"
                color = _color(spec, index, row)
                svg.append(f"<path d='{path}' fill='{color}'><title>{_esc(_row_label(row))}: {_esc(_row_format(row))}</title></path>")
                angle = end
            if chart_type == "donut":
                svg.append(f"<circle cx='{center_x}' cy='{center_y}' r='{radius * .52:.1f}' fill='#f8fafc'/><text x='{center_x}' y='{center_y + 5}' text-anchor='middle' font-weight='700' font-size='16'>{_esc(str(spec.get('totalFormattedValue') or spec.get('total_formatted_value') or total))}</text>")
        legend_x, legend_y = 430, 66
        for index, row in enumerate(rows):
            y = legend_y + index * 24
            if y > height - 20:
                break
            svg.append(f"<rect x='{legend_x}' y='{y - 11}' width='12' height='12' rx='2' fill='{_color(spec, index, row)}'/><text x='{legend_x + 18}' y='{y}' font-size='11' fill='#334155'><title>{_esc(_row_label(row))}</title>{_esc(_visual_label(_row_label(row), 30))}: {_esc(_row_format(row))}</text>")
    elif chart_type == "scatter":
        x_values = [_row_value(row, "xValue") if row.get("xValue") is not None else _row_value(row, "x_value") for row in rows]
        x_min, x_max = min(x_values), max(x_values)
        x_span = max(1.0, x_max - x_min)
        y_span = span
        svg.append(f"<path d='M {left} {top} V {height - bottom} H {width - right}' stroke='#94a3b8' fill='none'/>")
        for index, (row, x_value, value) in enumerate(zip(rows, x_values, values)):
            x = left + (x_value - x_min) / x_span * plot_width
            y = top + (maximum - value) / y_span * plot_height
            svg.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='5' fill='{_color(spec, index, row)}'><title>{_esc(_row_label(row))}: {_esc(_row_format(row))}</title></circle>")
    elif chart_type == "combo":
        secondary_values = [_row_value(row, "secondaryValue") if row.get("secondaryValue") is not None else _row_value(row, "secondary_value") for row in rows]
        secondary_min, secondary_max = min([0.0, *secondary_values]), max([0.0, *secondary_values])
        if secondary_max <= secondary_min:
            secondary_max = secondary_min + 1
        secondary_span = secondary_max - secondary_min
        step = plot_width / max(1, len(rows))
        points: list[str] = []
        baseline = top + (maximum / span) * plot_height
        for index, (row, value, secondary_value) in enumerate(zip(rows, values, secondary_values)):
            x = left + step * (index + .5)
            y = top + (maximum - value) / span * plot_height
            line_y = top + (secondary_max - secondary_value) / secondary_span * plot_height
            points.append(f"{x:.1f},{line_y:.1f}")
            svg.append(f"<rect x='{x - step * .32:.1f}' y='{min(y, baseline):.1f}' width='{max(3, step * .64):.1f}' height='{max(1, abs(baseline - y)):.1f}' rx='2' fill='{PRIMARY}'><title>{_esc(_row_label(row))}: {_esc(_row_format(row))}</title></rect><text x='{x:.1f}' y='{height - bottom + 18}' text-anchor='middle' font-size='10'><title>{_esc(_row_label(row))}</title>{_esc(_visual_label(_row_label(row), 14))}</text>")
        svg.append(f"<polyline points='{' '.join(points)}' fill='none' stroke='#0f766e' stroke-width='3'/>")
        for row, point in zip(rows, points):
            x, y = point.split(',')
            secondary_format = _row_format(row, "secondaryFormattedValue")
            svg.append(f"<circle cx='{x}' cy='{y}' r='4' fill='#0f766e'><title>{_esc(_row_label(row))}: {_esc(secondary_format)}</title></circle>")
    else:
        step = plot_width / max(1, len(rows))
        baseline = top + (maximum / span) * plot_height
        vertical_points: list[tuple[float, float]] = []
        for index, (row, value) in enumerate(zip(rows, values)):
            x = left + step * (index + .5)
            y = top + (maximum - value) / span * plot_height
            vertical_points.append((x, y))
            if chart_type == "bar":
                bar_y, bar_height = min(y, baseline), abs(baseline - y)
                svg.append(f"<rect x='{x - step * .34:.1f}' y='{bar_y:.1f}' width='{max(3, step * .68):.1f}' height='{max(1, bar_height):.1f}' rx='2' fill='{_color(spec, index, row)}'><title>{_esc(_row_label(row))}: {_esc(_row_format(row))}</title></rect>")
            svg.append(f"<text x='{x:.1f}' y='{height - bottom + 18}' text-anchor='middle' font-size='10'><title>{_esc(_row_label(row))}</title>{_esc(_visual_label(_row_label(row), 14))}</text>")
        if chart_type in {"line", "area"} and vertical_points:
            point_string = " ".join(f"{x:.1f},{y:.1f}" for x, y in vertical_points)
            if chart_type == "area":
                svg.append(f"<path d='M {vertical_points[0][0]:.1f},{baseline:.1f} L {point_string} L {vertical_points[-1][0]:.1f},{baseline:.1f} Z' fill='#a5b4fc' opacity='.55'/>")
            svg.append(f"<polyline points='{point_string}' fill='none' stroke='{PRIMARY}' stroke-width='3'/>")
            for row, (x, y) in zip(rows, vertical_points):
                svg.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{PRIMARY}'><title>{_esc(_row_label(row))}: {_esc(_row_format(row))}</title></circle>")
    svg.append("</svg>")
    return "".join(svg)
