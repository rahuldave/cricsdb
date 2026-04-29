#!/bin/bash
# Teams Overview (club anchor) — DOM-grounded summary band assertions.
#
# Closed window: Royal Challengers Bengaluru, IPL 2025. Asserts the
# always-on summary band on /teams?team=RCB&...
#
# Numbers verified by independent SQL — see audit/teams_overview_club.sql.
#
# Prereqs: agent-browser, vite :5173, uvicorn :8000.
# Run: ./tests/integration/dom/teams_overview_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — RCB IPL 2025 ───────────────
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025" \
  "Anchor — RCB IPL 2025 Overview"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Royal Challengers Bengaluru",
    "stats": {
        "Matches": {"value": "15"},
        "Wins":    {"value": "11"},
        "Losses":  {"value": "4"},
        "Win %":   {
            "value": "73.3%",
            "chip_value": 73.3,
            "chip_avg":   47.3,
            "chip_delta": 55.0,
        },
    },
    # Single keeper for RCB in IPL 2025 (Jitesh Sharma).
    "min_keepers": 1,
}
PYEXPECT
)

run_team_overview_assertions "RCB IPL 2025 Overview" "$JSON" "$EXPECTED"; record_result $?

print_summary
