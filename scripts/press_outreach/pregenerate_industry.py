#!/usr/bin/env python3
"""
Pre-generate industry outreach drafts into Numbers (Outreach draft / AI fit columns).

Usage:
  python3 scripts/press_outreach/pregenerate_industry.py --campaign industry-uk
  python3 scripts/press_outreach/pregenerate_industry.py --campaign industry-uk --limit 10
  python3 scripts/press_outreach/pregenerate_industry.py --campaign industry-uk --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from campaigns import get_campaign
from industry_contacts import load_industry_contacts, summarise_industry
from industry_numbers import write_outreach_plan
from llm_industry import approach_to_storage, generate_industry_approach


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign",
        choices=("industry-uk", "industry-intl", "industry-agents", "industry"),
        default="industry-uk",
    )
    parser.add_argument("--numbers", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Regenerate even if draft exists")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign = get_campaign(args.campaign)
    if not campaign.industry_schema:
        print(f"Campaign {campaign.id} is not an industry campaign.", file=sys.stderr)
        return 1

    numbers_path = args.numbers or campaign.default_numbers
    if not numbers_path.exists():
        print(f"Numbers file not found: {numbers_path}", file=sys.stderr)
        return 1

    contacts, doc, outreach_cols = load_industry_contacts(
        numbers_path,
        schema=campaign.industry_schema,
        ensure_columns=True,
    )
    table = doc.sheets[0].tables[0]
    counts = summarise_industry(contacts)
    print(f"Campaign: {campaign.label}")
    print(f"File: {numbers_path.name}")
    print(
        f"Total={len(contacts)} in_town={counts['in_town']} "
        f"actionable={counts['actionable']} with_draft={counts['with_draft']}"
    )

    todo = [c for c in contacts if c.is_actionable]
    if not args.refresh:
        todo = [c for c in todo if not c.draft.strip() and not c.ai_fit.startswith("SKIP:")]
    if args.limit:
        todo = todo[: args.limit]

    print(f"To generate: {len(todo)}")
    if not todo:
        return 0

    if args.dry_run:
        for contact in todo[:10]:
            print(f"  row {contact.row}: {contact.name} <{contact.email}>")
        if len(todo) > 10:
            print(f"  ... and {len(todo) - 10} more")
        return 0

    ok = 0
    for index, contact in enumerate(todo, start=1):
        print(f"[{index}/{len(todo)}] {contact.name}...", flush=True)
        try:
            approach = generate_industry_approach(
                contact, audience=campaign.industry_audience
            )
            draft, fit, priority = approach_to_storage(approach)
            write_outreach_plan(
                table,
                contact.row,
                outreach_cols,
                draft=draft,
                ai_fit=fit,
                priority=priority,
            )
            print(f"  {priority}: {fit[:80]}")
            if draft:
                print(f"  hook: {draft[:100]}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}", file=sys.stderr)
            write_outreach_plan(
                table,
                contact.row,
                outreach_cols,
                draft="",
                ai_fit=f"SKIP: generation failed ({exc})",
                priority="error",
            )

    doc.save(str(numbers_path))
    print(f"Saved {ok}/{len(todo)} plans to {numbers_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
