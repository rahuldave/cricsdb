#!/bin/bash
# Three-tier inline baseline visual on /batting, /bowling, /fielding.
#
# The dedicated discipline pages got the same per-tile baseline
# rendering as /players (Phase 5) — value / vs base N / coloured
# delta chip. This test locks the visual + plumbing per page.
#
# SQL-anchoring discipline (CLAUDE.md "Integration tests must
# self-anchor against SQL"): every numeric expected value is
# derived from cricket.db at test runtime, never hardcoded. The
# /api/v1/scope/averages/players/* sanity tests lock the API
# scope_avg ↔ direct SQL convex-combination chain; this
# integration test extends that to DOM ↔ API.
#
# Stable historical scopes — pinned to seasons that no longer
# accept new matches so the values stay stable across DB updates:
#   - Kohli IPL 2016 (famous 973-run season, 16 matches)
#   - Bumrah IPL 2016 (his early IPL peak)
#   - Kohli IPL 2016 fielding (catches as outfielder)
#
# Spec: spec-player-compare-average.md Phase 5 extended to
# discipline pages (out-of-spec polish 2026-05-20).
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0

KOHLI="ba607b88"
BUMRAH="462411b3"
IPL_URL="Indian+Premier+League"
IPL_ENC="Indian%20Premier%20League"

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
sql()     { sqlite3 "$DB" "$1" 2>&1; }
unq()     { sed 's/^"//;s/"$//'; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then ok "$label (=$expected)"
  else bad "$label  expected='$expected'  actual='$actual'"; fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  case "$haystack" in
    *"$needle"*) ok "$label (contains '$needle')" ;;
    *) bad "$label  '$haystack' missing '$needle'" ;;
  esac
}

# Get the subtitle text for a tile by label.
tile_sub() {
  local label="$1"
  ab_eval "
    Array.from(document.querySelectorAll('.wisden-stat'))
      .find(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label')
      ?.querySelector('.wisden-stat-sub')?.textContent?.trim() || ''
  " | unq
}

tile_value() {
  local label="$1"
  ab_eval "
    Array.from(document.querySelectorAll('.wisden-stat'))
      .find(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label')
      ?.querySelector('.wisden-stat-value')?.textContent?.trim() || ''
  " | unq
}

# ───────────────────────────────────────────────────────────────────
# Test 1 — /batting page, Kohli IPL 2016
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 1: /batting Kohli IPL 2016 (stable historical scope)"
ab open "$BASE/batting?player=$KOHLI&tournament=$IPL_URL&season_from=2016&season_to=2016"
sleep 3

# SQL-anchored expected average: SUM(runs_batter on legal balls) /
# COUNT(wicket rows where player_out_id=Kohli, not retired-hurt).
sql_runs=$(sql "
  SELECT SUM(d.runs_batter) FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE d.batter_id = '$KOHLI' AND i.super_over = 0
    AND m.event_name = 'Indian Premier League'
    AND m.season = '2016'
    AND d.extras_wides = 0 AND d.extras_noballs = 0
")
sql_dismissals=$(sql "
  SELECT COUNT(*) FROM wicket w
  JOIN delivery d ON d.id = w.delivery_id
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE w.player_out_id = '$KOHLI' AND i.super_over = 0
    AND m.event_name = 'Indian Premier League'
    AND m.season = '2016'
    AND w.kind NOT IN ('retired hurt', 'retired out')
")
sql_avg=$(python3 -c "print(f'{$sql_runs/$sql_dismissals:.2f}')")

dom_avg=$(tile_value "Average")
assert_eq "Kohli IPL 2016 Avg DOM ↔ SQL" "$sql_avg" "$dom_avg"

# Subtitle present with "vs base" + delta chip.
avg_sub=$(tile_sub "Average")
assert_contains "Avg subtitle has 'vs base'" "vs base " "$avg_sub"
assert_contains "Avg subtitle has %" "%" "$avg_sub"

# API scope_avg matches DOM subtitle scope_avg.
api_avg_scope=$(curl -s "$API/api/v1/batters/$KOHLI/summary?tournament=$IPL_ENC&season_from=2016&season_to=2016" \
  | python3 -c "import json,sys;m=json.load(sys.stdin)['average'];print(m['scope_avg'])")
assert_contains "Avg subtitle scope_avg ↔ API" "$api_avg_scope" "$avg_sub"

# Strike Rate, Dot % both have baselines.
sr_sub=$(tile_sub "Strike Rate")
assert_contains "SR subtitle has 'vs base'" "vs base " "$sr_sub"
dp_sub=$(tile_sub "Dot %")
assert_contains "Dot % subtitle has 'vs base'" "vs base " "$dp_sub"

# B/Four + B/Boundary baselines (added 2026-05-20 — cohort endpoint
# now derives balls_per_{four,six,boundary} per bucket as the
# inverse of fours/balls × 100, then convex-combines).
bf_sub=$(tile_sub "B/Four")
assert_contains "B/Four subtitle has 'vs base'" "vs base " "$bf_sub"
bb_sub=$(tile_sub "B/Boundary")
assert_contains "B/Boundary subtitle has 'vs base'" "vs base " "$bb_sub"

# Counts that don't have a cohort baseline should NOT have subtitles
# (Matches, Innings, Runs).
matches_sub=$(tile_sub "Matches")
assert_eq "Matches has no subtitle" "" "$matches_sub"

# ───────────────────────────────────────────────────────────────────
# Test 2 — /bowling page, Bumrah IPL 2016
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 2: /bowling Bumrah IPL 2016"
ab open "$BASE/bowling?player=$BUMRAH&tournament=$IPL_URL&season_from=2016&season_to=2016"
sleep 3

# SQL-anchored expected economy: SUM(runs_total) * 6 / SUM(legal_balls).
sql_runs_conceded=$(sql "
  SELECT SUM(d.runs_total) FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE d.bowler_id = '$BUMRAH' AND i.super_over = 0
    AND m.event_name = 'Indian Premier League'
    AND m.season = '2016'
")
sql_legal_balls=$(sql "
  SELECT COUNT(*) FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE d.bowler_id = '$BUMRAH' AND i.super_over = 0
    AND m.event_name = 'Indian Premier League'
    AND m.season = '2016'
    AND d.extras_wides = 0 AND d.extras_noballs = 0
")
sql_econ=$(python3 -c "print(f'{$sql_runs_conceded*6.0/$sql_legal_balls:.2f}')")

dom_econ=$(tile_value "Economy")
assert_eq "Bumrah IPL 2016 Econ DOM ↔ SQL" "$sql_econ" "$dom_econ"

econ_sub=$(tile_sub "Economy")
assert_contains "Econ subtitle has 'vs base'" "vs base " "$econ_sub"
# Bumrah's bowling stats should be BELOW cohort (he's elite) → ↓ green.
assert_contains "Econ subtitle has ↓ arrow (lower=better aligned)" "↓" "$econ_sub"

# Average + SR also have baselines.
avg_sub=$(tile_sub "Average")
assert_contains "Bowling Avg subtitle has 'vs base'" "vs base " "$avg_sub"
sr_sub=$(tile_sub "Strike Rate")
assert_contains "Bowling SR subtitle has 'vs base'" "vs base " "$sr_sub"

# B/Boundary baseline (added 2026-05-20 — bowling cohort derives
# balls_per_boundary from the combined boundaries column).
bb_sub=$(tile_sub "B/Boundary")
assert_contains "Bowling B/Boundary subtitle has 'vs base'" "vs base " "$bb_sub"
# Higher = better for bowler; Bumrah elite → ↑ arrow.
assert_contains "Bowling B/Boundary subtitle has ↑ (higher=better aligned)" "↑" "$bb_sub"

# API scope_avg matches DOM scope_avg for economy.
api_econ_scope=$(curl -s "$API/api/v1/bowlers/$BUMRAH/summary?tournament=$IPL_ENC&season_from=2016&season_to=2016" \
  | python3 -c "import json,sys;m=json.load(sys.stdin)['economy'];print(m['scope_avg'])")
assert_contains "Econ subtitle scope_avg ↔ API" "$api_econ_scope" "$econ_sub"

# Wickets count has no baseline.
wkts_sub=$(tile_sub "Wickets")
assert_eq "Wickets has no subtitle" "" "$wkts_sub"

# ───────────────────────────────────────────────────────────────────
# Test 3 — /fielding page, Kohli IPL 2016 (outfielder)
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 3: /fielding Kohli IPL 2016 (outfielder cohort)"
ab open "$BASE/fielding?player=$KOHLI&tournament=$IPL_URL&season_from=2016&season_to=2016"
sleep 3

# SQL-anchored: non-substitute fielding credits at this scope, /
# matchplayer matches at this scope.
sql_credits=$(sql "
  SELECT COUNT(*) FROM fieldingcredit fc
  JOIN delivery d ON d.id = fc.delivery_id
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE fc.fielder_id = '$KOHLI' AND i.super_over = 0
    AND m.event_name = 'Indian Premier League'
    AND m.season = '2016'
    AND COALESCE(fc.is_substitute, 0) = 0
")
sql_matches=$(sql "
  SELECT COUNT(DISTINCT mp.match_id) FROM matchplayer mp
  JOIN match m ON m.id = mp.match_id
  WHERE mp.person_id = '$KOHLI'
    AND m.event_name = 'Indian Premier League'
    AND m.season = '2016'
")

# Dis/Match value.
sql_dis_per_match=$(python3 -c "print(f'{$sql_credits/$sql_matches:.2f}' if $sql_matches > 0 else '-')")

dom_dis_match=$(tile_value "Dis/Match")
assert_eq "Kohli IPL 2016 Dis/Match DOM ↔ SQL" "$sql_dis_per_match" "$dom_dis_match"

dm_sub=$(tile_sub "Dis/Match")
assert_contains "Dis/Match subtitle has 'vs base'" "vs base " "$dm_sub"
assert_contains "Dis/Match subtitle has delta chip" "%" "$dm_sub"

# Counts shouldn't have baseline subtitles.
catches_sub=$(tile_sub "Catches")
assert_eq "Catches has no subtitle" "" "$catches_sub"

# ───────────────────────────────────────────────────────────────────
# Test 4 — Mobile viewport (390 width) — no overflow on any page
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 4: mobile viewport — no horizontal overflow"
ab set viewport 390 844

for path in \
  "/batting?player=$KOHLI&tournament=$IPL_URL&season_from=2016&season_to=2016" \
  "/bowling?player=$BUMRAH&tournament=$IPL_URL&season_from=2016&season_to=2016" \
  "/fielding?player=$KOHLI&tournament=$IPL_URL&season_from=2016&season_to=2016"; do
  ab open "$BASE$path"
  sleep 3
  overflow=$(ab_eval "document.body.scrollWidth > window.innerWidth ? 'YES' : 'NO'" | unq)
  label="mobile-fits $(echo "$path" | cut -d'?' -f1)"
  assert_eq "$label" "NO" "$overflow"
done

ab set viewport 1280 720

# ───────────────────────────────────────────────────────────────────

echo
echo "PASS: $PASS"
echo "FAIL: $FAIL"
[ "$FAIL" = 0 ]
