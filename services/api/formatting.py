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
    """Format dates for people without inventing a midnight time component."""
    parsed = parse_date_value(value)
    if not parsed:
        return str(value)
    if parsed.time().isoformat() == "00:00:00":
        return parsed.strftime("%d-%b-%y")
    return parsed.strftime("%d-%b-%y %H:%M:%S")


def format_number(value: float | int, precision: int = 2) -> str:
    """Grouped detail value with useful, bounded decimal precision."""
    number = float(value)
    if number.is_integer():
        return f"{number:,.0f}"
    rendered = f"{number:,.{precision}f}".rstrip("0").rstrip(".")
    return rendered if rendered not in {"-0", ""} else "0"


def compact_number(value: float | int) -> str:
    number = float(value)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(number) >= threshold:
            return f"{number / threshold:.1f}{suffix}"
    return format_number(number)


def value_format_descriptor() -> dict[str, object]:
    """Safe presentation metadata; currency is intentionally absent unless trusted."""
    return {"style": "number", "precision": 2, "compact_precision": 1}


def percent(value: float) -> str:
    return f"{value:.1f}%"
