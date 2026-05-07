"""Fielding analytics router."""

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
from ..wilson import prob_record

router = APIRouter(prefix="/api/v1/fielders", tags=["Fielding"])


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


def _fielding_filter(filters: FilterParams, person_id: str, aux: AuxParams | None = None):
    """Build WHERE clause for fielding queries via fielding_credit.

    Uses build_side_neutral so filter_team / filter_opponent apply at
    match level — fielders' credits live in opponent-batting innings,
    so the default `i.team = :team` would return zero.
    """
    where, params = filters.build_side_neutral(has_innings_join=True, aux=aux)
    params["person_id"] = person_id
    parts = ["fc.fielder_id = :person_id"]
    if where:
        parts.append(where)
    return " AND ".join(parts), params


@router.get("/leaders")
async def fielding_leaders(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
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
    # See batting_leaders + aux_clauses module for the rationale.
    # `aux_extra` is " AND <clause>..." with leading AND; we strip
    # for the AND-joined fc_parts list below.
    match_where, params = filters.build(has_innings_join=False, aux=aux)
    aux_extra = splice_aux_join_clauses(aux, params)
    has_filters = bool(match_where) or bool(aux_extra)

    # --- List 1: top fielders by total dismissals ------------------
    # All four kinds aggregated per fielder, with per-kind breakdown
    # so the UI can show how the total composes.
    fc_parts = ["fc.fielder_id IS NOT NULL"]
    if has_filters:
        fc_join = ("JOIN delivery d ON d.id = fc.delivery_id "
                   "JOIN innings i ON i.id = d.innings_id "
                   "JOIN match m ON m.id = i.match_id")
        if match_where:
            fc_parts.append(match_where)
        if aux_extra:
            # aux_extra carries leading " AND "; the fc_parts list
            # gets joined by " AND ", so strip the prefix.
            fc_parts.append(aux_extra.removeprefix(" AND "))
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
        if match_where:
            ka_parts.append(match_where)
        if aux_extra:
            ka_parts.append(aux_extra.removeprefix(" AND "))
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
    aux: AuxParams = Depends(),
):
    db = get_db()

    name_rows = await db.q(
        "SELECT name FROM person WHERE id = :pid", {"pid": person_id}
    )
    name = name_rows[0]["name"] if name_rows else person_id

    where, params = _fielding_filter(filters, person_id, aux=aux)

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
    match_where, match_params = filters.build(has_innings_join=False, aux=aux)
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
    keeping_where, keeping_params = filters.build_side_neutral(has_innings_join=True, aux=aux)
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
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)

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
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)

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
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)

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
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)

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
    aux: AuxParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)
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
    aux: AuxParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)
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


# ─────────────────────────────────────────────────────────────────────
# Per-match fielder distribution dossier — three sibling count blocks
# (catches / run_outs / stumpings) with three-simple milestone
# probabilities (P=0 / P=1 / P≥2), Wilson 95% CIs, and four form
# windows. Stumpings block emitted only for players with
# innings_kept > 0 in scope. Spec: internal_docs/spec-distribution-stats.md §13.


async def _match_master_sample_fielder(
    db, person_id: str, filters: FilterParams, aux: AuxParams,
) -> tuple[list[dict], int]:
    """Materialise per-match observation rows for a fielder under the
    active filter scope. One row per match the player appears on the
    team sheet (matchplayer.person_id = id). Returns (observations,
    substitute_catches). Spec §13.2.

    Match-grain filtering — drop has_innings_join. Side-neutral team
    filter — fielding credits live on the OPPOSITE-side innings.
    Inning aux is no-op for fielder (events span both innings; per
    spec §13.1).
    """
    # Match-level scope clause (no innings join). Side-neutral so
    # filter_team and filter_opponent apply at match level.
    where, params = filters.build_side_neutral(has_innings_join=False, aux=aux)
    params["person_id"] = person_id
    match_where = where if where else "1=1"

    # Single CTE-based query. player_matches is the scope-filtered
    # match list; fielding_per_match and keeping_per_match are
    # constrained only by player id (LEFT JOIN to player_matches
    # carries the scope filter).
    rows = await db.q(
        f"""
        WITH player_matches AS (
            SELECT mp.match_id,
                   MIN(md.date) AS date
            FROM matchplayer mp
            JOIN match m ON m.id = mp.match_id
            LEFT JOIN matchdate md ON md.match_id = mp.match_id
            WHERE mp.person_id = :person_id AND {match_where}
            GROUP BY mp.match_id
        ),
        fielding_per_match AS (
            SELECT i.match_id,
                   SUM(CASE WHEN fc.kind = 'caught'
                            AND COALESCE(fc.is_substitute, 0) = 0
                            THEN 1 ELSE 0 END) AS catches,
                   SUM(CASE WHEN fc.kind = 'run_out'
                            AND COALESCE(fc.is_substitute, 0) = 0
                            THEN 1 ELSE 0 END) AS run_outs,
                   SUM(CASE WHEN fc.kind = 'stumped'
                            THEN 1 ELSE 0 END) AS stumpings
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            JOIN innings i ON i.id = d.innings_id
            WHERE fc.fielder_id = :person_id
            GROUP BY i.match_id
        ),
        keeping_per_match AS (
            SELECT i.match_id,
                   COUNT(*) AS kept_innings
            FROM keeperassignment ka
            JOIN innings i ON i.id = ka.innings_id
            WHERE ka.keeper_id = :person_id
            GROUP BY i.match_id
        )
        SELECT pm.match_id,
               COALESCE(pm.date, '') AS date,
               COALESCE(fpm.catches, 0) AS catches,
               COALESCE(fpm.run_outs, 0) AS run_outs,
               COALESCE(fpm.stumpings, 0) AS stumpings,
               COALESCE(kpm.kept_innings, 0) AS kept_innings
        FROM player_matches pm
        LEFT JOIN fielding_per_match fpm ON fpm.match_id = pm.match_id
        LEFT JOIN keeping_per_match kpm ON kpm.match_id = pm.match_id
        ORDER BY pm.date ASC, pm.match_id ASC
        """,
        params,
    )
    observations = [
        {
            "match_id": r["match_id"],
            "date": r["date"],
            "catches": r["catches"] or 0,
            "run_outs": r["run_outs"] or 0,
            "stumpings": r["stumpings"] or 0,
            "kept_innings": r["kept_innings"] or 0,
            "is_keeper": 1 if (r["kept_innings"] or 0) > 0 else 0,
        }
        for r in rows
    ]

    # Substitute catches — same scope, separate scalar for
    # reconciliation against /fielders/{id}/summary.
    sub_rows = await db.q(
        f"""
        SELECT COUNT(*) AS sub_catches
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id = :person_id
          AND fc.kind = 'caught'
          AND fc.is_substitute = 1
          AND {match_where}
        """,
        params,
    )
    substitute_catches = (sub_rows[0]["sub_catches"] if sub_rows else 0) or 0
    return observations, substitute_catches


def _count_block(observations: list[dict], key: str) -> dict:
    """Sibling count block — `catches` / `run_outs` / `stumpings`.
    Three simples (P=0 / P=1 / P≥2), denom = n_matches. Spec §13.3.1."""
    n = len(observations)
    vals = [o[key] for o in observations]

    if n == 0:
        keys = ["p_zero", "p_one", "p_geq_2"]
        return {
            "total": 0,
            "mean_per_match": None,
            "median": None,
            "variance": None,
            "std": None,
            "milestones": {k: prob_record(0, 0) for k in keys},
        }

    total = sum(vals)
    mean = total / n
    median = statistics.median(vals)
    variance = statistics.variance(vals) if n >= 2 else 0.0
    std = variance ** 0.5

    def _count_eq(v: int) -> int:
        return sum(1 for x in vals if x == v)

    def _count_geq(v: int) -> int:
        return sum(1 for x in vals if x >= v)

    return {
        "total": total,
        "mean_per_match": round(mean, 4),
        "median": median,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "milestones": {
            "p_zero":  prob_record(_count_eq(0), n),
            "p_one":   prob_record(_count_eq(1), n),
            "p_geq_2": prob_record(_count_geq(2), n),
        },
    }


def _distribution_dossier_fielder(
    observations: list[dict], substitute_catches: int,
) -> dict:
    """Pure aggregate. Three count blocks + top-level scalars. The
    stumpings block is null when innings_kept == 0 (non-keepers).
    Spec §13.3."""
    n = len(observations)
    innings_kept = sum(o["kept_innings"] for o in observations)

    return {
        "n_matches": n,
        "innings_kept": innings_kept,
        "substitute_catches": substitute_catches,
        "observations": [
            {
                "match_id": o["match_id"],
                "date": o["date"],
                "catches": o["catches"],
                "run_outs": o["run_outs"],
                "stumpings": o["stumpings"],
                "is_keeper": o["is_keeper"],
            }
            for o in observations
        ],
        "catches": _count_block(observations, "catches"),
        "run_outs": _count_block(observations, "run_outs"),
        "stumpings": _count_block(observations, "stumpings") if innings_kept > 0 else None,
    }


def _form_windows_fielder(
    observations: list[dict], substitute_catches_total: int, today: date,
) -> dict:
    """Slice the date-asc observation list into four match-grain form
    windows, run the dossier on each, emit the fielder-specific delta
    block (three means per window, stumpings nullable). Spec §13.4.

    Substitute-catches scalar inside form windows is derived as the
    fraction of the lifetime total proportional to the window's
    n_matches share — substitutes are rare (≤ a handful per career)
    and per-match attribution would require a second filtered query
    per window. The dossier-level scalar is the authoritative number;
    form-window values are informational only.
    """
    last_10 = observations[-10:]
    cutoff_60d = (today - timedelta(days=60)).isoformat()
    cutoff_6mo = (today - timedelta(days=180)).isoformat()
    cutoff_1yr = (today - timedelta(days=365)).isoformat()
    last_60d = [o for o in observations if (o["date"] or "") >= cutoff_60d]
    last_6mo = [o for o in observations if (o["date"] or "") >= cutoff_6mo]
    last_1yr = [o for o in observations if (o["date"] or "") >= cutoff_1yr]

    # Form-window subs scalar: proportional share. Lifetime carries the
    # authoritative count.
    n_total = len(observations)
    def _sub_share(window_obs: list[dict]) -> int:
        if n_total == 0 or substitute_catches_total == 0:
            return 0
        return round(substitute_catches_total * len(window_obs) / n_total)

    lifetime_doss = _distribution_dossier_fielder(observations, substitute_catches_total)
    last_10_doss = _distribution_dossier_fielder(last_10, _sub_share(last_10))
    last_60d_doss = _distribution_dossier_fielder(last_60d, _sub_share(last_60d))
    last_6mo_doss = _distribution_dossier_fielder(last_6mo, _sub_share(last_6mo))
    last_1yr_doss = _distribution_dossier_fielder(last_1yr, _sub_share(last_1yr))

    def _delta(window_doss: dict, key: str) -> Optional[float]:
        wb = window_doss.get(key)
        lb = lifetime_doss.get(key)
        if wb is None or lb is None:
            return None
        wv = wb.get("mean_per_match")
        lv = lb.get("mean_per_match")
        if wv is None or lv is None:
            return None
        return round(wv - lv, 4)

    delta = {}
    for win_name, win_doss in [
        ("last_10", last_10_doss),
        ("last_60d", last_60d_doss),
        ("last_6mo", last_6mo_doss),
        ("last_1yr", last_1yr_doss),
    ]:
        for metric in ("catches", "run_outs", "stumpings"):
            delta[f"{win_name}_{metric}_mean_minus_lifetime"] = _delta(win_doss, metric)

    return {
        "last_10": last_10_doss,
        "last_60d": last_60d_doss,
        "last_6mo": last_6mo_doss,
        "last_1yr": last_1yr_doss,
        "delta": delta,
    }


@router.get("/{person_id}/distribution")
async def fielding_distribution(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    as_of_date: Optional[str] = Query(
        None,
        description=(
            "ISO date (YYYY-MM-DD) to anchor the calendar form windows"
            " (last_60d / last_6mo / last_1yr). Defaults to today;"
            " pin for deterministic regression tests."
        ),
    ),
):
    """Per-match fielding distribution dossier.

    Returns three sibling count blocks under one master sample —
    `catches`, `run_outs`, and `stumpings` (null for non-keepers) —
    plus four form windows (last_10 / last_60d / last_6mo / last_1yr),
    a `substitute_catches` reconciliation scalar, and scope-derived
    suggested-splits navigation hints.

    Master sample is per-match (one row per match the player appears
    in `matchplayer`). Substitute catches are excluded from the
    distribution and surfaced separately. Caught-and-bowled is bowler-
    credited and lives on the bowling dossier.

    Every probability ships as `{value, num, denom, ci_low, ci_high}`
    with a Wilson 95% CI. Three simples per block: `p_zero`, `p_one`,
    `p_geq_2`.

    Spec: internal_docs/spec-distribution-stats.md §13.
    """
    db = get_db()
    today = date.fromisoformat(as_of_date) if as_of_date else date.today()

    observations, substitute_catches = await _match_master_sample_fielder(
        db, person_id, filters, aux,
    )
    lifetime = _distribution_dossier_fielder(observations, substitute_catches)
    form = _form_windows_fielder(observations, substitute_catches, today)

    scope = scope_dict_from_filters(filters)
    splits = suggested_splits(scope)

    return {
        "scope": {k: v for k, v in scope.items() if v},
        "lifetime": lifetime,
        "form": form,
        "suggested_splits": splits,
    }
