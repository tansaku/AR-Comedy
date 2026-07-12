#!/usr/bin/env python3
"""Shared Numbers row styling for outreach status."""

from __future__ import annotations

from numbers_parser import Document
from numbers_parser.cell import RGB, Style

SENT_BG = (255, 240, 86)
SKIP_BG = (254, 174, 0)

StatusRGB = tuple[int, int, int]


def rgb_matches(bg, target: StatusRGB) -> bool:
    return (bg.r, bg.g, bg.b) == target


def row_status_from_name_cell(table, row: int, name_col: int = 1) -> str:
    """Return sent | skip | pending based on the name cell background."""
    cell = table.cell(row, name_col)
    style = cell.style
    if not style or not getattr(style, "bg_color", None):
        return "pending"
    bg = style.bg_color
    if rgb_matches(bg, SENT_BG):
        return "sent"
    if rgb_matches(bg, SKIP_BG):
        return "skip"
    return "pending"


def style_entire_row(table, row: int, bg: StatusRGB) -> None:
    """Apply one background colour across every column in a row."""
    row_style = Style(bg_color=RGB(*bg))
    for col in range(table.num_cols):
        table.set_cell_style(row, col, row_style)


def mark_row_sent(doc: Document, table, row: int) -> None:
    style_entire_row(table, row, SENT_BG)


def mark_row_skip(doc: Document, table, row: int) -> None:
    style_entire_row(table, row, SKIP_BG)
