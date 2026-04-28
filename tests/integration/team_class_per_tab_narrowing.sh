#!/bin/bash
# v3 team_class FilterBar — per-tab narrowing matrix.
#
# For each surface in spec §8.3, hit the page TWICE (off + on) and
# assert the on-state shows narrowed counts that match the SQL
# anchors in internal_docs/team-class-anchor-numbers.md.
#
# Plus: club no-op assertions — for RCB IPL 2025, the on-state must
# equal the off-state byte-identically (defensive backend gate).
#
# Skeleton — anchor numbers stubbed. Fill via commit 5 once Phase B
# subagent has populated team-class-anchor-numbers.md.
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

settle() { sleep "${1:-1.5}"; }

read_match_count() {
  agent-browser eval 'document.body.innerText.match(/Matches\s*\n?\s*([0-9,]+)/)?.[1] || ""' 2>/dev/null \
    | tail -1 | tr -d '" \t\n,'
}

# Test pattern: each surface gets a "narrowing assertion" function.
# - Open URL with team_class OFF  → capture metric
# - Open URL with team_class ON   → capture metric
# - assert FM-on count matches SQL anchor (or "control == narrowed" for club)

# --------------------------------------------------------------------
echo "Surface 3 · /teams?team=Australia → tab=Match List"
# TODO(commit-5):
#   off → expected 22 (anchor A3)
#   on  → expected 16 (anchor A4)

echo "Surface 5 · /teams?team=Australia → tab=Bowling"
# TODO(commit-5):
#   on → wickets / economy shifted; assert specific cell text matches anchor

echo "Surface 8 · /teams?team=Australia&filter_opponent=Scotland (vs Opp)"
# TODO(commit-5):
#   off → some count (anchor A7-derived)
#   on  → 0 (anchor A8 — Scotland is associate, FM excludes)

echo "Surface 9 · /teams?team=Australia → tab=Compare (URL E1)"
# TODO(commit-5):
#   on → all three cols narrow; Aus 16, India 31, avg 140 (Mode E1)
#   Verify chip alignment is native (no chip_team_class hint sent)

echo "Surface 10 · /teams?team=RCB → tab=Compare (URL G — club no-op)"
# TODO(commit-5):
#   off vs on → byte-identical numbers in every cell
#   Verify FilterBar pill is HIDDEN

echo "Surface 11 · /series landing"
# TODO(commit-5):
#   off → ICC Men's T20 WC tile = anchor A13 count
#   on  → ICC tile = anchor A14 count (smaller)
#   on  → India-vs-Scotland rivalry tile shows 0 (or hidden)

echo "Surface 12 · /series?tournament=ICC Men's T20 World Cup"
# TODO(commit-5):
#   off → A13 count
#   on  → A14 count

echo "Surface 14 · /head-to-head?mode=team India vs Scotland"
# TODO(commit-5):
#   on → 0 matches (anchor A16 FM=0)

echo "Surface 16 · /batting leaders"
# TODO(commit-5):
#   off → top-N matches anchor A9 (associate batters present)
#   on  → top-N matches anchor A10 (associates dropped)

echo "Surface 22 · /matches/:id (scorecard)"
# TODO(commit-5):
#   off vs on → identical (match identity is fixed; team_class is no-op)

# ... ~24 surfaces total per spec §8.3 matrix. Each is one block above.

# --------------------------------------------------------------------
echo
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
exit $((FAIL > 0 ? 1 : 0))
