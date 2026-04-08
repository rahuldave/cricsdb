"""Import cricsheet JSON data into SQLite via deebase."""

import asyncio
import csv
import glob
import json
import os
import time

from deebase import Database
from sqlalchemy import text

from models import (
    Person, PersonName, Match, MatchDate, MatchPlayer,
    Innings, Delivery, Wicket,
)
from team_aliases import canonicalize as canon_team
from event_aliases import canonicalize as canon_event

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(os.path.dirname(__file__), "cricket.db")

MATCH_DIRS = [
    # International T20s
    "t20s_male_json", "t20s_female_json",
    "it20s_male_json", "it20s_female_json",
    # Club T20 leagues
    "ipl_json", "bbl_json", "psl_json", "cpl_json",
    "hnd_json", "ntb_json", "ssm_json", "sma_json",
    "bpl_json", "lpl_json", "mlc_json", "sat_json",
    "ilt_json", "wbb_json", "wpl_json", "wsl_json",
    "ctc_json", "npl_json",
]


async def bulk_insert(db, table_obj, rows):
    """Bulk insert using raw SQL for performance."""
    if not rows:
        return
    sa_table = table_obj.sa_table
    async with db._engine.begin() as conn:
        await conn.execute(sa_table.insert(), rows)


async def bulk_insert_returning_ids(db, table_obj, rows):
    """Insert rows one at a time to get auto-increment IDs back."""
    if not rows:
        return []
    ids = []
    sa_table = table_obj.sa_table
    async with db._engine.begin() as conn:
        for row in rows:
            result = await conn.execute(sa_table.insert().values(**row))
            ids.append(result.lastrowid)
    return ids


async def import_people(db):
    """Import people.csv and names.csv."""
    people_table = await db.create(Person, pk="id", if_not_exists=True)
    names_table = await db.create(PersonName, pk="id", if_not_exists=True,
                                  indexes=["person_id"])

    people_csv = os.path.join(DATA_DIR, "people.csv")
    if not os.path.exists(people_csv):
        print("people.csv not found, skipping people import")
        return

    print("Importing people.csv...")
    with open(people_csv, newline="") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            person = {
                "id": row["identifier"],
                "name": row["name"],
                "unique_name": row["unique_name"],
            }
            for col in reader.fieldnames:
                if col.startswith("key_"):
                    val = row.get(col, "").strip()
                    person[col] = val if val else None
            batch.append(person)
            if len(batch) >= 5000:
                await bulk_insert(db, people_table, batch)
                batch = []
        if batch:
            await bulk_insert(db, people_table, batch)

    result = await db.q("SELECT COUNT(*) as c FROM person")
    print(f"  Imported {result[0]['c']} people")

    # Names
    names_csv = os.path.join(DATA_DIR, "names.csv")
    if os.path.exists(names_csv):
        print("Importing names.csv...")
        with open(names_csv, newline="") as f:
            reader = csv.DictReader(f)
            batch = []
            for row in reader:
                batch.append({
                    "person_id": row["identifier"],
                    "name": row["name"],
                })
                if len(batch) >= 5000:
                    await bulk_insert(db, names_table, batch)
                    batch = []
            if batch:
                await bulk_insert(db, names_table, batch)
        result = await db.q("SELECT COUNT(*) as c FROM personname")
        print(f"  Imported {result[0]['c']} name variants")


async def get_match_tables(db):
    """Create (if needed) and return all match-related tables."""
    return {
        "matches": await db.create(Match, pk="id", if_not_exists=True,
                                   indexes=["match_type", "gender", "season",
                                            "team1", "team2", "event_name"]),
        "dates": await db.create(MatchDate, pk="id", if_not_exists=True,
                                 indexes=["match_id"]),
        "players": await db.create(MatchPlayer, pk="id", if_not_exists=True,
                                   indexes=["match_id", "person_id"]),
        "innings": await db.create(Innings, pk="id", if_not_exists=True,
                                   indexes=["match_id"]),
        "deliveries": await db.create(Delivery, pk="id", if_not_exists=True,
                                      indexes=["innings_id", "batter_id",
                                                "bowler_id"]),
        "wickets": await db.create(Wicket, pk="id", if_not_exists=True,
                                   indexes=["delivery_id", "player_out_id"]),
    }


async def import_match_file(db, filepath, tables):
    """Import a single cricsheet match JSON file. Returns True on success."""
    with open(filepath) as f:
        data = json.load(f)

    filename = os.path.basename(filepath)
    meta = data["meta"]
    matches_table = tables["matches"]
    dates_table = tables["dates"]
    players_table = tables["players"]
    innings_table = tables["innings"]
    deliveries_table = tables["deliveries"]
    wickets_table = tables["wickets"]

    info = data["info"]
    registry = info.get("registry", {}).get("people", {})
    event = info.get("event", {})
    if not isinstance(event, dict):
        event = {}
    toss = info.get("toss", {})
    outcome = info.get("outcome", {})
    by = outcome.get("by", {})
    teams = info["teams"]

    match = await matches_table.insert({
        "filename": filename,
        "data_version": meta.get("data_version", ""),
        "meta_created": meta.get("created", ""),
        "meta_revision": meta.get("revision", 0),
        "gender": info["gender"],
        "match_type": info["match_type"],
        "team_type": info.get("team_type", ""),
        "season": str(info.get("season", "")),
        "team1": canon_team(teams[0]) if len(teams) > 0 else "",
        "team2": canon_team(teams[1]) if len(teams) > 1 else "",
        "venue": info.get("venue"),
        "city": info.get("city"),
        "event_name": canon_event(event.get("name")),
        "event_match_number": event.get("match_number"),
        "event_group": str(event["group"]) if "group" in event else None,
        "event_stage": event.get("stage"),
        "match_type_number": info.get("match_type_number"),
        "overs": info.get("overs"),
        "balls_per_over": info.get("balls_per_over", 6),
        "toss_winner": canon_team(toss.get("winner")),
        "toss_decision": toss.get("decision"),
        "toss_uncontested": toss.get("uncontested", False),
        "outcome_winner": canon_team(outcome.get("winner")),
        "outcome_by_runs": by.get("runs"),
        "outcome_by_wickets": by.get("wickets"),
        "outcome_by_innings": by.get("innings"),
        "outcome_result": outcome.get("result"),
        "outcome_method": outcome.get("method"),
        "outcome_eliminator": outcome.get("eliminator"),
        "outcome_bowl_out": outcome.get("bowl_out"),
        "player_of_match": info.get("player_of_match"),
        "dates": info.get("dates", []),
        "officials": info.get("officials"),
    })
    match_id = match["id"]

    date_rows = [{"match_id": match_id, "date": d}
                 for d in info.get("dates", [])]
    if date_rows:
        await bulk_insert(db, dates_table, date_rows)

    players = info.get("players", {})
    player_rows = []
    for team, player_list in players.items():
        canonical_team = canon_team(team)
        for pname in player_list:
            player_rows.append({
                "match_id": match_id,
                "team": canonical_team,
                "player_name": pname,
                "person_id": registry.get(pname),
            })
    if player_rows:
        await bulk_insert(db, players_table, player_rows)

    for inn_num, inn_data in enumerate(data.get("innings", [])):
        target = inn_data.get("target", {})
        penalty = inn_data.get("penalty_runs", {})

        innings = await innings_table.insert({
            "match_id": match_id,
            "innings_number": inn_num,
            "team": canon_team(inn_data["team"]),
            "declared": inn_data.get("declared", False),
            "forfeited": inn_data.get("forfeited", False),
            "super_over": inn_data.get("super_over", False),
            "target_runs": target.get("runs") if target else None,
            "target_overs": target.get("overs") if target else None,
            "powerplays": inn_data.get("powerplays"),
            "penalty_runs_pre": penalty.get("pre", 0) if penalty else 0,
            "penalty_runs_post": penalty.get("post", 0) if penalty else 0,
        })
        innings_id = innings["id"]

        delivery_rows = []
        wicket_pending = []

        for over_data in inn_data.get("overs", []):
            over_num = over_data["over"]
            for del_idx, del_data in enumerate(over_data["deliveries"]):
                runs = del_data.get("runs", {})
                extras = del_data.get("extras", {})

                delivery_rows.append({
                    "innings_id": innings_id,
                    "over_number": over_num,
                    "delivery_index": del_idx,
                    "batter": del_data["batter"],
                    "bowler": del_data["bowler"],
                    "non_striker": del_data["non_striker"],
                    "batter_id": registry.get(del_data["batter"]),
                    "bowler_id": registry.get(del_data["bowler"]),
                    "non_striker_id": registry.get(del_data["non_striker"]),
                    "runs_batter": runs.get("batter", 0),
                    "runs_extras": runs.get("extras", 0),
                    "runs_total": runs.get("total", 0),
                    "runs_non_boundary": runs.get("non_boundary"),
                    "extras_wides": extras.get("wides", 0),
                    "extras_noballs": extras.get("noballs", 0),
                    "extras_byes": extras.get("byes", 0),
                    "extras_legbyes": extras.get("legbyes", 0),
                    "extras_penalty": extras.get("penalty", 0),
                })

                if "wickets" in del_data:
                    for w in del_data["wickets"]:
                        wicket_pending.append((len(delivery_rows) - 1, w))

        if delivery_rows:
            del_ids = await bulk_insert_returning_ids(
                db, deliveries_table, delivery_rows)

            if wicket_pending:
                wicket_rows = []
                for batch_idx, w_data in wicket_pending:
                    wicket_rows.append({
                        "delivery_id": del_ids[batch_idx],
                        "player_out": w_data["player_out"],
                        "player_out_id": registry.get(w_data["player_out"]),
                        "kind": w_data["kind"],
                        "fielders": json.dumps(w_data.get("fielders"))
                            if w_data.get("fielders") else None,
                    })
                await bulk_insert(db, wickets_table, wicket_rows)

    return True


async def import_matches(db):
    """Import all match JSON files from the configured directories."""
    tables = await get_match_tables(db)

    all_files = []
    for dir_name in MATCH_DIRS:
        dir_path = os.path.join(DATA_DIR, dir_name)
        if os.path.isdir(dir_path):
            files = sorted(glob.glob(os.path.join(dir_path, "*.json")))
            all_files.extend(files)
            print(f"  {dir_name}: {len(files)} files")

    total = len(all_files)
    print(f"Total match files: {total}")
    start = time.time()

    for i, filepath in enumerate(all_files):
        if (i + 1) % 500 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print(f"  Progress: {i+1}/{total} "
                  f"({elapsed:.0f}s, {rate:.1f} matches/s)")
        await import_match_file(db, filepath, tables)

    elapsed = time.time() - start
    print(f"\nDone! Imported {total} matches in {elapsed:.1f}s")

    for tbl in ["match", "matchdate", "matchplayer",
                "innings", "delivery", "wicket"]:
        result = await db.q(f"SELECT COUNT(*) as c FROM {tbl}")
        print(f"  {tbl}: {result[0]['c']} rows")


async def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")

    await import_people(db)
    await import_matches(db)

    print(f"\nDatabase saved to {DB_PATH}")
    print(f"Size: {os.path.getsize(DB_PATH) / 1024 / 1024:.1f} MB")

    # Refresh frontend/src/generated/site-stats.json so the home page
    # masthead and Featured section pick up the new totals.
    print("\nRegenerating site stats…")
    import subprocess
    subprocess.run(
        ["python", "scripts/generate_site_stats.py"],
        check=False,
    )


if __name__ == "__main__":
    asyncio.run(main())
