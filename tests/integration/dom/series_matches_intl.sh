#!/bin/bash
# Series > Matches (intl). Anchor: ICC Men's T20 World Cup 2024.
# 44 matches DESC by date. Single DataTable on the page (no
# multi-leaderboard mode-picker), so bare extract_data_table works.
#
#   Row 0  — 2024-06-29 — India v South Africa — India won (the Final)
#   Row 43 — 2024-06-01 — Canada v USA          — USA won (the Opener)
#
# Numbers verified by independent SQL — see audit/series_matches_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_matches_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — T20 WC Men 2024 Matches ───────────────
navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&gender=male&team_type=international&tab=Matches" \
  "Anchor — Series Matches T20 WC Men 2024 (44)"

JSON=$(extract_data_table 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 44,
    "row_assertions": [
        # Row 0 — most recent (DESC). The Final, India beat South Africa.
        # Date / Season / Match (team1 v team2) / Winner.
        (0, [(0, "2024-06-29"), (1, "2024"),
             (2, "India"), (2, "South Africa"), (3, "India")]),
        # Row 43 — oldest in window. The Opener, USA beat Canada.
        (43, [(0, "2024-06-01"), (1, "2024"),
              (2, "Canada"), (2, "United States of America"),
              (3, "United States of America")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "T20 WC Men 2024 Matches" "$JSON" "$EXPECTED"; record_result $?

print_summary
