"""Download cricsheet JSON archives + people/names CSVs into data/.

Idempotent: skips files that already exist (unless --force).

Usage:
    uv run python download_data.py            # only missing files
    uv run python download_data.py --force    # re-download everything
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
import zipfile

from import_data import MATCH_DIRS, DATA_DIR

CRICSHEET_BASE = "https://cricsheet.org/downloads"
CRICSHEET_REGISTER = "https://cricsheet.org/register"
CSV_FILES = ["people.csv", "names.csv"]


def download(url: str, dest: str) -> None:
    print(f"  -> {url}")
    tmp = dest + ".part"
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as f:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)


def extract_zip(zip_path: str, out_dir: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.endswith(".json")]
        for n in names:
            # flatten — strip any internal dirs
            target = os.path.join(out_dir, os.path.basename(n))
            with zf.open(n) as src, open(target, "wb") as dst:
                dst.write(src.read())
        return len(names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="Re-download even if files exist")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    # CSVs (people, names)
    for csv_name in CSV_FILES:
        dest = os.path.join(DATA_DIR, csv_name)
        if os.path.exists(dest) and not args.force:
            print(f"[skip] {csv_name}")
            continue
        print(f"[get ] {csv_name}")
        download(f"{CRICSHEET_REGISTER}/{csv_name}", dest)

    # Match zips
    for dir_name in MATCH_DIRS:
        zip_name = f"{dir_name}.zip"
        zip_path = os.path.join(DATA_DIR, zip_name)
        out_dir = os.path.join(DATA_DIR, dir_name)

        if os.path.isdir(out_dir) and os.listdir(out_dir) and not args.force:
            print(f"[skip] {dir_name} (already extracted)")
            continue

        print(f"[get ] {zip_name}")
        try:
            download(f"{CRICSHEET_BASE}/{zip_name}", zip_path)
        except Exception as e:
            print(f"  !! download failed: {e}", file=sys.stderr)
            continue

        n = extract_zip(zip_path, out_dir)
        print(f"  extracted {n} json files -> {out_dir}/")

    print("\nDone. Now run: uv run python import_data.py")


if __name__ == "__main__":
    main()
