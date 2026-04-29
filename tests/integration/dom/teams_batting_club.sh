#!/bin/bash
# Teams Batting (club anchor) — DOM-grounded StatCard grid assertions.
#
# Closed window: Royal Challengers Bengaluru, IPL 2025. Same 15-card
# layout as teams_batting_intl.sh against a closed-league baseline
# (74-match season — IPL avg defines the chip baseline).
#
# Numbers verified by independent SQL — see audit/teams_batting_club.sql.
#
# Run: ./tests/integration/dom/teams_batting_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — RCB IPL 2025, Batting tab ───────────────
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Batting" \
  "Anchor — RCB IPL 2025 Batting"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "Royal Challengers Bengaluru",
    "stats": {
        # Row 1
        "Innings":     {"value": "15"},
        "Runs":        {"value": "2,653"},
        "Run rate":    {"value": "9.69", "chip_value": 9.69, "chip_avg": 9.63, "chip_delta": 0.6},
        "Boundary %":  {"value": "22.1%", "chip_value": 22.1, "chip_avg": 21.6, "chip_delta": 2.3},
        "Dot %":       {"value": "32.2%", "chip_value": 32.2, "chip_avg": 32.3, "chip_delta": -0.3},
        # Row 2
        "4s":  {"value": "238"},
        "6s":  {"value": "125"},
        "50s": {"value": "20"},
        "100s":{"value": "0"},
        # 50s/100s per inn = (20+0) / 15 = 1.33
        "50s / 100s per inn": {"value": "1.33"},
        # Row 3
        "Avg 1st-inn total": {"value": "181.5", "chip_value": 181.5, "chip_avg": 188.8, "chip_delta": -3.9},
        "Avg 2nd-inn total": {"value": "171.6", "chip_value": 171.6, "chip_avg": 174.0, "chip_delta": -1.4},
        "Highest total":     {"value": "230"},
        "Lowest all-out":    {"value": "189"},
        # Avg innings total = 2653 / 15 = 176.87 → 176.9
        "Avg innings total": {"value": "176.9"},
    },
}
PYEXPECT
)

run_team_overview_assertions "RCB IPL 2025 Batting" "$JSON" "$EXPECTED"; record_result $?

print_summary
