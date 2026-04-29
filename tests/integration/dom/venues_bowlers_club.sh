#!/bin/bash
# /venues?venue=Wankhede+Stadium&tab=Bowlers — venue-filtered
# bowler leaderboard. Anchor: Wankhede Stadium IPL 2025 — JJ Bumrah
# tops both modes (12W/140b: SR 11.67, econ 5.49).
#
# Renders TWO tables (by_strike_rate + by_economy), NOT three —
# by_wickets dropped at venue scope (same as venues_batters_*).
#
#   T0 By strike rate: JJ Bumrah SR 11.67, 12W, 140b
#   T1 By economy:     JJ Bumrah econ 5.49, 12W, 140b
#
# Numbers verified by independent SQL — see audit/venues_bowlers_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/venues_bowlers_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/venues?venue=Wankhede+Stadium&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Bowlers" \
  "Anchor — Wankhede IPL 2025 Bowlers (2 tables)"
sleep 4

JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Bowler | SR | W | Balls
        (0, [(0, "JJ Bumrah"), (1, "11.67"), (2, "12"), (3, "140")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Wankhede Bowlers by_SR" "$JSON_T0" "$EXPECTED_T0"; record_result $?

JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Bowler | Econ | W | Balls
        (0, [(0, "JJ Bumrah"), (1, "5.49"), (2, "12"), (3, "140")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Wankhede Bowlers by_econ" "$JSON_T1" "$EXPECTED_T1"; record_result $?

print_summary
