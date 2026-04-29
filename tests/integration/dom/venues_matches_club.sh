#!/bin/bash
# /venues?venue=Wankhede+Stadium&tab=Matches — venue match list.
# Anchor: Wankhede Stadium IPL 2025. 7 matches DESC by date,
# single page (≤ MATCHES_PAGE_SIZE = 50).
#
#   Row 0 — 2025-05-21 MI v DC          → MI won (last home match)
#   Row 6 — 2025-03-31 KKR v MI          → MI won (home opener)
#
# Numbers verified by independent SQL — see audit/venues_matches_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/venues_matches_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/venues?venue=Wankhede+Stadium&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Matches" \
  "Anchor — Wankhede IPL 2025 Matches (7 rows)"
sleep 4

JSON=$(extract_data_table 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 7,
    "row_assertions": [
        # Row 0 — most recent. cols: Date | Tournament | Season | Match | Winner | Score
        (0, [(0, "2025-05-21"), (1, "Indian Premier League"), (2, "2025"),
             (3, "Mumbai Indians"), (3, "Delhi Capitals"), (4, "Mumbai Indians")]),
        # Row 6 — oldest (the home opener).
        (6, [(0, "2025-03-31"),
             (3, "Kolkata Knight Riders"), (3, "Mumbai Indians"),
             (4, "Mumbai Indians")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "Wankhede IPL 2025 Matches" "$JSON" "$EXPECTED"; record_result $?

print_summary
