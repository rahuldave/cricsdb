"""Single source of truth for metric direction + envelope construction.

Every numeric metric returned by the team-compare endpoint family carries
a `{value, scope_avg, delta_pct, direction, sample_size}` envelope.
`direction` is a per-metric constant (some metrics are higher-is-better,
some lower-is-better, some have no preference) — this module is the
canonical map. UIs consume `direction` directly; they don't enumerate
the metric list themselves so they stay in lockstep when a new metric
joins.

See `internal_docs/spec-team-compare-average.md` Phase 2B for the
contract. Spec-1 UI (Teams > Compare) renders only `value`; the rest of
the envelope is shipped for future surfaces (player compare, leaderboard
delta columns, H2H baselines — see
`internal_docs/outlook-comparisons.md`).
"""
from __future__ import annotations

from typing import Literal, Optional

Direction = Literal["higher_better", "lower_better"] | None

# Metric keys are short, stable identifiers — NOT the JSON field names
# (which can collide across endpoints — `dot_pct` means "batter dot
# percentage" on batting endpoints and "bowler dot percentage" on
# bowling endpoints, with opposite directions). Use prefixed keys here
# (`bat_dot_pct`, `bowl_dot_pct`) and translate at call sites.
METRIC_DIRECTIONS: dict[str, Direction] = {
    # ── results / outcomes ─────────────────────────────────────────
    # Counts (matches, ties, wins, etc.) get direction=None so
    # delta_pct stays null — team-count-vs-league-total is ~10x scaled
    # and the percentage is misleading. Rates (win_pct,
    # bat_first_win_pct) get a real direction.
    "matches":          None,
    "wins":             None,
    "losses":           None,
    "ties":             None,
    "no_results":       None,
    "win_pct":          "higher_better",
    "toss_wins":        None,
    "bat_first_wins":   None,
    "field_first_wins": None,

    # ── batting (per-team) ─────────────────────────────────────────
    # Counts: total_runs, legal_balls, fours, sixes, fifties, hundreds,
    # innings_batted — null direction, scope_avg shipped for context.
    # Rates: run_rate, boundary_pct, bat_dot_pct, avg_*_innings_total.
    "innings_batted":   None,
    "total_runs":       None,
    "legal_balls":      None,
    "run_rate":         "higher_better",
    "boundary_pct":     "higher_better",
    "bat_dot_pct":      "lower_better",
    "fours":            None,
    "sixes":            None,
    "fifties":          None,
    "hundreds":         None,
    "avg_1st_innings_total": "higher_better",
    "avg_2nd_innings_total": "higher_better",

    # ── bowling (per-team — fielding side) ─────────────────────────
    "innings_bowled":   None,
    "runs_conceded":    None,
    "bowl_legal_balls": None,
    "overs":            None,
    "wickets":          None,
    "economy":          "lower_better",
    "strike_rate":      "lower_better",
    "average":          "lower_better",
    "bowl_dot_pct":     "higher_better",
    "fours_conceded":   None,
    "sixes_conceded":   None,
    "wides":            None,
    "noballs":          None,
    "wides_per_match":  "lower_better",
    "noballs_per_match": "lower_better",
    "avg_opposition_total": "lower_better",

    # ── fielding ───────────────────────────────────────────────────
    "catches":          None,
    "caught_and_bowled": None,
    "stumpings":        None,
    "run_outs":         None,
    "total_dismissals_contributed": None,
    "catches_per_match": "higher_better",
    "stumpings_per_match": "higher_better",
    "run_outs_per_match": "higher_better",

    # ── partnerships ───────────────────────────────────────────────
    "total":            None,
    "count_50_plus":    None,
    "count_100_plus":   None,
    "avg_runs":         "higher_better",
}


def wrap_metric(
    value: int | float | None,
    scope_avg: int | float | None,
    direction_key: str,
    sample_size: int | float | None = None,
) -> dict:
    """Build the per-metric envelope dict.

    `delta_pct` is signed (value - scope_avg) / scope_avg × 100, rounded
    to 1 decimal. Returns null for delta_pct when:
      - either side is null,
      - direction is informational (no preference),
      - the metric is a count (direction is None) — pool totals make
        delta_pct misleading because the league total dwarfs the team
        total by ~10x; the percentage is mathematically computable but
        not meaningfully interpretable as "above/below average."

    `direction` is the literal "higher_better" / "lower_better" or None;
    UIs consume directly.

    `sample_size` is the denominator that makes the comparison
    defensible (legal_balls for batting rates, balls_bowled for bowling
    rates, partnerships for partnership stats, matches for outcome
    rates). Optional — pass None when unknown.
    """
    direction = METRIC_DIRECTIONS.get(direction_key, None)
    delta_pct: Optional[float] = None
    if value is not None and scope_avg not in (None, 0) and direction is not None:
        delta_pct = round((value - scope_avg) / scope_avg * 100, 1)
    return {
        "value": value,
        "scope_avg": scope_avg,
        "delta_pct": delta_pct,
        "direction": direction,
        "sample_size": sample_size,
    }
