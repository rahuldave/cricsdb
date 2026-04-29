#!/bin/bash
# Series > Partnerships (intl). Anchor: ICC Men's T20 World Cup 2024.
# The tab fans out into 12 DataTables; we assert the two canonical
# aggregations (Table 0 = by-wicket grid, Table 1 = top overall):
#
#   Table 0 — "By wicket — averages"  (10 rows, 1st…10th wicket)
#     Row 0  (wkt 1)  — 84 partnerships, avg 17.2, best 86
#                       (Hendricks/de Kock SA v Eng, 2024-06-21)
#     Row 9  (wkt 10) — 17 partnerships, avg 5.1,  best 19
#                       (Delany/White Ire v Ind, 2024-06-05)
#
#   Table 1 — "Top partnerships" (top 20 by runs)
#     Row 0  — 131 (3rd wkt) AGS Gous & Aaron Jones, USA v Canada
#              2024-06-01 (the tournament opener — the highest stand)
#
# Numbers verified by independent SQL (with the same retired-hurt
# exclusion the API applies — see audit/series_partnerships_intl.sql).
# Multi-table page — uses the new ordinal arg on extract_data_table.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_partnerships_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — T20 WC Men 2024 Partnerships ───────────────
navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&gender=male&team_type=international&tab=Partnerships" \
  "Anchor — Series Partnerships T20 WC Men 2024 (12 tables)"
sleep 4   # +4s soak — 12 fan-out fetches must resolve before extract

# Table 0 — By-wicket grid (10 rows).
JSON_T0=$(extract_data_table 0 2>/dev/null)
EXPECTED_T0=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,
    "row_assertions": [
        # Row 0 — 1st wicket. cols: Wkt | N | Average | Balls | Best | Best stand | Match | Season | Date
        (0, [(0, "1"), (1, "84"), (2, "17.2"), (4, "86"),
             (5, "Hendricks"), (5, "de Kock"), (8, "2024-06-21")]),
        # Row 9 — 10th wicket.
        (9, [(0, "10"), (1, "17"), (2, "5.1"), (4, "19"),
             (5, "Delany"), (5, "White"), (8, "2024-06-05")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Partnerships T0 by-wicket" "$JSON_T0" "$EXPECTED_T0"; record_result $?

# Table 1 — Top partnerships (top 20).
JSON_T1=$(extract_data_table 1 2>/dev/null)
EXPECTED_T1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 20,
    "row_assertions": [
        # Row 0 — best stand of the tournament: 131, 3rd wkt, AGS Gous
        # & Aaron Jones, opener 2024-06-01 USA beat Canada.
        (0, [(0, "131"), (1, "3"),
             (2, "AGS Gous"), (2, "Aaron Jones"),
             (4, "2024"), (5, "2024-06-01")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Partnerships T1 top" "$JSON_T1" "$EXPECTED_T1"; record_result $?

print_summary
