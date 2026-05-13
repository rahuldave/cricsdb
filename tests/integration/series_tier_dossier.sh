#!/bin/bash
# /series at broad scope (tier dossier) integration tests.
#
# Spec: internal_docs/spec-league-pages.md §Testing — Integration
# (originally /league, merged into /series 2026-05-13).
#
# Covers /series at a scope BROADER than a single tournament:
#   1. /series?gender=male&team_type=club&... renders the tier dossier
#      (TierDossier component) with SQL-anchored stat counts.
#   2. Champions DataTable row count matches SQL.
#   3. Prose H2 reads "Men's club Twenty20 cricket, 2024–2025"; all 7
#      tabs (Overview / Batting / Bowling / Fielding / Partnerships /
#      Records / Matches) render.
#   4. Batting subtab: tile row, leaderboards, top batter DOM == API.
#   5. /league redirects to /series.
#   6. /series?tournament=IPL still renders the per-tournament dossier
#      (TournamentDossier; 8 tabs).
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL" —
# every numeric expected derives from sqlite3 + curl at test runtime.

set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-2}"; }
sql()     { sqlite3 "$DB" "$1"; }
ok()      { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad()     { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq()     { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

SCOPE="gender=male&team_type=club&season_from=2024&season_to=2025"
SCOPE_SQL="WHERE m.gender='male' AND m.team_type='club' AND m.season>='2024' AND m.season<='2025' AND m.match_type IN ('T20','IT20')"

# ─── Test 1 — /series at broad scope renders tier dossier ─────────────
echo "Test 1 · /series at broad scope — tier dossier loads with SQL-anchored counts"

ab open "$BASE/series?$SCOPE"
settle 6

sql_matches=$(sql "SELECT COUNT(DISTINCT m.id) FROM match m $SCOPE_SQL")
api_matches=$(curl -sS "$API/api/v1/league/overview?$SCOPE" | python3 -c "import json,sys; print(json.load(sys.stdin)['matches'])")
dom_matches=$(ab_eval "(() => { const stat = Array.from(document.querySelectorAll('.wisden-statrow .wisden-stat')).find(s => s.querySelector('.wisden-stat-label')?.textContent === 'Matches'); return stat?.querySelector('.wisden-stat-value')?.textContent?.replace(/,/g, ''); })()")
assert_eq "matches: SQL == API" "$sql_matches" "$api_matches"
assert_eq "matches: DOM == SQL" "$sql_matches" "$dom_matches"

sql_tournaments=$(sql "SELECT COUNT(DISTINCT m.event_name) FROM match m $SCOPE_SQL")
dom_tournaments=$(ab_eval "(() => { const stat = Array.from(document.querySelectorAll('.wisden-statrow .wisden-stat')).find(s => s.querySelector('.wisden-stat-label')?.textContent === 'Tournaments'); return stat?.querySelector('.wisden-stat-value')?.textContent; })()")
assert_eq "tournaments DOM == SQL" "$sql_tournaments" "$dom_tournaments"

# ─── Test 2 — Champions DataTable row count ───────────────────────────
echo ""
echo "Test 2 · Champions DataTable row count"

sql_champions=$(sql "SELECT COUNT(*) FROM match m $SCOPE_SQL AND m.event_stage='Final' AND m.outcome_winner IS NOT NULL AND m.event_name IS NOT NULL")
dom_champions=$(ab_eval "(() => { const all = Array.from(document.querySelectorAll('section')); const sec = all.find(s => s.querySelector('h3')?.textContent === 'Champions in scope'); return sec ? sec.querySelectorAll('table tbody tr').length : 0; })()")
assert_eq "champion rows: DOM == SQL" "$sql_champions" "$dom_champions"

# ─── Test 3 — Prose H2 + 7 tabs ───────────────────────────────────────
echo ""
echo "Test 3 · Prose H2 + 7-tab bar (Overview/Batting/Bowling/Fielding/Partnerships/Records/Matches)"

dom_h2=$(ab_eval "document.querySelector('.wisden-page-title')?.textContent")
assert_eq "H2 reads prose scope" "Men's club Twenty20 cricket, 2024–2025" "$dom_h2"

tab_count=$(ab_eval "document.querySelectorAll('.wisden-tabs .wisden-tab').length")
assert_eq "7 tabs render" "7" "$tab_count"

tab_list=$(ab_eval "Array.from(document.querySelectorAll('.wisden-tabs .wisden-tab')).map(t => t.textContent).join(',')")
assert_eq "tab list" "Overview,Batting,Bowling,Fielding,Partnerships,Records,Matches" "$tab_list"

# ─── Test 4 — Batting subtab loads tile row + leaderboards ────────────
echo ""
echo "Test 4 · Batting subtab"

ab open "$BASE/series?$SCOPE&tab=Batting"
settle 4

first_label=$(ab_eval "document.querySelector('.wisden-statrow .wisden-stat-label')?.textContent")
assert_eq "First batting tile label" "Avg innings total" "$first_label"

leaderboard_rows=$(ab_eval "document.querySelectorAll('table tbody tr').length")
if [ "$(unq "$leaderboard_rows")" -ge 30 ]; then
  ok "Batting leaderboards have rows ($leaderboard_rows)"
else
  bad "Batting leaderboards row count too low ($leaderboard_rows)"
fi

api_top_runs=$(curl -sS "$API/api/v1/league/leaders/batting?$SCOPE&limit=5" | python3 -c "import json,sys; d=json.load(sys.stdin)['by_runs'][0]; print(d['runs'])")
dom_top_runs=$(ab_eval "(() => { const all = Array.from(document.querySelectorAll('h3')); const h = all.find(el => el.textContent === 'Top batters by runs'); if (!h) return null; const tbody = h.parentElement.querySelector('table tbody'); const cells = tbody?.querySelector('tr')?.querySelectorAll('td'); return cells?.[1]?.textContent; })()")
assert_eq "Top batter by runs (API == DOM)" "$api_top_runs" "$dom_top_runs"

# ─── Test 5 — /league legacy URL redirects to /series ─────────────────
echo ""
echo "Test 5 · /league legacy redirect → /series"

ab open "$BASE/league?gender=male&team_type=club"
settle 3
url=$(ab_eval "location.pathname + location.search")
case "$(unq "$url")" in
  "/series?gender=male&team_type=club"*) ok "Redirected /league → /series (params preserved)" ;;
  *) bad "Did NOT redirect — got: $(unq "$url")" ;;
esac

# ─── Test 6 — /series?tournament=X still renders TournamentDossier ────
echo ""
echo "Test 6 · /series?tournament=BBL still renders per-tournament dossier (regression check)"

ab open "$BASE/series?tournament=Big+Bash+League&gender=male&team_type=club"
settle 4

dom_h2_t=$(ab_eval "document.querySelector('.wisden-page-title')?.textContent")
assert_eq "H2 reads tournament name" "Big Bash League" "$dom_h2_t"

tab_count_t=$(ab_eval "document.querySelectorAll('.wisden-tabs .wisden-tab').length")
assert_eq "8 tabs (incl. Editions)" "8" "$tab_count_t"

# ─── Report ───────────────────────────────────────────────────────────
echo ""
echo "─── Result ───"
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "OK"
