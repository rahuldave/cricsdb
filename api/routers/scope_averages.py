"""League-scope baseline endpoints — the "average team" / "average league
behaviour" counterpart to `/api/v1/teams/{team}/*`.

Every endpoint here mirrors a `/teams/{team}/*` sibling but with the
team filter dropped — the result is the pool-weighted average over the
current FilterBar scope. Used by the Teams Compare tab to render an
"average team" column alongside selected teams.

Path-level "team" parameter is gone; everything else (gender,
team_type, tournament, season_from, season_to, filter_venue,
series_type) is identical to the team siblings via FilterParams +
AuxParams.

The helpers `_team_innings_clause` and `_partnership_filter` in
`api.routers.teams` accept `team=None` precisely so this router can
reuse the same WHERE-clause logic — guaranteeing both code paths agree
on filter injection. Identity-bearing nested objects from the team
endpoints (highest_total, best_pair, keepers list, etc.) are kept where
they're meaningful at scope level (highest league total has a team
owner, league's best pair has people identity) and dropped where they
aren't (a "league average team" has no captain or home ground).

Spec: `internal_docs/spec-team-compare-average.md`.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from ..filters import FilterParams, AuxParams
from ..dependencies import get_db
from ..metrics_metadata import wrap_metric
from ..scope_averages_players import (
    batting_threshold,
    bowling_threshold,
    fielding_threshold,
    parse_mix,
    parse_drop,
    build_scope_clauses,
    convex_combine,
    batting_bucket_label,
    bowling_bucket_label,
    fielding_bucket_label,
)
from .teams import (
    _team_innings_clause, _partnership_filter, _scope_to_team_clause, _safe_div,
    _apply_batting_per_innings, _apply_bowling_per_innings,
    _apply_fielding_per_innings, _apply_partnerships_per_innings,
    _apply_results_per_team, _unique_teams_in_scope,
    _option_b_team_inning, _cohort_outcome_clause,
)
from .bucket_baseline_dispatch import (
    is_precomputed_scope, baseline_where, LEAGUE_TEAM_KEY,
)

router = APIRouter(prefix="/api/v1/scope/averages", tags=["Scope-Averages"])


# ── per-innings divisors ──────────────────────────────────────────
# Each scope-averages endpoint needs an innings_count (or matches × 2
# for fielding) to divide absolute counts by. Baseline path reads
# from bucketbaselinebatting / bucketbaselinebowling / bucketbaselinematch;
# live path runs a small COUNT(DISTINCT i.id) query against the
# delivery + innings + match tables.

async def _baseline_innings_batted(filters, aux) -> int:
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"SELECT SUM(innings_batted) AS innings_batted FROM bucketbaselinebatting {where}",
        params,
    )
    return (rows[0].get("innings_batted") if rows else 0) or 0


async def _baseline_innings_bowled(filters, aux) -> int:
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"SELECT SUM(innings_bowled) AS innings_bowled FROM bucketbaselinebowling {where}",
        params,
    )
    return (rows[0].get("innings_bowled") if rows else 0) or 0


async def _baseline_matches(filters, aux) -> int:
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"SELECT SUM(matches) AS matches FROM bucketbaselinematch {where}",
        params,
    )
    return (rows[0].get("matches") if rows else 0) or 0


async def _live_innings_batted(filters, aux) -> int:
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)
    rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS innings_batted
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    return (rows[0].get("innings_batted") if rows else 0) or 0


async def _live_innings_bowled(filters, aux) -> int:
    """Same as innings_batted but counts innings where the team was
    fielding. For league-scope (team=None), this equals innings_batted
    since every batting innings has a corresponding fielding innings."""
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)
    rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS innings_bowled
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    return (rows[0].get("innings_bowled") if rows else 0) or 0


async def _live_match_count(filters, aux) -> int:
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)
    rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) AS matches
        FROM match m
        JOIN innings i ON i.match_id = m.id
        WHERE {where}
        """,
        params,
    )
    return (rows[0].get("matches") if rows else 0) or 0


# ============================================================
# Summary (results / toss style — match-level aggregates)
# ============================================================

@router.get("/summary")
async def scope_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """League-scope match-level totals + toss/bat-first signals.

    Dispatches to bucket_baseline_match for precomputed-regime scopes
    (~10x faster); falls back to live aggregation for filter_venue /
    rivalry / series_type / partial-season filters.
    """
    if is_precomputed_scope(filters, aux):
        return await _summary_from_baseline(filters, aux)
    return await _summary_live(filters, aux)


async def _summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT
            SUM(matches) AS matches,
            SUM(decided) AS decided,
            SUM(ties) AS ties,
            SUM(no_results) AS no_results,
            SUM(toss_decided) AS toss_decided,
            SUM(bat_first_wins) AS bat_first_wins,
            SUM(field_first_wins) AS field_first_wins
        FROM bucketbaselinematch {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    decided = r.get("decided", 0) or 0
    bf = r.get("bat_first_wins", 0) or 0
    bf_pct = round(bf * 100 / decided, 1) if decided > 0 else None
    pool = {
        "matches": r.get("matches", 0) or 0,
        "decided": decided,
        "ties": r.get("ties", 0) or 0,
        "no_results": r.get("no_results", 0) or 0,
        "toss_decided": r.get("toss_decided", 0) or 0,
        "bat_first_wins": bf,
        "field_first_wins": r.get("field_first_wins", 0) or 0,
        "bat_first_win_pct": bf_pct,
    }
    unique_teams = await _unique_teams_in_scope(filters, aux)
    return _apply_results_per_team(pool, unique_teams)


async def _summary_live(filters, aux):
    db = get_db()
    # Match-level filter only (no innings join).
    filters.team = None
    where, params = filters.build(has_innings_join=False, aux=aux)
    # Avg slot's auto-narrow to primary team's tournament universe.
    st_clause, st_params = _scope_to_team_clause(aux, filters)
    if st_clause:
        where = f"{where} AND {st_clause}" if where else st_clause
        params.update(st_params)
    where = where or "1=1"

    rows = await db.q(
        f"""
        SELECT
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL THEN 1 ELSE 0 END) as decided,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results,
            SUM(CASE WHEN m.toss_winner IS NOT NULL THEN 1 ELSE 0 END) as toss_decided,
            SUM(CASE WHEN m.toss_decision = 'bat'
                     AND m.toss_winner = m.outcome_winner THEN 1
                     WHEN m.toss_decision = 'field'
                     AND m.outcome_winner IS NOT NULL
                     AND m.toss_winner != m.outcome_winner THEN 1
                     ELSE 0 END) as bat_first_wins,
            SUM(CASE WHEN m.toss_decision = 'field'
                     AND m.toss_winner = m.outcome_winner THEN 1
                     WHEN m.toss_decision = 'bat'
                     AND m.outcome_winner IS NOT NULL
                     AND m.toss_winner != m.outcome_winner THEN 1
                     ELSE 0 END) as field_first_wins
        FROM match m
        WHERE {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    decided = r.get("decided", 0) or 0
    bf = r.get("bat_first_wins", 0) or 0
    bf_pct = round(bf * 100 / decided, 1) if decided > 0 else None
    pool = {
        "matches": r.get("matches", 0) or 0,
        "decided": decided,
        "ties": r.get("ties", 0) or 0,
        "no_results": r.get("no_results", 0) or 0,
        "toss_decided": r.get("toss_decided", 0) or 0,
        "bat_first_wins": bf,
        "field_first_wins": r.get("field_first_wins", 0) or 0,
        "bat_first_win_pct": bf_pct,
    }
    unique_teams = await _unique_teams_in_scope(filters, aux)
    return _apply_results_per_team(pool, unique_teams)


# ============================================================
# Batting
# ============================================================

@router.get("/batting/summary")
async def scope_batting_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope batting aggregates."""
    if is_precomputed_scope(filters, aux):
        return await _batting_summary_from_baseline(filters, aux)
    return await _batting_summary_live(filters, aux)


def _format_batting_summary(
    innings_batted, total_runs, legal_balls, fours, sixes, dots,
    first_inn_runs_sum, first_inn_count,
    second_inn_runs_sum, second_inn_count,
    highest_total,
):
    runs = total_runs or 0
    balls = legal_balls or 0
    fours = fours or 0
    sixes = sixes or 0
    dots = dots or 0
    boundaries = fours + sixes
    avg_1st = round((first_inn_runs_sum or 0) / first_inn_count, 1) if first_inn_count else None
    avg_2nd = round((second_inn_runs_sum or 0) / second_inn_count, 1) if second_inn_count else None
    return {
        "innings_batted": innings_batted or 0,
        "total_runs": runs,
        "legal_balls": balls,
        "run_rate": _safe_div(runs, balls, 6),
        "boundary_pct": _safe_div(boundaries, balls, 100, 1),
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
    }


async def _batting_summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT
          SUM(innings_batted) AS innings_batted,
          SUM(total_runs) AS total_runs,
          SUM(legal_balls) AS legal_balls,
          SUM(fours) AS fours, SUM(sixes) AS sixes, SUM(dots) AS dots,
          SUM(first_inn_runs_sum) AS first_inn_runs_sum,
          SUM(first_inn_count) AS first_inn_count,
          SUM(second_inn_runs_sum) AS second_inn_runs_sum,
          SUM(second_inn_count) AS second_inn_count
        FROM bucketbaselinebatting {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    # Highest_total: pick the cell row with the largest highest_inn_runs.
    hi_rows = await db.q(
        f"""
        SELECT highest_inn_runs AS runs, highest_inn_match_id AS match_id,
               highest_inn_team AS team, highest_inn_innings_number AS innings_number
        FROM bucketbaselinebatting {where} AND highest_inn_runs > 0
        ORDER BY highest_inn_runs DESC, highest_inn_match_id LIMIT 1
        """,
        params,
    )
    highest = None
    if hi_rows:
        h = hi_rows[0]
        highest = {
            "runs": h["runs"],
            "team": h["team"],
            "match_id": h["match_id"],
            "innings_number": (h["innings_number"] or 0) + 1,
        }
    out = _format_batting_summary(highest_total=highest, **{k: r.get(k) for k in (
        "innings_batted", "total_runs", "legal_balls", "fours", "sixes", "dots",
        "first_inn_runs_sum", "first_inn_count",
        "second_inn_runs_sum", "second_inn_count",
    )})
    return _apply_batting_per_innings(out, out.get("innings_batted") or 0, drop_divisor=True)


async def _batting_summary_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)

    core = await db.q(
        f"""
        SELECT
            COUNT(DISTINCT i.id) as innings_batted,
            SUM(d.runs_total) as total_runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    c = core[0] if core else {}
    total_runs = c.get("total_runs") or 0
    legal_balls = c.get("legal_balls") or 0
    fours = c.get("fours") or 0
    sixes = c.get("sixes") or 0
    dots = c.get("dots") or 0
    boundaries = fours + sixes

    # Per-innings totals → avg 1st/2nd-innings + highest single innings.
    innings_rows = await db.q(
        f"""
        SELECT
            i.id as innings_id, i.match_id, i.innings_number,
            i.team as innings_team,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.id, i.match_id, i.innings_number, i.team
        """,
        params,
    )
    first_totals = [r["runs"] for r in innings_rows if r["innings_number"] == 0 and r["runs"] is not None]
    second_totals = [r["runs"] for r in innings_rows if r["innings_number"] == 1 and r["runs"] is not None]
    avg_1st = round(sum(first_totals) / len(first_totals), 1) if first_totals else None
    avg_2nd = round(sum(second_totals) / len(second_totals), 1) if second_totals else None

    highest_total = None
    if innings_rows:
        top = max(innings_rows, key=lambda r: r["runs"] or 0)
        highest_total = {
            "runs": top["runs"] or 0,
            "team": top["innings_team"],
            "match_id": top["match_id"],
            "innings_number": top["innings_number"] + 1,
        }

    out = {
        "innings_batted": c.get("innings_batted") or 0,
        "total_runs": total_runs,
        "legal_balls": legal_balls,
        "run_rate": _safe_div(total_runs, legal_balls, 6),
        "boundary_pct": _safe_div(boundaries, legal_balls, 100, 1),
        "dot_pct": _safe_div(dots, legal_balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
    }
    return _apply_batting_per_innings(out, out.get("innings_batted") or 0, drop_divisor=True)


@router.get("/batting/by-phase")
async def scope_batting_by_phase(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted phase splits (PP 0-5 / Mid 6-14 / Death 15-19).
    Bucket-baseline path for precomputed scopes; live fallback for
    venue / rivalry / series_type filters."""
    if is_precomputed_scope(filters, aux):
        return await _batting_by_phase_from_baseline(filters, aux)
    return await _batting_by_phase_live(filters, aux)


@router.get("/batting/dismissals")
async def scope_batting_dismissals(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pooled-scope dismissal distribution — the cohort baseline for
    the player Dismissals tab's three normalized charts. Mirrors the
    player /batters/{id}/dismissals queries minus the player_out_id
    filter, so player and cohort are scope-aligned by construction.

    Returns pooled counts across every batter at scope:
      - by_kind:  {kind: count}      (mode-of-dismissal, ÷ innings)
      - by_over:  [{over_number, dismissals}]  (÷ out-innings)
      - by_phase: {phase: count}     (÷ out-innings)
      - total_dismissals, innings, not_outs (innings = batting innings
        at scope; not_outs = innings − total_dismissals).
    """
    db = get_db()
    # Same batting-side innings clause used by every other scope
    # endpoint. With team=None this is the league-wide pool — "all
    # batters at scope" — matching the cohort convention on the By
    # Over / By Phase tabs.
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)
    # Exclude the same non-dismissal wicket kinds the player endpoint
    # excludes, so the two distributions count identically.
    kind_excl = "w.kind NOT IN ('retired hurt', 'retired out')"

    kind_rows, over_rows, phase_rows = await asyncio.gather(
        db.q(
            f"""
            SELECT w.kind, COUNT(*) AS cnt
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where} AND {kind_excl}
            GROUP BY w.kind
            ORDER BY cnt DESC
            """,
            params,
        ),
        db.q(
            f"""
            SELECT d.over_number, COUNT(*) AS dismissals
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where} AND {kind_excl} AND d.over_number BETWEEN 0 AND 19
            GROUP BY d.over_number
            ORDER BY d.over_number
            """,
            params,
        ),
        db.q(
            f"""
            SELECT
                CASE
                    WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                    WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                    WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
                END AS phase,
                COUNT(*) AS dismissals
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where} AND {kind_excl} AND d.over_number BETWEEN 0 AND 19
            GROUP BY phase
            """,
            params,
        ),
    )

    by_kind = {r["kind"]: r["cnt"] for r in kind_rows}
    total = sum(by_kind.values())
    for r in over_rows:
        r["over_number"] = r["over_number"] + 1  # display as 1-20
    by_phase = {r["phase"]: r["dismissals"] for r in phase_rows if r["phase"]}

    # Cohort denominator = total BATTER-innings at scope (distinct
    # (batter, innings) appearances), NOT team-innings — each team
    # innings fields ~11 batters who each play one innings. Counted
    # under the SAME scope clause as the dismissal numerators so the
    # mode distribution (kinds + not-out) is internally consistent.
    inn_rows = await db.q(
        f"""
        SELECT COUNT(*) AS batter_innings FROM (
            SELECT DISTINCT d.batter_id, d.innings_id
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
        )
        """,
        params,
    )
    innings = (inn_rows[0].get("batter_innings") if inn_rows else 0) or 0
    not_outs = max(innings - total, 0)

    return {
        "total_dismissals": total,
        "by_kind": by_kind,
        "by_phase": by_phase,
        "by_over": over_rows,
        "innings": innings,
        "not_outs": not_outs,
    }


OVER_RANGES = [
    ("powerplay", [1, 6]),
    ("middle",    [7, 15]),
    ("death",     [16, 20]),
]


async def _batting_by_phase_from_baseline(filters, aux):
    db = get_db()
    # Two SUM passes against bucket_baseline_phase: batting rows for
    # delivery counters; bowling rows separately give wickets-lost
    # because that's actually a bowler-credited count for the phase
    # (mirrored to wickets_lost in the live aggregator's wkt query
    # which only excludes retired*).
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    bat_rows = await db.q(
        f"""
        SELECT phase,
               SUM(runs) AS runs,
               SUM(legal_balls) AS balls,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes,
               SUM(dots) AS dots
        FROM bucketbaselinephase {where} AND side='batting'
        GROUP BY phase
        """,
        params,
    )
    by_phase = {r["phase"]: r for r in bat_rows if r["phase"]}

    # wickets_lost in the live aggregator excludes only retired*; our
    # baseline phase.wickets is bowler-credited (excludes run-out etc.)
    # — wider exclusion. To match exactly, we run a small live query
    # for wickets_lost.
    # NOTE: live path's wickets_lost uses a different exclusion list;
    # match it with a targeted query that respects only retired*.
    where_live, params_live = _team_innings_clause(filters, None, side="batting", aux=aux)
    wkt_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets_lost
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where_live}
          AND d.over_number BETWEEN 0 AND 19
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY phase
        """,
        params_live,
    )
    wkt_by_phase = {r["phase"]: r["wickets_lost"] for r in wkt_rows if r["phase"]}

    out = []
    for phase, ranges in OVER_RANGES:
        s = by_phase.get(phase) or {}
        runs = s.get("runs") or 0
        balls = s.get("balls") or 0
        fours = s.get("fours") or 0
        sixes = s.get("sixes") or 0
        dots = s.get("dots") or 0
        boundaries = fours + sixes
        out.append({
            "phase": phase,
            "overs_range": ranges,
            "runs": runs,
            "balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "wickets_lost": wkt_by_phase.get(phase, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "dot_pct": _safe_div(dots, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        })
    return _phase_per_innings(out, await _baseline_innings_batted(filters, aux))


def _phase_per_innings(rows: list[dict], innings_count: int) -> dict:
    """Divide phase-row absolute counts by innings_count. Per-innings
    treatment for the avg endpoint (rates stay pool ≡ per-innings)."""
    if innings_count and innings_count > 0:
        keys = ("runs", "runs_conceded", "balls", "wickets_lost", "wickets",
                "fours", "sixes", "fours_conceded", "sixes_conceded")
        for r in rows:
            for k in keys:
                v = r.get(k)
                if v is not None:
                    r[k] = round(v / innings_count, 2)
    return {"by_phase": rows}


async def _batting_by_phase_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.over_number BETWEEN 0 AND 19
        GROUP BY phase
        """,
        params,
    )
    by_phase = {r["phase"]: r for r in rows if r["phase"]}

    wkt_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets_lost
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.over_number BETWEEN 0 AND 19
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY phase
        """,
        params,
    )
    wkt_by_phase = {r["phase"]: r["wickets_lost"] for r in wkt_rows if r["phase"]}

    out = []
    for phase, ranges in OVER_RANGES:
        s = by_phase.get(phase) or {}
        runs = s.get("runs") or 0
        balls = s.get("balls") or 0
        fours = s.get("fours") or 0
        sixes = s.get("sixes") or 0
        dots = s.get("dots") or 0
        boundaries = fours + sixes
        out.append({
            "phase": phase,
            "overs_range": ranges,
            "runs": runs,
            "balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "wickets_lost": wkt_by_phase.get(phase, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "dot_pct": _safe_div(dots, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        })
    return _phase_per_innings(out, await _live_innings_batted(filters, aux))


@router.get("/batting/by-season")
async def scope_batting_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted batting aggregates per season — drives the season-
    trajectory strip in the Compare tab."""
    if is_precomputed_scope(filters, aux):
        return await _batting_by_season_from_baseline(filters, aux)
    return await _batting_by_season_live(filters, aux)


def _format_batting_season_row(season, innings_batted, total_runs, legal_balls, fours, sixes, dots):
    runs = total_runs or 0
    balls = legal_balls or 0
    fours = fours or 0
    sixes = sixes or 0
    dots = dots or 0
    boundaries = fours + sixes
    inn = innings_batted or 0
    out = {
        "season": season,
        "innings_batted": inn,
        "total_runs": runs,
        "legal_balls": balls,
        "run_rate": _safe_div(runs, balls, 6),
        "boundary_pct": _safe_div(boundaries, balls, 100, 1),
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
    }
    return _apply_batting_per_innings(out, inn, drop_divisor=True)


async def _batting_by_season_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT season,
               SUM(innings_batted) AS innings_batted,
               SUM(total_runs) AS total_runs,
               SUM(legal_balls) AS legal_balls,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes,
               SUM(dots) AS dots
        FROM bucketbaselinebatting {where}
        GROUP BY season ORDER BY season
        """,
        params,
    )
    return {"by_season": [_format_batting_season_row(**r) for r in rows]}


async def _batting_by_season_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)
    rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(DISTINCT i.id) as innings_batted,
            SUM(d.runs_total) as total_runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    return {"by_season": [_format_batting_season_row(**r) for r in rows]}


# ============================================================
# Bowling
# ============================================================

@router.get("/bowling/summary")
async def scope_bowling_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope bowling aggregates."""
    if is_precomputed_scope(filters, aux):
        return await _bowling_summary_from_baseline(filters, aux)
    return await _bowling_summary_live(filters, aux)


def _format_bowling_summary(
    innings_bowled, matches, runs_conceded, legal_balls,
    wides, noballs, fours_conceded, sixes_conceded, dots, wickets,
):
    runs = runs_conceded or 0
    balls = legal_balls or 0
    dots = dots or 0
    matches = matches or 0
    wickets = wickets or 0
    inn = innings_bowled or 0
    fours = fours_conceded or 0
    sixes = sixes_conceded or 0
    out = {
        "innings_bowled": inn,
        "matches": matches,
        "runs_conceded": runs,
        "legal_balls": balls,
        "overs": round(balls / 6, 1) if balls else 0,
        "wickets": wickets,
        "economy": _safe_div(runs, balls, 6),
        "strike_rate": _safe_div(balls, wickets) if wickets else None,
        "average": _safe_div(runs, wickets) if wickets else None,
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours_conceded": fours,
        "sixes_conceded": sixes,
        "boundaries_conceded": fours + sixes,
        "wides": wides or 0,
        "noballs": noballs or 0,
        "wides_per_match": _safe_div(wides or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(noballs or 0, matches, 1, 2),
    }
    return _apply_bowling_per_innings(out, inn, drop_divisor=True)


async def _bowling_summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT
            SUM(innings_bowled) AS innings_bowled,
            SUM(matches) AS matches,
            SUM(runs_conceded) AS runs_conceded,
            SUM(legal_balls) AS legal_balls,
            SUM(wides) AS wides,
            SUM(noballs) AS noballs,
            SUM(fours_conceded) AS fours_conceded,
            SUM(sixes_conceded) AS sixes_conceded,
            SUM(dots) AS dots,
            SUM(wickets) AS wickets
        FROM bucketbaselinebowling {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    return _format_bowling_summary(
        innings_bowled=r.get("innings_bowled"), matches=r.get("matches"),
        runs_conceded=r.get("runs_conceded"), legal_balls=r.get("legal_balls"),
        wides=r.get("wides"), noballs=r.get("noballs"),
        fours_conceded=r.get("fours_conceded"), sixes_conceded=r.get("sixes_conceded"),
        dots=r.get("dots"), wickets=r.get("wickets"),
    )


async def _bowling_summary_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    core = await db.q(
        f"""
        SELECT
            COUNT(DISTINCT i.id) as innings_bowled,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.extras_wides > 0 THEN 1 ELSE 0 END) as wides,
            SUM(CASE WHEN d.extras_noballs > 0 THEN 1 ELSE 0 END) as noballs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    c = core[0] if core else {}
    wkt_rows = await db.q(
        f"""
        SELECT COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')
        """,
        params,
    )
    matches_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM match m
        JOIN innings i ON i.match_id = m.id
        WHERE {where}
        """,
        params,
    )
    return _format_bowling_summary(
        innings_bowled=c.get("innings_bowled"),
        matches=matches_rows[0]["matches"] if matches_rows else 0,
        runs_conceded=c.get("runs_conceded"), legal_balls=c.get("legal_balls"),
        wides=c.get("wides"), noballs=c.get("noballs"),
        fours_conceded=c.get("fours_conceded"), sixes_conceded=c.get("sixes_conceded"),
        dots=c.get("dots"),
        wickets=wkt_rows[0]["wickets"] if wkt_rows else 0,
    )


@router.get("/bowling/by-phase")
async def scope_bowling_by_phase(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted bowling phase splits."""
    if is_precomputed_scope(filters, aux):
        return await _bowling_by_phase_from_baseline(filters, aux)
    return await _bowling_by_phase_live(filters, aux)


def _format_bowling_phase_row(phase, ranges, runs_conceded, balls, fours_conceded, sixes_conceded, dots, wickets):
    runs = runs_conceded or 0
    balls = balls or 0
    fours = fours_conceded or 0
    sixes = sixes_conceded or 0
    dots = dots or 0
    boundaries = fours + sixes
    return {
        "phase": phase, "overs_range": ranges,
        "runs_conceded": runs, "balls": balls,
        "economy": _safe_div(runs, balls, 6),
        "wickets": wickets or 0,
        "boundary_pct": _safe_div(boundaries, balls, 100, 1),
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours_conceded": fours, "sixes_conceded": sixes,
    }


async def _bowling_by_phase_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT phase,
               SUM(runs) AS runs_conceded,
               SUM(legal_balls) AS balls,
               SUM(fours) AS fours_conceded,
               SUM(sixes) AS sixes_conceded,
               SUM(dots) AS dots,
               SUM(wickets) AS wickets
        FROM bucketbaselinephase {where} AND side='bowling'
        GROUP BY phase
        """,
        params,
    )
    by_phase = {r["phase"]: r for r in rows if r["phase"]}
    out = [
        _format_bowling_phase_row(
            phase=phase, ranges=ranges,
            runs_conceded=(by_phase.get(phase) or {}).get("runs_conceded"),
            balls=(by_phase.get(phase) or {}).get("balls"),
            fours_conceded=(by_phase.get(phase) or {}).get("fours_conceded"),
            sixes_conceded=(by_phase.get(phase) or {}).get("sixes_conceded"),
            dots=(by_phase.get(phase) or {}).get("dots"),
            wickets=(by_phase.get(phase) or {}).get("wickets"),
        )
        for phase, ranges in OVER_RANGES
    ]
    return _phase_per_innings(out, await _baseline_innings_bowled(filters, aux))


async def _bowling_by_phase_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.over_number BETWEEN 0 AND 19
        GROUP BY phase
        """,
        params,
    )
    by_phase = {r["phase"]: r for r in rows if r["phase"]}

    wkt_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.over_number BETWEEN 0 AND 19
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')
        GROUP BY phase
        """,
        params,
    )
    wkt_by_phase = {r["phase"]: r["wickets"] for r in wkt_rows if r["phase"]}

    out = [
        _format_bowling_phase_row(
            phase=phase, ranges=ranges,
            runs_conceded=(by_phase.get(phase) or {}).get("runs_conceded"),
            balls=(by_phase.get(phase) or {}).get("balls"),
            fours_conceded=(by_phase.get(phase) or {}).get("fours_conceded"),
            sixes_conceded=(by_phase.get(phase) or {}).get("sixes_conceded"),
            dots=(by_phase.get(phase) or {}).get("dots"),
            wickets=wkt_by_phase.get(phase, 0),
        )
        for phase, ranges in OVER_RANGES
    ]
    return _phase_per_innings(out, await _live_innings_bowled(filters, aux))


@router.get("/bowling/by-season")
async def scope_bowling_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted bowling aggregates per season."""
    if is_precomputed_scope(filters, aux):
        return await _bowling_by_season_from_baseline(filters, aux)
    return await _bowling_by_season_live(filters, aux)


def _format_bowling_season_row(season, innings_bowled, runs_conceded, legal_balls, boundaries_conceded, dots, wickets):
    runs = runs_conceded or 0
    balls = legal_balls or 0
    inn = innings_bowled or 0
    out = {
        "season": season,
        "innings_bowled": inn,
        "runs_conceded": runs,
        "legal_balls": balls,
        "overs": round(balls / 6, 1) if balls else 0,
        "wickets": wickets or 0,
        "economy": _safe_div(runs, balls, 6),
        "dot_pct": _safe_div(dots or 0, balls, 100, 1),
        "boundaries_conceded": boundaries_conceded or 0,
    }
    # `boundaries_conceded` isn't in BOWLING_COUNT_KEYS — divide it
    # explicitly per spec by-season transform.
    if inn:
        out["boundaries_conceded"] = round((boundaries_conceded or 0) / inn, 2)
    return _apply_bowling_per_innings(out, inn, drop_divisor=True)


async def _bowling_by_season_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT season,
               SUM(innings_bowled) AS innings_bowled,
               SUM(runs_conceded) AS runs_conceded,
               SUM(legal_balls) AS legal_balls,
               SUM(fours_conceded + sixes_conceded) AS boundaries_conceded,
               SUM(dots) AS dots,
               SUM(wickets) AS wickets
        FROM bucketbaselinebowling {where}
        GROUP BY season ORDER BY season
        """,
        params,
    )
    return {"by_season": [_format_bowling_season_row(**r) for r in rows]}


async def _bowling_by_season_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(DISTINCT i.id) as innings_bowled,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN (d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0)
                     OR d.runs_batter = 6 THEN 1 ELSE 0 END) as boundaries_conceded,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    wkt_rows = await db.q(
        f"""
        SELECT m.season, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')
        GROUP BY m.season
        """,
        params,
    )
    wkt_by_season = {r["season"]: r["wickets"] for r in wkt_rows}
    return {"by_season": [
        _format_bowling_season_row(
            season=r["season"], innings_bowled=r["innings_bowled"],
            runs_conceded=r["runs_conceded"], legal_balls=r["legal_balls"],
            boundaries_conceded=r["boundaries_conceded"], dots=r["dots"],
            wickets=wkt_by_season.get(r["season"], 0),
        )
        for r in rows
    ]}


# ============================================================
# Fielding
# ============================================================

@router.get("/fielding/summary")
async def scope_fielding_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope fielding aggregates."""
    if is_precomputed_scope(filters, aux):
        return await _fielding_summary_from_baseline(filters, aux)
    return await _fielding_summary_live(filters, aux)


def _format_fielding_summary(matches, catches_only, caught_and_bowled, stumpings, run_outs, *, inning_active: bool = False):
    matches = matches or 0
    catches_only = catches_only or 0
    cnb = caught_and_bowled or 0
    stumpings = stumpings or 0
    run_outs = run_outs or 0
    catches = catches_only + cnb  # response.catches includes c_a_b
    out = {
        "matches": matches,
        "catches": catches,
        "caught_and_bowled": cnb,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches + stumpings + run_outs,
        "catches_per_match": _safe_div(catches, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }
    # inning_active narrows each match to 1 fielding innings in scope
    # (vs 2 for the all-innings case). Spec: spec-inning-split.md §5.5.
    mult = 1 if inning_active else 2
    return _apply_fielding_per_innings(
        out, matches * mult, halve_per_match=not inning_active,
    )


async def _fielding_summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT SUM(matches) AS matches,
               SUM(catches) AS catches_only,
               SUM(caught_and_bowled) AS caught_and_bowled,
               SUM(stumpings) AS stumpings,
               SUM(run_outs) AS run_outs
        FROM bucketbaselinefielding {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    inning_active = aux is not None and aux.inning is not None
    return _format_fielding_summary(
        matches=r.get("matches"),
        catches_only=r.get("catches_only"),
        caught_and_bowled=r.get("caught_and_bowled"),
        stumpings=r.get("stumpings"),
        run_outs=r.get("run_outs"),
        inning_active=inning_active,
    )


async def _fielding_summary_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled') THEN 1 ELSE 0 END) as catches,
            SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) as caught_and_bowled,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) as stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) as run_outs
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    matches_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM match m
        JOIN innings i ON i.match_id = m.id
        WHERE {where}
        """,
        params,
    )
    matches = matches_rows[0]["matches"] if matches_rows else 0
    # Live SQL puts c_a_b into "catches"; baseline keeps them split.
    # Normalise to the baseline shape so the formatter handles both.
    catches_with_cnb = r.get("catches") or 0
    cnb = r.get("caught_and_bowled") or 0
    inning_active = aux is not None and aux.inning is not None
    return _format_fielding_summary(
        matches=matches,
        catches_only=catches_with_cnb - cnb,
        caught_and_bowled=cnb,
        stumpings=r.get("stumpings") or 0,
        run_outs=r.get("run_outs") or 0,
        inning_active=inning_active,
    )


@router.get("/fielding/by-season")
async def scope_fielding_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted fielding aggregates per season."""
    if is_precomputed_scope(filters, aux):
        return await _fielding_by_season_from_baseline(filters, aux)
    return await _fielding_by_season_live(filters, aux)


def _format_fielding_season_row(season, matches, catches, stumpings, run_outs, *, inning_active: bool = False):
    matches = matches or 0
    catches = catches or 0
    stumpings = stumpings or 0
    run_outs = run_outs or 0
    out = {
        "season": season,
        "matches": matches,
        "catches": catches,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches + stumpings + run_outs,
        "catches_per_match": _safe_div(catches, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }
    mult = 1 if inning_active else 2
    return _apply_fielding_per_innings(
        out, matches * mult, halve_per_match=not inning_active,
    )


async def _fielding_by_season_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    # SUM matches per season from bucketbaselinematch (matches denominator);
    # SUM catches+stumpings+run_outs from bucketbaselinefielding.
    f_rows = await db.q(
        f"""
        SELECT season,
               SUM(catches + caught_and_bowled) AS catches,
               SUM(stumpings) AS stumpings,
               SUM(run_outs) AS run_outs
        FROM bucketbaselinefielding {where}
        GROUP BY season
        HAVING SUM(catches + caught_and_bowled + stumpings + run_outs) > 0
        ORDER BY season
        """,
        params,
    )
    where_m, params_m = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    m_rows = await db.q(
        f"SELECT season, SUM(matches) AS matches FROM bucketbaselinematch {where_m} GROUP BY season",
        params_m,
    )
    m_by_season = {r["season"]: r["matches"] for r in m_rows}
    inning_active = aux is not None and aux.inning is not None
    return {"by_season": [
        _format_fielding_season_row(
            season=r["season"], matches=m_by_season.get(r["season"], 0),
            catches=r["catches"], stumpings=r["stumpings"], run_outs=r["run_outs"],
            inning_active=inning_active,
        )
        for r in f_rows
    ]}


async def _fielding_by_season_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            m.season,
            SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled') THEN 1 ELSE 0 END) as catches,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) as stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) as run_outs
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    matches_rows = await db.q(
        f"""
        SELECT m.season, COUNT(DISTINCT m.id) as matches
        FROM match m
        JOIN innings i ON i.match_id = m.id
        WHERE {where}
        GROUP BY m.season
        """,
        params,
    )
    matches_by_season = {r["season"]: r["matches"] for r in matches_rows}
    inning_active = aux is not None and aux.inning is not None
    return {"by_season": [
        _format_fielding_season_row(
            season=r["season"], matches=matches_by_season.get(r["season"], 0),
            catches=r["catches"], stumpings=r["stumpings"], run_outs=r["run_outs"],
            inning_active=inning_active,
        )
        for r in rows
    ]}


# ============================================================
# Partnerships
# ============================================================

@router.get("/partnerships/summary")
async def scope_partnerships_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted partnership aggregates across the whole league."""
    if is_precomputed_scope(filters, aux):
        return await _partnerships_summary_from_baseline(filters, aux)
    return await _partnerships_summary_live(filters, aux)


async def _fetch_partnership_identity(db, partnership_id: int) -> dict | None:
    """One small SELECT against partnership table for identity payload —
    same shape as the live endpoint's `highest` / `best_partnership`."""
    if partnership_id is None:
        return None
    rows = await db.q(
        """
        SELECT p.id AS partnership_id, p.partnership_runs AS runs,
               p.partnership_balls AS balls,
               p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
               m.id AS match_id, m.season, m.event_name AS tournament,
               i.team AS team,
               (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) AS date
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE p.id = :pid
        """,
        {"pid": partnership_id},
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "partnership_id": r["partnership_id"],
        "match_id": r["match_id"],
        "date": r["date"],
        "season": r["season"],
        "tournament": r["tournament"],
        "team": r["team"],
        "batter1": {"person_id": r["batter1_id"], "name": r["batter1_name"]},
        "batter2": {"person_id": r["batter2_id"], "name": r["batter2_name"]},
        "runs": r["runs"],
        "balls": r["balls"],
    }


async def _partnerships_summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT SUM(n) AS total,
               SUM(count_50_plus) AS count_50_plus,
               SUM(count_100_plus) AS count_100_plus,
               SUM(total_runs) AS total_runs
        FROM bucketbaselinepartnership {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    total = r.get("total") or 0
    avg_runs = round((r.get("total_runs") or 0) / total, 1) if total else None
    # Highest: pick row with MAX(best_runs); fetch identity by partnership_id.
    hi_rows = await db.q(
        f"""
        SELECT best_runs, best_pair_partnership_id
        FROM bucketbaselinepartnership {where} AND best_runs > 0
        ORDER BY best_runs DESC, best_pair_partnership_id LIMIT 1
        """,
        params,
    )
    highest = None
    if hi_rows:
        highest_full = await _fetch_partnership_identity(db, hi_rows[0]["best_pair_partnership_id"])
        if highest_full:
            # /partnerships/summary live shape strips tournament/season/
            # partnership_id from the identity payload — match it.
            highest = {
                "runs": highest_full["runs"], "balls": highest_full["balls"],
                "match_id": highest_full["match_id"], "date": highest_full["date"],
                "team": highest_full["team"],
                "batter1": highest_full["batter1"],
                "batter2": highest_full["batter2"],
            }
    out = {
        "total": total,
        "count_50_plus": r.get("count_50_plus") or 0,
        "count_100_plus": r.get("count_100_plus") or 0,
        "avg_runs": avg_runs,
        "highest": highest,
    }
    return _apply_partnerships_per_innings(out, await _baseline_innings_batted(filters, aux))


async def _partnerships_summary_live(filters, aux):
    db = get_db()
    where, params = _partnership_filter(filters, None, "batting", aux=aux)

    core = await db.q(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN p.partnership_runs >= 50 THEN 1 ELSE 0 END) as count_50_plus,
            SUM(CASE WHEN p.partnership_runs >= 100 THEN 1 ELSE 0 END) as count_100_plus,
            ROUND(AVG(p.partnership_runs), 1) as avg_runs,
            MAX(p.partnership_runs) as best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        """,
        params,
    )
    c = core[0] if core else {}
    total = c.get("total") or 0
    best = c.get("best_runs")

    highest = None
    if best:
        hi_rows = await db.q(
            f"""
            SELECT p.id, p.partnership_runs as runs, p.partnership_balls as balls,
                   p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
                   m.id as match_id,
                   (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
                   i.team as team
            FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
              AND p.partnership_runs = :best
            ORDER BY p.id
            LIMIT 1
            """,
            {**params, "best": best},
        )
        if hi_rows:
            r = hi_rows[0]
            highest = {
                "runs": r["runs"], "balls": r["balls"],
                "match_id": r["match_id"], "date": r["date"],
                "team": r["team"],
                "batter1": {"person_id": r["batter1_id"], "name": r["batter1_name"]},
                "batter2": {"person_id": r["batter2_id"], "name": r["batter2_name"]},
            }

    out = {
        "total": total,
        "count_50_plus": c.get("count_50_plus") or 0,
        "count_100_plus": c.get("count_100_plus") or 0,
        "avg_runs": c.get("avg_runs"),
        "highest": highest,
    }
    return _apply_partnerships_per_innings(out, await _live_innings_batted(filters, aux))


@router.get("/partnerships/by-wicket")
async def scope_partnerships_by_wicket(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-wicket league averages — runs / partnership at each wicket
    position. The `best_partnership` per wicket carries identity
    (specific pair + match)."""
    if is_precomputed_scope(filters, aux):
        return await _partnerships_by_wicket_from_baseline(filters, aux)
    return await _partnerships_by_wicket_live(filters, aux)


async def _partnerships_by_wicket_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    # Aggregate per wicket_number: SUM counters, MAX best_runs.
    agg_rows = await db.q(
        f"""
        SELECT wicket_number,
               SUM(n) AS n,
               SUM(total_runs) AS total_runs,
               SUM(total_balls) AS total_balls,
               COALESCE(MAX(best_runs), 0) AS best_runs
        FROM bucketbaselinepartnership {where}
        GROUP BY wicket_number ORDER BY wicket_number
        """,
        params,
    )
    # Per wicket, find the cell holding MAX(best_runs); then
    # _fetch_partnership_identity. One small SELECT per wicket
    # position (max 10 calls).
    by_wicket = []
    for r in agg_rows:
        wn = r["wicket_number"]
        best = None
        if r["best_runs"]:
            id_rows = await db.q(
                f"""
                SELECT best_pair_partnership_id
                FROM bucketbaselinepartnership {where}
                  AND wicket_number = :_wn AND best_runs > 0
                ORDER BY best_runs DESC, best_pair_partnership_id LIMIT 1
                """,
                {**params, "_wn": wn},
            )
            if id_rows:
                best = await _fetch_partnership_identity(db, id_rows[0]["best_pair_partnership_id"])
        n = r["n"] or 0
        by_wicket.append({
            "wicket_number": wn,
            "n": n,
            "avg_runs": round((r["total_runs"] or 0) / n, 1) if n else None,
            "avg_balls": round((r["total_balls"] or 0) / n, 1) if n else None,
            "best_runs": r["best_runs"] or 0,
            "best_partnership": best,
        })
    return _by_wicket_per_innings(by_wicket, await _baseline_innings_batted(filters, aux))


def _by_wicket_per_innings(rows: list[dict], innings_batted: int) -> dict:
    """Divide each by-wicket row's `n` count by innings_batted —
    spec-avg-column-per-innings.md `/scope/averages/partnerships/by-wicket`."""
    if innings_batted and innings_batted > 0:
        for r in rows:
            v = r.get("n")
            if v is not None:
                r["n"] = round(v / innings_batted, 2)
    return {"by_wicket": rows}


async def _partnerships_by_wicket_live(filters, aux):
    db = get_db()
    where, params = _partnership_filter(filters, None, "batting", aux=aux)

    rows = await db.q(
        f"""
        SELECT p.wicket_number,
               COUNT(*) as n,
               ROUND(AVG(p.partnership_runs), 1) as avg_runs,
               ROUND(AVG(p.partnership_balls), 1) as avg_balls,
               MAX(p.partnership_runs) as best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.wicket_number IS NOT NULL
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY p.wicket_number
        ORDER BY p.wicket_number
        """,
        params,
    )

    by_wicket = []
    for r in rows:
        wn = r["wicket_number"]
        best = None
        if r["best_runs"]:
            best_rows = await db.q(
                f"""
                SELECT p.id as partnership_id, p.partnership_runs as runs,
                       p.partnership_balls as balls,
                       p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
                       m.id as match_id, m.season, m.event_name as tournament,
                       i.team as team,
                       (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date
                FROM partnership p
                JOIN innings i ON i.id = p.innings_id
                JOIN match m ON m.id = i.match_id
                WHERE {where}
                  AND p.wicket_number = :wn
                  AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
                  AND p.partnership_runs = :best
                ORDER BY p.id
                LIMIT 1
                """,
                {**params, "wn": wn, "best": r["best_runs"]},
            )
            if best_rows:
                bb = best_rows[0]
                best = {
                    "partnership_id": bb["partnership_id"],
                    "match_id": bb["match_id"],
                    "date": bb["date"],
                    "season": bb["season"],
                    "tournament": bb["tournament"],
                    "team": bb["team"],
                    "runs": bb["runs"],
                    "balls": bb["balls"],
                    "batter1": {"person_id": bb["batter1_id"], "name": bb["batter1_name"]},
                    "batter2": {"person_id": bb["batter2_id"], "name": bb["batter2_name"]},
                }
        by_wicket.append({
            "wicket_number": wn,
            "n": r["n"],
            "avg_runs": r["avg_runs"],
            "avg_balls": r["avg_balls"],
            "best_runs": r["best_runs"],
            "best_partnership": best,
        })
    return _by_wicket_per_innings(by_wicket, await _live_innings_batted(filters, aux))


@router.get("/partnerships/by-season")
async def scope_partnerships_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-season partnership aggregates across the whole league."""
    if is_precomputed_scope(filters, aux):
        return await _partnerships_by_season_from_baseline(filters, aux)
    return await _partnerships_by_season_live(filters, aux)


async def _partnerships_by_season_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT season,
               SUM(n) AS total,
               SUM(count_50_plus) AS count_50_plus,
               SUM(count_100_plus) AS count_100_plus,
               SUM(total_runs) AS total_runs,
               COALESCE(MAX(best_runs), 0) AS best_runs
        FROM bucketbaselinepartnership {where}
        GROUP BY season ORDER BY season
        """,
        params,
    )
    # Per-season innings_batted divisor from bucketbaselinebatting (same scope).
    where_b, params_b = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    inn_rows = await db.q(
        f"SELECT season, SUM(innings_batted) AS innings_batted FROM bucketbaselinebatting {where_b} GROUP BY season",
        params_b,
    )
    inn_by_season = {r["season"]: r["innings_batted"] or 0 for r in inn_rows}
    out = []
    for r in rows:
        total = r["total"] or 0
        season = r["season"]
        row = {
            "season": season,
            "total": total,
            "count_50_plus": r["count_50_plus"] or 0,
            "count_100_plus": r["count_100_plus"] or 0,
            "avg_runs": round((r["total_runs"] or 0) / total, 1) if total else None,
            "best_runs": r["best_runs"],
        }
        out.append(_apply_partnerships_per_innings(row, inn_by_season.get(season, 0)))
    return {"by_season": out}


async def _partnerships_by_season_live(filters, aux):
    db = get_db()
    where, params = _partnership_filter(filters, None, "batting", aux=aux)

    rows = await db.q(
        f"""
        SELECT m.season,
               COUNT(*) as total,
               SUM(CASE WHEN p.partnership_runs >= 50 THEN 1 ELSE 0 END) as count_50_plus,
               SUM(CASE WHEN p.partnership_runs >= 100 THEN 1 ELSE 0 END) as count_100_plus,
               ROUND(AVG(p.partnership_runs), 1) as avg_runs,
               MAX(p.partnership_runs) as best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    # Per-season innings_batted divisor — same scope, side='batting'.
    where_inn, params_inn = _team_innings_clause(filters, None, side="batting", aux=aux)
    inn_rows = await db.q(
        f"""
        SELECT m.season, COUNT(DISTINCT i.id) AS innings_batted
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where_inn}
        GROUP BY m.season
        """,
        params_inn,
    )
    inn_by_season = {r["season"]: r["innings_batted"] or 0 for r in inn_rows}
    out = []
    for r in rows:
        season = r["season"]
        row = {
            "season": season,
            "total": r["total"] or 0,
            "count_50_plus": r["count_50_plus"] or 0,
            "count_100_plus": r["count_100_plus"] or 0,
            "avg_runs": r["avg_runs"],
            "best_runs": r["best_runs"],
        }
        out.append(_apply_partnerships_per_innings(row, inn_by_season.get(season, 0)))
    return {"by_season": out}


# ════════════════════════════════════════════════════════════════════
# /scope/averages/players/* — Phase 3 of spec-player-compare-average.md
# ════════════════════════════════════════════════════════════════════
#
# Position-adaptive cohort baseline endpoints. Each accepts a mix
# vector + the standard FilterBar axes (scope_key axes honoured;
# venue/team/opponent/team_class/series_type scope below the
# precomputed-table grain and are intentionally NOT applied — matches
# Phase 2's /summary distribution-array contract).
#
# Strict-cliff sliding scale: if any bucket the player has non-zero
# mix-weight on has a cohort sample below the bucket's threshold, the
# entire response's `scope_avg` is null. Convex combination over the
# player's full mix otherwise — no drops, no renormalisation.
# Spec §5.1 + §6.


async def _batting_cohort_precomputed(
    db, filters: FilterParams, drop_set: Optional[set[str]],
):
    """Fast path: aggregate the precomputed `playerscopestatsposition`
    table by `scope_key`. Used when none of the six aux/filter axes
    (venue / opponent / team / inning / toss / result) is set.

    The scope_key IN-subquery beats a JOIN to playerscopestats by ~5×
    on unfiltered scopes (SQLite picks parent-first scan-and-search for
    the JOIN form; IN-subquery seeks the scope_key index). Parallel
    pool query halves total latency."""
    where, params = build_scope_clauses(filters, drop=drop_set)
    main_sql = f"""
        SELECT pssp.position_bucket,
               SUM(pssp.innings)      AS innings,
               SUM(pssp.runs)         AS runs,
               SUM(pssp.legal_balls)  AS legal_balls,
               SUM(pssp.dismissals)   AS dismissals,
               SUM(pssp.fours)        AS fours,
               SUM(pssp.sixes)        AS sixes,
               SUM(pssp.dots)         AS dots,
               SUM(pssp.thirties)     AS thirties,
               SUM(pssp.fifties)      AS fifties,
               SUM(pssp.hundreds)     AS hundreds,
               SUM(pssp.ducks)        AS ducks,
               SUM(pssp.failures_10)  AS failures_10,
               SUM(pssp.seventies)    AS seventies,
               COUNT(DISTINCT pssp.person_id) AS n_players
        FROM playerscopestatsposition pssp
        WHERE pssp.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
        GROUP BY pssp.position_bucket
        ORDER BY pssp.position_bucket
    """
    pool_sql = f"""
        SELECT COUNT(DISTINCT pssp.person_id) AS n_players,
               SUM(pssp.innings)              AS n_innings_total
        FROM playerscopestatsposition pssp
        WHERE pssp.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
    """
    return await asyncio.gather(db.q(main_sql, params), db.q(pool_sql, params))


def _batting_live_where(filters: FilterParams, aux: AuxParams) -> tuple[str, dict]:
    """Build the per-innings (or per-delivery) WHERE for the live batting
    cohort paths (3b summary + 3c by-season / by-phase). Assumes the
    query joins `innings i` and `match m`; reuses the team-side cohort
    clauses keyed on `i.team` so the league baseline narrows
    apples-to-apples with the player's own number under the SIX
    aux/filter axes (venue / opponent / team / inning / toss / result).

    Returns `(where_sql, params)` — the caller AND-joins it after any
    table-specific predicate (e.g. `ib.batter_id = :__pid` for the
    player-side mix query). Spec: spec-player-baseline-aux-fallback.md
    Phase 3b/3c."""
    where, params = filters.build(has_innings_join=True, apply_inning=False, aux=aux)
    parts = ["i.super_over = 0"]
    if where:
        parts.append(where)
    inn_clause, inn_params = _option_b_team_inning(None, "batting", aux)
    if inn_clause:
        parts.append(inn_clause)
        params.update(inn_params)
    coh_clause, coh_params = _cohort_outcome_clause("batting", aux)
    if coh_clause:
        parts.append(coh_clause)
        params.update(coh_params)
    return " AND ".join(parts), params


async def _batting_cohort_live(
    db, filters: FilterParams, aux: AuxParams,
):
    """Live path: aggregate `inningsbatterperf` joined to innings+match
    so the SIX aux/filter axes (venue / opponent / team / inning / toss
    / result) actually narrow the cohort. Reuses team-side cohort
    clauses keyed on `i.team` so the league baseline is apples-to-apples
    with the player's own narrowed number (chip↔baseline symmetry).

    The per-innings table carries every column the precomputed read
    derives (runs/balls/dots/fours/sixes per innings + not_out +
    position_bucket); it's an exact-integer rollup of
    `playerscopestatsposition` at none-of-six (verified by
    `tests/sanity/test_playerscopestatsposition_rollup.py`), so the
    dispatch can't introduce a step at the gate boundary.

    Spec: internal_docs/spec-player-baseline-aux-fallback.md Phase 3b
    + internal_docs/plan-3b-batting-live-cohort.md."""
    where_full, params = _batting_live_where(filters, aux)
    main_sql = f"""
        SELECT ib.position_bucket,
               COUNT(*)                                                       AS innings,
               SUM(ib.runs)                                                   AS runs,
               SUM(ib.balls)                                                  AS legal_balls,
               SUM(CASE WHEN ib.not_out = 0                  THEN 1 ELSE 0 END) AS dismissals,
               SUM(ib.fours)                                                  AS fours,
               SUM(ib.sixes)                                                  AS sixes,
               SUM(ib.dots)                                                   AS dots,
               SUM(CASE WHEN ib.runs >= 30 AND ib.runs < 50  THEN 1 ELSE 0 END) AS thirties,
               SUM(CASE WHEN ib.runs >= 50 AND ib.runs < 100 THEN 1 ELSE 0 END) AS fifties,
               SUM(CASE WHEN ib.runs >= 100                  THEN 1 ELSE 0 END) AS hundreds,
               SUM(CASE WHEN ib.runs  = 0 AND ib.not_out = 0 THEN 1 ELSE 0 END) AS ducks,
               SUM(CASE WHEN ib.runs <= 10                   THEN 1 ELSE 0 END) AS failures_10,
               SUM(CASE WHEN ib.runs >= 70 AND ib.runs < 100 THEN 1 ELSE 0 END) AS seventies,
               COUNT(DISTINCT ib.batter_id)                                   AS n_players
        FROM inningsbatterperf ib
        JOIN innings i ON i.id = ib.innings_id
        JOIN match   m ON m.id = i.match_id
        WHERE {where_full}
        GROUP BY ib.position_bucket
        ORDER BY ib.position_bucket
    """
    pool_sql = f"""
        SELECT COUNT(DISTINCT ib.batter_id) AS n_players,
               COUNT(*)                     AS n_innings_total
        FROM inningsbatterperf ib
        JOIN innings i ON i.id = ib.innings_id
        JOIN match   m ON m.id = i.match_id
        WHERE {where_full}
    """
    return await asyncio.gather(db.q(main_sql, params), db.q(pool_sql, params))


async def compute_players_batting_cohort(
    db,
    filters: FilterParams,
    aux: AuxParams,
    mix: list[float],
    drop_set: Optional[set[str]] = None,
) -> dict:
    """In-process batting cohort baseline — same shape as the HTTP
    endpoint. Phase 4 player /summary endpoints call this to fold the
    cohort baseline into their envelope-wrapped response without a
    second HTTP roundtrip. The HTTP endpoint is a thin wrapper.

    Dispatches on `is_precomputed_scope`:
      - none of the six set → fast precomputed read
        (`_batting_cohort_precomputed`).
      - any of the six set → live aggregation over inningsbatterperf
        (`_batting_cohort_live`) so the cohort actually narrows.

    `drop_set` masks scope-key axes on the precomputed path only — the
    live path queries the match table directly, where the axes are
    already first-class WHERE clauses; current batting callers pass
    None.

    Specs: spec-player-compare-average.md Phase 4 (backend folding) +
    spec-player-baseline-aux-fallback.md Phase 3b (live fallback)."""
    if is_precomputed_scope(filters, aux):
        rows, pool = await _batting_cohort_precomputed(db, filters, drop_set)
    else:
        rows, pool = await _batting_cohort_live(db, filters, aux)
    by_bucket = {r["position_bucket"]: r for r in rows}
    n_players_total = (pool[0].get("n_players") if pool else 0) or 0
    n_innings_total = (pool[0].get("n_innings_total") if pool else 0) or 0

    by_position: list[dict] = []
    for b in range(1, 11):
        r = by_bucket.get(b)
        threshold = batting_threshold(b)
        if r is None:
            by_position.append({
                "bucket": b, "label": batting_bucket_label(b),
                "n_innings": 0, "n_players": 0, "threshold": threshold,
                "below_support": True,
                "innings_per_player": None, "runs_per_player": None,
                "average": None, "strike_rate": None,
                "boundary_pct": None, "dot_pct": None,
                "balls_per_four": None, "balls_per_six": None,
                "balls_per_boundary": None,
                # Tier 1 of spec-apples-to-apples-baselines.md —
                # per-position per-innings rates so the cohort baseline
                # can convex-combine over the player's position mix.
                "runs_per_innings": None,
                "fours_per_innings": None,
                "sixes_per_innings": None,
                "boundaries_per_innings": None,
                "thirties_per_innings": None,
                "fifties_per_innings": None,
                "hundreds_per_innings": None,
                "ducks_per_innings": None,
                # PT1 of spec-prob-baselines.md — per-bucket prob rates
                # for the batting ProbChip cohort baselines. Simples
                # divide milestone count by innings; conditionals divide
                # the milestone count at the higher threshold by the
                # count at the lower threshold (NOT cv-of-ratios — see
                # spec §4.3).
                "prob_failures_10":  None,
                "prob_30_plus":      None,
                "prob_50_plus":      None,
                "prob_100_plus":     None,
                "prob_50_given_30":  None,
                "prob_70_given_50":  None,
            })
            continue
        innings = r["innings"] or 0
        runs = r["runs"] or 0
        balls = r["legal_balls"] or 0
        dismissals = r["dismissals"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        boundaries = fours + sixes
        dots = r["dots"] or 0
        thirties = r["thirties"] or 0
        fifties = r["fifties"] or 0
        hundreds = r["hundreds"] or 0
        ducks = r["ducks"] or 0
        failures_10 = r["failures_10"] or 0
        seventies = r["seventies"] or 0
        # PT1 of spec-prob-baselines.md — derived milestone counts for
        # the prob simples + conditionals. `count_50` and `count_30` are
        # the conditional denominators ("innings reaching ≥X").
        count_50 = fifties + hundreds
        count_30 = thirties + fifties + hundreds
        count_70 = seventies + hundreds
        n_p = r["n_players"] or 0
        by_position.append({
            "bucket": b, "label": batting_bucket_label(b),
            "n_innings": innings, "n_players": n_p, "threshold": threshold,
            "below_support": innings < threshold,
            "innings_per_player": round(innings / n_p, 2) if n_p else None,
            "runs_per_player":    round(runs / n_p, 2) if n_p else None,
            "average":            round(runs / dismissals, 2) if dismissals else None,
            "strike_rate":        round(runs / balls * 100, 1) if balls else None,
            "boundary_pct":       round(boundaries / balls * 100, 1) if balls else None,
            "dot_pct":            round(dots / balls * 100, 1) if balls else None,
            # Inverse boundary-frequency rates. Lower = better for the
            # batter (fewer balls between scoring shots). Convex-
            # combined like the other rates.
            "balls_per_four":      round(balls / fours, 2)      if fours else None,
            "balls_per_six":       round(balls / sixes, 2)      if sixes else None,
            "balls_per_boundary":  round(balls / boundaries, 2) if boundaries else None,
            # Per-position per-innings rates (Tier 1). Stored on
            # by_position so the convex-combine helper `cv` below can
            # mix them by the player's position mix — replaces the
            # scope-flat parent-table aggregate used pre-Tier 1.
            "runs_per_innings":       (runs / innings)       if innings else None,
            "fours_per_innings":      (fours / innings)      if innings else None,
            "sixes_per_innings":      (sixes / innings)      if innings else None,
            "boundaries_per_innings": (boundaries / innings) if innings else None,
            "thirties_per_innings":   (thirties / innings)   if innings else None,
            "fifties_per_innings":    (fifties / innings)    if innings else None,
            "hundreds_per_innings":   (hundreds / innings)   if innings else None,
            "ducks_per_innings":      (ducks / innings)      if innings else None,
            # PT1 of spec-prob-baselines.md — per-bucket prob rates.
            # Simples convex-combine cleanly. Conditionals get their
            # ratio computed AT the bucket grain (NOT as the ratio of
            # two convex-combines — see spec §4.3); under cliff buckets
            # the per-bucket prob is None and convex_combine skips it.
            "prob_failures_10": (failures_10 / innings) if innings else None,
            "prob_30_plus":     (count_30 / innings)    if innings else None,
            "prob_50_plus":     (count_50 / innings)    if innings else None,
            "prob_100_plus":    (hundreds / innings)    if innings else None,
            "prob_50_given_30": (count_50 / count_30)   if count_30 else None,
            "prob_70_given_50": (count_70 / count_50)   if count_50 else None,
        })

    # Strict-cliff gate.
    cliff_buckets: list[int] = [
        b for b in range(1, 11)
        if mix[b - 1] > 0 and by_position[b - 1]["below_support"]
    ]

    cohort_block = {
        "match_dimension": "position_mix",
        "position_mix": mix,
        "n_players": n_players_total,
        "n_innings_total": n_innings_total,
    }

    if cliff_buckets:
        return {
            "cohort": cohort_block,
            "below_support": True,
            "cliff_buckets": cliff_buckets,
            "innings_batted": wrap_metric(None, None, "bat_innings",     sample_size=n_innings_total),
            "runs":           wrap_metric(None, None, "bat_runs",        sample_size=n_innings_total),
            "average":        wrap_metric(None, None, "bat_average",     sample_size=n_innings_total),
            "strike_rate":    wrap_metric(None, None, "bat_strike_rate", sample_size=n_innings_total),
            "boundary_pct":   wrap_metric(None, None, "boundary_pct",    sample_size=n_innings_total),
            "dot_pct":        wrap_metric(None, None, "bat_dot_pct",     sample_size=n_innings_total),
            "balls_per_four":     wrap_metric(None, None, "bat_balls_per_four",     sample_size=n_innings_total),
            "balls_per_six":      wrap_metric(None, None, "bat_balls_per_six",      sample_size=n_innings_total),
            "balls_per_boundary": wrap_metric(None, None, "bat_balls_per_boundary", sample_size=n_innings_total),
            # Tier 1 of spec-apples-to-apples-baselines.md — per-innings
            # rates are now position-weighted via convex combination on
            # per-bucket rates. Under cliff, they null out alongside the
            # other rates (the player has weight on a thin bucket).
            "boundaries_per_innings": wrap_metric(None, None, "bat_boundaries_per_innings", sample_size=n_innings_total),
            "sixes_per_innings":      wrap_metric(None, None, "bat_sixes_per_innings",      sample_size=n_innings_total),
            "fours_per_innings":      wrap_metric(None, None, "bat_fours_per_innings",      sample_size=n_innings_total),
            "thirties_per_innings":   wrap_metric(None, None, "bat_thirties_per_innings",   sample_size=n_innings_total),
            "fifties_per_innings":    wrap_metric(None, None, "bat_fifties_per_innings",    sample_size=n_innings_total),
            "hundreds_per_innings":   wrap_metric(None, None, "bat_hundreds_per_innings",   sample_size=n_innings_total),
            "ducks_per_innings":      wrap_metric(None, None, "bat_ducks_per_innings",      sample_size=n_innings_total),
            "runs_per_innings":       wrap_metric(None, None, "bat_runs_per_innings",       sample_size=n_innings_total),
            # PT1 of spec-prob-baselines.md — chip probability cohort
            # baselines null out under cliff alongside the rates.
            "prob_failures_10": wrap_metric(None, None, "bat_prob_failures_10", sample_size=n_innings_total),
            "prob_30_plus":     wrap_metric(None, None, "bat_prob_30_plus",     sample_size=n_innings_total),
            "prob_50_plus":     wrap_metric(None, None, "bat_prob_50_plus",     sample_size=n_innings_total),
            "prob_100_plus":    wrap_metric(None, None, "bat_prob_100_plus",    sample_size=n_innings_total),
            "prob_50_given_30": wrap_metric(None, None, "bat_prob_50_given_30", sample_size=n_innings_total),
            "prob_70_given_50": wrap_metric(None, None, "bat_prob_70_given_50", sample_size=n_innings_total),
            "by_position": by_position,
        }

    def cv(field: str) -> Optional[float]:
        return convex_combine(mix, {b: by_position[b - 1][field] for b in range(1, 11)})

    cc_innings = cv("innings_per_player")
    cc_runs    = cv("runs_per_player")
    cc_avg     = cv("average")
    cc_sr      = cv("strike_rate")
    cc_bp      = cv("boundary_pct")
    cc_dp      = cv("dot_pct")
    cc_bpf     = cv("balls_per_four")
    cc_bps     = cv("balls_per_six")
    cc_bpb     = cv("balls_per_boundary")
    # Tier 1 of spec-apples-to-apples-baselines.md — position-weighted
    # per-innings rates. Replaces the prior scope-flat parent-table
    # aggregate; uses the same cv() helper as the per-balls rates.
    cc_runs_pi       = cv("runs_per_innings")
    cc_fours_pi      = cv("fours_per_innings")
    cc_sixes_pi      = cv("sixes_per_innings")
    cc_boundaries_pi = cv("boundaries_per_innings")
    cc_thirties_pi   = cv("thirties_per_innings")
    cc_fifties_pi    = cv("fifties_per_innings")
    cc_hundreds_pi   = cv("hundreds_per_innings")
    cc_ducks_pi      = cv("ducks_per_innings")
    # PT1 of spec-prob-baselines.md — convex-combine the per-bucket
    # prob rates. Conditionals use per-bucket (num/denom) so the cv is
    # the weighted average of bucket conditionals (NOT the ratio of two
    # cv'd marginals); see spec §4.3.
    cc_prob_failures_10 = cv("prob_failures_10")
    cc_prob_30_plus     = cv("prob_30_plus")
    cc_prob_50_plus     = cv("prob_50_plus")
    cc_prob_100_plus    = cv("prob_100_plus")
    cc_prob_50_given_30 = cv("prob_50_given_30")
    cc_prob_70_given_50 = cv("prob_70_given_50")

    def _r(v: Optional[float], ndigits: int) -> Optional[float]:
        return round(v, ndigits) if v is not None else None

    return {
        "cohort": cohort_block,
        "below_support": False,
        "cliff_buckets": [],
        "innings_batted": wrap_metric(_r(cc_innings, 2), _r(cc_innings, 2), "bat_innings",     sample_size=n_innings_total),
        "runs":           wrap_metric(_r(cc_runs, 2),    _r(cc_runs, 2),    "bat_runs",        sample_size=n_innings_total),
        "average":        wrap_metric(_r(cc_avg, 2),     _r(cc_avg, 2),     "bat_average",     sample_size=n_innings_total),
        "strike_rate":    wrap_metric(_r(cc_sr, 1),      _r(cc_sr, 1),      "bat_strike_rate", sample_size=n_innings_total),
        "boundary_pct":   wrap_metric(_r(cc_bp, 1),      _r(cc_bp, 1),      "boundary_pct",    sample_size=n_innings_total),
        "dot_pct":        wrap_metric(_r(cc_dp, 1),      _r(cc_dp, 1),      "bat_dot_pct",     sample_size=n_innings_total),
        "balls_per_four":     wrap_metric(_r(cc_bpf, 2), _r(cc_bpf, 2), "bat_balls_per_four",     sample_size=n_innings_total),
        "balls_per_six":      wrap_metric(_r(cc_bps, 2), _r(cc_bps, 2), "bat_balls_per_six",      sample_size=n_innings_total),
        "balls_per_boundary": wrap_metric(_r(cc_bpb, 2), _r(cc_bpb, 2), "bat_balls_per_boundary", sample_size=n_innings_total),
        # Tier 1: position-weighted per-innings rates.
        "boundaries_per_innings": wrap_metric(_r(cc_boundaries_pi, 3), _r(cc_boundaries_pi, 3), "bat_boundaries_per_innings", sample_size=n_innings_total),
        "sixes_per_innings":      wrap_metric(_r(cc_sixes_pi, 3),      _r(cc_sixes_pi, 3),      "bat_sixes_per_innings",      sample_size=n_innings_total),
        "fours_per_innings":      wrap_metric(_r(cc_fours_pi, 3),      _r(cc_fours_pi, 3),      "bat_fours_per_innings",      sample_size=n_innings_total),
        "thirties_per_innings":   wrap_metric(_r(cc_thirties_pi, 3),   _r(cc_thirties_pi, 3),   "bat_thirties_per_innings",   sample_size=n_innings_total),
        "fifties_per_innings":    wrap_metric(_r(cc_fifties_pi, 3),    _r(cc_fifties_pi, 3),    "bat_fifties_per_innings",    sample_size=n_innings_total),
        "hundreds_per_innings":   wrap_metric(_r(cc_hundreds_pi, 3),   _r(cc_hundreds_pi, 3),   "bat_hundreds_per_innings",   sample_size=n_innings_total),
        "ducks_per_innings":      wrap_metric(_r(cc_ducks_pi, 3),      _r(cc_ducks_pi, 3),      "bat_ducks_per_innings",      sample_size=n_innings_total),
        "runs_per_innings":       wrap_metric(_r(cc_runs_pi, 2),       _r(cc_runs_pi, 2),       "bat_runs_per_innings",       sample_size=n_innings_total),
        # PT1 of spec-prob-baselines.md — chip probability cohort
        # baselines. 4-dp matches the ProbRecord shape (existing `value`
        # field is also 4-dp via wilson.prob_record).
        "prob_failures_10": wrap_metric(_r(cc_prob_failures_10, 4), _r(cc_prob_failures_10, 4), "bat_prob_failures_10", sample_size=n_innings_total),
        "prob_30_plus":     wrap_metric(_r(cc_prob_30_plus, 4),     _r(cc_prob_30_plus, 4),     "bat_prob_30_plus",     sample_size=n_innings_total),
        "prob_50_plus":     wrap_metric(_r(cc_prob_50_plus, 4),     _r(cc_prob_50_plus, 4),     "bat_prob_50_plus",     sample_size=n_innings_total),
        "prob_100_plus":    wrap_metric(_r(cc_prob_100_plus, 4),    _r(cc_prob_100_plus, 4),    "bat_prob_100_plus",    sample_size=n_innings_total),
        "prob_50_given_30": wrap_metric(_r(cc_prob_50_given_30, 4), _r(cc_prob_50_given_30, 4), "bat_prob_50_given_30", sample_size=n_innings_total),
        "prob_70_given_50": wrap_metric(_r(cc_prob_70_given_50, 4), _r(cc_prob_70_given_50, 4), "bat_prob_70_given_50", sample_size=n_innings_total),
        "by_position": by_position,
    }


@router.get("/players/batting/summary")
async def scope_players_batting_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    position_mix: str = Query(
        ...,
        description=(
            "Comma-separated 10-element vector of the player's mix"
            " across position buckets (1=opener for positions 1+2"
            " merged, 2=#3, ..., 10=#11). Must sum to 1.0 +/- 0.001."
            " Trailing zeros may be omitted."
        ),
    ),
    drop: Optional[str] = Query(
        None,
        description=(
            "Comma-separated FilterBar axis names to mask before"
            " clause construction. Per-endpoint structural plumbing"
            " for tautology-prone cohort surfaces; unused for the"
            " player-compare baseline path. Recognised names:"
            " gender, team_type, tournament, season, filter_venue,"
            " filter_team, filter_opponent, team_class, series_type."
        ),
    ),
):
    """Position-mix-weighted cohort baseline for batting (HTTP wrapper)."""
    db = get_db()
    try:
        mix = parse_mix(position_mix, 10)
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                    f" Recognised: {sorted(_DROP_AXES)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_batting_cohort(db, filters, aux, mix, drop_set)


# ============================================================
# /scope/averages/players/batting/by-season — Phase 4 of
# spec-player-baseline-parity.md (this spec). Per-season cohort
# baseline computed under the player's PER-SEASON position-mix.
# Q2 decision: by-season endpoints take `person_id`, derive
# per-season mix server-side from playerscopestats_position.
# ============================================================


async def _by_season_precomputed(
    db, person_id: str, filters: FilterParams, drop_set: Optional[set[str]],
):
    """Fast path: per-(season, position) cohort + player-mix reads off the
    precomputed `playerscopestatsposition` table by scope_key. Used when
    none of the six aux/filter axes is set. Returns the
    `(player_rows, cohort_rows, pool_rows)` triple the downstream
    row-builder consumes."""
    where, params = build_scope_clauses(filters, drop=drop_set)

    # Q1: player's per-season position innings, for mix derivation.
    player_sql = f"""
        SELECT pss.season,
               pssp.position_bucket,
               pssp.innings
        FROM playerscopestatsposition pssp
        JOIN playerscopestats pss
          ON pss.scope_key = pssp.scope_key
         AND pss.person_id = pssp.person_id
        WHERE {where}
          AND pssp.person_id = :__pid
        ORDER BY pss.season, pssp.position_bucket
    """
    # Q2: cohort aggregates per (season, position_bucket) over the
    # whole population at the filtered scope.
    cohort_sql = f"""
        SELECT pss.season,
               pssp.position_bucket,
               SUM(pssp.innings)      AS innings,
               SUM(pssp.runs)         AS runs,
               SUM(pssp.legal_balls)  AS legal_balls,
               SUM(pssp.dismissals)   AS dismissals,
               SUM(pssp.fours)        AS fours,
               SUM(pssp.sixes)        AS sixes,
               SUM(pssp.dots)         AS dots,
               SUM(pssp.thirties)     AS thirties,
               SUM(pssp.fifties)      AS fifties,
               SUM(pssp.hundreds)     AS hundreds,
               SUM(pssp.ducks)        AS ducks,
               COUNT(DISTINCT pssp.person_id) AS n_players
        FROM playerscopestatsposition pssp
        JOIN playerscopestats pss
          ON pss.scope_key = pssp.scope_key
         AND pss.person_id = pssp.person_id
        WHERE {where}
        GROUP BY pss.season, pssp.position_bucket
        ORDER BY pss.season, pssp.position_bucket
    """
    # Q3: per-season pool totals (n_players, n_innings) — denominator
    # for the cohort_block metadata.
    pool_sql = f"""
        SELECT pss.season,
               COUNT(DISTINCT pssp.person_id) AS n_players,
               SUM(pssp.innings)              AS n_innings_total
        FROM playerscopestatsposition pssp
        JOIN playerscopestats pss
          ON pss.scope_key = pssp.scope_key
         AND pss.person_id = pssp.person_id
        WHERE {where}
        GROUP BY pss.season
        ORDER BY pss.season
    """
    p_params = {**params, "__pid": person_id}
    return await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(cohort_sql, params),
        db.q(pool_sql, params),
    )


async def _by_season_live(
    db, person_id: str, filters: FilterParams, aux: AuxParams,
):
    """Live path: per-(season, position) cohort + player-mix aggregated
    over `inningsbatterperf` joined to innings+match, so the six
    aux/filter axes (venue / opponent / team / inning / toss / result)
    actually narrow the per-season baseline. Mirrors 3b's
    `_batting_cohort_live` shape with `m.season` added to the GROUP BY.

    The player-side mix query (Q1) carries the SAME WHERE as the cohort
    (Q2) — narrowing the player's per-season position mix to the same
    pool so the convex-combine stays apples-to-apples (chip↔baseline
    symmetry under filtration). Column shape matches
    `_by_season_precomputed` so the downstream row-builder is identical.

    Spec: spec-player-baseline-aux-fallback.md Phase 3c
    + plan-3c-batting-by-season-by-phase-live.md §3."""
    where_full, params = _batting_live_where(filters, aux)

    # Q1: player's per-(season, position) innings at the narrowed scope.
    player_sql = f"""
        SELECT m.season,
               ib.position_bucket,
               COUNT(*) AS innings
        FROM inningsbatterperf ib
        JOIN innings i ON i.id = ib.innings_id
        JOIN match   m ON m.id = i.match_id
        WHERE {where_full}
          AND ib.batter_id = :__pid
        GROUP BY m.season, ib.position_bucket
        ORDER BY m.season, ib.position_bucket
    """
    # Q2: cohort aggregates per (season, position_bucket).
    cohort_sql = f"""
        SELECT m.season,
               ib.position_bucket,
               COUNT(*)                                                       AS innings,
               SUM(ib.runs)                                                   AS runs,
               SUM(ib.balls)                                                  AS legal_balls,
               SUM(CASE WHEN ib.not_out = 0                  THEN 1 ELSE 0 END) AS dismissals,
               SUM(ib.fours)                                                  AS fours,
               SUM(ib.sixes)                                                  AS sixes,
               SUM(ib.dots)                                                   AS dots,
               SUM(CASE WHEN ib.runs >= 30 AND ib.runs < 50  THEN 1 ELSE 0 END) AS thirties,
               SUM(CASE WHEN ib.runs >= 50 AND ib.runs < 100 THEN 1 ELSE 0 END) AS fifties,
               SUM(CASE WHEN ib.runs >= 100                  THEN 1 ELSE 0 END) AS hundreds,
               SUM(CASE WHEN ib.runs  = 0 AND ib.not_out = 0 THEN 1 ELSE 0 END) AS ducks,
               COUNT(DISTINCT ib.batter_id)                                   AS n_players
        FROM inningsbatterperf ib
        JOIN innings i ON i.id = ib.innings_id
        JOIN match   m ON m.id = i.match_id
        WHERE {where_full}
        GROUP BY m.season, ib.position_bucket
        ORDER BY m.season, ib.position_bucket
    """
    # Q3: per-season pool totals.
    pool_sql = f"""
        SELECT m.season,
               COUNT(DISTINCT ib.batter_id) AS n_players,
               COUNT(*)                     AS n_innings_total
        FROM inningsbatterperf ib
        JOIN innings i ON i.id = ib.innings_id
        JOIN match   m ON m.id = i.match_id
        WHERE {where_full}
        GROUP BY m.season
        ORDER BY m.season
    """
    p_params = {**params, "__pid": person_id}
    return await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(cohort_sql, params),
        db.q(pool_sql, params),
    )


async def compute_players_batting_by_season(
    db,
    person_id: str,
    filters: FilterParams,
    aux: AuxParams,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """Per-season batting cohort baseline keyed off the player's
    per-season position-mix. Returns `{by_season: [...]}` where each
    season row is one of:
      - {season, mix, n_players, n_innings, <metrics with scope_avg>}
      - {season, mix, n_players, n_innings, below_support: true,
         cliff_buckets: [...], <metrics all null>}

    Dispatches on `is_precomputed_scope` (mirrors 3b's summary path):
    none of the six set → precomputed scope-key read; any set → live
    aggregation over inningsbatterperf so the per-season cohort narrows.

    Spec: spec-player-baseline-parity.md §3.2 + Phase 3c of
    spec-player-baseline-aux-fallback.md.
    """
    if is_precomputed_scope(filters, aux):
        player_rows, cohort_rows, pool_rows = await _by_season_precomputed(
            db, person_id, filters, drop_set,
        )
    else:
        player_rows, cohort_rows, pool_rows = await _by_season_live(
            db, person_id, filters, aux,
        )

    # Roll cohort aggregates into {season: {bucket: row}}.
    cohort_by_season: dict[str, dict[int, dict]] = {}
    for r in cohort_rows:
        season = r["season"]
        cohort_by_season.setdefault(season, {})[r["position_bucket"]] = r

    # Pool totals per season.
    pool_by_season: dict[str, dict] = {r["season"]: r for r in pool_rows}

    # Player's per-season mix from innings per bucket.
    player_innings: dict[str, dict[int, int]] = {}
    for r in player_rows:
        player_innings.setdefault(r["season"], {})[r["position_bucket"]] = r["innings"]

    by_season: list[dict] = []
    for season in sorted(player_innings.keys()):
        # Derive mix vector from player innings.
        buckets = player_innings[season]
        total = sum(buckets.values())
        if total == 0:
            continue
        mix = [0.0] * 10
        for b, n in buckets.items():
            if 1 <= b <= 10:
                mix[b - 1] = n / total

        # Per-bucket cohort aggregates for this season.
        season_cohort = cohort_by_season.get(season, {})
        by_bucket: list[dict] = []
        cliff_buckets: list[int] = []
        for b in range(1, 11):
            threshold = batting_threshold(b)
            r = season_cohort.get(b)
            if r is None:
                by_bucket.append({"below_support": True, "innings": 0})
                if mix[b - 1] > 0:
                    cliff_buckets.append(b)
                continue
            innings = r["innings"] or 0
            runs = r["runs"] or 0
            balls = r["legal_balls"] or 0
            dismissals = r["dismissals"] or 0
            fours = r["fours"] or 0
            sixes = r["sixes"] or 0
            dots = r["dots"] or 0
            thirties = r["thirties"] or 0
            fifties = r["fifties"] or 0
            hundreds = r["hundreds"] or 0
            ducks = r["ducks"] or 0
            boundaries = fours + sixes
            n_p = r["n_players"] or 0
            below = innings < threshold
            if below and mix[b - 1] > 0:
                cliff_buckets.append(b)
            by_bucket.append({
                "below_support": below,
                "innings_per_player": (innings / n_p) if n_p else None,
                "runs_per_player":    (runs / n_p) if n_p else None,
                "average":            (runs / dismissals) if dismissals else None,
                "strike_rate":        (runs / balls * 100) if balls else None,
                "boundary_pct":       (boundaries / balls * 100) if balls else None,
                "dot_pct":            (dots / balls * 100) if balls else None,
                "balls_per_four":     (balls / fours) if fours else None,
                "balls_per_six":      (balls / sixes) if sixes else None,
                "balls_per_boundary": (balls / boundaries) if boundaries else None,
                "sixes_per_innings": (sixes / innings) if innings else None,
                "fours_per_innings": (fours / innings) if innings else None,
                "boundaries_per_innings": (boundaries / innings) if innings else None,
                "runs_per_innings": (runs / innings) if innings else None,
                # Tier 1 of spec-apples-to-apples-baselines.md —
                # per-position per-innings milestone rates. Replaces
                # the prior scope-flat parent-table per-season totals
                # so the by-season chip values stay comparable to the
                # position-weighted /summary chip values.
                "thirties_per_innings": (thirties / innings) if innings else None,
                "fifties_per_innings":  (fifties / innings)  if innings else None,
                "hundreds_per_innings": (hundreds / innings) if innings else None,
                "ducks_per_innings":    (ducks / innings)    if innings else None,
            })

        pool = pool_by_season.get(season, {})
        n_players_total = pool.get("n_players") or 0
        n_innings_total = pool.get("n_innings_total") or 0

        row: dict = {
            "season": season,
            "mix": [round(m, 4) for m in mix],
            "n_players": n_players_total,
            "n_innings": n_innings_total,
        }

        if cliff_buckets:
            row.update({
                "below_support": True,
                "cliff_buckets": cliff_buckets,
                "total_runs":            None,
                "run_rate":              None,
                "strike_rate":           None,
                "boundary_pct":          None,
                "dot_pct":               None,
                "balls_per_four":        None,
                "balls_per_boundary":    None,
                "sixes_per_innings":     None,
                "fours_per_innings":     None,
                "boundaries_per_innings": None,
                "runs_per_innings":      None,
                # Tier 1: milestones are now position-weighted too;
                # under cliff they null out alongside the other rates.
                "hundreds_per_innings":  None,
                "fifties_per_innings":   None,
                "thirties_per_innings":  None,
                "ducks_per_innings":     None,
            })
            by_season.append(row)
            continue

        def cv(field: str) -> Optional[float]:
            return convex_combine(mix, {b: by_bucket[b - 1].get(field) for b in range(1, 11)})

        def _r(v, n):
            return round(v, n) if v is not None else None

        # total_runs and run_rate aren't directly in by_bucket — derive
        # from runs_per_player (totals are extensive, rate is intensive).
        cc_runs_per_player = cv("runs_per_player")
        cc_innings_per_player = cv("innings_per_player")
        # run_rate = runs / balls × 6 (overs sense). Re-derive at the
        # bucket grain (runs / balls) and convex-combine.
        # Approximate: cv(strike_rate)/100*6 ≈ runs/over.
        row.update({
            "below_support": False,
            "cliff_buckets": [],
            "total_runs":         _r(cc_runs_per_player, 2),
            "run_rate":           _r((cv("strike_rate") or 0) * 6 / 100, 2) if cv("strike_rate") is not None else None,
            "strike_rate":        _r(cv("strike_rate"), 1),
            "boundary_pct":       _r(cv("boundary_pct"), 1),
            "dot_pct":            _r(cv("dot_pct"), 1),
            "balls_per_four":     _r(cv("balls_per_four"), 2),
            "balls_per_boundary": _r(cv("balls_per_boundary"), 2),
            "sixes_per_innings":  _r(cv("sixes_per_innings"), 3),
            "fours_per_innings":  _r(cv("fours_per_innings"), 3),
            "boundaries_per_innings": _r(cv("boundaries_per_innings"), 3),
            "runs_per_innings":      _r(cv("runs_per_innings"), 2),
            # Tier 1: position-weighted per-season milestone rates.
            "hundreds_per_innings":  _r(cv("hundreds_per_innings"), 3),
            "fifties_per_innings":   _r(cv("fifties_per_innings"), 3),
            "thirties_per_innings":  _r(cv("thirties_per_innings"), 3),
            "ducks_per_innings":     _r(cv("ducks_per_innings"), 3),
        })
        by_season.append(row)

    return {"by_season": by_season}


@router.get("/players/batting/by-season")
async def scope_players_batting_by_season(
    person_id: str = Query(
        ...,
        description=(
            "Player ID. The endpoint derives per-season position-mix"
            " server-side from playerscopestats_position joined on this"
            " person_id; per-season cohort baseline is then computed"
            " under each season's mix."
        ),
    ),
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    drop: Optional[str] = Query(
        None,
        description=(
            "Comma-separated FilterBar axis names to mask before"
            " clause construction. Same semantics as the existing"
            " /players/batting/summary endpoint."
        ),
    ),
):
    """Per-season position-mix-weighted cohort baseline for batting."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_batting_by_season(
        db, person_id, filters, aux, drop_set,
    )


# ============================================================
# /scope/averages/players/batting/by-phase — Phase 4 of
# spec-player-baseline-parity.md (this spec). Per-phase cohort
# baseline for batting. Position-flat: the new
# playerscopestats_batting_phase table is keyed by phase only (not
# position × phase), so this endpoint surfaces the league-wide
# per-phase aggregate at the filtered scope without further
# position-mix weighting. person_id is accepted for API symmetry
# with the other by-season / by-phase endpoints but not used to
# narrow the cohort (a future spec extension could add a
# (person × scope × position × phase) table for true position-
# weighted phase baselines).
# ============================================================


# Minimum cohort innings per phase to count as supported. Below
# this, the phase row's scope_avg fields are null. Mirrors the
# bowling-middle threshold (30 balls); on the population grain
# even narrow scopes typically have plenty.
PHASE_INNINGS_THRESHOLD = 30


async def _by_phase_precomputed(
    db, person_id: str, filters: FilterParams, drop_set: Optional[set[str]],
):
    """Fast path: per-(phase, position) cohort + player-mix + per-phase
    pool reads off the precomputed phase×position / phase child tables by
    scope_key. Used when none of the six aux/filter axes is set. Returns
    the `(player_rows, cohort_rows, pool_rows)` triple the downstream
    row-builder consumes."""
    where, params = build_scope_clauses(filters, drop=drop_set)

    # Q1: player's per-(phase, position) innings → mix derivation.
    player_sql = f"""
        SELECT pssbpp.phase_bucket, pssbpp.position_bucket,
               pssbpp.innings_in_phase AS innings
        FROM playerscopestatsbattingphaseposition pssbpp
        JOIN playerscopestats pss
          ON pss.scope_key = pssbpp.scope_key
         AND pss.person_id = pssbpp.person_id
        WHERE {where}
          AND pssbpp.person_id = :__pid
    """
    # Q2: cohort aggregates per (phase, position).
    cohort_sql = f"""
        SELECT pssbpp.phase_bucket,
               pssbpp.position_bucket,
               SUM(pssbpp.innings_in_phase)     AS innings,
               SUM(pssbpp.balls_in_phase)       AS balls,
               SUM(pssbpp.runs_in_phase)        AS runs,
               SUM(pssbpp.dots_in_phase)        AS dots,
               SUM(pssbpp.fours_in_phase)       AS fours,
               SUM(pssbpp.sixes_in_phase)       AS sixes,
               SUM(pssbpp.boundaries_in_phase)  AS boundaries,
               SUM(pssbpp.dismissals_in_phase)  AS dismissals,
               COUNT(DISTINCT pssbpp.person_id) AS n_players
        FROM playerscopestatsbattingphaseposition pssbpp
        JOIN playerscopestats pss
          ON pss.scope_key = pssbpp.scope_key
         AND pss.person_id = pssbpp.person_id
        WHERE {where}
        GROUP BY pssbpp.phase_bucket, pssbpp.position_bucket
        ORDER BY pssbpp.phase_bucket, pssbpp.position_bucket
    """
    # Q3: per-phase pool totals (cohort-wide n_innings_in_phase + n_players
    # at the phase grain). Used for surface-level cohort metadata.
    pool_sql = f"""
        SELECT pssbp.phase_bucket,
               SUM(pssbp.innings_in_phase) AS innings,
               COUNT(DISTINCT pssbp.person_id) AS n_players
        FROM playerscopestatsbattingphase pssbp
        JOIN playerscopestats pss
          ON pss.scope_key = pssbp.scope_key
         AND pss.person_id = pssbp.person_id
        WHERE {where}
        GROUP BY pssbp.phase_bucket
    """
    p_params = {**params, "__pid": person_id}
    return await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(cohort_sql, params),
        db.q(pool_sql, params),
    )


async def _by_phase_live(
    db, person_id: str, filters: FilterParams, aux: AuxParams,
):
    """Live path: per-(phase, position) cohort + player-mix + per-phase
    pool aggregated at the DELIVERY grain so the six aux/filter axes
    actually narrow the per-phase baseline.

    The per-innings tables carry no phase dimension, so this mirrors the
    per-ball populate (`populate_playerscopestats_batting_phase_position`)
    live: each striker delivery is classified into a phase by its over,
    its innings-level position bucket is read off `inningsbatterperf`
    (the join is cheap — one row per batter-innings, derived by the same
    `derive_positions` + `position_to_bucket` the populate uses), and
    runs/fours/sixes are counted over ALL deliveries while balls/dots and
    innings-in-phase are legal-ball-only — the shared all-ball convention
    (`batting_convention.batting_delivery_contrib`). The
    `(legal OR runs_batter <> 0)` predicate replicates the populate's
    skip of pure wides / 0-off-bat no-balls so n_players matches exactly.

    Dismissals aren't selected — the by-phase output never reads them
    (no per-phase average), so the wicket join the populate needs for
    its dismissals column is skipped here.

    Column shape matches `_by_phase_precomputed` so the downstream
    row-builder is identical. Spec: spec-player-baseline-aux-fallback.md
    Phase 3c + plan-3c-batting-by-season-by-phase-live.md §4."""
    where_full, params = _batting_live_where(filters, aux)
    # over_number is 0-indexed: 0-5 powerplay, 6-14 middle, 15-19 death
    # (matches scripts/populate_playerscopestats_batting_phase.phase_bucket).
    PHASE = ("CASE WHEN d.over_number <= 5 THEN 1 "
             "WHEN d.over_number <= 14 THEN 2 ELSE 3 END")
    LEGAL = "(d.extras_wides = 0 AND d.extras_noballs = 0)"
    # Skip pure wides / 0-off-bat no-balls — they create no populate cell.
    contributes = f"({LEGAL} OR d.runs_batter <> 0)"
    joins = """
        FROM delivery d
        JOIN inningsbatterperf ib
          ON ib.innings_id = d.innings_id AND ib.batter_id = d.batter_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match   m ON m.id = i.match_id
    """

    # Q1: player's per-(phase, position) innings_in_phase → mix.
    player_sql = f"""
        SELECT {PHASE} AS phase_bucket,
               ib.position_bucket,
               COUNT(DISTINCT CASE WHEN {LEGAL} THEN d.innings_id END) AS innings
        {joins}
        WHERE {where_full}
          AND {contributes}
          AND d.batter_id = :__pid
        GROUP BY phase_bucket, ib.position_bucket
    """
    # Q2: cohort aggregates per (phase, position). innings = per-(person,
    # innings) count where the batter faced ≥1 legal ball in the phase.
    cohort_sql = f"""
        SELECT {PHASE} AS phase_bucket,
               ib.position_bucket,
               COUNT(DISTINCT CASE WHEN {LEGAL}
                     THEN d.innings_id || '-' || d.batter_id END)        AS innings,
               SUM(CASE WHEN {LEGAL} THEN 1 ELSE 0 END)                  AS balls,
               SUM(d.runs_batter)                                        AS runs,
               SUM(CASE WHEN {LEGAL} AND d.runs_batter = 0
                         AND d.runs_total = 0 THEN 1 ELSE 0 END)         AS dots,
               SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END)        AS fours,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END)        AS sixes,
               SUM(CASE WHEN d.runs_batter IN (4, 6) THEN 1 ELSE 0 END)  AS boundaries,
               COUNT(DISTINCT d.batter_id)                               AS n_players
        {joins}
        WHERE {where_full}
          AND {contributes}
        GROUP BY phase_bucket, ib.position_bucket
        ORDER BY phase_bucket, ib.position_bucket
    """
    # Q3: per-phase pool totals — distinct batters + (person, innings)
    # pairs that faced ≥1 legal ball in the phase, matching the
    # phase-only precompute table's grain.
    pool_sql = f"""
        SELECT {PHASE} AS phase_bucket,
               COUNT(DISTINCT CASE WHEN {LEGAL}
                     THEN d.innings_id || '-' || d.batter_id END) AS innings,
               COUNT(DISTINCT d.batter_id)                        AS n_players
        {joins}
        WHERE {where_full}
          AND {contributes}
        GROUP BY phase_bucket
    """
    p_params = {**params, "__pid": person_id}
    return await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(cohort_sql, params),
        db.q(pool_sql, params),
    )


async def compute_players_batting_by_phase(
    db,
    person_id: str,
    filters: FilterParams,
    aux: AuxParams,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """Per-phase batting cohort baseline — POSITION-WEIGHTED (Tier 3
    of spec-apples-to-apples-baselines.md).

    For each phase, derives the player's per-phase position mix from
    the new playerscopestatsbattingphaseposition child table (per-
    phase innings_in_phase per position bucket), then convex-combines
    per-(phase, position) cohort rates by that mix. Drops the prior
    position-FLAT path that compared an opener's powerplay against the
    league-wide powerplay (dominated by tail-enders).

    Dispatches on `is_precomputed_scope` (mirrors 3b's summary path):
    none of the six set → precomputed phase×position read; any set →
    live delivery-grain aggregation so the per-phase cohort narrows.

    Returns `{ by_phase: [{ phase, phase_bucket, n_players,
    n_innings_in_phase, mix, strike_rate, dot_pct, boundary_pct,
    balls_per_four, balls_per_boundary, runs_per_innings_in_phase,
    sixes_per_innings, fours_per_innings, boundaries_per_innings,
    below_support, cliff_buckets }, …] }`.

    Spec: spec-player-baseline-parity.md §4 + Phase 3c of
    spec-player-baseline-aux-fallback.md.
    """
    if is_precomputed_scope(filters, aux):
        player_rows, cohort_rows, pool_rows = await _by_phase_precomputed(
            db, person_id, filters, drop_set,
        )
    else:
        player_rows, cohort_rows, pool_rows = await _by_phase_live(
            db, person_id, filters, aux,
        )

    # Roll cohort into {phase: {position: row}}.
    cohort_by_phase: dict[int, dict[int, dict]] = {}
    for r in cohort_rows:
        cohort_by_phase.setdefault(r["phase_bucket"], {})[r["position_bucket"]] = r

    # Player innings per (phase, position) → per-phase mix vector.
    player_inn_by_phase: dict[int, dict[int, int]] = {}
    for r in player_rows:
        player_inn_by_phase.setdefault(r["phase_bucket"], {})[r["position_bucket"]] = r["innings"]

    pool_by_phase: dict[int, dict] = {r["phase_bucket"]: r for r in pool_rows}

    PHASE_NAMES = {1: "powerplay", 2: "middle", 3: "death"}

    def _r(v, n):
        return round(v, n) if v is not None else None

    by_phase: list[dict] = []
    for phase_b in range(1, 4):
        out: dict = {
            "phase": PHASE_NAMES[phase_b],
            "phase_bucket": phase_b,
        }

        pool = pool_by_phase.get(phase_b, {})
        n_players_total = pool.get("n_players") or 0
        n_innings_total = pool.get("innings") or 0

        # Player mix at this phase: per-position fraction of player's
        # phase-innings. Sums to 1 (or 0 if player never appears in
        # this phase).
        player_buckets = player_inn_by_phase.get(phase_b, {})
        player_total = sum(player_buckets.values())
        mix = [0.0] * 10
        if player_total > 0:
            for pos_b, inn in player_buckets.items():
                if 1 <= pos_b <= 10:
                    mix[pos_b - 1] = inn / player_total

        # No data for player at this phase → return cohort-wide pool
        # rate (the prior position-flat behavior) so the chip still
        # shows a meaningful comparison rather than null. Same
        # approach the by-season cohort takes when the player has
        # zero innings in a season.
        season_cohort_for_phase = cohort_by_phase.get(phase_b, {})
        if player_total == 0:
            # Aggregate phase-wide as fallback (sum across all positions).
            agg_runs = sum((r["runs"] or 0) for r in season_cohort_for_phase.values())
            agg_balls = sum((r["balls"] or 0) for r in season_cohort_for_phase.values())
            agg_dots = sum((r["dots"] or 0) for r in season_cohort_for_phase.values())
            agg_fours = sum((r["fours"] or 0) for r in season_cohort_for_phase.values())
            agg_sixes = sum((r["sixes"] or 0) for r in season_cohort_for_phase.values())
            agg_bdr = sum((r["boundaries"] or 0) for r in season_cohort_for_phase.values())
            agg_inn = sum((r["innings"] or 0) for r in season_cohort_for_phase.values())
            below = agg_inn < PHASE_INNINGS_THRESHOLD
            out.update({
                "mix": mix,
                "n_players": n_players_total,
                "n_innings_in_phase": n_innings_total,
                "below_support": below,
                "cliff_buckets": [],
                "strike_rate":         _r((agg_runs / agg_balls * 100) if agg_balls else None, 1) if not below else None,
                "dot_pct":             _r((agg_dots / agg_balls * 100) if agg_balls else None, 1) if not below else None,
                "boundary_pct":        _r((agg_bdr  / agg_balls * 100) if agg_balls else None, 1) if not below else None,
                "balls_per_four":      _r((agg_balls / agg_fours) if agg_fours else None, 2) if not below else None,
                "balls_per_boundary":  _r((agg_balls / agg_bdr) if agg_bdr else None, 2) if not below else None,
                "runs_per_innings_in_phase": _r((agg_runs / agg_inn) if agg_inn else None, 2) if not below else None,
                "sixes_per_innings":   _r((agg_sixes / agg_inn) if agg_inn else None, 3) if not below else None,
                "fours_per_innings":   _r((agg_fours / agg_inn) if agg_inn else None, 3) if not below else None,
                "boundaries_per_innings": _r((agg_bdr / agg_inn) if agg_inn else None, 3) if not below else None,
            })
            by_phase.append(out)
            continue

        # Build per-(phase, position) rate dict + cliff check.
        per_bucket_rates: dict[str, dict[int, Optional[float]]] = {
            "strike_rate": {}, "dot_pct": {}, "boundary_pct": {},
            "balls_per_four": {}, "balls_per_boundary": {},
            "runs_per_innings_in_phase": {},
            "sixes_per_innings": {},
            "fours_per_innings": {},
            "boundaries_per_innings": {},
        }
        cliff_buckets: list[int] = []
        for pos_b in range(1, 11):
            r = season_cohort_for_phase.get(pos_b)
            if r is None:
                if mix[pos_b - 1] > 0:
                    cliff_buckets.append(pos_b)
                for k in per_bucket_rates:
                    per_bucket_rates[k][pos_b] = None
                continue
            innings = r["innings"] or 0
            balls = r["balls"] or 0
            runs = r["runs"] or 0
            dots = r["dots"] or 0
            fours = r["fours"] or 0
            sixes = r["sixes"] or 0
            boundaries = r["boundaries"] or 0
            # Per-bucket support threshold = PHASE_INNINGS_THRESHOLD
            # (30 innings at this phase × position). Mirrors the prior
            # phase-only cliff but applies at the finer grain.
            if mix[pos_b - 1] > 0 and innings < PHASE_INNINGS_THRESHOLD:
                cliff_buckets.append(pos_b)
            per_bucket_rates["strike_rate"][pos_b] = (runs / balls * 100) if balls else None
            per_bucket_rates["dot_pct"][pos_b] = (dots / balls * 100) if balls else None
            per_bucket_rates["boundary_pct"][pos_b] = (boundaries / balls * 100) if balls else None
            per_bucket_rates["balls_per_four"][pos_b] = (balls / fours) if fours else None
            per_bucket_rates["balls_per_boundary"][pos_b] = (balls / boundaries) if boundaries else None
            per_bucket_rates["runs_per_innings_in_phase"][pos_b] = (runs / innings) if innings else None
            per_bucket_rates["sixes_per_innings"][pos_b] = (sixes / innings) if innings else None
            per_bucket_rates["fours_per_innings"][pos_b] = (fours / innings) if innings else None
            per_bucket_rates["boundaries_per_innings"][pos_b] = (boundaries / innings) if innings else None

        if cliff_buckets:
            out.update({
                "mix": [round(m, 4) for m in mix],
                "n_players": n_players_total,
                "n_innings_in_phase": n_innings_total,
                "below_support": True,
                "cliff_buckets": cliff_buckets,
                "strike_rate": None, "dot_pct": None,
                "boundary_pct": None, "balls_per_four": None,
                "balls_per_boundary": None,
                "runs_per_innings_in_phase": None,
                "sixes_per_innings": None, "fours_per_innings": None,
                "boundaries_per_innings": None,
            })
            by_phase.append(out)
            continue

        out.update({
            "mix": [round(m, 4) for m in mix],
            "n_players": n_players_total,
            "n_innings_in_phase": n_innings_total,
            "below_support": False,
            "cliff_buckets": [],
            "strike_rate":         _r(convex_combine(mix, per_bucket_rates["strike_rate"]), 1),
            "dot_pct":             _r(convex_combine(mix, per_bucket_rates["dot_pct"]), 1),
            "boundary_pct":        _r(convex_combine(mix, per_bucket_rates["boundary_pct"]), 1),
            "balls_per_four":      _r(convex_combine(mix, per_bucket_rates["balls_per_four"]), 2),
            "balls_per_boundary":  _r(convex_combine(mix, per_bucket_rates["balls_per_boundary"]), 2),
            "runs_per_innings_in_phase": _r(convex_combine(mix, per_bucket_rates["runs_per_innings_in_phase"]), 2),
            "sixes_per_innings":   _r(convex_combine(mix, per_bucket_rates["sixes_per_innings"]), 3),
            "fours_per_innings":   _r(convex_combine(mix, per_bucket_rates["fours_per_innings"]), 3),
            "boundaries_per_innings": _r(convex_combine(mix, per_bucket_rates["boundaries_per_innings"]), 3),
        })
        by_phase.append(out)

    return {"by_phase": by_phase, "person_id": person_id}


@router.get("/players/batting/by-phase")
async def scope_players_batting_by_phase(
    person_id: str = Query(
        ...,
        description=(
            "Player ID. Accepted for API symmetry with by-season; the"
            " per-phase cohort is position-flat (no per-phase position"
            " sub-mix data available), so person_id doesn't narrow the"
            " response — it only labels the request."
        ),
    ),
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    drop: Optional[str] = Query(None),
):
    """Per-phase position-flat cohort baseline for batting."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_batting_by_phase(
        db, person_id, filters, aux, drop_set,
    )


# ============================================================
# /scope/averages/players/batting/by-over — Tier 4 of
# spec-apples-to-apples-baselines.md. Per-over batting cohort
# baseline. Mirrors the existing bowling /by-over path: derives
# the player's per-over ball mix server-side from
# playerscopestatsbattingover (joined on person_id), then computes
# per-bucket cohort rates (strike_rate, dot_pct, boundary_pct,
# balls_per_four, balls_per_boundary, runs_per_innings) at the
# filtered scope. Closes spec §2.2 A7 + backs the SR-by-Over
# chart overlay via Tier 5's BarChart referenceData prop.
# ============================================================


# Minimum cohort legal balls per over bucket to count as supported.
# Mirrors the bowling-side U-shape thresholds in shape (loose at the
# extremes where samples are thin; tight in the middle).
def batting_over_threshold(over: int) -> int:
    if over <= 2 or over >= 19:
        return 80
    if over <= 6 or over >= 16:
        return 60
    return 40


async def compute_players_batting_by_over(
    db,
    person_id: str,
    filters: FilterParams,
    aux: AuxParams,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """Per-over batting cohort baseline keyed off the player's per-
    over BALL mix (legal_balls_faced fraction).

    Returns `{ by_over: [{ over, n_players, n_innings, strike_rate,
    dot_pct, boundary_pct, balls_per_four, balls_per_boundary,
    runs_per_innings, below_support }, …] }` over overs 1..20. Spec:
    spec-apples-to-apples-baselines.md §3 Tier 4.
    """
    where, params = build_scope_clauses(filters, drop=drop_set)

    # Q1: player's per-over legal_balls_faced (mix derivation).
    player_sql = f"""
        SELECT psbo.over_number,
               psbo.legal_balls_faced AS legal_balls
        FROM playerscopestatsbattingover psbo
        JOIN playerscopestats pss
          ON pss.scope_key = psbo.scope_key
         AND pss.person_id = psbo.person_id
        WHERE {where}
          AND psbo.person_id = :__pid
        ORDER BY psbo.over_number
    """
    # Q2: cohort aggregates per over_number.
    cohort_sql = f"""
        SELECT psbo.over_number,
               SUM(psbo.runs)              AS runs,
               SUM(psbo.legal_balls_faced) AS legal_balls,
               SUM(psbo.dots)              AS dots,
               SUM(psbo.fours)             AS fours,
               SUM(psbo.sixes)             AS sixes,
               SUM(psbo.dismissals)        AS dismissals,
               SUM(psbo.innings_faced)     AS innings_faced,
               COUNT(DISTINCT psbo.person_id) AS n_players
        FROM playerscopestatsbattingover psbo
        WHERE psbo.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
        GROUP BY psbo.over_number
        ORDER BY psbo.over_number
    """
    pool_sql = f"""
        SELECT COUNT(DISTINCT psbo.person_id) AS n_players,
               SUM(psbo.legal_balls_faced)    AS n_balls_total
        FROM playerscopestatsbattingover psbo
        WHERE psbo.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
    """
    p_params = {**params, "__pid": person_id}
    player_rows, cohort_rows, pool_rows = await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(cohort_sql, params),
        db.q(pool_sql, params),
    )

    by_over_cohort = {r["over_number"]: r for r in cohort_rows}
    n_players_total = (pool_rows[0].get("n_players") if pool_rows else 0) or 0
    n_balls_total = (pool_rows[0].get("n_balls_total") if pool_rows else 0) or 0

    # Player's mix vector from per-over legal balls faced.
    player_balls: dict[int, int] = {r["over_number"]: r["legal_balls"] for r in player_rows}
    total_player_balls = sum(player_balls.values())
    mix = [0.0] * 20
    if total_player_balls > 0:
        for o, b in player_balls.items():
            if 1 <= o <= 20:
                mix[o - 1] = b / total_player_balls

    by_over: list[dict] = []
    for o in range(1, 21):
        r = by_over_cohort.get(o)
        threshold = batting_over_threshold(o)
        if r is None:
            by_over.append({
                "over": o,
                "n_balls": 0, "n_players": 0,
                "n_innings": 0,
                "threshold": threshold,
                "below_support": True,
                "strike_rate": None, "dot_pct": None, "boundary_pct": None,
                "balls_per_four": None, "balls_per_boundary": None,
                "runs_per_innings": None,
            })
            continue
        balls = r["legal_balls"] or 0
        runs = r["runs"] or 0
        dots = r["dots"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        dismissals = r["dismissals"] or 0
        innings_faced = r["innings_faced"] or 0
        boundaries = fours + sixes
        below = balls < threshold
        by_over.append({
            "over": o,
            "n_balls": balls,
            "n_players": r["n_players"] or 0,
            "n_innings": innings_faced,
            "threshold": threshold,
            "below_support": below,
            "strike_rate":       round(runs / balls * 100, 1)       if balls else None,
            "dot_pct":           round(dots / balls * 100, 1)       if balls else None,
            "boundary_pct":      round(boundaries / balls * 100, 1) if balls else None,
            "balls_per_four":    round(balls / fours, 2)            if fours else None,
            "balls_per_boundary": round(balls / boundaries, 2)      if boundaries else None,
            # Per-bucket per-innings rates (Tier 4). Sibling unit to the
            # bowling-side per-bucket per-innings rates added in Tier 2.
            "runs_per_innings":  round(runs / innings_faced, 2)     if innings_faced else None,
            # Volume hints — useful for downstream chart axis labels.
            "dismissals": dismissals,
        })

    return {
        "by_over": by_over,
        "cohort": {
            "match_dimension": "ball_mix",
            "ball_mix": mix,
            "n_players": n_players_total,
            "n_balls_total": n_balls_total,
        },
    }


@router.get("/players/batting/by-over")
async def scope_players_batting_by_over(
    person_id: str = Query(
        ...,
        description=(
            "Player ID. The endpoint derives the per-over ball mix"
            " server-side from playerscopestatsbattingover joined on"
            " this person_id; per-bucket cohort rates are computed"
            " over the whole population at the filtered scope. Mirror"
            " of the bowling-side /by-over (which uses bowling balls,"
            " not faced balls)."
        ),
    ),
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    drop: Optional[str] = Query(None),
):
    """Per-over batting cohort baseline (Tier 4)."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_batting_by_over(
        db, person_id, filters, aux, drop_set,
    )


def _bowling_live_where(filters: FilterParams, aux: AuxParams) -> tuple[str, dict]:
    """Build the per-delivery WHERE for the live bowling cohort paths
    (Phase 3d). Assumes the query joins `innings i` and `match m`.

    Bowling/fielding orientation (the bowler's team is the side NOT
    batting in innings i), so it differs from `_batting_live_where`:

      - innings  → `_option_b_team_inning(None, "bowling", aux)` flips to
        `i.innings_number = (1 - aux.inning)`.
      - toss/result → `_cohort_outcome_clause("bowling", aux)` keys the
        outcome on the OTHER match team (the bowling side), not i.team.
      - filter_team=X (bowler's team) → `i.team != X AND X in match`.
      - filter_opponent=X (bowled against X = X batting) → `i.team = X`.
        build()'s native team/opponent clauses are batting orientation,
        so they're dropped from build and re-added flipped here — the
        cohort narrows on the same axis as the bowler's OWN value
        (chip↔baseline symmetry). Spec: spec-player-baseline-aux-fallback.md
        Phase 3d + plan-3d-bowling-live-cohort.md §2."""
    where, params = filters.build(
        has_innings_join=True, apply_inning=False, aux=aux,
        drop={"filter_team", "filter_opponent"},
    )
    parts = ["i.super_over = 0"]
    if where:
        parts.append(where)
    if filters.team:
        parts.append(
            "(i.team != :bowl_team AND (m.team1 = :bowl_team OR m.team2 = :bowl_team))"
        )
        params["bowl_team"] = filters.team
    if filters.opponent:
        parts.append("i.team = :bowl_opp")
        params["bowl_opp"] = filters.opponent
    inn_clause, inn_params = _option_b_team_inning(None, "bowling", aux)
    if inn_clause:
        parts.append(inn_clause)
        params.update(inn_params)
    coh_clause, coh_params = _cohort_outcome_clause("bowling", aux)
    if coh_clause:
        parts.append(coh_clause)
        params.update(coh_params)
    return " AND ".join(parts), params


# Bowler valid-wicket exclusions — MUST match
# scripts/populate_playerscopestats_over.py BOWLER_WICKET_EXCLUDED (4
# kinds; NOT the team-side live path's 5-kind set which also drops
# 'retired not out'). Parity with the precomputed over table depends on
# this exact set.
_BOWLING_WICKET_EXCLUDED_SQL = (
    "('run out', 'retired hurt', 'retired out', 'obstructing the field')"
)


async def _bowling_over_cohort_live(
    db, filters: FilterParams, aux: AuxParams,
):
    """Live per-over bowling cohort aggregation under the six filters
    (Phase 3d, by-phase column subset).

    Reproduces, for the filtered pool, the simple-sum + maiden columns of
    `playerscopestatsover` at the over-bucket grain (1..20). Conventions
    match `scripts/populate_playerscopestats_over.py` exactly:
      runs_conceded = SUM(runs_total) over ALL deliveries;
      legal = wides=0 AND noballs=0; dot = runs_batter=0 AND runs_total=0;
      boundary = runs_batter IN (4,6); valid wicket = kind NOT IN the
      4-kind excluded set; maiden = a (innings, over, bowler) with 6
      legal balls and 0 runs_total; over bucket = over_number + 1.

    Returns cohort_rows[] keyed like the precomputed cohort read so the
    downstream by_over builder is identical. (by-season / summary add the
    per-spell columns in 3d-2 / 3d-3.)"""
    where_full, params = _bowling_live_where(filters, aux)
    joins = """
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match   m ON m.id = i.match_id
    """
    base = f"{joins} WHERE {where_full} AND d.bowler_id IS NOT NULL AND d.over_number BETWEEN 0 AND 19"
    deliv_sql = f"""
        SELECT (d.over_number + 1) AS over_number,
               SUM(d.runs_total)                                              AS runs_conceded,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls,
               SUM(CASE WHEN d.runs_batter = 0 AND d.runs_total = 0 THEN 1 ELSE 0 END)      AS dots,
               SUM(CASE WHEN d.runs_batter IN (4, 6) THEN 1 ELSE 0 END)       AS boundaries,
               COUNT(DISTINCT d.bowler_id)                                    AS n_players
        {base}
        GROUP BY d.over_number
        ORDER BY d.over_number
    """
    wkt_sql = f"""
        SELECT (d.over_number + 1) AS over_number, COUNT(*) AS wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match   m ON m.id = i.match_id
        WHERE {where_full}
          AND d.bowler_id IS NOT NULL AND d.over_number BETWEEN 0 AND 19
          AND w.kind NOT IN {_BOWLING_WICKET_EXCLUDED_SQL}
        GROUP BY d.over_number
    """
    maiden_sql = f"""
        SELECT (over_number + 1) AS over_number, COUNT(*) AS maidens
        FROM (
            SELECT d.innings_id, d.over_number, d.bowler_id
            {base}
            GROUP BY d.innings_id, d.over_number, d.bowler_id
            HAVING SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) = 6
               AND SUM(d.runs_total) = 0
        )
        GROUP BY over_number
    """
    deliv_rows, wkt_rows, maiden_rows = await asyncio.gather(
        db.q(deliv_sql, params),
        db.q(wkt_sql, params),
        db.q(maiden_sql, params),
    )
    by_over: dict[int, dict] = {}
    for r in deliv_rows:
        by_over[r["over_number"]] = {
            "over_number": r["over_number"],
            "runs_conceded": r["runs_conceded"] or 0,
            "legal_balls": r["legal_balls"] or 0,
            "dots": r["dots"] or 0,
            "boundaries": r["boundaries"] or 0,
            "n_players": r["n_players"] or 0,
            "wickets": 0,
            "maidens": 0,
        }
    for r in wkt_rows:
        if r["over_number"] in by_over:
            by_over[r["over_number"]]["wickets"] = r["wickets"] or 0
    for r in maiden_rows:
        if r["over_number"] in by_over:
            by_over[r["over_number"]]["maidens"] = r["maidens"] or 0
    return [by_over[o] for o in sorted(by_over)]


async def _bowling_player_over_mix_live(
    db, person_id: str, filters: FilterParams, aux: AuxParams,
):
    """The bowler's own per-over legal-ball counts at the narrowed scope —
    the over-mix weights for the live by-phase / by-season convex-combine.
    Same WHERE as the cohort so the mix matches the narrowed pool."""
    where_full, params = _bowling_live_where(filters, aux)
    sql = f"""
        SELECT (d.over_number + 1) AS over_number,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match   m ON m.id = i.match_id
        WHERE {where_full}
          AND d.bowler_id = :__pid AND d.over_number BETWEEN 0 AND 19
        GROUP BY d.over_number
        ORDER BY d.over_number
    """
    return await db.q(sql, {**params, "__pid": person_id})


async def compute_players_bowling_cohort(
    db,
    filters: FilterParams,
    aux: AuxParams,
    mix: list[float],
    drop_set: Optional[set[str]] = None,
) -> dict:
    """In-process bowling cohort baseline — same shape as the HTTP
    endpoint. Phase 4 player /summary endpoints call this to fold the
    cohort baseline into their envelope-wrapped response without a
    second HTTP roundtrip.
    """
    where, params = build_scope_clauses(filters, drop=drop_set)

    main_sql = f"""
        SELECT psso.over_number,
               SUM(psso.runs_conceded)       AS runs_conceded,
               SUM(psso.legal_balls)         AS legal_balls,
               SUM(psso.wickets)             AS wickets,
               SUM(psso.dots)                AS dots,
               SUM(psso.boundaries)          AS boundaries,
               SUM(psso.maidens)             AS maidens,
               SUM(psso.innings_bowled)      AS innings_bowled,
               SUM(psso.four_wicket_hauls)   AS four_wicket_hauls,
               SUM(psso.three_wicket_hauls)  AS three_wicket_hauls,
               SUM(psso.five_wicket_hauls)   AS five_wicket_hauls,
               SUM(psso.innings_with_wicket) AS innings_with_wicket,
               SUM(psso.innings_with_two)    AS innings_with_two,
               SUM(psso.innings_qualifying)  AS innings_qualifying,
               SUM(psso.innings_econ_leq_6)  AS innings_econ_leq_6,
               SUM(psso.innings_econ_leq_7)  AS innings_econ_leq_7,
               SUM(psso.innings_econ_geq_9)  AS innings_econ_geq_9,
               SUM(psso.innings_econ_geq_10) AS innings_econ_geq_10,
               SUM(psso.innings_runs_leq_15) AS innings_runs_leq_15,
               SUM(psso.innings_runs_leq_25) AS innings_runs_leq_25,
               SUM(psso.innings_runs_geq_40) AS innings_runs_geq_40,
               SUM(psso.innings_runs_geq_50) AS innings_runs_geq_50,
               COUNT(DISTINCT psso.person_id) AS n_players
        FROM playerscopestatsover psso
        WHERE psso.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
        GROUP BY psso.over_number
        ORDER BY psso.over_number
    """
    pool_sql = f"""
        SELECT COUNT(DISTINCT psso.person_id) AS n_players,
               SUM(psso.legal_balls)           AS n_balls_total
        FROM playerscopestatsover psso
        WHERE psso.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
    """
    # Tier 2 of spec-apples-to-apples-baselines.md — cohort_unique_innings
    # is the per-innings denominator for the per-innings rates'
    # dimensional alignment with the player-side value (which is
    # wickets / distinct innings_bowled). The per-bucket cv() yields
    # per-attendance-tuple rates; multiplying by cohort_avg_attendances_
    # per_innings ≈ SUM(innings_bowled)/SUM(per-bucket-attendance) scales
    # back to per-innings. The parent table now carries `bowling_innings`
    # (populated by Tier 2.SP) so the SUM is one query.
    bowling_inn_sql = f"""
        SELECT SUM(pss.bowling_innings) AS bowling_innings_total
        FROM playerscopestats pss
        WHERE {where}
    """
    rows, pool, bi = await asyncio.gather(
        db.q(main_sql, params),
        db.q(pool_sql, params),
        db.q(bowling_inn_sql, params),
    )
    by_over = {r["over_number"]: r for r in rows}
    n_players_total = (pool[0].get("n_players") if pool else 0) or 0
    n_balls_total = (pool[0].get("n_balls_total") if pool else 0) or 0
    cohort_unique_innings = (bi[0].get("bowling_innings_total") if bi else 0) or 0
    cohort_total_attendances = sum((r["innings_bowled"] or 0) for r in rows)
    per_innings_scale = (
        cohort_total_attendances / cohort_unique_innings
        if cohort_unique_innings else 0
    )

    by_over_arr: list[dict] = []
    for o in range(1, 21):
        r = by_over.get(o)
        threshold = bowling_threshold(o)
        if r is None:
            by_over_arr.append({
                "over": o, "label": bowling_bucket_label(o),
                "n_balls": 0, "n_players": 0, "threshold": threshold,
                "below_support": True,
                "economy": None, "average": None, "strike_rate": None,
                "dot_pct": None, "wickets_per_over": None,
                "boundary_pct": None, "balls_per_boundary": None,
                # Tier 2 of spec-apples-to-apples-baselines.md —
                # per-bucket per-innings rates so the cohort can
                # convex-combine over the bowler's over mix.
                "wickets_per_innings": None,
                "maidens_per_innings": None,
                "four_wicket_hauls_per_innings": None,
                # PT2 of spec-prob-baselines.md — per-bucket prob
                # rates. Simples (P(0), P(≥1), P(≥2)) use the per-
                # spell-touching numerators (innings_with_*); ≥3/4/5
                # use over-attribution numerators (three/four/five_
                # wicket_hauls) so the cv must be scaled back to per-
                # innings via per_innings_scale at the return site.
                # Conditionals use bucket-grain ratio per spec §4.3.
                "prob_zero":         None,
                "prob_geq_1":        None,
                "prob_geq_2":        None,
                "prob_geq_3_attr":   None,
                "prob_geq_4_attr":   None,
                "prob_geq_5_attr":   None,
                "prob_3_given_2":    None,
                "prob_4_given_2":    None,
                "prob_5_given_2":    None,
                # PT3 of spec-prob-baselines.md — econ + runs-conceded
                # threshold probs. Per-bucket rate uses innings_qualifying
                # as denominator so cohort matches the chip's master-
                # sample min_balls=12 gate (apples-to-apples).
                "prob_econ_leq_6":   None,
                "prob_econ_leq_7":   None,
                "prob_econ_geq_9":   None,
                "prob_econ_geq_10":  None,
                "prob_runs_leq_15":  None,
                "prob_runs_leq_25":  None,
                "prob_runs_geq_40":  None,
                "prob_runs_geq_50":  None,
            })
            continue
        balls = r["legal_balls"] or 0
        runs = r["runs_conceded"] or 0
        wickets = r["wickets"] or 0
        dots = r["dots"] or 0
        boundaries = r["boundaries"] or 0
        maidens = r["maidens"] or 0
        innings_bowled = r["innings_bowled"] or 0
        four_wicket_hauls = r["four_wicket_hauls"] or 0
        three_wicket_hauls = r["three_wicket_hauls"] or 0
        five_wicket_hauls = r["five_wicket_hauls"] or 0
        innings_with_wicket = r["innings_with_wicket"] or 0
        innings_with_two = r["innings_with_two"] or 0
        innings_qualifying = r["innings_qualifying"] or 0
        innings_econ_leq_6  = r["innings_econ_leq_6"]  or 0
        innings_econ_leq_7  = r["innings_econ_leq_7"]  or 0
        innings_econ_geq_9  = r["innings_econ_geq_9"]  or 0
        innings_econ_geq_10 = r["innings_econ_geq_10"] or 0
        innings_runs_leq_15 = r["innings_runs_leq_15"] or 0
        innings_runs_leq_25 = r["innings_runs_leq_25"] or 0
        innings_runs_geq_40 = r["innings_runs_geq_40"] or 0
        innings_runs_geq_50 = r["innings_runs_geq_50"] or 0
        by_over_arr.append({
            "over": o, "label": bowling_bucket_label(o),
            "n_balls": balls, "n_players": r["n_players"] or 0,
            "threshold": threshold,
            "below_support": balls < threshold,
            "economy":          round(runs * 6 / balls, 2)            if balls else None,
            "average":          round(runs / wickets, 2)              if wickets else None,
            "strike_rate":      round(balls / wickets, 2)             if wickets else None,
            "dot_pct":          round(dots / balls * 100, 1)          if balls else None,
            "wickets_per_over": round(wickets * 6 / balls, 3)         if balls else None,
            "boundary_pct":     round(boundaries / balls * 100, 1)    if balls else None,
            # Inverse boundary-frequency. Higher = better for the
            # bowler (more balls between boundaries conceded).
            # The over child table doesn't break out 4s vs 6s, so
            # only the combined balls_per_boundary is available.
            "balls_per_boundary": round(balls / boundaries, 2)        if boundaries else None,
            # Tier 2: per-bucket per-innings rates. innings_bowled is
            # the distinct-innings denominator for this over bucket.
            "wickets_per_innings":          (wickets / innings_bowled)          if innings_bowled else None,
            "maidens_per_innings":          (maidens / innings_bowled)          if innings_bowled else None,
            "four_wicket_hauls_per_innings": (four_wicket_hauls / innings_bowled) if innings_bowled else None,
            # PT2 of spec-prob-baselines.md — per-bucket prob rates for
            # the wicket-ladder chips on /bowlers/.../distribution.
            #
            # P(0), P(≥1), P(≥2) use per-spell-touching numerators —
            # innings_bowled is the same per-spell-touching count, so
            # the ratio is directly a probability without scaling.
            #
            # P(≥3), P(≥4), P(≥5) use over-attribution numerators
            # (haul_at_bucket). The cv result is per-attendance and
            # needs per_innings_scale at the return site to read as
            # per-innings P(≥k). The cohort baseline is exact for
            # events that happen at most once per innings (≥3/4/5
            # wickets), matching the four_wicket_hauls_per_innings
            # Tier 2 pattern.
            #
            # Conditionals (P(≥k│≥2)) divide attribution at the bucket
            # by innings_with_two at the bucket and convex-combine the
            # ratio — bucket-grain, per spec §4.3 (NOT ratio-of-cv).
            "prob_zero":       ((innings_bowled - innings_with_wicket) / innings_bowled) if innings_bowled else None,
            "prob_geq_1":      (innings_with_wicket / innings_bowled)                     if innings_bowled else None,
            "prob_geq_2":      (innings_with_two / innings_bowled)                        if innings_bowled else None,
            "prob_geq_3_attr": (three_wicket_hauls / innings_bowled)                      if innings_bowled else None,
            "prob_geq_4_attr": (four_wicket_hauls / innings_bowled)                       if innings_bowled else None,
            "prob_geq_5_attr": (five_wicket_hauls / innings_bowled)                       if innings_bowled else None,
            "prob_3_given_2":  (three_wicket_hauls / innings_with_two)                    if innings_with_two else None,
            "prob_4_given_2":  (four_wicket_hauls / innings_with_two)                     if innings_with_two else None,
            "prob_5_given_2":  (five_wicket_hauls / innings_with_two)                     if innings_with_two else None,
            # PT3 of spec-prob-baselines.md — econ + runs-conceded probs.
            # Denominator is innings_qualifying (≥12-ball spells), the
            # SAME population the chip's master sample shows; per-bucket
            # rate is a direct spell-level probability (no scaling).
            "prob_econ_leq_6":   (innings_econ_leq_6  / innings_qualifying) if innings_qualifying else None,
            "prob_econ_leq_7":   (innings_econ_leq_7  / innings_qualifying) if innings_qualifying else None,
            "prob_econ_geq_9":   (innings_econ_geq_9  / innings_qualifying) if innings_qualifying else None,
            "prob_econ_geq_10":  (innings_econ_geq_10 / innings_qualifying) if innings_qualifying else None,
            "prob_runs_leq_15":  (innings_runs_leq_15 / innings_qualifying) if innings_qualifying else None,
            "prob_runs_leq_25":  (innings_runs_leq_25 / innings_qualifying) if innings_qualifying else None,
            "prob_runs_geq_40":  (innings_runs_geq_40 / innings_qualifying) if innings_qualifying else None,
            "prob_runs_geq_50":  (innings_runs_geq_50 / innings_qualifying) if innings_qualifying else None,
        })

    cliff_buckets: list[int] = [
        o for o in range(1, 21)
        if mix[o - 1] > 0 and by_over_arr[o - 1]["below_support"]
    ]

    cohort_block = {
        "match_dimension": "over_mix",
        "over_mix": mix,
        "n_players": n_players_total,
        "n_balls_total": n_balls_total,
    }

    if cliff_buckets:
        return {
            "cohort": cohort_block,
            "below_support": True,
            "cliff_buckets": cliff_buckets,
            "economy":          wrap_metric(None, None, "bowl_economy",      sample_size=n_balls_total),
            "average":          wrap_metric(None, None, "bowl_average",      sample_size=n_balls_total),
            "strike_rate":      wrap_metric(None, None, "bowl_strike_rate",  sample_size=n_balls_total),
            "dot_pct":          wrap_metric(None, None, "bowl_dot_pct",      sample_size=n_balls_total),
            "wickets_per_over": wrap_metric(None, None, "bowl_wickets_per_over", sample_size=n_balls_total),
            "boundary_pct":     wrap_metric(None, None, "bowl_boundary_pct", sample_size=n_balls_total),
            "balls_per_boundary": wrap_metric(None, None, "bowl_balls_per_boundary", sample_size=n_balls_total),
            # Tier 2: per-innings rates are now over-weighted via
            # convex combination on per-bucket innings_bowled-
            # denominated rates. Under cliff they null out alongside
            # the other rates.
            "wickets_per_innings":          wrap_metric(None, None, "bowl_wickets_per_innings", sample_size=n_balls_total),
            "maidens_per_innings":          wrap_metric(None, None, "bowl_maidens_per_innings", sample_size=n_balls_total),
            "four_wicket_hauls_per_innings": wrap_metric(None, None, "bowl_four_wicket_hauls_per_innings", sample_size=n_balls_total),
            # PT2 of spec-prob-baselines.md — wicket-ladder ProbChip
            # cohort baselines null out under cliff alongside the rates.
            "prob_zero":      wrap_metric(None, None, "bowl_prob_zero",      sample_size=n_balls_total),
            "prob_geq_1":     wrap_metric(None, None, "bowl_prob_geq_1",     sample_size=n_balls_total),
            "prob_geq_2":     wrap_metric(None, None, "bowl_prob_geq_2",     sample_size=n_balls_total),
            "prob_geq_3":     wrap_metric(None, None, "bowl_prob_geq_3",     sample_size=n_balls_total),
            "prob_geq_4":     wrap_metric(None, None, "bowl_prob_geq_4",     sample_size=n_balls_total),
            "prob_geq_5":     wrap_metric(None, None, "bowl_prob_geq_5",     sample_size=n_balls_total),
            "prob_3_given_2": wrap_metric(None, None, "bowl_prob_3_given_2", sample_size=n_balls_total),
            "prob_4_given_2": wrap_metric(None, None, "bowl_prob_4_given_2", sample_size=n_balls_total),
            "prob_5_given_2": wrap_metric(None, None, "bowl_prob_5_given_2", sample_size=n_balls_total),
            # PT3 of spec-prob-baselines.md — econ + runs-conceded
            # threshold cohort probs null under cliff alongside the rates.
            "prob_econ_leq_6":  wrap_metric(None, None, "bowl_prob_econ_leq_6",  sample_size=n_balls_total),
            "prob_econ_leq_7":  wrap_metric(None, None, "bowl_prob_econ_leq_7",  sample_size=n_balls_total),
            "prob_econ_geq_9":  wrap_metric(None, None, "bowl_prob_econ_geq_9",  sample_size=n_balls_total),
            "prob_econ_geq_10": wrap_metric(None, None, "bowl_prob_econ_geq_10", sample_size=n_balls_total),
            "prob_runs_leq_15": wrap_metric(None, None, "bowl_prob_runs_leq_15", sample_size=n_balls_total),
            "prob_runs_leq_25": wrap_metric(None, None, "bowl_prob_runs_leq_25", sample_size=n_balls_total),
            "prob_runs_geq_40": wrap_metric(None, None, "bowl_prob_runs_geq_40", sample_size=n_balls_total),
            "prob_runs_geq_50": wrap_metric(None, None, "bowl_prob_runs_geq_50", sample_size=n_balls_total),
            "by_over": by_over_arr,
        }

    def cv(field: str) -> Optional[float]:
        return convex_combine(mix, {o: by_over_arr[o - 1][field] for o in range(1, 21)})

    cc_econ = cv("economy")
    cc_avg  = cv("average")
    cc_sr   = cv("strike_rate")
    cc_dp   = cv("dot_pct")
    cc_wpo  = cv("wickets_per_over")
    cc_bp   = cv("boundary_pct")
    cc_bpb  = cv("balls_per_boundary")
    # Tier 2 of spec-apples-to-apples-baselines.md — over-weighted
    # per-innings rates. Replaces the prior `wickets_per_over × 4`
    # heuristic + scope-flat parent aggregate; per-bucket rate uses the
    # per-bucket innings_bowled (attendance) denominator. Multiplying
    # cv result by `per_innings_scale` (cohort avg attendances/innings)
    # converts the mix-weighted per-attendance rate to a per-unique-
    # innings rate, dimensionally matching player.wickets_per_innings
    # (wickets / distinct innings bowled) on the chip side.
    def cv_pi(field: str) -> Optional[float]:
        v = cv(field)
        if v is None or per_innings_scale == 0:
            return v
        return v * per_innings_scale
    cc_wpi  = cv_pi("wickets_per_innings")
    cc_mpi  = cv_pi("maidens_per_innings")
    cc_fwh_pi = cv_pi("four_wicket_hauls_per_innings")
    # PT2 of spec-prob-baselines.md — wicket-ladder cohort probs.
    # Simples P(0), P(≥1), P(≥2) cv on per-spell-touching rates: no
    # scaling needed (denominator matches numerator semantics).
    # P(≥3), P(≥4), P(≥5) cv on attribution rates and then per_innings_
    # scale to convert per-attendance to per-innings, matching the chip
    # value semantics on the bowler side. Conditionals cv per-bucket
    # ratios directly (spec §4.3).
    cc_prob_zero    = cv("prob_zero")
    cc_prob_geq_1   = cv("prob_geq_1")
    cc_prob_geq_2   = cv("prob_geq_2")
    cc_prob_geq_3   = cv_pi("prob_geq_3_attr")
    cc_prob_geq_4   = cv_pi("prob_geq_4_attr")
    cc_prob_geq_5   = cv_pi("prob_geq_5_attr")
    cc_prob_3_g_2   = cv("prob_3_given_2")
    cc_prob_4_g_2   = cv("prob_4_given_2")
    cc_prob_5_g_2   = cv("prob_5_given_2")
    # PT3 of spec-prob-baselines.md — econ + runs-conceded threshold
    # probs. Direct cv on the per-bucket prob rates (denominator is
    # innings_qualifying, gated by the chip's min_balls=12 qualifier).
    cc_prob_econ_leq_6   = cv("prob_econ_leq_6")
    cc_prob_econ_leq_7   = cv("prob_econ_leq_7")
    cc_prob_econ_geq_9   = cv("prob_econ_geq_9")
    cc_prob_econ_geq_10  = cv("prob_econ_geq_10")
    cc_prob_runs_leq_15  = cv("prob_runs_leq_15")
    cc_prob_runs_leq_25  = cv("prob_runs_leq_25")
    cc_prob_runs_geq_40  = cv("prob_runs_geq_40")
    cc_prob_runs_geq_50  = cv("prob_runs_geq_50")

    def _r(v: Optional[float], ndigits: int) -> Optional[float]:
        return round(v, ndigits) if v is not None else None

    return {
        "cohort": cohort_block,
        "below_support": False,
        "cliff_buckets": [],
        "economy":          wrap_metric(_r(cc_econ, 2), _r(cc_econ, 2), "bowl_economy",         sample_size=n_balls_total),
        "average":          wrap_metric(_r(cc_avg, 2),  _r(cc_avg, 2),  "bowl_average",         sample_size=n_balls_total),
        "strike_rate":      wrap_metric(_r(cc_sr, 2),   _r(cc_sr, 2),   "bowl_strike_rate",     sample_size=n_balls_total),
        "dot_pct":          wrap_metric(_r(cc_dp, 1),   _r(cc_dp, 1),   "bowl_dot_pct",         sample_size=n_balls_total),
        "wickets_per_over": wrap_metric(_r(cc_wpo, 3),  _r(cc_wpo, 3),  "bowl_wickets_per_over", sample_size=n_balls_total),
        "boundary_pct":     wrap_metric(_r(cc_bp, 1),   _r(cc_bp, 1),   "bowl_boundary_pct",    sample_size=n_balls_total),
        "balls_per_boundary": wrap_metric(_r(cc_bpb, 2), _r(cc_bpb, 2), "bowl_balls_per_boundary", sample_size=n_balls_total),
        # Tier 2: over-weighted per-innings rates.
        "wickets_per_innings":          wrap_metric(_r(cc_wpi, 3),    _r(cc_wpi, 3),    "bowl_wickets_per_innings",          sample_size=n_balls_total),
        "maidens_per_innings":          wrap_metric(_r(cc_mpi, 3),    _r(cc_mpi, 3),    "bowl_maidens_per_innings",          sample_size=n_balls_total),
        "four_wicket_hauls_per_innings": wrap_metric(_r(cc_fwh_pi, 4), _r(cc_fwh_pi, 4), "bowl_four_wicket_hauls_per_innings", sample_size=n_balls_total),
        # PT2 of spec-prob-baselines.md — wicket-ladder probs.
        "prob_zero":      wrap_metric(_r(cc_prob_zero, 4),  _r(cc_prob_zero, 4),  "bowl_prob_zero",      sample_size=n_balls_total),
        "prob_geq_1":     wrap_metric(_r(cc_prob_geq_1, 4), _r(cc_prob_geq_1, 4), "bowl_prob_geq_1",     sample_size=n_balls_total),
        "prob_geq_2":     wrap_metric(_r(cc_prob_geq_2, 4), _r(cc_prob_geq_2, 4), "bowl_prob_geq_2",     sample_size=n_balls_total),
        "prob_geq_3":     wrap_metric(_r(cc_prob_geq_3, 4), _r(cc_prob_geq_3, 4), "bowl_prob_geq_3",     sample_size=n_balls_total),
        "prob_geq_4":     wrap_metric(_r(cc_prob_geq_4, 4), _r(cc_prob_geq_4, 4), "bowl_prob_geq_4",     sample_size=n_balls_total),
        "prob_geq_5":     wrap_metric(_r(cc_prob_geq_5, 4), _r(cc_prob_geq_5, 4), "bowl_prob_geq_5",     sample_size=n_balls_total),
        "prob_3_given_2": wrap_metric(_r(cc_prob_3_g_2, 4), _r(cc_prob_3_g_2, 4), "bowl_prob_3_given_2", sample_size=n_balls_total),
        "prob_4_given_2": wrap_metric(_r(cc_prob_4_g_2, 4), _r(cc_prob_4_g_2, 4), "bowl_prob_4_given_2", sample_size=n_balls_total),
        "prob_5_given_2": wrap_metric(_r(cc_prob_5_g_2, 4), _r(cc_prob_5_g_2, 4), "bowl_prob_5_given_2", sample_size=n_balls_total),
        # PT3 of spec-prob-baselines.md — econ + runs-conceded threshold probs.
        "prob_econ_leq_6":  wrap_metric(_r(cc_prob_econ_leq_6, 4),  _r(cc_prob_econ_leq_6, 4),  "bowl_prob_econ_leq_6",  sample_size=n_balls_total),
        "prob_econ_leq_7":  wrap_metric(_r(cc_prob_econ_leq_7, 4),  _r(cc_prob_econ_leq_7, 4),  "bowl_prob_econ_leq_7",  sample_size=n_balls_total),
        "prob_econ_geq_9":  wrap_metric(_r(cc_prob_econ_geq_9, 4),  _r(cc_prob_econ_geq_9, 4),  "bowl_prob_econ_geq_9",  sample_size=n_balls_total),
        "prob_econ_geq_10": wrap_metric(_r(cc_prob_econ_geq_10, 4), _r(cc_prob_econ_geq_10, 4), "bowl_prob_econ_geq_10", sample_size=n_balls_total),
        "prob_runs_leq_15": wrap_metric(_r(cc_prob_runs_leq_15, 4), _r(cc_prob_runs_leq_15, 4), "bowl_prob_runs_leq_15", sample_size=n_balls_total),
        "prob_runs_leq_25": wrap_metric(_r(cc_prob_runs_leq_25, 4), _r(cc_prob_runs_leq_25, 4), "bowl_prob_runs_leq_25", sample_size=n_balls_total),
        "prob_runs_geq_40": wrap_metric(_r(cc_prob_runs_geq_40, 4), _r(cc_prob_runs_geq_40, 4), "bowl_prob_runs_geq_40", sample_size=n_balls_total),
        "prob_runs_geq_50": wrap_metric(_r(cc_prob_runs_geq_50, 4), _r(cc_prob_runs_geq_50, 4), "bowl_prob_runs_geq_50", sample_size=n_balls_total),
        "by_over": by_over_arr,
    }


@router.get("/players/bowling/summary")
async def scope_players_bowling_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    over_mix: str = Query(
        ...,
        description=(
            "Comma-separated 20-element vector of the bowler's mix"
            " across overs 1..20. Must sum to 1.0 +/- 0.001."
            " Trailing zeros may be omitted."
        ),
    ),
    drop: Optional[str] = Query(
        None,
        description=(
            "Comma-separated FilterBar axis names to mask before"
            " clause construction. Recognised: gender, team_type,"
            " tournament, season, filter_venue, filter_team,"
            " filter_opponent, team_class, series_type."
        ),
    ),
):
    """Over-mix-weighted cohort baseline for bowling (HTTP wrapper)."""
    db = get_db()
    try:
        mix = parse_mix(over_mix, 20)
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                    f" Recognised: {sorted(_DROP_AXES)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_bowling_cohort(db, filters, aux, mix, drop_set)


# ============================================================
# /scope/averages/players/bowling/by-season — Phase 4 of
# spec-player-baseline-parity.md. Per-season cohort baseline
# computed under the player's PER-SEASON over-mix (Q2 decision).
# ============================================================


async def compute_players_bowling_by_season(
    db,
    person_id: str,
    filters: FilterParams,
    aux: AuxParams,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """Per-season bowling cohort baseline keyed off the player's
    per-season over-mix. Spec: spec-player-baseline-parity.md §3.2.
    """
    where, params = build_scope_clauses(filters, drop=drop_set)

    # Q1: player's per-season legal_balls by over_number (mix derivation).
    player_sql = f"""
        SELECT pss.season,
               psso.over_number,
               psso.legal_balls
        FROM playerscopestatsover psso
        JOIN playerscopestats pss
          ON pss.scope_key = psso.scope_key
         AND pss.person_id = psso.person_id
        WHERE {where}
          AND psso.person_id = :__pid
        ORDER BY pss.season, psso.over_number
    """
    # Q2: cohort aggregates per (season, over_number).
    cohort_sql = f"""
        SELECT pss.season,
               psso.over_number,
               SUM(psso.runs_conceded)      AS runs_conceded,
               SUM(psso.legal_balls)        AS legal_balls,
               SUM(psso.wickets)            AS wickets,
               SUM(psso.dots)               AS dots,
               SUM(psso.boundaries)         AS boundaries,
               SUM(psso.maidens)            AS maidens,
               SUM(psso.innings_bowled)     AS innings_bowled,
               SUM(psso.four_wicket_hauls)  AS four_wicket_hauls,
               COUNT(DISTINCT psso.person_id) AS n_players
        FROM playerscopestatsover psso
        JOIN playerscopestats pss
          ON pss.scope_key = psso.scope_key
         AND pss.person_id = psso.person_id
        WHERE {where}
        GROUP BY pss.season, psso.over_number
        ORDER BY pss.season, psso.over_number
    """
    # Q3: per-season pool totals.
    pool_sql = f"""
        SELECT pss.season,
               COUNT(DISTINCT psso.person_id) AS n_players,
               SUM(psso.legal_balls)          AS n_balls_total
        FROM playerscopestatsover psso
        JOIN playerscopestats pss
          ON pss.scope_key = psso.scope_key
         AND pss.person_id = psso.person_id
        WHERE {where}
        GROUP BY pss.season
        ORDER BY pss.season
    """
    # Tier 2 of spec-apples-to-apples-baselines.md — per-season cohort
    # unique innings (denominator for the per-innings-scale factor that
    # converts per-bucket-attendance-rate cv to per-unique-innings rate).
    bowling_inn_sql = f"""
        SELECT pss.season,
               SUM(pss.bowling_innings) AS bowling_innings_total
        FROM playerscopestats pss
        WHERE {where}
        GROUP BY pss.season
        ORDER BY pss.season
    """
    p_params = {**params, "__pid": person_id}
    player_rows, cohort_rows, pool_rows, bi_rows = await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(cohort_sql, params),
        db.q(pool_sql, params),
        db.q(bowling_inn_sql, params),
    )

    # Roll up.
    cohort_by_season: dict[str, dict[int, dict]] = {}
    for r in cohort_rows:
        cohort_by_season.setdefault(r["season"], {})[r["over_number"]] = r
    pool_by_season: dict[str, dict] = {r["season"]: r for r in pool_rows}
    bowling_inn_by_season: dict[str, int] = {
        r["season"]: (r["bowling_innings_total"] or 0) for r in bi_rows
    }

    player_balls: dict[str, dict[int, int]] = {}
    # innings per season for wickets_per_innings derivation. The bowling
    # child table doesn't carry innings directly; we approximate via
    # the parent playerscopestats (innings_batted excludes pure
    # bowling-innings; use n_balls / 6 as a proxy span when not
    # surfaced — for now we elide wickets_per_innings on by-season
    # and surface wickets at the more natural per-over rate).
    for r in player_rows:
        player_balls.setdefault(r["season"], {})[r["over_number"]] = r["legal_balls"]

    by_season: list[dict] = []
    for season in sorted(player_balls.keys()):
        overs = player_balls[season]
        total = sum(overs.values())
        if total == 0:
            continue
        mix = [0.0] * 20
        for o, n in overs.items():
            if 1 <= o <= 20:
                mix[o - 1] = n / total

        season_cohort = cohort_by_season.get(season, {})
        by_over: list[dict] = []
        cliff_overs: list[int] = []
        for o in range(1, 21):
            threshold = bowling_threshold(o)
            r = season_cohort.get(o)
            if r is None:
                by_over.append({"below_support": True, "balls": 0})
                if mix[o - 1] > 0:
                    cliff_overs.append(o)
                continue
            balls = r["legal_balls"] or 0
            runs = r["runs_conceded"] or 0
            wickets = r["wickets"] or 0
            dots = r["dots"] or 0
            boundaries = r["boundaries"] or 0
            maidens = r["maidens"] or 0
            innings_bowled = r["innings_bowled"] or 0
            four_wicket_hauls = r["four_wicket_hauls"] or 0
            below = balls < threshold
            if below and mix[o - 1] > 0:
                cliff_overs.append(o)
            by_over.append({
                "below_support": below,
                "economy":           (runs * 6 / balls) if balls else None,
                "average":           (runs / wickets) if wickets else None,
                "strike_rate":       (balls / wickets) if wickets else None,
                "dot_pct":           (dots / balls * 100) if balls else None,
                "boundary_pct":      (boundaries / balls * 100) if balls else None,
                "balls_per_boundary": (balls / boundaries) if boundaries else None,
                "wickets_per_over":  (wickets * 6 / balls) if balls else None,
                # Tier 2: per-bucket per-innings rates use the new
                # innings_bowled denominator — replaces the prior
                # wickets/over × 4 heuristic for per-innings cohort.
                "wickets_per_innings":           (wickets / innings_bowled) if innings_bowled else None,
                "maidens_per_innings":           (maidens / innings_bowled) if innings_bowled else None,
                "four_wicket_hauls_per_innings": (four_wicket_hauls / innings_bowled) if innings_bowled else None,
            })

        pool = pool_by_season.get(season, {})
        n_players_total = pool.get("n_players") or 0
        n_balls_total = pool.get("n_balls_total") or 0

        row: dict = {
            "season": season,
            "mix": [round(m, 4) for m in mix],
            "n_players": n_players_total,
            "n_balls": n_balls_total,
        }

        if cliff_overs:
            row.update({
                "below_support": True,
                "cliff_overs": cliff_overs,
                "economy": None, "bowling_avg": None,
                "strike_rate": None, "dot_pct": None,
                "boundary_pct": None, "balls_per_boundary": None,
                "wickets_per_over": None, "wickets_per_innings": None,
                "maidens_per_innings": None,
                # Tier 2: now over-weighted, null under cliff.
                "four_wicket_hauls_per_innings": None,
            })
            by_season.append(row)
            continue

        def cv(field: str) -> Optional[float]:
            return convex_combine(mix, {o: by_over[o - 1].get(field) for o in range(1, 21)})

        def _r(v, n):
            return round(v, n) if v is not None else None

        cc_wpo = cv("wickets_per_over")
        # Tier 2: per-innings rates need scaling by per-season
        # avg_attendances_per_innings — same dimensional rationale as
        # the /summary path (see compute_players_bowling_cohort).
        season_attendances = sum(
            (r["innings_bowled"] or 0) for r in season_cohort.values()
        )
        season_unique_innings = bowling_inn_by_season.get(season, 0)
        season_scale = (
            (season_attendances / season_unique_innings)
            if season_unique_innings else 0
        )

        def cv_pi(field: str) -> Optional[float]:
            v = cv(field)
            if v is None or season_scale == 0:
                return v
            return v * season_scale

        row.update({
            "below_support": False,
            "cliff_overs": [],
            "economy":            _r(cv("economy"), 2),
            "bowling_avg":        _r(cv("average"), 2),
            "strike_rate":        _r(cv("strike_rate"), 2),
            "dot_pct":            _r(cv("dot_pct"), 1),
            "boundary_pct":       _r(cv("boundary_pct"), 1),
            "balls_per_boundary": _r(cv("balls_per_boundary"), 2),
            "wickets_per_over":   _r(cc_wpo, 3),
            # Tier 2: over-weighted per-innings rates via per-bucket
            # innings_bowled (attendance) × per-season scaling factor.
            "wickets_per_innings":           _r(cv_pi("wickets_per_innings"), 3),
            "maidens_per_innings":           _r(cv_pi("maidens_per_innings"), 3),
            "four_wicket_hauls_per_innings": _r(cv_pi("four_wicket_hauls_per_innings"), 4),
        })
        by_season.append(row)

    return {"by_season": by_season}


@router.get("/players/bowling/by-season")
async def scope_players_bowling_by_season(
    person_id: str = Query(
        ...,
        description=(
            "Player ID. The endpoint derives per-season over-mix"
            " server-side from playerscopestatsover joined on this"
            " person_id; per-season cohort baseline is then computed"
            " under each season's mix."
        ),
    ),
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    drop: Optional[str] = Query(None),
):
    """Per-season over-mix-weighted cohort baseline for bowling."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_bowling_by_season(
        db, person_id, filters, aux, drop_set,
    )


# ============================================================
# /scope/averages/players/bowling/by-phase — derives from
# playerscopestatsover (no new table) by mapping over_number to
# phase. Uses the player's phase-specific over-mix (overs in
# phase renormalized) so the cohort baseline reflects bowlers in
# the same role at the same phase.
# ============================================================


# Over → phase bucket mapping matches the batting populate / team-
# side conventions: 1-6 → pp, 7-15 → middle, 16-20 → death (1-indexed
# over_number in playerscopestatsover).
PHASE_OVERS = {
    1: list(range(1, 7)),     # powerplay
    2: list(range(7, 16)),    # middle
    3: list(range(16, 21)),   # death
}


async def _by_phase_bowling_precomputed(
    db, person_id: str, filters: FilterParams, drop_set: Optional[set[str]],
):
    """Fast path: per-over player-mix + cohort reads off the precomputed
    `playerscopestatsover` table by scope_key (none-of-six). Returns the
    `(player_rows, cohort_rows)` pair the by-phase builder consumes."""
    where, params = build_scope_clauses(filters, drop=drop_set)
    player_sql = f"""
        SELECT psso.over_number, psso.legal_balls
        FROM playerscopestatsover psso
        WHERE psso.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
          AND psso.person_id = :__pid
    """
    cohort_sql = f"""
        SELECT psso.over_number,
               SUM(psso.runs_conceded) AS runs_conceded,
               SUM(psso.legal_balls)   AS legal_balls,
               SUM(psso.wickets)       AS wickets,
               SUM(psso.dots)          AS dots,
               SUM(psso.boundaries)    AS boundaries,
               SUM(psso.maidens)       AS maidens,
               COUNT(DISTINCT psso.person_id) AS n_players
        FROM playerscopestatsover psso
        WHERE psso.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
        GROUP BY psso.over_number
        ORDER BY psso.over_number
    """
    p_params = {**params, "__pid": person_id}
    return await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(cohort_sql, params),
    )


async def compute_players_bowling_by_phase(
    db,
    person_id: str,
    filters: FilterParams,
    aux: AuxParams,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """Per-phase bowling cohort baseline with phase-specific over-mix.

    Derives from playerscopestatsover — for each phase, the cohort
    rates are convex-combined across the overs in that phase, weighted
    by the player's renormalized over distribution within that phase.

    Dispatches on `is_precomputed_scope` (Phase 3d): none of the six set
    → precomputed per-over read; any set → live per-over aggregation over
    `delivery` (bowling orientation) so the per-phase cohort narrows.

    Spec: spec-player-baseline-parity.md §3.2 + Phase 3d of
    spec-player-baseline-aux-fallback.md.
    """
    if is_precomputed_scope(filters, aux):
        player_rows, cohort_rows = await _by_phase_bowling_precomputed(
            db, person_id, filters, drop_set,
        )
    else:
        player_rows, cohort_rows = await asyncio.gather(
            _bowling_player_over_mix_live(db, person_id, filters, aux),
            _bowling_over_cohort_live(db, filters, aux),
        )

    cohort_by_over = {r["over_number"]: r for r in cohort_rows}
    player_balls_by_over = {r["over_number"]: r["legal_balls"] for r in player_rows}

    PHASE_NAMES = {1: "powerplay", 2: "middle", 3: "death"}

    def _r(v, n):
        return round(v, n) if v is not None else None

    by_phase: list[dict] = []
    for phase in (1, 2, 3):
        overs = PHASE_OVERS[phase]
        # Player mix within this phase.
        phase_balls_total = sum(player_balls_by_over.get(o, 0) for o in overs)
        phase_mix = {o: 0.0 for o in overs}
        if phase_balls_total > 0:
            for o in overs:
                phase_mix[o] = player_balls_by_over.get(o, 0) / phase_balls_total

        # Cliff: any over with player mix > 0 must meet bowling_threshold.
        cliff_overs: list[int] = []
        per_over_rates: dict[int, dict] = {}
        for o in overs:
            r = cohort_by_over.get(o)
            threshold = bowling_threshold(o)
            if r is None:
                if phase_mix[o] > 0:
                    cliff_overs.append(o)
                per_over_rates[o] = {"below_support": True}
                continue
            balls = r["legal_balls"] or 0
            runs = r["runs_conceded"] or 0
            wickets = r["wickets"] or 0
            dots = r["dots"] or 0
            boundaries = r["boundaries"] or 0
            maidens = r["maidens"] or 0
            n_p = r["n_players"] or 0
            below = balls < threshold
            if below and phase_mix[o] > 0:
                cliff_overs.append(o)
            per_over_rates[o] = {
                "below_support": below,
                "economy":           (runs * 6 / balls) if balls else None,
                "strike_rate":       (balls / wickets) if wickets else None,
                "dot_pct":           (dots / balls * 100) if balls else None,
                "boundary_pct":      (boundaries / balls * 100) if balls else None,
                "wickets_per_over":  (wickets * 6 / balls) if balls else None,
                "maidens_per_player_over": (maidens / n_p) if n_p else None,
            }

        # Cohort-wide phase aggregates for n_players + n_balls totals.
        phase_balls_cohort = sum(
            (cohort_by_over.get(o, {}).get("legal_balls") or 0) for o in overs
        )
        phase_players_cohort = max(
            ((cohort_by_over.get(o, {}).get("n_players") or 0) for o in overs),
            default=0,
        )

        row: dict = {
            "phase": PHASE_NAMES[phase],
            "phase_bucket": phase,
            "mix": [round(phase_mix[o], 4) for o in overs],
            "overs": overs,
            "n_players": phase_players_cohort,
            "n_balls_in_phase": phase_balls_cohort,
        }

        if cliff_overs or phase_balls_total == 0:
            row.update({
                "below_support": True,
                "cliff_overs": cliff_overs,
                "economy": None, "strike_rate": None, "dot_pct": None,
                "boundary_pct": None, "wickets_per_over": None,
                "wickets_per_innings_in_phase": None,
            })
            by_phase.append(row)
            continue

        # Convex-combine using the phase mix (normalized within phase
        # overs only).
        def pcv(field: str) -> Optional[float]:
            total_w = 0.0
            total_v = 0.0
            for o in overs:
                w = phase_mix[o]
                if w == 0:
                    continue
                total_w += w
                v = per_over_rates[o].get(field)
                if v is None:
                    continue
                total_v += w * v
            if total_w == 0:
                return None
            return total_v

        cc_wpo = pcv("wickets_per_over")
        row.update({
            "below_support": False,
            "cliff_overs": [],
            "economy":      _r(pcv("economy"), 2),
            "strike_rate":  _r(pcv("strike_rate"), 2),
            "dot_pct":      _r(pcv("dot_pct"), 1),
            "boundary_pct": _r(pcv("boundary_pct"), 1),
            "wickets_per_over": _r(cc_wpo, 3),
            # Per-innings approximation: typical bowler bowls 1.x overs
            # of a phase per innings. Phase 1 (PP, 6 overs of innings),
            # phase 2 (middle, 9 overs of innings), phase 3 (death, 5
            # overs of innings). The player's actual within-phase
            # workload varies; we'd need per-innings data for an exact
            # number. For the chip purpose, we expose wickets_per_over
            # (exact) — wickets_per_innings_in_phase = wickets_per_over
            # × (phase_balls_total / n_innings_for_player). Without
            # per-innings, we approximate by the cohort's typical phase
            # workload as overs in the phase that the cohort bowled
            # per player: phase_balls_cohort / phase_players_cohort / 6.
            "wickets_per_innings_in_phase": _r(
                cc_wpo * (phase_balls_cohort / phase_players_cohort / 6)
                if (cc_wpo is not None and phase_players_cohort > 0) else None,
                3,
            ),
        })
        by_phase.append(row)

    return {"by_phase": by_phase, "person_id": person_id}


@router.get("/players/bowling/by-phase")
async def scope_players_bowling_by_phase(
    person_id: str = Query(
        ...,
        description=(
            "Player ID. The endpoint derives the bowler's phase-"
            "specific over-mix (renormalized within each phase's"
            " overs) from playerscopestatsover; per-phase cohort"
            " baseline is computed under each phase's mix."
        ),
    ),
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    drop: Optional[str] = Query(None),
):
    """Per-phase phase-mix-weighted cohort baseline for bowling."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_bowling_by_phase(
        db, person_id, filters, aux, drop_set,
    )


async def compute_players_fielding_cohort(
    db,
    filters: FilterParams,
    aux: AuxParams,
    is_keeper: int,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """In-process fielding cohort baseline — same shape as the HTTP
    endpoint. Phase 4 player /summary endpoints call this to fold the
    cohort baseline into their envelope-wrapped response without a
    second HTTP roundtrip.
    """
    where, params = build_scope_clauses(filters, drop=drop_set)

    # Cohort partition: matches_as_keeper > 0 selects keepers; = 0
    # selects pure outfielders. Subtotals over `catches`, `stumpings`,
    # `runouts`, `matches` aggregated from parent playerscopestats —
    # non-substitute numerator comes from the fielding-position child
    # in parallel (substitute fielders excluded there at populate).
    # The keeper-flag partition is PER (person, scope) — a player who
    # kept in 2023 but not 2024 belongs to the outfielder cohort for
    # 2024 only. Use a JOIN so the matches_as_keeper predicate gates
    # at the right grain rather than IN-subquery which leaks across
    # scope_keys for one person.
    keeper_pred = ">" if is_keeper else "="
    pool_sql = f"""
        SELECT COUNT(*)                       AS n_fielders,
               SUM(pss.matches)               AS n_matches_total
        FROM playerscopestats pss
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {where}
    """
    # Non-substitute catches/stumpings/run_outs from the fielding-
    # position child, joined per-row to the parent keeper-partition.
    nonsub_sql = f"""
        SELECT SUM(pssfp.catches)    AS catches,
               SUM(pssfp.stumpings)  AS stumpings,
               SUM(pssfp.run_outs)   AS run_outs,
               SUM(pssfp.dismissals) AS dismissals
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pss.person_id = pssfp.person_id
         AND pss.scope_key = pssfp.scope_key
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {where}
    """
    by_dis_pos_sql = f"""
        SELECT pssfp.position_bucket,
               SUM(pssfp.catches)    AS catches,
               SUM(pssfp.stumpings)  AS stumpings,
               SUM(pssfp.run_outs)   AS run_outs,
               SUM(pssfp.dismissals) AS dismissals,
               COUNT(DISTINCT pssfp.person_id) AS n_players
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pss.person_id = pssfp.person_id
         AND pss.scope_key = pssfp.scope_key
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {where}
        GROUP BY pssfp.position_bucket
        ORDER BY pssfp.position_bucket
    """

    # PT4 of spec-prob-baselines.md — match-grain catch distribution
    # aggregated across the keeper-binary cohort. Backs the cohort
    # baselines for the P(=0)/P(=1)/P(≥2) chips on /fielders/.../
    # distribution. Joined per-row to the parent keeper-partition so
    # the cohort matches the existing per-match-rate cohorts.
    catch_dist_sql = f"""
        SELECT SUM(pssfcd.matches_with_0)   AS m0,
               SUM(pssfcd.matches_with_1)   AS m1,
               SUM(pssfcd.matches_with_ge2) AS mge2
        FROM playerscopestatsfieldingcatchdist pssfcd
        JOIN playerscopestats pss
          ON pss.person_id = pssfcd.person_id
         AND pss.scope_key = pssfcd.scope_key
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {where}
    """

    pool, nonsub, by_dis_rows, catch_dist = await asyncio.gather(
        db.q(pool_sql, params),
        db.q(nonsub_sql, params),
        db.q(by_dis_pos_sql, params),
        db.q(catch_dist_sql, params),
    )

    n_fielders = (pool[0].get("n_fielders") if pool else 0) or 0
    n_matches = (pool[0].get("n_matches_total") if pool else 0) or 0

    nonsub_catches    = (nonsub[0].get("catches") if nonsub else 0) or 0
    nonsub_stumpings  = (nonsub[0].get("stumpings") if nonsub else 0) or 0
    nonsub_run_outs   = (nonsub[0].get("run_outs") if nonsub else 0) or 0
    nonsub_dismissals = (nonsub[0].get("dismissals") if nonsub else 0) or 0

    def _r(num: int, den: int, ndigits: int) -> Optional[float]:
        return round(num / den, ndigits) if den else None

    catches_pm    = _r(nonsub_catches,    n_matches, 3)
    stumpings_pm  = _r(nonsub_stumpings,  n_matches, 3)
    run_outs_pm   = _r(nonsub_run_outs,   n_matches, 3)
    dismissals_pm = _r(nonsub_dismissals, n_matches, 3)

    # by_dismissed_position — per-bucket cohort sub-rates for next-spec.
    by_dis: list[dict] = []
    by_dis_by_bucket = {r["position_bucket"]: r for r in by_dis_rows}
    for b in range(1, 11):
        r = by_dis_by_bucket.get(b)
        threshold = fielding_threshold(b)
        if r is None:
            by_dis.append({
                "bucket": b, "label": fielding_bucket_label(b),
                "n_dismissals": 0, "n_players": 0, "threshold": threshold,
                "below_support": True,
                "catches_per_match": None, "stumpings_per_match": None,
                "run_outs_per_match": None, "dismissals_per_match": None,
            })
            continue
        dis = r["dismissals"] or 0
        by_dis.append({
            "bucket": b, "label": fielding_bucket_label(b),
            "n_dismissals": dis, "n_players": r["n_players"] or 0,
            "threshold": threshold,
            "below_support": dis < threshold,
            "catches_per_match":    _r(r["catches"] or 0, n_matches, 4),
            "stumpings_per_match":  _r(r["stumpings"] or 0, n_matches, 4),
            "run_outs_per_match":   _r(r["run_outs"] or 0, n_matches, 4),
            "dismissals_per_match": _r(dis, n_matches, 4),
        })

    cohort_block = {
        "match_dimension": "is_keeper",
        "is_keeper": is_keeper,
        "n_fielders": n_fielders,
        "n_matches_total": n_matches,
    }

    # No per-headline cliff for fielding (spec §5.4): the binary
    # is_keeper axis isn't a sliding-scale dimension. The
    # by_dismissed_position[].below_support flags surface for the
    # next-spec impact-weighted analyses to consume.
    # PT4 of spec-prob-baselines.md — per-match catch ProbChip cohort
    # baselines. Aggregate counts across the keeper-binary cohort then
    # divide by their sum (which is matches_total across the cohort).
    # The cohort sample matches the chip's master sample exactly
    # (Convention 3 catches + is_substitute=0, matchplayer-based).
    cd_m0   = (catch_dist[0].get("m0")   if catch_dist else 0) or 0
    cd_m1   = (catch_dist[0].get("m1")   if catch_dist else 0) or 0
    cd_mge2 = (catch_dist[0].get("mge2") if catch_dist else 0) or 0
    cd_total = cd_m0 + cd_m1 + cd_mge2
    prob_zero  = round(cd_m0   / cd_total, 4) if cd_total else None
    prob_one   = round(cd_m1   / cd_total, 4) if cd_total else None
    prob_geq_2 = round(cd_mge2 / cd_total, 4) if cd_total else None

    return {
        "cohort": cohort_block,
        "catches_per_match":    wrap_metric(catches_pm,    catches_pm,    "field_catches_per_match",    sample_size=n_matches),
        "stumpings_per_match":  wrap_metric(stumpings_pm,  stumpings_pm,  "field_stumpings_per_match",  sample_size=n_matches),
        "run_outs_per_match":   wrap_metric(run_outs_pm,   run_outs_pm,   "field_run_outs_per_match",   sample_size=n_matches),
        "dismissals_per_match": wrap_metric(dismissals_pm, dismissals_pm, "field_dismissals_per_match", sample_size=n_matches),
        # PT4 of spec-prob-baselines.md — catch-per-match ProbChip cohort
        # baselines. cd_total is the cohort's matches_total (sum of the
        # three bucket counts); sample_size mirrors the per-match-rate
        # envelopes for consistency. direction conventions live on the
        # chip side (spec §6) — P(=0) lower_better, P(=1) descriptive,
        # P(≥2) higher_better.
        "prob_zero":   wrap_metric(prob_zero,  prob_zero,  "field_prob_zero",   sample_size=cd_total),
        "prob_one":    wrap_metric(prob_one,   prob_one,   "field_prob_one",    sample_size=cd_total),
        "prob_geq_2":  wrap_metric(prob_geq_2, prob_geq_2, "field_prob_geq_2",  sample_size=cd_total),
        "by_dismissed_position": by_dis,
    }


# ============================================================
# /scope/averages/players/fielding/by-season — Phase 4 of
# spec-player-baseline-parity.md. Per-season cohort baseline for
# fielding. The cohort is keeper-binary; for each season the
# endpoint determines whether the player kept in that season
# (matches_as_keeper > 0 → keeper, else outfielder) and surfaces
# the matching cohort's per-match rates.
# ============================================================


async def compute_players_fielding_by_season(
    db,
    person_id: str,
    filters: FilterParams,
    aux: AuxParams,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """Per-season fielding cohort baseline keyed off the player's
    per-season keeper status (binary). Returns one row per season.
    Spec: spec-player-baseline-parity.md §3.2.
    """
    where, params = build_scope_clauses(filters, drop=drop_set)

    # Q1: player's per-season keeper status.
    player_sql = f"""
        SELECT pss.season,
               CASE WHEN pss.matches_as_keeper > 0 THEN 1 ELSE 0 END AS is_keeper,
               pss.matches AS player_matches
        FROM playerscopestats pss
        WHERE {where}
          AND pss.person_id = :__pid
        ORDER BY pss.season
    """
    # Q2: cohort pool per (season, keeper_flag) from parent.
    pool_sql = f"""
        SELECT pss.season,
               CASE WHEN pss.matches_as_keeper > 0 THEN 1 ELSE 0 END AS is_keeper,
               COUNT(*)                AS n_fielders,
               SUM(pss.matches)        AS n_matches_total
        FROM playerscopestats pss
        WHERE {where}
        GROUP BY pss.season, is_keeper
        ORDER BY pss.season, is_keeper
    """
    # Q3: cohort fielding aggregates per (season, keeper_flag) from
    # the fielding-position child (non-substitute) joined to parent.
    nonsub_sql = f"""
        SELECT pss.season,
               CASE WHEN pss.matches_as_keeper > 0 THEN 1 ELSE 0 END AS is_keeper,
               SUM(pssfp.catches)    AS catches,
               SUM(pssfp.stumpings)  AS stumpings,
               SUM(pssfp.run_outs)   AS run_outs,
               SUM(pssfp.dismissals) AS dismissals
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pss.person_id = pssfp.person_id
         AND pss.scope_key = pssfp.scope_key
        WHERE {where}
        GROUP BY pss.season, is_keeper
        ORDER BY pss.season, is_keeper
    """
    p_params = {**params, "__pid": person_id}
    player_rows, pool_rows, nonsub_rows = await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(pool_sql, params),
        db.q(nonsub_sql, params),
    )

    # Roll up. Key by (season, is_keeper).
    pool_by = {(r["season"], r["is_keeper"]): r for r in pool_rows}
    nonsub_by = {(r["season"], r["is_keeper"]): r for r in nonsub_rows}

    def _r(num, den, n):
        return round(num / den, n) if den else None

    by_season: list[dict] = []
    for pr in player_rows:
        season = pr["season"]
        is_keeper = pr["is_keeper"]
        pool = pool_by.get((season, is_keeper))
        nonsub = nonsub_by.get((season, is_keeper))

        n_fielders = (pool.get("n_fielders") if pool else 0) or 0
        n_matches  = (pool.get("n_matches_total") if pool else 0) or 0
        catches    = (nonsub.get("catches") if nonsub else 0) or 0
        stumpings  = (nonsub.get("stumpings") if nonsub else 0) or 0
        run_outs   = (nonsub.get("run_outs") if nonsub else 0) or 0
        dismissals = (nonsub.get("dismissals") if nonsub else 0) or 0

        below = n_fielders < 3  # tiny-cohort guard

        row = {
            "season": season,
            "is_keeper": is_keeper,
            "n_players": n_fielders,
            "n_matches": n_matches,
            "below_support": below,
        }
        if below:
            row.update({
                "catches_per_match": None, "stumpings_per_match": None,
                "run_outs_per_match": None, "dismissals_per_match": None,
            })
        else:
            row.update({
                "catches_per_match":    _r(catches,    n_matches, 4),
                "stumpings_per_match":  _r(stumpings,  n_matches, 4),
                "run_outs_per_match":   _r(run_outs,   n_matches, 4),
                "dismissals_per_match": _r(dismissals, n_matches, 4),
            })
        by_season.append(row)

    return {"by_season": by_season}


@router.get("/players/fielding/by-season")
async def scope_players_fielding_by_season(
    person_id: str = Query(
        ...,
        description=(
            "Player ID. The endpoint determines per-season is_keeper"
            " status from matches_as_keeper > 0 and surfaces the"
            " matching keeper-binary cohort's per-match rates."
        ),
    ),
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    drop: Optional[str] = Query(None),
):
    """Per-season keeper-binary cohort baseline for fielding."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_fielding_by_season(
        db, person_id, filters, aux, drop_set,
    )


@router.get("/players/fielding/summary")
async def scope_players_fielding_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    is_keeper: int = Query(
        ...,
        description=(
            "Binary axis. 0 = outfielder cohort (pss.matches_as_keeper"
            " = 0); 1 = keeper cohort (pss.matches_as_keeper > 0)."
            " Spec §5.4 — fielding is NOT position-weighted at the"
            " headline; the partition is on this binary instead."
        ),
        ge=0, le=1,
    ),
    drop: Optional[str] = Query(
        None,
        description="See batting/summary for recognised axis names.",
    ),
):
    """Keeper-flag-partitioned cohort baseline for fielding (HTTP wrapper)."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                    f" Recognised: {sorted(_DROP_AXES)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_fielding_cohort(db, filters, aux, is_keeper, drop_set)


# ============================================================
# /scope/averages/players/fielding/by-phase — Phase 4 of
# spec-player-baseline-parity.md. Per-phase keeper-binary cohort
# baseline for fielding. Backed by playerscopestats_fielding_phase.
# ============================================================


async def compute_players_fielding_by_phase(
    db,
    person_id: str,
    filters: FilterParams,
    aux: AuxParams,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """Per-phase keeper-binary fielding cohort baseline. The player's
    LIFETIME keeper status (matches_as_keeper > 0 anywhere in scope)
    determines which cohort the phase row reads — per-season variation
    is surfaced in /by-season; the phase view is by design a stable
    role-baseline.
    Spec: spec-player-baseline-parity.md §3.2.
    """
    where, params = build_scope_clauses(filters, drop=drop_set)

    # Q1: player's keeper status across all scope (lifetime).
    player_sql = f"""
        SELECT CASE WHEN COALESCE(SUM(pss.matches_as_keeper), 0) > 0
                    THEN 1 ELSE 0 END AS is_keeper,
               COALESCE(SUM(pss.matches), 0) AS player_matches
        FROM playerscopestats pss
        WHERE {where}
          AND pss.person_id = :__pid
    """
    # Q2: cohort fielding aggregates per (phase, keeper_flag) from the
    # new phase child table joined to parent for the keeper partition.
    cohort_sql = f"""
        SELECT pssfph.phase_bucket,
               CASE WHEN pss.matches_as_keeper > 0 THEN 1 ELSE 0 END AS is_keeper,
               SUM(pssfph.catches_in_phase)    AS catches,
               SUM(pssfph.stumpings_in_phase)  AS stumpings,
               SUM(pssfph.run_outs_in_phase)   AS run_outs,
               SUM(pssfph.dismissals_in_phase) AS dismissals,
               COUNT(DISTINCT pssfph.person_id) AS n_players
        FROM playerscopestatsfieldingphase pssfph
        JOIN playerscopestats pss
          ON pss.person_id = pssfph.person_id
         AND pss.scope_key = pssfph.scope_key
        WHERE {where}
        GROUP BY pssfph.phase_bucket, is_keeper
        ORDER BY pssfph.phase_bucket, is_keeper
    """
    # Q3: pool denominator (n_matches) per keeper_flag — used as the
    # per-match-rate denominator. Same partition logic as the cohort
    # summary's pool query.
    pool_sql = f"""
        SELECT CASE WHEN pss.matches_as_keeper > 0 THEN 1 ELSE 0 END AS is_keeper,
               COUNT(*)         AS n_fielders,
               SUM(pss.matches) AS n_matches_total
        FROM playerscopestats pss
        WHERE {where}
        GROUP BY is_keeper
    """
    p_params = {**params, "__pid": person_id}
    player_rows, cohort_rows, pool_rows = await asyncio.gather(
        db.q(player_sql, p_params),
        db.q(cohort_sql, params),
        db.q(pool_sql, params),
    )

    is_keeper = (player_rows[0].get("is_keeper") if player_rows else 0) or 0
    pool_by_keeper = {r["is_keeper"]: r for r in pool_rows}
    pool = pool_by_keeper.get(is_keeper, {})
    n_matches = (pool.get("n_matches_total") or 0)
    n_fielders = (pool.get("n_fielders") or 0)

    cohort_by_phase = {
        r["phase_bucket"]: r for r in cohort_rows if r["is_keeper"] == is_keeper
    }

    PHASE_NAMES = {1: "powerplay", 2: "middle", 3: "death"}

    def _r(num, den, n):
        return round(num / den, n) if den else None

    by_phase: list[dict] = []
    for b in (1, 2, 3):
        r = cohort_by_phase.get(b)
        out = {
            "phase": PHASE_NAMES[b],
            "phase_bucket": b,
            "is_keeper": is_keeper,
            "n_players": n_fielders,
            "n_matches": n_matches,
        }
        if r is None or n_matches == 0:
            out.update({
                "below_support": True,
                "catches_per_match": None, "stumpings_per_match": None,
                "run_outs_per_match": None, "dismissals_per_match": None,
            })
            by_phase.append(out)
            continue

        catches = r["catches"] or 0
        stumpings = r["stumpings"] or 0
        run_outs = r["run_outs"] or 0
        dismissals = r["dismissals"] or 0
        # Below-support: tiny cohort.
        below = (r["n_players"] or 0) < 3
        out.update({
            "below_support": below,
            "catches_per_match":    None if below else _r(catches,    n_matches, 4),
            "stumpings_per_match":  None if below else _r(stumpings,  n_matches, 4),
            "run_outs_per_match":   None if below else _r(run_outs,   n_matches, 4),
            "dismissals_per_match": None if below else _r(dismissals, n_matches, 4),
        })
        by_phase.append(out)

    return {"by_phase": by_phase, "person_id": person_id, "is_keeper": is_keeper}


@router.get("/players/fielding/by-phase")
async def scope_players_fielding_by_phase(
    person_id: str = Query(
        ...,
        description=(
            "Player ID. Lifetime keeper status (matches_as_keeper > 0"
            " anywhere in scope) selects the keeper-binary cohort;"
            " per-phase rates are then surfaced for that cohort."
        ),
    ),
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    drop: Optional[str] = Query(None),
):
    """Per-phase keeper-binary cohort baseline for fielding."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_fielding_by_phase(
        db, person_id, filters, aux, drop_set,
    )


@router.get("/players/keeping/summary")
async def scope_players_keeping_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    drop: Optional[str] = Query(
        None,
        description="See batting/summary for recognised axis names.",
    ),
):
    """Cohort baseline for KEEPING (HTTP wrapper around the in-process helper)."""
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                    f" Recognised: {sorted(_DROP_AXES)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await compute_players_keeping_cohort(db, filters, aux, drop_set)


async def compute_players_keeping_cohort(
    db,
    filters: FilterParams,
    aux: AuxParams,
    drop_set: Optional[set[str]] = None,
) -> dict:
    """In-process keeping cohort baseline.

    Headline rates use matches_as_keeper as the per-keeper denominator
    (catches_as_keeper, stumpings, run_outs — all higher_better).
    Byes-per-innings deferred — needs keeperassignment join.
    """
    where, params = build_scope_clauses(filters, drop=drop_set)

    # Aggregate over keeper-active rows. matches_as_keeper > 0 selects
    # the keeper cohort; the per-keeper-match denominator is exact
    # because stumpings + catches_as_keeper only accrue during keeping.
    pool_sql = f"""
        SELECT COUNT(*)                    AS n_keepers,
               SUM(pss.matches_as_keeper)  AS n_matches_keeping,
               SUM(pss.catches_as_keeper)  AS catches_as_keeper,
               SUM(pss.stumpings)          AS stumpings
        FROM playerscopestats pss
        WHERE pss.matches_as_keeper > 0
          AND {where}
    """
    # run_outs while keeping aren't separately tracked on parent;
    # approximate by summing the fielding-position child's run_outs
    # for the same keeper-cohort rows (per-(person, scope) JOIN, same
    # pattern as Phase 3.3).
    runouts_sql = f"""
        SELECT SUM(pssfp.run_outs) AS run_outs
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pss.person_id = pssfp.person_id
         AND pss.scope_key = pssfp.scope_key
        WHERE pss.matches_as_keeper > 0
          AND {where}
    """
    pool, ro_row = await asyncio.gather(
        db.q(pool_sql, params),
        db.q(runouts_sql, params),
    )

    n_keepers = (pool[0].get("n_keepers") if pool else 0) or 0
    n_matches_keeping = (pool[0].get("n_matches_keeping") if pool else 0) or 0
    catches = (pool[0].get("catches_as_keeper") if pool else 0) or 0
    stumpings = (pool[0].get("stumpings") if pool else 0) or 0
    run_outs = (ro_row[0].get("run_outs") if ro_row else 0) or 0
    dismissals = catches + stumpings + run_outs

    def _r(num: int, den: int, ndigits: int) -> Optional[float]:
        return round(num / den, ndigits) if den else None

    catches_pm     = _r(catches,    n_matches_keeping, 3)
    stumpings_pm   = _r(stumpings,  n_matches_keeping, 3)
    run_outs_pm    = _r(run_outs,   n_matches_keeping, 3)
    dismissals_pm  = _r(dismissals, n_matches_keeping, 3)

    cohort_block = {
        "match_dimension": "is_keeper",
        "is_keeper": 1,
        "n_keepers": n_keepers,
        "n_matches_keeping": n_matches_keeping,
    }

    return {
        "cohort": cohort_block,
        "catches_per_match":    wrap_metric(catches_pm,    catches_pm,    "keep_catches_per_match",    sample_size=n_matches_keeping),
        "stumpings_per_match":  wrap_metric(stumpings_pm,  stumpings_pm,  "keep_stumpings_per_match",  sample_size=n_matches_keeping),
        "run_outs_per_match":   wrap_metric(run_outs_pm,   run_outs_pm,   "keep_run_outs_per_match",   sample_size=n_matches_keeping),
        "dismissals_per_match": wrap_metric(dismissals_pm, dismissals_pm, "keep_dismissals_per_match", sample_size=n_matches_keeping),
    }
