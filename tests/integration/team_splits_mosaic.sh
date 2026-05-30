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
echo "Test 10 · 'All matches' entry clears all aux filters (replaces reset button)"

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&toss_outcome=won&inning=0"
settle 4

# The standalone [reset] button is gone — the full reset is now the
# reset-bar's "All matches · N" entry.
ab_eval "[...document.querySelectorAll('$MOSAIC_SEL .wisden-splits-reset-bar button')].find(b=>b.innerText.trim().startsWith('All matches'))?.click()"
settle 2
url_after=$(agent-browser get url 2>/dev/null)
url_clean=$(echo "$url_after" | grep -cE "toss_outcome=|inning=|result=" || true)
assert_eq "URL has no aux params after 'All matches'" "0" "$url_clean"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 11b · Bowling tab inning=0 — Option-B POV ('batted first → bowled second')"

# Per Option-B (CLAUDE.md / spec-inning-unify-option-b): ?inning=0 means
# THE TEAM BATTED FIRST on every page. On the Bowling tab that means
# the team BOWLED in the OTHER innings — i.e. bowled SECOND. So the
# Mosaic's row label is "Bowled second" (not "Bowled first"), and the
# strip narrows to the team's batted-first matches.
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&tab=Bowling&inning=0"
settle 4

# Row label says "Bowled second" (team batted first → bowled second)
row_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-row-primary')?.innerText || ''")
assert_contains "Bowling tab row label shows 'Bowled second' (Option-B: batted-first → bowled-second)" "Bowled second" "$row_text"

# Secondary label echoes the batting-POV: team Batted second is the
# OPPOSITE row — when inning=0 (batted first), the secondary row
# describes the other category.
secondary_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-row-secondary')?.innerText || ''")
assert_contains "secondary shows '(Batted second)'" "Batted second" "$secondary_text"

# Strip says "bowling second" — the data narrows to the team's
# batted-first (= bowled-second) matches. SQL: count matches where
# the team batted first.
sql_bat_first=$(sql "
SELECT COUNT(*) FROM match m
WHERE $RCB_WHERE
  AND ((m.toss_decision = 'bat' AND m.toss_winner = '$TEAM')
       OR (m.toss_decision = 'field' AND m.toss_winner != '$TEAM'))
")
strip_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "Bowling-tab strip shows 'Of <N> matches bowling second'" "Of $sql_bat_first matches bowling second" "$strip_text"

# Batting tab — same URL inning=0 = batted first; strip says "batting first"
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&tab=Batting&inning=0"
settle 4
strip_text_bat=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "Batting-tab strip shows 'Of <N> matches batting first'" "Of $sql_bat_first matches batting first" "$strip_text_bat"

# Fielding tab acts like Bowling (also POV-flips to "Bowled second")
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&tab=Fielding&inning=0"
settle 4
row_text_field=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-row-primary')?.innerText || ''")
assert_contains "Fielding tab also flips to 'Bowled second'" "Bowled second" "$row_text_field"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 11c · Landing + toss_outcome=won returns league-conditional data"

# Subject-POV gate was lifted 2026-05-11. Clicking "Won toss" at
# landing (no ?team=) now narrows the league mosaic to the toss-
# winners-only slice — exactly the league conditional baseline users
# read for "P(win | won toss)" at league level.
#
# Pre-lift the click triggered a 400 and the mosaic emptied; this
# test guards against the gate being re-introduced.

ab open "$BASE/teams?$SCOPE_URL"
settle 4

has_table_before=$(ab_eval "!!document.querySelector('.wisden-splits-table')")
assert_eq "Mosaic present on valid landing (pre-click)" "true" "$has_table_before"

# Click the "Won toss" column header.
ab_eval "Array.from(document.querySelectorAll('.wisden-splits-col-header')).find(el => el.innerText.startsWith('Won toss'))?.click()" >/dev/null
settle 3

url_after=$(agent-browser get url 2>/dev/null)
assert_contains "URL gained toss_outcome=won after click" "toss_outcome=won" "$url_after"

# Post-click the mosaic stays present (no 400, real data).
has_table_after=$(ab_eval "!!document.querySelector('.wisden-splits-table')")
assert_eq "Mosaic stays present after toss_outcome click (gate lifted)" "true" "$has_table_after"

# Strip reads the FILTERED total — count of team-views that won the
# toss in this scope (one per match in the unpivot).
sql_won_toss=$(sql "
SELECT COUNT(*) FROM match m
WHERE m.toss_winner IS NOT NULL
  AND m.gender = 'male'
  AND m.team_type = 'club'
  AND m.event_name = 'Indian Premier League'
  AND m.season >= '2024'
  AND m.season <= '2024'
")
strip_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-strip')?.innerText || ''")
assert_contains "Strip reads filtered won-toss total" "Of $sql_won_toss toss wins" "$strip_text"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 11d · useFetch contract: data cleared on error (not stale)"

# Regression guard for the useFetch primitive's contract: when a
# refetch errors, the previous successful response must NOT stay
# mounted (the bug that surfaced via the now-lifted /splits 400 gate).
# Triggered here via the /venues/{x}/summary 404 path — the one
# remaining backend 4xx still reachable from a URL (path param).
#
# Pattern:
#   1. Load /venues?venue=Eden Gardens → dossier loads (200, data).
#   2. Change URL to /venues?venue=NotARealVenue → 404.
#   3. Assert the dossier rendered in step 1 is NOT still on screen
#      (stale-data would have it sticking around).

ab open "$BASE/venues?venue=Eden+Gardens"
settle 5

# Sanity: dossier loaded with valid venue (some kind of header text
# anchored to "Eden Gardens" should be present).
dossier_loaded=$(ab_eval "document.body.innerText.includes('Eden Gardens')")
assert_eq "Eden Gardens dossier loaded (pre-error)" "true" "$dossier_loaded"

# Navigate to a bad venue → backend 404.
ab open "$BASE/venues?venue=NotARealVenue"
settle 5

# Stale-data check: the previous "Eden Gardens" content should NOT
# linger in the DOM. (The URL bar's venue= query param is allowed to
# contain "Eden", so check inside main page content only — exclude
# inputs and search placeholders.)
stale_eden=$(ab_eval "
  Array.from(document.querySelectorAll('main, [class*=\"dossier\"], h1, h2'))
    .some(el => el.innerText.includes('Eden Gardens'))
")
assert_eq "No stale Eden Gardens dossier after navigating to bad venue" "false" "$stale_eden"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 12 · Dual-use redesign — top reset bar full-scope, NW corner + marginals live"
#
# The Mosaic split its two jobs onto two surfaces:
#   • top reset/reference bar — FULL-SCOPE (aux-stripped) numbers that
#     stay PUT when you click into a filter.
#   • northwest corner Won/Tied/Lost + toss/inning marginals — LIVE,
#     re-split to the current filter.
#
# Anchors derive from the API at runtime (full-scope vs result=won).
# Against the pre-redesign code every assertion below is RED: there
# was no corner element, the toss header read the aux-stripped (frozen)
# value, and the reset-bar class didn't exist.

api_full=$(curl -s "http://localhost:8000/api/v1/teams/splits?team=$TEAM_URL&$SCOPE_URL")
api_won=$(curl -s "http://localhost:8000/api/v1/teams/splits?team=$TEAM_URL&$SCOPE_URL&result=won")

full_won_n=$(echo "$api_full"   | python3 -c "import sys,json;print(json.load(sys.stdin)['marginals']['result']['won']['n'])")
full_toss_won=$(echo "$api_full" | python3 -c "import sys,json;print(json.load(sys.stdin)['marginals']['toss_outcome']['won']['n'])")
won_scope_n=$(echo "$api_won"    | python3 -c "import sys,json;print(json.load(sys.stdin)['scope_total_n'])")
live_toss_won=$(echo "$api_won"  | python3 -c "import sys,json;print(json.load(sys.stdin)['marginals']['toss_outcome']['won']['n'])")

# 12a — reset bar holds FULL-SCOPE "All won · <N>" even under result=lost.
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&result=lost"
settle 4
reset_text=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-reset-bar')?.innerText.replace(/\\n/g,' ') || ''")
assert_contains "reset bar shows full-scope 'All won · $full_won_n' under result=lost" "All won · $full_won_n" "$reset_text"

# 12b — northwest corner is LIVE: under result=won it reads Won=<scope>, Tied 0, Lost 0.
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&result=won"
settle 4
corner_won=$(ab_eval "[...document.querySelectorAll('$MOSAIC_SEL .wisden-splits-corner-outcome')].find(b=>b.innerText.trim().startsWith('Won'))?.innerText.replace(/\\n/g,' ') || ''")
corner_tied=$(ab_eval "[...document.querySelectorAll('$MOSAIC_SEL .wisden-splits-corner-outcome')].find(b=>b.innerText.trim().startsWith('Tied'))?.innerText.replace(/\\n/g,' ') || ''")
corner_lost=$(ab_eval "[...document.querySelectorAll('$MOSAIC_SEL .wisden-splits-corner-outcome')].find(b=>b.innerText.trim().startsWith('Lost'))?.innerText.replace(/\\n/g,' ') || ''")
assert_contains "corner Won is live ($won_scope_n) under result=won" "Won $won_scope_n" "$corner_won"
assert_contains "corner Tied collapses to 0 under result=won" "Tied 0" "$corner_tied"
assert_contains "corner Lost collapses to 0 under result=won" "Lost 0" "$corner_lost"

# 12c — toss column-header is LIVE under result=won (re-splits within the
# wins → $live_toss_won, NOT the full-scope $full_toss_won).
won_toss_header=$(ab_eval "[...document.querySelectorAll('$MOSAIC_SEL .wisden-splits-col-header')].find(b=>b.innerText.trim().startsWith('Won toss'))?.innerText.replace(/\\n/g,' ') || ''")
assert_contains "Won-toss header shows LIVE count (· $live_toss_won) under result=won" "· $live_toss_won" "$won_toss_header"
if [ "$live_toss_won" != "$full_toss_won" ]; then
  if [[ "$(unq "$won_toss_header")" == *"· $full_toss_won"* ]]; then
    bad "Won-toss header still shows FROZEN full-scope count ($full_toss_won) — marginal not live"
  else
    ok "Won-toss header is not the frozen full-scope count ($full_toss_won)"
  fi
fi

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 13 · Reset-bar entries are CONDITIONAL + mounted in collapsed views"
#
# Each 'All X' drops/switches only its own axis and holds the others;
# the count is the slice you'd land on. Anchors derive from the
# aux-stripped joint cells at runtime (mirrors the frontend's cell-sum).
# State: toss_outcome=won & result=won (a 1-free / 1D-bar view).

cells_json=$(curl -s "http://localhost:8000/api/v1/teams/splits?team=$TEAM_URL&$SCOPE_URL")
cells_count=$(echo "$cells_json" | python3 -c "import sys,json;print(len(json.load(sys.stdin)['cells']))")
assert_eq "endpoint emits the full 12-cell joint (zero-filled)" "12" "$cells_count"

cond_alltoss=$(echo "$cells_json" | python3 -c "import sys,json;print(sum(c['n'] for c in json.load(sys.stdin)['cells'] if c['result']=='won'))")
cond_alllost=$(echo "$cells_json" | python3 -c "import sys,json;print(sum(c['n'] for c in json.load(sys.stdin)['cells'] if c['toss_outcome']=='won' and c['result']=='lost'))")
full_total=$(echo "$cells_json"   | python3 -c "import sys,json;print(json.load(sys.stdin)['scope_total_n'])")

ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&toss_outcome=won&result=won"
settle 4

# This 2-filter state is the 1-free 1D-bar layout — assert the bar is present there too.
has_1d=$(ab_eval "!!document.querySelector('$MOSAIC_SEL .wisden-splits-1d')")
assert_eq "1-free view still shows the 1D bar" "true" "$has_1d"
has_bar=$(ab_eval "!!document.querySelector('$MOSAIC_SEL .wisden-splits-reset-bar')")
assert_eq "reset bar mounted in the 1-free view" "true" "$has_bar"

bar=$(ab_eval "document.querySelector('$MOSAIC_SEL .wisden-splits-reset-bar')?.innerText.replace(/\\n/g,' ') || ''")
assert_contains "All toss conditional (drop toss, keep won) = $cond_alltoss" "All toss · $cond_alltoss" "$bar"
assert_contains "All lost conditional (won toss, lost game) = $cond_alllost" "All lost · $cond_alllost" "$bar"
assert_contains "All matches = full scope $full_total" "All matches · $full_total" "$bar"

# Reset bar also mounts in the 0-free (all three set) status-strip view.
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&toss_outcome=won&inning=0&result=won"
settle 4
has_bar0=$(ab_eval "!!document.querySelector('$MOSAIC_SEL .wisden-splits-reset-bar')")
assert_eq "reset bar mounted in the 0-free status-strip view" "true" "$has_bar0"

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
