"""Club-tier classification — used by the FilterBar `team_class`
pill (`primary_club` / `secondary_club` values) and a future Teams
landing-page split.

Two tiers, partitioning every cricsheet club T20 `event_name` exactly
once:

  - PRIMARY_CLUB_LEAGUES — marquee international franchise leagues
    with auction-driven full-member overseas rosters (IPL, BBL, PSL,
    BPL, CPL, SA20, ILT20, LPL, MLC, The Hundred, plus the four
    women's franchise leagues).

  - SECONDARY_CLUB_LEAGUES — domestic state / county / provincial
    competitions and small-market franchises (Vitality Blast, Syed
    Mushtaq Ali Trophy, CSA T20 Challenge, Super Smash, Nepal Premier
    League, plus the two NZ women's provincial event_names).

Rationale + the marquee-international principle behind each
classification:
`internal_docs/club-tier-classification.md`. Spec:
`internal_docs/spec-filterbar-team-class-club.md`. DB-derived
anchors: `internal_docs/club-tier-anchor-numbers.md`.

Structurally analogous to api/full_members.py — a frozenset of
trusted hardcoded names + a clause builder that interpolates safely.
"""

from __future__ import annotations


PRIMARY_CLUB_LEAGUES: frozenset[str] = frozenset({
    "Indian Premier League",
    "Big Bash League",
    "Pakistan Super League",
    "Bangladesh Premier League",
    "Caribbean Premier League",
    "SA20",
    "International League T20",
    "Lanka Premier League",
    "Major League Cricket",
    "The Hundred Men's Competition",
    "Women's Big Bash League",
    "Women's Premier League",
    "The Hundred Women's Competition",
    "Women's Cricket Super League",
})


SECONDARY_CLUB_LEAGUES: frozenset[str] = frozenset({
    "Vitality Blast",
    "Syed Mushtaq Ali Trophy",
    "CSA T20 Challenge",
    "Super Smash",
    "Nepal Premier League",
    "Women's Super Smash",
    "New Zealand Cricket Women's Twenty20",
})


# Disjointness invariant — caught at import so a future contributor
# slotting a league into both sets fails fast, before the silent
# no-op surfaces in production.
assert PRIMARY_CLUB_LEAGUES & SECONDARY_CLUB_LEAGUES == frozenset(), (
    "PRIMARY_CLUB_LEAGUES and SECONDARY_CLUB_LEAGUES must be disjoint;"
    f" intersection: {PRIMARY_CLUB_LEAGUES & SECONDARY_CLUB_LEAGUES}"
)


def _event_name_in(events: frozenset[str], col: str) -> str:
    """Build a literal `{col} IN (...)` fragment for a closed event-name
    set. Single quotes doubled for SQL escaping; inputs are
    compile-time constants, so f-string interpolation is safe.
    """
    quoted = ", ".join(f"'{e.replace(chr(39), chr(39) * 2)}'"
                       for e in sorted(events))
    return f"{col} IN ({quoted})"


def primary_club_clause(table_alias: str = "m") -> str:
    """Match's event_name belongs to a primary-tier club league
    (and is club-typed). Mirrors `full_member_clause`'s shape — a
    literal-IN fragment with no bind params."""
    a = table_alias
    return (f"({a}.team_type = 'club' AND "
            f"{_event_name_in(PRIMARY_CLUB_LEAGUES, f'{a}.event_name')})")


def secondary_club_clause(table_alias: str = "m") -> str:
    """Match's event_name belongs to a secondary-tier club league."""
    a = table_alias
    return (f"({a}.team_type = 'club' AND "
            f"{_event_name_in(SECONDARY_CLUB_LEAGUES, f'{a}.event_name')})")
