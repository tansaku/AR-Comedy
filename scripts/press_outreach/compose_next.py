#!/usr/bin/env python3
"""
Open the next pending press contact in Thunderbird compose for one-at-a-time review.

Flow (--loop, default):
  1. Sync Sent Mail → Numbers yellow highlights
  2. Thunderbird opens compose with a grey contact-notes box + intro draft + press release
  3. Use the notes (org, interests, etc.) to personalise; delete the grey box; Send
  4. Script detects the send and opens the next compose window automatically

Usage:
  python3 scripts/press_outreach/compose_next.py
  python3 scripts/press_outreach/compose_next.py --refresh-template
  python3 scripts/press_outreach/compose_next.py --once
  python3 scripts/press_outreach/compose_next.py --dry-run

Requires Thunderbird at /Applications/Thunderbird.app
Close the Numbers contact list before running (so highlights can be saved).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contacts import (
    DEFAULT_NUMBERS_PATH,
    MediaContact,
    build_contact_notes_html,
    load_contacts,
    summarise,
)
from intros import draft_intro, draft_london_note
from sync_sent import sent_mail_size, sync_and_mark, wait_for_press_send
from template import build_compose_arg, describe_cached_template, write_personalised_html

THUNDERBIRD = Path("/Applications/Thunderbird.app/Contents/MacOS/thunderbird")
COMPOSE_DIR = Path(__file__).resolve().parents[2] / "data" / ".press-compose-drafts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numbers", type=Path, default=DEFAULT_NUMBERS_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Prepare draft only; do not open Thunderbird")
    parser.add_argument(
        "--refresh-template",
        action="store_true",
        help="Force re-copy from Thunderbird even if cache looks current",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip Sent Mail sync / Numbers yellow highlighting",
    )
    parser.add_argument(
        "--full-rescan",
        action="store_true",
        help="Rescan entire Sent Mail mbox (slow; first-time bootstrap uses last 200MB only)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Open one compose window only (do not auto-advance after send)",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=3.0,
        help="How often to check Sent Mail when waiting for a send (default: 3)",
    )
    return parser.parse_args()


def launch_compose(compose_arg: str) -> None:
    subprocess.run([str(THUNDERBIRD), "-compose", compose_arg], check=False)


def do_initial_sync(args: argparse.Namespace) -> None:
    if args.no_sync:
        return
    print("Syncing sent press emails from Thunderbird → Numbers highlights...")
    try:
        marked, total_sent = sync_and_mark(
            numbers_path=args.numbers,
            full_rescan=args.full_rescan,
        )
        print(f"Known press sends: {total_sent}; newly marked yellow: {marked}")
    except FileNotFoundError as exc:
        print(f"Sync skipped: {exc}", file=sys.stderr)


def prepare_compose_for_contact(
    contact: MediaContact,
    *,
    refresh_template: bool,
) -> tuple[Path, str, str]:
    intro = draft_intro(contact)
    london_note = draft_london_note(contact)
    notes_html = build_contact_notes_html(contact)

    print(f"\nNext: row {contact.row} — {contact.name} <{contact.email}>")
    print(f"Org: {contact.organisation}")
    print(f"Intro draft: {intro}")
    if london_note:
        print(f"London note: {london_note}")
    print(
        "\nGrey contact-notes box is at the top of the compose window — "
        "use it for personalisation, then delete it before sending."
    )

    html_path = COMPOSE_DIR / f"row-{contact.row}.html"
    html_path, subject = write_personalised_html(
        html_path,
        first_name=contact.first_name,
        intro=intro,
        london_note=london_note,
        contact_notes_html=notes_html,
        refresh_template=refresh_template,
    )
    compose_arg = build_compose_arg(
        to_email=contact.email,
        subject=subject,
        html_path=html_path,
    )
    print(f"Draft written: {html_path}")
    print(f"Subject: {subject}")
    print(f"Template: {describe_cached_template()}")
    return html_path, subject, compose_arg


def open_compose_for_contact(
    contact: MediaContact,
    *,
    refresh_template: bool,
) -> None:
    _, _, compose_arg = prepare_compose_for_contact(
        contact, refresh_template=refresh_template
    )
    launch_compose(compose_arg)


def run_once(args: argparse.Namespace, contact: MediaContact) -> int:
    _, _, compose_arg = prepare_compose_for_contact(
        contact, refresh_template=args.refresh_template
    )
    if args.dry_run:
        print("(dry-run — not launching Thunderbird)")
        return 0
    if not THUNDERBIRD.exists():
        print(f"Thunderbird not found at {THUNDERBIRD}", file=sys.stderr)
        return 1
    launch_compose(compose_arg)
    return 0


def run_loop(args: argparse.Namespace) -> int:
    if not THUNDERBIRD.exists() and not args.dry_run:
        print(f"Thunderbird not found at {THUNDERBIRD}", file=sys.stderr)
        return 1

    print(
        "Loop mode: after each send, the next compose window opens automatically. "
        "Press Ctrl+C to stop.\n"
    )

    while True:
        contacts = load_contacts(args.numbers)
        pending = [c for c in contacts if c.is_actionable]
        if not pending:
            print("No actionable pending contacts left. Done.")
            return 0

        contact = pending[0]
        if args.dry_run:
            prepare_compose_for_contact(contact, refresh_template=args.refresh_template)
            print("(dry-run — not launching Thunderbird or waiting for send)")
            return 0

        watch_offset = sent_mail_size()
        open_compose_for_contact(contact, refresh_template=args.refresh_template)

        try:
            wait_for_press_send(
                contact.email,
                since_offset=watch_offset,
                poll_seconds=args.poll_seconds,
            )
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

        print(f"Sent detected for {contact.email}.")
        if not args.no_sync:
            try:
                marked, total_sent = sync_and_mark(numbers_path=args.numbers)
                print(f"Synced: {total_sent} known sends; newly marked yellow: {marked}")
            except FileNotFoundError as exc:
                print(f"Sync skipped: {exc}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    do_initial_sync(args)

    contacts = load_contacts(args.numbers)
    counts = summarise(contacts)
    print(
        f"List status: sent={counts['sent']} skip={counts['skip']} "
        f"pending={counts['pending']} actionable={counts['actionable']}"
    )

    if counts["actionable"] == 0:
        print("No actionable pending contacts left.")
        return 0

    if args.once or args.dry_run:
        pending = [c for c in contacts if c.is_actionable]
        return run_once(args, pending[0])

    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
