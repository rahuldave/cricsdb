#!/bin/bash
# /venues?venue=Eden+Gardens&tab=Batters — venue-filtered batter
# leaderboard. Anchor: Eden Gardens men_intl all-time.
#
# Renders TWO DataTables (NOT three like Series Batters): "By
# average" + "By strike rate". The by_runs mode is dropped at
# venue scope because at low match volumes (Eden = 18 matches),
# by_runs would just rank by appearances.
#
#   T0 By average:     N Pooran  184r/131b/61.33/SR 140.46
#   T1 By strike rate: R Powell  SR 153.70/166r/108b
#
# Numbers verified by independent SQL — see audit/venues_batters_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/venues_batters_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/venues?venue=Eden+Gardens&gender=male&team_type=international&tab=Batters" \
  "Anchor — Eden Gardens men_intl Batters (2 tables)"
sleep 4

JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Batter | Runs | Balls | Avg | SR
        (0, [(0, "N Pooran"), (1, "184"), (2, "131"), (3, "61.33"), (4, "140.46")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Batters by_average" "$JSON_T0" "$EXPECTED_T0"; record_result $?

JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Batter | SR | Runs | Balls
        (0, [(0, "R Powell"), (1, "153.70"), (2, "166"), (3, "108")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Batters by_strike_rate" "$JSON_T1" "$EXPECTED_T1"; record_result $?

print_summary
