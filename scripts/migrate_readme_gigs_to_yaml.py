#!/usr/bin/env python3
"""
One-off migration: README.md gig bullets -> _data/gigs.yml
Run from repo root: python3 scripts/migrate_readme_gigs_to_yaml.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

DATE_RE = re.compile(
    r"^\*\s*(?P<mon>\w+)\s+(?P<day>\d+)(?:st|nd|rd|th)?(?::)?\s*(?:\((?P<dow>[^)]+)\))?\s*(?P<rest>.+)$"
)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def month_key(name: str) -> int:
    key = name.strip().lower()[:3]
    if key not in MONTHS:
        raise ValueError(f"Unknown month: {name!r}")
    return MONTHS[key]


def infer_years(entries: list[tuple[int, int, str]]) -> list[tuple[int, int, int, str]]:
    """entries: (month, day, first_line) in document order (newest first)."""
    if not entries:
        return []
    year = 2025
    out: list[tuple[int, int, int, str]] = []
    prev_m: int | None = None
    for m, d, rest in entries:
        if prev_m is not None and m > prev_m:
            year -= 1
        out.append((year, m, d, rest))
        prev_m = m
    return out


def parse_first_line(rest: str) -> tuple[str, str | None, str | None]:
    """Return show, show_url, role_note (parenthetical after link, e.g. MC)."""
    rest = rest.strip()
    # [Title](url) or [Title](url) (MC) — avoid treating URL's closing ")" as a role
    m = re.match(
        r"^\[([^\]]+)\]\(([^)]+)\)(?:\s*\(([^)]+)\))?\s*$",
        rest,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip(), (
            m.group(3).strip() if m.group(3) else None
        )
    # Plain title with optional trailing (role)
    rm = re.search(r"\s+\(([^)]+)\)\s*$", rest)
    role = None
    if rm:
        role = rm.group(1).strip()
        rest = rest[: rm.start()].strip()
    return rest or "Gig", None, role


def parse_venue_line(line: str) -> tuple[str, str | None]:
    line = line.strip()
    if not line.startswith("- "):
        return line, None
    body = line[2:].strip()
    m = LINK_RE.fullmatch(body)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return body, None


def extract_bullets(text: str) -> list[list[str]]:
    """Return list of bullet blocks; each block is lines (first starts with *)."""
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("* "):
            if current:
                blocks.append(current)
            current = [line]
        elif current and (line.startswith("  ") or line.startswith("\t")):
            current.append(line)
        elif current and line == "":
            blocks.append(current)
            current = None
    if current:
        blocks.append(current)
    return blocks


def block_to_record(
    block: list[str], kind: str, year: int, month: int, day: int
) -> dict:
    first = block[0]
    m = DATE_RE.match(first)
    if not m:
        raise ValueError(f"Bad first line: {first!r}")
    rest = m.group("rest").strip()
    if rest.startswith("- "):
        rest = rest[2:].strip()
    show, show_url, role = parse_first_line(rest)
    detail_lines: list[str] = []
    schedule = None
    venue_text = None
    venue_map_url = None
    for ln in block[1:]:
        stripped = ln.strip()
        if not stripped.startswith("- "):
            continue
        inner = stripped[2:].strip()
        detail_lines.append(inner)
        low = inner.lower()
        if "doors" in low or low.startswith("show ") or inner.startswith("Show "):
            if schedule is None:
                schedule = inner
        elif venue_text is None and not re.match(r'^\d+m\s+"', inner):
            vt, vu = parse_venue_line(stripped)
            venue_text = vt
            venue_map_url = vu
    rec: dict = {
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "kind": kind,
        "show": show,
        "schedule": schedule,
        "venue": venue_text,
    }
    if show_url:
        rec["show_url"] = show_url
    if venue_map_url:
        rec["venue_map_url"] = venue_map_url
    if role:
        rec["role"] = role
    extras = [d for d in detail_lines if d != schedule and d != venue_text]
    if extras:
        rec["notes"] = extras
    return rec


def parse_section(content: str, kind: str) -> list[dict]:
    bullets = extract_bullets(content)
    parsed: list[tuple[int, int, str]] = []
    blocks_by_key: list[tuple[int, int, list[str]]] = []
    for block in bullets:
        m = DATE_RE.match(block[0])
        if not m:
            continue
        mon = month_key(m.group("mon"))
        day = int(m.group("day"))
        parsed.append((mon, day, block[0]))
        blocks_by_key.append((mon, day, block))
    dated = infer_years(parsed)
    records = []
    for (y, mo, d, _), (_, _, block) in zip(dated, blocks_by_key):
        records.append(block_to_record(block, kind, y, mo, d))
    return records


def yaml_quote(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def dump_gig_records(f, gigs: list[dict]) -> None:
    f.write("gigs:\n")
    for g in gigs:
        f.write("  -\n")
        for key in ("date", "kind", "show", "show_url", "role", "schedule", "venue", "venue_map_url"):
            if key in g and g[key] is not None:
                val = g[key]
                f.write(f"    {key}: {yaml_quote(str(val))}\n")
        if "notes" in g and g["notes"]:
            f.write("    notes:\n")
            for n in g["notes"]:
                f.write(f"      - {yaml_quote(str(n))}\n")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    if "Upcoming Gigs" not in readme or "Past Gigs" not in readme:
        print(
            "README.md no longer contains legacy sections (Upcoming Gigs / Past Gigs). "
            "Restore an old README from git history to re-run migration.",
            file=sys.stderr,
        )
        return 1
    parts = readme.split("Upcoming Gigs")
    if len(parts) < 2:
        print("Could not find Upcoming Gigs", file=sys.stderr)
        return 1
    after_up = parts[1]
    upcoming_chunk, after_up_rest = after_up.split("Find The AR Comedian", 1)
    past_part = after_up_rest.split("Upcoming Podcasts")[0]
    past_chunk = past_part.split("Past Gigs", 1)[1]

    bringer = readme.split("Gigs Attended as a Bringer")[1].split("# Gigs as Booker")[0]
    booker = readme.split("# Gigs as Booker")[1].split("# Cancelled or Withdrawn Gigs")[0]
    cancelled = readme.split("# Cancelled or Withdrawn Gigs")[1].split("# Terms and Conditions")[0]

    records: list[dict] = []
    records.extend(parse_section(upcoming_chunk, "performed"))
    records.extend(parse_section(past_chunk, "performed"))
    records.extend(parse_section(bringer, "bringer"))
    records.extend(parse_section(booker, "booker"))
    records.extend(parse_section(cancelled, "cancelled"))

    # De-dupe by (date, show, kind) keeping first occurrence (document order)
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for r in records:
        key = (r["date"], r["show"], r["kind"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    # Newest first (negative date int), then show name A–Z within the same day
    unique.sort(key=lambda x: (-int(x["date"].replace("-", "")), x["show"]))

    out_path = root / "_data" / "gigs.yml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(
            "# Gig list for Jekyll (comedy.neurogrid.com).\n"
            "# Newest dates first — add upcoming gigs near the top of the list.\n"
            "# kind: performed | booker | bringer | cancelled\n"
            "# Dates are ISO; upcoming vs archive uses site build time (GitHub Pages on push).\n\n"
        )
        dump_gig_records(f, unique)
    print(f"Wrote {len(unique)} gigs to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
