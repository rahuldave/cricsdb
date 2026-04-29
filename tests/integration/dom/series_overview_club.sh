#!/bin/bash
# Series Overview (club anchor) — DOM-grounded summary StatCard grid.
# Closed window: IPL 2025 (74 matches).

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=Indian+Premier+League&gender=male&team_type=club&season_from=2025&season_to=2025" \
  "Anchor — IPL 2025 Overview"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Indian Premier League",
    "stats": {
        "Matches":    {"value": "74"},
        "Run rate":   {"value": "9.63"},
        "Boundary %": {"value": "21.6"},  # API 21.55 → 21.6 (1-decimal)
        "Dot %":      {"value": "32.3"},  # API 32.34 → 32.3
        "Fours":      {"value": "2,257"}, # toLocaleString
        "Sixes":      {"value": "1,301"},
    },
}
PYEXPECT
)

run_team_overview_assertions "IPL 2025 Overview" "$JSON" "$EXPECTED"; record_result $?

print_summary
