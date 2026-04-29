#!/bin/bash
# Teams Bowling (intl anchor) — DOM-grounded StatCard grid assertions.
#
# Closed window: Australia, men's T20I 2024-2025. The Bowling tab
# renders 3 rows of cards: Innings + Overs + Wickets + Runs conceded;
# Economy + Average + Strike rate + Dot %; Avg opp total + Worst
# conceded + Best defence + Wides/match. Five carry chip envelopes.
#
# Numbers verified by independent SQL — see audit/teams_bowling_intl.sql.
# Run: ./tests/integration/dom/teams_bowling_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&tab=Bowling" \
  "Anchor — Aus 2024-25 men_intl Bowling"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Australia",
    "stats": {
        # Row 1
        "Innings":       {"value": "22"},
        "Overs":         {"value": "416.7"},      # legal_balls / 6, 1-decimal
        "Wickets":       {"value": "173"},
        "Runs conceded": {"value": "3,477"},      # toLocaleString
        # Row 2
        "Economy":     {"value": "8.34", "chip_value": 8.34, "chip_avg": 7.52, "chip_delta": 10.9},
        "Average":     {"value": "20.10", "chip_value": 20.10, "chip_avg": 21.9, "chip_delta": -8.2},
        "Strike rate": {"value": "14.45", "chip_value": 14.45, "chip_avg": 17.48, "chip_delta": -17.3},
        "Dot %":       {"value": "38.7%", "chip_value": 38.7, "chip_avg": 42.0, "chip_delta": -7.9},
        # Row 3
        "Avg opp total":  {"value": "158.0", "chip_value": 158.0, "chip_avg": 134.3, "chip_delta": 17.6},
        "Worst conceded": {"value": "218"},  # API: worst_conceded.runs = 218
        "Best defence":   {"value": "64"},   # API: best_defence.runs = 64
        "Wides/match":    {"value": "4.5", "chip_value": 4.5, "chip_avg": 4.67, "chip_delta": -3.6},
    },
}
PYEXPECT
)

run_team_overview_assertions "Aus 24-25 Bowling" "$JSON" "$EXPECTED"; record_result $?

print_summary
