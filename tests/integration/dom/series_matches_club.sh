#!/bin/bash
# Series > Matches (club). Anchor: Indian Premier League 2025 — 74
# matches, paginated 50/page (MATCHES_PAGE_SIZE in TournamentDossier).
# Two navigations needed to verify dataset boundaries:
#
#   Page 1 (default):
#     50 rows. Row 0 = the Final (2025-06-03 RCB v PBKS, RCB won
#     by 6 runs).
#
#   Page 2 (?page=2):
#     24 rows. Row 23 = the Opener (2025-03-22 KKR v RCB, RCB won).
#
# Total = 50 + 24 = 74.
#
# Numbers verified by independent SQL — see audit/series_matches_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_matches_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR 1 — Page 1 (the Final) ───────────────
navigate "$BASE/series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&gender=male&team_type=club&tab=Matches" \
  "Anchor P1 — IPL 2025 Matches page 1 (50 visible, the Final)"
sleep 3   # extra soak — table re-renders after pagination wires up

JSON_P1=$(extract_data_table 2>/dev/null)

EXPECTED_P1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 50,
    "total_label_contains": "Page 1 of 2",
    "row_assertions": [
        # Row 0 — most recent. The IPL 2025 Final, RCB beat PBKS by 6 runs.
        (0, [(0, "2025-06-03"), (1, "2025"),
             (2, "Royal Challengers Bengaluru"), (2, "Punjab Kings"),
             (3, "Royal Challengers Bengaluru")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "IPL 2025 Matches P1" "$JSON_P1" "$EXPECTED_P1"; record_result $?

# ─────────────── ANCHOR 2 — Page 2 (the Opener) ───────────────
navigate "$BASE/series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&gender=male&team_type=club&tab=Matches&page=2" \
  "Anchor P2 — IPL 2025 Matches page 2 (24 visible, the Opener)"
sleep 3

JSON_P2=$(extract_data_table 2>/dev/null)

EXPECTED_P2=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 24,
    "total_label_contains": "Page 2 of 2",
    "row_assertions": [
        # Row 23 — oldest. The IPL 2025 Opener, RCB beat KKR by 7 wickets.
        (23, [(0, "2025-03-22"), (1, "2025"),
              (2, "Kolkata Knight Riders"), (2, "Royal Challengers Bengaluru"),
              (3, "Royal Challengers Bengaluru")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "IPL 2025 Matches P2" "$JSON_P2" "$EXPECTED_P2"; record_result $?

print_summary
