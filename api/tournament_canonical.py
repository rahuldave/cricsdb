"""Canonical tournament map — shared by filters + tournaments router.

Cricsheet's `event_name` drifts across eras. The Men's T20 World Cup
exists under three names. The Women's T20 World Cup under three. This
module owns the merge map so that filters.py can transparently expand
`tournament=<canonical>` into `event_name IN (variants)` on every
endpoint in the system. That keeps the entire FilterBar coherent:
picking "T20 World Cup (Men)" narrows Teams, Batting, Bowling,
Fielding, Matches, and Tournaments identically — and baselines (e.g.
"avg bowling powerplay across teams in IPL 2024") aggregate over the
full merged scope without needing callers to know about variants.
"""

from __future__ import annotations


# Canonical display name → list of cricsheet event_name variants.
# Single-variant tournaments are absent (resolved by identity).
TOURNAMENT_CANONICAL: dict[str, list[str]] = {
    "T20 World Cup (Men)": [
        "ICC World Twenty20",        # 2007/08 – 2012/13
        "World T20",                 # 2013/14 – 2015/16
        "ICC Men's T20 World Cup",   # 2021/22 – present
    ],
    "T20 World Cup (Women)": [
        "ICC Women's World Twenty20",
        "Women's World T20",
        "ICC Women's T20 World Cup",
    ],
}

# Series-type classification, keyed by canonical name. Drives the
# tournaments landing's section bucketing. Unlisted items default to
# 'other'.
TOURNAMENT_SERIES_TYPE: dict[str, str] = {
    # ICC / continental events (men)
    "T20 World Cup (Men)": "icc_event",
    "ICC Men's T20 World Cup Qualifier": "icc_event",
    "ACC Men's Premier Cup": "icc_event",
    "Asia Cup": "icc_event",

    # ICC / continental events (women)
    "T20 World Cup (Women)": "icc_event",
    "ICC Women's T20 World Cup Qualifier": "icc_event",
    "Women's Asia Cup": "icc_event",
    "ICC Women's Emerging Nations Trophy": "icc_event",

    # Men's franchise leagues
    "Indian Premier League": "franchise_league",
    "Big Bash League": "franchise_league",
    "Pakistan Super League": "franchise_league",
    "Bangladesh Premier League": "franchise_league",
    "Caribbean Premier League": "franchise_league",
    "SA20": "franchise_league",
    "International League T20": "franchise_league",
    "Lanka Premier League": "franchise_league",
    "Major League Cricket": "franchise_league",
    "Nepal Premier League": "franchise_league",
    "The Hundred Men's Competition": "franchise_league",
    "Super Smash": "franchise_league",

    # Men's domestic leagues
    "Vitality Blast": "domestic_league",
    "Syed Mushtaq Ali Trophy": "domestic_league",
    "CSA T20 Challenge": "domestic_league",

    # Women's franchise leagues
    "Women's Big Bash League": "women_franchise",
    "Women's Premier League": "women_franchise",
    "The Hundred Women's Competition": "women_franchise",
    "Women's Cricket Super League": "women_franchise",
    "Women's Super Smash": "women_franchise",
}

ICC_EVENT_NAMES: frozenset[str] = frozenset({
    name for name, t in TOURNAMENT_SERIES_TYPE.items() if t == "icc_event"
})

# Default rivalry grid — 9 full-member men's teams. C(9,2) = 36 pairs.
BILATERAL_TOP_TEAMS: list[str] = [
    "India", "Pakistan", "Bangladesh", "South Africa",
    "England", "Australia", "New Zealand", "Sri Lanka", "West Indies",
]

# Reverse lookup: cricsheet event_name → canonical display name.
_EVENT_TO_CANONICAL: dict[str, str] = {
    variant: canonical
    for canonical, variants_list in TOURNAMENT_CANONICAL.items()
    for variant in variants_list
}


def canonicalize(event_name: str | None) -> str | None:
    """Return the canonical display name for a cricsheet event_name."""
    if event_name is None:
        return None
    return _EVENT_TO_CANONICAL.get(event_name, event_name)


def variants(canonical: str) -> list[str]:
    """Return cricsheet event_name variants for a canonical display name.

    Single-variant tournaments (no drift) return [canonical].
    """
    return TOURNAMENT_CANONICAL.get(canonical, [canonical])


def is_canonical_with_variants(name: str) -> bool:
    """True iff `name` is a canonical that expands to multiple cricsheet
    event_names. Used by filters.py to decide between `= :tournament`
    and `IN (...)` clauses.
    """
    return name in TOURNAMENT_CANONICAL


def event_name_in_clause(names: list[str], col: str = "m.event_name") -> str:
    """Build a safe `{col} IN (...)` clause for hardcoded event names.

    Single quotes doubled for SQL escaping. Inputs come from hardcoded
    dicts; not safe for user-supplied values.
    """
    if not names:
        return f"{col} IN ('')"
    escaped = ",".join("'" + n.replace("'", "''") + "'" for n in names)
    return f"{col} IN ({escaped})"


def series_type(canonical: str) -> str:
    """Classify a canonical name into a landing-page bucket."""
    return TOURNAMENT_SERIES_TYPE.get(canonical, "other")


def series_type_clause(series_type_value: str | None, alias: str = "m") -> str | None:
    """Build a clause to narrow matches by series category.

    Four mutually-exclusive categories that together partition the data:

    - `bilateral` — international bilateral T20Is. team_type='international'
      AND event_name not in ICC events (so things like
      "England tour of West Indies" or NULL event_name).
    - `icc` — international ICC events. event_name in {T20 World Cup
      (Men/Women), Asia Cup, Women's Asia Cup, qualifiers, …}.
    - `club` — franchise + domestic club tournaments. team_type='club'.
    - `all` (or None / unrecognized) — no clause.

    Legacy names `bilateral_only` and `tournament_only` map to
    `bilateral` and `icc` respectively for URL-bookmark compat, with
    one semantic difference: the old `bilateral_only` ALSO included
    club matches (everything-not-ICC); the new `bilateral` is
    international-only. The old name was confusing — "club matchups
    showing under bilateral" — so we tightened the definition.

    Lives here (not in routers/tournaments.py) so head_to_head and
    other routers can import it without depending on the tournaments
    router.
    """
    # Legacy name aliases for back-compat
    if series_type_value == "bilateral_only":
        series_type_value = "bilateral"
    elif series_type_value == "tournament_only":
        series_type_value = "icc"

    if series_type_value not in ("bilateral", "icc", "club"):
        return None

    icc_variants: list[str] = []
    for canon in ICC_EVENT_NAMES:
        icc_variants.extend(variants(canon))
    icc_in = event_name_in_clause(icc_variants, col=f"{alias}.event_name")

    if series_type_value == "bilateral":
        # International AND not in ICC events
        return f"({alias}.team_type = 'international' AND ({alias}.event_name IS NULL OR NOT {icc_in}))"
    if series_type_value == "icc":
        return icc_in
    # series_type_value == "club"
    return f"{alias}.team_type = 'club'"
