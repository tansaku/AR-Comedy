#!/usr/bin/env python3
"""
Import Camden Fringe press-list PDF into an Apple Numbers contact file.

Usage:
  python3 scripts/press_outreach/import_camden_press_pdf.py \\
    ~/Downloads/CamdenFringePressList-07-31-2026-161647-7911.pdf

  python3 scripts/press_outreach/import_camden_press_pdf.py --dry-run path/to/list.pdf
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from camden_press_pdf import parse_camden_press_pdf, summarise_camden
from contacts import first_name_from

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "Camden Fringe 2026 Press List.numbers"
DEFAULT_CSV = REPO_ROOT / "data" / "camden-press-list-import.csv"

HEADERS = [
    "Name",
    "Email",
    "Organisation",
    "Job title",
    "Interests",
    "Country",
    "Consent",
    "Section",
    "Notes",
    "Contact URL",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Camden Fringe press list PDF")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _job_title(contact) -> str:
    parts = [contact.section]
    if contact.name and contact.organisation and contact.name != contact.organisation:
        parts.append(contact.name)
    return " · ".join(parts)


def _display_name(contact) -> str:
    if contact.name:
        if contact.organisation and contact.name != contact.organisation:
            return f"{contact.name} ({contact.organisation})"
        return contact.name
    return contact.organisation


def build_rows(contacts):
    rows = []
    for contact in contacts:
        rows.append(
            {
                "Name": _display_name(contact),
                "Email": contact.email,
                "Organisation": contact.organisation,
                "Job title": _job_title(contact),
                "Interests": ", ".join(contact.tags),
                "Country": "England",
                "Consent": "yes" if contact.email else "no",
                "Section": contact.section,
                "Notes": contact.notes,
                "Contact URL": contact.contact_url,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def write_numbers(path: Path, rows: list[dict[str, str]]) -> None:
    from numbers_parser import Document

    doc = Document()
    sheet = doc.sheets[0]
    table = sheet.tables[0]
    table.name = "Camden Press"

    for col, header in enumerate(HEADERS):
        table.write(0, col, header)

    for row_index, row in enumerate(rows, start=1):
        for col, header in enumerate(HEADERS):
            table.write(row_index, col, row.get(header, ""))

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def main() -> int:
    args = parse_args()
    if not args.pdf.exists():
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    contacts = parse_camden_press_pdf(args.pdf)
    counts = summarise_camden(contacts)
    rows = build_rows(contacts)

    print(f"Parsed {counts['total']} entries from {args.pdf.name}")
    print(
        f"  with_email={counts['with_email']} url_only={counts['url_only']} "
        f"comedy={counts['comedy']} sections={counts['sections']}"
    )

    actionable = [c for c in contacts if c.is_actionable]
    print(f"  actionable (have email)={len(actionable)}")

    if args.dry_run:
        print("\nFirst 10 with email:")
        for contact in actionable[:10]:
            print(f"  {contact.organisation} <{contact.email}> [{contact.section}]")
        if len(actionable) > 10:
            print(f"  ... and {len(actionable) - 10} more")
        return 0

    write_csv(args.csv, rows)
    write_numbers(args.out, rows)
    print(f"\nWrote CSV → {args.csv}")
    print(f"Wrote Numbers → {args.out}")
    print(
        "\nNext:\n"
        "  1. Open the Numbers file and skim url-only rows (no email)\n"
        "  2. Save a Camden Thunderbird template with CAMDEN_FRINGE_PRESS_RELEASE in the subject\n"
        "  3. python3 scripts/press_outreach/compose_next.py --campaign camden-press"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
