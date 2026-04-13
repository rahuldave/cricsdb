"""
Canonical fielder-name mapping.

Cricsheet's wicket.fielders stores names that sometimes don't match any
person.name or personname.name in the registry. This module maps those
unmatched fielder names to the canonical person.name so the
fielding_credit table can resolve fielder_id.

Same pattern as team_aliases.py. The population script tries direct
lookup first, then falls back to this mapping. Names that map to None
are genuinely unresolvable (~42 cases).

This mapping is populated incrementally — run populate_fielding_credits.py
with --show-unmatched to discover new entries.
"""

FIELDER_ALIASES: dict[str, str | None] = {
    # ─── Married-name changes ──────────────────────────────────────
    "NR Sciver-Brunt": "NR Sciver",
    "KH Sciver-Brunt": "KH Brunt",
    "L Winfield-Hill": "L Winfield",
    "AE Jones-Mayall": "AE Jones",
    "JL Gunn-Jones": "JL Gunn",
    "EA Perry-Mayall": "EA Perry",

    # ─── Disambiguated names (cricsheet parenthetical suffix) ──────
    "Mohammad Nawaz (3)": "Mohammad Nawaz",
    "Imran Khan (1)": "Imran Khan",
    "Imran Khan (2)": "Imran Khan",
    "Mohammad Hasnain (2)": "Mohammad Hasnain",
    "Mohammad Nabi (2)": "Mohammad Nabi",
    "Mohammad Wasim (2)": "Mohammad Wasim",
    "Sandeep Sharma (2)": "Sandeep Sharma",
    "Shahid Afridi (2)": "Shahid Afridi",

    # ─── Minor spelling / transliteration variants ─────────────────
    "Fakhar-e-Alam": "Fakhar e Alam",
    "Sai Sudharsan": "B Sai Sudharsan",
}


def resolve_fielder_name(name: str) -> str | None:
    """Return the canonical person.name for a fielder, or the name itself
    if no alias exists. Returns None only if explicitly mapped to None."""
    return FIELDER_ALIASES.get(name, name)
