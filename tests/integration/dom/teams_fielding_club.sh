#!/bin/bash
# Teams Fielding (club anchor) — DOM-grounded StatCard grid.
# Closed window: Royal Challengers Bengaluru, IPL 2025.

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Fielding" \
  "Anchor — RCB IPL 2025 Fielding"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Royal Challengers Bengaluru",
    "stats": {
        # Row 1
        "Matches":   {"value": "15"},
        "Catches":   {"value": "69"},
        "Stumpings": {"value": "1"},
        "Run-outs":  {"value": "7"},
        # Row 2
        "Catches/match":   {"value": "4.60", "chip_value": 4.60, "chip_avg": 4.21, "chip_delta": 9.3},
        "Stumpings/match": {"value": "0.07", "chip_value": 0.07, "chip_avg": 0.12, "chip_delta": -41.7},
        "Run-outs/match":  {"value": "0.47", "chip_value": 0.47, "chip_avg": 0.39, "chip_delta": 20.5},
        "C&B":             {"value": "0"},
    },
}
PYEXPECT
)

run_team_overview_assertions "RCB IPL 2025 Fielding" "$JSON" "$EXPECTED"; record_result $?

print_summary
