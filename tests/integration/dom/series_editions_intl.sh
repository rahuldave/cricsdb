#!/bin/bash
# Series > Editions (intl). Anchor: ICC Men's T20 World Cup, all
# editions in the DB. Cricsheet's coverage of pre-2021 T20 WCs is
# sparse — 5 mini-section blocks (post 2026-05-12 layout):
#
#   Block 0  — 2025/26   49 matches   India (8/9)
#   Block 1  — 2024      44 matches   India (7/7)
#   Block 2  — 2022/23   39 matches   England (4/5)
#   Block 3  — 2021/22   40 matches   Australia (6/7)
#   Block 4  — 2013/14   1 match      no champion (lone early-era recorded match)
#
# Each block (except 2013/14, which has only 1 match and no
# knockouts) renders a mini knockouts table with the season's
# Final + Semi Finals + Super 8 / qualifier ties, Final highlighted.
#
# Backed by /api/v1/series/by-season + /api/v1/series/summary.
# Numbers verified by independent SQL — see audit/series_editions_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_editions_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — T20 WC Men Editions ───────────────
navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&gender=male&team_type=international&tab=Editions" \
  "Anchor — Series Editions T20 WC Men (5 editions)"
sleep 5

extract_edition_blocks > /tmp/ed_intl_blocks.json

python3 - <<'PYEOF'
import json, sys

with open('/tmp/ed_intl_blocks.json') as fh:
    blocks = json.load(fh)

passes = 0
fails = 0

def check(label, expected_substr, actual):
    global passes, fails
    if expected_substr in (actual or ''):
        print(f"  ✓ {label} contains '{expected_substr}'")
        passes += 1
    else:
        print(f"  ✗ {label} expected '{expected_substr}' in: {actual!r}")
        fails += 1

if len(blocks) == 5:
    print("  ✓ 5 edition blocks")
    passes += 1
else:
    print(f"  ✗ expected 5 edition blocks, got {len(blocks)}")
    fails += 1
    print(f"\nPasses: {passes}  Fails: {fails}")
    sys.exit(1)

# Block 0 — 2025/26 (most recent).
b = blocks[0]
check("Block 0 season",  "2025/26", b["season"])
check("Block 0 matches", "49",      b["matches_text"])
check("Block 0 champion", "India",  b["champs"])

# Block 1 — 2024 (the marquee window — also covered in detail by
# series_knockouts_intl.sh).
b = blocks[1]
check("Block 1 season",  "2024", b["season"])
check("Block 1 matches", "44",   b["matches_text"])
check("Block 1 champion", "India", b["champs"])
check("Block 1 runner-up", "South Africa", b["champs"])

# Block 2 — 2022/23 England.
b = blocks[2]
check("Block 2 season",  "2022/23", b["season"])
check("Block 2 matches", "39",      b["matches_text"])
check("Block 2 champion", "England", b["champs"])

# Block 3 — 2021/22 Australia.
b = blocks[3]
check("Block 3 season",  "2021/22",   b["season"])
check("Block 3 matches", "40",        b["matches_text"])
check("Block 3 champion", "Australia", b["champs"])

# Block 4 — 2013/14 sparse 1-match edition (no champion).
b = blocks[4]
check("Block 4 season",  "2013/14", b["season"])
check("Block 4 matches", "1",       b["matches_text"])
# Should have no champion (no Final played in cricsheet data for this row).
if not b["champs"]:
    print("  ✓ Block 4 (2013/14) has no champion")
    passes += 1
else:
    print(f"  ✗ Block 4 (2013/14) unexpectedly has champs: {b['champs']!r}")
    fails += 1

# 4 of 5 blocks have a knockouts mini-table (2013/14 has only 1
# match recorded, no knockout-stage data).
n_with_final = sum(1 for x in blocks if x["ko_final_row"])
if n_with_final == 4:
    print("  ✓ 4 of 5 blocks have a Final row (2013/14 sparse data excluded)")
    passes += 1
else:
    print(f"  ✗ expected 4 Final rows, got {n_with_final}")
    fails += 1

print()
print("──────────────────────────────────")
print(f"Passed: {passes}  Failed: {fails}")
sys.exit(0 if fails == 0 else 1)
PYEOF
