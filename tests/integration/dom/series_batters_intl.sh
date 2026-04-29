#!/bin/bash
# Series > Batters (intl). Anchor: ICC Men's T20 World Cup 2024.
# Three DataTables (one per leaderboard mode):
#   Table 0 — By runs scored
#   Table 1 — By average (min_balls=100 + min_dismissals=3 threshold)
#   Table 2 — By strike rate (min_balls=100 threshold)
#
# Top rows (verified via API + SQL):
#   T0 row 0 — TM Head        255 runs, 158 balls, SR 161.39
#   T1 row 0 — TM Head        255 runs, 158 balls, avg 51.00, SR 161.39
#                              (Head was top by both runs AND average)
#   T2 row 0 — RG Sharma      SR 164.90, 249 runs, 151 balls
#                              (Rohit pipped Head by 3.5 SR points)
#
# Numbers verified by independent SQL — see audit/series_batters_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_batters_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&gender=male&team_type=international&tab=Batters" \
  "Anchor — Series Batters T20 WC Men 2024 (3 tables)"
sleep 4   # +4s soak — 3 fan-out fetches

# Table 0 — By runs scored.
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # Row 0 — top run-scorer of the tournament.
        # cols: Batter | Runs | Balls | SR
        (0, [(0, "TM Head"), (1, "255"), (2, "158"), (3, "161.39")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Batters by_runs" "$JSON_T0" "$EXPECTED_T0"; record_result $?

# Table 1 — By average.
JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # Row 0 — Head was top by both runs and average.
        # cols: Batter | Runs | Balls | Avg | SR
        (0, [(0, "TM Head"), (1, "255"), (3, "51.00"), (4, "161.39")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Batters by_average" "$JSON_T1" "$EXPECTED_T1"; record_result $?

# Table 2 — By strike rate.
JSON_T2=$(extract_data_table 2 2>/dev/null)
EXPECTED_T2=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # Row 0 — Rohit pipped Head by 3.5 SR points.
        # cols: Batter | SR | Runs | Balls
        (0, [(0, "RG Sharma"), (1, "164.90"), (2, "249"), (3, "151")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Batters by_strike_rate" "$JSON_T2" "$EXPECTED_T2"; record_result $?

print_summary
