"""Single source of the all-ball batting-runs convention.

spec-batting-allball-runs-single-source.md §2 / D3: a batsman's
runs / fours / sixes count over ALL his deliveries — runs off a no-ball
are his, a boundary off a no-ball is his boundary — while balls faced
and dots are legal-only (a no-ball is never a ball faced). Every batting
populate that scans deliveries (the parent player_scope_stats + the
per-over / per-phase / phase×position children) routes each striker
delivery through this one helper so the convention can't drift between
them. (api/ is the shared home for populate-time cricket helpers, same
as api.innings_positions.derive_positions.)

NOTE on fours: this matches inningsbatterperf + the cohort tables, which
count any runs_batter == 4 as a four. The read queries in
api/routers/batting.py additionally keep their pre-existing
`runs_non_boundary = 0` guard (a clean boundary four, not a ran-four);
that guard is intentionally NOT applied here so parent ↔ child pool
conservation and the inningsbatterperf rollup stay exact-integer.
"""

from __future__ import annotations


def batting_delivery_contrib(
    runs_batter: int,
    runs_total: int,
    extras_wides: int,
    extras_noballs: int,
) -> tuple[int, int, int, int, int]:
    """One striker delivery's batting contribution.

    Returns (runs, is_four, is_six, legal_ball, dot):
      runs       — runs off the bat (counted on ALL deliveries).
      is_four    — 1 if a four off the bat (any delivery), else 0.
      is_six     — 1 if a six off the bat (any delivery), else 0.
      legal_ball — 1 if a legal ball faced (not wide / no-ball), else 0.
      dot        — 1 if a legal ball with no run off the bat AND no run
                   total (a leg-bye/bye is not a dot), else 0.
    """
    legal = extras_wides == 0 and extras_noballs == 0
    return (
        runs_batter,
        1 if runs_batter == 4 else 0,
        1 if runs_batter == 6 else 0,
        1 if legal else 0,
        1 if (legal and runs_batter == 0 and runs_total == 0) else 0,
    )
