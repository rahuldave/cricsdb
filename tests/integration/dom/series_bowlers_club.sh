#!/bin/bash
# Series > Bowlers (club). Anchor: Indian Premier League 2025.
# Three DataTables — same shape as the intl twin.
#
#   T0 (By wickets):     M Prasidh Krishna  25 W, 354 balls, econ 8.58 (purple cap)
#   T1 (By strike rate): W O'Rourke         SR 10.33, 6 W, 62 balls
#   T2 (By economy):     JJ Bumrah          econ 6.80, 18 W, 284 balls
#
# Numbers verified by independent SQL — see audit/series_bowlers_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_bowlers_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&gender=male&team_type=club&tab=Bowlers" \
  "Anchor — Series Bowlers IPL 2025 (3 tables)"
sleep 4

# Table 0 — By wickets.
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        (0, [(0, "M Prasidh Krishna"), (1, "25"), (2, "354"), (3, "8.58")]),
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
        (0, [(0, "W O'Rourke"), (1, "10.33"), (2, "6"), (3, "62")]),
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
        (0, [(0, "JJ Bumrah"), (1, "6.80"), (2, "18"), (3, "284")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Bowlers by_economy" "$JSON_T2" "$EXPECTED_T2"; record_result $?

print_summary
