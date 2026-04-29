#!/bin/bash
# /venues?venue=Eden+Gardens&tab=Records — venue Records fan-out.
# Anchor: Eden Gardens men_intl all-time. Renders 7 DataTables:
#
#   T0 Highest team totals     — 207 Scotland v Italy 2026-02-09
#   T1 Lowest all-out totals   —  70 Bangladesh v NZ  2016-03-26
#                                  (the WC 2016 group-stage rout)
#   T2 Biggest wins by runs    —  75 NZ beat BD 2016-03-26 (same match)
#   T3 Biggest wins by wickets —   9 NZ beat SA 2026-03-04
#   T4 Largest partnerships    — 126 Munsey & Jones 2026-02-09
#   T5 Best bowling figures    — 5/20 R Shepherd 2026-02-07
#   T6 Most sixes in a match   —  25 Eng v Italy 2026-02-16
#
# Asserts row 0 of each table. 5 rows per table (page-size cap).
#
# Numbers verified by independent SQL — see audit/venues_records_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/venues_records_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/venues?venue=Eden+Gardens&gender=male&team_type=international&tab=Records" \
  "Anchor — Eden Gardens men_intl Records (7 tables)"
sleep 5   # +5s soak — 7 fan-out fetches

# T0 — Highest team totals.
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Runs | Team | vs | Date
        (0, [(0, "207"), (1, "Scotland"), (2, "Italy"), (3, "2026-02-09")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Records highest_team_total" "$JSON_T0" "$EXPECTED_T0"; record_result $?

# T1 — Lowest all-out totals.
JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        (0, [(0, "70"), (1, "Bangladesh"), (2, "New Zealand"), (3, "2016-03-26")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Records lowest_all_out" "$JSON_T1" "$EXPECTED_T1"; record_result $?

# T2 — Biggest wins by runs.
JSON_T2=$(extract_data_table 2 2>/dev/null)
EXPECTED_T2=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Runs | Winner | Loser | Date — same match as T1 row 0.
        (0, [(0, "75"), (1, "New Zealand"), (2, "Bangladesh"), (3, "2016-03-26")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Records biggest_wins_runs" "$JSON_T2" "$EXPECTED_T2"; record_result $?

# T3 — Biggest wins by wickets.
JSON_T3=$(extract_data_table 3 2>/dev/null)
EXPECTED_T3=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Wkts | Winner | Loser | Date
        (0, [(0, "9"), (1, "New Zealand"), (2, "South Africa"), (3, "2026-03-04")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Records biggest_wins_wickets" "$JSON_T3" "$EXPECTED_T3"; record_result $?

# T4 — Largest partnerships.
JSON_T4=$(extract_data_table 4 2>/dev/null)
EXPECTED_T4=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Runs | Batters | Date
        (0, [(0, "126"), (1, "HG Munsey"), (1, "MA Jones"), (2, "2026-02-09")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Records largest_partnership" "$JSON_T4" "$EXPECTED_T4"; record_result $?

# T5 — Best bowling figures.
JSON_T5=$(extract_data_table 5 2>/dev/null)
EXPECTED_T5=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Figures | Bowler | Date
        (0, [(0, "5/20"), (1, "R Shepherd"), (2, "2026-02-07")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Records best_bowling" "$JSON_T5" "$EXPECTED_T5"; record_result $?

# T6 — Most sixes in a match.
JSON_T6=$(extract_data_table 6 2>/dev/null)
EXPECTED_T6=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Sixes | Teams | Date
        (0, [(0, "25"), (1, "England"), (1, "Italy"), (2, "2026-02-16")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Eden Records most_sixes" "$JSON_T6" "$EXPECTED_T6"; record_result $?

print_summary
