#!/bin/bash
# Series > Editions tab — per-edition mini knockouts table. Knockouts
# moved off Overview on 2026-05-12; the same SQL truth (T20 WC Men
# 2024 had Final India v South Africa + Semi Final India v England)
# is now asserted inside the 2024 edition's mini-table on the
# Editions tab.
#
# Anchor: ICC Men's T20 World Cup 2024 (single-season filter) +
# `?tab=Editions`. With one season in scope, EditionsTab renders
# exactly one `.wisden-edition-block`, whose mini knockouts table
# has exactly two rows:
#   Final (highlighted via tr.is-final):
#     2024-06-29 · Final · India ed 176/7 v South Africa ed 169/8
#                · India (7 runs) · Kensington Oval
#   Semi Final:
#     2024-06-27 · Semi Final · India ed v England ed
#                · India (68 runs) · Providence Stadium
#
# Numbers verified by independent SQL — see audit/series_knockouts_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_knockouts_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — T20 WC Men 2024 Knockouts ───────────────
navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&gender=male&team_type=international&tab=Editions" \
  "Anchor — Series Editions T20 WC Men 2024 (1 block, 2 knockouts)"
sleep 4

extract_edition_blocks > /tmp/ko_intl_blocks.json

# All assertions in Python — block fields contain spaces, slashes,
# parentheses that aren't shell-safe. Pythonn emits PASS/FAIL lines
# that we count in the shell summary.
python3 - <<'PYEOF'
import json, sys

with open('/tmp/ko_intl_blocks.json') as fh:
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

# 1 edition block in scope.
if len(blocks) == 1:
    print("  ✓ 1 edition block for T20 WC Men 2024")
    passes += 1
else:
    print(f"  ✗ expected 1 edition block, got {len(blocks)}")
    fails += 1
    print(f"\nPasses: {passes}  Fails: {fails}")
    sys.exit(1)

b = blocks[0]
check("block season", "2024", b["season"])

# Mini knockouts table: 2 rows, Final present + highlighted.
ko = b["ko_rows"]
if len(ko) == 2:
    print("  ✓ ko_rows count = 2")
    passes += 1
else:
    print(f"  ✗ expected 2 ko rows, got {len(ko)}")
    fails += 1

final = b["ko_final_row"]
if final:
    print("  ✓ tr.is-final row present")
    passes += 1
else:
    print("  ✗ no tr.is-final row found")
    fails += 1

# Schema: Date | Stage | Match (w/ inline scores) | Winner | Venue.
if final:
    check("Final col 0 (Date)",          "2024-06-29",   final[0])
    check("Final col 1 (Stage)",         "Final",        final[1])
    check("Final col 2 (Match) India",   "India",        final[2])
    check("Final col 2 (Match) SA",      "South Africa", final[2])
    check("Final col 2 (Match) scores",  "176/7",        final[2])
    check("Final col 3 (Winner)",        "India",        final[3])
    check("Final col 3 (Margin)",        "7 runs",       final[3])

# Second row — Semi Final (DESC by date, so SF after Final).
if len(ko) > 1:
    sf = ko[1]
    check("SF col 1 (Stage)",         "Semi Final",   sf[1])
    check("SF col 2 (Match) England", "England",      sf[2])
    check("SF col 3 (Margin)",        "68 runs",      sf[3])

print()
print("──────────────────────────────────")
print(f"Passed: {passes}  Failed: {fails}")
sys.exit(0 if fails == 0 else 1)
PYEOF
