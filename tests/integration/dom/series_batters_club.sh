#!/bin/bash
# Series > Batters (club). Anchor: Indian Premier League 2025.
# Three DataTables (one per leaderboard mode):
#   Table 0 — By runs scored
#   Table 1 — By average (min_balls + min_dismissals threshold)
#   Table 2 — By strike rate (min_balls threshold)
#
# Top rows (verified via API + SQL):
#   T0 row 0 — B Sai Sudharsan   759 runs, 486 balls, SR 156.17 (orange cap)
#   T1 row 0 — SA Yadav          717 runs, 427 balls, avg 65.18, SR 167.92
#   T2 row 0 — V Suryavanshi     SR 208.26, 252 runs, 121 balls
#                                 (Vaibhav Suryavanshi — 14yo phenom)
#
# Numbers verified by independent SQL — see audit/series_batters_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_batters_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&gender=male&team_type=club&tab=Batters" \
  "Anchor — Series Batters IPL 2025 (3 tables)"
sleep 4

# Table 0 — By runs scored.
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # Row 0 — orange cap.
        (0, [(0, "B Sai Sudharsan"), (1, "759"), (2, "486"), (3, "156.17")]),
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
        (0, [(0, "SA Yadav"), (1, "717"), (3, "65.18"), (4, "167.92")]),
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
        # Row 0 — V Suryavanshi (14yo Rajasthan Royals debutant who tore
        # up IPL 2025 — 121 balls but the highest SR in scope).
        (0, [(0, "V Suryavanshi"), (1, "208.26"), (2, "252"), (3, "121")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Batters by_strike_rate" "$JSON_T2" "$EXPECTED_T2"; record_result $?

print_summary
