"""Fielding analytics router."""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams
from ..player_nationality import player_nationalities

router = APIRouter(prefix="/api/v1/fielders", tags=["Fielding"])


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


def _fielding_filter(filters: FilterParams, person_id: str):
    """Build WHERE clause for fielding queries via fielding_credit.

    Uses build_side_neutral so filter_team / filter_opponent apply at
    match level — fielders' credits live in opponent-batting innings,
    so the default `i.team = :team` would return zero.
    """
    where, params = filters.build_side_neutral(has_innings_join=True)
    params["person_id"] = person_id
    parts = ["fc.fielder_id = :person_id"]
    if where:
        parts.append(where)
    return " AND ".join(parts), params


@router.get("/leaders")
async def fielding_leaders(
    filters: FilterParams = Depends(),
    limit: int = Query(10, ge=1, le=50),
):
    """Top fielders + top keepers in the current filter scope.

    Fielding leaderboards are volume-based, not rate-based: catches
    per match is mostly a position/opportunity stat, not a skill stat.
    So no thresholds — the top-N ranking is self-filtering.

    Returns two lists:
      - by_dismissals: sum of catches + run-outs + caught-and-bowled +
        stumpings per fielder. Inclusive — keepers will appear here
        too since they take many catches.
      - by_keeper_dismissals: catches + stumpings from innings where
        the fielder was the designated keeper per
        `keeper_assignment`. This separates specialist keeping from
        sub-fielders who caught behind the stumps. Uses the Tier 2
        keeper-identification pipeline; see docs/spec-fielding-tier2.md.

    Tiebreak: stumpings DESC (evidence of sharp hands) then catches
    DESC then run-outs DESC.
    """
    db = get_db()
    match_where, params = filters.build(has_innings_join=False)
    has_filters = bool(match_where)

    # --- List 1: top fielders by total dismissals ------------------
    # All four kinds aggregated per fielder, with per-kind breakdown
    # so the UI can show how the total composes.
    fc_parts = ["fc.fielder_id IS NOT NULL"]
    if has_filters:
        fc_join = ("JOIN delivery d ON d.id = fc.delivery_id "
                   "JOIN innings i ON i.id = d.innings_id "
                   "JOIN match m ON m.id = i.match_id")
        fc_parts.append(match_where)
    else:
        fc_join = ""
    fc_where = " AND ".join(fc_parts)
    fielder_rows = await db.q(
        f"""
        SELECT fc.fielder_id AS person_id,
               COUNT(*) AS total,
               SUM(CASE WHEN fc.kind = 'caught' THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
               SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs,
               SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) AS c_and_b
        FROM fieldingcredit fc {fc_join}
        WHERE {fc_where}
        GROUP BY fc.fielder_id
        ORDER BY total DESC, stumpings DESC, catches DESC, run_outs DESC
        LIMIT :lim
        """,
        {**params, "lim": limit},
    )

    # --- List 2: top keepers by keeper dismissals ------------------
    # Only fielding credits from innings where this fielder was the
    # designated keeper count. Restricts to caught + stumped (run
    # outs by the keeper are rare and muddy — they're fielding, not
    # keeping).
    ka_join = ("JOIN delivery d ON d.id = fc.delivery_id "
               "JOIN innings i ON i.id = d.innings_id "
               "JOIN keeperassignment ka ON ka.innings_id = i.id")
    ka_parts = [
        "fc.fielder_id IS NOT NULL",
        "ka.keeper_id = fc.fielder_id",
        "fc.kind IN ('caught', 'stumped')",
    ]
    if has_filters:
        ka_join += " JOIN match m ON m.id = i.match_id"
        ka_parts.append(match_where)
    ka_where = " AND ".join(ka_parts)
    keeper_rows = await db.q(
        f"""
        SELECT fc.fielder_id AS person_id,
               COUNT(*) AS total,
               SUM(CASE WHEN fc.kind = 'caught' THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings
        FROM fieldingcredit fc {ka_join}
        WHERE {ka_where}
        GROUP BY fc.fielder_id
        ORDER BY total DESC, stumpings DESC, catches DESC
        LIMIT :lim
        """,
        {**params, "lim": limit},
    )

    # Batch name lookup for the ~20 survivors.
    top_ids = {r["person_id"] for r in fielder_rows} | {r["person_id"] for r in keeper_rows}
    name_map: dict[str, str] = {}
    if top_ids:
        placeholders = ",".join(f":n{i}" for i in range(len(top_ids)))
        name_params = {f"n{i}": pid for i, pid in enumerate(top_ids)}
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({placeholders})",
            name_params,
        )
        name_map = {r["id"]: r["name"] for r in name_rows}

    def enrich(r, keeper: bool) -> dict:
        d = {
            "person_id": r["person_id"],
            "name": name_map.get(r["person_id"], r["person_id"]),
            "total": r["total"] or 0,
            "catches": r["catches"] or 0,
            "stumpings": r["stumpings"] or 0,
        }
        if not keeper:
            d["run_outs"] = r["run_outs"] or 0
            d["c_and_b"] = r["c_and_b"] or 0
        return d

    return {
        "by_dismissals": [enrich(r, keeper=False) for r in fielder_rows],
        "by_keeper_dismissals": [enrich(r, keeper=True) for r in keeper_rows],
    }


@router.get("/{person_id}/summary")
async def fielding_summary(
    person_id: str,
    filters: FilterParams = Depends(),
):
    db = get_db()

    name_rows = await db.q(
        "SELECT name FROM person WHERE id = :pid", {"pid": person_id}
    )
    name = name_rows[0]["name"] if name_rows else person_id

    where, params = _fielding_filter(filters, person_id)

    # Counts by kind
    kind_rows = await db.q(
        f"""
        SELECT fc.kind, COUNT(*) as cnt,
               SUM(CASE WHEN fc.is_substitute THEN 1 ELSE 0 END) as sub_cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY fc.kind
        """,
        params,
    )

    catches = 0
    stumpings = 0
    run_outs = 0
    caught_and_bowled = 0
    substitute_catches = 0

    for r in kind_rows:
        if r["kind"] == "caught":
            catches = r["cnt"]
            substitute_catches = r["sub_cnt"] or 0
        elif r["kind"] == "stumped":
            stumpings = r["cnt"]
        elif r["kind"] == "run_out":
            run_outs = r["cnt"]
        elif r["kind"] == "caught_and_bowled":
            caught_and_bowled = r["cnt"]

    total = catches + stumpings + run_outs + caught_and_bowled

    # Match count from matchplayer
    match_where, match_params = filters.build(has_innings_join=False)
    match_params["person_id"] = person_id
    match_parts = ["mp.person_id = :person_id"]
    if match_where:
        match_parts.append(match_where)
    match_clause = " AND ".join(match_parts)

    match_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT mp.match_id) as matches
        FROM matchplayer mp
        JOIN match m ON m.id = mp.match_id
        WHERE {match_clause}
        """,
        match_params,
    )
    matches = match_rows[0]["matches"] if match_rows else 0

    # Tier 2: innings where this person was identified as the keeper.
    # Used by the frontend to decide whether to render the "Keeping" tab.
    # side-neutral: keeper's innings live in opponent-batting innings.
    keeping_where, keeping_params = filters.build_side_neutral(has_innings_join=True)
    keeping_params["person_id"] = person_id
    keeping_parts = ["ka.keeper_id = :person_id"]
    if keeping_where:
        keeping_parts.append(keeping_where)
    keeping_clause = " AND ".join(keeping_parts)
    keeping_rows = await db.q(
        f"""
        SELECT COUNT(*) as c FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {keeping_clause}
        """,
        keeping_params,
    )
    innings_kept = keeping_rows[0]["c"] if keeping_rows else 0

    nationalities = await player_nationalities(db, person_id)

    return {
        "person_id": person_id,
        "name": name,
        "nationalities": nationalities,
        "matches": matches,
        "catches": catches,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "caught_and_bowled": caught_and_bowled,
        "total_dismissals": total,
        "dismissals_per_match": _safe_div(total, matches),
        "substitute_catches": substitute_catches,
        "innings_kept": innings_kept,
    }


@router.get("/{person_id}/by-season")
async def fielding_by_season(
    person_id: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id)

    rows = await db.q(
        f"""
        SELECT
            m.season,
            fc.kind,
            COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, fc.kind
        ORDER BY m.season
        """,
        params,
    )

    from collections import defaultdict
    seasons = defaultdict(lambda: {"catches": 0, "stumpings": 0, "run_outs": 0, "caught_and_bowled": 0})
    for r in rows:
        s = seasons[r["season"]]
        if r["kind"] == "caught":
            s["catches"] = r["cnt"]
        elif r["kind"] == "stumped":
            s["stumpings"] = r["cnt"]
        elif r["kind"] == "run_out":
            s["run_outs"] = r["cnt"]
        elif r["kind"] == "caught_and_bowled":
            s["caught_and_bowled"] = r["cnt"]

    by_season = []
    for season in sorted(seasons.keys()):
        s = seasons[season]
        total = s["catches"] + s["stumpings"] + s["run_outs"] + s["caught_and_bowled"]
        by_season.append({
            "season": season,
            "catches": s["catches"],
            "stumpings": s["stumpings"],
            "run_outs": s["run_outs"],
            "caught_and_bowled": s["caught_and_bowled"],
            "total": total,
        })

    return {"by_season": by_season}


@router.get("/{person_id}/by-phase")
async def fielding_by_phase(
    person_id: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            fc.kind,
            COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY phase, fc.kind
        ORDER BY MIN(d.over_number)
        """,
        params,
    )

    from collections import defaultdict
    phases = defaultdict(lambda: {"catches": 0, "stumpings": 0, "run_outs": 0, "caught_and_bowled": 0})
    for r in rows:
        p = phases[r["phase"]]
        if r["kind"] == "caught":
            p["catches"] = r["cnt"]
        elif r["kind"] == "stumped":
            p["stumpings"] = r["cnt"]
        elif r["kind"] == "run_out":
            p["run_outs"] = r["cnt"]
        elif r["kind"] == "caught_and_bowled":
            p["caught_and_bowled"] = r["cnt"]

    phase_labels = {"powerplay": "1-6", "middle": "7-15", "death": "16-20"}
    phase_order = ["powerplay", "middle", "death"]

    by_phase = []
    for phase in phase_order:
        if phase not in phases:
            continue
        p = phases[phase]
        total = p["catches"] + p["stumpings"] + p["run_outs"] + p["caught_and_bowled"]
        by_phase.append({
            "phase": phase,
            "overs": phase_labels[phase],
            "catches": p["catches"],
            "stumpings": p["stumpings"],
            "run_outs": p["run_outs"],
            "caught_and_bowled": p["caught_and_bowled"],
            "total": total,
        })

    return {"by_phase": by_phase}


@router.get("/{person_id}/by-over")
async def fielding_by_over(
    person_id: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id)

    rows = await db.q(
        f"""
        SELECT
            d.over_number,
            COUNT(*) as dismissals
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY d.over_number
        ORDER BY d.over_number
        """,
        params,
    )

    by_over = []
    for r in rows:
        by_over.append({
            "over_number": r["over_number"] + 1,  # display as 1-20
            "dismissals": r["dismissals"],
        })

    return {"by_over": by_over}


@router.get("/{person_id}/dismissal-types")
async def fielding_dismissal_types(
    person_id: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id)

    rows = await db.q(
        f"""
        SELECT fc.kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY fc.kind
        ORDER BY cnt DESC
        """,
        params,
    )

    by_kind = {r["kind"]: r["cnt"] for r in rows}
    total = sum(by_kind.values())

    return {"total": total, "by_kind": by_kind}


@router.get("/{person_id}/victims")
async def fielding_victims(
    person_id: str,
    filters: FilterParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id)
    params["limit"] = limit

    rows = await db.q(
        f"""
        SELECT
            w.player_out_id as batter_id,
            w.player_out as batter_name,
            fc.kind,
            COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN wicket w ON w.id = fc.wicket_id
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY w.player_out_id, fc.kind
        ORDER BY cnt DESC
        """,
        params,
    )

    from collections import defaultdict
    victim_agg = defaultdict(lambda: {
        "batter_name": "", "catches": 0, "stumpings": 0, "run_outs": 0, "total": 0,
    })
    for r in rows:
        v = victim_agg[r["batter_id"]]
        v["batter_name"] = r["batter_name"]
        if r["kind"] == "caught":
            v["catches"] += r["cnt"]
        elif r["kind"] == "caught_and_bowled":
            v["catches"] += r["cnt"]
        elif r["kind"] == "stumped":
            v["stumpings"] += r["cnt"]
        elif r["kind"] == "run_out":
            v["run_outs"] += r["cnt"]
        v["total"] += r["cnt"]

    victims = sorted(
        [{"batter_id": k, **v} for k, v in victim_agg.items()],
        key=lambda x: x["total"],
        reverse=True,
    )[:limit]

    return {"victims": victims}


@router.get("/{person_id}/by-innings")
async def fielding_by_innings(
    person_id: str,
    filters: FilterParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id)
    params["limit"] = limit
    params["offset"] = offset

    # Count total distinct match appearances with fielding credits
    count_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.match_id) as total
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
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
            m.event_name as tournament,
            SUM(CASE WHEN fc.kind = 'caught' THEN 1 ELSE 0 END) as catches,
            SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) as caught_and_bowled,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) as stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) as run_outs,
            COUNT(*) as total
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.match_id
        ORDER BY date DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    # For each match, figure out the opponent from the fielder's team perspective
    innings_list = []
    for r in rows:
        # Look up which team this fielder was on in this match
        team_rows = await db.q(
            "SELECT team FROM matchplayer WHERE match_id = :mid AND person_id = :pid LIMIT 1",
            {"mid": r["match_id"], "pid": person_id},
        )
        team = team_rows[0]["team"] if team_rows else None

        match_rows = await db.q(
            "SELECT team1, team2 FROM match WHERE id = :mid",
            {"mid": r["match_id"]},
        )
        if match_rows and team:
            mr = match_rows[0]
            opponent = mr["team2"] if mr["team1"] == team else mr["team1"]
        else:
            opponent = None

        innings_list.append({
            "match_id": r["match_id"],
            "date": r["date"],
            "opponent": opponent,
            "tournament": r["tournament"],
            "catches": r["catches"] + r["caught_and_bowled"],
            "stumpings": r["stumpings"],
            "run_outs": r["run_outs"],
            "total": r["total"],
        })

    return {"innings": innings_list, "total": total}
