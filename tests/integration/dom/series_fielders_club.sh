#!/bin/bash
# Series > Fielders (club). Anchor: Indian Premier League 2025.
# Three DataTables — same shape as the intl twin.
#
#   T0 (By dismissals all): JM Sharma    22 / 19 C / 1 St / 2 RO
#                            (RCB's keeper-cum-finisher Jitesh)
#   T1 (By keeper dismissals): JM Sharma 20 / 19 / 1 (13 keepers ranked)
#   T2 (By run-outs):       RD Rickelton 4 RO / 20 total / 11 C / 5 St
#                            (MI's keeper, top of the run-out chart
#                             ahead of JM Sharma's 2)
#
# Numbers verified by independent SQL — see audit/series_fielders_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_fielders_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&gender=male&team_type=club&tab=Fielders" \
  "Anchor — Series Fielders IPL 2025 (3 tables)"
sleep 4

# Table 0 — By dismissals.
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        (0, [(0, "JM Sharma"), (1, "22"), (2, "19"), (3, "1"), (4, "2")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Fielders by_dismissals" "$JSON_T0" "$EXPECTED_T0"; record_result $?

# Table 1 — By keeper dismissals.
JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 13,
    "row_assertions": [
        (0, [(0, "JM Sharma"), (1, "20"), (2, "19"), (3, "1")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Fielders by_keeper" "$JSON_T1" "$EXPECTED_T1"; record_result $?

# Table 2 — By run-outs.
JSON_T2=$(extract_data_table 2 2>/dev/null)
EXPECTED_T2=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # cols: Fielder | RO | Total | C | St
        (0, [(0, "RD Rickelton"), (1, "4"), (2, "20"), (3, "11"), (4, "5")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Fielders by_run_outs" "$JSON_T2" "$EXPECTED_T2"; record_result $?

print_summary
