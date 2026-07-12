#!/usr/bin/env python3
"""Sync sent press-release emails from Thunderbird into Numbers highlights."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

from numbers_parser import Document

from contacts import (
    COLUMNS,
    DEFAULT_NUMBERS_PATH,
    load_contacts,
)
from numbers_style import SKIP_BG, row_status_from_name_cell, style_entire_row

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SYNC_STATE = REPO_ROOT / "data" / ".press-outreach-sent-sync.json"
DEFAULT_SENT_MAIL = Path.home() / (
    "Library/Thunderbird/Profiles/magfbx3x.default-release/"
    "ImapMail/imap.gmail-1.com/[Gmail].sbd/Sent Mail"
)
SUBJECT_MARKER = "ED_FRINGE_PRESS_RELEASE"
TAIL_SCAN_BYTES = 200 * 1024 * 1024  # first-run bootstrap: last 200MB
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+", re.IGNORECASE)


def _load_state(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _emails_from_header(value: str) -> set[str]:
    return {match.lower() for match in EMAIL_RE.findall(value or "")}


MBOX_DATE_RE = re.compile(r"^\w{3} \w{3} +\d+ +\d+:\d+:\d+ +\d{4}\s*$")


def _message_body_from_chunk(chunk: str) -> str:
    chunk = chunk.strip()
    if chunk.startswith("From - "):
        chunk = chunk[len("From - ") :]
    lines = chunk.splitlines()
    if not lines:
        return ""
    # Drop mbox envelope date line (contains colons in the time, but is not a header).
    if MBOX_DATE_RE.match(lines[0].strip()) or not re.match(r"^[\w-]+:", lines[0]):
        lines = lines[1:]
    return "\n".join(lines)


def _emails_from_message_chunk(chunk: str, *, subject_marker: str) -> set[str]:
    if subject_marker not in chunk:
        return set()
    body = _message_body_from_chunk(chunk)
    if not body:
        return set()
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            body.encode("utf-8", errors="replace")
        )
    except (UnicodeError, ValueError):
        return set()
    subject = message.get("Subject", "")
    spaced = subject_marker.replace("_", " ")
    if (
        subject_marker not in subject
        and spaced not in subject
        and subject_marker not in chunk
    ):
        return set()
    return _emails_from_header(message.get("To", ""))


def _iter_chunks_from_text(text: str) -> list[str]:
    return text.split("\nFrom - ")


def scan_sent_mail(
    sent_path: Path,
    *,
    subject_marker: str = SUBJECT_MARKER,
    start_offset: int = 0,
    tail_only: bool = False,
) -> tuple[set[str], int]:
    """Return (recipient emails, new end offset) from Sent Mail mbox."""
    if not sent_path.exists():
        raise FileNotFoundError(f"Thunderbird Sent Mail not found: {sent_path}")

    size = sent_path.stat().st_size
    offset = max(0, size - TAIL_SCAN_BYTES) if tail_only else start_offset

    with sent_path.open("rb") as handle:
        handle.seek(offset)
        raw = handle.read()
        end_offset = handle.tell()

    text = raw.decode("utf-8", errors="replace")
    if offset > 0:
        split_at = text.find("\nFrom - ")
        if split_at >= 0:
            text = text[split_at + 1 :]
    elif text.startswith("From - "):
        text = text[len("From - ") :]

    found: set[str] = set()
    for chunk in _iter_chunks_from_text(text):
        found.update(_emails_from_message_chunk(chunk, subject_marker=subject_marker))
    return found, end_offset


def sync_sent_recipients(
    *,
    sent_path: Path | None = None,
    state_path: Path | None = None,
    subject_marker: str = SUBJECT_MARKER,
    full_rescan: bool = False,
) -> set[str]:
    """Update sync state from Thunderbird Sent Mail; return all known sent emails."""
    sent_path = sent_path or DEFAULT_SENT_MAIL
    state_path = state_path or DEFAULT_SYNC_STATE
    state = _load_state(state_path)
    known = {email.lower() for email in state.get("sent_emails", [])}

    if full_rescan:
        batch, end_offset = scan_sent_mail(
            sent_path, subject_marker=subject_marker, start_offset=0, tail_only=False
        )
    elif "byte_offset" not in state or not state.get("sent_emails"):
        batch, end_offset = scan_sent_mail(
            sent_path, subject_marker=subject_marker, tail_only=True
        )
    else:
        size = sent_path.stat().st_size
        previous_offset = state["byte_offset"]
        if previous_offset >= size:
            batch, end_offset = set(), size
        else:
            batch, end_offset = scan_sent_mail(
                sent_path,
                subject_marker=subject_marker,
                start_offset=previous_offset,
            )

    known.update(batch)
    state["sent_emails"] = sorted(known)
    state["byte_offset"] = end_offset
    state["last_sync"] = datetime.now(timezone.utc).isoformat()
    _save_state(state_path, state)
    return known


def _is_skip_cell(table, row: int) -> bool:
    return row_status_from_name_cell(table, row, COLUMNS["name"]) == "skip"


def mark_sent_rows_in_numbers(
    sent_emails: set[str],
    *,
    numbers_path: Path | None = None,
) -> int:
    """Yellow-highlight entire rows whose email appears in sent_emails."""
    numbers_path = numbers_path or DEFAULT_NUMBERS_PATH
    sent_lookup = {email.lower() for email in sent_emails}
    contacts = load_contacts(numbers_path)

    doc = Document(str(numbers_path))
    table = doc.sheets[0].tables[0]
    updated = 0

    for contact in contacts:
        if contact.email.lower() not in sent_lookup:
            continue
        if contact.status == "sent":
            continue
        if _is_skip_cell(table, contact.row):
            continue
        style_entire_row(table, contact.row, (255, 240, 86))
        updated += 1

    if updated:
        doc.save(str(numbers_path))
    return updated


def repair_row_highlights(
    numbers_path: Path,
    *,
    name_col: int = 1,
) -> int:
    """Re-apply sent/skip colours across entire rows (fixes legacy name-only highlights)."""
    doc = Document(str(numbers_path))
    table = doc.sheets[0].tables[0]
    updated = 0
    for row in range(1, table.num_rows):
        status = row_status_from_name_cell(table, row, name_col)
        if status == "sent":
            style_entire_row(table, row, (255, 240, 86))
            updated += 1
        elif status == "skip":
            style_entire_row(table, row, SKIP_BG)
            updated += 1
    if updated:
        doc.save(str(numbers_path))
    return updated


def mark_row_skipped(
    row: int,
    *,
    numbers_path: Path,
    reason: str = "",
    fit_col: int | None = None,
) -> None:
    """Orange-highlight a row and optionally record a skip reason."""
    doc = Document(str(numbers_path))
    table = doc.sheets[0].tables[0]
    style_entire_row(table, row, SKIP_BG)
    if reason and fit_col is not None:
        table.write(row, fit_col, f"SKIP: {reason}")
    doc.save(str(numbers_path))


def sync_and_mark(
    *,
    numbers_path: Path | None = None,
    sent_path: Path | None = None,
    state_path: Path | None = None,
    subject_marker: str = SUBJECT_MARKER,
    full_rescan: bool = False,
) -> tuple[int, int]:
    """Sync Thunderbird sent mail and update Numbers highlights.

    Returns (newly_marked_rows, total_known_sent_emails).
    """
    sent_emails = sync_sent_recipients(
        sent_path=sent_path,
        state_path=state_path,
        subject_marker=subject_marker,
        full_rescan=full_rescan,
    )
    marked = mark_sent_rows_in_numbers(sent_emails, numbers_path=numbers_path)
    return marked, len(sent_emails)


def sent_mail_size(sent_path: Path | None = None) -> int:
    path = sent_path or DEFAULT_SENT_MAIL
    return path.stat().st_size


def recipient_sent_since(
    recipient_email: str,
    *,
    since_offset: int,
    sent_path: Path | None = None,
    subject_marker: str = SUBJECT_MARKER,
) -> bool:
    """True if a campaign message to recipient_email appears after since_offset."""
    sent_path = sent_path or DEFAULT_SENT_MAIL
    recipients, _ = scan_sent_mail(
        sent_path, subject_marker=subject_marker, start_offset=since_offset
    )
    return recipient_email.lower() in recipients


def wait_for_press_send(
    recipient_email: str,
    *,
    since_offset: int,
    sent_path: Path | None = None,
    subject_marker: str = SUBJECT_MARKER,
    poll_seconds: float = 3.0,
) -> None:
    """Block until recipient appears in Sent Mail, polling incrementally."""
    import time

    sent_path = sent_path or DEFAULT_SENT_MAIL
    print(
        f"Waiting for send to {recipient_email} "
        f"(checking every {poll_seconds:g}s — Ctrl+C to stop)..."
    )
    while True:
        if recipient_sent_since(
            recipient_email,
            since_offset=since_offset,
            sent_path=sent_path,
            subject_marker=subject_marker,
        ):
            return
        time.sleep(poll_seconds)
