#!/bin/bash
# Teams > Compare (CLUB anchor) — DOM-grounded chip + value assertions.
#
# One anchor against IPL 2025 (74 matches, closed):
#   B. Royal Challengers Bengaluru + Sunrisers Hyderabad + IPL avg.
#
# Numbers verified by an independent subagent that did NOT read api/
# source — see audit/teams_compare_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/teams_compare_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR B — IPL 2025 (closed-league avg) ───────────────
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tab=Compare&compare1=__avg__&compare2=Sunrisers+Hyderabad&season_from=2025&season_to=2025" \
  "Anchor B — IPL 2025 club"

JSON_B=$(extract_grid 2>/dev/null)

EXPECTED_B=$(cat <<'PYEXPECT'
{
  "Royal Challengers Bengaluru": {
    "_match_header": "Royal Challengers Bengaluru",
    "matches_text": "15",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 15},
      ("BATTING", "Run rate"):    {"value": 9.69, "chip_value": 9.69, "chip_avg": 9.63},
      ("BATTING", "Boundary %"):  {"chip_value": 22.1, "chip_avg": 21.6},
      ("BOWLING", "Economy"):     {"chip_value": 9.24, "chip_avg": 9.63},
    },
  },
  "Indian Premier League average": {
    "_match_header": "Indian Premier League average",
    # 2026-04-28 per-team transform: avg col matches identity is now
    # the per-team rate, not absolute pool. 74 × 2 / 10 = 14.8.
    "matches_text": "14.8 matches in scope",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 9.63},
    },
  },
  "Sunrisers Hyderabad": {
    "_match_header": "Sunrisers Hyderabad",
    "matches_text": "14",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 14},
      ("BATTING", "Run rate"):    {"value": 10.04, "chip_value": 10.04, "chip_avg": 9.63},
      ("BATTING", "Boundary %"):  {"chip_value": 22.5, "chip_avg": 21.6},
      ("BOWLING", "Economy"):     {"chip_value": 9.90, "chip_avg": 9.63},
    },
  },
}
PYEXPECT
)

run_assertions "ANCHOR B IPL 2025" "$JSON_B" "$EXPECTED_B"; record_result $?

print_summary
