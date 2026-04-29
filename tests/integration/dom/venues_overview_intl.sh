#!/bin/bash
# /venues?venue=Eden+Gardens — Overview tab. The VenueDossier
# Overview band is a 9-StatCard row backed by
# /api/v1/venues/{venue}/summary. Anchor: Eden Gardens men_intl
# all-time (18 matches in cricsheet's record, spanning 2011/12
# through 2025/26).
#
# DOM:
#   Title:           "Eden Gardens · Kolkata"
#   StatCards:       Matches 18 / Avg 1st-inn 164.6 / Bat-first %
#                    50.0% / Chase % 50.0% / Tie+NR 0 / Chose bat 5 /
#                    Chose field 13 / Won toss+bat 80.0% / Won toss+
#                    field 61.5%.
#
# Numbers verified by independent SQL — see audit/venues_overview_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/venues_overview_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/venues?venue=Eden+Gardens&gender=male&team_type=international" \
  "Anchor — Eden Gardens men_intl Overview"
sleep 4

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Eden Gardens",
    "stats": {
        "Matches":           {"value": "18"},
        "Avg 1st-inn total": {"value": "164.6"},
        "Bat-first win %":   {"value": "50.0%"},
        "Chase win %":       {"value": "50.0%"},
        "Tie / NR":          {"value": "0"},
        "Chose to bat":      {"value": "5"},
        "Chose to field":    {"value": "13"},
        "Won toss + chose bat":   {"value": "80.0%"},
        "Won toss + chose field": {"value": "61.5%"},
    },
}
PYEXPECT
)

run_team_overview_assertions "Eden men_intl" "$JSON" "$EXPECTED"; record_result $?

print_summary
