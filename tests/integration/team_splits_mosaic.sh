#!/bin/bash
# Splits Mosaic — DOM integration test on /teams.
#
# Spec: internal_docs/spec-splits-mosaic.md §6.2.
#
# Covers all four dimensionality cases (0/1/2/3 aux filters set),
# the three click surfaces (marginal / outer cell / outcome sub-rect)
# and their URL writes, the Wilson-CI tooltip presence, and mobile
# rendering at 390x844.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL" —
# every numeric expected value derives from cricket.db at runtime.
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-3}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected' (from SQL), got '$au'"; fi
}

assert_contains() {
  local label="$1" needle="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not found in: $au"; fi
}

sql()  { sqlite3 "$DB" "$1" 2>&1; }

MOSAIC_SEL='.wisden-splits-mosaic'

# Fixture — RCB IPL 2024. Closed window, won't drift.
TEAM="Royal Challengers Bengaluru"
TEAM_URL="Royal%20Challengers%20Bengaluru"
SCOPE_URL='gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024'

# Match-level scope clause for RCB in IPL 2024 (mirrors _team_filter_clause).
RCB_WHERE="
(m.team1 = '$TEAM' OR m.team2 = '$TEAM')
AND m.toss_winner IS NOT NULL
AND m.gender = 'male'
AND m.team_type = 'club'
AND m.event_name = 'Indian Premier League'
AND m.season >= '2024'
AND m.season <= '2024'
"

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1
agent-browser set viewport 1280 720 >/dev/null 2>&1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Landing mode mounts (no ?team=)"

ab open "$BASE/teams?$SCOPE_URL"
settle 4

mosaic_present=$(ab_eval "!!document.querySelector('$MOSAIC_SEL')")
assert_eq "mosaic mounted on landing" "true" "$mosaic_present"

# Strip says "All <N> matches" — landing N = 2 × all-IPL-2024 matches with toss
sql_landing_n=$(sql "
SELECT COUNT(*) * 2 FROM match m
WHERE m.toss_winner IS NOT NULL
  AND m.gender = 'male'
  AND m.team_type = 'club'
  AND m.event_name = 'Indian Premier League'
  AND m.season >= '2024'
  AND m.season <= '2024'
")
landing_strip=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "landing strip says 'All <N> matches'" "All $sql_landing_n matches" "$landing_strip"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Team-detail mounts; cell counts match SQL"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL"
settle 4

mosaic_present=$(ab_eval "!!document.querySelector('$MOSAIC_SEL')")
assert_eq "mosaic mounted on team-detail" "true" "$mosaic_present"

# Total RCB matches in scope (with toss_winner IS NOT NULL — per endpoint)
sql_total=$(sql "SELECT COUNT(*) FROM match m WHERE $RCB_WHERE")
dom_strip=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "team strip says 'All <N> matches'" "All $sql_total matches" "$dom_strip"

# Won-toss + batted-first + won-game cell count
# Bat first when: (toss=bat AND toss_winner=team) OR (toss=field AND toss_winner != team)
sql_won_bf_won=$(sql "
SELECT COUNT(*) FROM match m
WHERE $RCB_WHERE
  AND m.toss_winner = '$TEAM'
  AND ((m.toss_decision = 'bat' AND m.toss_winner = '$TEAM')
       OR (m.toss_decision = 'field' AND m.toss_winner != '$TEAM'))
  AND m.outcome_winner = '$TEAM'
")
# Read the cell text — the first cell in the first row should be Won toss × Batted first
# Use the API directly for a clean assertion
api_cells=$(curl -s "http://localhost:8000/api/v1/teams/splits?team=$TEAM_URL&$SCOPE_URL")
api_won_bf_won=$(echo "$api_cells" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for c in d['cells']:
    if c['toss_outcome']=='won' and c['inning']==0 and c['result']=='won':
        print(c['n']); break
" 2>/dev/null)
assert_eq "API cell (won-toss, bat-first, won) matches SQL" "$sql_won_bf_won" "$api_won_bf_won"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Marginal click writes one URL param"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL"
settle 4

# Click "Won toss" column header — should set ?toss_outcome=won
ab_eval "[...document.querySelectorAll('$MOSAIC_SEL .wisden-splits-marginal')].find(el => el.innerText.startsWith('Won toss'))?.click()"
settle 2
url_after=$(agent-browser get url 2>/dev/null)
assert_contains "URL gains toss_outcome=won" "toss_outcome=won" "$url_after"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Outer-cell click writes toss + inning"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL"
settle 4

# Click the cell-fills container of the first cell (toss=won, inning=0)
ab_eval "document.querySelectorAll('$MOSAIC_SEL .wisden-splits-cell-fills')[0]?.click()"
settle 2
url_after=$(agent-browser get url 2>/dev/null)
assert_contains "URL gains toss_outcome= after outer-cell click" "toss_outcome=" "$url_after"
assert_contains "URL gains inning= after outer-cell click" "inning=" "$url_after"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Sub-rect click writes all THREE filters"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL"
settle 4

# Click the first sub-rect inside the first cell (green = won outcome)
ab_eval "document.querySelectorAll('$MOSAIC_SEL .wisden-splits-subrect')[0]?.click()"
settle 2
url_after=$(agent-browser get url 2>/dev/null)
assert_contains "URL gains result= after sub-rect click" "result=" "$url_after"
assert_contains "URL gains toss_outcome= after sub-rect click" "toss_outcome=" "$url_after"
assert_contains "URL gains inning= after sub-rect click" "inning=" "$url_after"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 · Wilson CI tooltip is in DOM (title attr)"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL"
settle 4

has_wilson=$(ab_eval "[...document.querySelectorAll('$MOSAIC_SEL .wisden-splits-subrect')].some(el => (el.title || '').includes('Wilson 95% CI'))")
assert_eq "sub-rects carry Wilson CI tooltip" "true" "$has_wilson"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 7 · 2-free case (one aux set) shows correct denominator"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&toss_outcome=won"
settle 4

# RCB won toss N times in IPL 2024
sql_won_toss=$(sql "
SELECT COUNT(*) FROM match m
WHERE $RCB_WHERE AND m.toss_winner = '$TEAM'
")
strip_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "strip says 'Of <N> toss wins'" "Of $sql_won_toss toss wins" "$strip_text"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 8 · 1-free case (two aux set) shows 1D bar"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&result=won&inning=0"
settle 4

has_1d=$(ab_eval "!!document.querySelector('$MOSAIC_SEL .wisden-splits-1d')")
assert_eq "1D stacked bar rendered" "true" "$has_1d"

bar_segments=$(ab_eval "document.querySelectorAll('$MOSAIC_SEL .wisden-splits-1d-segment').length")
assert_eq "1D bar has 2 toss segments" "2" "$bar_segments"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 9 · 0-free case (all aux set) collapses to status strip"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&toss_outcome=lost&inning=0&result=won"
settle 4

# Status strip is verbose colloquial form
strip_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "0-free strip contains 'Lost toss'" "Lost toss" "$strip_text"
assert_contains "0-free strip contains 'Batted first'" "Batted first" "$strip_text"
assert_contains "0-free strip contains 'Won the game'" "Won the game" "$strip_text"

# No mosaic chart — only the strip should be present.
has_grid=$(ab_eval "!!document.querySelector('$MOSAIC_SEL .wisden-splits-grid')")
assert_eq "0-free has no mosaic grid" "false" "$has_grid"
has_1d=$(ab_eval "!!document.querySelector('$MOSAIC_SEL .wisden-splits-1d')")
assert_eq "0-free has no 1D bar" "false" "$has_1d"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 10 · Reset button clears all aux filters"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&toss_outcome=won&inning=0"
settle 4

ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-reset')?.click()"
settle 2
url_after=$(agent-browser get url 2>/dev/null)
url_clean=$(echo "$url_after" | grep -cE "toss_outcome=|inning=|result=" || true)
assert_eq "URL has no aux params after reset" "0" "$url_clean"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 11b · Bowling tab inning=0 flips to 'bowled first' POV"

# On Bowling tab with ?inning=0, the URL means "team bowled in match
# innings 0 = bowled first" — opposite of Batting tab's interpretation.
# Mosaic must flip its label AND its data to match.
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&tab=Bowling&inning=0"
settle 4

# Row label says "Bowled first" (not "Batted first")
row_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-row-primary')?.innerText || ''")
assert_contains "Bowling tab row label shows 'Bowled first'" "Bowled first" "$row_text"

# Secondary label shows the batting-POV equivalent
secondary_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-row-secondary')?.innerText || ''")
assert_contains "secondary shows '(Batted second)'" "Batted second" "$secondary_text"

# Strip says "bowling first" — the data reflects team-bowled-first matches.
# RCB bowled first in IPL 2024 = RCB batted second in IPL 2024 = 8 matches.
sql_bowl_first=$(sql "
SELECT COUNT(*) FROM match m
WHERE $RCB_WHERE
  AND NOT ((m.toss_decision = 'bat' AND m.toss_winner = '$TEAM')
        OR (m.toss_decision = 'field' AND m.toss_winner != '$TEAM'))
")
strip_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "Bowling-tab strip shows 'Of <N> matches bowling first'" "Of $sql_bowl_first matches bowling first" "$strip_text"

# Compare to Batting tab where same URL inning=0 means batted first
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&tab=Batting&inning=0"
settle 4
sql_bat_first=$(sql "
SELECT COUNT(*) FROM match m
WHERE $RCB_WHERE
  AND ((m.toss_decision = 'bat' AND m.toss_winner = '$TEAM')
       OR (m.toss_decision = 'field' AND m.toss_winner != '$TEAM'))
")
strip_text_bat=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "Batting-tab strip shows 'Of <N> matches batting first'" "Of $sql_bat_first matches batting first" "$strip_text_bat"

# Fielding tab acts like Bowling
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&tab=Fielding&inning=0"
settle 4
row_text_field=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-row-primary')?.innerText || ''")
assert_contains "Fielding tab also flips to 'Bowled first'" "Bowled first" "$row_text_field"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 11 · Mobile viewport (390x844) renders without overflow"

agent-browser set viewport 390 844 >/dev/null 2>&1
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL"
settle 4

mobile_visible=$(ab_eval "
  (() => {
    const el = document.querySelector('$MOSAIC_SEL');
    if (!el) return 'no-mosaic';
    const rect = el.getBoundingClientRect();
    return rect.width <= 390 && rect.width > 200 ? 'fits' : 'overflow:' + rect.width;
  })()
")
assert_eq "mobile mosaic fits viewport" "fits" "$mobile_visible"

# Reset viewport
agent-browser set viewport 1280 720 >/dev/null 2>&1

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─── Results ───"
echo "PASS: $PASS"
echo "FAIL: $FAIL"
[ $FAIL -eq 0 ] && exit 0 || { echo -e "Failures:$FAILS"; exit 1; }
