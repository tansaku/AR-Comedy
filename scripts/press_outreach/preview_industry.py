#!/usr/bin/env python3
"""
Preview AI-generated industry outreach emails from Numbers.

Usage:
  python3 scripts/press_outreach/preview_industry.py --campaign industry-uk
  python3 scripts/press_outreach/preview_industry.py --campaign industry-uk --row 5
  python3 scripts/press_outreach/preview_industry.py --campaign industry-uk --limit 5
  python3 scripts/press_outreach/preview_industry.py --campaign industry-uk --html
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from campaigns import get_campaign
from industry_contacts import IndustryContact, load_industry_contacts, summarise_industry
from industry_email import DEFAULT_SUBJECT, build_industry_html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign",
        choices=("industry-uk", "industry-intl", "industry-agents", "industry"),
        default="industry-uk",
    )
    parser.add_argument("--numbers", type=Path, default=None)
    parser.add_argument("--row", type=int, default=0, help="Preview one Numbers row")
    parser.add_argument("--limit", type=int, default=10, help="Max contacts to show (0 = all)")
    parser.add_argument(
        "--include-skip",
        action="store_true",
        help="Also show rows marked SKIP in AI fit",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Write HTML previews and open the first in your browser",
    )
    parser.add_argument(
        "--html-dir",
        type=Path,
        default=None,
        help="Where to write HTML previews (default: data/.industry-preview/)",
    )
    return parser.parse_args()


def _contacts_with_drafts(contacts: list[IndustryContact], *, include_skip: bool):
    for contact in contacts:
        if contact.draft.strip():
            yield contact
            continue
        if include_skip and contact.ai_fit.startswith("SKIP:"):
            yield contact


def format_terminal_preview(contact: IndustryContact) -> str:
    subject = contact.subject.strip() or DEFAULT_SUBJECT
    lines = [
        "",
        "─" * 72,
        f"Row {contact.row}: {contact.name} <{contact.email}>",
        f"{contact.organisation} · {contact.job_title}",
        f"In town: {contact.in_town_start} – {contact.in_town_end}",
        f"Priority: {contact.priority} · {contact.ai_fit}",
        "",
        f"Subject: {subject}",
        "",
        f"Hi {contact.first_name},",
        "",
        contact.draft or "(no body — skipped)",
        "",
        "Best,",
        "Sam Joseph",
        "─" * 72,
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    campaign = get_campaign(args.campaign)
    numbers_path = args.numbers or campaign.default_numbers

    if not numbers_path.exists():
        print(f"Numbers file not found: {numbers_path}", file=sys.stderr)
        return 1

    contacts, _, _ = load_industry_contacts(
        numbers_path,
        schema=campaign.industry_schema or "programmer",
    )
    counts = summarise_industry(contacts)
    print(f"{campaign.label} — {numbers_path.name}")
    print(
        f"drafts={counts['with_draft']} ready={counts.get('ready', 0)} "
        f"in_town={counts['in_town']} sent={counts['sent']} skip={counts['skip']}"
    )

    if args.row:
        matches = [c for c in contacts if c.row == args.row]
        if not matches:
            print(f"No contact at row {args.row}", file=sys.stderr)
            return 1
        selected = matches
    else:
        selected = list(_contacts_with_drafts(contacts, include_skip=args.include_skip))
        if args.limit:
            selected = selected[: args.limit]

    if not selected:
        print("No drafts yet — pregeneration may still be running.")
        print(f"Tail the log: data/.industry-pregenerate.log")
        return 0

    html_dir = args.html_dir or (Path(__file__).resolve().parents[2] / "data" / ".industry-preview")
    first_html: Path | None = None

    for contact in selected:
        print(format_terminal_preview(contact))
        if args.html and contact.draft.strip():
            html_dir.mkdir(parents=True, exist_ok=True)
            html = build_industry_html(contact, campaign, body=contact.draft)
            path = html_dir / f"{campaign.id}-row-{contact.row}.html"
            path.write_text(html, encoding="utf-8")
            print(f"HTML: {path}")
            if first_html is None:
                first_html = path

    if first_html:
        webbrowser.open(first_html.as_uri())
        print(f"\nOpened {first_html} in your browser.")

    if not args.row and len(selected) < counts["with_draft"]:
        remaining = counts["with_draft"] - len(selected)
        print(f"\n… and {remaining} more with drafts. Use --limit 0 to show all, or --row N for one.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
