#!/bin/bash
# Series > Editions (club). Anchor: Indian Premier League, all
# editions in the DB. 19 rows DESC by season:
#
#   Row 0  — 2026     38 matches  (in progress; champion still null)
#   Row 1  — 2025     74 matches  Royal Challengers Bengaluru
#   Row 2  — 2024     71 matches  Kolkata Knight Riders
#   Row 4  — 2022     74 matches  Gujarat Titans
#   Row 18 — 2007/08  58 matches  Rajasthan Royals (the inaugural)
#
# Single DataTable on the page — bare extract_data_table works.
# DataTable's default page size is 10, so we need to tell the
# extractor to look at all 19 rows. The Editions page sets a high
# pageSize internally so all rows render — verify_anchor first.
#
# Backed by /api/v1/series/by-season.
#
# Numbers verified by independent SQL — see audit/series_editions_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_editions_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — IPL Editions ───────────────
navigate "$BASE/series?tournament=Indian+Premier+League&gender=male&team_type=club&tab=Editions" \
  "Anchor — Series Editions IPL (19 editions)"
sleep 4   # Editions table is large (19 rows) — extra soak for render

JSON=$(extract_data_table 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 19,
    "row_assertions": [
        # Row 0 — most recent, in-progress (no champion yet).
        (0, [(0, "2026"), (1, "38")]),
        # Row 1 — IPL 2025, the marquee window for our other anchors.
        (1, [(0, "2025"), (1, "74"), (2, "Royal Challengers Bengaluru")]),
        # Row 2 — 2024.
        (2, [(0, "2024"), (1, "71"), (2, "Kolkata Knight Riders")]),
        # Row 4 — 2022 GT win (different champion to break monotony).
        (4, [(0, "2022"), (1, "74"), (2, "Gujarat Titans")]),
        # Row 18 — IPL 2007/08, the inaugural edition.
        (18, [(0, "2007/08"), (1, "58"), (2, "Rajasthan Royals")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "IPL Editions" "$JSON" "$EXPECTED"; record_result $?

print_summary
