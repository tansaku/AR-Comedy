#!/usr/bin/env python3
"""Repair full-row sent/skip highlights on a Numbers contact list."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from campaigns import get_campaign
from sync_sent import repair_row_highlights


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default="press")
    parser.add_argument("--numbers", type=Path, default=None)
    args = parser.parse_args()
    campaign = get_campaign(args.campaign)
    path = args.numbers or campaign.default_numbers
    updated = repair_row_highlights(path)
    print(f"Repaired {updated} rows in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
