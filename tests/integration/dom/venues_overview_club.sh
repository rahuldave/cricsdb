#!/bin/bash
# /venues?venue=Wankhede+Stadium — Overview tab, club anchor.
# Anchor: Wankhede Stadium (Mumbai) IPL 2025 — MI's home ground,
# 7 matches in 2025. All 7 toss winners chose to FIELD (the modern
# dew-friendly chase preference at Wankhede); chasing won 57.1%.
#
# DOM:
#   Title:        "Wankhede Stadium · Mumbai"
#   StatCards:    Matches 7 / Avg 1st-inn 175.0 / Bat-first 42.9% /
#                 Chase 57.1% / Tie+NR 0 / Chose bat 0 / Chose field 7
#                 / Won toss+bat "-" (no toss winner chose to bat) /
#                 Won toss+field 57.1%.
#
# Numbers verified by independent SQL — see audit/venues_overview_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/venues_overview_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/venues?venue=Wankhede+Stadium&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025" \
  "Anchor — Wankhede IPL 2025 Overview"
sleep 4

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Wankhede Stadium",
    "stats": {
        "Matches":           {"value": "7"},
        "Avg 1st-inn total": {"value": "175.0"},
        "Bat-first win %":   {"value": "42.9%"},
        "Chase win %":       {"value": "57.1%"},
        "Tie / NR":          {"value": "0"},
        "Chose to bat":      {"value": "0"},
        "Chose to field":    {"value": "7"},
        # Won-toss-bat shows "-" since no toss winner picked bat.
        "Won toss + chose bat":   {"value": "-"},
        "Won toss + chose field": {"value": "57.1%"},
    },
}
PYEXPECT
)

run_team_overview_assertions "Wankhede IPL 2025" "$JSON" "$EXPECTED"; record_result $?

print_summary
