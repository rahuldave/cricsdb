#!/bin/bash
# Teams > Match List — proves the FilterBar team_class=full_member
# narrows match-list rows. Two anchors against the same Aus 2024-25
# scope:
#
#   M1 (unbounded): no team_class      → 22 rows, OLDEST row vs Oman
#                                        (associate — drops out under FM)
#   M2 (FM-only):   team_class=full_member → 16 rows, OLDEST row vs England
#
# Closed historical window so values stay stable across rebuilds.
# Numbers verified by independent SQL — see
# audit/teams_match_list_intl_fm.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/teams_match_list_intl_fm.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR M1 — UNBOUNDED (22 matches) ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&tab=Match+List" \
  "Anchor M1 — Aus 2024-25 unbounded match list (22)"

JSON_M1=$(extract_data_table 2>/dev/null)

EXPECTED_M1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 22,
    "total_label_contains": "of 22",
    "row_assertions": [
        # Row 0 — most recent (DESC sort)
        (0, [(0, "2025-08-16"), (1, "South Africa"), (3, "South Africa tour of Australia")]),
        # Row 21 — oldest in window. Oman is an ICC associate, NOT a
        # full member — this row's PRESENCE under unbounded is the
        # control that proves the narrowing in M2.
        (21, [(0, "2024-06-05"), (1, "Oman")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "M1 unbounded" "$JSON_M1" "$EXPECTED_M1"; record_result $?

# ─────────────── ANCHOR M2 — FM-only (16 matches) ───────────────
# Same scope + team_class=full_member on the FilterBar. The Aus-vs-
# associate matches (Oman, Scotland, Namibia, USA, Canada, Papua New
# Guinea) drop out, leaving 16. The most-recent row stays the same
# (Aus's most-recent FM opponent in window = same as overall most-
# recent: South Africa 2025-08-16). The oldest row changes from
# Oman 2024-06-05 to England 2024-06-08.
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member&tab=Match+List" \
  "Anchor M2 — Aus 2024-25 FM-only match list (16)"

JSON_M2=$(extract_data_table 2>/dev/null)

EXPECTED_M2=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 16,
    "total_label_contains": "of 16",
    "row_assertions": [
        # Row 0 — most recent (unchanged from unbounded — both teams FM)
        (0, [(0, "2025-08-16"), (1, "South Africa"), (3, "South Africa tour of Australia")]),
        # Row 15 — oldest in FM-only window. Was Oman in unbounded;
        # narrows to England under FM filter. THIS is the signal that
        # team_class is wired into the match-list endpoint.
        (15, [(0, "2024-06-08"), (1, "England"), (3, "ICC Men's T20 World Cup")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "M2 FM-only" "$JSON_M2" "$EXPECTED_M2"; record_result $?

print_summary
