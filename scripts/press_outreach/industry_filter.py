#!/usr/bin/env python3
"""Filter industry contacts by Edinburgh show dates and related rules."""

from __future__ import annotations

from datetime import date, datetime

SHOW_START = date(2026, 8, 20)
SHOW_END = date(2026, 8, 30)


def parse_numbers_date(value: str | float | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def overlaps_show_dates(
    in_town_start: date | None,
    in_town_end: date | None,
    *,
    show_start: date = SHOW_START,
    show_end: date = SHOW_END,
) -> bool:
    """True when the contact's in-town window overlaps the show run."""
    if not in_town_start and not in_town_end:
        return False
    start = in_town_start or in_town_end
    end = in_town_end or in_town_start
    if start is None or end is None:
        return False
    if start > end:
        start, end = end, start
    return start <= show_end and end >= show_start
