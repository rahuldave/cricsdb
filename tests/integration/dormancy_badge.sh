#!/bin/bash
# Dormancy badge integration test.
#
# Spec: internal_docs/design-decisions.md "Dormancy badge" +
# spec-distribution-stats.md §8 / §11 / §13 (last_match_date field
# on distribution lifetime block).
#
# Asserts:
# 1. Active player (Kohli) — badge ABSENT in both ScopedPageHeader
#    and ScopeStatusStrip.
# 2. Retired player (Gayle, db584dad) — badge PRESENT with
#    '(0 in 1y+)' text.
# 3. Backend last_match_date field present on the distribution
#    lifetime block; matches sqlite3 max-match-date for the scope.
# 4. Tight-scope Kohli@IPL 2016 — badge fires because scope's last
#    is 2016, > 1y ago. (Scope-aware dormancy.)
# 5. all-time button on a player page sets explicit
#    season_from / season_to (not empty); status bar shows season
#    range.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL".
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-2}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

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
  else bad "$label — '$needle' not in: $au"; fi
}

assert_absent() {
  local label="$1" needle="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" != *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' should be absent, found in: $au"; fi
}

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

KOHLI=ba607b88
GAYLE=db584dad
ABDV=c4487b84

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Backend — last_match_date on distribution lifetime block"

# Gayle's API response should carry last_match_date.
gayle_api_lmd=$(curl -sS "$API/api/v1/batters/$GAYLE/distribution" | python3 -c "import json,sys; print(json.load(sys.stdin)['lifetime']['last_match_date'])")
gayle_sql_lmd=$(sqlite3 "$DB" "
  SELECT MAX(md.date)
  FROM matchdate md
  JOIN innings i ON i.match_id = md.match_id
  JOIN delivery d ON d.innings_id = i.id
  WHERE d.batter_id = '$GAYLE'
")
assert_eq "Gayle last_match_date matches SQL" "$gayle_sql_lmd" "$gayle_api_lmd"

# Kohli's last_match_date should be recent (within 60 days of today).
kohli_api_lmd=$(curl -sS "$API/api/v1/batters/$KOHLI/distribution" | python3 -c "import json,sys; print(json.load(sys.stdin)['lifetime']['last_match_date'])")
gap_days=$(python3 -c "
from datetime import date
last = date.fromisoformat('$kohli_api_lmd')
gap = (date.today() - last).days
print(gap)
")
if [ "$gap_days" -le 60 ]; then ok "Kohli last_match_date within 60d of today (gap=$gap_days)"
else bad "Kohli last_match_date is $gap_days days old — expected ≤60"; fi

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · DOM — active player Kohli, badge ABSENT"

ab open "$BASE/batting?player=$KOHLI&gender=male"
settle 3

kohli_badge=$(ab_eval "document.querySelector('.wisden-dormancy-badge')?.textContent || 'NONE'")
assert_eq "Kohli — no dormancy badge" "NONE" "$kohli_badge"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · DOM — retired Gayle, badge PRESENT '(0 in 1y+)'"

ab open "$BASE/batting?player=$GAYLE&gender=male"
settle 3

# Page header: subject name + flag + badge
title_text=$(ab_eval "document.querySelector('.wisden-page-title')?.textContent")
assert_contains "Gayle title contains '(0 in 1y+)' badge" "(0 in 1y+)" "$title_text"

# Status bar: should have the badge too
status_text=$(ab_eval "document.querySelector('.wisden-scope-strip')?.textContent")
assert_contains "Gayle status strip contains '(0 in 1y+)'" "(0 in 1y+)" "$status_text"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Scope-aware — Kohli @ IPL 2016 → badge fires"

ab open "$BASE/batting?player=$KOHLI&gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2016&season_to=2016"
settle 3

scoped_title=$(ab_eval "document.querySelector('.wisden-page-title')?.textContent")
# 2016 is > 1 year ago at any plausible test date past 2017
assert_contains "Kohli IPL 2016 title contains '(0 in 1y+)'" "(0 in 1y+)" "$scoped_title"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Status bar derives all-time season range — URL stays clean"
# Spec: design-decisions.md "Status bar computes the all-time season
# range". When a subject is set + no season filter, the strip
# computes the implicit range from /api/v1/seasons (player-aware)
# and renders e.g. "Season: 2005/06–2021 (all-time)" — derived,
# visually distinct via the italic suffix. URL stays clean.

ab open "$BASE/batting?player=$ABDV&gender=male"
settle 3

# URL stays clean — no season_from / season_to auto-mutated.
url_clean=$(ab_eval "location.search")
case "$url_clean" in
  *season_from*|*season_to*) bad "URL gained season_* params on landing — should stay clean. Got: $url_clean" ;;
  *) ok "URL stays clean on subject-page landing (no auto-mutation)" ;;
esac

# Status bar derives the range from seasons fetch.
status_landed=$(ab_eval "document.querySelector('.wisden-scope-strip')?.textContent")
assert_contains "Status strip derives Season range" "Season:" "$status_landed"

# ABdV first season is 2005/06; last is 2021 (SQL-anchored).
abdv_first=$(sqlite3 "$DB" "
  SELECT MIN(season) FROM (
    SELECT DISTINCT m.season FROM match m
    JOIN matchplayer mp ON mp.match_id = m.id
    WHERE mp.person_id = '$ABDV' AND m.gender = 'male'
  )
")
abdv_last=$(sqlite3 "$DB" "
  SELECT MAX(season) FROM (
    SELECT DISTINCT m.season FROM match m
    JOIN matchplayer mp ON mp.match_id = m.id
    WHERE mp.person_id = '$ABDV' AND m.gender = 'male'
  )
")
assert_contains "Derived range starts at SQL-derived first ($abdv_first)" "$abdv_first" "$status_landed"
assert_contains "Derived range ends at SQL-derived last ($abdv_last)" "$abdv_last" "$status_landed"
assert_contains "Derived range carries '(all-time)' italic suffix" "(all-time)" "$status_landed"

# When the user picks a season range, the derived suffix DROPS.
ab open "$BASE/batting?player=$ABDV&gender=male&season_from=2018&season_to=2018"
settle 3
status_picked=$(ab_eval "document.querySelector('.wisden-scope-strip')?.textContent")
assert_contains "User-picked range shows Season: 2018" "Season: 2018" "$status_picked"
case "$status_picked" in
  *all-time*) bad "User-picked range still shows '(all-time)' suffix — should drop. Got: $status_picked" ;;
  *) ok "User-picked range drops '(all-time)' suffix" ;;
esac

# Landing without a subject path-param: derived range does NOT fire
# (would otherwise show the dataset's full span which isn't useful).
ab open "$BASE/batting?gender=male"
settle 3
status_landing=$(ab_eval "document.querySelector('.wisden-scope-strip')?.textContent")
case "$status_landing" in
  *all-time*) bad "Subject-less landing shows '(all-time)' — should be absent. Got: $status_landing" ;;
  *) ok "Subject-less landing does NOT compute derived range" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────"
echo "Dormancy badge integration: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
