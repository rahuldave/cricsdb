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

from import_data import DB_PATH, DATA_DIR, get_match_tables, import_match_file

CRICSHEET_BASE = "https://cricsheet.org/downloads"
CRICSHEET_REGISTER = "https://cricsheet.org/register"
T20_MATCH_TYPES = {"T20", "IT20"}  # club + international T20s
AVAILABLE_WINDOWS = [2, 7, 14, 30]
PEOPLE_CSVS = ["people.csv", "names.csv"]


def check_people_freshness(data_dir: str) -> None:
    """Compare local people.csv / names.csv against cricsheet's via HEAD."""
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

        if not os.path.exists(local):
            print(f"  {name}: MISSING locally — remote {remote_size} bytes, "
                  f"Last-Modified {remote_lm}")
            continue

        local_size = os.path.getsize(local)
        local_mtime = os.path.getmtime(local)
        remote_mtime = None
        if remote_lm:
            try:
                remote_mtime = email.utils.parsedate_to_datetime(remote_lm).timestamp()
            except Exception:
                pass

        size_match = (remote_size == local_size)
        mtime_newer = (remote_mtime is not None and remote_mtime > local_mtime + 1)

        if size_match and not mtime_newer:
            print(f"  {name}: up to date "
                  f"({local_size} bytes, Last-Modified {remote_lm})")
        else:
            reason = []
            if not size_match:
                reason.append(f"size {local_size} -> {remote_size}")
            if mtime_newer:
                reason.append(f"server newer ({remote_lm})")
            print(f"  {name}: STALE ({'; '.join(reason)}) — "
                  f"re-run download_data.py --force to refresh")


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
    args = ap.parse_args()

    window = pick_window(args.days)
    if window != args.days:
        print(f"Note: requested {args.days} days, using cricsheet's "
              f"{window}-day bundle (smallest that covers it)")
    if args.days > AVAILABLE_WINDOWS[-1]:
        print(f"WARNING: --days={args.days} exceeds cricsheet's largest "
              f"bundle ({AVAILABLE_WINDOWS[-1]}); some matches may be missed. "
              f"For a full rebuild, use download_data.py + import_data.py.")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Build the DB first.", file=sys.stderr)
        sys.exit(1)

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
        db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
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

        tables = await get_match_tables(db)
        imported = 0
        failed = 0
        for fp in new_files:
            try:
                await import_match_file(db, fp, tables)
                imported += 1
                print(f"  + {os.path.basename(fp)}")
            except Exception as e:
                failed += 1
                print(f"  ! {os.path.basename(fp)}: {e}", file=sys.stderr)

        print(f"\nImported {imported} matches ({failed} failed)")

    finally:
        if args.keep:
            print(f"Kept workdir: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
