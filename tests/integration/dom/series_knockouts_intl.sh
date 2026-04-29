#!/bin/bash
# Series > Overview "Knockouts" table — intl-only anchor scoped to a
# single edition. (NOT a separate "Knockouts" tab — the section
# lives within the Overview tab.)
#
# Anchor: ICC Men's T20 World Cup 2024 — exactly two knockout
# matches:
#   Row 0 — Final:      India v South Africa  → India (7 runs)
#   Row 1 — Semi Final: India v England       → India (68 runs)
#
# Knockouts table = DataTable at index 0 on the page (idx 1 is the
# Champions by-season table). With single-season filter the
# Knockouts table shrinks to that season's SFs + Final and the
# Champions table to that season's single Final.
#
# Numbers verified by independent SQL — see audit/series_knockouts_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_knockouts_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — T20 WC Men 2024 Knockouts ───────────────
navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&gender=male&team_type=international" \
  "Anchor — Series Overview Knockouts (T20 WC Men 2024)"
sleep 4

# Knockouts — table at idx 0.
JSON=$(extract_data_table 0 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 2,
    "row_assertions": [
        # Row 0 — Final, India beat South Africa by 7 runs.
        # cols: Season | Stage | Match | Winner | Venue | Date and Score
        (0, [(0, "2024"), (1, "Final"),
             (2, "India"), (2, "South Africa"),
             (3, "India"), (3, "7 runs")]),
        # Row 1 — Semi Final, India beat England by 68 runs.
        (1, [(0, "2024"), (1, "Semi Final"),
             (2, "India"), (2, "England"),
             (3, "India"), (3, "68 runs")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "T20 WC Men 2024 Knockouts" "$JSON" "$EXPECTED"; record_result $?

print_summary
