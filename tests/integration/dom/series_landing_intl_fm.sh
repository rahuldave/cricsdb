#!/bin/bash
# /series landing — proves the FilterBar team_class=full_member
# narrows ICC-event tile counts AND collapses associate-only events.
#
# Closed window: men's T20Is, 2024-2025.
#
#   L1 (unbounded):
#     - T20 World Cup (Men)            44 matches
#     - ACC Men's Premier Cup          24 matches  (associate-only event)
#   L2 (FM-only via team_class=full_member):
#     - T20 World Cup (Men)            16 matches  (drops 28 vs-associate
#                                                   group-stage matches)
#     - ACC Men's Premier Cup          tile ABSENT (FM-only count = 0,
#                                                   so endpoint omits it)
#
# Numbers verified by independent SQL — see audit/series_landing_intl_fm.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_landing_intl_fm.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR L1 — UNBOUNDED ───────────────
navigate "$BASE/series?gender=male&team_type=international&season_from=2024&season_to=2025" \
  "Anchor L1 — /series unbounded male intl 2024-25"

JSON_L1=$(extract_landing_tiles 2>/dev/null)

EXPECTED_L1=$(cat <<'PYEXPECT'
{
    "tile_assertions": [
        ("T20 World Cup (Men)",     44),
        ("ACC Men's Premier Cup",   24),
    ],
}
PYEXPECT
)

run_landing_assertions "L1 unbounded" "$JSON_L1" "$EXPECTED_L1"; record_result $?

# ─────────────── ANCHOR L2 — FM-only ───────────────
navigate "$BASE/series?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member" \
  "Anchor L2 — /series FM-only male intl 2024-25"

JSON_L2=$(extract_landing_tiles 2>/dev/null)

EXPECTED_L2=$(cat <<'PYEXPECT'
{
    "tile_assertions": [
        ("T20 World Cup (Men)", 16),    # narrowed from 44 → 16
    ],
    "absent_tiles": [
        "ACC Men's Premier Cup",         # 0 FM-vs-FM matches; tile vanishes
    ],
}
PYEXPECT
)

run_landing_assertions "L2 FM-only" "$JSON_L2" "$EXPECTED_L2"; record_result $?

print_summary
