#!/bin/bash
# Series > Bowlers (intl). Anchor: ICC Men's T20 World Cup 2024.
# Three DataTables (one per leaderboard mode); the DOM order is
# wickets / strike_rate / economy (NOT the API JSON key order which
# is wickets / strike_rate / economy in the response, but the keys
# are visited as wickets-strike_rate-economy by the page render).
#
#   T0 (By wickets):     Arshdeep Singh  14 W, 156 balls, econ 7.19
#   T1 (By strike rate): N Thushara      SR 8.00, 8 W, 64 balls
#   T2 (By economy):     LH Ferguson     econ 3.17, 6 W, 72 balls
#
# Numbers verified by independent SQL — see audit/series_bowlers_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_bowlers_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&gender=male&team_type=international&tab=Bowlers" \
  "Anchor — Series Bowlers T20 WC Men 2024 (3 tables)"
sleep 4

# Table 0 — By wickets.
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # cols: Bowler | W | Balls | Econ
        (0, [(0, "Arshdeep Singh"), (1, "14"), (2, "156"), (3, "7.19")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Bowlers by_wickets" "$JSON_T0" "$EXPECTED_T0"; record_result $?

# Table 1 — By strike rate.
JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # cols: Bowler | SR | W | Balls
        (0, [(0, "N Thushara"), (1, "8.00"), (2, "8"), (3, "64")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Bowlers by_strike_rate" "$JSON_T1" "$EXPECTED_T1"; record_result $?

# Table 2 — By economy.
JSON_T2=$(extract_data_table 2 2>/dev/null)
EXPECTED_T2=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # cols: Bowler | Econ | W | Balls
        (0, [(0, "LH Ferguson"), (1, "3.17"), (2, "6"), (3, "72")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Bowlers by_economy" "$JSON_T2" "$EXPECTED_T2"; record_result $?

print_summary
