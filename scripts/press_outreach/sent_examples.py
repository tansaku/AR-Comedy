#!/usr/bin/env python3
"""Extract personalised hook examples from sent press-release emails."""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import asdict, dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path

from contacts import MediaContact, load_contacts
from sync_sent import (
    DEFAULT_SENT_MAIL,
    SUBJECT_MARKER,
    _emails_from_header,
    _message_body_from_chunk,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_CACHE_PATH = REPO_ROOT / "data" / ".press-sent-hook-examples.json"

BASE_LINE = (
    "Hope you're well - Just sharing the press release for my upcoming Edinburgh show."
)
HOOK_EXTRACT_RE = re.compile(
    rf"{re.escape(BASE_LINE)}\s*(.*?)\s*Best, Sam Joseph",
    re.DOTALL | re.IGNORECASE,
)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class SentHookExample:
    email: str
    name: str
    organisation: str
    hook: str


def _message_text(message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/html":
                return part.get_content()
            if part.get_content_type() == "text/plain":
                return part.get_content()
        return ""
    return message.get_content()


def _extract_hook_from_text(text: str) -> str | None:
    plain = TAG_RE.sub(" ", text or "")
    plain = html_lib.unescape(plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    match = HOOK_EXTRACT_RE.search(plain)
    if not match:
        return None
    hook = match.group(1).strip()
    return hook or None


def _contact_lookup(contacts: list[MediaContact]) -> dict[str, MediaContact]:
    return {contact.email.lower(): contact for contact in contacts}


def _examples_from_cache(sent_path: Path) -> list[SentHookExample] | None:
    if not EXAMPLES_CACHE_PATH.exists() or not sent_path.exists():
        return None
    try:
        payload = json.loads(EXAMPLES_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if payload.get("sent_mtime") != sent_path.stat().st_mtime:
        return None
    return [SentHookExample(**item) for item in payload.get("examples", [])]


def _save_examples_cache(sent_path: Path, examples: list[SentHookExample]) -> None:
    EXAMPLES_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sent_mtime": sent_path.stat().st_mtime,
        "examples": [asdict(example) for example in examples],
    }
    EXAMPLES_CACHE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _scan_sent_hook_examples(
    *,
    sent_path: Path,
    lookup: dict[str, MediaContact],
) -> list[SentHookExample]:
    size = sent_path.stat().st_size
    offset = max(0, size - 200 * 1024 * 1024)
    with sent_path.open("rb") as handle:
        handle.seek(offset)
        text = handle.read().decode("utf-8", errors="replace")
    split_at = text.find("\nFrom - ")
    if split_at >= 0:
        text = text[split_at + 1 :]

    examples: list[SentHookExample] = []
    seen: set[str] = set()

    for chunk in text.split("\nFrom - "):
        if SUBJECT_MARKER not in chunk:
            continue
        body = _message_body_from_chunk(chunk)
        if not body:
            continue
        try:
            message = BytesParser(policy=policy.default).parsebytes(
                body.encode("utf-8", errors="replace")
            )
        except (UnicodeError, ValueError):
            continue
        to_emails = _emails_from_header(message.get("To", ""))
        if not to_emails:
            continue
        email = sorted(to_emails)[0]
        if email in seen:
            continue
        hook = _extract_hook_from_text(_message_text(message))
        if not hook:
            continue
        contact = lookup.get(email)
        examples.append(
            SentHookExample(
                email=email,
                name=contact.name if contact else email,
                organisation=contact.organisation if contact else "",
                hook=hook,
            )
        )
        seen.add(email)

    return examples


_examples_cache: list[SentHookExample] | None = None


def load_sent_hook_examples(
    *,
    sent_path=DEFAULT_SENT_MAIL,
    contacts: list[MediaContact] | None = None,
    refresh: bool = False,
) -> list[SentHookExample]:
    """Return hooks from sent press emails, joined to Numbers contact metadata."""
    global _examples_cache
    if not refresh and _examples_cache is not None:
        return _examples_cache

    if not refresh:
        cached = _examples_from_cache(sent_path)
        if cached is not None:
            _examples_cache = cached
            return cached

    contacts = contacts or load_contacts()
    lookup = _contact_lookup(contacts)
    examples = _scan_sent_hook_examples(sent_path=sent_path, lookup=lookup)
    _save_examples_cache(sent_path, examples)
    _examples_cache = examples
    return examples
