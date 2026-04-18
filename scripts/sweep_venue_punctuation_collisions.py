"""
Sweep api/venue_aliases.py for punctuation-only collisions — distinct
canonical venue strings that refer to the same physical ground,
differing only by punctuation (dots, commas, apostrophes, hyphens,
whitespace). The initial Phase 1 canonicalization missed these because
its heuristics matched on token-level prefix/suffix, not punctuation-
insensitive equality.

Run this periodically — especially after a big incremental import
pulls in cricsheet data that might introduce new punctuation variants
of existing grounds. Shouldn't fire often (new stadiums are rare) but
catching one "M.Chinnaswamy Stadium" vs "M Chinnaswamy Stadium" split
is worth the rerun.

Strategy per canonical (venue, city, country) tuple:
  1. Compute a `slug` by lower-casing, replacing every non-[a-z0-9]
     character with a single space, collapsing whitespace.
  2. Strip the canonical_city off the tail of the slug if present
     (so "m chinnaswamy stadium bengaluru" → "m chinnaswamy stadium").
  3. Group by (slug_base, country).
  4. Any group with >1 distinct canonical venue is a merge candidate.

Output: lists candidate groups to stdout, with per-canonical match
counts, so the user can decide which to merge. Does NOT modify
anything — the actual merge is a manual (`api/venue_aliases.py` edit
or /tmp fix script) + `scripts/fix_venue_names.py` retrofit.

Usage:
    uv run python scripts/sweep_venue_punctuation_collisions.py
"""

from __future__ import annotations

import ast
import csv
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALIASES_PY = REPO_ROOT / "api" / "venue_aliases.py"
WORKLIST_DIR = REPO_ROOT / "docs" / "venue-worklist"

SPACE_RE = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    return SPACE_RE.sub(" ", s.lower()).strip()


def strip_city_suffix(slug: str, city: str | None) -> str:
    if not city:
        return slug
    city_slug = slugify(city)
    if slug.endswith(" " + city_slug):
        return slug[: -len(city_slug) - 1].strip()
    return slug


ENTRY_RE = re.compile(r"^\s*(\([^)]+\))\s*:\s*(\([^)]+\))\s*,\s*$")


def parse_alias_entries() -> list[tuple[tuple, tuple]]:
    out: list[tuple[tuple, tuple]] = []
    for line in ALIASES_PY.read_text().splitlines():
        m = ENTRY_RE.match(line)
        if not m:
            continue
        try:
            key = ast.literal_eval(m.group(1))
            val = ast.literal_eval(m.group(2))
        except (ValueError, SyntaxError):
            continue
        if not (isinstance(key, tuple) and isinstance(val, tuple) and len(val) == 3):
            continue
        out.append((key, val))
    return out


def load_latest_worklist_counts() -> dict[tuple[str, str], int]:
    """Pull (raw_venue, raw_city) → match_count from the most recent
    worklist CSV, for showing per-canonical match totals in the output."""
    if not WORKLIST_DIR.exists():
        return {}
    csvs = sorted(p for p in WORKLIST_DIR.iterdir() if p.name.endswith("-worklist.csv"))
    if not csvs:
        return {}
    counts: dict[tuple[str, str], int] = {}
    with open(csvs[-1]) as f:
        for r in csv.DictReader(f):
            counts[(r["raw_venue"], r["raw_city"] or "")] = int(r["match_count"])
    return counts


def main():
    entries = parse_alias_entries()
    print(f"Parsed {len(entries)} alias entries from {ALIASES_PY.relative_to(REPO_ROOT)}")

    counts = load_latest_worklist_counts()

    canonicals: set[tuple[str, str, str]] = set()
    for _, (cv, cc, country) in entries:
        canonicals.add((cv, cc, country))

    groups: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for (cv, cc, country) in canonicals:
        slug = strip_city_suffix(slugify(cv), cc)
        groups[(slug, country)].append((cv, cc, country))

    candidates = [(k, vs) for k, vs in groups.items() if len(vs) > 1]
    candidates.sort(key=lambda kv: (kv[0][1], kv[0][0]))

    if not candidates:
        print("\nNo punctuation-collision candidates found. ✓")
        return

    print(f"\nFound {len(candidates)} merge-candidate group(s):\n")
    for (slug, country), vs in candidates:
        canon_match_count: dict[str, int] = defaultdict(int)
        for (raw_v, raw_c), (cv, cc, _) in entries:
            if (cv, cc, country) in vs:
                canon_match_count[cv] += counts.get((raw_v, raw_c), 0)
        print(f"  [{country}] base slug: {slug!r}")
        for (cv, cc, _) in sorted(vs):
            print(f"    {canon_match_count[cv]:5d} matches  {cv!r} (city={cc!r})")
        print()

    print("To resolve: pick the preferred canonical per group, edit the")
    print("losing canonical's entries in api/venue_aliases.py so their")
    print("VALUE tuple points to the winner, then rerun")
    print("scripts/fix_venue_names.py to retrofit the DB.")


if __name__ == "__main__":
    main()
