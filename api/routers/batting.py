"""Batting analytics router."""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams
from ..player_nationality import player_nationalities

router = APIRouter(prefix="/api/v1/batters", tags=["Batting"])


def _safe_div(a, b, mul=1, ndigits=2):
    """Safe division returning None on zero denominator."""
    if not b:
        return None
    return round(a * mul / b, ndigits)


def _batting_filter(filters: FilterParams, person_id: str, bowler_id: str | None = None):
    """Build WHERE clause for batting delivery queries."""
    where, params = filters.build(has_innings_join=True)
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
    # has_innings_join=False → only match-level clauses, no super_over
    # filter. Empty string = no filters at all → skip both joins.
    match_where, params = filters.build(has_innings_join=False)
    has_filters = bool(match_where)

    if has_filters:
        agg_sql = f"""
            SELECT d.batter_id AS person_id,
                   SUM(d.runs_batter) AS runs,
                   COUNT(*) AS balls
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE d.batter_id IS NOT NULL
              AND d.extras_wides = 0 AND d.extras_noballs = 0
              AND {match_where}
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
              AND {match_where}
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
    bowler_id: Optional[str] = Query(None),
):
    db = get_db()

    # Get player name
    name_rows = await db.q(
        "SELECT name FROM person WHERE id = :pid", {"pid": person_id}
    )
    name = name_rows[0]["name"] if name_rows else person_id

    where, params = _batting_filter(filters, person_id, bowler_id)

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
    bowler_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("date"),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, bowler_id)
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
    bowler_id: Optional[str] = Query(None),
    min_balls: int = Query(6, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("balls"),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, bowler_id)
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
    dismiss_where, dismiss_params = filters.build(has_innings_join=True)
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
    bowler_id: Optional[str] = Query(None),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, bowler_id)

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
    dismiss_where, dismiss_params = filters.build(has_innings_join=True)
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
    bowler_id: Optional[str] = Query(None),
):
    db = get_db()
    where, params = _batting_filter(filters, person_id, bowler_id)

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
    dismiss_where, dismiss_params = filters.build(has_innings_join=True)
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
):
    db = get_db()
    where, params = _batting_filter(filters, person_id)

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
    bowler_id: Optional[str] = Query(None),
):
    db = get_db()
    filt_where, filt_params = filters.build(has_innings_join=True)
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
):
    db = get_db()
    where, params = filters.build(has_innings_join=True)
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
