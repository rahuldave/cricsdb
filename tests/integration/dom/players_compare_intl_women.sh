#!/bin/bash
# /players?player=X&compare=Y — 2-way player compare, women intl.
# Anchor: S Mandhana × BL Mooney, women_intl 2024-25 (the first
# COMPARE_WOMEN pair in CuratedLists.ts).
#
# Two contrasted columns:
#   Mandhana = specialist batter (no KEEPING band rendered with rows;
#              the section label appears as a placeholder for
#              cross-column alignment but the dt/dd row dict is empty)
#   Mooney   = keeper-batter (KEEPING band rendered with 5 rows).
#
# Expected (DOM-asserted):
#   Mandhana:  BATTING 877/43.85/133.69/1×100/8×50/HS 112
#              FIELDING 10C/0St/2RO/Total 12
#   Mooney:    BATTING 548/54.80/137.34/0×100/4×50/HS 94
#              FIELDING 8C/1St/3RO/Total 12
#              KEEPING  Innings kept 8, Catches 5, Stumpings 1,
#                       Byes 10, Byes/inn 1.25
#
# Numbers verified by independent SQL — see audit/players_compare_intl_women.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/players_compare_intl_women.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/players?player=5d2eda89&compare=52d1dbc8&gender=female&team_type=international&season_from=2024&season_to=2025" \
  "Anchor — Mandhana × Mooney 2-way compare (women_intl 24-25)"
sleep 4

JSON=$(extract_grid 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "Mandhana": {
        "_match_header": "S Mandhana",
        "matches_text": "25 matches",
        "rows": {
            ("BATTING",  "Runs"):     {"value": 877},
            ("BATTING",  "Avg"):      {"value": 43.85},
            ("BATTING",  "SR"):       {"value": 133.69},
            ("BATTING",  "100s"):     {"value": 1},
            ("BATTING",  "50s"):      {"value": 8},
            ("BATTING",  "HS"):       {"value": 112},
            ("FIELDING", "Catches"):  {"value": 10},
            ("FIELDING", "Stumpings"): {"value": 0},
            ("FIELDING", "Run-outs"):  {"value": 2},
            ("FIELDING", "Total"):    {"value": 12},
        },
    },
    "Mooney": {
        "_match_header": "BL Mooney",
        "matches_text": "14 matches",
        "rows": {
            ("BATTING",  "Runs"):     {"value": 548},
            ("BATTING",  "Avg"):      {"value": 54.80},
            ("BATTING",  "SR"):       {"value": 137.34},
            ("BATTING",  "100s"):     {"value": 0},
            ("BATTING",  "50s"):      {"value": 4},
            ("BATTING",  "HS"):       {"value": 94},
            ("FIELDING", "Catches"):  {"value": 8},
            ("FIELDING", "Stumpings"): {"value": 1},
            ("FIELDING", "Run-outs"):  {"value": 3},
            ("FIELDING", "Total"):    {"value": 12},
            ("KEEPING",  "Innings kept"): {"value": 8},
            ("KEEPING",  "Catches"):     {"value": 5},
            ("KEEPING",  "Stumpings"):   {"value": 1},
            ("KEEPING",  "Byes"):        {"value": 10},
        },
    },
}
PYEXPECT
)

run_assertions "Mandhana × Mooney 24-25" "$JSON" "$EXPECTED"; record_result $?

print_summary
