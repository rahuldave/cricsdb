"""Populate the player_scope_stats table — denormalized per-player aggregates.

See `internal_docs/spec-team-compare-average.md` for the full spec.
The table grain is one row per (person_id, scope_key), where scope_key
encodes (tournament || season || gender || team_type). Spec 1 populates
this table but does NOT consume it from any endpoint — it exists as
infrastructure for Spec 2 (cross-app comparisons), particularly
position-matched player compare.

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_player_scope_stats.py
    Truncates player_scope_stats and rebuilds from every regular innings.

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)
    Recomputes only the (person, scope_key) rows touched by the new
    matches. Reads the touched scopes from the new matches, then
    re-aggregates those scopes from scratch over all matches in scope
    (since scope-level aggregates are sums; recomputing the few
    affected (person, scope_key) cells is exact).

Called automatically by import_data.py (full) and update_recent.py
(incremental) after the partnership populate call.

Phase boundaries: powerplay = over 0-5, middle = 6-14, death = 15-19
(matches `api/routers/teams.py`).

Bowler `wickets` excludes run out / retired hurt / retired out /
obstructing the field (matches `api/routers/bowling.py`).

Position derivation: per innings, position 1 = striker on the first
delivery, position 2 = non_striker on the first delivery, position N
(N >= 3) = each subsequent newcomer in delivery order.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database
from models import (
    Person, Match, MatchPlayer, Innings, Delivery, Wicket,
    FieldingCredit, KeeperAssignment, Partnership, PlayerScopeStats,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")

BOWLER_WICKET_EXCLUDED = {
    "run out", "retired hurt", "retired out", "obstructing the field",
}
BATTER_DISMISSAL_EXCLUDED = {"retired hurt", "retired out"}


def make_scope_key(tournament: str | None, season: str, gender: str, team_type: str) -> str:
    """Stable hash of (tournament, season, gender, team_type).

    NULL tournament becomes the literal string '' so bilateral matches
    with no event_name still produce a stable key. The hash is short
    (12 hex chars) — collision risk is negligible at the cardinality we
    have (low thousands of distinct scopes).
    """
    raw = f"{tournament or ''}||{season}||{gender}||{team_type}"
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=6).hexdigest()


async def _ensure_tables(db, incremental: bool = False):
    """Register all tables with deebase so FK references resolve.

    In incremental mode, skip index creation (they already exist).
    """
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(MatchPlayer, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)
    await db.create(FieldingCredit, pk="id", if_not_exists=True)
    await db.create(KeeperAssignment, pk="id", if_not_exists=True)
    await db.create(Partnership, pk="id", if_not_exists=True)

    idx = {} if incremental else {
        "indexes": [
            ("scope_key", "avg_batting_position"),
            "scope_key",
        ],
    }
    return await db.create(
        PlayerScopeStats,
        pk=["person_id", "scope_key"],
        if_not_exists=True,
        **idx,
    )


# ============================================================
# Aggregation core
# ============================================================

# A "scope" is identified by (tournament, season, gender, team_type).
# Per (person, scope) we accumulate batting/bowling/fielding tallies
# and a per-position innings histogram.
class _Acc:
    __slots__ = (
        "tournament", "season", "gender", "team_type",
        "matches_set",
        "innings_batted_set", "runs", "legal_balls", "dots",
        "fours", "sixes", "dismissals",
        "position_sum", "position_innings",
        "innings_by_position",  # list[int], length 12
        "balls_bowled", "runs_conceded", "wickets",
        "bowling_dots", "boundaries_conceded",
        "powerplay_legal", "middle_legal", "death_legal",
        "catches", "runouts", "stumpings",
        "catches_as_keeper", "matches_as_keeper_set",
    )

    def __init__(self, tournament, season, gender, team_type):
        self.tournament = tournament
        self.season = season
        self.gender = gender
        self.team_type = team_type
        self.matches_set = set()
        self.innings_batted_set = set()
        self.runs = 0
        self.legal_balls = 0
        self.dots = 0
        self.fours = 0
        self.sixes = 0
        self.dismissals = 0
        self.position_sum = 0  # SUM(position_in_innings)
        self.position_innings = 0  # innings counted toward position avg
        self.innings_by_position = [0] * 12
        self.balls_bowled = 0
        self.runs_conceded = 0
        self.wickets = 0
        self.bowling_dots = 0
        self.boundaries_conceded = 0
        self.powerplay_legal = 0
        self.middle_legal = 0
        self.death_legal = 0
        self.catches = 0
        self.runouts = 0
        self.stumpings = 0
        self.catches_as_keeper = 0
        self.matches_as_keeper_set = set()

    def to_row(self, person_id: str, scope_key: str) -> dict:
        if self.position_innings > 0:
            avg_pos = self.position_sum / self.position_innings
        else:
            avg_pos = None
        return {
            "person_id": person_id,
            "scope_key": scope_key,
            "tournament": self.tournament,
            "season": self.season,
            "gender": self.gender,
            "team_type": self.team_type,
            "matches": len(self.matches_set),
            "innings_batted": len(self.innings_batted_set),
            "runs": self.runs,
            "legal_balls": self.legal_balls,
            "dots": self.dots,
            "fours": self.fours,
            "sixes": self.sixes,
            "dismissals": self.dismissals,
            "avg_batting_position": avg_pos,
            "innings_by_position_json": json.dumps(self.innings_by_position),
            "balls_bowled": self.balls_bowled,
            "runs_conceded": self.runs_conceded,
            "wickets": self.wickets,
            "bowling_dots": self.bowling_dots,
            "boundaries_conceded": self.boundaries_conceded,
            "powerplay_overs": round(self.powerplay_legal / 6.0, 2),
            "middle_overs": round(self.middle_legal / 6.0, 2),
            "death_overs": round(self.death_legal / 6.0, 2),
            "catches": self.catches,
            "runouts": self.runouts,
            "stumpings": self.stumpings,
            "catches_as_keeper": self.catches_as_keeper,
            "matches_as_keeper": len(self.matches_as_keeper_set),
        }


def _phase(over_number: int) -> str:
    if over_number <= 5:
        return "pp"
    if over_number <= 14:
        return "mid"
    return "death"


def _derive_positions(deliveries: list[dict]) -> dict[str, int]:
    """Return {person_id: position} for one innings, by delivery order.

    Position 1 = striker on first ball, position 2 = non_striker on
    first ball, then each new face in delivery order gets the next
    position. We only key by person_id (skip rows where it's NULL —
    those don't contribute to player_scope_stats anyway).
    """
    positions: dict[str, int] = {}
    next_pos = 1
    for d in deliveries:
        for pid in (d["batter_id"], d["non_striker_id"]):
            if pid is None:
                continue
            if pid not in positions:
                if next_pos > 11:
                    # Shouldn't happen in practice — 11 distinct batters
                    # per innings is the convention. Park the rest in
                    # bucket 11 (super-rare 12th-man-style edge cases).
                    positions[pid] = 11
                else:
                    positions[pid] = next_pos
                    next_pos += 1
    return positions


# ============================================================
# Full / scoped recompute over a set of matches
# ============================================================

async def _aggregate_matches(db, match_ids: list[int] | None) -> dict[tuple[str, str], _Acc]:
    """Aggregate stats keyed by (person_id, scope_key) over the given matches.

    If match_ids is None → aggregate over every regular match in the DB.
    """
    if match_ids is not None and not match_ids:
        return {}

    # Match metadata (tournament/season/gender/team_type) keyed by match id.
    if match_ids is None:
        match_rows = await db.q("""
            SELECT id, event_name AS tournament, season, gender, team_type
            FROM match
        """)
    else:
        id_list = ",".join(str(m) for m in match_ids)
        match_rows = await db.q(f"""
            SELECT id, event_name AS tournament, season, gender, team_type
            FROM match
            WHERE id IN ({id_list})
        """)
    match_meta: dict[int, dict] = {}
    for r in match_rows:
        match_meta[r["id"]] = {
            "tournament": r["tournament"],
            "season": r["season"] or "",
            "gender": r["gender"] or "",
            "team_type": r["team_type"] or "",
            "scope_key": make_scope_key(
                r["tournament"], r["season"] or "",
                r["gender"] or "", r["team_type"] or "",
            ),
        }

    if not match_meta:
        return {}

    accs: dict[tuple[str, str], _Acc] = {}

    def get_acc(person_id: str, match_id: int) -> _Acc:
        m = match_meta[match_id]
        key = (person_id, m["scope_key"])
        acc = accs.get(key)
        if acc is None:
            acc = _Acc(m["tournament"], m["season"], m["gender"], m["team_type"])
            accs[key] = acc
        return acc

    # ------------------------------------------------------------
    # Matches in XI (matchplayer drives `matches`).
    # ------------------------------------------------------------
    mid_list = ",".join(str(i) for i in match_meta.keys())
    mp_rows = await db.q(f"""
        SELECT match_id, person_id
        FROM matchplayer
        WHERE person_id IS NOT NULL
          AND match_id IN ({mid_list})
    """)
    for r in mp_rows:
        get_acc(r["person_id"], r["match_id"]).matches_set.add(r["match_id"])

    # ------------------------------------------------------------
    # Innings list (regular innings only).
    # ------------------------------------------------------------
    innings_rows = await db.q(f"""
        SELECT id, match_id
        FROM innings
        WHERE super_over = 0
          AND match_id IN ({mid_list})
    """)
    innings_ids = [r["id"] for r in innings_rows]
    innings_match: dict[int, int] = {r["id"]: r["match_id"] for r in innings_rows}
    if not innings_ids:
        return accs

    iid_list_full = ",".join(str(i) for i in innings_ids)

    # ------------------------------------------------------------
    # Deliveries — chunked load to keep result sets bounded.
    # ------------------------------------------------------------
    chunk = 500
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        d_rows = await db.q(f"""
            SELECT id, innings_id, over_number, delivery_index,
                   batter_id, bowler_id, non_striker_id,
                   runs_batter, runs_total,
                   extras_wides, extras_noballs,
                   extras_byes, extras_legbyes, extras_penalty
            FROM delivery
            WHERE innings_id IN ({sub_list})
            ORDER BY innings_id, over_number, delivery_index, id
        """)
        deliveries_by_innings: dict[int, list[dict]] = defaultdict(list)
        for d in d_rows:
            deliveries_by_innings[d["innings_id"]].append(d)

        for iid in sub:
            ds = deliveries_by_innings.get(iid, [])
            if not ds:
                continue
            mid = innings_match[iid]
            positions = _derive_positions(ds)

            # Track the set of batters who actually faced ≥1 legal ball
            # this innings — those are the players who get an
            # innings_batted credit. Non-strikers who never faced a
            # ball still count for "batted" by convention; we record
            # them too.
            batters_appeared: set[str] = set()
            for pid in positions.keys():
                batters_appeared.add(pid)
                acc = get_acc(pid, mid)
                acc.innings_batted_set.add(iid)
                pos = positions[pid]
                acc.position_sum += pos
                acc.position_innings += 1
                if 1 <= pos <= 11:
                    acc.innings_by_position[pos] += 1
                else:
                    acc.innings_by_position[11] += 1

            # Per-delivery accumulation (batter side, bowler side).
            for d in ds:
                legal = (d["extras_wides"] == 0 and d["extras_noballs"] == 0)
                phase = _phase(d["over_number"])

                # Batter side. Only legal balls count as faced.
                bid = d["batter_id"]
                if bid is not None and legal:
                    acc = get_acc(bid, mid)
                    acc.legal_balls += 1
                    rb = d["runs_batter"]
                    acc.runs += rb
                    # Dot rule mirrors api/routers/batting.py: legal AND
                    # runs_batter=0 AND no extras. On a legal ball, no
                    # wides/noballs, so runs_total=0 implies runs_batter,
                    # byes, legbyes, penalty are all 0 — equivalent.
                    if rb == 0 and d["runs_total"] == 0:
                        acc.dots += 1
                    if rb == 4:
                        acc.fours += 1
                    elif rb == 6:
                        acc.sixes += 1

                # Bowler side.
                bow = d["bowler_id"]
                if bow is not None:
                    acc = get_acc(bow, mid)
                    if legal:
                        acc.balls_bowled += 1
                        if phase == "pp":
                            acc.powerplay_legal += 1
                        elif phase == "mid":
                            acc.middle_legal += 1
                        else:
                            acc.death_legal += 1
                    # Bowler runs conceded = runs_total minus byes,
                    # legbyes, penalty (matches existing bowling router
                    # gist — boundaries/conceded use runs_total, but
                    # for econ we exclude non-bowler extras). The
                    # spec field is `runs_conceded` — use the
                    # bowling-router default of SUM(runs_total)
                    # to stay consistent; bowling.py:68/93 use
                    # SUM(d.runs_total) for runs_conceded.
                    acc.runs_conceded += d["runs_total"]
                    rb = d["runs_batter"]
                    if rb == 0 and d["runs_total"] == 0:
                        acc.bowling_dots += 1
                    if rb == 4 or rb == 6:
                        acc.boundaries_conceded += 1

    # ------------------------------------------------------------
    # Wickets — batter dismissals + bowler wickets.
    # ------------------------------------------------------------
    chunk = 500
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        w_rows = await db.q(f"""
            SELECT w.id, w.delivery_id, w.kind, w.player_out_id,
                   d.bowler_id, d.innings_id
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            WHERE d.innings_id IN ({sub_list})
        """)
        for w in w_rows:
            mid = innings_match[w["innings_id"]]
            kind = w["kind"]
            # Batter dismissals.
            pout = w["player_out_id"]
            if pout is not None and kind not in BATTER_DISMISSAL_EXCLUDED:
                get_acc(pout, mid).dismissals += 1
            # Bowler wickets.
            bow = w["bowler_id"]
            if bow is not None and kind not in BOWLER_WICKET_EXCLUDED:
                get_acc(bow, mid).wickets += 1

    # ------------------------------------------------------------
    # Fielding credits (catches, runouts, stumpings, c+b).
    # ------------------------------------------------------------
    chunk = 500
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        fc_rows = await db.q(f"""
            SELECT fc.fielder_id, fc.kind, d.innings_id
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            WHERE fc.fielder_id IS NOT NULL
              AND d.innings_id IN ({sub_list})
        """)
        for fc in fc_rows:
            mid = innings_match[fc["innings_id"]]
            acc = get_acc(fc["fielder_id"], mid)
            kind = fc["kind"]
            if kind in ("caught", "caught_and_bowled"):
                acc.catches += 1
            elif kind == "stumped":
                acc.stumpings += 1
            elif kind == "run_out":
                acc.runouts += 1

    # ------------------------------------------------------------
    # Keeper assignments → catches_as_keeper + matches_as_keeper.
    # catches_as_keeper := catches taken (caught only, not c&b) by
    # the designated keeper of the innings they took it in.
    # matches_as_keeper := distinct matches the person was the
    # designated keeper for at least one innings.
    # ------------------------------------------------------------
    ka_rows = await db.q(f"""
        SELECT ka.innings_id, ka.keeper_id
        FROM keeperassignment ka
        WHERE ka.keeper_id IS NOT NULL
          AND ka.innings_id IN ({iid_list_full})
    """)
    keeper_by_innings: dict[int, str] = {r["innings_id"]: r["keeper_id"] for r in ka_rows}
    if keeper_by_innings:
        for iid, kpid in keeper_by_innings.items():
            mid = innings_match[iid]
            get_acc(kpid, mid).matches_as_keeper_set.add(mid)

        # Catches-as-keeper: join fielding_credit (kind=caught) where
        # fielder_id == keeper_by_innings[innings_id].
        ki_list = ",".join(str(i) for i in keeper_by_innings.keys())
        fc_rows = await db.q(f"""
            SELECT fc.fielder_id, d.innings_id
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            WHERE fc.kind = 'caught'
              AND fc.fielder_id IS NOT NULL
              AND d.innings_id IN ({ki_list})
        """)
        for r in fc_rows:
            iid = r["innings_id"]
            kpid = keeper_by_innings.get(iid)
            if kpid is not None and r["fielder_id"] == kpid:
                mid = innings_match[iid]
                get_acc(kpid, mid).catches_as_keeper += 1

    return accs


# ============================================================
# Write paths
# ============================================================

async def _flush(db, table, rows: list[dict]) -> int:
    if not rows:
        return 0
    sa_table = table.sa_table
    async with db._engine.begin() as conn:
        await conn.execute(sa_table.insert(), rows)
    return len(rows)


async def populate_full(db) -> int:
    """Truncate player_scope_stats and rebuild from every regular match."""
    print("Populating player_scope_stats (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='playerscopestats'"
    )
    table_exists = len(existing) > 0
    table = await _ensure_tables(db, incremental=table_exists)
    if table_exists:
        await db.q("DELETE FROM playerscopestats")

    # Aggregate over the universe.
    print("  scanning all matches…")
    accs = await _aggregate_matches(db, match_ids=None)
    print(f"  {len(accs)} (person, scope_key) cells aggregated")

    rows: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key), acc in accs.items():
        rows.append(acc.to_row(person_id, scope_key))
        if len(rows) >= batch:
            total += await _flush(db, table, rows)
            rows = []
    total += await _flush(db, table, rows)

    elapsed = time.time() - start
    print(f"  Inserted {total} rows in {elapsed:.1f}s")
    return total


async def populate_incremental(db, new_match_ids: list[int]) -> int:
    """Recompute player_scope_stats rows touched by the new matches.

    Strategy: identify the set of scope_keys touched by the new
    matches; for each touched scope, find ALL matches in that scope
    (not just the new ones), recompute the per-(person, scope_key)
    aggregates from scratch over that set, delete the old rows for
    that scope_key, and insert the fresh ones. This is exact and
    avoids the trickier "in-place upsert with deltas" path (where a
    match correction would cause drift).
    """
    if not new_match_ids:
        print("player_scope_stats: no new matches, skipping")
        return 0

    print(f"Populating player_scope_stats for {len(new_match_ids)} new matches…")
    table = await _ensure_tables(db, incremental=True)

    # Determine touched scopes.
    id_list = ",".join(str(m) for m in new_match_ids)
    rows = await db.q(f"""
        SELECT DISTINCT event_name AS tournament, season, gender, team_type
        FROM match
        WHERE id IN ({id_list})
    """)
    touched_scopes: list[tuple[str | None, str, str, str]] = [
        (r["tournament"], r["season"] or "", r["gender"] or "", r["team_type"] or "")
        for r in rows
    ]
    if not touched_scopes:
        print("  no scopes resolved, skipping")
        return 0

    scope_keys = [make_scope_key(*s) for s in touched_scopes]
    print(f"  {len(scope_keys)} scopes touched")

    # Find every match in each touched scope.
    where_parts = []
    params: dict = {}
    for i, (tn, se, ge, tt) in enumerate(touched_scopes):
        if tn is None:
            tn_clause = "event_name IS NULL"
        else:
            tn_clause = f"event_name = :tn{i}"
            params[f"tn{i}"] = tn
        where_parts.append(
            f"({tn_clause} AND season = :se{i} AND gender = :ge{i} AND team_type = :tt{i})"
        )
        params[f"se{i}"] = se
        params[f"ge{i}"] = ge
        params[f"tt{i}"] = tt
    where_sql = " OR ".join(where_parts)
    match_rows = await db.q(f"SELECT id FROM match WHERE {where_sql}", params)
    affected_match_ids = [r["id"] for r in match_rows]
    print(f"  {len(affected_match_ids)} total matches in touched scopes")

    # Recompute over all affected matches.
    accs = await _aggregate_matches(db, match_ids=affected_match_ids)

    # Delete old rows for every touched scope_key, then insert fresh.
    sk_list = ",".join(f"'{sk}'" for sk in scope_keys)
    deleted_rows = await db.q(
        f"SELECT COUNT(*) AS c FROM playerscopestats WHERE scope_key IN ({sk_list})"
    )
    old_count = deleted_rows[0]["c"] if deleted_rows else 0
    await db.q(f"DELETE FROM playerscopestats WHERE scope_key IN ({sk_list})")

    rows_to_insert: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key), acc in accs.items():
        if scope_key not in scope_keys:
            # Defensive — shouldn't happen because we filtered matches
            # by touched scopes.
            continue
        rows_to_insert.append(acc.to_row(person_id, scope_key))
        if len(rows_to_insert) >= batch:
            total += await _flush(db, table, rows_to_insert)
            rows_to_insert = []
    total += await _flush(db, table, rows_to_insert)

    print(f"  player_scope_stats: replaced {old_count} rows with {total}")
    return total


async def main():
    argparse.ArgumentParser(description="Populate player_scope_stats").parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
