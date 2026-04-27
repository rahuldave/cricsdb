"""ICC full-member team list — used by the Teams landing-page split
AND the `team_class=full_member` aux filter (avg-baseline narrowing on
internationals).

Same team strings work for men's and women's — cricsheet uses identical
country labels across genders.

Afghanistan + Ireland were elevated to full-member status in 2017; they
play the full tournament calendar today, so we treat them as regular for
display + filter purposes. Zimbabwe remains a full member despite
historical ICC pressure.
"""

from __future__ import annotations

ICC_FULL_MEMBERS: frozenset[str] = frozenset({
    "Afghanistan", "Australia", "Bangladesh", "England", "India",
    "Ireland", "New Zealand", "Pakistan", "South Africa", "Sri Lanka",
    "West Indies", "Zimbabwe",
})


def full_member_clause(table_alias: str = "m") -> str:
    """Both teams in a match must be full members.

    Returned as a literal-IN clause (no bind params) because frozenset
    expansion via :param doesn't work with SQLite. The list is closed
    and trusted (compile-time constant), so f-string interpolation is
    safe here.
    """
    a = table_alias
    quoted = ", ".join(f"'{t}'" for t in sorted(ICC_FULL_MEMBERS))
    return f"({a}.team1 IN ({quoted}) AND {a}.team2 IN ({quoted}))"
