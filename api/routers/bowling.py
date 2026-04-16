"""Bowling analytics router."""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams
from ..player_nationality import player_nationalities

router = APIRouter(prefix="/api/v1/bowlers", tags=["Bowling"])


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


def _bowling_legal_filter(filters: FilterParams, person_id: str, batter_id: str | None = None):
    """WHERE clause for legal-ball bowling queries — side-neutral team filter."""
    where, params = filters.build_side_neutral(has_innings_join=True)
    params["person_id"] = person_id
    parts = ["d.bowler_id = :person_id", "d.extras_wides = 0", "d.extras_noballs = 0"]
    if where:
        parts.append(where)
    if batter_id:
        parts.append("d.batter_id = :batter_id")
        params["batter_id"] = batter_id
    return " AND ".join(parts), params


@router.get("/leaders")
async def bowling_leaders(
    filters: FilterParams = Depends(),
    limit: int = Query(10, ge=1, le=50),
    min_balls: int = Query(60, ge=1),
    min_wickets: int = Query(3, ge=0),
):
    """Top bowlers in the current filter scope.

    Returns two leaderboards:
      - by_strike_rate: filtered to `min_balls` + `min_wickets`,
        sorted by legal_balls / wickets (ASC — lower is better).
      - by_economy: filtered to `min_balls`, sorted by runs × 6 /
        legal_balls (ASC). No wicket requirement.

    runs_conceded uses SUM(d.runs_total) so it matches the existing
    bowling endpoints (all deliveries including extras). Wickets
    exclude run out / retired / obstructing the field (not bowler-
    credited).

    Perf note: When no match-level filter is active we skip the
    innings/match JOINs entirely. See batting_leaders for the
    super-over caveat (0.04% noise, imperceptible).
    """
    db = get_db()
    match_where, params = filters.build(has_innings_join=False)
    has_filters = bool(match_where)

    if has_filters:
        agg_sql = f"""
            SELECT d.bowler_id AS person_id,
                   SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                            THEN 1 ELSE 0 END) AS balls,
                   SUM(d.runs_total) AS runs_conceded
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE d.bowler_id IS NOT NULL AND {match_where}
            GROUP BY d.bowler_id
            HAVING balls >= :min_balls
        """
        wkt_sql = f"""
            SELECT d.bowler_id AS person_id, COUNT(*) AS wickets
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE d.bowler_id IS NOT NULL
              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
              AND {match_where}
            GROUP BY d.bowler_id
        """
    else:
        agg_sql = """
            SELECT d.bowler_id AS person_id,
                   SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                            THEN 1 ELSE 0 END) AS balls,
                   SUM(d.runs_total) AS runs_conceded
            FROM delivery d
            WHERE d.bowler_id IS NOT NULL
            GROUP BY d.bowler_id
            HAVING balls >= :min_balls
        """
        wkt_sql = """
            SELECT d.bowler_id AS person_id, COUNT(*) AS wickets
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            WHERE d.bowler_id IS NOT NULL
              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
            GROUP BY d.bowler_id
        """

    agg_rows = await db.q(agg_sql, {**params, "min_balls": min_balls})
    wkt_rows = await db.q(wkt_sql, params)
    wkt_map = {r["person_id"]: r["wickets"] or 0 for r in wkt_rows}

    entries: list[dict] = []
    for r in agg_rows:
        pid = r["person_id"]
        balls = r["balls"] or 0
        runs = r["runs_conceded"] or 0
        wkts = wkt_map.get(pid, 0)
        entries.append({
            "person_id": pid,
            "balls": balls,
            "runs_conceded": runs,
            "wickets": wkts,
            "strike_rate": _safe_div(balls, wkts) if wkts > 0 else None,
            "economy": _safe_div(runs, balls, 6),
        })

    sr_top = sorted(
        (e for e in entries if e["wickets"] >= min_wickets and e["strike_rate"] is not None),
        key=lambda e: (e["strike_rate"], -e["wickets"]),
    )[:limit]
    econ_top = sorted(
        (e for e in entries if e["economy"] is not None),
        key=lambda e: (e["economy"], -e["balls"]),
    )[:limit]

    top_ids = {e["person_id"] for e in sr_top} | {e["person_id"] for e in econ_top}
    name_map: dict[str, str] = {}
    if top_ids:
        placeholders = ",".join(f":n{i}" for i in range(len(top_ids)))
        name_params = {f"n{i}": pid for i, pid in enumerate(top_ids)}
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({placeholders})",
            name_params,
        )
        name_map = {r["id"]: r["name"] for r in name_rows}
    for e in sr_top:
        e["name"] = name_map.get(e["person_id"], e["person_id"])
    for e in econ_top:
        e["name"] = name_map.get(e["person_id"], e["person_id"])

    return {
        "by_strike_rate": sr_top,
        "by_economy": econ_top,
        "thresholds": {
            "min_balls": min_balls,
            "min_wickets": min_wickets,
        },
    }


def _bowling_all_filter(filters: FilterParams, person_id: str, batter_id: str | None = None):
    """WHERE clause for all-delivery bowling queries (includes wides/noballs).

    side-neutral: a bowler's deliveries live in opponent-batting innings.
    """
    where, params = filters.build_side_neutral(has_innings_join=True)
    params["person_id"] = person_id
    parts = ["d.bowler_id = :person_id"]
    if where:
        parts.append(where)
    if batter_id:
        parts.append("d.batter_id = :batter_id")
        params["batter_id"] = batter_id
    return " AND ".join(parts), params


def _bowling_wicket_filter(filters: FilterParams, person_id: str, batter_id: str | None = None):
    """WHERE clause for bowler wicket queries — side-neutral team filter."""
    where, params = filters.build_side_neutral(has_innings_join=True)
    params["person_id"] = person_id
    parts = [
        "d.bowler_id = :person_id",
        "w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')",
    ]
    if where:
        parts.append(where)
    if batter_id:
        parts.append("w.player_out_id = :batter_id")
        params["batter_id"] = batter_id
    return " AND ".join(parts), params


def _enrich_bowling_row(r: dict) -> dict:
    """Add computed bowling metrics."""
    balls = r.get("balls") or 0
    runs = r.get("runs_conceded") or r.get("runs") or 0
    wickets = r.get("wickets") or 0
    fours = r.get("fours") or r.get("fours_conceded") or 0
    sixes = r.get("sixes") or r.get("sixes_conceded") or 0
    dots = r.get("dots") or 0
    boundaries = fours + sixes

    r["economy"] = _safe_div(runs, balls, 6)
    r["average"] = _safe_div(runs, wickets)
    r["strike_rate"] = _safe_div(balls, wickets) if wickets else None
    r["dot_pct"] = _safe_div(dots, balls, 100, 1) if balls else None
    r["boundary_pct"] = _safe_div(boundaries, balls, 100, 1) if balls else None
    r["balls_per_four"] = _safe_div(balls, fours) if fours else None
    r["balls_per_six"] = _safe_div(balls, sixes) if sixes else None
    r["balls_per_boundary"] = _safe_div(balls, boundaries) if boundaries else None
    return r


def _format_overs(balls: int) -> str:
    return f"{balls // 6}.{balls % 6}"


@router.get("/{person_id}/summary")
async def bowling_summary(
    person_id: str,
    filters: FilterParams = Depends(),
    batter_id: Optional[str] = Query(None),
):
    db = get_db()

    name_rows = await db.q(
        "SELECT name FROM person WHERE id = :pid", {"pid": person_id}
    )
    name = name_rows[0]["name"] if name_rows else person_id

    # Legal balls: balls, batter runs, boundaries, dots
    legal_where, legal_params = _bowling_legal_filter(filters, person_id, batter_id)
    legal = await db.q(
        f"""
        SELECT
            COUNT(*) as legal_balls,
            SUM(d.runs_batter) as batter_runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {legal_where}
        """,
        legal_params,
    )
    lc = legal[0] if legal else {}

    # All deliveries: runs conceded, wides, noballs
    all_where, all_params = _bowling_all_filter(filters, person_id, batter_id)
    all_del = await db.q(
        f"""
        SELECT
            COUNT(*) as all_deliveries,
            SUM(d.runs_total) as runs_conceded,
            SUM(d.extras_wides) as wides,
            SUM(d.extras_noballs) as noballs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {all_where}
        """,
        all_params,
    )
    ac = all_del[0] if all_del else {}

    # Wickets
    wkt_where, wkt_params = _bowling_wicket_filter(filters, person_id, batter_id)
    wkt_rows = await db.q(
        f"""
        SELECT COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        """,
        wkt_params,
    )
    wickets = wkt_rows[0]["wickets"] if wkt_rows else 0

    # Innings + matches count (distinct match_ids the bowler appeared in)
    innings_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT d.innings_id) as innings,
               COUNT(DISTINCT i.match_id) as matches
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {all_where}
        """,
        all_params,
    )
    innings_count = innings_rows[0]["innings"] if innings_rows else 0
    matches_count = innings_rows[0]["matches"] if innings_rows else 0

    # Best figures (per innings)
    best_rows = await db.q(
        f"""
        SELECT d.innings_id,
               COUNT(*) as wkts,
               (SELECT SUM(d2.runs_total) FROM delivery d2
                WHERE d2.innings_id = d.innings_id AND d2.bowler_id = :person_id) as runs
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        GROUP BY d.innings_id
        ORDER BY wkts DESC, runs ASC
        LIMIT 1
        """,
        wkt_params,
    )
    if best_rows:
        best = f"{best_rows[0]['wkts']}/{best_rows[0]['runs']}"
    else:
        best = None

    # Four-wicket hauls
    fwh_rows = await db.q(
        f"""
        SELECT COUNT(*) as cnt FROM (
            SELECT d.innings_id, COUNT(*) as wkts
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {wkt_where}
            GROUP BY d.innings_id
            HAVING COUNT(*) >= 4
        )
        """,
        wkt_params,
    )
    four_wkt_hauls = fwh_rows[0]["cnt"] if fwh_rows else 0

    # Maiden overs
    maiden_rows = await db.q(
        f"""
        SELECT COUNT(*) as maidens FROM (
            SELECT d.innings_id, d.over_number
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {all_where}
            GROUP BY d.innings_id, d.over_number
            HAVING SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) = 6
               AND SUM(d.runs_total) = 0
        )
        """,
        all_params,
    )
    maidens = maiden_rows[0]["maidens"] if maiden_rows else 0

    balls = lc.get("legal_balls") or 0
    runs_conceded = ac.get("runs_conceded") or 0
    fours = lc.get("fours") or 0
    sixes = lc.get("sixes") or 0
    dots = lc.get("dots") or 0
    boundaries = fours + sixes

    nationalities = await player_nationalities(db, person_id)

    return {
        "person_id": person_id,
        "name": name,
        "nationalities": nationalities,
        "matches": matches_count,
        "innings": innings_count,
        "balls": balls,
        "overs": _format_overs(balls),
        "runs_conceded": runs_conceded,
        "wickets": wickets,
        "average": _safe_div(runs_conceded, wickets),
        "economy": _safe_div(runs_conceded, balls, 6),
        "strike_rate": _safe_div(balls, wickets) if wickets else None,
        "best_figures": best,
        "four_wicket_hauls": four_wkt_hauls,
        "fours_conceded": fours,
        "sixes_conceded": sixes,
        "boundaries_conceded": boundaries,
        "dots": dots,
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "wides": ac.get("wides") or 0,
        "noballs": ac.get("noballs") or 0,
        "balls_per_four": _safe_div(balls, fours),
        "balls_per_six": _safe_div(balls, sixes),
        "balls_per_boundary": _safe_div(balls, boundaries),
        "maiden_overs": maidens,
    }


@router.get("/{person_id}/by-innings")
async def bowling_by_innings(
    person_id: str,
    filters: FilterParams = Depends(),
    batter_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("date"),
):
    db = get_db()
    all_where, all_params = _bowling_all_filter(filters, person_id, batter_id)
    all_params["limit"] = limit
    all_params["offset"] = offset

    sort_map = {
        "date": "date DESC",
        "wickets": "wickets DESC",
        "economy": "economy ASC",
        "runs": "runs_conceded ASC",
    }
    order = sort_map.get(sort, "date DESC")

    count_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT d.innings_id) as total
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {all_where}
        """,
        all_params,
    )
    total = count_rows[0]["total"] if count_rows else 0

    rows = await db.q(
        f"""
        SELECT
            i.match_id,
            (SELECT md.date FROM matchdate md WHERE md.match_id = i.match_id
             ORDER BY md.date LIMIT 1) as date,
            i.team as batting_team,
            CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END as team,
            CASE WHEN m.team1 != i.team THEN m.team2 ELSE m.team1 END as opponent,
            m.event_name as tournament,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) as dots,
            SUM(d.extras_wides) as wides,
            SUM(d.extras_noballs) as noballs,
            (SELECT COUNT(*) FROM wicket w2
             JOIN delivery d2 ON d2.id = w2.delivery_id
             WHERE d2.innings_id = d.innings_id AND d2.bowler_id = :person_id
               AND w2.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
            ) as wickets
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {all_where}
        GROUP BY d.innings_id
        HAVING 1=1
        ORDER BY {order}
        LIMIT :limit OFFSET :offset
        """,
        all_params,
    )

    innings = []
    for r in rows:
        balls = r["balls"] or 0
        runs = r["runs_conceded"] or 0
        innings.append({
            "match_id": r["match_id"],
            "date": r["date"],
            "team": r["team"],
            "opponent": r["opponent"],
            "tournament": r["tournament"],
            "overs": _format_overs(balls),
            "balls": balls,
            "runs": runs,
            "wickets": r["wickets"] or 0,
            "economy": _safe_div(runs, balls, 6),
            "fours": r["fours"] or 0,
            "sixes": r["sixes"] or 0,
            "dots": r["dots"] or 0,
            "maidens": 0,  # Would need per-over sub-query; omitting for perf
            "wides": r["wides"] or 0,
            "noballs": r["noballs"] or 0,
        })

    return {"innings": innings, "total": total}


@router.get("/{person_id}/vs-batters")
async def bowling_vs_batters(
    person_id: str,
    filters: FilterParams = Depends(),
    batter_id: Optional[str] = Query(None),
    min_balls: int = Query(6, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("balls"),
):
    db = get_db()
    legal_where, legal_params = _bowling_legal_filter(filters, person_id, batter_id)
    legal_params["min_balls"] = min_balls
    legal_params["limit"] = limit

    sort_map = {
        "balls": "balls DESC",
        "runs": "runs_conceded DESC",
        "economy": "economy ASC",
        "wickets": "wickets DESC",
    }
    order = sort_map.get(sort, "balls DESC")

    rows = await db.q(
        f"""
        SELECT
            d.batter_id,
            d.batter as batter_name,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs_conceded,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {legal_where}
        GROUP BY d.batter_id
        HAVING COUNT(*) >= :min_balls
        ORDER BY balls DESC
        LIMIT :limit
        """,
        legal_params,
    )

    # Wickets by batter
    wkt_where, wkt_params = _bowling_wicket_filter(filters, person_id, batter_id)
    wkt_rows = await db.q(
        f"""
        SELECT w.player_out_id as batter_id, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        GROUP BY w.player_out_id
        """,
        wkt_params,
    )
    wkt_map = {r["batter_id"]: r["wickets"] for r in wkt_rows}

    matchups = []
    for r in rows:
        r["wickets"] = wkt_map.get(r["batter_id"], 0)
        r["fours"] = r.pop("fours_conceded", 0)
        r["sixes"] = r.pop("sixes_conceded", 0)
        _enrich_bowling_row(r)
        matchups.append(r)

    if sort == "wickets":
        matchups.sort(key=lambda x: x.get("wickets", 0), reverse=True)

    return {"matchups": matchups}


@router.get("/{person_id}/by-over")
async def bowling_by_over(
    person_id: str,
    filters: FilterParams = Depends(),
    batter_id: Optional[str] = Query(None),
):
    db = get_db()
    legal_where, legal_params = _bowling_legal_filter(filters, person_id, batter_id)

    rows = await db.q(
        f"""
        SELECT
            d.over_number,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs_conceded,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {legal_where}
        GROUP BY d.over_number
        ORDER BY d.over_number
        """,
        legal_params,
    )

    # Wickets per over
    wkt_where, wkt_params = _bowling_wicket_filter(filters, person_id, batter_id)
    wkt_rows = await db.q(
        f"""
        SELECT d.over_number, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        GROUP BY d.over_number
        """,
        wkt_params,
    )
    wkt_map = {r["over_number"]: r["wickets"] for r in wkt_rows}

    by_over = []
    for r in rows:
        r["wickets"] = wkt_map.get(r["over_number"], 0)
        r["over_number"] = r["over_number"] + 1  # display as 1-20
        _enrich_bowling_row(r)
        by_over.append(r)

    return {"by_over": by_over}


@router.get("/{person_id}/by-phase")
async def bowling_by_phase(
    person_id: str,
    filters: FilterParams = Depends(),
    batter_id: Optional[str] = Query(None),
):
    db = get_db()
    legal_where, legal_params = _bowling_legal_filter(filters, person_id, batter_id)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs_conceded,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {legal_where}
        GROUP BY phase
        ORDER BY MIN(d.over_number)
        """,
        legal_params,
    )

    wkt_where, wkt_params = _bowling_wicket_filter(filters, person_id, batter_id)
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
        WHERE {wkt_where}
        GROUP BY phase
        """,
        wkt_params,
    )
    wkt_map = {r["phase"]: r["wickets"] for r in wkt_rows}

    phase_labels = {"powerplay": "1-6", "middle": "7-15", "death": "16-20"}
    by_phase = []
    for r in rows:
        r["overs_range"] = phase_labels.get(r["phase"], "")
        r["wickets"] = wkt_map.get(r["phase"], 0)
        _enrich_bowling_row(r)
        by_phase.append(r)

    # Sub-phase splits for powerplay: overs 1-3 (0-2) and overs 4-6 (3-5).
    # Returned as extra entries so the frontend can lay them out alongside
    # the full powerplay.
    sub_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 2 THEN 'pp_early'
                WHEN d.over_number BETWEEN 3 AND 5 THEN 'pp_late'
            END as phase,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs_conceded,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {legal_where} AND d.over_number BETWEEN 0 AND 5
        GROUP BY phase
        ORDER BY MIN(d.over_number)
        """,
        legal_params,
    )
    sub_wkt_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 2 THEN 'pp_early'
                WHEN d.over_number BETWEEN 3 AND 5 THEN 'pp_late'
            END as phase,
            COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where} AND d.over_number BETWEEN 0 AND 5
        GROUP BY phase
        """,
        wkt_params,
    )
    sub_wkt_map = {r["phase"]: r["wickets"] for r in sub_wkt_rows}
    sub_labels = {"pp_early": "1-3", "pp_late": "4-6"}
    for r in sub_rows:
        r["overs_range"] = sub_labels.get(r["phase"], "")
        r["wickets"] = sub_wkt_map.get(r["phase"], 0)
        _enrich_bowling_row(r)
        by_phase.append(r)

    return {"by_phase": by_phase}


@router.get("/{person_id}/by-season")
async def bowling_by_season(
    person_id: str,
    filters: FilterParams = Depends(),
    batter_id: Optional[str] = Query(None),
):
    db = get_db()
    legal_where, legal_params = _bowling_legal_filter(filters, person_id, batter_id)

    rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(*) as balls,
            SUM(d.runs_batter) as runs_conceded,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0 THEN 1 ELSE 0 END) as dots,
            COUNT(DISTINCT d.innings_id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {legal_where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        legal_params,
    )

    # All deliveries per season for runs_conceded
    all_where, all_params = _bowling_all_filter(filters, person_id, batter_id)
    all_rows = await db.q(
        f"""
        SELECT m.season, SUM(d.runs_total) as runs_conceded
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {all_where}
        GROUP BY m.season
        """,
        all_params,
    )
    runs_map = {r["season"]: r["runs_conceded"] for r in all_rows}

    # Wickets per season
    wkt_where, wkt_params = _bowling_wicket_filter(filters, person_id, batter_id)
    wkt_rows = await db.q(
        f"""
        SELECT m.season, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        GROUP BY m.season
        """,
        wkt_params,
    )
    wkt_map = {r["season"]: r["wickets"] for r in wkt_rows}

    by_season = []
    for r in rows:
        season = r["season"]
        r["runs_conceded"] = runs_map.get(season, 0)
        r["wickets"] = wkt_map.get(season, 0)
        r["overs"] = _format_overs(r["balls"] or 0)
        _enrich_bowling_row(r)
        by_season.append(r)

    return {"by_season": by_season}


@router.get("/{person_id}/wickets")
async def bowling_wickets(
    person_id: str,
    filters: FilterParams = Depends(),
    batter_id: Optional[str] = Query(None),
):
    db = get_db()
    wkt_where, wkt_params = _bowling_wicket_filter(filters, person_id, batter_id)

    # by_kind
    kind_rows = await db.q(
        f"""
        SELECT w.kind, COUNT(*) as cnt
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        GROUP BY w.kind
        ORDER BY cnt DESC
        """,
        wkt_params,
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
            COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        GROUP BY phase
        """,
        wkt_params,
    )
    by_phase = {r["phase"]: r["wickets"] for r in phase_rows}

    # by_over
    over_rows = await db.q(
        f"""
        SELECT d.over_number, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        GROUP BY d.over_number
        ORDER BY d.over_number
        """,
        wkt_params,
    )

    # top_victims
    victim_rows = await db.q(
        f"""
        SELECT w.player_out_id as batter_id, w.player_out as batter_name,
               w.kind, COUNT(*) as cnt
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {wkt_where}
        GROUP BY w.player_out_id, w.kind
        ORDER BY cnt DESC
        """,
        wkt_params,
    )
    from collections import defaultdict
    victim_agg = defaultdict(lambda: {"dismissals": 0, "kinds": {}, "batter_name": ""})
    for r in victim_rows:
        bid = r["batter_id"]
        victim_agg[bid]["batter_name"] = r["batter_name"]
        victim_agg[bid]["dismissals"] += r["cnt"]
        victim_agg[bid]["kinds"][r["kind"]] = r["cnt"]

    top_victims = sorted(
        [{"batter_id": k, **v} for k, v in victim_agg.items()],
        key=lambda x: x["dismissals"],
        reverse=True,
    )[:10]

    for r in over_rows:
        r["over_number"] = r["over_number"] + 1  # display as 1-20

    return {
        "total_wickets": total,
        "by_kind": by_kind,
        "by_phase": by_phase,
        "by_over": over_rows,
        "top_victims": top_victims,
    }
