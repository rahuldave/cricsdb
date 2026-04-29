#!/bin/bash
# /venues?venue=Wankhede+Stadium&tab=Fielders — venue-filtered
# fielder leaderboard. Anchor: Wankhede Stadium IPL 2025.
#
# Two tables:
#   T0 By dismissals (10 rows): RD Rickelton 10 / 6 C / 4 St / 0 RO
#   T1 By keeper      (1 row):  RD Rickelton 10 / 6 / 4
#                                (only one designated keeper at
#                                 Wankhede in IPL 2025 — Rickelton
#                                 keeped MI's home matches)
#
# Numbers verified by independent SQL — see audit/venues_fielders_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/venues_fielders_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/venues?venue=Wankhede+Stadium&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Fielders" \
  "Anchor — Wankhede IPL 2025 Fielders (2 tables)"
sleep 4

JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Fielder | Total | C | St | RO
        (0, [(0, "RD Rickelton"), (1, "10"), (2, "6"), (3, "4"), (4, "0")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Wankhede Fielders by_dismissals" "$JSON_T0" "$EXPECTED_T0"; record_result $?

JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 1,
    "row_assertions": [
        (0, [(0, "RD Rickelton"), (1, "10"), (2, "6"), (3, "4")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Wankhede Fielders by_keeper" "$JSON_T1" "$EXPECTED_T1"; record_result $?

print_summary
