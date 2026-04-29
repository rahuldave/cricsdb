#!/bin/bash
# Series Overview (intl anchor) — DOM-grounded summary StatCard grid.
#
# Closed window: T20 World Cup Men 2024 (44 matches). The Series
# dossier's Overview tab is the default landing — renders one row of
# 6 StatCards (Matches, Run rate, Boundary %, Dot %, Fours, Sixes)
# plus a leaders row (Most titles, Top scorer, Top wicket-taker).
# Asserts the 6-card row; leader cards contain composed TeamLink/
# PlayerLink elements deferred to a Batch 3 leader-extractor.
#
# Numbers verified by independent SQL — see audit/series_overview_intl.sql.

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&gender=male&team_type=international&season_from=2024&season_to=2024" \
  "Anchor — T20 WC Men 2024 Overview"

JSON=$(extract_team_overview 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "team_name": "ICC Men's T20 World Cup",
    "stats": {
        "Matches":    {"value": "44"},
        "Run rate":   {"value": "7.13"},
        "Boundary %": {"value": "13.6"},  # API returns 13.62, fmt(_, 1) → "13.6"
        "Dot %":      {"value": "44.4"},  # API 44.41 → "44.4"
        "Fours":      {"value": "814"},
        "Sixes":      {"value": "454"},
    },
}
PYEXPECT
)

run_team_overview_assertions "T20 WC Men 2024 Overview" "$JSON" "$EXPECTED"; record_result $?

print_summary
