"""Helpers for the `/scope/averages/players/*` endpoint family.

Phase 3 of the player-baselines rollout. See
`internal_docs/spec-player-compare-average.md` §5 + §7 Phase 3.

Each discipline endpoint composes:
  1. Mix-vector parsing (10 floats batting / 20 bowling / binary
     keeper flag fielding).
  2. Per-bucket cohort aggregation joined from
     playerscopestats_<discipline> → playerscopestats (scope_key axes).
  3. Sliding-scale strict-cliff gate: if any bucket the player has
     non-zero mix-weight on has a cohort sample below the bucket's
     threshold, the entire response's `scope_avg` is null.
  4. Convex combination of per-bucket cohort rates, weighted by the
     player's mix — only when no cliff fires.

This module exposes the primitives. Each endpoint inlines the
discipline-specific aggregation queries in
`api/routers/scope_averages.py`.
"""

from __future__ import annotations

from typing import Optional

from .tournament_canonical import (
    is_canonical_with_variants,
    variants as canonical_variants,
    event_name_in_clause,
    ICC_EVENT_NAMES,
)
from .club_tiers import PRIMARY_CLUB_LEAGUES, SECONDARY_CLUB_LEAGUES


# ── Sliding-scale thresholds ───────────────────────────────────────
# Each threshold is the MINIMUM cohort sample at that bucket required
# for the bucket to count as "supported" for a player who weights it.
# Spec: spec-player-compare-average.md §6.


def batting_threshold(bucket: int) -> int:
    """Bucket 1..10 → cohort innings threshold. Linear 27 − 2·bucket.

    Bucket 1 (opener) → 25; bucket 10 (#11) → 7.
    """
    return 27 - 2 * bucket


def bowling_threshold(over: int) -> int:
    """Over 1..20 → cohort balls threshold. U-shape.

    Over 1, 2:  60 (new-ball specialists)
    Over 3–6:   50 (PP continuation)
    Over 7–15:  30 (middle — diverse, lots of part-timers)
    Over 16–19: 50 (death-finisher specialists)
    Over 20:    60 (final-over specialists)
    """
    if over in (1, 2, 20):
        return 60
    if 3 <= over <= 6 or 16 <= over <= 19:
        return 50
    return 30  # overs 7..15


def fielding_threshold(bucket: int) -> int:
    """Bucket 1..10 → cohort dismissals threshold. Linear 13 − bucket.

    Bucket 1 (opener) → 12; bucket 10 (#11) → 3.
    Used by the next-spec impact-weighted analyses; this rollout's
    fielding headline baseline uses the binary keeper flag instead
    (spec §5.4).
    """
    return 13 - bucket


# ── Mix-vector parsing ─────────────────────────────────────────────


def parse_mix(mix_str: str, expected_len: int) -> list[float]:
    """Parse the `?<axis>_mix=...` query parameter.

    Comma-separated floats summing to 1.0 ± 0.001. Trailing zeros may
    be omitted; missing entries default to 0.0. Length must be ≤
    expected_len; shorter inputs are right-padded.

    Raises ValueError on malformed input — the route handler should
    translate to HTTP 400.
    """
    if not mix_str:
        raise ValueError("mix is required")
    parts = mix_str.split(",")
    if len(parts) > expected_len:
        raise ValueError(
            f"mix has {len(parts)} entries; max {expected_len} "
            f"(buckets are 1..{expected_len})"
        )
    vals: list[float] = []
    for i, p in enumerate(parts):
        s = p.strip()
        if s == "":
            vals.append(0.0)
            continue
        try:
            vals.append(float(s))
        except ValueError:
            raise ValueError(f"mix entry [{i}] = {p!r} is not a number")
    while len(vals) < expected_len:
        vals.append(0.0)
    for i, v in enumerate(vals):
        if v < 0:
            raise ValueError(f"mix entry [{i}] = {v} is negative")
    total = sum(vals)
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"mix sums to {total:.4f}, expected 1.0 ± 0.001")
    return vals


# ── drop= parsing ─────────────────────────────────────────────────


def parse_drop(drop_str: Optional[str]) -> Optional[set[str]]:
    """Parse `?drop=axis1,axis2,…` into a set or None.

    Validation of axis names happens inside FilterBarParams.build()
    (raises ValueError on unknown axes); this helper just splits.
    """
    if not drop_str:
        return None
    return {s.strip() for s in drop_str.split(",") if s.strip()}


# ── Scope-key column filter clauses ────────────────────────────────


def build_scope_clauses(
    filters,
    drop: Optional[set[str]] = None,
    table_alias: str = "pss",
) -> tuple[str, dict]:
    """Build WHERE clauses against the scope_key columns on
    playerscopestats (default alias `pss`).

    Honours the four scope_key axes: gender, team_type, tournament,
    season (both season_from and season_to). Other FilterBar axes
    scope below the scope_key grain and are intentionally NOT
    applied here — matches the precomputed-table-only contract Phase 2
    used for the /summary distribution arrays.

    The `drop=` set masks named axes by the same names used in
    FilterBarParams.build(drop=...). Unknown axes are not validated
    here; the calling endpoint should validate via
    FilterBarParams.build (which raises on unknown axes).

    Returns ("clause1 AND clause2", {params}) — no leading AND.
    """
    drop = drop or set()
    clauses: list[str] = []
    params: dict = {}

    if "gender" not in drop and filters.gender:
        clauses.append(f"{table_alias}.gender = :gender")
        params["gender"] = filters.gender
    if "team_type" not in drop and filters.team_type:
        clauses.append(f"{table_alias}.team_type = :team_type")
        params["team_type"] = filters.team_type
    if "tournament" not in drop and filters.tournament:
        if is_canonical_with_variants(filters.tournament):
            clauses.append(event_name_in_clause(
                canonical_variants(filters.tournament),
                col=f"{table_alias}.tournament",
            ))
        else:
            clauses.append(f"{table_alias}.tournament = :tournament")
            params["tournament"] = filters.tournament
    if "season" not in drop and filters.season_from:
        clauses.append(f"{table_alias}.season >= :season_from")
        params["season_from"] = filters.season_from
    if "season" not in drop and filters.season_to:
        clauses.append(f"{table_alias}.season <= :season_to")
        params["season_to"] = filters.season_to

    if "series_type" not in drop and filters.series_type:
        st_clause = _series_type_clause_pss(filters.series_type, table_alias)
        if st_clause:
            clauses.append(st_clause)

    # team_class is polymorphic over team_type — same gates as
    # FilterBarParams.build: cross-type combinations are silent no-ops.
    # When team_type is dropped, the polymorphism guard sees None, so
    # team_class also doesn't fire (matches filters.build's
    # eff_team_type pattern).
    eff_team_type = None if "team_type" in drop else filters.team_type
    if "team_class" not in drop and filters.team_class:
        tc_clause = _team_class_clause_pss(
            filters.team_class, eff_team_type, table_alias,
        )
        if tc_clause:
            clauses.append(tc_clause)

    where = " AND ".join(clauses) if clauses else "1=1"
    return where, params


def _team_class_clause_pss(
    team_class: str, team_type: Optional[str], table_alias: str
) -> Optional[str]:
    """Player-side team_class clause against playerscopestats.tournament.

    Mirrors the polymorphism gate in FilterBarParams.build:
      - full_member requires team_type='international'
      - primary_club / secondary_club require team_type='club'

    Cross-type combinations silent-no-op. full_member operates on team
    names which playerscopestats doesn't carry — so we skip it here;
    the player's own summary endpoint honours team_class properly via
    filters.build (which has team1/team2 columns). For the cohort
    baseline at international scope, team_class=full_member widens
    the cohort slightly (includes associate nations) — acceptable
    looseness flagged in the spec §4.6 precomputed-table contract.
    """
    a = table_alias

    def event_name_in_literal(events: frozenset[str]) -> str:
        # Literal IN list — events are constants. Match the helper in
        # club_tiers._event_name_in (private, so re-inline).
        quoted = ", ".join(f"'{e.replace(chr(39), chr(39) * 2)}'"
                           for e in sorted(events))
        return f"{a}.tournament IN ({quoted})"

    if team_class == "full_member" and team_type == "international":
        # No-op at scope_key grain — see docstring.
        return None
    if team_class == "primary_club" and team_type == "club":
        return f"({a}.team_type = 'club' AND {event_name_in_literal(PRIMARY_CLUB_LEAGUES)})"
    if team_class == "secondary_club" and team_type == "club":
        return f"({a}.team_type = 'club' AND {event_name_in_literal(SECONDARY_CLUB_LEAGUES)})"
    return None


def _series_type_clause_pss(value: str, table_alias: str) -> Optional[str]:
    """Player-side series_type clause against playerscopestats columns.

    The canonical helper in tournament_canonical.series_type_clause
    uses match-table column names (m.event_name + m.team_type);
    playerscopestats stores the same axes as `tournament` and
    `team_type`. This wrapper applies the same partitioning logic
    against the player-scope-stats columns.

    Returns None for unknown values, matching the canonical helper.
    """
    # Legacy aliases.
    if value == "bilateral_only":
        value = "bilateral"
    elif value == "tournament_only":
        value = "icc"
    if value not in ("bilateral", "icc", "club"):
        return None

    icc_variants: list[str] = []
    for canon in ICC_EVENT_NAMES:
        icc_variants.extend(canonical_variants(canon))
    icc_in = event_name_in_clause(icc_variants, col=f"{table_alias}.tournament")

    if value == "bilateral":
        return (
            f"({table_alias}.team_type = 'international' AND "
            f"({table_alias}.tournament IS NULL OR {table_alias}.tournament = ''"
            f" OR NOT {icc_in}))"
        )
    if value == "icc":
        return icc_in
    # club
    return f"{table_alias}.team_type = 'club'"


# ── Convex combination ────────────────────────────────────────────


def convex_combine(
    mix: list[float],
    per_bucket_values: dict[int, float | None],
) -> float | None:
    """Compute Σ_b mix[b-1] × per_bucket_values[b].

    `per_bucket_values` is keyed by 1-indexed bucket number; missing
    buckets contribute 0. Values that are None (e.g. a rate with zero
    denominator at that bucket) ALSO contribute 0 — they are not
    counted toward the sum but do not poison the result (only the
    strict-cliff gate decides whether the headline is null).

    Returns None only when the mix is entirely zero (degenerate).
    """
    total = 0.0
    total_mix = 0.0
    for b, w in enumerate(mix, start=1):
        if w == 0:
            continue
        total_mix += w
        v = per_bucket_values.get(b)
        if v is None:
            continue
        total += w * v
    if total_mix == 0:
        return None
    return total


# ── Bucket labels ─────────────────────────────────────────────────


def batting_bucket_label(b: int) -> str:
    """1=Opener, 2=#3, …, 10=#11."""
    if b == 1:
        return "Opener"
    return f"#{b + 1}"  # bucket 2 → #3, bucket 10 → #11


def bowling_bucket_label(o: int) -> str:
    """1..20 → "Over 1" .. "Over 20"."""
    return f"Over {o}"


def fielding_bucket_label(b: int) -> str:
    """Same as batting (dismissed batter's position)."""
    return batting_bucket_label(b)
