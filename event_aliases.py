"""
Canonical tournament-name mapping.

Some cricket competitions appear in the database under multiple
`event_name` strings because they were rebranded across sponsorship
deals. The competition is the same — same teams, same league
structure, same continuity of records — only the sponsor name on the
trophy changed. This module is the single source of truth that
collapses each chain of sponsor rebrands into one canonical name.

Used by:
- import_data.py — apply on insert so the database is clean from the start
- update_recent.py — same (via the shared import_match_file function)
- scripts/fix_event_names.py — one-time pass over the existing database

Same conservative principle as team_aliases.py: only merge when the
competition has continuous history across the rename. Don't merge
genuinely separate competitions just because they're "similar."
"""

EVENT_ALIASES: dict[str, str] = {
    # ─── English domestic men's T20 ─────────────────────────────────
    # NatWest sponsored 2014-2017, then Vitality from 2018+. Cricsheet
    # added 'Men' as a disambiguator in 2025 but there's no women's
    # Vitality Blast in the DB — collapse the disambiguator back.
    "NatWest T20 Blast": "Vitality Blast",
    "Vitality Blast Men": "Vitality Blast",

    # ─── South African domestic men's T20 ──────────────────────────
    # MiWAY (2011/12) → Ram Slam (2012/13-2017/18) → CSA (2016/17+)
    "MiWAY T20 Challenge": "CSA T20 Challenge",
    "Ram Slam T20 Challenge": "CSA T20 Challenge",

    # ─── New Zealand domestic men's T20 ────────────────────────────
    # The HRV-sponsored era is tiny in the DB (4 matches total) but
    # rolling them in keeps the tournament unified.
    "HRV Cup": "Super Smash",
    "HRV Twenty20": "Super Smash",
}


def canonicalize(name: str | None) -> str | None:
    """Return the canonical tournament name for `name`, or `name` unchanged."""
    if not name:
        return name
    return EVENT_ALIASES.get(name, name)
