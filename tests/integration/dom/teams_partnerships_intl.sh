#!/bin/bash
# Teams Partnerships (intl anchor) — DOM-grounded by-wicket grid.
#
# Closed window: Aus 2024-25 men_intl, batting side. The Partnerships
# tab renders multiple DataTables (by-wicket, best-pairs, top-N);
# extract_data_table grabs the FIRST (by-wicket grid). Asserts top
# row (wkt 1) and bottom row (wkt 10) — the spec's "first and last
# row" rule for tabular surfaces (catches ordering bugs that show
# the right top row but wrong tail).
#
# Numbers verified by independent SQL — see audit/teams_partnerships_intl.sql.
# Run: ./tests/integration/dom/teams_partnerships_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&tab=Partnerships" \
  "Anchor — Aus 2024-25 men_intl Partnerships (by-wicket)"

JSON=$(extract_data_table 2>/dev/null)

# DataTable columns (from JSX wicketColumns):
#   0: Wkt    1: n    2: Avg runs    3: Avg balls    4: Best (runs)
#   5: Highest single partnership (formatted text)
EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,         # wickets 1-10
    "row_assertions": [
        # Top row: wkt 1
        (0, [(0, "1"), (1, "22"), (2, "26.5"), (4, "86")]),
        # Bottom row: wkt 10
        (9, [(0, "10"), (1, "3"), (2, "6.3"), (4, "12")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "Aus 24-25 Partnerships by-wicket" "$JSON" "$EXPECTED"; record_result $?

print_summary
