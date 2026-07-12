#!/usr/bin/env python3
"""Parse Edinburgh Fringe media contact list from Apple Numbers."""

from __future__ import annotations

import html
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from numbers_parser import Document

from numbers_style import SENT_BG, SKIP_BG, row_status_from_name_cell, style_entire_row

Status = Literal["sent", "skip", "pending"]

DEFAULT_NUMBERS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "2026 Media Contact List .numbers"
)

COLUMNS = {
    "name": 0,
    "email": 1,
    "organisation": 2,
    "job_title": 3,
    "interests": 4,
    "country": 5,
    "consent": 6,
}


@dataclass(frozen=True)
class MediaContact:
    row: int
    name: str
    email: str
    organisation: str
    job_title: str
    interests: str
    country: str
    consent: str
    status: Status
    first_name: str

    @property
    def is_london_relevant(self) -> bool:
        country = (self.country or "").lower()
        return country in {"england", "united kingdom", "uk", "wales", "northern ireland"}

    @property
    def covers_comedy_or_theatre(self) -> bool:
        interests = self.interests or ""
        return "Comedy" in interests or "Theatre" in interests

    @property
    def has_consent(self) -> bool:
        return (self.consent or "").strip().lower() == "yes"

    @property
    def is_actionable(self) -> bool:
        return (
            self.status == "pending"
            and self.has_consent
            and self.covers_comedy_or_theatre
            and bool(self.email)
        )


def classify_row_status(table, row: int) -> Status:
    status = row_status_from_name_cell(table, row, COLUMNS["name"])
    return status  # type: ignore[return-value]


def first_name_from(full_name: str) -> str:
    """Return a friendly first name from the Fringe 'Name' column."""
    name = (full_name or "").strip()
    if not name:
        return "there"
    if "(" in name:
        name = name.split("(", 1)[0].strip()
    return name.split()[0]


def load_contacts(numbers_path: Path | None = None) -> list[MediaContact]:
    path = numbers_path or DEFAULT_NUMBERS_PATH
    doc = Document(str(path))
    table = doc.sheets[0].tables[0]
    contacts: list[MediaContact] = []

    for row in range(1, table.num_rows):
        name = table.cell(row, COLUMNS["name"]).value or ""
        contacts.append(
            MediaContact(
                row=row,
                name=name,
                email=(table.cell(row, COLUMNS["email"]).value or "").strip(),
                organisation=(table.cell(row, COLUMNS["organisation"]).value or "").strip(),
                job_title=(table.cell(row, COLUMNS["job_title"]).value or "").strip(),
                interests=(table.cell(row, COLUMNS["interests"]).value or "").strip(),
                country=(table.cell(row, COLUMNS["country"]).value or "").strip(),
                consent=(table.cell(row, COLUMNS["consent"]).value or "").strip(),
                status=classify_row_status(table, row),
                first_name=first_name_from(name),
            )
        )
    return contacts


def summarise(contacts: list[MediaContact]) -> dict[str, int]:
    counts: dict[str, int] = {"sent": 0, "skip": 0, "pending": 0, "actionable": 0}
    for contact in contacts:
        counts[contact.status] = counts.get(contact.status, 0) + 1
        if contact.is_actionable:
            counts["actionable"] += 1
    return counts


def contact_to_dict(contact: MediaContact) -> dict[str, str | int]:
    data = asdict(contact)
    data["is_london_relevant"] = contact.is_london_relevant
    data["is_actionable"] = contact.is_actionable
    return data


def build_contact_notes_html(
    contact: MediaContact,
    *,
    intro_suggestion: str = "",
    london_note: str = "",
) -> str:
    """Editable reference block at the top of the compose window — delete before sending."""
    fields = [
        ("Row", str(contact.row)),
        ("Name", contact.name),
        ("Email", contact.email),
        ("Organisation", contact.organisation),
        ("Job title", contact.job_title),
        ("Country", contact.country),
        ("Interests", contact.interests),
    ]
    lines = "".join(
        f"<div><strong>{html.escape(label)}:</strong> {html.escape(value or '—')}</div>"
        for label, value in fields
    )
    extras = ""
    if intro_suggestion.strip():
        extras += (
            f'<div style="margin-top:8px;"><strong>Intro idea (optional):</strong> '
            f"{html.escape(intro_suggestion)}</div>"
        )
    if london_note.strip():
        extras += (
            f'<div style="margin-top:8px;"><strong>London preview note (optional):</strong> '
            f"{html.escape(london_note)}</div>"
        )
    return (
        '<div id="press-contact-notes" style="margin:0 0 16px 0;padding:12px 14px;'
        "border:2px dashed #888;background:#f5f5f5;color:#333;font-family:Arial,sans-serif;"
        'font-size:11pt;line-height:1.5;">'
        "<p style=\"margin:0 0 8px 0;\"><strong>Contact notes — delete this whole "
        "grey box before sending</strong></p>"
        f"{lines}{extras}"
        "<hr style=\"margin:12px 0 0 0;border:none;border-top:1px solid #bbb;\">"
        "</div>"
    )
