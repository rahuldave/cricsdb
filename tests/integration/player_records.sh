#!/bin/bash
# Per-player Records subtab — integration test (d2026e5 / 0efeb65 / 1a146e4).
#
# Three sections:
#   §A — Batting Records subtab on /batting?player=X
#   §B — Bowling Records subtab on /bowling?player=X
#   §C — Fielding Records subtab on /fielding?player=X
#
# Anchors against the API at the same scope (which has its SQL
# correctness locked by tests/regression/{batting,bowling,fielding}/
# urls.txt § *_records_*). DOM ↔ API plumbing only.
#
# Anchor scopes (closed-window — first-row entries shouldn't drift on
# DB rebuilds because they're set by pre-2026 matches):
#   - Kohli (ba607b88) batting, IPL men's club
#   - Bumrah (462411b3) bowling, IPL men's club
#   - Dhoni (4a8a2e3b) fielding, all-scope (most catches in match
#     across all formats — robust anchor)
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()      { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad()     { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq()     { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }
assert_contains() {
  local label="$1" needle="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not in '$au'"; fi
}
assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

get_first_row() {
  local idx=$1
  ab_eval "(() => {
    const tbls = document.querySelectorAll('table tbody');
    const r = tbls[$idx]?.querySelector('tr');
    return r ? r.textContent.replace(/\s+/g, ' ').trim() : null;
  })()"
}

# ── §A — Batting Records (Kohli, IPL men's club) ────────────────────
echo
echo "§A — Batting Records: Kohli, IPL men's club"
KOHLI=ba607b88
SCOPE="tournament=Indian+Premier+League&team_type=club&gender=male"
URL="$BASE/batting?player=$KOHLI&$SCOPE&tab=Records"

JSON=$(curl -s "$API/api/v1/batters/$KOHLI/records?tournament=Indian+Premier+League&team_type=club&gender=male&limit=10")
py() { echo "$JSON" | python3 -c "$1"; }
hs_figs=$(   py "import json,sys; print(json.load(sys.stdin)['highest_scores'][0]['figures'])")
hs_opp=$(    py "import json,sys; print(json.load(sys.stdin)['highest_scores'][0]['opponent'])")
f50_figs=$(  py "import json,sys; print(json.load(sys.stdin)['fastest_50s'][0]['figures'])")
f100_figs=$( py "import json,sys; print(json.load(sys.stdin)['fastest_100s'][0]['figures'])")
ms_sixes=$(  py "import json,sys; print(json.load(sys.stdin)['most_sixes_innings'][0]['sixes'])")
mf_fours=$(  py "import json,sys; print(json.load(sys.stdin)['most_fours_innings'][0]['fours'])")
sr_val=$(    py "import json,sys; print(json.load(sys.stdin)['best_strike_rates'][0]['strike_rate'])")

ab set viewport 1280 800
ab open "$URL"
ab wait --load networkidle
sleep 3

active=$(ab_eval "(() => document.querySelector('.wisden-tab.is-active')?.textContent)()")
assert_eq "§A active tab is Records" "Records" "$active"

all_text=$(ab_eval "(() => document.body.textContent)()")
for h in "Highest scores" "Fastest 50s" "Fastest 100s" "Most sixes" "Most fours" "Best strike rates"; do
  assert_contains "§A section: $h" "$h" "$all_text"
done

assert_contains "§A row 0 (highest) figures $hs_figs" "$hs_figs" "$(get_first_row 0)"
assert_contains "§A row 0 (highest) opponent $hs_opp" "$hs_opp" "$(get_first_row 0)"
assert_contains "§A row 1 (fastest 50) figures $f50_figs" "$f50_figs" "$(get_first_row 1)"
assert_contains "§A row 2 (fastest 100) figures $f100_figs" "$f100_figs" "$(get_first_row 2)"
assert_contains "§A row 3 (most sixes) sixes $ms_sixes" "$ms_sixes" "$(get_first_row 3)"
assert_contains "§A row 4 (most fours) fours $mf_fours" "$mf_fours" "$(get_first_row 4)"
assert_contains "§A row 5 (best SR) value $sr_val" "$sr_val" "$(get_first_row 5)"

# ── §B — Bowling Records (Bumrah, IPL men's club) ───────────────────
echo
echo "§B — Bowling Records: Bumrah, IPL men's club"
BUMRAH=462411b3
URL="$BASE/bowling?player=$BUMRAH&tournament=Indian+Premier+League&team_type=club&gender=male&tab=Records"

JSON=$(curl -s "$API/api/v1/bowlers/$BUMRAH/records?tournament=Indian+Premier+League&team_type=club&gender=male&limit=10")
bf_figs=$(   py "import json,sys; print(json.load(sys.stdin)['best_figures'][0]['figures'])")
bf_opp=$(    py "import json,sys; print(json.load(sys.stdin)['best_figures'][0]['opponent'])")
econ_econ=$( py "import json,sys; print(json.load(sys.stdin)['most_economical'][0]['economy'])")

ab open "$URL"
ab wait --load networkidle
sleep 3
active=$(ab_eval "(() => document.querySelector('.wisden-tab.is-active')?.textContent)()")
assert_eq "§B active tab is Records" "Records" "$active"

all_text=$(ab_eval "(() => document.body.textContent)()")
assert_contains "§B section: Best bowling figures" "Best bowling figures" "$all_text"
assert_contains "§B section: Most economical spells" "Most economical spells" "$all_text"

assert_contains "§B row 0 (best figs) $bf_figs" "$bf_figs" "$(get_first_row 0)"
assert_contains "§B row 0 (best figs) opp $bf_opp" "$bf_opp" "$(get_first_row 0)"
assert_contains "§B row 1 (most econ) econ $econ_econ" "$econ_econ" "$(get_first_row 1)"

# ── §C — Fielding Records (Dhoni, all-scope) ────────────────────────
echo
echo "§C — Fielding Records: Dhoni, all-scope"
DHONI=4a8a2e3b
URL="$BASE/fielding?player=$DHONI&tab=Records"

JSON=$(curl -s "$API/api/v1/fielders/$DHONI/records?limit=10")
mc_catches=$(py "import json,sys; print(json.load(sys.stdin)['most_catches_match'][0]['catches'])")
mc_opp=$(    py "import json,sys; print(json.load(sys.stdin)['most_catches_match'][0]['opponent'])")
mst_stumps=$(py "import json,sys; print(json.load(sys.stdin)['most_stumpings_match'][0]['stumpings'])")
md_dism=$(   py "import json,sys; print(json.load(sys.stdin)['most_dismissals_match'][0]['dismissals'])")

ab open "$URL"
ab wait --load networkidle
sleep 3
active=$(ab_eval "(() => document.querySelector('.wisden-tab.is-active')?.textContent)()")
assert_eq "§C active tab is Records" "Records" "$active"

all_text=$(ab_eval "(() => document.body.textContent)()")
assert_contains "§C section: Most catches in a match" "Most catches in a match" "$all_text"
assert_contains "§C section: Most stumpings in a match" "Most stumpings in a match" "$all_text"
assert_contains "§C section: Most dismissals in a match" "Most dismissals in a match" "$all_text"

assert_contains "§C row 0 (catches) c=$mc_catches" "$mc_catches" "$(get_first_row 0)"
assert_contains "§C row 0 (catches) opp $mc_opp" "$mc_opp" "$(get_first_row 0)"
assert_contains "§C row 1 (stumpings) st=$mst_stumps" "$mst_stumps" "$(get_first_row 1)"
assert_contains "§C row 2 (dismissals) total=$md_dism" "$md_dism" "$(get_first_row 2)"

# ── §D — Mobile viewport, no body overflow ──────────────────────────
echo
echo "§D — 390x844 mobile no overflow"
ab set viewport 390 844
for path in "batting?player=$KOHLI&$SCOPE&tab=Records" "bowling?player=$BUMRAH&tournament=Indian+Premier+League&team_type=club&gender=male&tab=Records" "fielding?player=$DHONI&tab=Records"; do
  ab open "$BASE/$path"
  ab wait --load networkidle
  sleep 2
  overflow=$(ab_eval '(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)()')
  overflow=$(unq "$overflow")
  if [ "$overflow" -le 2 ] 2>/dev/null; then
    ok "Mobile no overflow ($path, delta=${overflow}px)"
  else
    bad "Mobile overflow ${overflow}px ($path)"
  fi
done

echo
echo "== Summary =="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
