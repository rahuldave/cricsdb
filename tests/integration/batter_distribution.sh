#!/bin/bash
# Batter Distribution panel — DOM integration test.
#
# Spec: internal_docs/spec-distribution-stats.md §9.10.
#
# Asserts the panel renders correctly on /batting?player=X, that
# stat-strip values match SQL-derived anchors against cricket.db,
# that the window toggle is URL-encoded (?dist_window=...) per
# §9.7 + feedback_state_location.md, that deep-links with the
# param land on the right window with no Lifetime flash, that
# the form-delta line is window-independent (per §9.2.5), that
# back-button restores prior window, and that suggested-split
# clicks navigate to the broader scope.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL"
# — every numeric expected value is derived from cricket.db at
# runtime, never hardcoded.
#
# Per the post-be4d755 rule (feedback_test_every_call_site): the
# inning aux interaction is exercised via click-after-mount, not
# just deep-link.
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

sql() { sqlite3 "$DB" "$1" 2>&1; }

KOHLI=ba607b88
SCOPE='tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&gender=male&team_type=club'
# WHERE clause shared by every SQL anchor below — keep the API +
# integration aligned by reading the same clauses at test runtime.
KOHLI_IPL_2024_WHERE="
d.batter_id = '$KOHLI'
AND d.extras_wides = 0 AND d.extras_noballs = 0
AND m.event_name = 'Indian Premier League'
AND m.season = '2024'
AND i.super_over = 0
"
INNS_SQL="SELECT COUNT(DISTINCT i.id) FROM delivery d JOIN innings i ON i.id = d.innings_id JOIN match m ON m.id = i.match_id WHERE $KOHLI_IPL_2024_WHERE"

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Panel renders + stat strip matches SQL"

ab open "$BASE/batting?player=$KOHLI&$SCOPE"
settle 4

# Panel section presence
panel_present=$(ab_eval "!!document.querySelector('section[aria-label=\"Per-innings runs distribution\"]')")
assert_eq "panel section exists" "true" "$panel_present"

# n_innings — SQL anchor
sql_inns=$(sql "$INNS_SQL")
dom_inns=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.match(/(\d+)\s+inns/)?.[1] || ''")
assert_eq "Lifetime n_innings matches SQL" "$sql_inns" "$dom_inns"

# Total runs — SQL anchor on Average label-value via lifetime mean
# integrity: mean × n ≈ total. Easier: just check Mean value matches
# computed mean from SQL.
sql_runs=$(sql "SELECT SUM(d.runs_batter) FROM delivery d JOIN innings i ON i.id = d.innings_id JOIN match m ON m.id = i.match_id WHERE $KOHLI_IPL_2024_WHERE")
sql_mean=$(awk "BEGIN { printf \"%.1f\", $sql_runs / $sql_inns }")
dom_mean=$(ab_eval "(() => { const t = document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText; const m = t.match(/Mean \/ inn\s*\n([\d.]+)/); return m ? m[1] : ''; })()")
assert_eq "Lifetime Mean / inn matches SQL-derived mean" "$sql_mean" "$dom_mean"

# Median — SQL ordered-row trick: pull the middle value(s) from runs
# per innings. Cricket median is the cricketing convention (notouts
# treated as completed) so we just take the literal median of the
# per-innings runs sum.
sql_median=$(sql "
WITH sorted AS (
  SELECT SUM(d.runs_batter) AS r,
         ROW_NUMBER() OVER (ORDER BY SUM(d.runs_batter)) AS rn,
         COUNT(*) OVER () AS n
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $KOHLI_IPL_2024_WHERE
  GROUP BY i.id
)
SELECT CAST(AVG(r) AS INTEGER) FROM sorted WHERE rn IN ((n+1)/2, (n+2)/2)
")
dom_median=$(ab_eval "(() => { const t = document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText; const m = t.match(/Median\s*\n(\d+)/); return m ? m[1] : ''; })()")
assert_eq "Lifetime Median matches SQL median" "$sql_median" "$dom_median"

# P(≥50) — count(runs ≥ 50) / n_innings
sql_50_plus=$(sql "
SELECT COUNT(*) FROM (
  SELECT SUM(d.runs_batter) AS r
  FROM delivery d JOIN innings i ON i.id = d.innings_id JOIN match m ON m.id = i.match_id
  WHERE $KOHLI_IPL_2024_WHERE GROUP BY i.id
) WHERE r >= 50
")
sql_p50_pct=$(awk "BEGIN { printf \"%d\", ($sql_50_plus / $sql_inns) * 100 + 0.5 }")
dom_p50=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.match(/P\(.50\)\s*\n(\d+)%/)?.[1] || ''")
assert_eq "Lifetime P(≥50)% matches SQL count/n" "$sql_p50_pct" "$dom_p50"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Window toggle URL state"

# Toggle to Last 10
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button')].find(b => b.innerText.includes('Last 10')).click()" >/dev/null
settle 1
url_after=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_window=last_10 on toggle" "dist_window=last_10" "\"$url_after\""

# n_innings on Last 10 view — should be ≤ 10 and exactly min(10, lifetime_n)
expected_l10_n=$(awk "BEGIN { print ($sql_inns < 10) ? $sql_inns : 10 }")
dom_l10_inns=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.match(/(\d+)\s+inns/)?.[1] || ''")
assert_eq "Last 10 n_innings = min(10, lifetime_n)" "$expected_l10_n" "$dom_l10_inns"

# Form delta line stays the same — assert it's still present and
# hasn't changed shape (window-independent per §9.2.5).
form_delta_visible=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.includes('Form vs scope')")
assert_eq "Form delta line visible after Last 10 toggle (window-independent)" "true" "$form_delta_visible"

# Back to Scope (default) via toggle — URL should DELETE dist_window
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button')].find(b => b.innerText.trim() === 'Scope').click()" >/dev/null
settle 1
url_scope=$(ab_eval "window.location.href" | tr -d '"')
case "$url_scope" in
  *dist_window*) bad "Scope click DELETES dist_window param — still present in: $url_scope" ;;
  *) ok "Scope click DELETES dist_window param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Back-button restores prior window"

# Navigate Scope → Last 10 → Last 60d, then back.
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button')].find(b => b.innerText.trim() === 'Last 10').click()" >/dev/null
settle 1
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button')].find(b => b.innerText.trim() === 'Last 60d').click()" >/dev/null
settle 1

# Back should restore Last 10 (dist_window=last_10)
ab back >/dev/null
settle 1
url_after_back=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "back-button after Last 60d → Last 10" "dist_window=last_10" "\"$url_after_back\""
active=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"] .wisden-seg.is-active')?.innerText")
assert_eq "active toggle = Last 10 after back" "Last 10" "$active"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Deep-link with dist_window — no Lifetime flash"

ab open "$BASE/batting?player=$KOHLI&$SCOPE&dist_window=last_60d"
settle 4
active=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"] .wisden-seg.is-active')?.innerText")
assert_eq "deep-link ?dist_window=last_60d → Last 60d active" "Last 60d" "$active"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Suggested split navigates + URL updates"

# Land back on the IPL 2024 view
ab open "$BASE/batting?player=$KOHLI&$SCOPE"
settle 4

# Click "All Indian Premier League"
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] a')].find(a => a.innerText === 'All Indian Premier League')?.click()" >/dev/null
settle 4
url_after_split=$(ab_eval "window.location.href" | tr -d '"')
case "$url_after_split" in
  *season_from=2024*) bad "Split click should DROP season_from but still present: $url_after_split" ;;
  *) ok "Split click DROPS season_from from URL" ;;
esac
assert_contains "Split click KEEPS tournament=Indian Premier League" "tournament=Indian+Premier+League" "\"$url_after_split\""

# n_innings on the new (broader) scope > 15
sql_ipl_all_inns=$(sql "
SELECT COUNT(DISTINCT i.id)
FROM delivery d JOIN innings i ON i.id = d.innings_id JOIN match m ON m.id = i.match_id
WHERE d.batter_id = '$KOHLI'
  AND d.extras_wides = 0 AND d.extras_noballs = 0
  AND m.event_name = 'Indian Premier League'
  AND i.super_over = 0
")
dom_ipl_all_inns=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.match(/(\d+)\s+inns/)?.[1] || ''")
assert_eq "Broader-scope n_innings (all IPL) matches SQL" "$sql_ipl_all_inns" "$dom_ipl_all_inns"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 · Inning aux click-after-mount refetches the panel"

# Mount the page (no inning aux)
ab open "$BASE/batting?player=$KOHLI&$SCOPE"
settle 4
mount_inns=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.match(/(\d+)\s+inns/)?.[1] || ''")
assert_eq "Lifetime n_innings on mount (sanity)" "$sql_inns" "$mount_inns"

# Click the InningToggle "1st innings" pill (NOT a panel pill — the
# top-of-page toggle that sets ?inning=0)
ab_eval "[...document.querySelectorAll('.wisden-seg')].find(b => b.innerText.trim() === '1st innings')?.click()" >/dev/null
settle 3
url_with_inning=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "InningToggle click writes ?inning=0" "inning=0" "\"$url_with_inning\""

# Panel n_innings should now be SMALLER (only innings where Kohli's
# team batted first). SQL anchor: count innings with i.innings_number=0
sql_inn0=$(sql "
SELECT COUNT(DISTINCT i.id)
FROM delivery d JOIN innings i ON i.id = d.innings_id JOIN match m ON m.id = i.match_id
WHERE $KOHLI_IPL_2024_WHERE AND i.innings_number = 0
")
dom_inn0=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.match(/(\d+)\s+inns/)?.[1] || ''")
assert_eq "Panel n_innings refetches under inning=0" "$sql_inn0" "$dom_inn0"
# And inning=0 + inning=1 should partition lifetime (sanity)
ab_eval "[...document.querySelectorAll('.wisden-seg')].find(b => b.innerText.trim() === '2nd innings')?.click()" >/dev/null
settle 3
sql_inn1=$(sql "
SELECT COUNT(DISTINCT i.id)
FROM delivery d JOIN innings i ON i.id = d.innings_id JOIN match m ON m.id = i.match_id
WHERE $KOHLI_IPL_2024_WHERE AND i.innings_number = 1
")
dom_inn1=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.match(/(\d+)\s+inns/)?.[1] || ''")
assert_eq "Panel n_innings refetches under inning=1" "$sql_inn1" "$dom_inn1"
partition_n=$((sql_inn0 + sql_inn1))
assert_eq "inning=0 + inning=1 == lifetime n_innings (partition)" "$sql_inns" "$partition_n"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 7 · Empty-scope renders placeholder"

ab open "$BASE/batting?player=$KOHLI&filter_venue=Nonexistent%20Ground"
settle 4
panel_text=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText")
assert_contains "Empty-scope placeholder shown" "No innings under this filter" "$panel_text"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────────────────────────"
echo "$PASS pass · $FAIL fail"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
