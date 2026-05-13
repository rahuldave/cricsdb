#!/bin/bash
# Series > Editions (club). Anchor: Indian Premier League, all
# editions in the DB. As of 2026-05-12 Editions renders as 19
# `.wisden-edition-block` mini-sections (not a flat DataTable). Each
# block carries season + matches header, top scorer / top wicket-
# taker stats, champion + runner-up flex line, and a per-edition
# mini knockouts table whose Final row carries `tr.is-final`.
#
# Marker editions verified here (DESC by season):
#   Block 0  — 2026     in progress; champion still null
#   Block 1  — 2025     74 matches  Royal Challengers Bengaluru
#   Block 2  — 2024     71 matches  Kolkata Knight Riders
#   Block 4  — 2022     74 matches  Gujarat Titans
#   Block 18 — 2007/08  58 matches  Rajasthan Royals (inaugural)
#
# Backed by /api/v1/series/by-season (for the seasons list) +
# /api/v1/series/summary (for knockouts, which the EditionsTab now
# slices by season). Numbers verified by independent SQL — see
# audit/series_editions_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_editions_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — IPL Editions ───────────────
navigate "$BASE/series?tournament=Indian+Premier+League&gender=male&team_type=club&tab=Editions" \
  "Anchor — Series Editions IPL (19 editions)"
sleep 5  # 19 blocks + 18 mini-tables — extra soak for render

extract_edition_blocks > /tmp/ed_club_blocks.json

python3 - <<'PYEOF'
import json, sys

with open('/tmp/ed_club_blocks.json') as fh:
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

# 19 IPL editions in DB (2007/08 → 2026).
if len(blocks) == 19:
    print("  ✓ 19 edition blocks")
    passes += 1
else:
    print(f"  ✗ expected 19 edition blocks, got {len(blocks)}")
    fails += 1
    print(f"\nPasses: {passes}  Fails: {fails}")
    sys.exit(1)

# Block 0 — 2026 in-progress (champion null, no knockouts yet).
b = blocks[0]
check("Block 0 season", "2026", b["season"])
if not b["ko_rows"]:
    print("  ✓ Block 0 (2026) has no knockouts (in-progress)")
    passes += 1
else:
    print(f"  ✗ Block 0 (2026) unexpectedly has {len(b['ko_rows'])} knockout rows")
    fails += 1

# Block 1 — 2025, RCB champion. Stats + Final assertions.
b = blocks[1]
check("Block 1 season",       "2025",                             b["season"])
check("Block 1 matches",      "74",                               b["matches_text"])
check("Block 1 stats",        "B Sai Sudharsan",                  b["stats"])
check("Block 1 champion",     "Royal Challengers Bengaluru",      b["champs"])
check("Block 1 runner-up",    "Punjab Kings",                     b["champs"])
final = b["ko_final_row"] or []
if final:
    check("Block 1 Final date",       "2025-06-03",               final[0])
    check("Block 1 Final stage",      "Final",                    final[1])
    check("Block 1 Final match RCB",  "Royal Challengers Bengaluru", final[2])
    check("Block 1 Final score 190",  "190/9",                    final[2])
    check("Block 1 Final winner",     "Royal Challengers Bengaluru", final[3])
    check("Block 1 Final margin",     "6 runs",                   final[3])
else:
    print("  ✗ Block 1 has no Final row")
    fails += 1

# Block 2 — 2024, KKR champion. Spot-check stats + champion only.
b = blocks[2]
check("Block 2 season",   "2024",                  b["season"])
check("Block 2 matches",  "71",                    b["matches_text"])
check("Block 2 champion", "Kolkata Knight Riders", b["champs"])

# Block 4 — 2022, GT win (different champion to break monotony).
b = blocks[4]
check("Block 4 season",   "2022",          b["season"])
check("Block 4 matches",  "74",            b["matches_text"])
check("Block 4 champion", "Gujarat Titans", b["champs"])

# Block 18 — IPL 2007/08, inaugural edition, Rajasthan Royals.
b = blocks[18]
check("Block 18 season",   "2007/08",         b["season"])
check("Block 18 matches",  "58",              b["matches_text"])
check("Block 18 champion", "Rajasthan Royals", b["champs"])

# Tally how many mini-tables exist across all blocks (=18 — 19 editions
# minus the in-progress 2026 which has no knockouts yet).
n_with_ko = sum(1 for x in blocks if x["ko_rows"])
if n_with_ko == 18:
    print("  ✓ 18 blocks have a knockouts mini-table (2026 in-progress excluded)")
    passes += 1
else:
    print(f"  ✗ expected 18 blocks with ko_rows, got {n_with_ko}")
    fails += 1

# Every block with knockouts has exactly one Final row (tr.is-final).
n_with_final = sum(1 for x in blocks if x["ko_final_row"])
if n_with_final == 18:
    print("  ✓ all 18 ko-tables have exactly one tr.is-final row")
    passes += 1
else:
    print(f"  ✗ expected 18 Final rows, got {n_with_final}")
    fails += 1

print()
print("──────────────────────────────────")
print(f"Passed: {passes}  Failed: {fails}")
sys.exit(0 if fails == 0 else 1)
PYEOF
