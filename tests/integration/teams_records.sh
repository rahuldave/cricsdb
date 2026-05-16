#!/bin/bash
# Teams Records subtab — integration test (c7afdf1 + 056a1c7).
#
# Anchors the 8 record-list tables against the team-records API. The
# API's SQL correctness is locked by the regression harness
# (tests/regression/teams/urls.txt § team_records_*) — this script
# tests DOM ↔ API plumbing only, per CLAUDE.md "Integration tests
# anchor against /summary's scope_avg, not re-derived SQL".
#
# Anchor scope: Mumbai Indians IPL men's club. Closed-window numbers
# (top entries) shouldn't drift on DB rebuilds because they're set by
# pre-2026 matches.
#
# Asserts:
#   1. Records subtab is present in Teams' tab bar.
#   2. All 8 record-list section headers render.
#   3. Top entries on each list match the API's first row (subject-
#      team semantics — MI's totals/wins/partnerships/etc., never the
#      opposition's).
#   4. Mobile 390 viewport has no body overflow.
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
TEAM_PATH="Mumbai%20Indians"
TEAM_QUERY="Mumbai+Indians"
SCOPE="team_type=club&gender=male&tournament=Indian+Premier+League"
URL="$BASE/teams?team=$TEAM_QUERY&$SCOPE&tab=Records"
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
assert_contains() {
  local label="$1" needle="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not in '$au'"; fi
}

# --- Top entries from the API (the source of truth) ---
JSON=$(curl -s "$API/api/v1/teams/$TEAM_PATH/records?team_type=club&gender=male&tournament=Indian+Premier+League&limit=5")

py() { echo "$JSON" | python3 -c "$1"; }
htt_runs=$(py "import json,sys; d=json.load(sys.stdin); print(d['highest_team_totals'][0]['runs'])")
htt_opp=$( py "import json,sys; d=json.load(sys.stdin); print(d['highest_team_totals'][0]['opponent'])")
loat_runs=$(py "import json,sys; d=json.load(sys.stdin); print(d['lowest_all_out_totals'][0]['runs'])")
bwr_margin=$(py "import json,sys; d=json.load(sys.stdin); print(d['biggest_wins_by_runs'][0]['margin'])")
bww_margin=$(py "import json,sys; d=json.load(sys.stdin); print(d['biggest_wins_by_wickets'][0]['margin'])")
lp_runs=$(py "import json,sys; d=json.load(sys.stdin); print(d['largest_partnerships'][0]['runs'])")
bi_figs=$(py "import json,sys; d=json.load(sys.stdin); print(d['best_individual_batting'][0]['figures'])")
bi_name=$(py "import json,sys; d=json.load(sys.stdin); print(d['best_individual_batting'][0]['name'])")
bb_figs=$(py "import json,sys; d=json.load(sys.stdin); print(d['best_bowling_figures'][0]['figures'])")
bb_name=$(py "import json,sys; d=json.load(sys.stdin); print(d['best_bowling_figures'][0]['name'])")
ms_sixes=$(py "import json,sys; d=json.load(sys.stdin); print(d['most_sixes_in_a_match'][0]['sixes'])")

echo "API anchors @ MI/IPL men's club:"
echo "  highest=$htt_runs vs $htt_opp · lowest_ao=$loat_runs · win_runs=$bwr_margin · win_wkts=$bww_margin"
echo "  partnership=$lp_runs · batting=$bi_figs ($bi_name) · bowling=$bb_figs ($bb_name) · sixes=$ms_sixes"

# --- Test 1: Records subtab present + active when deep-linked ---
echo
echo "Test 1 — Records tab present + active"
ab set viewport 1280 800
ab open "$URL"
ab wait --load networkidle
sleep 3

tabs_active=$(ab_eval "(() => document.querySelector('.wisden-tab.is-active')?.textContent)()")
assert_eq "Active tab is Records" "Records" "$tabs_active"

tabs_inv=$(ab_eval "(() => Array.from(document.querySelectorAll('.wisden-tab')).map(t => t.textContent).join(','))()")
assert_contains "Records tab is in the tab inventory" "Records" "$tabs_inv"

# --- Test 2: All 8 section headers render ---
echo
echo "Test 2 — 8 record-list section headers"
all_text=$(ab_eval "(() => document.body.textContent)()")
for hdr in "Highest team totals" "Lowest all-out" "Biggest wins by runs" "Biggest wins by wickets" \
           "Largest partnerships" "Best individual batting" "Best bowling figures" "Most sixes in a match"; do
  assert_contains "Section: $hdr" "$hdr" "$all_text"
done

# --- Test 3: Top-row values match the API ---
# DataTable renders Runs/Margin in the first numeric column. The
# row text is the concatenation of cells; assert_contains tolerates
# the surrounding cell labels.
echo
echo "Test 3 — Top entries match API"

# Pull first row text from each of the 8 tables. DataTable renders
# tables in DOM order matching the JSX order in RecordsTab (the same
# 2-col grid we saw at 1280): row0..row7 → records lists in this
# order: highest, lowest, win_runs, win_wkts, partnership, batting,
# bowling, sixes.
get_first_row() {
  local idx=$1
  ab_eval "(() => {
    const tbls = document.querySelectorAll('table tbody');
    const r = tbls[$idx]?.querySelector('tr');
    return r ? r.textContent.replace(/\s+/g, ' ').trim() : null;
  })()"
}

assert_contains "Row 0 (highest) contains $htt_runs"        "$htt_runs"   "$(get_first_row 0)"
assert_contains "Row 0 (highest) contains opponent"          "$htt_opp"    "$(get_first_row 0)"
assert_contains "Row 1 (lowest all-out) contains $loat_runs" "$loat_runs"  "$(get_first_row 1)"
assert_contains "Row 2 (win by runs) contains $bwr_margin"   "$bwr_margin" "$(get_first_row 2)"
assert_contains "Row 3 (win by wickets) contains $bww_margin" "$bww_margin" "$(get_first_row 3)"
assert_contains "Row 4 (partnership) contains $lp_runs"       "$lp_runs"   "$(get_first_row 4)"
assert_contains "Row 5 (best batting) figures $bi_figs"       "$bi_figs"   "$(get_first_row 5)"
assert_contains "Row 5 (best batting) name $bi_name"          "$bi_name"   "$(get_first_row 5)"
assert_contains "Row 6 (best bowling) figures $bb_figs"       "$bb_figs"   "$(get_first_row 6)"
assert_contains "Row 6 (best bowling) name $bb_name"          "$bb_name"   "$(get_first_row 6)"
assert_contains "Row 7 (most sixes) sixes=$ms_sixes"          "$ms_sixes"  "$(get_first_row 7)"

# --- Test 4: Mobile no overflow ---
echo
echo "Test 4 — 390x844 mobile no overflow"
ab set viewport 390 844
ab open "$URL"
ab wait --load networkidle
sleep 3
overflow=$(ab_eval '(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)()')
overflow=$(unq "$overflow")
if [ "$overflow" -le 2 ] 2>/dev/null; then
  ok "Mobile body has no horizontal overflow (delta=${overflow}px)"
else
  bad "Mobile body overflows by ${overflow}px"
fi

echo
echo "== Summary =="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
