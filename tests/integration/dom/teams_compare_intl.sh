#!/bin/bash
# Teams > Compare (INTL anchors) — DOM-grounded chip + value assertions.
#
# Three anchors against Men's T20I 2024-2025:
#   A.  Australia + India (avg unbounded, all team_types).
#   A'. Same scope, avg pinned to FM-only via per-slot compare1_team_class.
#   E1. Same scope, FilterBar team_class=full_member — all 3 cols inherit FM.
#
# Closed historical window so expected values stay stable across DB
# rebuilds. Numbers verified by an independent subagent that did NOT
# read api/ source — see audit/teams_compare_intl.sql for the SQL.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/teams_compare_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR A — INTL 2024-2025 (avg unbounded) ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&tab=Compare&compare1=__avg__&compare2=India&season_from=2024&season_to=2025" \
  "Anchor A — INTL 2024-2025, avg unbounded"

JSON_A=$(extract_grid 2>/dev/null)

EXPECTED_A=$(cat <<'PYEXPECT'
{
  "Australia": {
    "_match_header": "Australia",
    "matches_text": "22",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 22},
      ("BATTING", "Run rate"):    {"value": 9.91, "chip_value": 9.91, "chip_avg": 7.52, "chip_delta": 31.8},
      ("BATTING", "Boundary %"):  {"value": 23.1, "chip_value": 23.1, "chip_avg": 14.3},
      ("BOWLING", "Economy"):     {"value": 8.3, "chip_value": 8.34, "chip_avg": 7.52},
    },
  },
  "International average": {
    "_match_header": "International average",
    # 2026-04-28 per-team transform: avg col matches identity is now
    # the per-team rate, not absolute pool. 870 × 2 / 100 ≈ 17.4.
    "matches_text": "17.4 matches in scope",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 7.52},
      ("BATTING", "Boundary %"):  {"value": 14.3},
    },
  },
  "India": {
    "_match_header": "India",
    "matches_text": "34",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 34},
      ("BATTING", "Run rate"):    {"value": 9.39, "chip_value": 9.39, "chip_avg": 7.52, "chip_delta": 24.9},
      ("BATTING", "Boundary %"):  {"value": 21.0, "chip_value": 21.0, "chip_avg": 14.3},
      ("BOWLING", "Economy"):     {"value": 7.5, "chip_value": 7.51, "chip_avg": 7.52},
    },
  },
}
PYEXPECT
)

run_assertions "ANCHOR A unbounded" "$JSON_A" "$EXPECTED_A"; record_result $?

# ─────────────── ANCHOR A' — same scope, FM-only avg slot ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&tab=Compare&compare1=__avg__&compare1_team_class=full_member&compare2=India&season_from=2024&season_to=2025" \
  "Anchor A' — INTL 2024-2025, avg FM-only"

JSON_AP=$(extract_grid 2>/dev/null)

EXPECTED_AP=$(cat <<'PYEXPECT'
{
  "Australia": {
    "_match_header": "Australia",
    "matches_text": "22",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 9.91, "chip_value": 9.91, "chip_avg": 8.50, "chip_delta": 16.6},
      ("BATTING", "Boundary %"):  {"chip_value": 23.1, "chip_avg": 17.6},
      ("BOWLING", "Economy"):     {"chip_value": 8.34, "chip_avg": 8.50},
    },
  },
  "Full-member average": {
    "_match_header": "Full-member average",
    # 2026-04-28 per-team transform: avg col matches identity is now
    # the per-team rate, not absolute pool. 140 × 2 / 11 = 25.45.
    "matches_text": "25.45 matches in scope",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 8.50},
    },
  },
  "India": {
    "_match_header": "India",
    "matches_text": "34",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 9.39, "chip_value": 9.39, "chip_avg": 8.50, "chip_delta": 10.5},
      ("BATTING", "Boundary %"):  {"chip_value": 21.0, "chip_avg": 17.6},
    },
  },
}
PYEXPECT
)

run_assertions "ANCHOR A' FM-only avg slot" "$JSON_AP" "$EXPECTED_AP"; record_result $?

# ─────────────── ANCHOR E1 — FilterBar fm narrows everything ───────────────
# v3 — same scope as A' but team_class is on the FILTERBAR rather
# than the avg slot. Expectation: all three columns inherit fm:
#   - Australia col narrows to its 16 FM matches (vs 22 unbounded)
#   - India col narrows to 31 FM matches (vs 34 unbounded)
#   - Avg col stays at the 140 FM pool
# Chip ↔ avg agreement is native — both sides compute against
# filters.team_class=fm (no chip alignment hint needed).
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&tab=Compare&compare1=__avg__&compare2=India&season_from=2024&season_to=2025&team_class=full_member" \
  "Anchor E1 — INTL 2024-2025, FilterBar fm (3 cols inherit)"

JSON_E1=$(extract_grid 2>/dev/null)

EXPECTED_E1=$(cat <<'PYEXPECT'
{
  "Australia": {
    "_match_header": "Australia",
    "matches_text": "16",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 16},
      ("BATTING", "Run rate"):    {"value": 9.82, "chip_avg": 8.50},
    },
  },
  "Full-member average": {
    "_match_header": "Full-member average",
    # 2026-04-28 per-team transform: avg col matches identity is now
    # the per-team rate, not absolute pool. 140 × 2 / 11 = 25.45.
    "matches_text": "25.45 matches in scope",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 8.50},
    },
  },
  "India": {
    "_match_header": "India",
    "matches_text": "31",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 31},
      ("BATTING", "Run rate"):    {"value": 9.47, "chip_avg": 8.50},
    },
  },
}
PYEXPECT
)

run_assertions "ANCHOR E1 FilterBar fm inheritance" "$JSON_E1" "$EXPECTED_E1"; record_result $?

print_summary
