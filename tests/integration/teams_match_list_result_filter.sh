#!/bin/bash
# ResultFilter — Teams Match List subtab integration test.
#
# Locks the standalone Won/Lost/Tied pill row added in e880abd:
#   - 4 pills (All / Won / Lost / Tied) render with counts that
#     match /summary's matches/wins/losses values at scope.
#   - Tied pill collapses ties + no_results — mirrors the Mosaic
#     and the API's `?result=tied` predicate (outcome_winner IS NULL).
#   - Click → URL roundtrip on every pill, including All resets.
#   - Counts stay STABLE when the active filter is applied (unaux-
#     stripped summary contract — the affordance reads as a stat
#     card not a moving target).
#   - No mobile body overflow at 390w.
#
# Anchor: Mumbai Indians IPL men's. /summary is the source of truth
# (its SQL correctness is locked by tests/sanity/); this script
# validates DOM ↔ API plumbing only. Pattern matches CLAUDE.md
# "Integration tests anchor against /summary's scope_avg, not
# re-derived SQL".
#
# Spec: internal_docs/inning-controls-mount-sites.md §4 (test bed
# rationale for this mount site).
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
# Path segment needs %20 (literal '+' in path is the plus character);
# query value can use '+' or %20 interchangeably.
TEAM_PATH="Mumbai%20Indians"
TEAM_QUERY="Mumbai+Indians"
SCOPE="team_type=club&gender=male&tournament=Indian+Premier+League"
URL="$BASE/teams?team=$TEAM_QUERY&$SCOPE&tab=Match+List"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()      { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad()     { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq()     { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }
assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

# --- Expected counts from /summary -----------------------------------
SUMMARY_JSON=$(curl -s "$API/api/v1/teams/$TEAM_PATH/summary?$SCOPE")
matches=$(echo "$SUMMARY_JSON"  | python3 -c "import json,sys; print(json.load(sys.stdin)['matches']['value'])")
wins=$(echo "$SUMMARY_JSON"     | python3 -c "import json,sys; print(json.load(sys.stdin)['wins']['value'])")
losses=$(echo "$SUMMARY_JSON"   | python3 -c "import json,sys; print(json.load(sys.stdin)['losses']['value'])")
ties=$(echo "$SUMMARY_JSON"     | python3 -c "import json,sys; print(json.load(sys.stdin)['ties']['value'])")
no_results=$(echo "$SUMMARY_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['no_results']['value'])")
tied_total=$((ties + no_results))

echo "/summary @ Mumbai Indians IPL men's club: matches=$matches wins=$wins losses=$losses ties=$ties no_results=$no_results → Tied pill=$tied_total"

# DOM probes — pluck the Result wisden-filter-group regardless of the
# other filter-groups (Gender, Team Type, etc.) on the page. Each
# probe returns a single value so assert_eq compares cleanly.
PROBE_BTN_TEXT='
(() => {
  const groups = document.querySelectorAll(".wisden-filter-group");
  for (const g of groups) {
    if (g.querySelector(".wisden-filter-label")?.textContent === "Result") {
      const btns = g.querySelectorAll("button");
      return btns[IDX].textContent.trim().replace(/\s+/g, " ");
    }
  }
  return null;
})()'
PROBE_ACTIVE='
(() => {
  const groups = document.querySelectorAll(".wisden-filter-group");
  for (const g of groups) {
    if (g.querySelector(".wisden-filter-label")?.textContent === "Result") {
      for (const b of g.querySelectorAll("button")) {
        if (b.className.includes("is-active")) {
          return b.textContent.trim().split(/[0-9]/)[0].trim();
        }
      }
    }
  }
  return null;
})()'
PROBE_RESULT_URL='(() => new URL(location.href).searchParams.get("result") || "")()'
click_pill() {
  agent-browser eval "
    (() => {
      const groups = document.querySelectorAll('.wisden-filter-group');
      for (const g of groups) {
        if (g.querySelector('.wisden-filter-label')?.textContent === 'Result') {
          g.querySelectorAll('button')[$1].click();
          return true;
        }
      }
    })()
  " >/dev/null 2>&1
  sleep 0.5
}
btn_text() {
  local idx=$1
  ab_eval "${PROBE_BTN_TEXT//IDX/$idx}"
}

# --- Test 1: mount + counts at 1280 ----------------------------------
echo
echo "Test 1 — mount counts (1280x800)"
ab set viewport 1280 800
ab open "$URL"
ab wait --load networkidle
sleep 2

assert_eq "Pill 0 (All matches) shows scope matches"        "All matches$matches" "$(btn_text 0)"
assert_eq "Pill 1 (Won) shows scope wins"                   "Won$wins"            "$(btn_text 1)"
assert_eq "Pill 2 (Lost) shows scope losses"                "Lost$losses"         "$(btn_text 2)"
assert_eq "Pill 3 (Tied) shows ties+no_results collapsed"   "Tied$tied_total"     "$(btn_text 3)"
assert_eq "Initial active is All"                           "All matches"         "$(ab_eval "$PROBE_ACTIVE")"
assert_eq "Initial URL has no result= param"                ""                    "$(ab_eval "$PROBE_RESULT_URL")"

# --- Test 2: click Won — URL roundtrip + counts stable ---------------
echo
echo "Test 2 — click Won → ?result=won + counts unchanged (unaux contract)"
click_pill 1
assert_eq "After click Won — URL result=won"                "won"                 "$(ab_eval "$PROBE_RESULT_URL")"
assert_eq "After click Won — Won pill is-active"            "Won"                 "$(ab_eval "$PROBE_ACTIVE")"
assert_eq "After click Won — All count unchanged"           "All matches$matches" "$(btn_text 0)"
assert_eq "After click Won — Won count unchanged"           "Won$wins"            "$(btn_text 1)"
assert_eq "After click Won — Lost count unchanged"          "Lost$losses"         "$(btn_text 2)"
assert_eq "After click Won — Tied count unchanged"          "Tied$tied_total"     "$(btn_text 3)"

# --- Test 3: click Lost — URL switches -------------------------------
echo
echo "Test 3 — click Lost → ?result=lost"
click_pill 2
assert_eq "After click Lost — URL result=lost"              "lost"                "$(ab_eval "$PROBE_RESULT_URL")"
assert_eq "After click Lost — Lost pill is-active"          "Lost"                "$(ab_eval "$PROBE_ACTIVE")"

# --- Test 4: click Tied — URL switches -------------------------------
echo
echo "Test 4 — click Tied → ?result=tied"
click_pill 3
assert_eq "After click Tied — URL result=tied"              "tied"                "$(ab_eval "$PROBE_RESULT_URL")"
assert_eq "After click Tied — Tied pill is-active"          "Tied"                "$(ab_eval "$PROBE_ACTIVE")"

# --- Test 5: click All — reset --------------------------------------
echo
echo "Test 5 — click All → ?result= dropped"
click_pill 0
assert_eq "After click All — URL has no result= param"      ""                    "$(ab_eval "$PROBE_RESULT_URL")"
assert_eq "After click All — All pill is-active"            "All matches"         "$(ab_eval "$PROBE_ACTIVE")"

# --- Test 6: deep-link ?result=won — mount-state contract ------------
echo
echo "Test 6 — deep-link ?result=won → Won pill mounts is-active"
ab open "$URL&result=won"
ab wait --load networkidle
sleep 2
assert_eq "Deep-link — Won pill is-active at mount"         "Won"                 "$(ab_eval "$PROBE_ACTIVE")"
assert_eq "Deep-link — All count still scope total"         "All matches$matches" "$(btn_text 0)"

# --- Test 7: mobile viewport — no body overflow ----------------------
echo
echo "Test 7 — 390x844 mobile no overflow"
ab set viewport 390 844
ab open "$URL"
ab wait --load networkidle
sleep 2
overflow=$(ab_eval '(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)()')
overflow=$(unq "$overflow")
if [ "$overflow" -le 2 ] 2>/dev/null; then
  ok "Mobile body has no horizontal overflow (delta=${overflow}px)"
else
  bad "Mobile body overflows by ${overflow}px (limit: 2px)"
fi

# --- Summary --------------------------------------------------------
echo
echo "== Summary =="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
