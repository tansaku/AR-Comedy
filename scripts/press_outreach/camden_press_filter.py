#!/usr/bin/env python3
"""Skip rules for Camden Fringe press list contacts."""

from __future__ import annotations

from contacts import MediaContact


SKIP_SECTIONS = {
    "DANCE PRESS",
    "FAMILY / CHILDRENS PRESS",
    "IRISH PRESS",
    "BLACK PRESS",
}


def _section_from_contact(contact: MediaContact) -> str:
    job = (contact.job_title or "").strip()
    if " · " in job:
        return job.split(" · ", 1)[0].strip().upper()
    return job.upper()


def _blob(contact: MediaContact) -> str:
    return " ".join(
        [
            contact.name,
            contact.organisation,
            contact.job_title,
            contact.interests,
        ]
    ).lower()


def camden_skip_reason(contact: MediaContact) -> str | None:
    """Return a skip reason, or None if this contact should receive outreach."""
    section = _section_from_contact(contact)
    if section in SKIP_SECTIONS:
        return f"{section.title()} — not targeting this outreach"

    text = _blob(contact)

    if contact.organisation.strip().lower() == "london pub theatres":
        return "Pub theatres only (min 3 performances) — no list email"

    if "musical theatre review" in text or "musicals only" in text:
        return "Musicals only — solo stand-up not a fit"

    if "dance press" in text or contact.job_title.strip().upper().startswith("DANCE PRESS"):
        return "Dance press — not comedy stand-up"

    if "family / childrens press" in text or "family / children" in text:
        return "Family/children's press — 18+ solo show"

    if contact.organisation.lower() in {"fringetheatreawards.co.uk", "the offies", "offies.london"}:
        return "Awards listing — no press contact"

    return None


def is_camden_actionable(contact: MediaContact) -> bool:
    return contact.is_actionable and camden_skip_reason(contact) is None
