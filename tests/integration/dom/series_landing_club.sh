#!/bin/bash
# /series landing — male club, calendar 2025. The club twin of
# series_landing_intl_fm.sh. No team_class filter (clubs don't carry
# one). Single closed calendar season → single edition per
# tournament.
#
# Tile assertions (SQL-verified):
#   Franchise leagues
#     - Indian Premier League            74 matches
#     - Pakistan Super League            34 matches
#     - The Hundred Men's Competition    34 matches
#     - Major League Cricket             33 matches
#     - Caribbean Premier League         32 matches
#   Domestic leagues
#     - Vitality Blast                  132 matches
#
# Note: BBL 2024/25 lives under season "2024/25" (Australian cricket-
# summer spans two calendar years) so it does NOT appear in a single
# calendar=2025 anchor — that's the right behavior, just not what
# the original spec sketched.
#
# Numbers verified by independent SQL — see audit/series_landing_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_landing_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — male club 2025 landing ───────────────
navigate "$BASE/series?gender=male&team_type=club&season_from=2025&season_to=2025" \
  "Anchor — /series landing male club 2025"

JSON=$(extract_landing_tiles 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "tile_assertions": [
        ("Indian Premier League",            74),
        ("Pakistan Super League",            34),
        ("The Hundred Men's Competition",    34),
        ("Major League Cricket",             33),
        ("Caribbean Premier League",         32),
        ("Vitality Blast",                  132),
    ],
    "section_min_tiles": [
        ("Franchise leagues", 5),
        ("Domestic leagues",  1),
    ],
}
PYEXPECT
)

run_landing_assertions "Club 2025" "$JSON" "$EXPECTED"; record_result $?

print_summary
