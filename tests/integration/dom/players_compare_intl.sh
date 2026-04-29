#!/bin/bash
# /players?player=X&compare=Y — 2-way player compare. Anchor:
# V Kohli (ba607b88) × RG Sharma (740742ef), men_intl 2024-25.
# Both played 7 T20Is in the post-WC return window, so the two
# columns carry parallel coverage.
#
# Compare-mode DOM uses .wisden-compare-col + .wisden-player-compact-row
# dt/dd shape (NOT the .wisden-statrow band shape used by
# players_single_*.sh). The existing extract_grid harness from
# _lib.sh — built for Teams Compare — works unchanged here:
# columns are matched by header substring, sections + rows by label.
# (PlayerCompareGrid carries no chip envelopes today, so chip_value
# / chip_avg / chip_delta + math invariants are not asserted here.)
#
# Expected (DOM-asserted):
#   Kohli col:  BATTING Runs 127, Avg 18.14, SR 116.51, 100s 0,
#                       50s 1, HS 76
#               FIELDING Catches 2, Total 2
#   Sharma col: BATTING Runs 249, Avg 41.50, SR 164.90, 100s 0,
#                       50s 3, HS 92
#               FIELDING Catches 3, Total 3
#
# Numbers verified by independent SQL — see audit/players_compare_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/players_compare_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — Kohli × Sharma men_intl 24-25 ───────────────
navigate "$BASE/players?player=ba607b88&compare=740742ef&gender=male&team_type=international&season_from=2024&season_to=2025" \
  "Anchor — Kohli × Sharma 2-way compare (men_intl 24-25)"
sleep 4   # +4s soak — getPlayerProfile × 2 columns = 8 parallel fetches

JSON=$(extract_grid 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "Kohli": {
        "_match_header": "V Kohli",
        "matches_text": "7 matches",
        "rows": {
            ("BATTING",  "Runs"):     {"value": 127},
            ("BATTING",  "Avg"):      {"value": 18.14},
            ("BATTING",  "SR"):       {"value": 116.51},
            ("BATTING",  "100s"):     {"value": 0},
            ("BATTING",  "50s"):      {"value": 1},
            ("BATTING",  "HS"):       {"value": 76},
            ("FIELDING", "Catches"):  {"value": 2},
            ("FIELDING", "Stumpings"): {"value": 0},
            ("FIELDING", "Run-outs"):  {"value": 0},
            ("FIELDING", "Total"):    {"value": 2},
        },
    },
    "Sharma": {
        "_match_header": "RG Sharma",
        "matches_text": "7 matches",
        "rows": {
            ("BATTING",  "Runs"):     {"value": 249},
            ("BATTING",  "Avg"):      {"value": 41.50},
            ("BATTING",  "SR"):       {"value": 164.90},
            ("BATTING",  "100s"):     {"value": 0},
            ("BATTING",  "50s"):      {"value": 3},
            ("BATTING",  "HS"):       {"value": 92},
            ("FIELDING", "Catches"):  {"value": 3},
            ("FIELDING", "Stumpings"): {"value": 0},
            ("FIELDING", "Run-outs"):  {"value": 0},
            ("FIELDING", "Total"):    {"value": 3},
        },
    },
}
PYEXPECT
)

run_assertions "Kohli × Sharma 24-25" "$JSON" "$EXPECTED"; record_result $?

print_summary
