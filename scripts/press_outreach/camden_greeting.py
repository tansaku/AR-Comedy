#!/usr/bin/env python3
"""Choose a sensible Hi {addressee} greeting for Camden Fringe press contacts."""

from __future__ import annotations

import re

from contacts import MediaContact, first_name_from

GENERIC_EMAIL_LOCALS = {
    "press",
    "pressreleases",
    "hello",
    "info",
    "news",
    "editorial",
    "admin",
    "contact",
    "reviews",
    "theatre",
    "listings",
    "newsdesk",
    "pictures",
    "features",
    "editor",
    "site",
    "webnews",
    "culture",
    "arts",
    "news.london",
    "theatrelistings",
    "comedy",
    "prteam",
    "contactus",
    "times",
    "ayoungishperspective",
}

ARTICLE_PREFIXES = {"a", "an", "the"}

ORG_WORDS = (
    "review",
    "reviews",
    "magazine",
    "theatre",
    "theatres",
    "blog",
    "blogs",
    "news",
    "press",
    "hub",
    "guide",
    "world",
    "baby",
    "stage",
    "fringe",
    "comedy",
    "times",
    "standard",
    "metro",
    "guardian",
    "post",
    "voice",
    "chronicle",
    "independent",
    "telegraph",
    "weekly",
    "journal",
    "citizen",
    "gazette",
    "towner",
    "ist",
    "timeout",
    "chortle",
    "upcoming",
    "listings",
    "mag",
    "media",
    "radio",
    "tv",
    "film",
    "art",
    "culture",
    "living",
    "cheap",
    "nudge",
    "peg",
    "muse",
    "stop",
    "tonic",
    "ushers",
    "dazzles",
    "curtain",
    "stalls",
    "booby",
    "shiny",
    "perspective",
    "land",
    "everything",
    "night",
    "room",
    "current",
    "play",
    "thing",
    "chap",
    "spy",
    "indiependent",
    "sounds",
    "rated",
    "read",
    "bus",
    "rhombus",
    "salterton",
    "seen",
    "beyond",
    "binge",
    "breaking",
    "broadway",
    "deskbound",
    "dress",
    "circle",
    "girl",
    "london",
    "longstaff",
    "lost",
    "lou",
    "mark",
    "aspen",
    "musical",
    "north",
    "west",
    "end",
    "obscurity",
    "off",
    "pink",
    "prince",
    "plays",
    "see",
    "youngish",
)


def _person_from_job_title(contact: MediaContact) -> str:
    job = (contact.job_title or "").strip()
    if " · " not in job:
        return ""
    person = job.split(" · ", 1)[1].strip()
    if _looks_like_person(person):
        return person
    return ""


def _looks_like_org(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return True
    lower = cleaned.lower()
    if " for " in lower or " & " in lower:
        return True
    if _article_led_title(cleaned):
        return True
    if cleaned.count(" ") >= 2:
        return True
    return any(word in lower for word in ORG_WORDS)


def _article_led_title(text: str) -> bool:
    parts = (text or "").strip().split()
    return len(parts) >= 2 and parts[0].lower() in ARTICLE_PREFIXES


def _looks_like_person(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned or _looks_like_org(cleaned):
        return False
    parts = [p for p in re.split(r"\s+", cleaned) if p]
    if not parts or len(parts) > 4:
        return False
    if not all(re.match(r"^[A-Za-z][A-Za-z'.()-]*$", p) for p in parts):
        return False
    if len(parts) == 1 and len(parts[0]) <= 2:
        return False
    return 1 <= len(parts) <= 3


def _first_name_from_email(email: str) -> str:
    local = (email or "").split("@", 1)[0].lower()
    if local in GENERIC_EMAIL_LOCALS or local.startswith("news."):
        return ""
    token = re.split(r"[._+-]", local)[0]
    if token in GENERIC_EMAIL_LOCALS or len(token) < 3 or not token.isalpha():
        return ""
    if token in {w.replace("(", "").replace(")", "") for w in ORG_WORDS}:
        return ""
    return token.capitalize()


def _clean_publication_name(name: str) -> str:
    label = (name or "").strip()
    label = re.sub(r"\(([^)]*)\)", r"\1", label)
    label = re.sub(r"\s+", " ", label).strip()
    if _article_led_title(label):
        label = " ".join(label.split()[1:])
    return label


def _publication_label(contact: MediaContact) -> str:
    for candidate in (contact.organisation, contact.name):
        label = _clean_publication_name(candidate)
        if label:
            return label
    return "there"


def _org_addressee(contact: MediaContact) -> str:
    label = _publication_label(contact)
    if label.lower() == "there":
        return "there"
    if label.lower().endswith((" team", " folks")):
        return label
    if any(word in label.lower() for word in ("magazine", "blog", "review", "perspective", "guide")):
        return f"{label} folks"
    return f"{label} team"


def rule_based_greeting(contact: MediaContact) -> str:
    """Return addressee text for Hi {addressee}, (no Hi prefix)."""
    from_email = _first_name_from_email(contact.email)
    person = _person_from_job_title(contact)
    if person and from_email:
        if from_email.lower() != first_name_from(person).lower():
            return from_email
    if person:
        return first_name_from(person)

    display = (contact.name or "").strip()
    org = (contact.organisation or "").strip()

    if display and _looks_like_person(display) and display.lower() != org.lower():
        return first_name_from(display)

    if from_email:
        return from_email

    if display and not _looks_like_org(display):
        token = first_name_from(display)
        if token and token.lower() != "there" and len(token) > 2:
            return token

    return _org_addressee(contact)


def greeting_for(contact: MediaContact) -> tuple[str, str]:
    """Return (addressee_after_hi, source label). Prefer draft_greeting() when LLM is on."""
    return rule_based_greeting(contact), "rules"
