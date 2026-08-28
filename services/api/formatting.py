"""Deterministic display formatting for OpenData analytical artifacts."""
from __future__ import annotations

from datetime import datetime

DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


def parse_date_value(value: str) -> datetime | None:
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def format_display_date(value: str) -> str:
    parsed = parse_date_value(value)
    return parsed.strftime("%d-%b-%y") if parsed else str(value)


def compact_number(value: float | int) -> str:
    number = float(value)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(number) >= threshold:
            return f"{number / threshold:.1f}{suffix}"
    return f"{number:.1f}"


def percent(value: float) -> str:
    return f"{value:.1f}%"
