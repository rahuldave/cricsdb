"""Batting analytics router."""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams, AuxParams
from ..aux_clauses import splice_aux_join_clauses
from ..player_nationality import player_nationalities
from ..scope_links import suggested_splits, scope_dict_from_filters

router = APIRouter(prefix="/api/v1/batters", tags=["Batting"])


def _safe_div(a, b, mul=1, ndigits=2):
    """Safe division returning None on zero denominator."""
    if not b:
        return None
    return round(a * mul / b, ndigits)


def _batting_filter(filters: FilterParams, person_id: str, bowler_id: str | None = None, aux: AuxParams | None = None):
    """Build WHERE clause for batting delivery queries."""
    where, params = filters.build(has_innings_join=True, aux=aux)
    params["person_id"] = person_id
    parts = ["d.batter_id = :person_id", "d.extras_wides = 0", "d.extras_noballs = 0"]
    if where:
        parts.append(where)
    if bowler_id:
        parts.append("d.bowler_id = :bowler_id")
        params["bowler_id"] = bowler_id
    return " AND ".join(parts), params


@router.get("/leaders")
async def batting_leaders(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(10, ge=1, le=50),
    min_balls: int = Query(100, ge=1),
    min_dismissals: int = Query(3, ge=0),
):
    """Top batters in the current filter scope.

    Returns two leaderboards:
      - by_average: filtered to `min_balls` + `min_dismissals`, sorted
        by runs/dismissals (DESC). Excludes tiny-sample "never out"
        inflations.
      - by_strike_rate: filtered to `min_balls`, sorted by
        runs × 100 / balls (DESC). No dismissal requirement — SR is
        a per-ball measure.

    Tiebreak by total runs (DESC) so within equal rates, the higher-
    volume batter surfaces.

    Perf note: When no match-level filter is active we skip the
    innings/match JOINs entirely — scanning the delivery table by
    batter_id index is ~100× faster than joining row-by-row to match.
    The trade-off is super-over deliveries (0.04% of 2.95M) leak into
    the no-filter leaderboard, which is imperceptible given the
    thresholds.
    """
    db = get_db()
    # has_innings_join=False keeps `match_where` empty when truly
    # unfiltered → bare-delivery fast path engages (~100× faster).
    # Aux-narrowings (e.g. inning) are gated inside `filters.build`
    # because they reference aliases that aren't always in scope,
    # so we splice them via the JOIN_CLAUSES registry on the
    # JOIN-branch SQL (where the aliases ARE in scope).
    # Adding a new aux narrowing → register a new JoinClause; no
    # change required here.
    match_where, params = filters.build(has_innings_join=False, aux=aux)
    aux_extra = splice_aux_join_clauses(aux, params)
    has_filters = bool(match_where) or bool(aux_extra)

    if has_filters:
        # match_where may be empty if only an aux narrowing is set
        # — `1=1` keeps the trailing AND chain valid.
        m_where = match_where if match_where else "1=1"
        agg_sql = f"""
            SELECT d.batter_id AS person_id,
                   SUM(d.runs_batter) AS runs,
                   COUNT(*) AS balls
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE d.batter_id IS NOT NULL
              AND d.extras_wides = 0 AND d.extras_noballs = 0
              AND {m_where}{aux_extra}
            GROUP BY d.batter_id
            HAVING COUNT(*) >= :min_balls
        """
        dism_sql = f"""
            SELECT w.player_out_id AS person_id, COUNT(*) AS dismissals
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE w.player_out_id IS NOT NULL
              AND w.kind NOT IN ('retired hurt', 'retired out')
              AND {m_where}{aux_extra}
            GROUP BY w.player_out_id
        """
    else:
        agg_sql = """
            SELECT d.batter_id AS person_id,
                   SUM(d.runs_batter) AS runs,
                   COUNT(*) AS balls
            FROM delivery d
            WHERE d.batter_id IS NOT NULL
              AND d.extras_wides = 0 AND d.extras_noballs = 0
            GROUP BY d.batter_id
            HAVING COUNT(*) >= :min_balls
        """
        dism_sql = """
            SELECT w.player_out_id AS person_id, COUNT(*) AS dismissals
            FROM wicket w
            WHERE w.player_out_id IS NOT NULL
              AND w.kind NOT IN ('retired hurt', 'retired out')
            GROUP BY w.player_out_id
        """

    agg_rows = await db.q(agg_sql, {**params, "min_balls": min_balls})
    dism_rows = await db.q(dism_sql, params)
    dism_map = {r["person_id"]: r["dismissals"] or 0 for r in dism_rows}

    # Rank in Python, then only fetch names for the ~20 survivors
    # (top 10 avg + top 10 SR, possibly overlapping). Avoids a
    # thousand-element IN-clause for name lookup.
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

    avg_top = sorted(
        (e for e in entries if e["dismissals"] >= min_dismissals and e["average"] is not None),
        key=lambda e: (e["average"], e["runs"]),
        reverse=True,
    )[:limit]
    sr_top = sorted(
        (e for e in entries if e["strike_rate"] is not None),
        key=lambda e: (e["strike_rate"], e["runs"]),
        reverse=True,
    )[:limit]

    top_ids = {e["person_id"] for e in avg_top} | {e["person_id"] for e in sr_top}
    name_map: dict[str, str] = {}
    if top_ids:
        placeholders = ",".join(f":n{i}" for i in range(len(top_ids)))
        name_params = {f"n{i}": pid for i, pid in enumerate(top_ids)}
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({placeholders})",
            name_params,
        )
        name_map = {r["id"]: r["name"] for r in name_rows}
    for e in avg_top:
        e["name"] = name_map.get(e["person_id"], e["person_id"])
    for e in sr_top:
        e["name"] = name_map.get(e["person_id"], e["person_id"])

    return {
        "by_average": avg_top,
        "by_strike_rate": sr_top,
        "thresholds": {
            "min_balls": min_balls,
            "min_dismissals": min_dismissals,
        },
    }


def _enrich_batting_row(r: dict) -> dict:
    """Add computed metrics to a batting aggregation row."""
    balls = r.get("balls") or 0
    runs = r.get("runs") or 0
    fours = r.get("fours") or 0
    sixes = r.get("sixes") or 0
    dots = r.get("dots") or 0
    dismissals = r.get("dismissals") or 0
    boundaries = fours + sixes

    r["boundaries"] = boundaries
    r["strike_rate"] = _safe_div(runs, balls, 100)
    r["average"] = _safe_div(runs, dismissals)
    r["dot_pct"] = _safe_div(dots, balls, 100, 1)
    r["boundary_pct"] = _safe_div(boundaries, balls, 100, 1)
    r["balls_per_four"] = _safe_div(balls, fours) if fours else None
    r["balls_per_six"] = _safe_div(balls, sixes) if sixes else None
    r["balls_per_boundary"] = _safe_div(balls, boundaries) if boundaries else None
    return r


@router.get("/{person_id}/summary")
async def batting_summary(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    bowler_id: Optional[str] = Query(None),
):
    db = get_db()

    # Get player name
    name_rows = await db.q(
        "SELECT name FROM person WHERE id = :pid", {"pid": person_id}
    )
    name = name_rows[0]["name"] if name_rows else person_id

    where, params = _batting_filter(filters, person_id, bowler_id, aux=aux)

    # Core ball-level aggregation (legal balls only)
    core = await db.q(
        f"""
        SELECT
            COUNT(*) as balls_faced,
            SUM(d.runs_batter) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    c = core[0] if core else {}

    # Per-innings stats (for highest, 50s, 100s, ducks, not-outs, innings count)
    inn_where = where  # same filters
    innings_rows = await db.q(
        f"""
        SELECT
            i.match_id,
            i.innings_number,
            SUM(d.runs_batter) as innings_runs,
            COUNT(*) as innings_balls,
            MAX(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) as was_dismissed
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.player_out_id = :person_id
            AND w.kind NOT IN ('retired hurt', 'retired out')
        WHERE {inn_where}
        GROUP BY i.match_id, i.innings_number
        """,
        params,
    )

    innings_count = len(innings_rows)
    runs = c.get("runs") or 0
    balls = c.get("balls_faced") or 0
    fours = c.get("fours") or 0
    sixes = c.get("sixes") or 0
    dots = c.get("dots") or 0
    boundaries = fours + sixes

    not_outs = sum(1 for r in innings_rows if not r["was_dismissed"])
    dismissals = innings_count - not_outs
    highest = max((r["innings_runs"] for r in innings_rows), default=0)
    hundreds = sum(1 for r in innings_rows if (r["innings_runs"] or 0) >= 100)
    fifties = sum(1 for r in innings_rows if 50 <= (r["innings_runs"] or 0) < 100)
    thirties = sum(1 for r in innings_rows if 30 <= (r["innings_runs"] or 0) < 50)
    ducks = sum(
        1 for r in innings_rows
        if (r["innings_runs"] or 0) == 0 and r["was_dismissed"]
    )

    matches_count = len({r["match_id"] for r in innings_rows})
    nationalities = await player_nationalities(db, person_id)

    return {
        "person_id": person_id,
        "name": name,
        "nationalities": nationalities,
        "matches": matches_count,
        "innings": innings_count,
        "runs": runs,
        "balls_faced": balls,
        "not_outs": not_outs,
        "dismissals": dismissals,
        "average": _safe_div(runs, dismissals),
        "strike_rate": _safe_div(runs, balls, 100),
        "highest_score": highest,
        "hundreds": hundreds,
        "fifties": fifties,
        "thirties": thirties,
        "ducks": ducks,
        "fours": fours,
        "sixes": sixes,
        "boundaries": boundaries,
        "dots": dots,
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "balls_per_four": _safe_div(balls, fours),
        "balls_per_six": _safe_div(balls, sixes),
        "balls_per_boundary": _safe_div(balls, boundaries),
    }


@router.get("/{person_id}/by-innings")
async def batting_by_innings(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    bowler_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("date"),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, bowler_id, aux=aux)
    params["limit"] = limit
    params["offset"] = offset

    sort_map = {
        "date": "date DESC",
        "runs": "runs DESC",
        "strike_rate": "strike_rate DESC",
    }
    order = sort_map.get(sort, "date DESC")

    # Count total
    count_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.match_id || '-' || i.innings_number) as total
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    total = count_rows[0]["total"] if count_rows else 0

    rows = await db.q(
        f"""
        SELECT
            i.match_id,
            (SELECT md.date FROM matchdate md WHERE md.match_id = i.match_id
             ORDER BY md.date LIMIT 1) as date,
            i.team,
            CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END as opponent,
            m.venue,
            m.event_name as tournament,
            SUM(d.runs_batter) as runs,
            COUNT(*) as balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            ROUND(SUM(d.runs_batter) * 100.0 / COUNT(*), 2) as strike_rate,
            MAX(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) as was_out,
            MAX(w.kind) as how_out,
            MAX(CASE WHEN w.id IS NOT NULL THEN d.bowler ELSE NULL END) as dismissed_by
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.player_out_id = :person_id
            AND w.kind NOT IN ('retired hurt', 'retired out')
        WHERE {where}
        GROUP BY i.match_id, i.innings_number
        ORDER BY {order}
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    innings = []
    for r in rows:
        innings.append({
            "match_id": r["match_id"],
            "date": r["date"],
            "team": r["team"],
            "opponent": r["opponent"],
            "venue": r["venue"],
            "tournament": r["tournament"],
            "runs": r["runs"],
            "balls": r["balls"],
            "fours": r["fours"],
            "sixes": r["sixes"],
            "strike_rate": r["strike_rate"],
            "not_out": not r["was_out"],
            "how_out": r["how_out"] if r["was_out"] else None,
            "dismissed_by": r["dismissed_by"] if r["was_out"] else None,
        })

    return {"innings": innings, "total": total}


@router.get("/{person_id}/vs-bowlers")
async def batting_vs_bowlers(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    bowler_id: Optional[str] = Query(None),
    min_balls: int = Query(6, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("balls"),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, bowler_id, aux=aux)
    params["min_balls"] = min_balls
    params["limit"] = limit

    sort_map = {
        "balls": "balls DESC",
        "runs": "runs DESC",
        "strike_rate": "strike_rate DESC",
        "dismissals": "dismissals DESC",
    }
    order = sort_map.get(sort, "balls DESC")

    # Ball-level stats
    rows = await db.q(
        f"""
        SELECT
            d.bowler_id,
            d.bowler as bowler_name,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY d.bowler_id
        HAVING COUNT(*) >= :min_balls
        ORDER BY balls DESC
        LIMIT :limit
        """,
        params,
    )

    # Dismissals by bowler
    dismiss_where, dismiss_params = filters.build(has_innings_join=True, aux=aux)
    dismiss_params["person_id"] = person_id
    dismiss_parts = [
        "w.player_out_id = :person_id",
        "w.kind NOT IN ('retired hurt', 'retired out')",
    ]
    if dismiss_where:
        dismiss_parts.append(dismiss_where)
    if bowler_id:
        dismiss_parts.append("d.bowler_id = :bowler_id")
        dismiss_params["bowler_id"] = bowler_id
    dismiss_clause = " AND ".join(dismiss_parts)

    dismiss_rows = await db.q(
        f"""
        SELECT d.bowler_id, COUNT(*) as dismissals
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {dismiss_clause}
        GROUP BY d.bowler_id
        """,
        dismiss_params,
    )
    dismiss_map = {r["bowler_id"]: r["dismissals"] for r in dismiss_rows}

    matchups = []
    for r in rows:
        r["dismissals"] = dismiss_map.get(r["bowler_id"], 0)
        _enrich_batting_row(r)
        matchups.append(r)

    # Re-sort if sorting by dismissals (which was computed after the query)
    if sort == "dismissals":
        matchups.sort(key=lambda x: x.get("dismissals", 0), reverse=True)

    return {"matchups": matchups}


@router.get("/{person_id}/by-over")
async def batting_by_over(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    bowler_id: Optional[str] = Query(None),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, bowler_id, aux=aux)

    rows = await db.q(
        f"""
        SELECT
            d.over_number,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY d.over_number
        ORDER BY d.over_number
        """,
        params,
    )

    # Dismissals per over
    dismiss_where, dismiss_params = filters.build(has_innings_join=True, aux=aux)
    dismiss_params["person_id"] = person_id
    dismiss_parts = [
        "w.player_out_id = :person_id",
        "w.kind NOT IN ('retired hurt', 'retired out')",
    ]
    if dismiss_where:
        dismiss_parts.append(dismiss_where)
    if bowler_id:
        dismiss_parts.append("d.bowler_id = :bowler_id")
        dismiss_params["bowler_id"] = bowler_id
    dismiss_clause = " AND ".join(dismiss_parts)

    dismiss_rows = await db.q(
        f"""
        SELECT d.over_number, COUNT(*) as dismissals
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {dismiss_clause}
        GROUP BY d.over_number
        """,
        dismiss_params,
    )
    dismiss_map = {r["over_number"]: r["dismissals"] for r in dismiss_rows}

    by_over = []
    for r in rows:
        r["dismissals"] = dismiss_map.get(r["over_number"], 0)
        r["over_number"] = r["over_number"] + 1  # display as 1-20
        _enrich_batting_row(r)
        by_over.append(r)

    return {"by_over": by_over}


@router.get("/{person_id}/by-phase")
async def batting_by_phase(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    bowler_id: Optional[str] = Query(None),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, bowler_id, aux=aux)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY phase
        ORDER BY MIN(d.over_number)
        """,
        params,
    )

    # Dismissals per phase
    dismiss_where, dismiss_params = filters.build(has_innings_join=True, aux=aux)
    dismiss_params["person_id"] = person_id
    dismiss_parts = [
        "w.player_out_id = :person_id",
        "w.kind NOT IN ('retired hurt', 'retired out')",
    ]
    if dismiss_where:
        dismiss_parts.append(dismiss_where)
    if bowler_id:
        dismiss_parts.append("d.bowler_id = :bowler_id")
        dismiss_params["bowler_id"] = bowler_id
    dismiss_clause = " AND ".join(dismiss_parts)

    dismiss_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as dismissals
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {dismiss_clause}
        GROUP BY phase
        """,
        dismiss_params,
    )
    dismiss_map = {r["phase"]: r["dismissals"] for r in dismiss_rows}

    phase_labels = {"powerplay": "1-6", "middle": "7-15", "death": "16-20"}
    by_phase = []
    for r in rows:
        r["overs"] = phase_labels.get(r["phase"], "")
        r["dismissals"] = dismiss_map.get(r["phase"], 0)
        _enrich_batting_row(r)
        by_phase.append(r)

    return {"by_phase": by_phase}


@router.get("/{person_id}/by-season")
async def batting_by_season(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, aux=aux)

    # Ball-level stats by season
    rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )

    # Per-innings stats for 50s/100s/dismissals/innings count per season
    innings_rows = await db.q(
        f"""
        SELECT
            m.season,
            i.match_id,
            i.innings_number,
            SUM(d.runs_batter) as innings_runs,
            MAX(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) as was_dismissed
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.player_out_id = :person_id
            AND w.kind NOT IN ('retired hurt', 'retired out')
        WHERE {where}
        GROUP BY m.season, i.match_id, i.innings_number
        """,
        params,
    )

    # Build per-season innings aggregates
    from collections import defaultdict
    season_inn = defaultdict(list)
    for r in innings_rows:
        season_inn[r["season"]].append(r)

    by_season = []
    for r in rows:
        season = r["season"]
        inns = season_inn.get(season, [])
        innings_count = len(inns)
        dismissals = sum(1 for x in inns if x["was_dismissed"])
        fifties = sum(1 for x in inns if 50 <= (x["innings_runs"] or 0) < 100)
        hundreds = sum(1 for x in inns if (x["innings_runs"] or 0) >= 100)

        r["innings"] = innings_count
        r["dismissals"] = dismissals
        r["fifties"] = fifties
        r["hundreds"] = hundreds
        _enrich_batting_row(r)
        by_season.append(r)

    return {"by_season": by_season}


@router.get("/{person_id}/dismissals")
async def batting_dismissals(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    bowler_id: Optional[str] = Query(None),
):
    db = get_db()
    filt_where, filt_params = filters.build(has_innings_join=True, aux=aux)
    filt_params["person_id"] = person_id
    base_parts = [
        "w.player_out_id = :person_id",
        "w.kind NOT IN ('retired hurt', 'retired out')",
    ]
    if filt_where:
        base_parts.append(filt_where)
    if bowler_id:
        base_parts.append("d.bowler_id = :bowler_id")
        filt_params["bowler_id"] = bowler_id
    base_clause = " AND ".join(base_parts)

    # Total + by_kind
    kind_rows = await db.q(
        f"""
        SELECT w.kind, COUNT(*) as cnt
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        GROUP BY w.kind
        ORDER BY cnt DESC
        """,
        filt_params,
    )
    by_kind = {r["kind"]: r["cnt"] for r in kind_rows}
    total = sum(by_kind.values())

    # by_phase
    phase_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as dismissals
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        GROUP BY phase
        """,
        filt_params,
    )
    by_phase = {r["phase"]: r["dismissals"] for r in phase_rows}

    # by_over
    over_rows = await db.q(
        f"""
        SELECT d.over_number, COUNT(*) as dismissals
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        GROUP BY d.over_number
        ORDER BY d.over_number
        """,
        filt_params,
    )

    # top_bowlers
    bowler_rows = await db.q(
        f"""
        SELECT d.bowler_id, d.bowler as bowler_name, w.kind, COUNT(*) as cnt
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        GROUP BY d.bowler_id, w.kind
        ORDER BY cnt DESC
        """,
        filt_params,
    )
    from collections import defaultdict
    bowler_agg = defaultdict(lambda: {"dismissals": 0, "kinds": {}, "bowler_name": ""})
    for r in bowler_rows:
        bid = r["bowler_id"]
        bowler_agg[bid]["bowler_name"] = r["bowler_name"]
        bowler_agg[bid]["dismissals"] += r["cnt"]
        bowler_agg[bid]["kinds"][r["kind"]] = r["cnt"]

    top_bowlers = sorted(
        [{"bowler_id": k, **v} for k, v in bowler_agg.items()],
        key=lambda x: x["dismissals"],
        reverse=True,
    )[:10]

    for r in over_rows:
        r["over_number"] = r["over_number"] + 1  # display as 1-20

    return {
        "total_dismissals": total,
        "by_kind": by_kind,
        "by_phase": by_phase,
        "by_over": over_rows,
        "top_bowlers": top_bowlers,
    }


@router.get("/{person_id}/inter-wicket")
async def batting_inter_wicket(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = filters.build(has_innings_join=True, aux=aux)
    params["person_id"] = person_id

    filter_clause = f"d.batter_id = :person_id"
    if where:
        filter_clause += f" AND {where}"

    # Get all innings_ids where this batter batted
    innings_ids_rows = await db.q(
        f"""
        SELECT DISTINCT d.innings_id
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {filter_clause}
          AND d.extras_wides = 0 AND d.extras_noballs = 0
        """,
        params,
    )

    if not innings_ids_rows:
        return {"inter_wicket": []}

    innings_ids = [r["innings_id"] for r in innings_ids_rows]

    # Fetch all deliveries + wickets for those innings, ordered by id
    # Process in batches to avoid huge IN clauses
    from collections import defaultdict
    buckets = defaultdict(lambda: {
        "innings_set": set(),
        "balls": 0, "runs": 0, "fours": 0, "sixes": 0, "dots": 0,
        "dismissals": 0,
    })

    batch_size = 500
    for start in range(0, len(innings_ids), batch_size):
        batch = innings_ids[start:start + batch_size]
        placeholders = ",".join(str(iid) for iid in batch)

        # Get all deliveries in these innings with wicket info
        all_deliveries = await db.q(
            f"""
            SELECT d.id, d.innings_id, d.batter_id,
                   d.runs_batter, d.runs_extras,
                   d.extras_wides, d.extras_noballs,
                   d.runs_non_boundary,
                   w.id as wicket_id, w.player_out_id, w.kind
            FROM delivery d
            LEFT JOIN wicket w ON w.delivery_id = d.id
            WHERE d.innings_id IN ({placeholders})
            ORDER BY d.innings_id, d.id
            """
        )

        # Group by innings
        innings_deliveries = defaultdict(list)
        for d in all_deliveries:
            innings_deliveries[d["innings_id"]].append(d)

        for iid, deliveries in innings_deliveries.items():
            wickets_down = 0
            for d in deliveries:
                # If this delivery is faced by our batter (legal ball)
                if (
                    d["batter_id"] == person_id
                    and d["extras_wides"] == 0
                    and d["extras_noballs"] == 0
                ):
                    b = buckets[wickets_down]
                    b["innings_set"].add(iid)
                    b["balls"] += 1
                    b["runs"] += d["runs_batter"] or 0
                    if (
                        d["runs_batter"] == 4
                        and not d.get("runs_non_boundary")
                    ):
                        b["fours"] += 1
                    if d["runs_batter"] == 6:
                        b["sixes"] += 1
                    if (d["runs_batter"] or 0) == 0 and (d["runs_extras"] or 0) == 0:
                        b["dots"] += 1

                # Check if a wicket fell on this delivery (any kind except retired)
                if (
                    d["wicket_id"] is not None
                    and d["kind"] not in ("retired hurt", "retired out")
                ):
                    # If the batter was dismissed, count it in current bucket
                    if d["player_out_id"] == person_id:
                        buckets[wickets_down]["dismissals"] += 1
                    wickets_down += 1

    inter_wicket = []
    for wd in sorted(buckets.keys()):
        b = buckets[wd]
        balls = b["balls"]
        runs = b["runs"]
        fours = b["fours"]
        sixes = b["sixes"]
        boundaries = fours + sixes

        inter_wicket.append({
            "wickets_down": wd,
            "innings_count": len(b["innings_set"]),
            "balls": balls,
            "runs": runs,
            "fours": fours,
            "sixes": sixes,
            "strike_rate": _safe_div(runs, balls, 100),
            "dismissals": b["dismissals"],
            "dot_pct": _safe_div(b["dots"], balls, 100, 1),
            "balls_per_boundary": _safe_div(balls, boundaries) if boundaries else None,
        })

    return {"inter_wicket": inter_wicket}


# ─── Distribution dossier ──────────────────────────────────────────────
#
# Per-innings runs distribution for a batter, with phase decomposition,
# milestone probabilities, and last-10-innings + last-60-day form
# windows. Spec: internal_docs/spec-distribution-stats.md §8.
#
# The spec mentions three "retired" exclusions for the dismissed flag
# but existing batting endpoints exclude only ('retired hurt',
# 'retired out') — 'retired not out' is 13 rows in 162k wickets and
# materially irrelevant. We match the existing convention here for
# cross-endpoint consistency; revisit in a project-wide sweep if the
# semantic gap matters.

# Phase boundaries on the DB-side over_number (0-19). Mirrors the
# convention in /by-phase. PP=overs 1-6, Mid=7-15, Death=16-20 in
# user-facing 1-indexed numbering.
_PHASE_RANGES = {
    "powerplay": (0, 5),
    "middle": (6, 14),
    "death": (15, 19),
}


async def _innings_master_sample(
    db, person_id: str, filters: FilterParams, aux: AuxParams,
) -> list[dict]:
    """Materialise per-innings observation rows for a batter under the
    active filter scope. One row per (match, innings the batter batted
    in). Used as the master sample for the distribution dossier and
    its form windows. Spec §8.2."""
    where, params = _batting_filter(filters, person_id, aux=aux)
    rows = await db.q(
        f"""
        SELECT
            i.id AS innings_id,
            i.match_id,
            i.innings_number,
            (SELECT md.date FROM matchdate md WHERE md.match_id = i.match_id
             ORDER BY md.date LIMIT 1) AS date,
            SUM(d.runs_batter) AS runs,
            COUNT(*) AS balls,
            MAX(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS dismissed,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) AS fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
            SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) AS dots,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 5
                     THEN d.runs_batter ELSE 0 END) AS runs_pp,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 5
                     THEN 1 ELSE 0 END) AS balls_pp,
            SUM(CASE WHEN d.over_number BETWEEN 6 AND 14
                     THEN d.runs_batter ELSE 0 END) AS runs_mid,
            SUM(CASE WHEN d.over_number BETWEEN 6 AND 14
                     THEN 1 ELSE 0 END) AS balls_mid,
            SUM(CASE WHEN d.over_number BETWEEN 15 AND 19
                     THEN d.runs_batter ELSE 0 END) AS runs_death,
            SUM(CASE WHEN d.over_number BETWEEN 15 AND 19
                     THEN 1 ELSE 0 END) AS balls_death
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.player_out_id = :person_id
            AND w.kind NOT IN ('retired hurt', 'retired out')
        WHERE {where}
        GROUP BY i.id
        ORDER BY date ASC, i.innings_number ASC
        """,
        params,
    )
    return [
        {
            "innings_id": r["innings_id"],
            "match_id": r["match_id"],
            "date": r["date"],
            "runs": r["runs"] or 0,
            "balls": r["balls"] or 0,
            "dismissed": bool(r["dismissed"]),
            "fours": r["fours"] or 0,
            "sixes": r["sixes"] or 0,
            "dots": r["dots"] or 0,
            "runs_pp": r["runs_pp"] or 0,
            "balls_pp": r["balls_pp"] or 0,
            "runs_mid": r["runs_mid"] or 0,
            "balls_mid": r["balls_mid"] or 0,
            "runs_death": r["runs_death"] or 0,
            "balls_death": r["balls_death"] or 0,
        }
        for r in rows
    ]


def _distribution_dossier(observations: list[dict]) -> dict:
    """Pure aggregate of a per-innings observation list. No DB access.
    Same shape used for lifetime + form windows. Spec §8.3 / §8.4 / §8.5.

    Empty samples return a sane null shape — mean / median / variance /
    average / milestones all `null`; phase totals all 0; observations
    list empty.
    """
    n = len(observations)
    if n == 0:
        return {
            "n_innings": 0,
            "n_dismissals": 0,
            "n_notouts": 0,
            "runs": {
                "total": 0, "balls_total": 0,
                "mean_per_innings": None, "median": None,
                "variance": None, "std": None, "average": None,
                "observations": [],
            },
            "milestones": {
                "p_failure_10": None,
                "p_25_plus": None,
                "p_30_plus": None,
                "p_50_plus": None,
                "p_100_plus": None,
                "p_50_given_30": None,
                "p_70_given_50": None,
            },
            "phase": {
                k: {"runs_total": 0, "balls_total": 0, "innings_active": 0}
                for k in _PHASE_RANGES
            },
        }

    runs_list = [o["runs"] for o in observations]
    n_dismissals = sum(1 for o in observations if o["dismissed"])
    n_notouts = n - n_dismissals
    total_runs = sum(runs_list)
    total_balls = sum(o["balls"] for o in observations)

    mean_runs = total_runs / n
    median_runs = statistics.median(runs_list)
    # Sample variance needs n >= 2; for n == 1 fall back to 0.
    variance = statistics.variance(runs_list) if n >= 2 else 0.0
    std = variance ** 0.5
    average = (total_runs / n_dismissals) if n_dismissals > 0 else None

    def _count_geq(threshold: int) -> int:
        return sum(1 for r in runs_list if r >= threshold)

    def _p_geq(threshold: int) -> float:
        return _count_geq(threshold) / n

    def _p_leq(threshold: int) -> float:
        return sum(1 for r in runs_list if r <= threshold) / n

    def _p_cond(num_threshold: int, denom_threshold: int) -> Optional[float]:
        """Conditional probability P(runs ≥ num | runs ≥ denom). Null
        when no innings reached the denominator threshold (undefined)."""
        denom = _count_geq(denom_threshold)
        if denom == 0:
            return None
        return _count_geq(num_threshold) / denom

    phase = {}
    for name, (lo, hi) in _PHASE_RANGES.items():
        if name == "powerplay":
            runs_key, balls_key = "runs_pp", "balls_pp"
        elif name == "middle":
            runs_key, balls_key = "runs_mid", "balls_mid"
        else:
            runs_key, balls_key = "runs_death", "balls_death"
        phase[name] = {
            "runs_total": sum(o[runs_key] for o in observations),
            "balls_total": sum(o[balls_key] for o in observations),
            "innings_active": sum(1 for o in observations if o[balls_key] > 0),
        }

    return {
        "n_innings": n,
        "n_dismissals": n_dismissals,
        "n_notouts": n_notouts,
        "runs": {
            "total": total_runs,
            "balls_total": total_balls,
            "mean_per_innings": round(mean_runs, 2),
            "median": median_runs,
            "variance": round(variance, 2),
            "std": round(std, 2),
            "average": round(average, 2) if average is not None else None,
            "observations": observations,
        },
        "milestones": {
            "p_failure_10": round(_p_leq(10), 4),
            "p_25_plus": round(_p_geq(25), 4),
            "p_30_plus": round(_p_geq(30), 4),
            "p_50_plus": round(_p_geq(50), 4),
            "p_100_plus": round(_p_geq(100), 4),
            # Conditional "going-on" probabilities — measure how often a
            # batter who reached the threshold went on to the next mark.
            # Null when the denominator threshold was never reached.
            "p_50_given_30": (
                round(_p_cond(50, 30), 4) if _p_cond(50, 30) is not None else None
            ),
            "p_70_given_50": (
                round(_p_cond(70, 50), 4) if _p_cond(70, 50) is not None else None
            ),
        },
        "phase": phase,
    }


def _form_windows(observations: list[dict], today: date) -> dict:
    """Derive last-10 + last-60d + last-6mo + last-1yr form windows from
    a date-asc observation list. Returns the per-window dossiers plus a
    delta block comparing each window's mean / median to the
    full-scope sample. Spec §8.6.

    Window definitions:
      - last_10:   ORDER BY date DESC LIMIT 10 (no calendar dependence).
      - last_60d:  match.date >= today − 60 days (recent form).
      - last_6mo:  match.date >= today − 180 days (medium-term arc).
      - last_1yr:  match.date >= today − 365 days (loss-of-form gauge).
    """
    last_10 = observations[-10:]
    cutoff_60d = (today - timedelta(days=60)).isoformat()
    cutoff_6mo = (today - timedelta(days=180)).isoformat()
    cutoff_1yr = (today - timedelta(days=365)).isoformat()
    last_60d = [o for o in observations if (o["date"] or "") >= cutoff_60d]
    last_6mo = [o for o in observations if (o["date"] or "") >= cutoff_6mo]
    last_1yr = [o for o in observations if (o["date"] or "") >= cutoff_1yr]

    lifetime_doss = _distribution_dossier(observations)
    last_10_doss = _distribution_dossier(last_10)
    last_60d_doss = _distribution_dossier(last_60d)
    last_6mo_doss = _distribution_dossier(last_6mo)
    last_1yr_doss = _distribution_dossier(last_1yr)

    def _delta(w: dict, key: str) -> Optional[float]:
        wv = w["runs"][key]
        lv = lifetime_doss["runs"][key]
        if wv is None or lv is None:
            return None
        return round(wv - lv, 2)

    return {
        "last_10": last_10_doss,
        "last_60d": last_60d_doss,
        "last_6mo": last_6mo_doss,
        "last_1yr": last_1yr_doss,
        "delta": {
            "last_10_mean_minus_lifetime": _delta(last_10_doss, "mean_per_innings"),
            "last_10_median_minus_lifetime": _delta(last_10_doss, "median"),
            "last_60d_mean_minus_lifetime": _delta(last_60d_doss, "mean_per_innings"),
            "last_60d_median_minus_lifetime": _delta(last_60d_doss, "median"),
            "last_6mo_mean_minus_lifetime": _delta(last_6mo_doss, "mean_per_innings"),
            "last_6mo_median_minus_lifetime": _delta(last_6mo_doss, "median"),
            "last_1yr_mean_minus_lifetime": _delta(last_1yr_doss, "mean_per_innings"),
            "last_1yr_median_minus_lifetime": _delta(last_1yr_doss, "median"),
        },
    }


@router.get("/{person_id}/distribution")
async def batting_distribution(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    as_of_date: Optional[str] = Query(
        None,
        description=(
            "ISO date (YYYY-MM-DD) to anchor the calendar-based form"
            " windows (last_60d / last_6mo / last_1yr). Defaults to the"
            " server's today. Pin this for deterministic regression"
            " tests; production callers leave it absent."
        ),
    ),
):
    """Per-innings runs distribution dossier for a batter under the
    active filter scope.

    Returns lifetime + four form-window dossiers (last-10 innings +
    last-60 days + last-6 months + last-1 year) plus scope-derived
    suggested-splits navigation hints.

    Spec: internal_docs/spec-distribution-stats.md §8.
    """
    db = get_db()
    today = date.fromisoformat(as_of_date) if as_of_date else date.today()

    observations = await _innings_master_sample(db, person_id, filters, aux)
    lifetime = _distribution_dossier(observations)
    form = _form_windows(observations, today)

    scope = scope_dict_from_filters(filters)
    splits = suggested_splits(scope)

    return {
        "scope": {k: v for k, v in scope.items() if v},
        "lifetime": lifetime,
        "form": form,
        "suggested_splits": splits,
    }
