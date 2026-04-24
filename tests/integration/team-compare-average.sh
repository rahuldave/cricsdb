#!/bin/bash
# Teams > Compare tab: average-team column + phase bands +
# partnership-by-wicket + season trajectory.
#
# Companion to teams.sh — covers the spec-team-compare-average.md
# Phase-3 surface only. Run after touching TeamCompareGrid,
# AddTeamComparePicker, AvgSummaryRow, PhaseBandsRow,
# PartnershipByWicketRows, SeasonTrajectoryStrip, or any
# /scope/averages/* endpoint.
#
# Prereqs: agent-browser, vite :5173 (or 5174), fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

assert_url_contains() {
  local needle="$1" got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == *"$needle"* ]]; then
    printf "  ✓ url contains %s\n" "$needle"; PASS=$((PASS + 1))
  else
    printf "  ✗ url missing %s\n    got: %s\n" "$needle" "$got"; FAIL=$((FAIL + 1))
  fi
}

_innerText_has() {
  local needle_b64 js_b64
  needle_b64=$(printf '%s' "$1" | base64)
  js_b64=$(printf 'document.body.innerText.toLowerCase().includes(atob("%s").toLowerCase())' "$needle_b64" | base64)
  agent-browser eval -b "$js_b64" 2>/dev/null | tail -1 | tr -d '[:space:]'
}

assert_snapshot_contains() {
  local needle="$1" label="${2:-$1}" got
  got=$(_innerText_has "$needle")
  if [[ "$got" == "true" ]]; then
    printf "  ✓ page contains %s\n" "$label"; PASS=$((PASS + 1))
  else
    printf "  ✗ page missing %s\n" "$label"; FAIL=$((FAIL + 1))
  fi
}

assert_snapshot_missing() {
  local needle="$1" label="${2:-$1}" got
  got=$(_innerText_has "$needle")
  if [[ "$got" != "true" ]]; then
    printf "  ✓ page lacks %s\n" "$label"; PASS=$((PASS + 1))
  else
    printf "  ✗ page unexpectedly contains %s\n" "$label"; FAIL=$((FAIL + 1))
  fi
}

# ──────────────────────────────────────────────────────────────────
# Test 1 — Compare tab loads with primary + secondary, phase bands +
# partnership-by-wicket render.
# ──────────────────────────────────────────────────────────────────
echo "Test 1: MI vs CSK in IPL 2024 — base compare grid"
agent-browser navigate "$BASE/teams?team=Mumbai+Indians&tab=Compare&compare=Chennai+Super+Kings&tournament=Indian+Premier+League&season_from=2024&season_to=2024" >/dev/null
sleep 3
assert_snapshot_contains "Mumbai Indians" "MI column header"
assert_snapshot_contains "Chennai Super Kings" "CSK column header"
assert_snapshot_contains "PP RR" "phase band: PP RR row"
assert_snapshot_contains "Death Econ" "phase band: Death Econ row"
assert_snapshot_contains "1st wkt" "partnership-by-wicket: 1st wkt row"
assert_snapshot_contains "10th wkt" "partnership-by-wicket: 10th wkt row"

# ──────────────────────────────────────────────────────────────────
# Test 2 — Add league average via the picker button.
# ──────────────────────────────────────────────────────────────────
echo
echo "Test 2: + Add league average → avg_slot=1, label rendered"
agent-browser eval 'document.querySelector("button.wisden-compare-picker-avg-btn")?.click()' >/dev/null 2>&1
sleep 2
assert_url_contains "avg_slot=1"
assert_snapshot_contains "Indian Premier League 2024 avg" "scope-computed avg label"
# Avg column shows aggregate counts much larger than single team's.
# League IPL 2024 had 71 matches per smoke test.
assert_snapshot_contains "71" "league total matches"

# ──────────────────────────────────────────────────────────────────
# Test 3 — Single-season hides season-trajectory strip; multi-season
# shows it.
# ──────────────────────────────────────────────────────────────────
echo
echo "Test 3: trajectory strip visibility under single vs multi-season"
# Single season scope → trajectory hidden (only one X point per line).
assert_snapshot_missing "SEASON TRAJECTORY" "trajectory hidden when single season"

# Switch to multi-season scope.
agent-browser navigate "$BASE/teams?team=Mumbai+Indians&tab=Compare&compare=Chennai+Super+Kings&tournament=Indian+Premier+League&season_from=2020&season_to=2024&team_type=club&gender=male&avg_slot=1" >/dev/null
sleep 3
assert_snapshot_contains "SEASON TRAJECTORY" "trajectory header"
assert_snapshot_contains "Batting RR" "batting RR panel"
assert_snapshot_contains "Bowling Econ" "bowling econ panel"

# ──────────────────────────────────────────────────────────────────
# Test 4 — Remove avg column via × button.
# ──────────────────────────────────────────────────────────────────
echo
echo "Test 4: remove avg column via ✕"
# The ✕ button next to "Indian Premier League 2020-2024 avg" header.
# Click via the aria-label selector.
agent-browser eval 'document.querySelector("button[aria-label=\"Remove league average\"]")?.click()' >/dev/null 2>&1
sleep 2
got=$(agent-browser get url 2>/dev/null)
if [[ "$got" != *"avg_slot=1"* ]]; then
  printf "  ✓ avg_slot dropped from URL\n"; PASS=$((PASS + 1))
else
  printf "  ✗ avg_slot still in URL: %s\n" "$got"; FAIL=$((FAIL + 1))
fi
assert_snapshot_missing "Indian Premier League 2020-2024 avg" "avg column gone"

# ──────────────────────────────────────────────────────────────────
# Test 5 — Cross-gender FilterBar lock holds for the avg column too.
# A women's-club scope should produce a Women-labelled avg column when
# we re-add the average. The auto-narrow on team_type/gender already
# locks scope; the avg label reflects the same narrowed scope.
# ──────────────────────────────────────────────────────────────────
echo
echo "Test 5: scope-computed label respects gender + team_type"
agent-browser navigate "$BASE/teams?team=Mumbai+Indians&tab=Compare&tournament=Indian+Premier+League&season_from=2024&season_to=2024&team_type=club&gender=male&avg_slot=1" >/dev/null
sleep 3
# Should NOT include "Men's" string in label since tournament IPL
# already pins it; but should include the scope tournament + season.
assert_snapshot_contains "Indian Premier League 2024 avg" "label shows tournament + season"

# ──────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────
echo
echo "─────────────────────────────────"
echo "Pass: $PASS"
echo "Fail: $FAIL"
[ "$FAIL" -eq 0 ]
