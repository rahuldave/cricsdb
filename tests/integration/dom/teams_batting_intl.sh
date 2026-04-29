#!/bin/bash
# Teams Batting (intl anchor) — DOM-grounded StatCard grid assertions.
#
# Closed window: Australia, men's T20I 2024-2025. The Batting tab
# renders 3 rows × 5 cards = 15 StatCards: Innings, Runs, Run rate,
# Boundary %, Dot %, 4s, 6s, 50s, 100s, 50s/100s per inn,
# Avg 1st-inn total, Avg 2nd-inn total, Highest total, Lowest all-out,
# Avg innings total. Five carry chip envelopes; the rest are absolute
# counts. Charts (run rate / boundary % / fours / sixes by season)
# are deferred to a Batch 3 chart-DOM extractor.
#
# Numbers verified by independent SQL — see audit/teams_batting_intl.sql.
#
# Prereqs: agent-browser, vite :5173, uvicorn :8000.
# Run: ./tests/integration/dom/teams_batting_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — Aus 2024-25 men_intl, Batting tab ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&tab=Batting" \
  "Anchor — Aus 2024-25 men_intl Batting"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Australia",
    "stats": {
        # Row 1
        "Innings":     {"value": "22"},
        "Runs":        {"value": "3,614"},                   # toLocaleString — comma format
        "Run rate":    {"value": "9.91", "chip_value": 9.91, "chip_avg": 7.52, "chip_delta": 31.8},
        "Boundary %":  {"value": "23.1%", "chip_value": 23.1, "chip_avg": 14.3, "chip_delta": 61.5},
        "Dot %":       {"value": "35.6%", "chip_value": 35.6, "chip_avg": 42.0, "chip_delta": -15.2},
        # Row 2
        "4s":  {"value": "304"},
        "6s":  {"value": "201"},
        "50s": {"value": "21"},
        "100s":{"value": "2"},
        # 50s/100s per inn = (21+2) / 22 = 1.05 → "1.05"
        "50s / 100s per inn": {"value": "1.05"},
        # Row 3
        "Avg 1st-inn total": {"value": "168.9", "chip_value": 168.9, "chip_avg": 146.5, "chip_delta": 15.3},
        "Avg 2nd-inn total": {"value": "161.6", "chip_value": 161.6, "chip_avg": 121.9, "chip_delta": 32.6},
        "Highest total":     {"value": "215"},
        "Lowest all-out":    {"value": "165"},
        # Avg innings total = 3614 / 22 = 164.27 → 164.3
        "Avg innings total": {"value": "164.3"},
    },
}
PYEXPECT
)

run_team_overview_assertions "Aus 24-25 Batting" "$JSON" "$EXPECTED"; record_result $?

print_summary
