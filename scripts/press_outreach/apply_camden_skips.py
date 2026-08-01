#!/usr/bin/env python3
"""Mark non-relevant Camden press rows orange and fix a few PDF parse quirks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from camden_press_filter import camden_skip_reason
from campaigns import get_campaign
from contacts import load_contacts
from numbers_style import mark_row_skip
from numbers_parser import Document

EMAIL_FIXUPS: dict[str, tuple[str, str]] = {
    "chanel@itgirlworld.co.uk": ("It Girl World", "Chanel Williams"),
    "info@londontheatrereviews.co.uk": ("London Theatre Reviews", ""),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numbers", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign = get_campaign("camden-press")
    numbers_path = args.numbers or campaign.default_numbers
    if not numbers_path.exists():
        print(f"Numbers file not found: {numbers_path}", file=sys.stderr)
        return 1

    contacts = load_contacts(numbers_path)
    doc = Document(str(numbers_path))
    table = doc.sheets[0].tables[0]
    skipped = 0
    fixed = 0

    for contact in contacts:
        if contact.email.lower() in EMAIL_FIXUPS:
            org, name = EMAIL_FIXUPS[contact.email.lower()]
            if not args.dry_run:
                table.write(contact.row, 2, org)
                display = f"{name} ({org})" if name else org
                table.write(contact.row, 0, display)
            print(f"Fix row {contact.row}: {contact.email} → {org}")
            fixed += 1
            continue

        reason = camden_skip_reason(contact)
        if reason and contact.status == "pending":
            print(f"Skip row {contact.row}: {contact.organisation} — {reason}")
            if not args.dry_run:
                mark_row_skip(doc, table, contact.row)
            skipped += 1

    if not args.dry_run and (skipped or fixed):
        doc.save(str(numbers_path))

    print(f"\nFixed {fixed} mis-parsed rows; marked {skipped} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
