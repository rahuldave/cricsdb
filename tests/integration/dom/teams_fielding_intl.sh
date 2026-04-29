#!/bin/bash
# Teams Fielding (intl anchor) — DOM-grounded StatCard grid.
#
# Closed window: Australia, men's T20I 2024-2025. Fielding tab cards:
# Matches, Catches (inclusive — catches_only + c&b), Stumpings,
# Run-outs; Catches/match, Stumpings/match, Run-outs/match, C&B.
# Three chips with envelopes (per-match rates).
#
# Numbers verified by independent SQL — see audit/teams_fielding_intl.sql.

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&tab=Fielding" \
  "Anchor — Aus 2024-25 men_intl Fielding"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Australia",
    "stats": {
        # Row 1
        "Matches":   {"value": "22"},
        "Catches":   {"value": "125"},   # inclusive (catches_only 124 + c&b 1)
        "Stumpings": {"value": "2"},
        "Run-outs":  {"value": "9"},
        # Row 2
        "Catches/match":   {"value": "5.68", "chip_value": 5.68, "chip_avg": 3.96, "chip_delta": 43.4},
        "Stumpings/match": {"value": "0.09", "chip_value": 0.09, "chip_avg": 0.17, "chip_delta": -47.1},
        "Run-outs/match":  {"value": "0.41", "chip_value": 0.41, "chip_avg": 0.77, "chip_delta": -46.8},
        "C&B":             {"value": "1"},
    },
}
PYEXPECT
)

run_team_overview_assertions "Aus 24-25 Fielding" "$JSON" "$EXPECTED"; record_result $?

print_summary
