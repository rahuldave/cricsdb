#!/bin/bash
# Series > Fielders (intl). Anchor: ICC Men's T20 World Cup 2024.
# Three DataTables (one per leaderboard mode):
#   T0 (By dismissals all): RR Pant   13 / 10 C / 1 St / 2 RO
#   T1 (By keeper dismissals): RR Pant 11 / 10 C / 1 St (15 keepers ranked)
#   T2 (By run-outs):       RR Pant   2 RO / 13 total
#                            (he topped all three lists in 2024 — Pant
#                             returned in style after the car accident)
#
# Numbers verified by independent SQL — see audit/series_fielders_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_fielders_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&gender=male&team_type=international&tab=Fielders" \
  "Anchor — Series Fielders T20 WC Men 2024 (3 tables)"
sleep 4

# Table 0 — By dismissals (all).
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # cols: Fielder | Total | C | St | RO
        (0, [(0, "RR Pant"), (1, "13"), (2, "10"), (3, "1"), (4, "2")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Fielders by_dismissals" "$JSON_T0" "$EXPECTED_T0"; record_result $?

# Table 1 — By keeper dismissals.
JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 15,
    "row_assertions": [
        # cols: Keeper | Total | C | St
        (0, [(0, "RR Pant"), (1, "11"), (2, "10"), (3, "1")]),
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
        (0, [(0, "RR Pant"), (1, "2"), (2, "13"), (3, "10"), (4, "1")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Fielders by_run_outs" "$JSON_T2" "$EXPECTED_T2"; record_result $?

print_summary
