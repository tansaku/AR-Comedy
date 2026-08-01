#!/usr/bin/env python3
"""Parse Camden Fringe press-list PDFs into structured contact rows."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", re.IGNORECASE)
URL_RE = re.compile(
    r"^(https?://|www\.|[a-z0-9.-]+\.(com|co\.uk|org|info|uk|blog)/)",
    re.IGNORECASE,
)
NOTE_HINTS = (
    "only",
    "do not",
    "minimum",
    "contact until",
    "listings",
    "pictures",
    "features",
    "newsdesk",
    "reviews",
    "editorial",
    "theatre critic",
    "culture section",
    "arts and culture",
    "will only",
)

SKIP_LINES = {
    "2026 press list",
    "fringetheatreawards.co.uk",
    "offies.london",
}


@dataclass(frozen=True)
class CamdenPressContact:
    section: str
    organisation: str
    name: str
    email: str
    contact_url: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        return self.organisation

    @property
    def is_actionable(self) -> bool:
        return bool(self.email)


def pdf_to_text(pdf_path: Path) -> str:
    return subprocess.check_output(
        ["pdftotext", str(pdf_path), "-"],
        text=True,
        stderr=subprocess.STDOUT,
    )


def _is_section_header(line: str) -> bool:
    if EMAIL_RE.match(line) or URL_RE.match(line):
        return False
    lowered = line.lower().strip()
    if lowered in SKIP_LINES:
        return True
    if line.isupper() and len(line) >= 8 and re.search(r"[A-Z]", line):
        return True
    if line.endswith(" PRESS") or line.endswith(" PRESS & BLOGS"):
        return True
    if line in {"AWARDS"}:
        return True
    return False


def _is_note(line: str) -> bool:
    lowered = line.lower()
    return any(hint in lowered for hint in NOTE_HINTS)


def _section_tags(section: str) -> list[str]:
    lowered = section.lower()
    tags: list[str] = []
    if "comedy" in lowered:
        tags.append("Comedy")
    if any(word in lowered for word in ("theatre", "fringe", "press", "national")):
        tags.append("Theatre")
    if "camden" in lowered or "london" in lowered:
        tags.append("London")
    if not tags:
        tags.append("Theatre")
    return tags


def _merge_notes(*parts: str) -> str:
    return " · ".join(part.strip() for part in parts if part and part.strip())


def parse_camden_press_text(text: str) -> list[CamdenPressContact]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    current_section = "General"
    contacts: list[CamdenPressContact] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if _is_section_header(line):
            current_section = line
            index += 1
            continue

        if EMAIL_RE.match(line):
            email_lines: list[str] = []
            while index < len(lines) and EMAIL_RE.match(lines[index]):
                email_lines.append(lines[index].lower())
                index += 1

            org = ""
            person = ""
            notes: list[str] = []
            back = index - len(email_lines) - 1
            while back >= 0 and not _is_section_header(lines[back]):
                prev = lines[back]
                if EMAIL_RE.match(prev) or URL_RE.match(prev):
                    break
                if _is_note(prev):
                    notes.insert(0, prev)
                elif not org:
                    org = prev
                elif not person:
                    person = prev
                else:
                    notes.insert(0, prev)
                back -= 1

            if not org and person:
                org, person = person, ""

            people = [person] if person else [""]
            if len(email_lines) > 1 and person:
                # Two emails under one named contact — keep one row per address.
                people = [person] * len(email_lines)
            elif len(email_lines) > 1:
                people = [""] * len(email_lines)

            for email, named in zip(email_lines, people, strict=False):
                contacts.append(
                    CamdenPressContact(
                        section=current_section,
                        organisation=org or named or email.split("@")[0],
                        name=named if org else "",
                        email=email,
                        notes=_merge_notes(*notes),
                        tags=_section_tags(current_section),
                    )
                )
            continue

        if URL_RE.match(line):
            org = ""
            person = ""
            notes: list[str] = []
            back = index - 1
            while back >= 0 and not _is_section_header(lines[back]):
                prev = lines[back]
                if EMAIL_RE.match(prev) or URL_RE.match(prev):
                    break
                if _is_note(prev):
                    notes.insert(0, prev)
                elif not org:
                    org = prev
                elif not person:
                    person = prev
                else:
                    notes.insert(0, prev)
                back -= 1
            if not org and person:
                org, person = person, ""

            contacts.append(
                CamdenPressContact(
                    section=current_section,
                    organisation=org or line,
                    name=person if org else "",
                    email="",
                    contact_url=line,
                    notes=_merge_notes(*notes, "No email — use contact page"),
                    tags=_section_tags(current_section),
                )
            )
            index += 1
            continue

        index += 1

    return contacts


def parse_camden_press_pdf(pdf_path: Path) -> list[CamdenPressContact]:
    return parse_camden_press_text(pdf_to_text(pdf_path))


def summarise_camden(contacts: list[CamdenPressContact]) -> dict[str, int]:
    counts = {
        "total": len(contacts),
        "with_email": sum(1 for c in contacts if c.email),
        "url_only": sum(1 for c in contacts if not c.email and c.contact_url),
        "comedy": sum(1 for c in contacts if "Comedy" in c.tags),
        "theatre": sum(1 for c in contacts if "Theatre" in c.tags),
    }
    by_section: dict[str, int] = {}
    for contact in contacts:
        by_section[contact.section] = by_section.get(contact.section, 0) + 1
    counts["sections"] = len(by_section)
    return counts
