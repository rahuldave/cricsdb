#!/bin/bash
# Teams > vs Opponent — club rivalry. Anchor: RCB vs Punjab Kings,
# IPL 2025 (4 matches: 3 wins, 1 loss — covers two league legs +
# Qualifier 1 + the Final on 2025-06-03 which RCB won by 6 runs).
# Picked over RCB-vs-MI (1 match) for a richer baseline.
#
# Backed by /api/v1/teams/Royal Challengers Bengaluru/vs/Punjab Kings.
# As with the intl twin, the page renders TWO StatCard rows — the
# top RCB summary then the vs-section. Last-write-wins keying means
# Matches/Wins/Losses pull from vs-row (4/3/1) and Ties is vs-only (0).
#
# Closed historical window — values stay stable across rebuilds.
# Numbers verified by independent SQL — see
# audit/teams_vs_opponent_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/teams_vs_opponent_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — RCB vs PBKS IPL 2025 ───────────────
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=vs+Opponent&vs=Punjab+Kings" \
  "Anchor — RCB vs Punjab Kings IPL 2025 vs-Opponent stats"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Royal Challengers Bengaluru",
    "stats": {
        # vs-section StatCards (overrides team-summary for shared labels).
        "Matches": {"value": "4"},
        "Wins":    {"value": "3"},
        "Losses":  {"value": "1"},
        "Ties":    {"value": "0"},
    },
}
PYEXPECT
)

run_team_overview_assertions "RCB-vs-PBKS IPL 2025" "$JSON" "$EXPECTED"; record_result $?

print_summary
