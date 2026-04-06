"""
Canonical team-name mapping.

Cricket franchises rename themselves periodically. Cricsheet records the
team name that was current when each match was played, so the same
franchise appears in the database under multiple names depending on the
season. This module is the single source of truth that collapses each
chain of renames into one canonical (latest) name.

Used by:
- import_data.py — apply on insert so the database is clean from the start
- update_recent.py — same (via the shared import_match_file function)
- scripts/fix_team_names.py — one-time pass over the existing database

Conservative principle: only merge when (a) the franchise has continuous
ownership across the rename and (b) the rename is well-attested. Teams
that were dissolved and replaced by a different ownership group with a
similar city name are NOT merged (e.g. Antigua Hawksbills 2013-14 vs
Antigua and Barbuda Falcons 2024 — 10-year gap, different franchise).
"""

TEAM_ALIASES: dict[str, str] = {
    # ─── IPL ────────────────────────────────────────────────────────
    "Kings XI Punjab": "Punjab Kings",                       # rebranded 2021
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",  # 2024 rebrand
    "Delhi Daredevils": "Delhi Capitals",                    # rebranded 2018
    "Rising Pune Supergiant": "Rising Pune Supergiants",     # 2017 dropped the 's'; collapse to the 2016 spelling

    # ─── CPL ────────────────────────────────────────────────────────
    "Barbados Tridents": "Barbados Royals",                  # rebranded 2021
    "St Lucia Zouks": "St Lucia Kings",                      # rebranded 2021 (same franchise)
    # Note: St Lucia Stars (2017-2018) is a SEPARATE one-season franchise, NOT merged.
    "Trinidad & Tobago Red Steel": "Trinbago Knight Riders", # rebranded 2016 when KKR took over

    # ─── ILT20 ──────────────────────────────────────────────────────
    "Sharjah Warriors": "Sharjah Warriorz",                  # 2024 z-spelling change

    # ─── Nepal Premier League ──────────────────────────────────────
    "Kathmandu Gorkhas": "Kathmandu Gurkhas",                # standard English spelling

    # ─── Lanka Premier League ──────────────────────────────────────
    # Each city slot has had multiple sponsor-driven rebrands. We map
    # all old names to the latest (most recent season) canonical name.
    "Jaffna Stallions": "Jaffna Kings",                      # 2020 → 2021+
    "Galle Gladiators": "Galle Marvels",                     # 2020-2022
    "Galle Titans": "Galle Marvels",                         # 2023
    "Kandy Tuskers": "Kandy Falcons",                        # 2020
    "Kandy Warriors": "Kandy Falcons",                       # 2021
    "B-Love Kandy": "Kandy Falcons",                         # 2023 (brief sponsor rename)
    "Colombo Kings": "Colombo Strikers",                     # 2020
    "Colombo Stars": "Colombo Strikers",                     # 2021-2022
    "Dambulla Viiking": "Dambulla Sixers",                   # 2020 (sic, Viiking with double i)
    "Dambulla Giants": "Dambulla Sixers",                    # 2021
    "Dambulla Aura": "Dambulla Sixers",                      # 2022-2023
}


def canonicalize(name: str | None) -> str | None:
    """Return the canonical team name for `name`, or `name` unchanged."""
    if not name:
        return name
    return TEAM_ALIASES.get(name, name)
