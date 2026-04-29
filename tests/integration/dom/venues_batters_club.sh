#!/bin/bash
# /venues?venue=Wankhede+Stadium&tab=Batters — club anchor.
# Anchor: Wankhede Stadium IPL 2025. Same 2-table shape as
# venues_batters_intl.
#
#   T0 By average:     SA Yadav 311r/175b/77.75/SR 177.71
#   T1 By strike rate: SA Yadav SR 177.71/311r/175b (Yadav tops
#                       both modes — 7-match venue pool, 3 rows
#                       per table)
#
# Numbers verified by independent SQL — see audit/venues_batters_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/venues_batters_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/venues?venue=Wankhede+Stadium&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Batters" \
  "Anchor — Wankhede IPL 2025 Batters (2 tables)"
sleep 4

JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 3,
    "row_assertions": [
        (0, [(0, "SA Yadav"), (1, "311"), (2, "175"), (3, "77.75"), (4, "177.71")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Wankhede Batters by_average" "$JSON_T0" "$EXPECTED_T0"; record_result $?

JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 3,
    "row_assertions": [
        (0, [(0, "SA Yadav"), (1, "177.71"), (2, "311"), (3, "175")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Wankhede Batters by_strike_rate" "$JSON_T1" "$EXPECTED_T1"; record_result $?

print_summary
