#!/bin/bash
# Teams Overview (intl anchor) — DOM-grounded summary band assertions.
#
# Closed window: Australia, men's T20I 2024-2025. The "Overview" tab
# is the default landing — it renders the always-on summary band
# (StatCards above the tab bar) PLUS the "Wins by Season" bar chart
# inside the By Season tab. This script asserts the summary-band
# numbers; the bar chart bars are deferred to a Batch 3 chart-DOM
# extractor.
#
# Numbers verified by independent SQL — see audit/teams_overview_intl.sql.
#
# Prereqs: agent-browser, vite :5173, uvicorn :8000.
# Run: ./tests/integration/dom/teams_overview_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — Aus 2024-25 men_intl ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025" \
  "Anchor — Aus 2024-25 men_intl Overview"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Australia",
    "stats": {
        "Matches": {"value": "22"},
        "Wins":    {"value": "19"},
        "Losses":  {"value": "3"},
        "Win %":   {
            "value": "86.4%",
            "chip_value": 86.4,
            "chip_avg":   48.45,
            "chip_delta": 78.3,
        },
    },
    # API summary returns 3 keepers; SQL audit O3 says 9 distinct
    # keeper_ids ever assigned (the API summary collapses by ranking
    # innings_kept). Just assert ≥1 — the summary's Keepers row IS
    # rendered for any active intl team in scope.
    "min_keepers": 1,
}
PYEXPECT
)

run_team_overview_assertions "Aus 24-25 Overview" "$JSON" "$EXPECTED"; record_result $?

print_summary
