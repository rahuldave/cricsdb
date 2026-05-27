"""Incrementally add newly-released cricsheet T20 matches to the database.

Downloads cricsheet's "recently added" bulk zip, filters to T20 / IT20
(international + club), dedupes against existing match.filename rows,
and imports only the new matches.

Usage:
    uv run python update_recent.py
    uv run python update_recent.py --window 30   # default
    uv run python update_recent.py --keep        # keep extracted files

Cricsheet only publishes bulk "recently_added" zips for specific windows
(7, 14, 30 days). Pass any integer via --days; the script picks the
smallest available bundle that covers it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

from deebase import Database

from import_data import (
    DB_PATH, DATA_DIR, get_match_tables, import_match_file,
    refresh_people_registry, write_unknown_venues,
)

CRICSHEET_BASE = "https://cricsheet.org/downloads"
CRICSHEET_REGISTER = "https://cricsheet.org/register"
T20_MATCH_TYPES = {"T20", "IT20"}  # club + international T20s
AVAILABLE_WINDOWS = [2, 7, 14, 30]
PEOPLE_CSVS = ["people.csv", "names.csv"]


def check_people_freshness(data_dir: str, *, refresh: bool = False) -> None:
    """Compare local people.csv / names.csv against cricsheet's via HEAD.
    With refresh=True, re-download stale files in place. Default
    behaviour (refresh=False) is log-only — used by --dry-run.
    """
    import email.utils

    print("People/names CSVs:")
    for name in PEOPLE_CSVS:
        local = os.path.join(data_dir, name)
        url = f"{CRICSHEET_REGISTER}/{name}"
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req) as resp:
                remote_size = int(resp.headers.get("Content-Length") or 0)
                remote_lm = resp.headers.get("Last-Modified")
        except Exception as e:
            print(f"  {name}: HEAD failed ({e})")
            continue

        local_size = os.path.getsize(local) if os.path.exists(local) else 0
        local_mtime = os.path.getmtime(local) if os.path.exists(local) else 0
        remote_mtime = None
        if remote_lm:
            try:
                remote_mtime = email.utils.parsedate_to_datetime(remote_lm).timestamp()
            except Exception:
                pass

        if not os.path.exists(local):
            stale = True
            reason = ["MISSING locally"]
        else:
            size_match = (remote_size == local_size)
            mtime_newer = (remote_mtime is not None and remote_mtime > local_mtime + 1)
            stale = not size_match or mtime_newer
            reason = []
            if not size_match:
                reason.append(f"size {local_size} -> {remote_size}")
            if mtime_newer:
                reason.append(f"server newer ({remote_lm})")

        if not stale:
            print(f"  {name}: up to date "
                  f"({local_size} bytes, Last-Modified {remote_lm})")
            continue

        if not refresh:
            print(f"  {name}: STALE ({'; '.join(reason)}) — "
                  f"re-run with refresh=True or download_data.py --force")
            continue

        # Refresh in place — atomic via .part suffix.
        print(f"  {name}: STALE ({'; '.join(reason)}) — refreshing")
        tmp = local + ".part"
        try:
            with urllib.request.urlopen(url) as resp, open(tmp, "wb") as f:
                shutil.copyfileobj(resp, f)
            os.replace(tmp, local)
            print(f"  {name}: refreshed -> {os.path.getsize(local)} bytes")
        except Exception as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            print(f"  {name}: refresh FAILED ({e}) — keeping existing")


def pick_window(days: int) -> int:
    for w in AVAILABLE_WINDOWS:
        if days <= w:
            return w
    return AVAILABLE_WINDOWS[-1]


def download(url: str, dest: str) -> None:
    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def extract(zip_path: str, out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    with zipfile.ZipFile(zip_path) as zf:
        for n in zf.namelist():
            if not n.endswith(".json"):
                continue
            target = os.path.join(out_dir, os.path.basename(n))
            with zf.open(n) as src, open(target, "wb") as dst:
                dst.write(src.read())
            paths.append(target)
    return paths


def is_t20(filepath: str) -> tuple[bool, str | None]:
    """Return (is_t20, team_type) for a cricsheet match file."""
    try:
        with open(filepath) as f:
            data = json.load(f)
    except Exception:
        return False, None
    info = data.get("info", {})
    mt = info.get("match_type")
    if mt not in T20_MATCH_TYPES:
        return False, None
    return True, info.get("team_type")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30,
                    help="How many days back to fetch. Cricsheet only "
                         "publishes 2/7/14/30-day bundles, so the smallest "
                         "bundle covering --days is used.")
    ap.add_argument("--keep", action="store_true",
                    help="Keep extracted files after import")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report how far behind the DB is and what would be "
                         "imported, without writing anything")
    ap.add_argument("--db", type=str, default=None,
                    help="Override the DB path (default: ./cricket.db). "
                         "Used to smoke-test against a staging copy, e.g. a "
                         "prod snapshot copied from ~/Downloads/t20-cricket-db_"
                         "download/data/cricket.db → /tmp. See "
                         "internal_docs/testing-update-recent.md.")
    args = ap.parse_args()

    db_path = args.db if args.db else DB_PATH

    window = pick_window(args.days)
    if window != args.days:
        print(f"Note: requested {args.days} days, using cricsheet's "
              f"{window}-day bundle (smallest that covers it)")
    if args.days > AVAILABLE_WINDOWS[-1]:
        print(f"WARNING: --days={args.days} exceeds cricsheet's largest "
              f"bundle ({AVAILABLE_WINDOWS[-1]}); some matches may be missed. "
              f"For a full rebuild, use download_data.py + import_data.py.")

    if not os.path.exists(db_path):
        print(f"ERROR: {db_path} not found. Build the DB first.", file=sys.stderr)
        sys.exit(1)
    if args.db:
        print(f"Using DB override: {db_path}")

    workdir = tempfile.mkdtemp(prefix="cricsheet_recent_")
    zip_path = os.path.join(workdir, f"recently_added_{window}_json.zip")
    extracted_dir = os.path.join(workdir, "extracted")

    try:
        download(f"{CRICSHEET_BASE}/recently_added_{window}_json.zip",
                 zip_path)
        all_files = extract(zip_path, extracted_dir)
        print(f"Extracted {len(all_files)} files")

        # Filter to T20 / IT20
        t20_files = []
        team_type_counts = {"international": 0, "club": 0, "other": 0}
        for fp in all_files:
            ok, tt = is_t20(fp)
            if not ok:
                continue
            t20_files.append(fp)
            team_type_counts[tt if tt in team_type_counts else "other"] += 1

        print(f"T20 matches in window: {len(t20_files)} "
              f"(international={team_type_counts['international']}, "
              f"club={team_type_counts['club']}, "
              f"other={team_type_counts['other']})")

        if not t20_files:
            print("Nothing to import.")
            return

        # Connect to DB and dedupe
        db = Database(f"sqlite+aiosqlite:///{db_path}")
        await db.q("PRAGMA journal_mode = WAL")

        # How far behind are we?
        from datetime import date as _date

        latest = await db.q("SELECT MAX(date) as d FROM matchdate")
        db_latest = latest[0]["d"] if latest else None

        # Latest *played* match date in the downloaded bundle (T20s only)
        bundle_latest = None
        for fp in t20_files:
            with open(fp) as f:
                dates = json.load(f).get("info", {}).get("dates", [])
            for d in dates:
                if bundle_latest is None or d > bundle_latest:
                    bundle_latest = d

        today_str = _date.today().isoformat()
        print()
        print(f"  Today:                        {today_str}")
        print(f"  Latest match in DB:           {db_latest or '(empty)'}")
        print(f"  Latest match in {window}-day bundle: {bundle_latest or '(none)'}")

        if db_latest and bundle_latest:
            if db_latest >= bundle_latest:
                print(f"  Status: IN SYNC with cricsheet — cricsheet itself "
                      f"is {(_date.fromisoformat(today_str) - _date.fromisoformat(bundle_latest)).days} "
                      f"day(s) behind today.")
            else:
                gap = (_date.fromisoformat(bundle_latest)
                       - _date.fromisoformat(db_latest)).days
                print(f"  Status: DB is BEHIND cricsheet by {gap} day(s).")
        print()

        existing = await db.q("SELECT filename FROM match")
        existing_set = {r["filename"] for r in existing}
        new_files = [fp for fp in t20_files
                     if os.path.basename(fp) not in existing_set]

        print(f"Already in DB: {len(t20_files) - len(new_files)}")
        print(f"New to import: {len(new_files)}")

        if args.dry_run:
            print()
            check_people_freshness(DATA_DIR)
            print()
            if new_files:
                print("\n[dry-run] Would import:")
                for fp in new_files:
                    with open(fp) as f:
                        info = json.load(f).get("info", {})
                    dates = info.get("dates", [])
                    teams = info.get("teams", [])
                    event = info.get("event") if isinstance(info.get("event"), dict) else {}
                    ev = (event or {}).get("name", "")
                    d0 = dates[0] if dates else "?"
                    print(f"  {d0}  {teams[0] if teams else '?'} vs "
                          f"{teams[1] if len(teams) > 1 else '?'}  [{ev}]")
            print("\n[dry-run] No changes written.")
            return

        if not new_files:
            print("Database is up to date.")
            return

        # 1. Refresh the local people.csv + names.csv from cricsheet
        # (only if stale). cricsheet adds names every cycle; without
        # this, a fresh person_id in the new match-JSONs has nowhere
        # to land in the person table. Atomic in-place download via
        # .part suffix; HEAD-driven so it's a no-op when up to date.
        check_people_freshness(DATA_DIR, refresh=True)

        # 2. Apply the (possibly-refreshed) CSVs onto the person +
        # personname tables via INSERT OR IGNORE. Existing rows
        # preserved; new ids land. Runs BEFORE the match-import loop
        # so matchplayer rows for the new matches have their
        # corresponding person rows in place. Without this, the
        # dossier-by-id pages (`/batting?player=<id>` etc.) render
        # without a name. Spec: project_next_session.md 2026-04-30.
        await refresh_people_registry(db)

        tables = await get_match_tables(db, incremental=True)
        imported = 0
        failed = 0
        imported_filenames = []
        for fp in new_files:
            try:
                await import_match_file(db, fp, tables)
                imported += 1
                imported_filenames.append(os.path.basename(fp))
                print(f"  + {os.path.basename(fp)}")
            except Exception as e:
                failed += 1
                print(f"  ! {os.path.basename(fp)}: {e}", file=sys.stderr)

        print(f"\nImported {imported} matches ({failed} failed)")

        if imported > 0:
            # Populate fielding credits for the new matches
            placeholders = ",".join(f"'{fn}'" for fn in imported_filenames)
            id_rows = await db.q(
                f"SELECT id FROM match WHERE filename IN ({placeholders})"
            )
            new_match_ids = [r["id"] for r in id_rows]
            if new_match_ids:
                from scripts.populate_fielding_credits import populate_incremental
                await populate_incremental(db, new_match_ids)

                # Keeper assignments follow fielding credits
                from scripts.populate_keeper_assignments import (
                    populate_incremental as keeper_incr,
                )
                await keeper_incr(db, new_match_ids)

                # Partnerships follow keeper assignments
                from scripts.populate_partnerships import (
                    populate_incremental as partnerships_incr,
                )
                await partnerships_incr(db, new_match_ids)

                # player_scope_stats — denormalized per-player rollups.
                # Recomputes the (person, scope_key) cells touched by
                # the new matches. Built but not consumed in Spec 1.
                from scripts.populate_player_scope_stats import (
                    populate_incremental as pss_incr,
                )
                await pss_incr(db, new_match_ids)

                # Records aggregates run HERE (ahead of position): the
                # position child is now a rollup of inningsbatterperf
                # (spec-batting-allball-runs-single-source.md §5/D2), so
                # the per-innings table must be current for the touched
                # matches before the rollup reads it.
                from scripts.populate_records_aggregates import (
                    populate_incremental as records_incr,
                )
                await records_incr(db, new_match_ids)

                # playerscopestats_position — per-position batting
                # child, now a rollup of inningsbatterperf (above).
                # Same touched-scope recompute strategy.
                from scripts.populate_playerscopestats_position import (
                    populate_incremental as pssp_incr,
                )
                await pssp_incr(db, new_match_ids)

                # playerscopestats_over — per-over bowling child of
                # player_scope_stats. Same touched-scope recompute.
                from scripts.populate_playerscopestats_over import (
                    populate_incremental as psso_incr,
                )
                await psso_incr(db, new_match_ids)

                # playerscopestats_fielding_position — per (fielder,
                # dismissed-batter-position) aggregates. Substitute
                # fielders excluded (distribution-side semantics).
                from scripts.populate_playerscopestats_fielding_position import (
                    populate_incremental as pssfp_incr,
                )
                await pssfp_incr(db, new_match_ids)

                # playerscopestats_fielding_catch_dist — per (person, scope)
                # match-grain catch distribution (matches_with_0/_1/_ge2).
                # Backs the fielding ProbChip cohort baselines (PT4 of
                # spec-prob-baselines.md). Same touched-scope recompute.
                from scripts.populate_playerscopestats_fielding_catch_dist import (
                    populate_incremental as pssfcd_incr,
                )
                await pssfcd_incr(db, new_match_ids)

                # playerscopestats_batting_phase — per-phase batting
                # child of player_scope_stats. Same touched-scope
                # recompute. Spec: spec-player-baseline-parity.md §3.1.1.
                from scripts.populate_playerscopestats_batting_phase import (
                    populate_incremental as pssbp_incr,
                )
                await pssbp_incr(db, new_match_ids)

                # playerscopestats_fielding_phase — per (fielder, phase)
                # aggregates. Substitute fielders excluded. Same
                # touched-scope recompute. Spec §3.1.2.
                from scripts.populate_playerscopestats_fielding_phase import (
                    populate_incremental as pssfph_incr,
                )
                await pssfph_incr(db, new_match_ids)

                # bucket_baseline_* — per-cell precomputed team / league
                # baselines for the Compare tab and team endpoints.
                # Recomputes only cells touched by new matches.
                from scripts.populate_bucket_baseline import (
                    populate_incremental as bb_incr,
                )
                await bb_incr(db, new_match_ids)

                # (records aggregates moved up — see right after
                # player_scope_stats; the position rollup depends on
                # inningsbatterperf being current first.)

                # Refresh query planner stats and ensure leaderboard
                # indexes exist. Index CREATE is a no-op if already
                # there; ANALYZE is cheap and keeps bowling-leader
                # joins from regressing after a big batch.
                print("Refreshing leaderboard indexes + ANALYZE…")
                await db.q("CREATE INDEX IF NOT EXISTS ix_delivery_batter_agg "
                           "ON delivery(batter_id, extras_wides, extras_noballs, runs_batter)")
                await db.q("CREATE INDEX IF NOT EXISTS ix_delivery_bowler_agg "
                           "ON delivery(bowler_id, extras_wides, extras_noballs, runs_total)")
                # Required by the Compare-tab avg slot's auto-narrow
                # subquery — see import_data.py for the context.
                await db.q("CREATE INDEX IF NOT EXISTS ix_matchplayer_team "
                           "ON matchplayer(team)")
                await db.q("ANALYZE")

            print("\nRegenerating site stats…")
            import subprocess
            subprocess.run(
                ["python", "scripts/generate_site_stats.py"],
                check=False,
            )

        write_unknown_venues()

    finally:
        if args.keep:
            print(f"Kept workdir: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
