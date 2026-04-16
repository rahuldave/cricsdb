"""Keeping analytics router — Tier 2 of fielding.

Uses the `keeper_assignment` table (populated by
scripts/populate_keeper_assignments.py) to expose keeper-specific
stats. See docs/spec-fielding-tier2.md for the algorithm + data model.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_db
from ..filters import FilterParams

router = APIRouter(prefix="/api/v1/fielders", tags=["Keeping"])


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


def _parse_json_list(val) -> list[str]:
    """`candidate_ids_json` may arrive as a list (deebase-decoded) or
    as a JSON string (depending on sqlite driver path). Normalize."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def _keeping_filter(filters: FilterParams, person_id: str) -> tuple[str, dict]:
    """WHERE clause for keeper_assignment queries — joins through
    innings → match so the standard filter params apply.

    side-neutral: keeperassignment's innings live in opponent-batting
    innings (keeper is in the field while opponent bats), so we can't
    use FilterParams' default `i.team = :team`.
    """
    where, params = filters.build_side_neutral(has_innings_join=True)
    params["person_id"] = person_id
    parts = ["ka.keeper_id = :person_id"]
    if where:
        parts.append(where)
    return " AND ".join(parts), params


# ============================================================
# Summary
# ============================================================


@router.get("/{person_id}/keeping/summary")
async def keeping_summary(
    person_id: str,
    filters: FilterParams = Depends(),
):
    db = get_db()

    name_rows = await db.q(
        "SELECT name FROM person WHERE id = :pid", {"pid": person_id}
    )
    name = name_rows[0]["name"] if name_rows else person_id

    where, params = _keeping_filter(filters, person_id)

    # Innings count + confidence breakdown
    conf_rows = await db.q(
        f"""
        SELECT ka.confidence, COUNT(*) as c
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY ka.confidence
        """,
        params,
    )
    by_conf = {r["confidence"]: r["c"] for r in conf_rows if r["confidence"]}
    innings_kept = sum(by_conf.values())

    # Stumpings, keeping catches, run outs while keeping (joined through fielding_credit)
    fc_rows = await db.q(
        f"""
        SELECT fc.kind, COUNT(*) as c
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN delivery d ON d.innings_id = i.id
        JOIN fieldingcredit fc ON fc.delivery_id = d.id
                               AND fc.fielder_id = ka.keeper_id
        WHERE {where}
        GROUP BY fc.kind
        """,
        params,
    )
    fc_counts = {r["kind"]: r["c"] for r in fc_rows}
    stumpings = fc_counts.get("stumped", 0)
    keeping_catches = fc_counts.get("caught", 0) + fc_counts.get("caught_and_bowled", 0)
    run_outs = fc_counts.get("run_out", 0)

    # Byes conceded — sum delivery.extras_byes across innings this person kept
    byes_rows = await db.q(
        f"""
        SELECT COALESCE(SUM(d.extras_byes), 0) as byes
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN delivery d ON d.innings_id = i.id
        WHERE {where}
        """,
        params,
    )
    byes_conceded = byes_rows[0]["byes"] or 0

    # Ambiguous innings where this person is a candidate
    # (filters apply through the innings→match join). side-neutral
    # because keeper-side innings live in opponent-batting rows.
    amb_where, amb_params = filters.build_side_neutral(has_innings_join=True)
    amb_params["person_id"] = person_id
    amb_parts = [
        "ka.keeper_id IS NULL",
        "ka.candidate_ids_json LIKE '%' || :person_id || '%'",
    ]
    if amb_where:
        amb_parts.append(amb_where)
    amb_clause = " AND ".join(amb_parts)
    amb_rows = await db.q(
        f"""
        SELECT COUNT(*) as c
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {amb_clause}
        """,
        amb_params,
    )
    ambiguous_innings = amb_rows[0]["c"]

    dismissals = stumpings + keeping_catches + run_outs

    return {
        "person_id": person_id,
        "name": name,
        "innings_kept": innings_kept,
        "innings_kept_by_confidence": {
            "definitive": by_conf.get("definitive", 0),
            "high": by_conf.get("high", 0),
            "medium": by_conf.get("medium", 0),
            "low": by_conf.get("low", 0),
        },
        "stumpings": stumpings,
        "keeping_catches": keeping_catches,
        "run_outs_while_keeping": run_outs,
        "byes_conceded": byes_conceded,
        "byes_per_innings": _safe_div(byes_conceded, innings_kept),
        "dismissals_while_keeping": dismissals,
        "keeping_dismissals_per_innings": _safe_div(dismissals, innings_kept),
        "ambiguous_innings": ambiguous_innings,
    }


# ============================================================
# By-season
# ============================================================


@router.get("/{person_id}/keeping/by-season")
async def keeping_by_season(
    person_id: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    where, params = _keeping_filter(filters, person_id)

    # Innings kept per season
    inn_rows = await db.q(
        f"""
        SELECT m.season, COUNT(*) as innings_kept
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        """,
        params,
    )
    by_season: dict[str, dict[str, Any]] = {
        r["season"]: {
            "season": r["season"],
            "innings_kept": r["innings_kept"],
            "stumpings": 0, "keeping_catches": 0, "run_outs_while_keeping": 0,
            "byes_conceded": 0,
        }
        for r in inn_rows
    }

    # Fielding credits while keeping, per season+kind
    fc_rows = await db.q(
        f"""
        SELECT m.season, fc.kind, COUNT(*) as c
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN delivery d ON d.innings_id = i.id
        JOIN fieldingcredit fc ON fc.delivery_id = d.id
                               AND fc.fielder_id = ka.keeper_id
        WHERE {where}
        GROUP BY m.season, fc.kind
        """,
        params,
    )
    for r in fc_rows:
        season = r["season"]
        if season not in by_season:
            continue
        if r["kind"] == "stumped":
            by_season[season]["stumpings"] += r["c"]
        elif r["kind"] in ("caught", "caught_and_bowled"):
            by_season[season]["keeping_catches"] += r["c"]
        elif r["kind"] == "run_out":
            by_season[season]["run_outs_while_keeping"] += r["c"]

    # Byes per season
    byes_rows = await db.q(
        f"""
        SELECT m.season, COALESCE(SUM(d.extras_byes), 0) as byes
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN delivery d ON d.innings_id = i.id
        WHERE {where}
        GROUP BY m.season
        """,
        params,
    )
    for r in byes_rows:
        if r["season"] in by_season:
            by_season[r["season"]]["byes_conceded"] = r["byes"]

    out = sorted(by_season.values(), key=lambda r: r["season"])
    for r in out:
        r["total_dismissals"] = (
            r["stumpings"] + r["keeping_catches"] + r["run_outs_while_keeping"]
        )
    return {"by_season": out}


# ============================================================
# By-innings (match-by-match log)
# ============================================================


@router.get("/{person_id}/keeping/by-innings")
async def keeping_by_innings(
    person_id: str,
    filters: FilterParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    where, params = _keeping_filter(filters, person_id)
    params["limit"] = limit
    params["offset"] = offset

    total_rows = await db.q(
        f"""
        SELECT COUNT(*) as total
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    total = total_rows[0]["total"]

    # One row per innings with per-innings stumpings, catches, byes, confidence
    rows = await db.q(
        f"""
        SELECT
            ka.innings_id, ka.confidence, ka.method,
            i.match_id, i.innings_number, i.team as batting_team,
            m.team1, m.team2, m.event_name as tournament,
            (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
            (SELECT COUNT(*) FROM fieldingcredit fc
              JOIN delivery d ON d.id = fc.delivery_id
              WHERE d.innings_id = i.id AND fc.fielder_id = ka.keeper_id
                AND fc.kind = 'stumped') as stumpings,
            (SELECT COUNT(*) FROM fieldingcredit fc
              JOIN delivery d ON d.id = fc.delivery_id
              WHERE d.innings_id = i.id AND fc.fielder_id = ka.keeper_id
                AND fc.kind IN ('caught', 'caught_and_bowled')) as catches,
            (SELECT COUNT(*) FROM fieldingcredit fc
              JOIN delivery d ON d.id = fc.delivery_id
              WHERE d.innings_id = i.id AND fc.fielder_id = ka.keeper_id
                AND fc.kind = 'run_out') as run_outs,
            (SELECT COALESCE(SUM(d.extras_byes), 0) FROM delivery d
              WHERE d.innings_id = i.id) as byes
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        ORDER BY date DESC, ka.innings_id DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    innings_out = []
    for r in rows:
        opponent = r["team2"] if r["batting_team"] == r["team1"] else r["team1"]
        # batting_team is the OPPOSING team (they were batting, our keeper was fielding)
        innings_out.append({
            "match_id": r["match_id"],
            "innings_number": r["innings_number"],
            "date": r["date"],
            "opponent": r["batting_team"],  # the batting side = the opponent's batters
            "tournament": r["tournament"],
            "confidence": r["confidence"],
            "method": r["method"],
            "stumpings": r["stumpings"],
            "catches": r["catches"],
            "run_outs": r["run_outs"],
            "byes": r["byes"],
            "total_dismissals": r["stumpings"] + r["catches"] + r["run_outs"],
        })

    return {"innings": innings_out, "total": total}


# ============================================================
# Ambiguous innings where this person is a candidate
# ============================================================


@router.get("/{person_id}/keeping/ambiguous")
async def keeping_ambiguous(
    person_id: str,
    filters: FilterParams = Depends(),
    limit: int = Query(100, ge=1, le=500),
):
    db = get_db()
    # side-neutral: ambiguous-keeper innings are opponent-batting.
    where, params = filters.build_side_neutral(has_innings_join=True)
    params["person_id"] = person_id
    params["limit"] = limit
    parts = [
        "ka.keeper_id IS NULL",
        "ka.candidate_ids_json LIKE '%' || :person_id || '%'",
    ]
    if where:
        parts.append(where)
    clause = " AND ".join(parts)

    rows = await db.q(
        f"""
        SELECT
            ka.innings_id, ka.ambiguous_reason, ka.candidate_ids_json,
            i.match_id, i.innings_number, i.team as batting_team,
            m.team1, m.team2, m.event_name as tournament, m.season,
            (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {clause}
        ORDER BY date DESC, ka.innings_id DESC
        LIMIT :limit
        """,
        params,
    )

    # Gather all candidate person_ids to batch-lookup their names
    all_cand_ids: set[str] = set()
    decoded_rows = []
    for r in rows:
        cands = _parse_json_list(r["candidate_ids_json"])
        # Safety filter: LIKE may match substrings — only keep rows that
        # genuinely have this person in the candidate list.
        if person_id not in cands:
            continue
        all_cand_ids.update(cands)
        decoded_rows.append((r, cands))

    name_map: dict[str, str] = {}
    if all_cand_ids:
        placeholders = ",".join(f"'{pid}'" for pid in all_cand_ids)
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({placeholders})"
        )
        name_map = {r["id"]: r["name"] for r in name_rows}

    innings = []
    for r, cands in decoded_rows:
        fielding_team = r["team2"] if r["batting_team"] == r["team1"] else r["team1"]
        cand_names = [name_map.get(cid, cid) for cid in cands]
        innings.append({
            "match_id": r["match_id"],
            "innings_id": r["innings_id"],
            "innings_number": r["innings_number"],
            "date": r["date"],
            "tournament": r["tournament"],
            "season": r["season"],
            "fielding_team": fielding_team,
            "opponent": r["batting_team"],
            "ambiguous_reason": r["ambiguous_reason"],
            "candidate_ids": cands,
            "candidate_names": cand_names,
        })

    return {"innings": innings, "total": len(innings)}
