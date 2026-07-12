#!/usr/bin/env python3
"""
Review and send industry outreach emails one at a time.

AI writes the full short email (subject + body) — no Thunderbird template needed.

Workflow:
  1. Run pregenerate_industry.py to fill Email subject / Outreach draft columns
  2. Run this script — each contact opens in Thunderbird with a grey notes box
  3. Send from Thunderbird → script advances automatically
  4. Close without sending → press Enter, then [s] skip / [n] defer / [r] reopen

Usage:
  python3 scripts/press_outreach/compose_industry.py --campaign industry-uk
  python3 scripts/press_outreach/compose_industry.py --campaign industry-uk --send-ready
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from campaigns import Campaign, get_campaign
from industry_contacts import IndustryContact, load_industry_contacts, summarise_industry
from industry_email import (
    DEFAULT_SUBJECT,
    build_industry_compose_arg,
    write_industry_compose,
)
from sync_sent import (
    mark_row_skipped,
    sent_mail_size,
    sync_and_mark,
    wait_for_send_or_done,
)
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


def _sync_marker(campaign: Campaign) -> str:
    return campaign.subject_marker if campaign.sync_require_subject else ""


def _format_in_town(contact: IndustryContact) -> str:
    if contact.in_town_start and contact.in_town_end:
        return f"{contact.in_town_start} – {contact.in_town_end}"
    return "—"


def build_notes_html(contact: IndustryContact) -> str:
    import html as html_lib

    based = ", ".join(part for part in (contact.city, contact.country) if part) or "—"
    fields = [
        ("Row", str(contact.row)),
        ("Name", contact.name),
        ("Email", contact.email),
        ("Organisation", contact.organisation),
        ("Job title", contact.job_title),
        ("Based", based),
        ("Website", contact.website),
        ("Role type", contact.role_type),
        ("Attending Fringe", contact.attend_mode),
        ("In town", _format_in_town(contact)),
        ("About", contact.about),
        ("Programmes from festival", contact.programme_from_festival),
        ("Work scale sought", contact.work_scale),
        ("Target audiences", contact.target_audiences),
        ("Work to avoid", contact.work_to_avoid),
        (
            "Interested in comedy",
            "yes" if contact.interested_comedy else "no",
        ),
        ("Comedy genres", contact.comedy_genres),
        ("AI fit", contact.ai_fit),
        ("Priority", contact.priority),
        ("Proposed subject", contact.subject),
    ]
    for key, value in contact.extra_fields.items():
        if value:
            fields.append((key, value))

    lines = "".join(
        f"<div><strong>{html_lib.escape(label)}:</strong> {html_lib.escape(value or '—')}</div>"
        for label, value in fields
    )
    return (
        '<div id="press-contact-notes" style="margin:0 0 16px 0;padding:12px 14px;'
        "border:2px dashed #888;background:#f5f5f5;color:#333;font-family:Arial,sans-serif;"
        'font-size:11pt;line-height:1.5;">'
        "<p style=\"margin:0 0 8px 0;\"><strong>Contact notes — delete this whole "
        "grey box before sending</strong></p>"
        f"{lines}"
        "<hr style=\"margin:12px 0 0 0;border:none;border-top:1px solid #bbb;\">"
        "</div>"
    )


def print_contact_header(
    contact: IndustryContact, campaign: Campaign, *, remaining: int
) -> None:
    subject = contact.subject.strip() or DEFAULT_SUBJECT
    print("\n" + "=" * 72)
    print(f"{remaining} remaining · {campaign.id} row {contact.row}: {contact.name}")
    print(f"To: {contact.email} · {contact.organisation}")
    print(f"Subject: {subject} · Priority: {contact.priority}")
    print("=" * 72)


def prompt_after_close() -> str:
    print("\n[s] Skip  [n] Defer (come back later)  [r] Reopen  [q] Quit")
    while True:
        choice = input("> ").strip().lower()
        if choice in {"s", "n", "r", "q"}:
            return choice
        print("Choose s, n, r, or q.")


def open_compose(
    contact: IndustryContact,
    campaign: Campaign,
    *,
    send_ready: bool,
    auto_send: bool,
    dry_run: bool,
) -> None:
    notes = "" if send_ready else build_notes_html(contact)
    subject = contact.subject.strip() or DEFAULT_SUBJECT
    html_path = campaign.compose_dir / f"row-{contact.row}.html"
    html_path, subject = write_industry_compose(
        html_path,
        contact,
        campaign,
        subject=subject,
        body=contact.draft,
        notes_html=notes,
        embed_poster=not send_ready,
    )
    compose_arg = build_industry_compose_arg(
        contact=contact, subject=subject, html_path=html_path
    )
    print(f"Subject: {subject}")
    print(f"Draft: {html_path} ({html_path.stat().st_size // 1024} KB)")
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
    marker = _sync_marker(campaign)

    if not numbers_path.exists():
        print(f"Numbers file not found: {numbers_path}", file=sys.stderr)
        return 1

    print(f"Campaign: {campaign.label}")
    print("Opens each draft in Thunderbird (grey notes box). Send to advance; Enter if you close.")
    print("Close Numbers before running so highlights and drafts can be saved.\n")

    if not args.no_sync:
        try:
            marked, total = sync_and_mark(
                numbers_path=numbers_path,
                state_path=campaign.sync_state,
                subject_marker=marker,
                industry_schema=campaign.industry_schema,
            )
            print(f"Sent sync: {total} known; newly marked yellow: {marked}")
        except FileNotFoundError as exc:
            print(f"Sync skipped: {exc}")

    contacts, _, outreach_cols = load_industry_contacts(
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
        print_contact_header(contact, campaign, remaining=len(pending_review))

        if args.dry_run:
            print("(dry-run — would open Thunderbird)")
            pending_review = pending_review[1:]
            continue

        watch_offset = sent_mail_size()
        open_compose(
            contact,
            campaign,
            send_ready=args.send_ready,
            auto_send=args.auto_send,
            dry_run=False,
        )

        try:
            outcome = wait_for_send_or_done(
                contact.email,
                since_offset=watch_offset,
                poll_seconds=args.poll_seconds,
                subject_marker=marker,
            )
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

        if outcome == "sent":
            print(f"Sent detected for {contact.email}.")
            if not args.no_sync:
                sync_and_mark(
                    numbers_path=numbers_path,
                    state_path=campaign.sync_state,
                    subject_marker=marker,
                    industry_schema=campaign.industry_schema,
                )
            contacts, _, outreach_cols = load_industry_contacts(
                numbers_path, schema=campaign.industry_schema or "programmer"
            )
            pending_review = [c for c in contacts if c.ready_to_review]
            continue

        action = prompt_after_close()
        if action == "q":
            print("Stopped.")
            return 0
        if action == "s":
            reason = input("Skip reason (optional): ").strip() or contact.ai_fit
            mark_row_skipped(
                contact.row,
                numbers_path=numbers_path,
                reason=reason,
                fit_col=outreach_cols.fit,
            )
            print(f"Skipped row {contact.row}.")
            contacts, _, outreach_cols = load_industry_contacts(
                numbers_path, schema=campaign.industry_schema or "programmer"
            )
            pending_review = [c for c in contacts if c.ready_to_review]
            continue
        if action == "n":
            print(f"Deferred row {contact.row} — will return later.")
            pending_review = pending_review[1:] + [contact]
            continue
        if action == "r":
            continue  # reopen same contact

    print("No more drafts to review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
