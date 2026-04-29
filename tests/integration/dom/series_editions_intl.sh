#!/bin/bash
# Series > Editions (intl). Anchor: ICC Men's T20 World Cup, all
# editions in the DB. Cricsheet's coverage of pre-2021 T20 WCs is
# sparse — 5 rows in the table:
#
#   2025/26   49 matches   India (8/9)
#   2024      44 matches   India (7/7)
#   2022/23   39 matches   England (4/5)
#   2021/22   40 matches   Australia (6/7)
#   2013/14    1 match     —     (single early-era recorded match)
#
# Single DataTable on the page — bare extract_data_table works.
# Backed by /api/v1/series/by-season (NOT /series/editions — the
# endpoint name differs from the tab label).
#
# Numbers verified by independent SQL — see audit/series_editions_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_editions_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — T20 WC Men Editions ───────────────
navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&gender=male&team_type=international&tab=Editions" \
  "Anchor — Series Editions T20 WC Men (5 editions)"

JSON=$(extract_data_table 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 5,
    "row_assertions": [
        # Row 0 — most recent (DESC by season).
        (0, [(0, "2025/26"), (1, "49"), (2, "India"), (3, "New Zealand")]),
        # Row 1 — 2024 (the marquee window for our other anchors).
        (1, [(0, "2024"), (1, "44"), (2, "India"), (3, "South Africa")]),
        # Row 2 — 2022/23.
        (2, [(0, "2022/23"), (1, "39"), (2, "England"), (3, "Pakistan")]),
        # Row 3 — 2021/22.
        (3, [(0, "2021/22"), (1, "40"), (2, "Australia"), (3, "New Zealand")]),
        # Row 4 — sparse 2013/14 single-match outlier (no champion).
        (4, [(0, "2013/14"), (1, "1")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "T20 WC Men Editions" "$JSON" "$EXPECTED"; record_result $?

print_summary
