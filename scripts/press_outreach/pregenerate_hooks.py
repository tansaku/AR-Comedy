#!/usr/bin/env python3
"""
Pre-generate LLM hook lines for pending press contacts (overnight batch).

Reads sent-email hooks as few-shot examples, then calls OpenRouter for each
actionable contact not already in the hook cache.

Usage:
  python3 scripts/press_outreach/pregenerate_hooks.py
  python3 scripts/press_outreach/pregenerate_hooks.py --limit 20
  python3 scripts/press_outreach/pregenerate_hooks.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contacts import DEFAULT_NUMBERS_PATH, load_contacts, summarise
from llm_hook import HOOK_CACHE_PATH, _load_hook_cache, generate_hook_llm, openrouter_configured
from sent_examples import load_sent_hook_examples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numbers", type=Path, default=DEFAULT_NUMBERS_PATH)
    parser.add_argument("--limit", type=int, default=0, help="Max contacts to generate (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="List contacts only; no API calls")
    parser.add_argument(
        "--refresh-examples",
        action="store_true",
        help="Rescan Sent Mail for hook examples (slow; default uses cache)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not openrouter_configured():
        print("OPENROUTER_API_KEY not set — add it to .env", file=sys.stderr)
        return 1

    contacts = load_contacts(args.numbers)
    counts = summarise(contacts)
    pending = [c for c in contacts if c.is_actionable]
    cache = _load_hook_cache()
    todo = [c for c in pending if c.email.lower() not in cache]
    if args.limit:
        todo = todo[: args.limit]

    print(
        f"Actionable={counts['actionable']} cached={len(cache)} "
        f"to_generate={len(todo)}"
    )
    if not todo:
        print("Nothing to do — all actionable contacts already cached.")
        return 0

    print("Loading sent hook examples...")
    examples = load_sent_hook_examples(refresh=args.refresh_examples)
    print(f"Few-shot examples: {len(examples)}")

    if args.dry_run:
        for contact in todo[:10]:
            print(f"  row {contact.row}: {contact.name} <{contact.email}>")
        if len(todo) > 10:
            print(f"  ... and {len(todo) - 10} more")
        return 0

    ok = 0
    for index, contact in enumerate(todo, start=1):
        try:
            hook = generate_hook_llm(contact, examples=examples, use_cache=True)
            print(f"[{index}/{len(todo)}] {contact.name}: {hook}")
            ok += 1
        except Exception as exc:  # noqa: BLE001 — batch job should continue on one failure
            print(f"[{index}/{len(todo)}] {contact.email} FAILED: {exc}", file=sys.stderr)

    print(f"Done: {ok}/{len(todo)} hooks cached at {HOOK_CACHE_PATH}")
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    raise SystemExit(main())
