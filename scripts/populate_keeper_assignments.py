"""Populate the keeper_assignment table — Tier 2 of fielding analytics.

Implements the 4-layer inference algorithm from
`docs/spec-fielding-tier2.md`:

    A — stumping this innings (definitive)
    B — exactly 1 season-candidate in XI (high)
    C — exactly 1 career N>=3 keeper in XI (medium)
    D — exactly 1 team-ever-keeper in XI (low)
    — otherwise ambiguous (NULL)

Ambiguous rows get exported to a date-partitioned CSV at
`docs/keeper-ambiguous/<YYYY-MM-DD>.csv`. Each innings_id appears in
exactly one partition — the run that first discovered it as
ambiguous. Later runs never move a row between partitions. Manual
resolutions live in the `resolved_keeper_id` column of those CSVs and
are applied by `scripts/apply_keeper_resolutions.py` (which also runs
at the end of populate_full / populate_incremental so corrections
persist across rebuilds).

Usage (standalone):
    uv run python scripts/populate_keeper_assignments.py
    uv run python scripts/populate_keeper_assignments.py --show-ambiguous-sample

Usage (library — called from import_data.py and update_recent.py):
    from scripts.populate_keeper_assignments import populate_full, populate_incremental
    await populate_full(db)
    await populate_incremental(db, new_match_ids)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import glob
import json
import os
import sys
import time
from collections import defaultdict
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database
from models import (
    Person, Match, MatchPlayer, Innings, Delivery, Wicket,
    FieldingCredit, KeeperAssignment,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")
PARTITION_DIR = os.path.join(PROJECT_ROOT, "docs", "keeper-ambiguous")

# Career stumpings threshold for "keeper-capable" in Layer C.
CAREER_N_THRESHOLD = 3

CSV_COLUMNS = [
    "innings_id", "match_id", "date", "tournament", "season",
    "fielding_team", "innings_number",
    "ambiguous_reason", "candidate_ids", "candidate_names",
    "resolved_keeper_id", "resolved_source", "notes",
]


# ============================================================
# Table registration
# ============================================================

async def _ensure_tables(db, incremental: bool = False):
    """Register all tables with deebase so FK references resolve.

    In incremental mode, skip index creation (they already exist).
    Same pattern as get_match_tables() in import_data.py and
    _ensure_tables() in populate_fielding_credits.py.
    """
    # Must register in dependency order so FKs resolve.
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(MatchPlayer, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)
    await db.create(FieldingCredit, pk="id", if_not_exists=True)

    idx = {} if incremental else {
        "indexes": ["keeper_id", "innings_id", "confidence", "ambiguous_reason"]
    }
    return await db.create(
        KeeperAssignment, pk="id", if_not_exists=True, **idx,
    )


# ============================================================
# Candidate set building
# ============================================================

async def _build_candidate_sets(db):
    """Build the in-memory structures the algorithm needs.

    Returns a dict with:
      - career_N3: set(person_id) with >= CAREER_N_THRESHOLD stumpings
      - season_cands: dict[(fielding_team, tournament, season)] -> set(person_id)
      - team_ever: dict[fielding_team] -> set(person_id) (ever stumped for team)
      - stumpers_by_innings: dict[innings_id] -> set(person_id or None)
      - xi_by_match: dict[match_id] -> dict[team] -> set(person_id)
      - person_name_by_id: dict[person_id] -> name (for CSV export)
    """
    # 1. Career N>=3
    rows = await db.q(f"""
        SELECT fielder_id, COUNT(*) as c
        FROM fieldingcredit
        WHERE kind = 'stumped' AND fielder_id IS NOT NULL
        GROUP BY fielder_id
        HAVING COUNT(*) >= {CAREER_N_THRESHOLD}
    """)
    career_N3 = {r["fielder_id"] for r in rows}

    # 2. Season candidates (anyone who stumped for this team in this tournament+season)
    rows = await db.q("""
        SELECT
            CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END as fielding_team,
            m.event_name as tournament,
            m.season,
            fc.fielder_id
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.kind = 'stumped' AND fc.fielder_id IS NOT NULL AND i.super_over = 0
        GROUP BY fielding_team, tournament, m.season, fc.fielder_id
    """)
    season_cands: dict[tuple, set[str]] = defaultdict(set)
    for r in rows:
        key = (r["fielding_team"], r["tournament"], r["season"])
        season_cands[key].add(r["fielder_id"])

    # 3. Team-ever-keeper
    rows = await db.q("""
        SELECT
            CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END as fielding_team,
            fc.fielder_id
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.kind = 'stumped' AND fc.fielder_id IS NOT NULL AND i.super_over = 0
        GROUP BY fielding_team, fc.fielder_id
    """)
    team_ever: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        team_ever[r["fielding_team"]].add(r["fielder_id"])

    # 4. Stumpers by innings (Layer A signal)
    rows = await db.q("""
        SELECT d.innings_id, fc.fielder_id
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        WHERE fc.kind = 'stumped'
    """)
    stumpers_by_innings: dict[int, set[Optional[str]]] = defaultdict(set)
    for r in rows:
        # Note: fielder_id may be None (unresolved stumping fielder)
        stumpers_by_innings[r["innings_id"]].add(r["fielder_id"])

    # 5. XI per match/team
    rows = await db.q("""
        SELECT match_id, team, person_id
        FROM matchplayer
        WHERE person_id IS NOT NULL
    """)
    xi_by_match: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for r in rows:
        xi_by_match[r["match_id"]][r["team"]].add(r["person_id"])

    # 6. Person name lookup (for CSV export only)
    rows = await db.q("SELECT id, name FROM person")
    person_name_by_id = {r["id"]: r["name"] for r in rows}

    return {
        "career_N3": career_N3,
        "season_cands": season_cands,
        "team_ever": team_ever,
        "stumpers_by_innings": stumpers_by_innings,
        "xi_by_match": xi_by_match,
        "person_name_by_id": person_name_by_id,
    }


# ============================================================
# Algorithm core
# ============================================================

def _assign_layers(inn: dict, sets: dict) -> dict:
    """Apply layers A/B/C/D to one innings row.

    `inn` must have: innings_id, match_id, team1, team2, batting_team,
    tournament, season.

    Returns a dict suitable for insert into keeper_assignment:
      {innings_id, keeper_id, method, confidence,
       ambiguous_reason, candidate_ids_json}
    """
    iid = inn["innings_id"]
    mid = inn["match_id"]
    batting_team = inn["batting_team"]
    fielding_team = inn["team2"] if batting_team == inn["team1"] else inn["team1"]
    xi = sets["xi_by_match"].get(mid, {}).get(fielding_team, set())

    def assigned(kid, method, confidence):
        return {
            "innings_id": iid,
            "keeper_id": kid,
            "method": method,
            "confidence": confidence,
            "ambiguous_reason": None,
            "candidate_ids_json": None,
        }

    def ambiguous(reason, candidates):
        # Store as a JSON list (deebase serializes dict-typed columns)
        cand_list = sorted(str(c) for c in candidates if c is not None)
        return {
            "innings_id": iid,
            "keeper_id": None,
            "method": None,
            "confidence": None,
            "ambiguous_reason": reason,
            "candidate_ids_json": cand_list if cand_list else [],
        }

    # Layer A — stumping this innings
    stumpers = sets["stumpers_by_innings"].get(iid, set())
    if stumpers:
        non_null = {s for s in stumpers if s is not None}
        if len(non_null) == 1:
            return assigned(next(iter(non_null)), "stumping", "definitive")
        if len(non_null) >= 2:
            return ambiguous("multi_stumpers_same_innings", non_null)
        # Stumping happened but fielder_id is unresolved
        return ambiguous("stump_fielder_unresolved", set())

    # Layer B — season candidates
    s_key = (fielding_team, inn["tournament"], inn["season"])
    s_cands = sets["season_cands"].get(s_key, set()) & xi
    if len(s_cands) == 1:
        return assigned(next(iter(s_cands)), "season_single", "high")
    if len(s_cands) >= 2:
        return ambiguous("multi_season", s_cands)

    # Layer C — career N>=3
    c_cands = sets["career_N3"] & xi
    if len(c_cands) == 1:
        return assigned(next(iter(c_cands)), "career_single", "medium")
    if len(c_cands) >= 2:
        return ambiguous("multi_career", c_cands)

    # Layer D — team-ever-keeper
    t_cands = sets["team_ever"].get(fielding_team, set()) & xi
    if len(t_cands) == 1:
        return assigned(next(iter(t_cands)), "team_ever_single", "low")
    if len(t_cands) >= 2:
        return ambiguous("multi_team_ever", t_cands)

    # Nothing
    return ambiguous("no_candidate", set())


# ============================================================
# Partition CSV I/O
# ============================================================

def _read_existing_partitions() -> tuple[set[int], dict[int, dict]]:
    """Return (innings_ids_already_in_any_partition, resolutions_by_innings_id).

    `resolutions_by_innings_id` keyed only for rows where
    `resolved_keeper_id` is set.
    """
    known_ids: set[int] = set()
    resolutions: dict[int, dict] = {}
    if not os.path.isdir(PARTITION_DIR):
        return known_ids, resolutions
    for path in sorted(glob.glob(os.path.join(PARTITION_DIR, "*.csv"))):
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    iid = int(row["innings_id"])
                except (KeyError, ValueError, TypeError):
                    continue
                known_ids.add(iid)
                resolved = (row.get("resolved_keeper_id") or "").strip()
                if resolved:
                    resolutions[iid] = {
                        "resolved_keeper_id": resolved,
                        "resolved_source": (row.get("resolved_source") or "").strip(),
                        "notes": (row.get("notes") or "").strip(),
                    }
    return known_ids, resolutions


def _write_partition_rows(today_iso: str, ambig_rows: list[dict]) -> str:
    """Append or create today's partition file. Returns the path.

    `ambig_rows` each have CSV_COLUMNS keys filled in (blank
    resolution columns). Dedups on innings_id against any existing
    rows already in today's partition.
    """
    os.makedirs(PARTITION_DIR, exist_ok=True)
    path = os.path.join(PARTITION_DIR, f"{today_iso}.csv")

    existing_ids: set[int] = set()
    if os.path.exists(path):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                try:
                    existing_ids.add(int(r["innings_id"]))
                except (KeyError, ValueError, TypeError):
                    pass

    new_rows = [r for r in ambig_rows if int(r["innings_id"]) not in existing_ids]

    write_header = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)

    return path


# ============================================================
# Resolution application (mirrors apply_keeper_resolutions.py)
# ============================================================

async def _apply_resolutions(db, resolutions: dict[int, dict], person_ids: set[str],
                             scope_innings: Optional[set[int]] = None) -> dict:
    """Apply manual resolutions from partition CSVs back into keeper_assignment.

    `resolutions` maps innings_id -> {resolved_keeper_id, resolved_source, notes}.
    `person_ids` is the set of all known person.id values (for validation).
    `scope_innings`: if set, only apply resolutions for these innings_ids.
    """
    applied = 0
    overrides = 0  # applied where the row was already non-NULL
    skipped_no_person = 0
    skipped_no_innings = 0

    if not resolutions:
        return {"applied": 0, "overrides": 0,
                "skipped_no_person": 0, "skipped_no_innings": 0}

    # Pre-fetch which innings_ids currently exist in keeper_assignment
    # (scoped to the resolution set for efficiency).
    res_ids = list(resolutions.keys())
    if scope_innings is not None:
        res_ids = [i for i in res_ids if i in scope_innings]
    if not res_ids:
        return {"applied": 0, "overrides": 0,
                "skipped_no_person": 0, "skipped_no_innings": 0}

    ids_csv = ",".join(str(i) for i in res_ids)
    existing = await db.q(
        f"SELECT innings_id, keeper_id FROM keeperassignment "
        f"WHERE innings_id IN ({ids_csv})"
    )
    existing_map = {r["innings_id"]: r["keeper_id"] for r in existing}

    for iid, res in resolutions.items():
        if scope_innings is not None and iid not in scope_innings:
            continue
        pid = res["resolved_keeper_id"]
        if pid not in person_ids:
            skipped_no_person += 1
            continue
        if iid not in existing_map:
            skipped_no_innings += 1
            continue
        was_assigned = existing_map[iid] is not None

        await db.q(
            """
            UPDATE keeperassignment
            SET keeper_id = :pid,
                method = 'manual',
                confidence = 'definitive',
                ambiguous_reason = NULL,
                candidate_ids_json = NULL
            WHERE innings_id = :iid
            """,
            {"pid": pid, "iid": iid},
        )
        applied += 1
        if was_assigned:
            overrides += 1

    return {
        "applied": applied,
        "overrides": overrides,
        "skipped_no_person": skipped_no_person,
        "skipped_no_innings": skipped_no_innings,
    }


# ============================================================
# Full populate
# ============================================================

async def populate_full(db, show_ambiguous_sample: bool = False):
    """Full rebuild: truncate keeper_assignment and re-run the algorithm."""
    print("Populating keeper assignments (full rebuild)...")
    start = time.time()

    # Auto-detect whether the table already exists to decide if we need
    # to create indexes. Same trap as populate_fielding_credits: running
    # populate_full a second time on an existing DB blows up on
    # "index already exists" if we force create.
    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='keeperassignment'"
    )
    table_exists = len(existing) > 0

    table = await _ensure_tables(db, incremental=table_exists)
    if table_exists:
        await db.q("DELETE FROM keeperassignment")

    print("  building candidate sets...")
    sets = await _build_candidate_sets(db)
    print(f"    career N>={CAREER_N_THRESHOLD}: {len(sets['career_N3'])} players")
    print(f"    season buckets: {len(sets['season_cands'])}")
    print(f"    team-ever: {len(sets['team_ever'])} teams")

    # All regular innings
    innings_rows = await db.q("""
        SELECT i.id as innings_id, i.innings_number, i.team as batting_team,
               m.id as match_id, m.team1, m.team2,
               m.event_name as tournament, m.season
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
    """)
    print(f"  {len(innings_rows)} regular innings to process")

    # Apply algorithm
    batch = []
    batch_size = 2000
    counts = defaultdict(int)
    ambig_detail: list[dict] = []  # for CSV export

    for inn in innings_rows:
        row = _assign_layers(inn, sets)
        batch.append(row)

        if row["keeper_id"] is not None:
            counts[row["confidence"]] += 1
        else:
            counts["null"] += 1
            counts[row["ambiguous_reason"]] += 1
            ambig_detail.append({"inn": inn, "row": row})

        if len(batch) >= batch_size:
            sa_table = table.sa_table
            async with db._engine.begin() as conn:
                await conn.execute(sa_table.insert(), batch)
            batch = []

    if batch:
        sa_table = table.sa_table
        async with db._engine.begin() as conn:
            await conn.execute(sa_table.insert(), batch)

    elapsed = time.time() - start
    print(f"\n  Inserted {len(innings_rows)} rows in {elapsed:.1f}s")
    print(f"  definitive: {counts['definitive']}")
    print(f"  high:       {counts['high']}")
    print(f"  medium:     {counts['medium']}")
    print(f"  low:        {counts['low']}")
    print(f"  NULL:       {counts['null']}")
    for reason in ("multi_stumpers_same_innings", "stump_fielder_unresolved",
                   "multi_season", "multi_career", "multi_team_ever", "no_candidate"):
        if counts[reason]:
            print(f"    {reason}: {counts[reason]}")

    # Load and apply existing resolutions (from all partition CSVs)
    print("\n  Loading existing resolutions from partition CSVs...")
    known_ids, resolutions = _read_existing_partitions()
    print(f"    partitions list {len(known_ids)} innings, "
          f"{len(resolutions)} resolved")

    person_ids = set(sets["person_name_by_id"].keys())
    res_stats = await _apply_resolutions(db, resolutions, person_ids)
    print(f"    applied: {res_stats['applied']} "
          f"(overrides: {res_stats['overrides']}); "
          f"skipped: {res_stats['skipped_no_person']} bad person_id, "
          f"{res_stats['skipped_no_innings']} missing innings")

    # Write new partition for ambiguous innings NOT already in any partition
    today_iso = datetime.date.today().isoformat()

    # Re-query what's actually still NULL in the DB (resolutions may have
    # flipped some ambig rows to assigned).
    still_null = await db.q(
        "SELECT innings_id FROM keeperassignment WHERE keeper_id IS NULL"
    )
    still_null_ids = {r["innings_id"] for r in still_null}

    # Build CSV rows for the ambiguous ones we haven't logged before
    new_ambig_ids = still_null_ids - known_ids
    if new_ambig_ids:
        # Need match dates for display
        id_list = ",".join(str(i) for i in new_ambig_ids)
        date_rows = await db.q(f"""
            SELECT ka.innings_id,
                   (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
                   ka.ambiguous_reason, ka.candidate_ids_json,
                   i.innings_number, i.team as batting_team,
                   m.id as match_id, m.team1, m.team2,
                   m.event_name as tournament, m.season
            FROM keeperassignment ka
            JOIN innings i ON i.id = ka.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE ka.innings_id IN ({id_list})
        """)

        csv_rows = []
        for r in date_rows:
            fielding_team = r["team2"] if r["batting_team"] == r["team1"] else r["team1"]
            cand_ids = _parse_json_list(r["candidate_ids_json"])
            cand_names = [sets["person_name_by_id"].get(cid, cid) for cid in cand_ids]
            csv_rows.append({
                "innings_id": r["innings_id"],
                "match_id": r["match_id"],
                "date": r["date"] or "",
                "tournament": r["tournament"] or "",
                "season": r["season"] or "",
                "fielding_team": fielding_team,
                "innings_number": r["innings_number"],
                "ambiguous_reason": r["ambiguous_reason"] or "",
                "candidate_ids": ",".join(cand_ids),
                "candidate_names": ",".join(cand_names),
                "resolved_keeper_id": "",
                "resolved_source": "",
                "notes": "",
            })

        # Sort by (reason, date DESC) so highest-value cases float to top
        csv_rows.sort(
            key=lambda r: (r["ambiguous_reason"], -_date_key(r["date"]))
        )

        path = _write_partition_rows(today_iso, csv_rows)
        print(f"\n  Wrote {len(csv_rows)} new ambiguous rows to {path}")
    else:
        print(f"\n  No new ambiguous innings to partition "
              f"(all already in existing files)")

    if show_ambiguous_sample and ambig_detail:
        print("\n  Ambiguous sample (first 5):")
        for i, a in enumerate(ambig_detail[:5]):
            print(f"    {i+1}. {a['row']['ambiguous_reason']} innings_id={a['inn']['innings_id']}")

    return {
        "total": len(innings_rows),
        "counts": dict(counts),
        "resolutions_applied": res_stats["applied"],
    }


# ============================================================
# Incremental populate
# ============================================================

async def populate_incremental(db, new_match_ids: list[int]):
    """Add keeper_assignment rows for new matches only.

    Does NOT touch existing rows. Does NOT retrofit older ambiguous
    innings with new signals (that's only done on full rebuild).
    """
    if not new_match_ids:
        print("Keeper assignments: no new matches, skipping")
        return 0

    print(f"Populating keeper assignments for {len(new_match_ids)} new matches...")

    table = await _ensure_tables(db, incremental=True)

    # Fresh candidate-set build (cheap, <1s) — picks up any new signals
    # from the matches we just imported.
    sets = await _build_candidate_sets(db)

    # Innings belonging to the new matches
    id_list = ",".join(str(i) for i in new_match_ids)
    innings_rows = await db.q(f"""
        SELECT i.id as innings_id, i.innings_number, i.team as batting_team,
               m.id as match_id, m.team1, m.team2,
               m.event_name as tournament, m.season
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE m.id IN ({id_list}) AND i.super_over = 0
    """)

    # Skip any innings that already have a row (dedup — safe re-run)
    existing = await db.q(
        f"SELECT innings_id FROM keeperassignment "
        f"WHERE innings_id IN ({','.join(str(r['innings_id']) for r in innings_rows) or '0'})"
    )
    already = {r["innings_id"] for r in existing}
    innings_rows = [r for r in innings_rows if r["innings_id"] not in already]

    if not innings_rows:
        print("  All new-match innings already have keeper_assignment rows")
        return 0

    rows_to_insert = []
    counts = defaultdict(int)
    for inn in innings_rows:
        row = _assign_layers(inn, sets)
        rows_to_insert.append(row)
        if row["keeper_id"] is not None:
            counts[row["confidence"]] += 1
        else:
            counts["null"] += 1

    sa_table = table.sa_table
    async with db._engine.begin() as conn:
        await conn.execute(sa_table.insert(), rows_to_insert)

    print(f"  Keeper assignments: +{len(rows_to_insert)} rows "
          f"(definitive={counts['definitive']} high={counts['high']} "
          f"medium={counts['medium']} low={counts['low']} NULL={counts['null']})")

    # Apply any existing resolutions that cover the new innings
    known_ids, resolutions = _read_existing_partitions()
    person_ids = set(sets["person_name_by_id"].keys())
    new_innings_ids = {r["innings_id"] for r in innings_rows}
    res_stats = await _apply_resolutions(
        db, resolutions, person_ids, scope_innings=new_innings_ids,
    )
    if res_stats["applied"]:
        print(f"  Applied {res_stats['applied']} existing resolutions to new innings")

    # Write new ambiguous rows to today's partition (if not already known)
    today_iso = datetime.date.today().isoformat()
    newly_ambig = [r["innings_id"] for r in rows_to_insert
                   if r["keeper_id"] is None
                   and r["innings_id"] not in known_ids]

    if newly_ambig:
        ambig_id_list = ",".join(str(i) for i in newly_ambig)
        date_rows = await db.q(f"""
            SELECT ka.innings_id,
                   (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
                   ka.ambiguous_reason, ka.candidate_ids_json,
                   i.innings_number, i.team as batting_team,
                   m.id as match_id, m.team1, m.team2,
                   m.event_name as tournament, m.season
            FROM keeperassignment ka
            JOIN innings i ON i.id = ka.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE ka.innings_id IN ({ambig_id_list})
        """)
        csv_rows = []
        for r in date_rows:
            fielding_team = r["team2"] if r["batting_team"] == r["team1"] else r["team1"]
            cand_ids = _parse_json_list(r["candidate_ids_json"])
            cand_names = [sets["person_name_by_id"].get(cid, cid) for cid in cand_ids]
            csv_rows.append({
                "innings_id": r["innings_id"],
                "match_id": r["match_id"],
                "date": r["date"] or "",
                "tournament": r["tournament"] or "",
                "season": r["season"] or "",
                "fielding_team": fielding_team,
                "innings_number": r["innings_number"],
                "ambiguous_reason": r["ambiguous_reason"] or "",
                "candidate_ids": ",".join(cand_ids),
                "candidate_names": ",".join(cand_names),
                "resolved_keeper_id": "",
                "resolved_source": "",
                "notes": "",
            })
        path = _write_partition_rows(today_iso, csv_rows)
        print(f"  Appended {len(csv_rows)} ambiguous rows to {path}")

    return len(rows_to_insert)


# ============================================================
# Helpers
# ============================================================

def _parse_json_list(val) -> list[str]:
    """The candidate_ids_json column round-trips through deebase/sqlite —
    it may arrive as a JSON string or an already-decoded list."""
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


def _date_key(date_str: str) -> int:
    """Convert YYYY-MM-DD to int for sorting; empty dates sort last."""
    if not date_str:
        return 0
    try:
        return int(date_str.replace("-", ""))
    except ValueError:
        return 0


# ============================================================
# CLI
# ============================================================

async def main():
    ap = argparse.ArgumentParser(description="Populate keeper_assignment")
    ap.add_argument("--show-ambiguous-sample", action="store_true",
                    help="Print a few ambiguous innings for eyeballing")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db, show_ambiguous_sample=args.show_ambiguous_sample)


if __name__ == "__main__":
    asyncio.run(main())
