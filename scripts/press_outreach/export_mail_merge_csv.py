#!/usr/bin/env python3
"""
Export pending press contacts to a Mail Merge CSV for Thunderbird.

Usage (from repo root):
  pip install numbers-parser
  python3 scripts/press_outreach/export_mail_merge_csv.py
  python3 scripts/press_outreach/export_mail_merge_csv.py --limit 10
  python3 scripts/press_outreach/export_mail_merge_csv.py --include-sent

Thunderbird Mail Merge template (compose once, then Tools → Mail Merge):
  To:      {{Email}}
  Subject: ED FRINGE PRESS RELEASE: I Think I'm Turning Japanese (I Really Think So, NOT!)
  Body:
    Hi {{FirstName}},

    {{Intro}}

    {{LondonNote}}

    [paste your press release block below — same as your current template]

  Deliver mode: Send Later  →  messages land in Local Folders → Outbox for review
  Then: File → Send Unsent Messages (or open and send individually)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contacts import DEFAULT_NUMBERS_PATH, load_contacts, summarise
from intros import draft_intro, draft_london_note

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "press-outreach-mail-merge.csv"
DEFAULT_MANIFEST = REPO_ROOT / "data" / "press-outreach-manifest.json"

CSV_FIELDS = [
    "Row",
    "Email",
    "FirstName",
    "Name",
    "Organisation",
    "Country",
    "Interests",
    "Intro",
    "LondonNote",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--numbers",
        type=Path,
        default=DEFAULT_NUMBERS_PATH,
        help="Path to the Apple Numbers contact list",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="CSV output path for Thunderbird Mail Merge",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="JSON sidecar with export metadata and row mapping",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max contacts to export (0 = all actionable)",
    )
    parser.add_argument(
        "--include-sent",
        action="store_true",
        help="Include yellow (already sent) rows — useful for re-export/testing",
    )
    parser.add_argument(
        "--include-skip",
        action="store_true",
        help="Include orange (skipped) rows",
    )
    return parser.parse_args()


def select_contacts(args: argparse.Namespace):
    contacts = load_contacts(args.numbers)
    selected = []
    for contact in contacts:
        if contact.status == "sent" and not args.include_sent:
            continue
        if contact.status == "skip" and not args.include_skip:
            continue
        if contact.status == "pending" and not contact.is_actionable:
            continue
        selected.append(contact)
    if args.limit:
        selected = selected[: args.limit]
    return contacts, selected


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.numbers.exists():
        print(f"Numbers file not found: {args.numbers}", file=sys.stderr)
        return 1

    all_contacts, selected = select_contacts(args)
    counts = summarise(all_contacts)

    rows = []
    for contact in selected:
        rows.append(
            {
                "Row": str(contact.row),
                "Email": contact.email,
                "FirstName": contact.first_name,
                "Name": contact.name,
                "Organisation": contact.organisation,
                "Country": contact.country,
                "Interests": contact.interests,
                "Intro": draft_intro(contact),
                "LondonNote": draft_london_note(contact),
            }
        )

    write_csv(args.out, rows)
    write_manifest(
        args.manifest,
        {
            "source_numbers": str(args.numbers),
            "exported_count": len(rows),
            "summary": counts,
            "rows": [int(row["Row"]) for row in rows],
        },
    )

    print(f"Wrote {len(rows)} contacts → {args.out}")
    print(f"Manifest → {args.manifest}")
    print(
        "List status:",
        f"sent={counts['sent']}",
        f"skip={counts['skip']}",
        f"pending={counts['pending']}",
        f"actionable={counts['actionable']}",
    )
    print("\nNext: open the CSV, tweak Intro/LondonNote columns, then run Mail Merge in Thunderbird.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
