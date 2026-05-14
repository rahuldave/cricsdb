"""Pure-unit invariants for bucket_baseline_dispatch.

`is_precomputed_scope(filters, aux)` and `baseline_where(filters, aux,
team, table_alias)` are pure functions — they examine FilterBarParams /
AuxParams attributes and produce a bool / (sql, params) pair, with no
database calls. They sit at the dispatch boundary for the entire Phase
A + B + C + D precompute work, so a subtle sign-flip or off-by-one in
their branches would silently flip many endpoints between bucket and
live paths.

Test discipline (mirrors tests/sanity/test_wilson_ci.py):
  - One assertion per docstring branch.
  - No DB. The tests run instantly and don't need cricket.db.

Usage:
  uv run python tests/sanity/test_dispatch_predicate.py

Exits 0 on all-pass, 1 on any failure.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.filters import FilterBarParams, AuxParams
from api.routers.bucket_baseline_dispatch import (
    is_precomputed_scope, baseline_where, LEAGUE_TEAM_KEY,
)


# ─── Test fixtures ───────────────────────────────────────────────────


def _filters(**overrides) -> FilterBarParams:
    """Construct a FilterBarParams with every Query() default replaced
    by None, then apply `overrides`. The Query() defaults stick around
    when __init__ is called outside a request context, so we explicitly
    null every field for predictability.
    """
    f = FilterBarParams()
    for k in ("gender", "team_type", "tournament", "season_from",
              "season_to", "team", "opponent", "venue", "team_class",
              "series_type"):
        setattr(f, k, None)
    for k, v in overrides.items():
        setattr(f, k, v)
    return f


def _aux(**overrides) -> AuxParams:
    a = AuxParams()
    for k in ("scope_to_team", "chip_team_class", "chip_baseline_scope_json",
              "inning", "result", "toss_outcome"):
        setattr(a, k, None)
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


# ─── is_precomputed_scope branches ────────────────────────────────────


def test_is_precomputed_scope():
    cases = [
        # Each tuple: (description, filters_overrides, aux_overrides, expected)
        ("empty scope (all-cricket) → precomputed",
         {}, {}, True),
        ("gender only → precomputed",
         {"gender": "male"}, {}, True),
        ("team_type only → precomputed",
         {"team_type": "club"}, {}, True),
        ("gender + team_type + season range → precomputed",
         {"gender": "male", "team_type": "international",
          "season_from": "2024", "season_to": "2024"}, {}, True),
        ("tournament filter via filters.tournament → precomputed",
         {"tournament": "Indian Premier League"}, {}, True),
        # Rejected branches per is_precomputed_scope's docstring:
        ("filter_venue set → live",
         {"venue": "Eden Gardens"}, {}, False),
        ("filter_team set (rivalry) → live",
         {"team": "India"}, {}, False),
        ("filter_opponent set (rivalry) → live",
         {"opponent": "Australia"}, {}, False),
        ("series_type='bilateral' → live",
         {"series_type": "bilateral"}, {}, False),
        ("series_type='all' (default) → precomputed",
         {"series_type": "all"}, {}, True),
        # team_class polymorphism — only rejects when paired with the
        # MATCHING team_type (cross-type is a silent no-op so bucket
        # dispatch stays enabled).
        ("team_class=full_member + team_type=international → live",
         {"team_class": "full_member", "team_type": "international"}, {}, False),
        ("team_class=full_member + team_type=club (cross-type) → precomputed",
         {"team_class": "full_member", "team_type": "club"}, {}, True),
        ("team_class=primary_club + team_type=club → live",
         {"team_class": "primary_club", "team_type": "club"}, {}, False),
        ("team_class=primary_club + team_type=international (cross-type) → precomputed",
         {"team_class": "primary_club", "team_type": "international"}, {}, True),
        ("team_class=secondary_club + team_type=club → live",
         {"team_class": "secondary_club", "team_type": "club"}, {}, False),
        # Aux branches
        ("aux.inning=0 → live",
         {}, {"inning": 0}, False),
        ("aux.inning=1 → live",
         {}, {"inning": 1}, False),
        ("aux.result='won' → live",
         {}, {"result": "won"}, False),
        ("aux.toss_outcome='lost' → live",
         {}, {"toss_outcome": "lost"}, False),
        ("aux.scope_to_team set → precomputed (handled in baseline_where)",
         {}, {"scope_to_team": "Mumbai Indians"}, True),
    ]
    failures = []
    for desc, f_over, a_over, expected in cases:
        got = is_precomputed_scope(_filters(**f_over), _aux(**a_over))
        if got is not expected:
            failures.append(f"FAIL: {desc} — expected {expected}, got {got}")
    if failures:
        for f in failures:
            print(f)
        return False
    print(f"PASS: is_precomputed_scope — {len(cases)} branches")
    return True


# ─── baseline_where output shape ──────────────────────────────────────


def test_baseline_where_empty_scope():
    """Empty FilterBarParams + no team → empty WHERE."""
    w, p = baseline_where(_filters(), _aux(), team=None)
    if w != "":
        print(f"FAIL: empty scope expected '' WHERE, got: {w!r}")
        return False
    if p != {}:
        print(f"FAIL: empty scope expected empty params, got: {p!r}")
        return False
    print("PASS: baseline_where empty scope → ('', {})")
    return True


def test_baseline_where_league_team():
    """team=LEAGUE_TEAM_KEY → WHERE includes team='__league__'."""
    w, p = baseline_where(_filters(gender="male"), _aux(), team=LEAGUE_TEAM_KEY)
    if "team = :_team" not in w:
        print(f"FAIL: expected team clause, got: {w!r}")
        return False
    if p.get("_team") != LEAGUE_TEAM_KEY:
        print(f"FAIL: expected _team={LEAGUE_TEAM_KEY}, got: {p.get('_team')!r}")
        return False
    if "gender = :_gender" not in w or p.get("_gender") != "male":
        print(f"FAIL: gender clause missing or wrong, got: {w!r} {p!r}")
        return False
    print("PASS: baseline_where with team + gender")
    return True


def test_baseline_where_season_range():
    """season_from / season_to map to >= / <= comparisons."""
    w, p = baseline_where(
        _filters(season_from="2020", season_to="2024"),
        _aux(), team=None,
    )
    if "season >= :_season_from" not in w:
        print(f"FAIL: season_from clause missing: {w!r}")
        return False
    if "season <= :_season_to" not in w:
        print(f"FAIL: season_to clause missing: {w!r}")
        return False
    if p.get("_season_from") != "2020" or p.get("_season_to") != "2024":
        print(f"FAIL: season params wrong: {p!r}")
        return False
    print("PASS: baseline_where season range")
    return True


def test_baseline_where_tournament_literal():
    """Non-canonical tournament (no variant mapping) → equality clause."""
    w, p = baseline_where(
        _filters(tournament="Super Smash"), _aux(), team=None,
    )
    if "tournament = :_tournament" not in w:
        print(f"FAIL: expected literal equality, got: {w!r}")
        return False
    if p.get("_tournament") != "Super Smash":
        print(f"FAIL: tournament param wrong: {p!r}")
        return False
    print("PASS: baseline_where tournament literal")
    return True


def test_baseline_where_tournament_canonical_variants():
    """Canonical tournament name (T20 WC Men) → IN-clause with variants."""
    w, p = baseline_where(
        _filters(tournament="T20 World Cup (Men)"), _aux(), team=None,
    )
    # Should expand to multiple variants — IN clause, not equality.
    if " IN (" not in w:
        print(f"FAIL: expected IN-clause for canonical, got: {w!r}")
        return False
    if "_tournament" in p:
        print(f"FAIL: variant expansion should inline IDs, got param _tournament: {p!r}")
        return False
    print("PASS: baseline_where canonical → IN-clause variants")
    return True


def test_baseline_where_scope_to_team_subquery():
    """aux.scope_to_team (no explicit tournament filter) → IN-subquery."""
    w, p = baseline_where(
        _filters(gender="male", team_type="club"),
        _aux(scope_to_team="Mumbai Indians"),
        team=None,
    )
    if "tournament IN (" not in w:
        print(f"FAIL: expected IN-subquery for scope_to_team, got: {w!r}")
        return False
    if "bucketbaselinematch" not in w:
        print(f"FAIL: scope_to_team subquery should hit bucketbaselinematch, got: {w!r}")
        return False
    if p.get("_scope_to_team") != "Mumbai Indians":
        print(f"FAIL: scope_to_team param wrong: {p!r}")
        return False
    print("PASS: baseline_where scope_to_team subquery")
    return True


def test_baseline_where_explicit_tournament_overrides_scope_to_team():
    """Explicit filters.tournament wins over aux.scope_to_team."""
    w, p = baseline_where(
        _filters(tournament="Indian Premier League"),
        _aux(scope_to_team="Mumbai Indians"),
        team=None,
    )
    # tournament clause present, scope_to_team subquery NOT.
    if "tournament IN (SELECT" in w:
        print(f"FAIL: scope_to_team subquery leaked when tournament was set: {w!r}")
        return False
    if "_scope_to_team" in p:
        print(f"FAIL: scope_to_team param leaked: {p!r}")
        return False
    print("PASS: baseline_where explicit tournament wins over scope_to_team")
    return True


def test_baseline_where_table_alias():
    """table_alias='b' prefixes every column with 'b.'."""
    w, _p = baseline_where(
        _filters(gender="male"), _aux(), team=LEAGUE_TEAM_KEY, table_alias="b",
    )
    if "b.team = " not in w or "b.gender = " not in w:
        print(f"FAIL: alias missing, got: {w!r}")
        return False
    print("PASS: baseline_where table_alias prefixing")
    return True


# ─── Runner ──────────────────────────────────────────────────────────


def main():
    tests = [
        test_is_precomputed_scope,
        test_baseline_where_empty_scope,
        test_baseline_where_league_team,
        test_baseline_where_season_range,
        test_baseline_where_tournament_literal,
        test_baseline_where_tournament_canonical_variants,
        test_baseline_where_scope_to_team_subquery,
        test_baseline_where_explicit_tournament_overrides_scope_to_team,
        test_baseline_where_table_alias,
    ]
    all_ok = True
    for t in tests:
        all_ok &= t()
    print()
    print("ALL PASS" if all_ok else "SOME FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
