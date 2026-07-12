#!/usr/bin/env python3
"""Parse industry outreach rows from exported Airtable Numbers files."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from numbers_parser import Document

from industry_numbers import OutreachColumns, ensure_outreach_columns, read_outreach_columns
from industry_filter import overlaps_show_dates, parse_numbers_date
from numbers_style import row_status_from_name_cell

Status = Literal["sent", "skip", "pending"]

REPO_ROOT = Path(__file__).resolve().parents[2]

PROGRAMMER_COLUMNS = {
    "name": 1,
    "job_title": 2,
    "organisation": 3,
    "country": 4,
    "city": 5,
    "email": 7,
    "website": 8,
    "about": 9,
    "role_type": 10,
    "programme_from_festival": 11,
    "work_scale": 12,
    "target_audiences": 13,
    "work_to_avoid": 14,
    "attend_mode": 15,
    "in_town_start": 16,
    "in_town_end": 17,
    "interested_comedy": 25,
    "comedy_genres": 26,
}

AGENT_COLUMNS = {
    "name": 1,
    "job_title": 2,
    "organisation": 3,
    "city": 4,
    "email": 6,
    "website": 7,
    "about": 8,
    "target_audiences": 9,
    "work_to_avoid": 10,
    "role_type": 11,
    "seeking_talent": 12,
    "attend_mode": 13,
    "in_town_start": 14,
    "in_town_end": 15,
    "interested_comedy": 22,
    "comedy_genres": 23,
}


def first_name_from(full_name: str) -> str:
    name = (full_name or "").strip()
    if not name:
        return "there"
    if "(" in name:
        name = name.split("(", 1)[0].strip()
    return name.split()[0]


def _cell_str(table, row: int, col: int) -> str:
    value = table.cell(row, col).value
    if value is None:
        return ""
    return str(value).strip()


def _cell_checked(table, row: int, col: int) -> bool:
    value = table.cell(row, col).value
    return str(value or "").lower() in {"checked", "true", "yes", "1"}


@dataclass(frozen=True)
class IndustryContact:
    row: int
    name: str
    email: str
    organisation: str
    job_title: str
    country: str
    city: str
    website: str
    about: str
    role_type: str
    attend_mode: str
    in_town_start: date | None
    in_town_end: date | None
    interested_comedy: bool
    comedy_genres: str
    programme_from_festival: str
    work_scale: str
    target_audiences: str
    work_to_avoid: str
    status: Status
    first_name: str
    draft: str = ""
    ai_fit: str = ""
    priority: str = ""
    in_town_overlap: bool = False
    extra_fields: dict[str, str] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """Eligible for AI draft generation (in town, comedy interest, not done)."""
        return (
            self.status == "pending"
            and bool(self.email)
            and self.in_town_overlap
            and (self.interested_comedy or "comedy" in self.comedy_genres.lower())
            and not self.ai_fit.startswith("SKIP:")
        )

    @property
    def ready_to_review(self) -> bool:
        """Has a draft ready for human review in the compose loop."""
        return (
            self.status == "pending"
            and bool(self.email)
            and bool(self.draft.strip())
            and not self.ai_fit.startswith("SKIP:")
        )

    def profile_text(self) -> str:
        lines = [
            f"Name: {self.name}",
            f"Job title: {self.job_title}",
            f"Organisation: {self.organisation}",
            f"Based: {self.city}, {self.country}".strip(", "),
            f"Website: {self.website}",
            f"Role type: {self.role_type}",
            f"Attending Fringe: {self.attend_mode}",
        ]
        if self.in_town_start and self.in_town_end:
            lines.append(f"In town: {self.in_town_start} – {self.in_town_end}")
        lines.extend(
            [
                f"About: {self.about}",
                f"Programmes from festival: {self.programme_from_festival}",
                f"Work scale sought: {self.work_scale}",
                f"Target audiences: {self.target_audiences}",
                f"Work to avoid: {self.work_to_avoid}",
                f"Interested in comedy: {'yes' if self.interested_comedy else 'no'}",
                f"Comedy genres: {self.comedy_genres}",
            ]
        )
        for key, value in self.extra_fields.items():
            if value:
                lines.append(f"{key}: {value}")
        return "\n".join(line for line in lines if line.split(": ", 1)[-1])


def _optional_cell(table, row: int, columns: dict[str, int], key: str) -> str:
    if key not in columns:
        return ""
    return _cell_str(table, row, columns[key])


def _load_row(
    table,
    row: int,
    columns: dict[str, int],
    outreach_cols: OutreachColumns,
) -> IndustryContact:
    in_start = parse_numbers_date(_cell_str(table, row, columns["in_town_start"]))
    in_end = parse_numbers_date(_cell_str(table, row, columns["in_town_end"]))
    country_col = columns.get("country")
    country = _cell_str(table, row, country_col) if country_col is not None else ""

    draft = ""
    ai_fit = ""
    priority = ""
    if outreach_cols.draft is not None:
        draft = _cell_str(table, row, outreach_cols.draft)
    if outreach_cols.fit is not None:
        ai_fit = _cell_str(table, row, outreach_cols.fit)
    if outreach_cols.priority is not None:
        priority = _cell_str(table, row, outreach_cols.priority)

    return IndustryContact(
        row=row,
        name=_cell_str(table, row, columns["name"]),
        email=_cell_str(table, row, columns["email"]),
        organisation=_cell_str(table, row, columns["organisation"]),
        job_title=_cell_str(table, row, columns["job_title"]),
        country=country,
        city=_cell_str(table, row, columns["city"]),
        website=_cell_str(table, row, columns["website"]),
        about=_cell_str(table, row, columns["about"]),
        role_type=_cell_str(table, row, columns["role_type"]),
        attend_mode=_cell_str(table, row, columns["attend_mode"]),
        in_town_start=in_start,
        in_town_end=in_end,
        interested_comedy=_cell_checked(table, row, columns["interested_comedy"]),
        comedy_genres=_cell_str(table, row, columns["comedy_genres"]),
        programme_from_festival=_optional_cell(table, row, columns, "programme_from_festival"),
        work_scale=_optional_cell(table, row, columns, "work_scale"),
        target_audiences=_optional_cell(table, row, columns, "target_audiences"),
        work_to_avoid=_optional_cell(table, row, columns, "work_to_avoid"),
        status=row_status_from_name_cell(table, row, columns["name"]),  # type: ignore[arg-type]
        first_name=first_name_from(_cell_str(table, row, columns["name"])),
        draft=draft,
        ai_fit=ai_fit,
        priority=priority,
        in_town_overlap=overlaps_show_dates(in_start, in_end),
    )


def load_industry_contacts(
    numbers_path: Path,
    *,
    schema: Literal["programmer", "agent"] = "programmer",
    ensure_columns: bool = False,
) -> tuple[list[IndustryContact], Document, OutreachColumns]:
    """Load contacts; optionally append Outreach draft / AI fit / Priority columns."""
    doc = Document(str(numbers_path))
    table = doc.sheets[0].tables[0]
    columns = PROGRAMMER_COLUMNS if schema == "programmer" else AGENT_COLUMNS
    outreach_cols = (
        ensure_outreach_columns(table, save_path=numbers_path, doc=doc)
        if ensure_columns
        else read_outreach_columns(table)
    )

    contacts: list[IndustryContact] = []
    for row in range(1, table.num_rows):
        name = _cell_str(table, row, columns["name"])
        if not name:
            continue
        contacts.append(_load_row(table, row, columns, outreach_cols))
    return contacts, doc, outreach_cols


def summarise_industry(contacts: list[IndustryContact]) -> dict[str, int]:
    counts: dict[str, int] = {
        "sent": 0,
        "skip": 0,
        "pending": 0,
        "in_town": 0,
        "with_draft": 0,
        "actionable": 0,
    }
    for contact in contacts:
        counts[contact.status] = counts.get(contact.status, 0) + 1
        if contact.in_town_overlap:
            counts["in_town"] += 1
        if contact.draft.strip():
            counts["with_draft"] += 1
        if contact.is_actionable:
            counts["actionable"] += 1
        if contact.ready_to_review:
            counts["ready"] = counts.get("ready", 0) + 1
    return counts
