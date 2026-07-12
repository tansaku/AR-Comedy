#!/usr/bin/env python3
"""
Review and send industry outreach emails one at a time.

Workflow:
  1. Run pregenerate_industry.py overnight to fill Outreach draft / AI fit columns
  2. Run this script to review each proposal: send, edit, or skip
  3. Skip marks the row orange in Numbers; send marks yellow (via Sent Mail sync)

Usage:
  python3 scripts/press_outreach/compose_industry.py --campaign industry-uk
  python3 scripts/press_outreach/compose_industry.py --campaign industry-uk --send-ready
  python3 scripts/press_outreach/compose_industry.py --campaign industry-uk --auto-send --send-ready

Save a Thunderbird template whose subject contains the campaign marker
(e.g. INDUSTRY_UK_OUTREACH) before composing.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from campaigns import Campaign, get_campaign
from industry_contacts import IndustryContact, load_industry_contacts, summarise_industry
from sync_sent import mark_row_skipped, sent_mail_size, sync_and_mark, wait_for_press_send
from template import build_compose_arg, describe_cached_template, write_personalised_html
from thunderbird_send import wait_and_send

THUNDERBIRD = Path("/Applications/Thunderbird.app/Contents/MacOS/thunderbird")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign",
        choices=("industry-uk", "industry-intl", "industry-agents", "industry"),
        default="industry-uk",
    )
    parser.add_argument("--numbers", type=Path, default=None)
    parser.add_argument("--send-ready", action="store_true", help="No grey box; final email body")
    parser.add_argument("--auto-send", action="store_true", help="Send after 3–4s (needs --send-ready)")
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.auto_send and not args.send_ready:
        parser.error("--auto-send requires --send-ready")
    return args


def launch_compose(compose_arg: str) -> None:
    subprocess.run([str(THUNDERBIRD), "-compose", compose_arg], check=False)


def build_notes_html(contact: IndustryContact) -> str:
    import html as html_lib

    fields = [
        ("AI fit", contact.ai_fit),
        ("Priority", contact.priority),
        ("Organisation", contact.organisation),
        ("Job title", contact.job_title),
        ("In town", f"{contact.in_town_start} – {contact.in_town_end}"),
        ("Draft hook", contact.draft),
    ]
    lines = "".join(
        f"<div><strong>{html_lib.escape(label)}:</strong> {html_lib.escape(value or '—')}</div>"
        for label, value in fields
    )
    return (
        '<div id="press-contact-notes" style="margin:0 0 16px 0;padding:12px 14px;'
        "border:2px dashed #888;background:#f5f5f5;color:#333;font-family:Arial,sans-serif;"
        'font-size:11pt;line-height:1.5;">'
        "<p style=\"margin:0 0 8px 0;\"><strong>Industry notes — delete before sending</strong></p>"
        f"{lines}"
        "</div>"
    )


def print_review_card(contact: IndustryContact, campaign: Campaign) -> None:
    print("\n" + "=" * 72)
    print(f"[{campaign.id}] row {contact.row}: {contact.name} <{contact.email}>")
    print(f"Org: {contact.organisation} · {contact.job_title}")
    print(f"In town: {contact.in_town_start} – {contact.in_town_end}")
    print(f"AI fit ({contact.priority}): {contact.ai_fit}")
    print(f"Draft hook:\n  {contact.draft}")
    print("=" * 72)


def prompt_action() -> str:
    print("\n[s] Send  [e] Edit in Thunderbird  [k] Skip  [q] Quit")
    while True:
        choice = input("> ").strip().lower()
        if choice in {"s", "e", "k", "q"}:
            return choice
        print("Choose s, e, k, or q.")


def open_compose(
    contact: IndustryContact,
    campaign: Campaign,
    *,
    send_ready: bool,
    auto_send: bool,
    dry_run: bool,
) -> None:
    notes = "" if send_ready else build_notes_html(contact)
    html_path = campaign.compose_dir / f"row-{contact.row}.html"
    html_path, subject = write_personalised_html(
        html_path,
        campaign=campaign,
        first_name=contact.first_name,
        contact_notes_html=notes,
        hook_line=contact.draft,
        include_instagram=True,
        industry_mode=True,
    )
    compose_arg = build_compose_arg(
        to_email=contact.email,
        subject=subject,
        html_path=html_path,
    )
    print(f"Subject: {subject}")
    print(f"Draft: {html_path}")
    if dry_run:
        print("(dry-run — not launching Thunderbird)")
        return
    launch_compose(compose_arg)
    if auto_send:
        delay = wait_and_send()
        print(f"Auto-sent after {delay:.1f}s.")


def main() -> int:
    args = parse_args()
    campaign = get_campaign(args.campaign)
    numbers_path = args.numbers or campaign.default_numbers

    if not numbers_path.exists():
        print(f"Numbers file not found: {numbers_path}", file=sys.stderr)
        return 1

    print(f"Campaign: {campaign.label}")
    print(f"Template marker: {campaign.subject_marker}")
    print(f"Close Numbers before running so highlights and drafts can be saved.\n")

    if not args.no_sync:
        try:
            marked, total = sync_and_mark(
                numbers_path=numbers_path,
                state_path=campaign.sync_state,
                subject_marker=campaign.subject_marker,
            )
            print(f"Sent sync: {total} known; newly marked yellow: {marked}")
        except FileNotFoundError as exc:
            print(f"Sync skipped: {exc}")

    contacts, doc, outreach_cols = load_industry_contacts(
        numbers_path,
        schema=campaign.industry_schema or "programmer",
    )
    counts = summarise_industry(contacts)
    print(
        f"Status: sent={counts['sent']} skip={counts['skip']} pending={counts['pending']} "
        f"ready={counts.get('ready', 0)}"
    )

    pending_review = [c for c in contacts if c.ready_to_review]
    if not pending_review:
        print("No drafts ready to review. Run pregenerate_industry.py first.")
        return 0

    if not THUNDERBIRD.exists() and not args.dry_run:
        print(f"Thunderbird not found at {THUNDERBIRD}", file=sys.stderr)
        return 1

    print(f"\nReview loop: {len(pending_review)} contacts with drafts. Ctrl+C to stop.\n")

    while pending_review:
        contact = pending_review[0]
        print_review_card(contact, campaign)
        action = "s" if args.auto_send else prompt_action()

        if action == "q":
            print("Stopped.")
            return 0

        if action == "k":
            reason = input("Skip reason (optional): ").strip() or contact.ai_fit
            mark_row_skipped(
                contact.row,
                numbers_path=numbers_path,
                reason=reason,
                fit_col=outreach_cols.fit,
            )
            print(f"Skipped row {contact.row}.")
            contacts, doc, outreach_cols = load_industry_contacts(
                numbers_path, schema=campaign.industry_schema or "programmer"
            )
            pending_review = [c for c in contacts if c.ready_to_review]
            continue

        watch_offset = sent_mail_size()
        open_compose(
            contact,
            campaign,
            send_ready=args.send_ready or action == "s",
            auto_send=args.auto_send and action == "s",
            dry_run=args.dry_run,
        )

        if args.dry_run:
            pending_review = pending_review[1:]
            continue

        if action in {"s", "e"}:
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
                sync_and_mark(
                    numbers_path=numbers_path,
                    state_path=campaign.sync_state,
                    subject_marker=campaign.subject_marker,
                )
        contacts, doc, outreach_cols = load_industry_contacts(
            numbers_path, schema=campaign.industry_schema or "programmer"
        )
        pending_review = [c for c in contacts if c.ready_to_review]

    print("No more drafts to review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
