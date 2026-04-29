#!/bin/bash
# Teams > Match List — club twin of teams_match_list_intl_fm. Anchor:
# RCB IPL 2025 (single closed-league season). 15 rows, DESC by date.
#
# First row (most recent): 2025-06-03 vs Punjab Kings (the final — RCB won
#                          by 6 runs)
# Last row (oldest):       2025-03-22 vs Kolkata Knight Riders (the opener)
#
# Closed historical window — values stay stable across rebuilds.
# Numbers verified by independent SQL — see
# audit/teams_match_list_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/teams_match_list_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — RCB IPL 2025 (15 matches) ───────────────
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Match+List" \
  "Anchor — RCB IPL 2025 match list (15)"

JSON=$(extract_data_table 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 15,
    "total_label_contains": "of 15",
    "row_assertions": [
        # Row 0 — most recent (DESC sort) — IPL 2025 final, RCB won by 6 runs.
        (0, [(0, "2025-06-03"), (1, "Punjab Kings"), (3, "Indian Premier League"), (4, "won"), (5, "6 runs")]),
        # Row 14 — oldest in window — IPL 2025 opener vs KKR (RCB won).
        (14, [(0, "2025-03-22"), (1, "Kolkata Knight Riders"), (3, "Indian Premier League"), (4, "won"), (5, "7 wickets")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "RCB IPL 2025" "$JSON" "$EXPECTED"; record_result $?

print_summary
