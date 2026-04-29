#!/bin/bash
# Teams > vs Opponent — intl rivalry. Anchor: India vs Sri Lanka,
# men_intl 2024-25 (4 matches: 2 wins, 0 losses, 2 ties — exercises
# the tied-match path the 1-match WC 2024 SF rivalry wouldn't reach).
#
# Backed by /api/v1/teams/India/vs/Sri%20Lanka. The vs-Opponent tab
# renders TWO StatCard rows: the always-on team summary (India in
# scope: 34 matches across 24-25) followed by the vs-section
# (4 matches vs SL). The extract_team_overview extractor keys by
# label so the LATER row wins for shared labels (Matches, Wins,
# Losses); we only assert those four values + Ties (vs-row only).
# The team summary's Win % survives in the dict but we don't pin it
# here — that pinning is teams_overview_intl's job.
#
# Closed historical window — values stay stable across rebuilds.
# Numbers verified by independent SQL — see
# audit/teams_vs_opponent_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/teams_vs_opponent_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — India vs Sri Lanka 2024-25 ───────────────
navigate "$BASE/teams?team=India&gender=male&team_type=international&season_from=2024&season_to=2025&tab=vs+Opponent&vs=Sri+Lanka" \
  "Anchor — India vs Sri Lanka 24-25 vs-Opponent stats"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "India",
    "stats": {
        # vs-section StatCards (the second statrow on the page —
        # overrides the team-summary row's same labels).
        "Matches": {"value": "4"},
        "Wins":    {"value": "2"},
        "Losses":  {"value": "0"},
        "Ties":    {"value": "2"},
    },
}
PYEXPECT
)

run_team_overview_assertions "Ind-vs-SL 24-25" "$JSON" "$EXPECTED"; record_result $?

print_summary
