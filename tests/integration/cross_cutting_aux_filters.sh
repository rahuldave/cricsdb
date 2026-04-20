#!/bin/bash
# Cross-cutting: AuxParams (series_type) propagation through useFilters.
#
# The bug this guards against: useFilters drops a URL param, so the
# frontend never includes it in API calls, the backend ignores it
# (defaults), and the page silently shows the wrong (broader) data.
# Backend regression can't catch this — backend works fine when given
# the param; it's the frontend that fails to send it. So we assert
# end-to-end: a page loaded with `?...&series_type=bilateral` must
# render a different (smaller) match count than the same page without
# series_type.
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

read_match_count() {
  # Reads the visible "Matches\n<N>" StatCard text. Returns the integer.
  agent-browser eval 'document.body.innerText.match(/Matches\s*\n?\s*([0-9,]+)/)?.[1] || ""' 2>/dev/null \
    | tail -1 | tr -d '" \t\n,'
}

settle() { sleep "${1:-1.5}"; }

# --------------------------------------------------------------------
echo "Test 1 · /teams Australia plain vs series_type=bilateral"
echo "  (regression coverage for useFilters dropping series_type)"

agent-browser open "$BASE/teams?team=Australia&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle
PLAIN=$(read_match_count)
echo "  plain Australia matches: $PLAIN"

agent-browser open "$BASE/teams?team=Australia&gender=male&team_type=international&series_type=bilateral" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle
BILAT=$(read_match_count)
echo "  series_type=bilateral matches: $BILAT"

agent-browser open "$BASE/teams?team=Australia&gender=male&team_type=international&series_type=icc" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle
ICC=$(read_match_count)
echo "  series_type=icc matches: $ICC"

if [[ -n "$PLAIN" && -n "$BILAT" && -n "$ICC" ]]; then
  if [[ "$PLAIN" -gt "$BILAT" && "$PLAIN" -gt "$ICC" && "$BILAT" -ne "$ICC" ]]; then
    echo "  ✓ all three counts differ (plain > bilat, plain > icc, bilat ≠ icc)"
    PASS=$((PASS + 1))
  else
    echo "  ✗ counts not properly partitioned (plain=$PLAIN bilat=$BILAT icc=$ICC)"
    FAIL=$((FAIL + 1))
  fi
  # Also assert plain == bilat + icc (the partition is exhaustive for international)
  SUM=$((BILAT + ICC))
  if [[ "$PLAIN" -eq "$SUM" ]]; then
    echo "  ✓ plain = bilat + icc ($PLAIN = $BILAT + $ICC)"
    PASS=$((PASS + 1))
  else
    echo "  ✗ partition not exhaustive: plain=$PLAIN, bilat+icc=$SUM (off by $((PLAIN - SUM)))"
    FAIL=$((FAIL + 1))
  fi
else
  echo "  ✗ failed to read match counts (plain='$PLAIN' bilat='$BILAT' icc='$ICC')"
  FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 2 · status strip surfaces series_type"
agent-browser open "$BASE/teams?team=Australia&gender=male&team_type=international&series_type=bilateral" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.0
STRIP=$(agent-browser eval 'document.querySelector(".wisden-scope-strip")?.innerText || ""' 2>/dev/null | tail -1 | tr -d '"')
if [[ "$STRIP" == *"bilateral"* ]]; then
  echo "  ✓ scope strip mentions bilateral"; PASS=$((PASS + 1))
else
  echo "  ✗ scope strip missing series_type label (got: $STRIP)"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
