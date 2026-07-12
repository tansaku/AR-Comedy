#!/usr/bin/env python3
"""Read/write AI outreach columns on industry Numbers exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from numbers_parser import Document

DRAFT_HEADER = "Outreach draft"
FIT_HEADER = "AI fit"
PRIORITY_HEADER = "Priority"


@dataclass(frozen=True)
class OutreachColumns:
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
        draft=_header_col(table, DRAFT_HEADER),
        fit=_header_col(table, FIT_HEADER),
        priority=_header_col(table, PRIORITY_HEADER),
    )


def ensure_outreach_columns(
    table,
    *,
    save_path: Path | None = None,
    doc: Document | None = None,
) -> OutreachColumns:
    """Append Outreach draft / AI fit / Priority columns if missing."""
    cols = read_outreach_columns(table)
    if cols.draft is not None:
        return cols

    start = table.num_cols
    table.add_column(3)
    table.write(0, start, DRAFT_HEADER)
    table.write(0, start + 1, FIT_HEADER)
    table.write(0, start + 2, PRIORITY_HEADER)
    cols = OutreachColumns(draft=start, fit=start + 1, priority=start + 2)
    if save_path and doc:
        doc.save(str(save_path))
    return cols


def write_outreach_plan(
    table,
    row: int,
    cols: OutreachColumns,
    *,
    draft: str,
    ai_fit: str,
    priority: str = "",
) -> None:
    if cols.draft is not None:
        table.write(row, cols.draft, draft)
    if cols.fit is not None:
        table.write(row, cols.fit, ai_fit)
    if cols.priority is not None and priority:
        table.write(row, cols.priority, priority)
