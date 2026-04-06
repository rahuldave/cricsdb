"""Matches router — match list + Cricinfo-style scorecard."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_db
from ..filters import FilterParams

router = APIRouter(prefix="/api/v1/matches", tags=["Matches"])


# ---------- helpers ----------

# Wicket kinds that don't credit the bowler
NON_BOWLER_WICKETS = {
    "run out",
    "retired hurt",
    "retired out",
    "obstructing the field",
}


def _balls_to_overs(balls: int) -> str:
    return f"{balls // 6}.{balls % 6}"


def _build_dismissal_text(
    kind: str,
    fielders_json: Optional[str],
    bowler: Optional[str],
) -> str:
    fielders = []
    if fielders_json:
        try:
            raw = json.loads(fielders_json)
            # The fielders column happens to be double-JSON-encoded (the import
            # path json.dumps'd a value that deebase also serialized).
            if isinstance(raw, str):
                raw = json.loads(raw)
            for f in raw or []:
                if isinstance(f, dict):
                    n = f.get("name")
                    if n:
                        fielders.append(n)
                elif isinstance(f, str):
                    fielders.append(f)
        except Exception:
            pass

    k = (kind or "").lower()
    if k == "bowled":
        return f"b {bowler}" if bowler else "bowled"
    if k == "lbw":
        return f"lbw b {bowler}" if bowler else "lbw"
    if k == "caught":
        if fielders and bowler and fielders[0] == bowler:
            return f"c & b {bowler}"
        if fielders:
            return f"c {fielders[0]} b {bowler}" if bowler else f"c {fielders[0]}"
        return f"c & b {bowler}" if bowler else "caught"
    if k == "caught and bowled":
        return f"c & b {bowler}" if bowler else "c & b"
    if k == "stumped":
        keeper = fielders[0] if fielders else "?"
        return f"st {keeper} b {bowler}" if bowler else f"st {keeper}"
    if k == "run out":
        if fielders:
            return f"run out ({'/'.join(fielders)})"
        return "run out"
    if k == "hit wicket":
        return f"hit wicket b {bowler}" if bowler else "hit wicket"
    if k == "retired hurt":
        return "retired hurt"
    if k == "retired out":
        return "retired out"
    if k == "obstructing the field":
        return "obstructing the field"
    if k == "handled the ball":
        return "handled the ball"
    if k == "timed out":
        return "timed out"
    return kind or "out"


def _result_text(m: dict) -> str:
    """Build a human-readable result line from a match row."""
    winner = m.get("outcome_winner")
    by_runs = m.get("outcome_by_runs")
    by_wkts = m.get("outcome_by_wickets")
    result = m.get("outcome_result")
    method = m.get("outcome_method")
    eliminator = m.get("outcome_eliminator")

    suffix = f" ({method})" if method else ""

    if result == "tie":
        if eliminator:
            return f"Match tied ({eliminator} won the super over){suffix}"
        return f"Match tied{suffix}"
    if result == "no result":
        return "No result"
    if result == "draw":
        return "Match drawn"
    if winner and by_runs:
        return f"{winner} won by {by_runs} run{'s' if by_runs != 1 else ''}{suffix}"
    if winner and by_wkts:
        return f"{winner} won by {by_wkts} wicket{'s' if by_wkts != 1 else ''}{suffix}"
    if winner:
        return f"{winner} won{suffix}"
    return "Result unknown"


async def _innings_summary(db, innings_id: int) -> dict:
    """Return total_runs, wickets, balls (legal), and team for one innings."""
    rows = await db.q(
        """
        SELECT
            i.team as team,
            COALESCE(SUM(d.runs_total), 0) as total_runs,
            COALESCE(SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                              THEN 1 ELSE 0 END), 0) as legal_balls
        FROM innings i
        LEFT JOIN delivery d ON d.innings_id = i.id
        WHERE i.id = :iid
        GROUP BY i.id, i.team
        """,
        {"iid": innings_id},
    )
    if not rows:
        return {"team": "", "total_runs": 0, "wickets": 0, "legal_balls": 0}
    row = rows[0]

    wkt_rows = await db.q(
        """
        SELECT COUNT(*) as c FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        WHERE d.innings_id = :iid
        """,
        {"iid": innings_id},
    )
    wickets = wkt_rows[0]["c"] if wkt_rows else 0
    return {
        "team": row["team"],
        "total_runs": row["total_runs"],
        "wickets": wickets,
        "legal_balls": row["legal_balls"],
    }


# ---------- endpoints ----------


@router.get("")
async def list_matches(
    filters: FilterParams = Depends(),
    team: Optional[str] = Query(None),
    player_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    where, params = filters.build(has_innings_join=False)
    clauses = [where] if where else []

    if team:
        clauses.append("(m.team1 = :team OR m.team2 = :team)")
        params["team"] = team
    if player_id:
        clauses.append(
            "EXISTS (SELECT 1 FROM matchplayer mp "
            "WHERE mp.match_id = m.id AND mp.person_id = :player_id)"
        )
        params["player_id"] = player_id

    where_sql = " AND ".join(clauses) if clauses else "1=1"

    count_rows = await db.q(
        f"SELECT COUNT(*) as c FROM match m WHERE {where_sql}", params
    )
    total = count_rows[0]["c"] if count_rows else 0

    params["limit"] = limit
    params["offset"] = offset
    rows = await db.q(
        f"""
        SELECT
            m.id as match_id,
            (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) as date,
            m.team1, m.team2,
            m.venue, m.city,
            m.event_name as tournament,
            m.season,
            m.outcome_winner,
            m.outcome_by_runs,
            m.outcome_by_wickets,
            m.outcome_result,
            m.outcome_method,
            m.outcome_eliminator
        FROM match m
        WHERE {where_sql}
        ORDER BY date DESC, m.id DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    if not rows:
        return {"matches": [], "total": total}

    # Per-match innings rollup (one query for all match_ids on this page)
    match_ids = [r["match_id"] for r in rows]
    placeholders = ",".join(f":id{i}" for i in range(len(match_ids)))
    id_params = {f"id{i}": mid for i, mid in enumerate(match_ids)}

    inn_rows = await db.q(
        f"""
        SELECT
            i.match_id,
            i.id as innings_id,
            i.innings_number,
            i.team,
            i.super_over,
            COALESCE(SUM(d.runs_total), 0) as total_runs,
            COALESCE(SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                              THEN 1 ELSE 0 END), 0) as legal_balls
        FROM innings i
        LEFT JOIN delivery d ON d.innings_id = i.id
        WHERE i.match_id IN ({placeholders})
          AND i.super_over = 0
        GROUP BY i.id
        ORDER BY i.match_id, i.innings_number
        """,
        id_params,
    )

    # Per-innings wicket counts
    wkt_rows = await db.q(
        f"""
        SELECT d.innings_id, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        WHERE i.match_id IN ({placeholders}) AND i.super_over = 0
        GROUP BY d.innings_id
        """,
        id_params,
    )
    wickets_by_innings = {r["innings_id"]: r["wickets"] for r in wkt_rows}

    # Bucket innings rollups by match → team
    rollup: dict[int, dict[str, str]] = {mid: {} for mid in match_ids}
    for ir in inn_rows:
        wkts = wickets_by_innings.get(ir["innings_id"], 0)
        score = (
            f"{ir['total_runs']}/{wkts} ({_balls_to_overs(ir['legal_balls'])})"
        )
        rollup[ir["match_id"]][ir["team"]] = score

    matches = []
    for r in rows:
        scores = rollup.get(r["match_id"], {})
        matches.append({
            "match_id": r["match_id"],
            "date": r["date"],
            "team1": r["team1"],
            "team2": r["team2"],
            "venue": r["venue"],
            "city": r["city"],
            "tournament": r["tournament"],
            "season": r["season"],
            "winner": r["outcome_winner"],
            "result_text": _result_text(r),
            "team1_score": scores.get(r["team1"]),
            "team2_score": scores.get(r["team2"]),
        })

    return {"matches": matches, "total": total}


@router.get("/{match_id}/scorecard")
async def scorecard(match_id: int):
    db = get_db()

    match_rows = await db.q(
        """
        SELECT m.*,
               (SELECT GROUP_CONCAT(date, ',') FROM matchdate
                WHERE match_id = m.id) as date_csv
        FROM match m WHERE m.id = :mid
        """,
        {"mid": match_id},
    )
    if not match_rows:
        raise HTTPException(status_code=404, detail="match not found")
    m = match_rows[0]

    dates = (m["date_csv"] or "").split(",") if m.get("date_csv") else []

    pom_raw = m.get("player_of_match")
    try:
        pom = json.loads(pom_raw) if isinstance(pom_raw, str) else (pom_raw or [])
    except Exception:
        pom = []

    officials_raw = m.get("officials")
    try:
        officials = json.loads(officials_raw) if isinstance(officials_raw, str) else officials_raw
    except Exception:
        officials = None

    info = {
        "match_id": match_id,
        "teams": [m["team1"], m["team2"]],
        "venue": m.get("venue"),
        "city": m.get("city"),
        "dates": dates,
        "tournament": m.get("event_name"),
        "season": m.get("season"),
        "match_number": m.get("event_match_number"),
        "stage": m.get("event_stage"),
        "toss_winner": m.get("toss_winner"),
        "toss_decision": m.get("toss_decision"),
        "result_text": _result_text(m),
        "method": m.get("outcome_method"),
        "player_of_match": pom,
        "officials": officials,
        "gender": m.get("gender"),
        "team_type": m.get("team_type"),
    }

    innings_rows = await db.q(
        """
        SELECT id, innings_number, team, super_over
        FROM innings
        WHERE match_id = :mid
        ORDER BY innings_number
        """,
        {"mid": match_id},
    )

    innings_out = []
    for inn in innings_rows:
        innings_out.append(await _build_innings(db, match_id, inn))

    return {"info": info, "innings": innings_out}


async def _build_innings(db, match_id: int, inn: dict) -> dict:
    iid = inn["id"]
    team = inn["team"]
    is_super = bool(inn["super_over"])

    summary = await _innings_summary(db, iid)
    legal_balls = summary["legal_balls"]
    overs_str = _balls_to_overs(legal_balls)
    total = summary["total_runs"]
    wkts = summary["wickets"]
    rr = round(total * 6 / legal_balls, 2) if legal_balls else 0.0

    # ---- Batting ----
    bat_rows = await db.q(
        """
        SELECT
            d.batter_id,
            d.batter,
            SUM(d.runs_batter) as runs,
            SUM(CASE WHEN d.extras_wides = 0 THEN 1 ELSE 0 END) as balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            MIN(d.id) as first_id
        FROM delivery d
        WHERE d.innings_id = :iid
        GROUP BY d.batter_id, d.batter
        ORDER BY first_id
        """,
        {"iid": iid},
    )

    # Dismissal lookup per batter
    dismissals = await db.q(
        """
        SELECT w.player_out, w.kind, w.fielders, d.bowler, d.bowler_id
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        WHERE d.innings_id = :iid
        """,
        {"iid": iid},
    )
    dismissal_by_name = {d["player_out"]: d for d in dismissals}

    batting = []
    for b in bat_rows:
        dismissal_row = dismissal_by_name.get(b["batter"])
        bowler_id = None
        if dismissal_row:
            text = _build_dismissal_text(
                dismissal_row["kind"],
                dismissal_row["fielders"],
                dismissal_row["bowler"],
            )
            # Only attribute the bowler when the dismissal kind credits one
            # — same exclusion list used in bowling figures.
            if (dismissal_row["kind"] or "").lower() not in NON_BOWLER_WICKETS:
                bowler_id = dismissal_row["bowler_id"]
        else:
            text = "not out"
        sr = round(b["runs"] * 100 / b["balls"], 2) if b["balls"] else 0.0
        batting.append({
            "person_id": b["batter_id"],
            "name": b["batter"],
            "dismissal": text,
            "dismissal_bowler_id": bowler_id,
            "runs": b["runs"],
            "balls": b["balls"],
            "fours": b["fours"],
            "sixes": b["sixes"],
            "strike_rate": sr,
        })

    # Did not bat: matchplayer (for this team) minus everyone who appeared
    appeared_rows = await db.q(
        """
        SELECT DISTINCT name FROM (
            SELECT batter as name FROM delivery WHERE innings_id = :iid
            UNION
            SELECT non_striker as name FROM delivery WHERE innings_id = :iid
        )
        """,
        {"iid": iid},
    )
    appeared = {r["name"] for r in appeared_rows}
    team_players = await db.q(
        """
        SELECT player_name FROM matchplayer
        WHERE match_id = :mid AND team = :team
        """,
        {"mid": match_id, "team": team},
    )
    did_not_bat = [
        r["player_name"] for r in team_players
        if r["player_name"] not in appeared
    ]

    # Extras
    ex_rows = await db.q(
        """
        SELECT
            COALESCE(SUM(extras_byes), 0) as byes,
            COALESCE(SUM(extras_legbyes), 0) as legbyes,
            COALESCE(SUM(extras_wides), 0) as wides,
            COALESCE(SUM(extras_noballs), 0) as noballs,
            COALESCE(SUM(extras_penalty), 0) as penalty
        FROM delivery WHERE innings_id = :iid
        """,
        {"iid": iid},
    )
    ex = ex_rows[0] if ex_rows else {}
    extras = {
        "byes": ex.get("byes", 0),
        "legbyes": ex.get("legbyes", 0),
        "wides": ex.get("wides", 0),
        "noballs": ex.get("noballs", 0),
        "penalty": ex.get("penalty", 0),
    }
    extras["total"] = sum(extras.values())

    # Fall of wickets — running total over deliveries in order
    delivery_runs = await db.q(
        """
        SELECT id, runs_total, over_number, delivery_index
        FROM delivery WHERE innings_id = :iid ORDER BY id
        """,
        {"iid": iid},
    )
    wickets_in_order = await db.q(
        """
        SELECT w.player_out, d.id as delivery_id,
               d.over_number, d.delivery_index
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        WHERE d.innings_id = :iid
        ORDER BY d.id
        """,
        {"iid": iid},
    )

    running_total = 0
    cumulative_by_delivery = {}
    for d in delivery_runs:
        running_total += d["runs_total"] or 0
        cumulative_by_delivery[d["id"]] = running_total

    fall_of_wickets = []
    for idx, w in enumerate(wickets_in_order, start=1):
        score_at = cumulative_by_delivery.get(w["delivery_id"], 0)
        # over.ball uses 1-based over numbering for display
        over_ball = f"{(w['over_number'] or 0) + 1}.{(w['delivery_index'] or 0) + 1}"
        fall_of_wickets.append({
            "wicket": idx,
            "score": score_at,
            "batter": w["player_out"],
            "over_ball": over_ball,
        })

    # ---- Bowling ----
    bowl_rows = await db.q(
        """
        SELECT
            d.bowler_id,
            d.bowler,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) as legal_balls,
            SUM(d.runs_total) as runs,
            SUM(d.extras_wides) as wides,
            SUM(d.extras_noballs) as noballs,
            MIN(d.id) as first_id
        FROM delivery d
        WHERE d.innings_id = :iid
        GROUP BY d.bowler_id, d.bowler
        ORDER BY first_id
        """,
        {"iid": iid},
    )

    # Maidens per bowler
    maiden_rows = await db.q(
        """
        SELECT bowler_id, COUNT(*) as maidens FROM (
            SELECT bowler_id, over_number,
                   SUM(runs_batter + extras_wides + extras_noballs) as conceded
            FROM delivery
            WHERE innings_id = :iid
            GROUP BY bowler_id, over_number
        ) WHERE conceded = 0
        GROUP BY bowler_id
        """,
        {"iid": iid},
    )
    maidens_by_bowler = {r["bowler_id"]: r["maidens"] for r in maiden_rows}

    # Wickets per bowler (excluding non-bowler dismissal kinds)
    wkt_per_bowler = await db.q(
        """
        SELECT d.bowler_id, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        WHERE d.innings_id = :iid
          AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field')
        GROUP BY d.bowler_id
        """,
        {"iid": iid},
    )
    wkts_by_bowler = {r["bowler_id"]: r["wickets"] for r in wkt_per_bowler}

    bowling = []
    for b in bowl_rows:
        balls = b["legal_balls"] or 0
        runs = b["runs"] or 0
        econ = round(runs * 6 / balls, 2) if balls else 0.0
        bowling.append({
            "person_id": b["bowler_id"],
            "name": b["bowler"],
            "overs": _balls_to_overs(balls),
            "maidens": maidens_by_bowler.get(b["bowler_id"], 0),
            "runs": runs,
            "wickets": wkts_by_bowler.get(b["bowler_id"], 0),
            "econ": econ,
            "wides": b["wides"] or 0,
            "noballs": b["noballs"] or 0,
        })

    # ---- By-over progression (for worm + Manhattan) ----
    over_rows = await db.q(
        """
        SELECT
            d.over_number,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN EXISTS (SELECT 1 FROM wicket w WHERE w.delivery_id = d.id)
                     THEN 1 ELSE 0 END) as wickets
        FROM delivery d
        WHERE d.innings_id = :iid
        GROUP BY d.over_number
        ORDER BY d.over_number
        """,
        {"iid": iid},
    )
    cum = 0
    by_over = []
    for r in over_rows:
        cum += r["runs"] or 0
        by_over.append({
            "over": (r["over_number"] or 0) + 1,  # display as 1-indexed
            "runs": r["runs"] or 0,
            "wickets": r["wickets"] or 0,
            "cumulative": cum,
        })

    label = f"Super Over ({team})" if is_super else f"{team} Innings"

    return {
        "innings_number": inn["innings_number"],
        "team": team,
        "is_super_over": is_super,
        "label": label,
        "total_runs": total,
        "wickets": wkts,
        "overs": overs_str,
        "run_rate": rr,
        "batting": batting,
        "did_not_bat": did_not_bat,
        "extras": extras,
        "fall_of_wickets": fall_of_wickets,
        "bowling": bowling,
        "by_over": by_over,
    }


@router.get("/{match_id}/innings-grid")
async def innings_grid(match_id: int):
    """
    Per-delivery data for an innings, structured for the grid visualization
    where each row is a ball and each column is a batter (in order of
    appearance). The frontend uses this to render the InningsGridChart.
    """
    db = get_db()
    inns = await db.q(
        """
        SELECT id, innings_number, team, super_over
        FROM innings WHERE match_id = :mid
        ORDER BY innings_number
        """,
        {"mid": match_id},
    )
    if not inns:
        raise HTTPException(status_code=404, detail="match not found")

    out_innings = []
    for inn in inns:
        if inn["super_over"]:
            continue
        iid = inn["id"]

        deliveries = await db.q(
            """
            SELECT
                d.id as delivery_id,
                d.over_number,
                d.delivery_index,
                d.batter,
                d.bowler,
                d.non_striker,
                d.runs_batter,
                d.runs_extras,
                d.runs_total,
                d.extras_wides,
                d.extras_noballs,
                d.extras_byes,
                d.extras_legbyes
            FROM delivery d
            WHERE d.innings_id = :iid
            ORDER BY d.id
            """,
            {"iid": iid},
        )

        wickets = await db.q(
            """
            SELECT w.delivery_id, w.player_out, w.kind, w.fielders, d.bowler
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            WHERE d.innings_id = :iid
            """,
            {"iid": iid},
        )
        wkt_by_did = {w["delivery_id"]: w for w in wickets}

        # Build the ordered list of batters as they first appear (either as
        # batter or non-striker — non-striker covers the very first ball
        # where both openers are at the crease but only one faces).
        seen: list[str] = []
        seen_set: set[str] = set()
        for d in deliveries:
            for name in (d["batter"], d["non_striker"]):
                if name and name not in seen_set:
                    seen.append(name)
                    seen_set.add(name)

        rows = []
        cumulative = 0
        wickets_so_far = 0
        for d in deliveries:
            cumulative += d["runs_total"] or 0
            wkt = wkt_by_did.get(d["delivery_id"])
            if wkt:
                wickets_so_far += 1
            rows.append({
                "over_ball": f"{(d['over_number'] or 0) + 1}.{(d['delivery_index'] or 0) + 1}",
                "bowler": d["bowler"],
                "batter": d["batter"],
                "batter_index": seen.index(d["batter"]),
                "non_striker": d["non_striker"],
                "non_striker_index": seen.index(d["non_striker"])
                    if d["non_striker"] in seen_set else None,
                "runs_batter": d["runs_batter"] or 0,
                "runs_extras": d["runs_extras"] or 0,
                "runs_total": d["runs_total"] or 0,
                "extras_wides": d["extras_wides"] or 0,
                "extras_noballs": d["extras_noballs"] or 0,
                "extras_byes": d["extras_byes"] or 0,
                "extras_legbyes": d["extras_legbyes"] or 0,
                "cumulative_runs": cumulative,
                "cumulative_wickets": wickets_so_far,
                "wicket_kind": wkt["kind"] if wkt else None,
                "wicket_player_out": wkt["player_out"] if wkt else None,
                "wicket_player_out_index": seen.index(wkt["player_out"])
                    if wkt and wkt["player_out"] in seen_set else None,
                "wicket_text": _build_dismissal_text(
                    wkt["kind"], wkt["fielders"], wkt["bowler"]
                ) if wkt else None,
            })

        out_innings.append({
            "innings_number": inn["innings_number"],
            "team": inn["team"],
            "batters": seen,
            "deliveries": rows,
            "total_balls": len(rows),
            "total_runs": cumulative,
            "total_wickets": wickets_so_far,
        })

    return {"match_id": match_id, "innings": out_innings}
