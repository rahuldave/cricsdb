#!/bin/bash
# Series > Points (club). Anchor: Indian Premier League 2025 league
# stage. /api/v1/series/points-table excludes playoffs (Final,
# Qualifier 1, Eliminator, Qualifier 2) and reconstructs the
# standings + NRR from delivery aggregates.
#
# Single round-robin → one DataTable, 10 rows DESC by points then NRR:
#
#   Row 0 — Punjab Kings    15 P, 9 W, 4 L, 0 T, 2 NR, 20 pts (top)
#   Row 1 — Royal Challengers Bengaluru  13 P, 9 W, 18 pts
#   Row 9 — Chennai Super Kings          14 P, 4 W, 10 L, 8 pts (wooden spoon)
#
# IPL 2025 had a replayed PBKS-DC match after the May 2025 mid-season
# pause, so PBKS + DC played 15; RCB + KKR played 13 (their match
# was canceled and not rescheduled). Other teams played 14 — the
# standard IPL format.
#
# Numbers verified by independent SQL — see audit/series_points_club.sql.
#
# No intl twin — ICC events have group-stage tables but they're
# rendered inside the per-edition Editions tab, not via the
# top-level Points tab.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_points_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — IPL 2025 Points ───────────────
navigate "$BASE/series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&gender=male&team_type=club&tab=Points" \
  "Anchor — Series Points IPL 2025 (10 rows)"
sleep 4

JSON=$(extract_data_table 0 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,
    "row_assertions": [
        # Row 0 — top of league: PBKS 15P / 9W / 4L / 0T / 2NR / 20pts.
        # cols: Team | P | W | L | T | NR | Pts | NRR
        (0, [(0, "Punjab Kings"), (1, "15"), (2, "9"), (3, "4"),
             (4, "0"), (5, "2"), (6, "20"), (7, "+0.342")]),
        # Row 1 — RCB 13P / 9W / 18pts (eventual champion via the
        # final, but second in league).
        (1, [(0, "Royal Challengers Bengaluru"), (1, "13"), (2, "9"),
             (6, "18")]),
        # Row 9 — wooden spoon: CSK 14P / 4W / 10L / 8pts.
        (9, [(0, "Chennai Super Kings"), (1, "14"), (2, "4"),
             (3, "10"), (6, "8"), (7, "-0.675")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "IPL 2025 Points" "$JSON" "$EXPECTED"; record_result $?

print_summary
