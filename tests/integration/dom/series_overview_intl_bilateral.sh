#!/bin/bash
# Series > Overview (intl, bilateral rivalry). Anchor: India vs
# England men_intl 2024-25, bilateral-only.
#
# Backed by /api/v1/series/summary?filter_team=India&filter_opponent=
# England&series_type=bilateral. The dossier reuses the regular
# Overview component but layers in a `by_team` block for h2h
# breakouts (top scorer per team, top wicket-taker per team, etc.)
# and the rivalry-mode StatCards (Matches | Team1 wins | Team2 wins
# | Ties | NR).
#
# 5 matches across the England tour of India in Jan/Feb 2025:
# India won 4, England won 1, run rate 8.79.
#
# The bilateral anchor that was deferred from Batch 2 — Ind-vs-Aus
# 24-25 (the spec's first suggestion) has zero bilateral matches in
# window (their only 24-25 meeting was a T20 WC SF — non-bilateral),
# so this script picks Ind-vs-Eng 24-25 instead.
#
# Numbers verified by independent SQL — see
# audit/series_overview_intl_bilateral.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_overview_intl_bilateral.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — Ind vs Eng bilateral 24-25 ───────────────
navigate "$BASE/series?filter_team=India&filter_opponent=England&gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral" \
  "Anchor — Series Overview Ind-vs-Eng bilateral 24-25"
sleep 4   # +4s soak — fan-out fetches need to resolve

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "India",
    "stats": {
        # rivalry cards (5 total: Matches / India / England / Ties / NR)
        "Matches":   {"value": "5"},
        "India":     {"value": "4"},
        "England":   {"value": "1"},
        "Ties":      {"value": "0"},
        "No result": {"value": "0"},
        # tournament-wide aggregates
        "Run rate":     {"value": "8.79"},
        "Boundary %":   {"value": "19.6"},
        "Dot %":        {"value": "38.3"},
        "Fours":        {"value": "138"},
        "Sixes":        {"value": "77"},
        # identity cards
        "Top scorer":        {"value": "Abhishek Sharma"},
        "Top wicket-taker":  {"value": "CV Varun"},
    },
}
PYEXPECT
)

run_team_overview_assertions "Ind-vs-Eng bilateral" "$JSON" "$EXPECTED"; record_result $?

print_summary
