#!/bin/bash
# Teams Partnerships (club anchor) — DOM-grounded by-wicket grid.
# Closed window: Royal Challengers Bengaluru, IPL 2025, batting side.

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Partnerships" \
  "Anchor — RCB IPL 2025 Partnerships (by-wicket)"

JSON=$(extract_data_table 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,
    "row_assertions": [
        # Top row: wkt 1
        (0, [(0, "1"), (1, "15"), (2, "45.5"), (4, "97")]),
        # Bottom row: wkt 10
        (9, [(0, "10"), (1, "1"), (2, "2"), (4, "2")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "RCB IPL 2025 Partnerships by-wicket" "$JSON" "$EXPECTED"; record_result $?

print_summary
