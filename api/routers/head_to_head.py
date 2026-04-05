"""Head-to-head batter vs bowler analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_db
from ..filters import FilterParams

router = APIRouter(prefix="/api/v1/head-to-head", tags=["Head to Head"])


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


@router.get("/{batter_id}/{bowler_id}")
async def head_to_head(
    batter_id: str,
    bowler_id: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    where, params = filters.build(has_innings_join=True)
    params["batter_id"] = batter_id
    params["bowler_id"] = bowler_id

    base_parts = [
        "d.batter_id = :batter_id",
        "d.bowler_id = :bowler_id",
        "d.extras_wides = 0",
        "d.extras_noballs = 0",
    ]
    if where:
        base_parts.append(where)
    base_clause = " AND ".join(base_parts)

    # Person names
    batter_rows = await db.q(
        "SELECT name FROM person WHERE id = :batter_id", {"batter_id": batter_id}
    )
    bowler_rows = await db.q(
        "SELECT name FROM person WHERE id = :bowler_id", {"bowler_id": bowler_id}
    )
    batter_name = batter_rows[0]["name"] if batter_rows else batter_id
    bowler_name = bowler_rows[0]["name"] if bowler_rows else bowler_id

    # Summary
    summary_rows = await db.q(
        f"""
        SELECT
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        """,
        params,
    )
    s = summary_rows[0] if summary_rows else {}
    balls = s.get("balls") or 0
    runs = s.get("runs") or 0
    fours = s.get("fours") or 0
    sixes = s.get("sixes") or 0
    dots = s.get("dots") or 0
    boundaries = fours + sixes

    # Dismissals
    dismiss_parts = [
        "d.batter_id = :batter_id",
        "d.bowler_id = :bowler_id",
        "w.player_out_id = :batter_id",
        "w.kind NOT IN ('retired hurt', 'retired out')",
    ]
    if where:
        dismiss_parts.append(where)
    dismiss_clause = " AND ".join(dismiss_parts)

    dismiss_rows = await db.q(
        f"""
        SELECT w.kind, COUNT(*) as cnt
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {dismiss_clause}
        GROUP BY w.kind
        """,
        params,
    )
    dismissal_kinds = {r["kind"]: r["cnt"] for r in dismiss_rows}
    dismissals = sum(dismissal_kinds.values())

    summary = {
        "balls": balls,
        "runs": runs,
        "dismissals": dismissals,
        "average": _safe_div(runs, dismissals),
        "strike_rate": _safe_div(runs, balls, 100),
        "fours": fours,
        "sixes": sixes,
        "dots": dots,
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "balls_per_boundary": _safe_div(balls, boundaries) if boundaries else None,
    }

    # By over
    by_over_rows = await db.q(
        f"""
        SELECT
            d.over_number,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        GROUP BY d.over_number
        ORDER BY d.over_number
        """,
        params,
    )

    # Wickets by over
    over_wkt_rows = await db.q(
        f"""
        SELECT d.over_number, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {dismiss_clause}
        GROUP BY d.over_number
        """,
        params,
    )
    over_wkt_map = {r["over_number"]: r["wickets"] for r in over_wkt_rows}
    by_over = []
    for r in by_over_rows:
        r["wickets"] = over_wkt_map.get(r["over_number"], 0)
        r["over_number"] = r["over_number"] + 1  # display as 1-20
        by_over.append(r)

    # By phase
    by_phase_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        GROUP BY phase
        ORDER BY MIN(d.over_number)
        """,
        params,
    )
    phase_wkt_rows = await db.q(
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
        WHERE {dismiss_clause}
        GROUP BY phase
        """,
        params,
    )
    phase_wkt_map = {r["phase"]: r["wickets"] for r in phase_wkt_rows}
    by_phase = []
    for r in by_phase_rows:
        b = r["balls"] or 0
        r["wickets"] = phase_wkt_map.get(r["phase"], 0)
        r["strike_rate"] = _safe_div(r["runs"] or 0, b, 100)
        by_phase.append(r)

    # By season
    by_season_rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    season_wkt_rows = await db.q(
        f"""
        SELECT m.season, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {dismiss_clause}
        GROUP BY m.season
        """,
        params,
    )
    season_wkt_map = {r["season"]: r["wickets"] for r in season_wkt_rows}
    by_season = []
    for r in by_season_rows:
        b = r["balls"] or 0
        r["wickets"] = season_wkt_map.get(r["season"], 0)
        r["strike_rate"] = _safe_div(r["runs"] or 0, b, 100)
        by_season.append(r)

    # By match
    by_match_rows = await db.q(
        f"""
        SELECT
            i.match_id,
            (SELECT md.date FROM matchdate md WHERE md.match_id = i.match_id
             ORDER BY md.date LIMIT 1) as date,
            m.event_name as tournament,
            m.venue,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {base_clause}
        GROUP BY i.match_id
        ORDER BY date DESC
        """,
        params,
    )

    # Dismissals per match
    match_dismiss_rows = await db.q(
        f"""
        SELECT i.match_id, w.kind
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {dismiss_clause}
        """,
        params,
    )
    match_dismiss_map = {}
    for r in match_dismiss_rows:
        match_dismiss_map[r["match_id"]] = r["kind"]

    by_match = []
    for r in by_match_rows:
        mid = r["match_id"]
        dismissed = mid in match_dismiss_map
        by_match.append({
            "match_id": mid,
            "date": r["date"],
            "tournament": r["tournament"],
            "venue": r["venue"],
            "balls": r["balls"],
            "runs": r["runs"],
            "fours": r["fours"],
            "sixes": r["sixes"],
            "dismissed": dismissed,
            "how_out": match_dismiss_map.get(mid),
        })

    return {
        "batter": {"id": batter_id, "name": batter_name},
        "bowler": {"id": bowler_id, "name": bowler_name},
        "summary": summary,
        "dismissal_kinds": dismissal_kinds,
        "by_over": by_over,
        "by_phase": by_phase,
        "by_season": by_season,
        "by_match": by_match,
    }
