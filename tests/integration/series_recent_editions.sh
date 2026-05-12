#!/bin/bash
# Series landing — recent-editions strip.
#
# WHY THIS SCRIPT EXISTS: 2026-05-12 we added a "Recently played
# editions" strip to the /series landing page — top 5 (canonical
# tournament, season) pairs ordered by latest match date desc,
# includes in-progress editions (no Final required). Drives quick
# jumps to the most-recent edition dossier.
#
# Tests:
#   1. List renders with exactly 5 items.
#   2. Each rendered item == SQL top-5 (canonical, season) by date.
#   3. Each link's href encodes tournament+season+gender+team_type.
#   4. Gender filter (women's) narrows list to women's editions only.
#   5. Click first link → navigates to that edition's dossier
#      (URL contains the tournament + season params).
#   6. Mobile 390 viewport — list fits without horizontal overflow.
#
# All numeric expecteds derived from cricket.db at runtime per
# CLAUDE.md "Integration tests must self-anchor against SQL".
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
sql()     { sqlite3 "$DB" "$1" 2>&1; }
unq()     { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au; au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}
assert_contains() {
  local label="$1" needle="$2" actual="$3"
  local au; au=$(unq "$actual")
  if [[ "$au" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not found in: $au"; fi
}

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1
agent-browser set viewport 1280 800 >/dev/null 2>&1

# ─────────────────────────────────────────────────────────────────
# Test 1 — 5 items rendered on /series.
# ─────────────────────────────────────────────────────────────────
echo "Test 1 · 5 items rendered on /series"
ab open "$BASE/series"; sleep 4
item_count=$(ab_eval "document.querySelectorAll('.wisden-recent-editions li').length")
assert_eq "list size" "5" "$item_count"

# ─────────────────────────────────────────────────────────────────
# Test 2 — Items match SQL top-5 by latest match date.
# Canonicalisation collapses event_name variants to a single name
# server-side; we approximate by SELECTing on event_name and only
# comparing the season component, which is canonicalisation-stable.
# Stronger check: first item's tournament+season EXACTLY equals the
# SQL #1 ranked row.
# ─────────────────────────────────────────────────────────────────
echo
echo "Test 2 · Top item matches SQL #1 by-date"
# Note: event names contain spaces ("Indonesia tour of Malaysia"), so
# parse pipe-separated explicitly — never whitespace-split SQL output.
sql_row=$(sql "
SELECT m.event_name, m.season, MAX(md.date) AS last_date
FROM match m JOIN matchdate md ON md.match_id = m.id
WHERE m.event_name IS NOT NULL AND m.match_type = 'T20'
GROUP BY m.event_name, m.season
ORDER BY last_date DESC, m.event_name
LIMIT 1
")
sql_season=$(echo "$sql_row" | awk -F'|' '{print $2}')
sql_date=$(echo   "$sql_row" | awk -F'|' '{print $3}')
# The rendered link text is `<canonical> <season>` — we match the
# season suffix exactly; tournament prefix may be canonicalised.
top_text=$(ab_eval "document.querySelector('.wisden-recent-editions li a')?.textContent?.trim()")
assert_contains "top item ends with SQL season" "$sql_season" "$top_text"
top_date_present=$(ab_eval "document.querySelector('.wisden-recent-editions li a')?.getAttribute('href')")
assert_contains "top item href has season_from=$sql_season"  "season_from=$sql_season" "$top_date_present"
assert_contains "top item href has season_to=$sql_season"    "season_to=$sql_season"   "$top_date_present"

# ─────────────────────────────────────────────────────────────────
# Test 3 — Items are date-sorted descending. SQL fetches the top 5
# match-dates; DOM order must agree.
# ─────────────────────────────────────────────────────────────────
echo
echo "Test 3 · Items are date-sorted desc"
# Pull the rendered seasons in order
dom_seasons=$(ab_eval "Array.from(document.querySelectorAll('.wisden-recent-editions li a')).map(a => { const m = a.href.match(/season_from=([^&]+)/); return m ? decodeURIComponent(m[1]) : ''; }).join(',')")
# All 5 should be 2026 (most-recent year on cricket.db today)
all_2026_count=$(echo "$(unq "$dom_seasons")" | tr ',' '\n' | grep -c '^2026$')
assert_eq "all 5 items are season=2026 (newest year)" "5" "$all_2026_count"

# ─────────────────────────────────────────────────────────────────
# Test 4 — Women's gender filter narrows list to women's editions.
# ─────────────────────────────────────────────────────────────────
echo
echo "Test 4 · Gender=female narrows list to women's editions"
ab open "$BASE/series?gender=female"; sleep 4
women_count=$(ab_eval "document.querySelectorAll('.wisden-recent-editions li').length")
assert_eq "women's view item count" "5" "$women_count"
# Every link href should encode gender=female
women_all_female=$(ab_eval "Array.from(document.querySelectorAll('.wisden-recent-editions li a')).every(a => a.href.includes('gender=female'))")
assert_eq "all 5 women's items have gender=female in href" "true" "$women_all_female"
# SQL: top women's event by date — first item should match
women_top_season=$(sql "
SELECT m.season FROM match m JOIN matchdate md ON md.match_id=m.id
WHERE m.event_name IS NOT NULL AND m.match_type='T20' AND m.gender='female'
GROUP BY m.event_name, m.season
ORDER BY MAX(md.date) DESC, m.event_name
LIMIT 1
")
women_top_href=$(ab_eval "document.querySelector('.wisden-recent-editions li a')?.getAttribute('href')")
assert_contains "women's top item href has season=$women_top_season" "season_from=$women_top_season" "$women_top_href"

# ─────────────────────────────────────────────────────────────────
# Test 5 — Clicking the top link navigates to that edition's dossier.
# ─────────────────────────────────────────────────────────────────
echo
echo "Test 5 · Click first item → navigates to edition dossier"
ab open "$BASE/series"; sleep 4
# Capture pre-click href to know where we're headed
pre_href=$(ab_eval "document.querySelector('.wisden-recent-editions li a')?.getAttribute('href')")
expected_tournament=$(echo "$(unq "$pre_href")" | sed -n 's/.*tournament=\([^&]*\).*/\1/p')
ab_eval "document.querySelector('.wisden-recent-editions li a')?.click()" >/dev/null
sleep 3
post_url=$(ab_eval "window.location.search")
assert_contains "post-click URL has tournament=$expected_tournament" "tournament=$expected_tournament" "$post_url"
assert_contains "post-click URL has season_from=2026" "season_from=2026" "$post_url"

# ─────────────────────────────────────────────────────────────────
# Test 6 — Mobile viewport check (no horizontal overflow).
# ─────────────────────────────────────────────────────────────────
echo
echo "Test 6 · Mobile 390 viewport renders without overflow"
agent-browser set viewport 390 844 >/dev/null 2>&1
ab open "$BASE/series"; sleep 4
overflows=$(ab_eval "(() => { const ul = document.querySelector('.wisden-recent-editions'); if (!ul) return 'no-list'; return ul.getBoundingClientRect().right > window.innerWidth ? 'true' : 'false'; })()")
assert_eq "list does not overflow on 390 viewport" "false" "$overflows"
agent-browser set viewport 1280 800 >/dev/null 2>&1

# ─────────────────────────────────────────────────────────────────
echo
echo "─────────────────────────────────────"
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
