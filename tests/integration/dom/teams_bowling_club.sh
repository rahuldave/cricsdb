#!/bin/bash
# Teams Bowling (club anchor) — DOM-grounded StatCard grid assertions.
#
# Closed window: Royal Challengers Bengaluru, IPL 2025.
# Numbers verified by independent SQL — see audit/teams_bowling_club.sql.
# Run: ./tests/integration/dom/teams_bowling_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Bowling" \
  "Anchor — RCB IPL 2025 Bowling"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Royal Challengers Bengaluru",
    "stats": {
        # Row 1
        "Innings":       {"value": "15"},
        "Overs":         {"value": "282.0"},
        "Wickets":       {"value": "91"},
        "Runs conceded": {"value": "2,606"},
        # Row 2
        "Economy":     {"value": "9.24", "chip_value": 9.24, "chip_avg": 9.63, "chip_delta": -4.0},
        "Average":     {"value": "28.64", "chip_value": 28.64, "chip_avg": 31.93, "chip_delta": -10.3},
        "Strike rate": {"value": "18.59", "chip_value": 18.59, "chip_avg": 19.89, "chip_delta": -6.5},
        "Dot %":       {"value": "33.7%", "chip_value": 33.7, "chip_avg": 32.3, "chip_delta": 4.3},
        # Row 3
        "Avg opp total":  {"value": "173.7", "chip_value": 173.7, "chip_avg": 181.5, "chip_delta": -4.3},
        "Worst conceded": {"value": "231"},
        "Best defence":   {"value": "146"},
        "Wides/match":    {"value": "2.7", "chip_value": 2.67, "chip_avg": 4.72, "chip_delta": -43.4},
    },
}
PYEXPECT
)

run_team_overview_assertions "RCB IPL 2025 Bowling" "$JSON" "$EXPECTED"; record_result $?

print_summary
