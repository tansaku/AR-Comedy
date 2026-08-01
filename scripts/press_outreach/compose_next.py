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
  python3 scripts/press_outreach/compose_next.py --no-llm
  python3 scripts/press_outreach/compose_next.py --send-ready
  python3 scripts/press_outreach/compose_next.py --send-ready --auto-send
  python3 scripts/press_outreach/compose_next.py --campaign industry --dry-run

Requires Thunderbird at /Applications/Thunderbird.app
Set OPENROUTER_API_KEY in .env for LLM-generated hook lines (see .env.example).
--auto-send uses AppleScript (Cmd+Enter) and needs Accessibility permission for your terminal.
Industry campaign: save a Thunderbird template with INDUSTRY_OUTREACH in the subject.
Close the Numbers contact list before running (so highlights can be saved).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from campaigns import Campaign, get_campaign
from contacts import (
    MediaContact,
    build_contact_notes_html,
    load_contacts,
    summarise,
)
from intros import draft_hook_line, draft_london_note, draft_london_ps
from sent_examples import load_sent_hook_examples
from sync_sent import sent_mail_size, sync_and_mark, wait_for_press_send
from template import build_compose_arg, describe_cached_template, write_personalised_html
from thunderbird_send import wait_and_send

THUNDERBIRD = Path("/Applications/Thunderbird.app/Contents/MacOS/thunderbird")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign",
        choices=("press", "camden-press", "industry"),
        default="press",
        help="Outreach campaign (default: press)",
    )
    parser.add_argument(
        "--numbers",
        type=Path,
        default=None,
        help="Numbers contact list (default: campaign-specific)",
    )
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
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip OpenRouter; use rule-based hook lines only",
    )
    parser.add_argument(
        "--send-ready",
        action="store_true",
        help="Final email: no grey notes box, Instagram link on sign-off, London p.s. for UK contacts",
    )
    parser.add_argument(
        "--auto-send",
        action="store_true",
        help="After opening compose, wait 3–4s (random) then send via Thunderbird (requires --send-ready)",
    )
    args = parser.parse_args()
    if args.auto_send and not args.send_ready:
        parser.error("--auto-send requires --send-ready (no grey box to delete)")
    return args


def launch_compose(compose_arg: str) -> None:
    subprocess.run([str(THUNDERBIRD), "-compose", compose_arg], check=False)


def do_initial_sync(args: argparse.Namespace, campaign: Campaign) -> None:
    if args.no_sync:
        return
    print(f"Syncing sent {campaign.label} emails from Thunderbird → Numbers highlights...")
    try:
        marked, total_sent = sync_and_mark(
            numbers_path=args.numbers,
            state_path=campaign.sync_state,
            subject_marker=campaign.subject_marker,
            full_rescan=args.full_rescan,
        )
        print(f"Known sends: {total_sent}; newly marked yellow: {marked}")
    except FileNotFoundError as exc:
        print(f"Sync skipped: {exc}", file=sys.stderr)


def prepare_compose_for_contact(
    contact: MediaContact,
    *,
    campaign: Campaign,
    refresh_template: bool,
    use_llm: bool,
    hook_examples=None,
    send_ready: bool = False,
) -> tuple[Path, str, str]:
    hook_line = ""
    hook_source = "none"
    if campaign.use_llm_hooks and use_llm:
        hook_line, hook_source = draft_hook_line(
            contact, use_llm=use_llm, examples=hook_examples, campaign_id=campaign.id
        )
    london_ps = draft_london_ps(contact, campaign_id=campaign.id) if send_ready else ""
    notes_html = ""
    if not send_ready:
        london_note = draft_london_note(contact, campaign_id=campaign.id)
        notes_html = build_contact_notes_html(
            contact,
            intro_suggestion=hook_line,
            london_note=london_note,
        )

    print(f"\n[{campaign.id}] Next: row {contact.row} — {contact.name} <{contact.email}>")
    print(f"Org: {contact.organisation}")
    if hook_line:
        print(f"Hook ({hook_source}): {hook_line}")
    if send_ready:
        print("Send-ready mode: no grey box; Instagram link on sign-off.")
        if london_ps:
            print(f"London p.s. included for {contact.country}.")
    else:
        london_note = draft_london_note(contact, campaign_id=campaign.id)
        if london_note:
            print(f"Press note idea (in grey box only): {london_note}")
        print(
            "\nGrey contact-notes box is at the top of the compose window — "
            "use it for reference, then delete it before sending."
        )
    print("Template hook line is injected into the email body for you to edit.")

    html_path = campaign.compose_dir / f"row-{contact.row}.html"
    html_path, subject = write_personalised_html(
        html_path,
        campaign=campaign,
        first_name=contact.first_name,
        contact_notes_html=notes_html,
        hook_line=hook_line,
        include_instagram=True,
        london_ps=london_ps,
        refresh_template=refresh_template,
    )
    compose_arg = build_compose_arg(
        to_email=contact.email,
        subject=subject,
        html_path=html_path,
    )
    print(f"Draft written: {html_path}")
    print(f"Subject: {subject}")
    print(f"Template: {describe_cached_template(campaign)}")
    return html_path, subject, compose_arg


def open_compose_for_contact(
    contact: MediaContact,
    *,
    campaign: Campaign,
    refresh_template: bool,
    use_llm: bool,
    hook_examples=None,
    send_ready: bool = False,
    auto_send: bool = False,
) -> None:
    _, _, compose_arg = prepare_compose_for_contact(
        contact,
        campaign=campaign,
        refresh_template=refresh_template,
        use_llm=use_llm,
        hook_examples=hook_examples,
        send_ready=send_ready,
    )
    launch_compose(compose_arg)
    if auto_send:
        delay = wait_and_send()
        print(f"Auto-sent after {delay:.1f}s.")


def run_once(
    args: argparse.Namespace, contact: MediaContact, campaign: Campaign, hook_examples=None
) -> int:
    _, _, compose_arg = prepare_compose_for_contact(
        contact,
        campaign=campaign,
        refresh_template=args.refresh_template,
        use_llm=not args.no_llm,
        hook_examples=hook_examples,
        send_ready=args.send_ready,
    )
    if args.dry_run:
        print("(dry-run — not launching Thunderbird)")
        return 0
    if not THUNDERBIRD.exists():
        print(f"Thunderbird not found at {THUNDERBIRD}", file=sys.stderr)
        return 1
    launch_compose(compose_arg)
    if args.auto_send:
        delay = wait_and_send()
        print(f"Auto-sent after {delay:.1f}s.")
    return 0


def run_loop(args: argparse.Namespace, campaign: Campaign, hook_examples=None) -> int:
    if not THUNDERBIRD.exists() and not args.dry_run:
        print(f"Thunderbird not found at {THUNDERBIRD}", file=sys.stderr)
        return 1

    if args.auto_send:
        print(
            "AUTO-SEND enabled: each compose will be sent after a random 3–4s pause. "
            "Press Ctrl+C to stop.\n"
        )
    else:
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
            prepare_compose_for_contact(
                contact,
                campaign=campaign,
                refresh_template=args.refresh_template,
                use_llm=not args.no_llm,
                hook_examples=hook_examples,
                send_ready=args.send_ready,
            )
            print("(dry-run — not launching Thunderbird or waiting for send)")
            return 0

        watch_offset = sent_mail_size()
        open_compose_for_contact(
            contact,
            campaign=campaign,
            refresh_template=args.refresh_template,
            use_llm=not args.no_llm,
            hook_examples=hook_examples,
            send_ready=args.send_ready,
            auto_send=args.auto_send,
        )

        try:
            wait_for_press_send(
                contact.email,
                since_offset=watch_offset,
                poll_seconds=args.poll_seconds,
                subject_marker=campaign.subject_marker,
            )
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

        print(f"Sent detected for {contact.email}.")
        if not args.no_sync:
            try:
                marked, total_sent = sync_and_mark(
                    numbers_path=args.numbers,
                    state_path=campaign.sync_state,
                    subject_marker=campaign.subject_marker,
                )
                print(f"Synced: {total_sent} known sends; newly marked yellow: {marked}")
            except FileNotFoundError as exc:
                print(f"Sync skipped: {exc}", file=sys.stderr)


def main() -> int:
    args = parse_args()
    campaign = get_campaign(args.campaign)
    if args.numbers is None:
        args.numbers = campaign.default_numbers

    print(f"Campaign: {campaign.label} ({campaign.subject_marker})")
    if campaign.poster_url:
        print(f"Poster: {campaign.poster_url}")

    do_initial_sync(args, campaign)

    contacts = load_contacts(args.numbers)
    counts = summarise(contacts)
    print(
        f"List status: sent={counts['sent']} skip={counts['skip']} "
        f"pending={counts['pending']} actionable={counts['actionable']}"
    )

    if counts["actionable"] == 0:
        print("No actionable pending contacts left.")
        return 0

    hook_examples = None
    if not args.no_llm and campaign.use_llm_hooks:
        print("Loading sent hook examples for LLM few-shot...")
        hook_examples = load_sent_hook_examples()
        print(f"Using {len(hook_examples)} sent examples.")

    if args.once or args.dry_run:
        pending = [c for c in contacts if c.is_actionable]
        return run_once(args, pending[0], campaign, hook_examples=hook_examples)

    return run_loop(args, campaign, hook_examples=hook_examples)


if __name__ == "__main__":
    raise SystemExit(main())
