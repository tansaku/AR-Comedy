#!/usr/bin/env python3
"""
Camden Fringe press outreach — built-in press release (no Thunderbird template).

Default flow:
  1. Opens the first contact in Thunderbird (poster embedded)
  2. Waits for you to send (auto-detects Sent Mail, or Enter when done)
  3. Prompts: auto-send rest, manual review each, or stop

Usage:
  python3 scripts/press_outreach/compose_camden.py
  python3 scripts/press_outreach/compose_camden.py --manual
  python3 scripts/press_outreach/compose_camden.py --auto-send-all
  python3 scripts/press_outreach/compose_camden.py --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contact_web_context import contact_web_context
from camden_press_email import DEFAULT_SUBJECT, build_camden_compose_arg, write_camden_compose
from camden_press_filter import is_camden_actionable
from campaigns import get_campaign
from contacts import MediaContact, load_contacts, summarise
from intros import draft_hook_line, draft_london_ps
from llm_greeting import draft_greeting
from sent_examples import load_sent_hook_examples
from sync_sent import sent_mail_size, sync_and_mark, wait_for_send_or_done
from thunderbird_send import wait_and_send

THUNDERBIRD = Path("/Applications/Thunderbird.app/Contents/MacOS/thunderbird")
SendMode = Literal["auto", "manual", "stop"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numbers", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument(
        "--refresh-hooks",
        action="store_true",
        help="Regenerate LLM hooks (ignore Camden hook cache)",
    )
    parser.add_argument(
        "--refresh-greetings",
        action="store_true",
        help="Regenerate LLM greetings (ignore Camden greeting cache)",
    )
    parser.add_argument(
        "--auto-send-all",
        action="store_true",
        help="Skip first-contact review; auto-send every remaining contact",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Manual review for every contact (open in TB, you send, Enter for next)",
    )
    parser.add_argument(
        "--open-first",
        action="store_true",
        help="Open the first contact in Thunderbird and exit (no follow-up prompt)",
    )
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    return parser.parse_args()


def launch_compose(compose_arg: str) -> None:
    subprocess.run([str(THUNDERBIRD), "-compose", compose_arg], check=False)


def pending_contacts(numbers_path: Path) -> list[MediaContact]:
    return [c for c in load_contacts(numbers_path) if is_camden_actionable(c)]


def draft_contact_content(
    contact: MediaContact,
    *,
    campaign,
    use_llm: bool,
    hook_examples,
    refresh_hooks: bool,
    refresh_greetings: bool,
) -> tuple[str, str, str, str, str, str]:
    """Return greeting, greet_src, hook, hook_src, web_url, web_blurb."""
    web_url, web_blurb = "", ""
    if use_llm:
        web_url, web_blurb = contact_web_context(contact)
        if web_url:
            print(f"Website context: {web_url}")

    greeting, greet_src = draft_greeting(
        contact,
        use_llm=use_llm,
        use_cache=not refresh_greetings,
        web_url=web_url,
        web_blurb=web_blurb,
    )

    hook_line = ""
    hook_source = "none"
    if use_llm:
        hook_line, hook_source = draft_hook_line(
            contact,
            use_llm=True,
            examples=hook_examples,
            campaign_id=campaign.id,
            use_cache=not refresh_hooks,
            web_url=web_url,
            web_blurb=web_blurb,
        )
    return greeting, greet_src, hook_line, hook_source, web_url, web_blurb


def open_contact(
    contact: MediaContact,
    *,
    campaign,
    use_llm: bool,
    hook_examples,
    embed_poster: bool,
    auto_send: bool,
    dry_run: bool,
    refresh_hooks: bool = False,
    refresh_greetings: bool = False,
    greeting_addressee: str | None = None,
    hook_line: str | None = None,
) -> None:
    if greeting_addressee is None or hook_line is None:
        greeting, greet_src, hook, hook_src, _, _ = draft_contact_content(
            contact,
            campaign=campaign,
            use_llm=use_llm,
            hook_examples=hook_examples,
            refresh_hooks=refresh_hooks,
            refresh_greetings=refresh_greetings,
        )
        if greeting_addressee is None:
            greeting_addressee = greeting
        if hook_line is None:
            hook_line = hook
        print(f"Greeting: Hi {greeting_addressee} ({greet_src})")
        if hook_line:
            print(f"Hook ({hook_src}): {hook_line}")
    else:
        print(f"Greeting: Hi {greeting_addressee}")
        if hook_line:
            print(f"Hook: {hook_line}")

    print(f"\nRow {contact.row}: {contact.name} <{contact.email}>")
    print(f"Org: {contact.organisation}")

    html_path = campaign.compose_dir / f"row-{contact.row}.html"
    html_path, subject = write_camden_compose(
        html_path,
        contact,
        campaign,
        greeting_addressee=greeting_addressee or "there",
        hook_line=hook_line or "",
        embed_poster=embed_poster,
        include_instagram=True,
        london_ps=draft_london_ps(contact, campaign_id=campaign.id),
        subject=DEFAULT_SUBJECT,
    )
    compose_arg = build_camden_compose_arg(
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


def prompt_send_mode() -> SendMode:
    print("\nWhat next?")
    print("  [y] Auto-send remaining — opens each in Thunderbird, sends after ~3–4s")
    print("  [m] Manual review — open each contact; you edit/send, Enter for next")
    print("  [n] Stop here")
    while True:
        choice = input("[y/m/n] > ").strip().lower()
        if choice in {"y", "yes"}:
            return "auto"
        if choice in {"m", "manual"}:
            return "manual"
        if choice in {"n", "no", ""}:
            return "stop"


def confirm_contact_sent(
    contact: MediaContact,
    *,
    since_offset: int,
    campaign,
    numbers_path: Path,
    no_sync: bool,
    poll_seconds: float,
) -> bool:
    """Wait for send in Thunderbird; sync Numbers when detected. Returns True if sent."""
    try:
        outcome = wait_for_send_or_done(
            contact.email,
            since_offset=since_offset,
            poll_seconds=poll_seconds,
            subject_marker=campaign.subject_marker,
        )
    except KeyboardInterrupt:
        raise

    if not no_sync:
        sync_and_mark(
            numbers_path=numbers_path,
            state_path=campaign.sync_state,
            subject_marker=campaign.subject_marker,
        )

    if outcome == "sent":
        print(f"Sent detected for {contact.email}.")
        return True

    still_pending = any(
        c.email.lower() == contact.email.lower()
        for c in pending_contacts(numbers_path)
    )
    if still_pending:
        print(
            f"Send not detected yet for {contact.email} — moving on "
            "(row stays pending until Sent Mail sync catches it)."
        )
    return False


def pending_after_contact(numbers_path: Path, *, skip_email: str = "") -> list[MediaContact]:
    pending = pending_contacts(numbers_path)
    skip = skip_email.lower().strip()
    if skip:
        pending = [c for c in pending if c.email.lower() != skip]
    return pending


def run_auto_loop(
    pending: list[MediaContact],
    *,
    campaign,
    numbers_path: Path,
    args: argparse.Namespace,
    hook_examples,
) -> None:
    print(f"\nAuto-sending {len(pending)} contacts. Ctrl+C to stop.\n")
    while pending:
        contact = pending[0]
        watch_offset = sent_mail_size()
        open_contact(
            contact,
            campaign=campaign,
            use_llm=not args.no_llm,
            hook_examples=hook_examples,
            embed_poster=False,
            auto_send=not args.dry_run,
            dry_run=args.dry_run,
            refresh_hooks=args.refresh_hooks,
            refresh_greetings=args.refresh_greetings,
        )
        if args.dry_run:
            break
        try:
            confirm_contact_sent(
                contact,
                since_offset=watch_offset,
                campaign=campaign,
                numbers_path=numbers_path,
                no_sync=args.no_sync,
                poll_seconds=args.poll_seconds,
            )
        except KeyboardInterrupt:
            print("\nStopped.")
            return
        pending = pending_contacts(numbers_path)


def run_manual_loop(
    pending: list[MediaContact],
    *,
    campaign,
    numbers_path: Path,
    args: argparse.Namespace,
    hook_examples,
    embed_poster_first: bool = False,
) -> None:
    print(f"\nManual review — {len(pending)} contacts. Ctrl+C to stop.\n")
    first = True
    while pending:
        contact = pending[0]
        watch_offset = sent_mail_size()
        open_contact(
            contact,
            campaign=campaign,
            use_llm=not args.no_llm,
            hook_examples=hook_examples,
            embed_poster=embed_poster_first and first,
            auto_send=False,
            dry_run=args.dry_run,
            refresh_hooks=args.refresh_hooks,
            refresh_greetings=args.refresh_greetings,
        )
        first = False
        if args.dry_run:
            break
        try:
            confirm_contact_sent(
                contact,
                since_offset=watch_offset,
                campaign=campaign,
                numbers_path=numbers_path,
                no_sync=args.no_sync,
                poll_seconds=args.poll_seconds,
            )
        except KeyboardInterrupt:
            print("\nStopped.")
            return
        pending = pending_after_contact(numbers_path, skip_email=contact.email)
        if pending and pending[0].email.lower() == contact.email.lower():
            pending = pending[1:]


def main() -> int:
    args = parse_args()
    campaign = get_campaign("camden-press")
    numbers_path = args.numbers or campaign.default_numbers

    if not numbers_path.exists():
        print(f"Numbers file not found: {numbers_path}", file=sys.stderr)
        return 1

    print(f"Campaign: {campaign.label}")
    print(f"Poster: {campaign.poster_url} (~42KB email JPEG)")

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

    contacts = load_contacts(numbers_path)
    counts = summarise(contacts)
    pending = pending_contacts(numbers_path)
    print(
        f"List: sent={counts['sent']} skip={counts['skip']} pending={counts['pending']} "
        f"camden_actionable={len(pending)}"
    )
    if not pending:
        print("No actionable Camden contacts left.")
        return 0

    if not THUNDERBIRD.exists() and not args.dry_run:
        print(f"Thunderbird not found at {THUNDERBIRD}", file=sys.stderr)
        return 1

    hook_examples = None
    if not args.no_llm:
        hook_examples = load_sent_hook_examples()
        print(f"LLM hooks + greetings enabled ({len(hook_examples)} sent examples).")

    if args.auto_send_all:
        run_auto_loop(
            pending,
            campaign=campaign,
            numbers_path=numbers_path,
            args=args,
            hook_examples=hook_examples,
        )
        print("Done.")
        return 0

    if args.manual:
        run_manual_loop(
            pending,
            campaign=campaign,
            numbers_path=numbers_path,
            args=args,
            hook_examples=hook_examples,
            embed_poster_first=True,
        )
        print("Done.")
        return 0

    contact = pending[0]
    print("\nOpening first contact in Thunderbird for review (poster embedded for preview).")
    watch_offset = sent_mail_size()
    open_contact(
        contact,
        campaign=campaign,
        use_llm=not args.no_llm,
        hook_examples=hook_examples,
        embed_poster=True,
        auto_send=False,
        dry_run=args.dry_run,
        refresh_hooks=args.refresh_hooks,
        refresh_greetings=args.refresh_greetings,
    )
    if args.dry_run:
        return 0

    if args.open_first:
        print("Opened first contact in Thunderbird. When happy, run:")
        print("  python3 scripts/press_outreach/compose_camden.py")
        print("  (choose y/m/n when prompted)")
        print("Or skip review and auto-send everyone:")
        print("  python3 scripts/press_outreach/compose_camden.py --auto-send-all")
        print("Or manual review for all remaining:")
        print("  python3 scripts/press_outreach/compose_camden.py --manual")
        return 0

    try:
        confirm_contact_sent(
            contact,
            since_offset=watch_offset,
            campaign=campaign,
            numbers_path=numbers_path,
            no_sync=args.no_sync,
            poll_seconds=args.poll_seconds,
        )
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0

    mode = prompt_send_mode()
    if mode == "stop":
        print("Stopped after first preview.")
        return 0

    pending = pending_after_contact(numbers_path, skip_email=contact.email)

    if not pending:
        print("No remaining contacts (first may already be marked sent).")
        return 0

    if mode == "manual":
        run_manual_loop(
            pending,
            campaign=campaign,
            numbers_path=numbers_path,
            args=args,
            hook_examples=hook_examples,
        )
    else:
        run_auto_loop(
            pending,
            campaign=campaign,
            numbers_path=numbers_path,
            args=args,
            hook_examples=hook_examples,
        )

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
