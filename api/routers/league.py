"""League router — above-tournament scope dossier endpoints.

The League page (`/league` in the SPA) is the destination for scope
configurations that are broader than a single tournament — "men's club
cricket", "men's primary-tier clubs across all leagues", "women's
international ICC events", etc. It mirrors `TournamentDossier`
structurally (Overview / Batting / Bowling / Fielding tabs) but every
endpoint here drops the per-tournament restriction in favour of pure
FilterParams scoping.

The discipline subtabs reuse the existing `/api/v1/scope/averages/*`
endpoints (already pool-weighted at every FilterBar scope). This
router adds the three remaining payload shapes the spec calls out:

  - `/api/v1/league/overview`    — Overview composite (counts +
    top-teams + best-moments singletons).
  - `/api/v1/league/champions`   — cross-tournament unionized
    Champions table (Series-by-season's finals shape, unioned).
  - `/api/v1/league/leaders/{batting,bowling,fielding}` — top-N
    players in scope across the whole pool, paginated.

Spec: `internal_docs/spec-league-pages.md`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_db
from ..filters import FilterParams, AuxParams
from .tournaments import (
    _tournament_scope_where, _inning_extras, _safe_div,
)

router = APIRouter(prefix="/api/v1/league", tags=["League"])


# ─── /league/overview ──────────────────────────────────────────────────

@router.get("/overview")
async def league_overview(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Composite Overview payload — counts strip, top teams, best moments.

    The Tournaments-in-scope tile grid uses the existing
    `/api/v1/series/landing` payload; the Champions table uses
    `/league/champions`. This endpoint covers the remaining four
    Overview blocks in a single roundtrip.

    Honours every FilterParams field (no tournament restriction —
    tournament-narrowed callers should be redirected to /series).
    """
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament=None)
    inn_clause, inn_params = _inning_extras(aux)
    params.update(inn_params)

    # ── Headline counts ──
    meta_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) AS matches,
               COUNT(DISTINCT m.event_name) AS tournaments
        FROM match m
        WHERE {where}
        """,
        params,
    )
    meta = meta_rows[0] if meta_rows else {"matches": 0, "tournaments": 0}

    inn_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS innings
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}{inn_clause}
        """,
        params,
    )
    innings = (inn_rows[0]["innings"] if inn_rows else 0) or 0

    teams_rows = await db.q(
        f"""
        WITH sides AS (
          SELECT m.team1 AS team FROM match m WHERE {where}
          UNION
          SELECT m.team2 FROM match m WHERE {where}
        )
        SELECT COUNT(*) AS n FROM sides
        """,
        params,
    )
    teams_count = (teams_rows[0]["n"] if teams_rows else 0) or 0

    # ── Top teams by win % (decided matches only) ──
    # `decided` = matches with an outcome_winner (excludes ties/NR).
    # win_pct ranks teams; secondary sort by `played` so a 100%-win 2-
    # game team doesn't outrank a 60%-win 500-game team.
    top_teams_rows = await db.q(
        f"""
        WITH sides AS (
          SELECT m.team1 AS team, m.id AS match_id,
                 m.outcome_winner, m.outcome_result
          FROM match m WHERE {where}
          UNION ALL
          SELECT m.team2, m.id, m.outcome_winner, m.outcome_result
          FROM match m WHERE {where}
        )
        SELECT team,
               COUNT(*) AS played,
               SUM(CASE WHEN outcome_winner = team THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN outcome_winner IS NOT NULL
                          AND outcome_winner != team THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN outcome_winner IS NOT NULL THEN 1 ELSE 0 END) AS decided
        FROM sides
        GROUP BY team
        HAVING played >= 5
        ORDER BY (CAST(SUM(CASE WHEN outcome_winner = team THEN 1 ELSE 0 END) AS REAL)
                  / NULLIF(SUM(CASE WHEN outcome_winner IS NOT NULL THEN 1 ELSE 0 END), 0)) DESC,
                 played DESC
        LIMIT 10
        """,
        params,
    )
    top_teams = [
        {
            "team": r["team"],
            "played": r["played"] or 0,
            "wins": r["wins"] or 0,
            "losses": r["losses"] or 0,
            "win_pct": _safe_div(r["wins"] or 0, r["decided"] or 0, 100, 1),
        }
        for r in top_teams_rows
    ]

    # ── Best moments — singleton from each record axis ──
    # Highest team total (innings-level)
    ht_rows = await db.q(
        f"""
        SELECT i.team, tot.total AS runs,
               m.id AS match_id, m.season AS season, m.event_name AS tournament,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM (
          SELECT d.innings_id, SUM(d.runs_total) AS total
          FROM delivery d
          GROUP BY d.innings_id
        ) tot
        JOIN innings i ON i.id = tot.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}{inn_clause}
        ORDER BY tot.total DESC
        LIMIT 1
        """,
        params,
    )
    highest_total = None
    if ht_rows:
        r = ht_rows[0]
        highest_total = {
            "team": r["team"], "runs": r["runs"],
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"], "opponent": r["opponent"],
            "date": r["date"],
        }

    # Lowest all-out total (10 wickets fell)
    lo_rows = await db.q(
        f"""
        WITH innings_totals AS (
          SELECT d.innings_id, SUM(d.runs_total) AS total,
                 (SELECT COUNT(*) FROM wicket w
                  JOIN delivery d2 ON d2.id = w.delivery_id
                  WHERE d2.innings_id = d.innings_id
                    AND w.kind NOT IN ('retired hurt', 'retired not out')) AS wkts
          FROM delivery d
          GROUP BY d.innings_id
        )
        SELECT i.team, it.total AS runs,
               m.id AS match_id, m.season AS season, m.event_name AS tournament,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM innings_totals it
        JOIN innings i ON i.id = it.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND it.wkts >= 10 AND {where}{inn_clause}
        ORDER BY it.total ASC
        LIMIT 1
        """,
        params,
    )
    lowest_all_out = None
    if lo_rows:
        r = lo_rows[0]
        lowest_all_out = {
            "team": r["team"], "runs": r["runs"],
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"], "opponent": r["opponent"],
            "date": r["date"],
        }

    # Biggest win by runs
    bwr_rows = await db.q(
        f"""
        SELECT m.outcome_winner AS winner,
               CASE WHEN m.team1 = m.outcome_winner THEN m.team2 ELSE m.team1 END AS loser,
               m.outcome_by_runs AS margin,
               m.id AS match_id, m.season AS season, m.event_name AS tournament,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where} AND m.outcome_by_runs IS NOT NULL
        ORDER BY m.outcome_by_runs DESC
        LIMIT 1
        """,
        params,
    )
    biggest_win_runs = None
    if bwr_rows:
        r = bwr_rows[0]
        biggest_win_runs = {
            "winner": r["winner"], "loser": r["loser"], "margin": r["margin"],
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"], "date": r["date"],
        }

    # Biggest win by wickets
    bww_rows = await db.q(
        f"""
        SELECT m.outcome_winner AS winner,
               CASE WHEN m.team1 = m.outcome_winner THEN m.team2 ELSE m.team1 END AS loser,
               m.outcome_by_wickets AS margin,
               m.id AS match_id, m.season AS season, m.event_name AS tournament,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where} AND m.outcome_by_wickets IS NOT NULL
        ORDER BY m.outcome_by_wickets DESC, m.outcome_by_runs ASC
        LIMIT 1
        """,
        params,
    )
    biggest_win_wickets = None
    if bww_rows:
        r = bww_rows[0]
        biggest_win_wickets = {
            "winner": r["winner"], "loser": r["loser"], "margin": r["margin"],
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"], "date": r["date"],
        }

    # Most sixes in a match
    ms_rows = await db.q(
        f"""
        SELECT m.id AS match_id, m.season AS season, m.event_name AS tournament,
               m.team1, m.team2,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}{inn_clause}
        GROUP BY m.id
        ORDER BY sixes DESC
        LIMIT 1
        """,
        params,
    )
    most_sixes_match = None
    if ms_rows:
        r = ms_rows[0]
        most_sixes_match = {
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"],
            "team1": r["team1"], "team2": r["team2"],
            "sixes": r["sixes"] or 0,
            "date": r["date"],
        }

    return {
        "matches": meta["matches"] or 0,
        "innings": innings,
        "teams_count": teams_count,
        "tournaments_count": meta["tournaments"] or 0,
        "top_teams": top_teams,
        "best_moments": {
            "highest_total": highest_total,
            "lowest_all_out": lowest_all_out,
            "biggest_win_runs": biggest_win_runs,
            "biggest_win_wickets": biggest_win_wickets,
            "most_sixes_match": most_sixes_match,
        },
    }


# ─── /league/champions ─────────────────────────────────────────────────

@router.get("/champions")
async def league_champions(
    filters: FilterParams = Depends(),
):
    """Cross-tournament Champions table.

    Returns one row per (season, tournament) Final played in scope —
    the unioned version of `/series/by-season`'s `finals_rows` slice
    that drives a single tournament's per-edition champion column.

    Sort: season DESC, then tournament. Frontend DataTable can re-sort
    by column. Bilateral series (event_name IS NULL) and unfinaled
    seasons (no event_stage='Final' yet) are omitted.
    """
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament=None)

    # Match the same scalar-subquery pattern as /series/by-season →
    # `finals_rows` for the score breakdown; the only structural
    # difference is the unrestricted tournament so we keep
    # m.event_name in SELECT for the response.
    rows = await db.q(
        f"""
        SELECT m.season, m.event_name AS tournament, m.id AS match_id,
               m.outcome_winner AS winner,
               m.team1, m.team2,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date,
               (SELECT COALESCE(SUM(d.runs_total), 0)
                  FROM innings i JOIN delivery d ON d.innings_id = i.id
                 WHERE i.match_id = m.id AND i.team = m.team1 AND i.super_over = 0) AS t1_runs,
               (SELECT COUNT(*) FROM wicket w
                  JOIN delivery d ON d.id = w.delivery_id
                  JOIN innings i ON i.id = d.innings_id
                 WHERE i.match_id = m.id AND i.team = m.team1 AND i.super_over = 0) AS t1_wkts,
               (SELECT COALESCE(SUM(d.runs_total), 0)
                  FROM innings i JOIN delivery d ON d.innings_id = i.id
                 WHERE i.match_id = m.id AND i.team = m.team2 AND i.super_over = 0) AS t2_runs,
               (SELECT COUNT(*) FROM wicket w
                  JOIN delivery d ON d.id = w.delivery_id
                  JOIN innings i ON i.id = d.innings_id
                 WHERE i.match_id = m.id AND i.team = m.team2 AND i.super_over = 0) AS t2_wkts,
               (SELECT COUNT(*) FROM innings i
                 WHERE i.match_id = m.id AND i.team = m.team1 AND i.super_over = 0) AS t1_has,
               (SELECT COUNT(*) FROM innings i
                 WHERE i.match_id = m.id AND i.team = m.team2 AND i.super_over = 0) AS t2_has
        FROM match m
        WHERE {where}
          AND m.event_stage = 'Final'
          AND m.outcome_winner IS NOT NULL
          AND m.event_name IS NOT NULL
        ORDER BY m.season DESC, m.event_name
        """,
        params,
    )
    out = []
    for r in rows:
        runner_up = r["team1"] if r["winner"] == r["team2"] else r["team2"]
        t1_score = f"{r['t1_runs']}/{r['t1_wkts']}" if r["t1_has"] else None
        t2_score = f"{r['t2_runs']}/{r['t2_wkts']}" if r["t2_has"] else None
        out.append({
            "season": r["season"],
            "tournament": r["tournament"],
            "champion": r["winner"],
            "runner_up": runner_up,
            "final_match_id": r["match_id"],
            "final_team1": r["team1"],
            "final_team2": r["team2"],
            "final_team1_score": t1_score,
            "final_team2_score": t2_score,
            "date": r["date"],
        })
    return {"rows": out}


# ─── /league/leaders/{batting,bowling,fielding} ────────────────────────
#
# Each mirrors the /series/{discipline}-leaders shape (same by_runs /
# by_average / by_strike_rate keys for batting etc.) but with NO
# tournament restriction. Pagination support — leader pools at league
# grain are much larger than any single tournament. The fetch picks
# top-N from each axis per page (offset…offset+limit).
#
# Cricket invariants honoured per CLAUDE.md:
#   - Convention 3 (catches INCLUDE caught_and_bowled) — fielding
#     predicate uses `kind IN ('caught', 'caught_and_bowled')`.
#   - Substitute fielders INCLUDED on /leaders (volume framing
#     matches /fielders/leaders semantic; the asymmetry vs
#     /distribution is intentional and codified — see
#     `how-stats-calculated.md`).


@router.get("/leaders/batting")
async def league_batters_leaders(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_balls: int = Query(1, ge=1),
    min_dismissals: int = Query(0, ge=0),
):
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament=None)
    inn_clause, inn_params = _inning_extras(aux)
    params.update(inn_params)

    agg_rows = await db.q(
        f"""
        SELECT d.batter_id AS person_id,
               SUM(d.runs_batter) AS runs,
               COUNT(*) AS balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY d.batter_id
        HAVING COUNT(*) >= :min_balls
        """,
        {**params, "min_balls": min_balls},
    )
    dism_rows = await db.q(
        f"""
        SELECT w.player_out_id AS person_id, COUNT(*) AS dismissals
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE w.player_out_id IS NOT NULL
          AND w.kind NOT IN ('retired hurt', 'retired out')
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY w.player_out_id
        """,
        params,
    )
    dism_map = {r["person_id"]: r["dismissals"] or 0 for r in dism_rows}

    entries: list[dict] = []
    for r in agg_rows:
        pid = r["person_id"]
        runs = r["runs"] or 0
        balls = r["balls"] or 0
        dism = dism_map.get(pid, 0)
        entries.append({
            "person_id": pid,
            "runs": runs,
            "balls": balls,
            "dismissals": dism,
            "average": _safe_div(runs, dism) if dism > 0 else None,
            "strike_rate": _safe_div(runs, balls, 100),
        })

    runs_top = sorted(
        entries,
        key=lambda e: (e["runs"], -e["balls"]), reverse=True,
    )[offset:offset + limit]
    avg_top = sorted(
        (e for e in entries if e["dismissals"] >= min_dismissals and e["average"] is not None),
        key=lambda e: (e["average"], e["runs"]), reverse=True,
    )[offset:offset + limit]
    sr_top = sorted(
        (e for e in entries if e["strike_rate"] is not None),
        key=lambda e: (e["strike_rate"], e["runs"]), reverse=True,
    )[offset:offset + limit]

    top_ids = (
        {e["person_id"] for e in runs_top}
        | {e["person_id"] for e in avg_top}
        | {e["person_id"] for e in sr_top}
    )
    name_map = await _name_map(db, top_ids)
    team_map = await _batter_team_map(
        db, where, inn_clause, params, top_ids,
    )
    for axis in (runs_top, avg_top, sr_top):
        for e in axis:
            e["name"] = name_map.get(e["person_id"], e["person_id"])
            e["team"] = team_map.get(e["person_id"])

    return {
        "by_runs": runs_top,
        "by_average": avg_top,
        "by_strike_rate": sr_top,
        "thresholds": {"min_balls": min_balls, "min_dismissals": min_dismissals},
        "limit": limit, "offset": offset,
    }


@router.get("/leaders/bowling")
async def league_bowlers_leaders(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_balls: int = Query(1, ge=1),
    min_wickets: int = Query(0, ge=0),
):
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament=None)
    inn_clause, inn_params = _inning_extras(aux)
    params.update(inn_params)

    agg_rows = await db.q(
        f"""
        SELECT d.bowler_id AS person_id,
               SUM(d.runs_total) AS runs,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.bowler_id IS NOT NULL
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY d.bowler_id
        HAVING balls >= :min_balls
        """,
        {**params, "min_balls": min_balls},
    )
    wkt_rows = await db.q(
        f"""
        SELECT d.bowler_id AS person_id, COUNT(*) AS wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.bowler_id IS NOT NULL
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY d.bowler_id
        """,
        params,
    )
    wkt_map = {r["person_id"]: r["wickets"] or 0 for r in wkt_rows}

    entries: list[dict] = []
    for r in agg_rows:
        pid = r["person_id"]
        runs = r["runs"] or 0
        balls = r["balls"] or 0
        wickets = wkt_map.get(pid, 0)
        entries.append({
            "person_id": pid,
            "runs": runs,
            "balls": balls,
            "wickets": wickets,
            "economy": _safe_div(runs, balls, 6),
            "strike_rate": _safe_div(balls, wickets) if wickets > 0 else None,
        })

    wickets_top = sorted(
        entries,
        key=lambda e: (e["wickets"], -(e["economy"] or 0)), reverse=True,
    )[offset:offset + limit]
    sr_top = sorted(
        (e for e in entries if e["wickets"] >= min_wickets and e["strike_rate"] is not None),
        key=lambda e: (e["strike_rate"], -e["wickets"]),
    )[offset:offset + limit]
    econ_top = sorted(
        (e for e in entries if e["economy"] is not None),
        key=lambda e: (e["economy"], -e["balls"]),
    )[offset:offset + limit]

    top_ids = (
        {e["person_id"] for e in wickets_top}
        | {e["person_id"] for e in sr_top}
        | {e["person_id"] for e in econ_top}
    )
    name_map = await _name_map(db, top_ids)
    team_map = await _bowler_team_map(
        db, where, inn_clause, params, top_ids,
    )
    for axis in (wickets_top, sr_top, econ_top):
        for e in axis:
            e["name"] = name_map.get(e["person_id"], e["person_id"])
            e["team"] = team_map.get(e["person_id"])

    return {
        "by_wickets": wickets_top,
        "by_strike_rate": sr_top,
        "by_economy": econ_top,
        "thresholds": {"min_balls": min_balls, "min_wickets": min_wickets},
        "limit": limit, "offset": offset,
    }


@router.get("/leaders/fielding")
async def league_fielders_leaders(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament=None)
    inn_clause, inn_params = _inning_extras(aux)
    params.update(inn_params)
    params["lim"] = limit
    params["off"] = offset

    # Volume framing — substitute fielders INCLUDED (mirrors
    # /fielders/leaders + /series/fielders-leaders). The /distribution
    # endpoints apply is_substitute=0 for per-match rate calibration;
    # /leaders does not. Codified in CLAUDE.md "Substitute fielders —
    # INCLUDED in /leaders, EXCLUDED in /distribution".
    #
    # Convention 3: catches INCLUDES caught_and_bowled.
    disp_rows = await db.q(
        f"""
        SELECT fc.fielder_id AS person_id,
               COUNT(*) AS total,
               SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled')
                        THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
               SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs,
               SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) AS c_and_b
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id IS NOT NULL
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY fc.fielder_id
        ORDER BY total DESC
        LIMIT :lim OFFSET :off
        """,
        params,
    )
    run_out_rows = await db.q(
        f"""
        SELECT fc.fielder_id AS person_id,
               COUNT(*) AS total,
               SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled')
                        THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
               SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs,
               SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) AS c_and_b
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id IS NOT NULL
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY fc.fielder_id
        HAVING run_outs > 0
        ORDER BY run_outs DESC, total DESC
        LIMIT :lim OFFSET :off
        """,
        params,
    )
    keeper_rows = await db.q(
        f"""
        SELECT ka.keeper_id AS person_id,
               SUM(CASE WHEN fc.kind IN ('caught','stumped') THEN 1 ELSE 0 END) AS total,
               SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled')
                        THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN delivery d ON d.innings_id = i.id
        JOIN fieldingcredit fc ON fc.delivery_id = d.id
          AND fc.fielder_id = ka.keeper_id
        WHERE ka.keeper_id IS NOT NULL
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY ka.keeper_id
        HAVING total > 0
        ORDER BY total DESC
        LIMIT :lim OFFSET :off
        """,
        params,
    )

    top_ids = (
        {r["person_id"] for r in disp_rows}
        | {r["person_id"] for r in run_out_rows}
        | {r["person_id"] for r in keeper_rows}
    )
    name_map = await _name_map(db, top_ids)
    team_map = await _fielder_team_map(
        db, where, inn_clause, params, top_ids,
    )

    def _pack(rows):
        out = []
        for r in rows:
            d = dict(r)
            d["name"] = name_map.get(d["person_id"], d["person_id"])
            d["team"] = team_map.get(d["person_id"])
            out.append(d)
        return out

    return {
        "by_dismissals": _pack(disp_rows),
        "by_keeper_dismissals": _pack(keeper_rows),
        "by_run_outs": _pack(run_out_rows),
        "limit": limit, "offset": offset,
    }


# ─── helpers — name + dominant-team maps ──────────────────────────────


async def _name_map(db, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    placeholders = ",".join(f":n{i}" for i in range(len(ids)))
    params = {f"n{i}": pid for i, pid in enumerate(ids)}
    rows = await db.q(
        f"SELECT id, name FROM person WHERE id IN ({placeholders})",
        params,
    )
    return {r["id"]: r["name"] for r in rows}


async def _batter_team_map(
    db, where: str, inn_clause: str, scope_params: dict, ids: set[str],
) -> dict[str, str]:
    if not ids:
        return {}
    placeholders = ",".join(f":n{i}" for i in range(len(ids)))
    name_params = {f"n{i}": pid for i, pid in enumerate(ids)}
    rows = await db.q(
        f"""
        SELECT d.batter_id AS pid, i.team AS team, COUNT(*) AS n
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.batter_id IN ({placeholders})
          AND d.extras_wides = 0 AND d.extras_noballs = 0
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY d.batter_id, i.team
        """,
        {**scope_params, **name_params},
    )
    return _dominant_team(rows)


async def _bowler_team_map(
    db, where: str, inn_clause: str, scope_params: dict, ids: set[str],
) -> dict[str, str]:
    if not ids:
        return {}
    placeholders = ",".join(f":n{i}" for i in range(len(ids)))
    name_params = {f"n{i}": pid for i, pid in enumerate(ids)}
    rows = await db.q(
        f"""
        SELECT d.bowler_id AS pid,
               CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END AS team,
               COUNT(*) AS n
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.bowler_id IN ({placeholders})
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY d.bowler_id, team
        """,
        {**scope_params, **name_params},
    )
    return _dominant_team(rows)


async def _fielder_team_map(
    db, where: str, inn_clause: str, scope_params: dict, ids: set[str],
) -> dict[str, str]:
    if not ids:
        return {}
    placeholders = ",".join(f":n{i}" for i in range(len(ids)))
    name_params = {f"n{i}": pid for i, pid in enumerate(ids)}
    rows = await db.q(
        f"""
        SELECT fc.fielder_id AS pid,
               CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END AS team,
               COUNT(*) AS n
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id IN ({placeholders})
          AND i.super_over = 0 AND {where}{inn_clause}
        GROUP BY fc.fielder_id, team
        """,
        {**scope_params, **name_params},
    )
    return _dominant_team(rows)


def _dominant_team(rows) -> dict[str, str]:
    """Per-pid dominant team — the team with the largest sample count."""
    per_pid: dict[str, tuple[str, int]] = {}
    for r in rows:
        pid, team, n = r["pid"], r["team"], r["n"] or 0
        if pid not in per_pid or n > per_pid[pid][1]:
            per_pid[pid] = (team, n)
    return {pid: v[0] for pid, v in per_pid.items()}
