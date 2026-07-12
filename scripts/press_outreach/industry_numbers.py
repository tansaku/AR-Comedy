#!/usr/bin/env python3
"""Read/write AI outreach columns on industry Numbers exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from numbers_parser import Document

SUBJECT_HEADER = "Email subject"
DRAFT_HEADER = "Outreach draft"
FIT_HEADER = "AI fit"
PRIORITY_HEADER = "Priority"


@dataclass(frozen=True)
class OutreachColumns:
    subject: int | None
    draft: int | None
    fit: int | None
    priority: int | None


def _header_col(table, header: str) -> int | None:
    for col in range(table.num_cols):
        if table.cell(0, col).value == header:
            return col
    return None


def read_outreach_columns(table) -> OutreachColumns:
    return OutreachColumns(
        subject=_header_col(table, SUBJECT_HEADER),
        draft=_header_col(table, DRAFT_HEADER),
        fit=_header_col(table, FIT_HEADER),
        priority=_header_col(table, PRIORITY_HEADER),
    )


def _append_columns(table, count: int) -> int:
    start = table.num_cols
    table.add_column(count)
    return start


def ensure_outreach_columns(
    table,
    *,
    save_path: Path | None = None,
    doc: Document | None = None,
) -> OutreachColumns:
    """Append outreach columns if missing (supports legacy 3-col and full 4-col layouts)."""
    cols = read_outreach_columns(table)
    if cols.subject is not None and cols.draft is not None:
        return cols

    if cols.draft is None:
        start = _append_columns(table, 4)
        table.write(0, start, SUBJECT_HEADER)
        table.write(0, start + 1, DRAFT_HEADER)
        table.write(0, start + 2, FIT_HEADER)
        table.write(0, start + 3, PRIORITY_HEADER)
        cols = OutreachColumns(
            subject=start, draft=start + 1, fit=start + 2, priority=start + 3
        )
    elif cols.subject is None:
        start = _append_columns(table, 1)
        table.write(0, start, SUBJECT_HEADER)
        cols = OutreachColumns(
            subject=start,
            draft=cols.draft,
            fit=cols.fit,
            priority=cols.priority,
        )

    if save_path and doc:
        doc.save(str(save_path))
    return cols


def write_outreach_plan(
    table,
    row: int,
    cols: OutreachColumns,
    *,
    subject: str = "",
    draft: str,
    ai_fit: str,
    priority: str = "",
) -> None:
    if cols.subject is not None and subject:
        table.write(row, cols.subject, subject)
    if cols.draft is not None:
        table.write(row, cols.draft, draft)
    if cols.fit is not None:
        table.write(row, cols.fit, ai_fit)
    if cols.priority is not None and priority:
        table.write(row, cols.priority, priority)
