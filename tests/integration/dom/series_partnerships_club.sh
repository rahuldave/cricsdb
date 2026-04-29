#!/bin/bash
# Series > Partnerships (club). Anchor: Indian Premier League 2025.
# Same multi-table shape as the intl twin (12 DataTables on the
# page); we assert Table 0 (by-wicket grid) + Table 1 (top-20 list).
#
#   Table 0 — "By wicket — averages"
#     Row 0 (wkt 1)  — 143 partnerships, avg 37.0, best 171
#                       (Travis Head & Abhishek Sharma SRH v PBKS
#                        2025-04-12 — the famous SRH 286/6 in 16
#                        overs flexer of an opening stand).
#     Row 9 (wkt 10) — 16 partnerships, avg 6.5, best 26.
#
#   Table 1 — "Top partnerships" (top 20)
#     Row 0 — 205 (wkt "-") B Sai Sudharsan & Shubman Gill,
#              GT v DC 2025-05-18 — an unbroken opening stand
#              (GT chased without losing a wicket, so wicket_number
#              is null and the col shows "-"). The /partnerships/top
#              endpoint does NOT filter wicket_number IS NULL — that
#              filter is only on /partnerships/by-wicket.
#
# Numbers verified by independent SQL — see audit/series_partnerships_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_partnerships_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — IPL 2025 Partnerships ───────────────
navigate "$BASE/series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&gender=male&team_type=club&tab=Partnerships" \
  "Anchor — Series Partnerships IPL 2025 (12 tables)"
sleep 4   # +4s soak — 12 fan-out fetches

# Table 0 — By-wicket grid.
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,
    "row_assertions": [
        # Row 0 — 1st wicket. Best: 171 by Head/Sharma SRH v PBKS 2025-04-12.
        (0, [(0, "1"), (1, "143"), (2, "37"), (4, "171"),
             (5, "TM Head"), (5, "Abhishek Sharma"), (8, "2025-04-12")]),
        # Row 9 — 10th wicket. Best: 26.
        (9, [(0, "10"), (1, "16"), (2, "6.5"), (4, "26")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "IPL 2025 Partnerships T0" "$JSON_T0" "$EXPECTED_T0"; record_result $?

# Table 1 — Top partnerships.
JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # Row 0 — best stand of the season: 205 unbroken (wkt col "-")
        # by B Sai Sudharsan & Shubman Gill, GT v DC 2025-05-18.
        (0, [(0, "205"), (1, "-"),
             (2, "B Sai Sudharsan"), (2, "Shubman Gill"),
             (4, "2025"), (5, "2025-05-18")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "IPL 2025 Partnerships T1" "$JSON_T1" "$EXPECTED_T1"; record_result $?

print_summary
