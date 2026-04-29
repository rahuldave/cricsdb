#!/bin/bash
# Series > Overview "Champions by season" table — intl-only anchor.
# (NOT a separate "Champions" tab — the section lives within the
# Overview tab, alongside "Knockouts" and "Best moments".)
#
# Anchor: ICC Men's T20 World Cup, ALL editions in DB (no season
# filter). Champions table = DataTable at index 1 on the page (idx
# 0 is the Knockouts table). 4 rows DESC by season:
#
#   2025/26   India v New Zealand    → India
#   2024      India v South Africa   → India
#   2022/23   Pakistan v England     → England
#   2021/22   New Zealand v Australia → Australia
#
# Numbers verified by independent SQL — see audit/series_champions_intl.sql.
#
# No club twin — IPL doesn't have a separate champions surface
# (its single-season champion is in the Editions tab + Match List
# Final row).
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_champions_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — All T20 WC Men editions ───────────────
navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&gender=male&team_type=international" \
  "Anchor — Series Overview Champions table (all editions)"
sleep 4

# Champions by season — table at idx 1 (idx 0 is Knockouts).
JSON=$(extract_data_table 1 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 4,
    "row_assertions": [
        # Row 0 — most recent, India.
        # cols: Season | Final | Champion | Date and Score
        (0, [(0, "2025/26"), (1, "India"), (1, "New Zealand"), (2, "India")]),
        # Row 1 — 2024, India.
        (1, [(0, "2024"), (1, "India"), (1, "South Africa"), (2, "India")]),
        # Row 2 — 2022/23, England (different champion to break monotony).
        (2, [(0, "2022/23"), (1, "Pakistan"), (1, "England"), (2, "England")]),
        # Row 3 — oldest, Australia.
        (3, [(0, "2021/22"), (1, "New Zealand"), (1, "Australia"), (2, "Australia")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "T20 WC Men Champions" "$JSON" "$EXPECTED"; record_result $?

print_summary
