#!/bin/bash
# Team-batting Distribution panel — DOM integration test.
#
# Spec: internal_docs/spec-distribution-stats.md §17.7.
#
# Asserts the panel renders correctly on /teams?team=X&tab=Batting,
# that stat-strip + chip values match SQL-derived anchors, that both
# URL-state keys (?dist_window_t and ?dist_metric_t_bat) round-trip
# correctly, that the sparkline bar count matches SQL n_innings
# (codified per-item-chart rule), and that the panel renders without
# overflow on a 390x844 mobile viewport.
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

sql() { sqlite3 "$DB" "$1" 2>&1; }

PANEL_SEL='section[aria-label="Per-innings team batting distribution"]'

# Fixture — Mumbai Indians IPL scope. Mirrors regression URL set so
# SQL + endpoint stay consistent.
TEAM="Mumbai Indians"
TEAM_URL="Mumbai%20Indians"
SCOPE_URL='gender=male&team_type=club&tournament=Indian%20Premier%20League'

# WHERE fragment that mirrors _team_innings_clause(team='Mumbai Indians',
# side='batting', filters={gender=male, team_type=club, tournament=IPL}).
# The leading `i.super_over=0` comes from FilterParams.build's
# has_innings_join branch.
MI_IPL_WHERE="
i.team = '$TEAM'
AND i.super_over = 0
AND m.gender = 'male'
AND m.team_type = 'club'
AND m.event_name = 'Indian Premier League'
"

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Panel mounts; Runs-tab stat strip matches SQL"

ab open "$BASE/teams?team=$TEAM_URL&tab=Batting&$SCOPE_URL"
settle 5

panel_present=$(ab_eval "!!document.querySelector('$PANEL_SEL')")
assert_eq "panel section exists" "true" "$panel_present"

# n_innings — count of MI batting innings under the active scope
sql_n=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_WHERE
  GROUP BY i.id
) sub
")
dom_n=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Innings\s*\n(\d+)/)?.[1] || ''")
assert_eq "Innings count matches SQL" "$sql_n" "$dom_n"

# Total runs
sql_total=$(sql "
SELECT SUM(runs) FROM (
  SELECT SUM(d.runs_total) AS runs FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_WHERE
  GROUP BY i.id
) sub
")
dom_total=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Total\s*\n(\d+)/)?.[1] || ''")
assert_eq "Total runs matches SQL" "$sql_total" "$dom_total"

# Mean / innings — render rounds to 1dp
sql_mean=$(awk "BEGIN { printf \"%.1f\", $sql_total / $sql_n }")
dom_mean=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Mean\s\/\sinnings\s*\n([\d.]+)/)?.[1] || ''")
assert_eq "Mean / innings matches SQL" "$sql_mean" "$dom_mean"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Runs tab — 9 chips render with correct denoms"

# Five simples + three chain-ladder + one doubling-at-10.
chip_n() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title*=\"95% CI\"]')].find(el => el.innerText.startsWith('$1'))?.title.match(/n=(\d+)/)?.[1] || ''"
}
chip_value() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title*=\"95% CI\"]')].find(el => el.innerText.startsWith('$1'))?.innerText.match(/(\d+)%/)?.[1] || ''"
}

n_lt100=$(unq "$(chip_n 'P(<100)')")
n_geq100=$(unq "$(chip_n 'P(≥100)')")
n_geq150=$(unq "$(chip_n 'P(≥150)')")
n_geq200=$(unq "$(chip_n 'P(≥200)')")
n_geq230=$(unq "$(chip_n 'P(≥230)')")
assert_eq "P(<100) chip denom == n_innings" "$sql_n" "$n_lt100"
assert_eq "P(≥100) chip denom == n_innings" "$sql_n" "$n_geq100"
assert_eq "P(≥150) chip denom == n_innings" "$sql_n" "$n_geq150"
assert_eq "P(≥200) chip denom == n_innings" "$sql_n" "$n_geq200"
assert_eq "P(≥230) chip denom == n_innings" "$sql_n" "$n_geq230"

# Chain-ladder: P(≥150│≥100) denom = SQL count(runs >= 100)
sql_n_ge100=$(sql "
SELECT COUNT(*) FROM (
  SELECT SUM(d.runs_total) AS runs FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_WHERE GROUP BY i.id
) sub WHERE runs >= 100
")
n_chain1=$(unq "$(chip_n 'P(≥150│≥100)')")
assert_eq "P(≥150│≥100) chip denom == count(runs ≥ 100)" "$sql_n_ge100" "$n_chain1"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Chip percentages match SQL anchors"

# P(≥150) value — render rounds to integer percent
sql_n_ge150=$(sql "
SELECT COUNT(*) FROM (
  SELECT SUM(d.runs_total) AS runs FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_WHERE GROUP BY i.id
) sub WHERE runs >= 150
")
sql_pct_ge150=$(awk "BEGIN { printf \"%d\", ($sql_n_ge150 * 100.0 / $sql_n) + 0.5 }")
dom_pct_ge150=$(unq "$(chip_value 'P(≥150)')")
assert_eq "P(≥150) percentage matches SQL" "$sql_pct_ge150" "$dom_pct_ge150"

# Doubling-at-10 cross-check: chip value × denom ≈ num
sql_doubling_denom=$(sql "
SELECT COUNT(*) FROM (
  SELECT SUM(d.runs_total) AS final_runs,
         SUM(CASE WHEN d.over_number BETWEEN 0 AND 9 THEN d.runs_total ELSE 0 END) AS runs_at_10,
         SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                  AND d.extras_wides=0 AND d.extras_noballs=0
                  THEN 1 ELSE 0 END) AS legal_balls_first_10
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_WHERE GROUP BY i.id
) sub WHERE legal_balls_first_10 >= 60 AND runs_at_10 > 0
")
sql_doubling_num=$(sql "
SELECT COUNT(*) FROM (
  SELECT SUM(d.runs_total) AS final_runs,
         SUM(CASE WHEN d.over_number BETWEEN 0 AND 9 THEN d.runs_total ELSE 0 END) AS runs_at_10,
         SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                  AND d.extras_wides=0 AND d.extras_noballs=0
                  THEN 1 ELSE 0 END) AS legal_balls_first_10
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_WHERE GROUP BY i.id
) sub WHERE legal_balls_first_10 >= 60 AND runs_at_10 > 0 AND final_runs >= 2.0 * runs_at_10
")
n_doubling=$(unq "$(chip_n 'P(2× final│at 10)')")
assert_eq "doubling chip denom == reached-10 count" "$sql_doubling_denom" "$n_doubling"
sql_doubling_pct=$(awk "BEGIN { printf \"%d\", ($sql_doubling_num * 100.0 / $sql_doubling_denom) + 0.5 }")
dom_doubling_pct=$(unq "$(chip_value 'P(2× final│at 10)')")
assert_eq "doubling chip percentage matches SQL" "$sql_doubling_pct" "$dom_doubling_pct"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Chip tier-color coordination"

# 3-tier discipline (CLAUDE.md): P(<100) INDIGO, P(≥100) SAGE,
# P(≥200) OCHRE. Tints from WISDEN_TIER_TINTS.
chip_bg() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title]')].find(el => el.innerText.startsWith('$1'))?.style.background || ''"
}
assert_contains "P(<100) chip uses INDIGO tint"  "rgba(112, 144, 168" "$(chip_bg 'P(<100)')"
assert_contains "P(≥100) chip uses SAGE tint"    "rgba(122, 142, 106" "$(chip_bg 'P(≥100)')"
assert_contains "P(≥200) chip uses OCHRE tint"   "rgba(201, 135, 31"  "$(chip_bg 'P(≥200)')"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Sparkline bar count == n_innings (codified rule)"

dom_spark_n=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]').length")
assert_eq "Sparkline bar count == SQL n_innings" "$sql_n" "$dom_spark_n"

# No height=0 bars — every innings should have a clickable
# footprint via the 4px stub zone.
zero_h=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]')].filter(r => parseFloat(r.getAttribute('height')) <= 0).length")
assert_eq "No height=0 bars (would be invisible)" "0" "$zero_h"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 · Match-link on first sparkline bar (chronological first)"

# First innings chronologically — match_id is the bar's <a href>
sql_first=$(sql "
SELECT i.match_id FROM (
  SELECT i.id, i.match_id, MIN(md.date) AS d
  FROM delivery dd
  JOIN innings i ON i.id = dd.innings_id
  JOIN match m ON m.id = i.match_id
  JOIN matchdate md ON md.match_id = m.id
  WHERE $MI_IPL_WHERE
  GROUP BY i.id
  ORDER BY d ASC, i.innings_number ASC
  LIMIT 1
) AS i
")
dom_first_href=$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline a')?.getAttribute('href') || ''")
assert_contains "first sparkline bar links to first match" "/matches/$sql_first" "$dom_first_href"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 7 · Run Rate tab — URL state + 4 chips"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Run Rate').click()" >/dev/null
settle 1
url_after=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric_t_bat=run_rate" "dist_metric_t_bat=run_rate" "\"$url_after\""

# Pool RR — render rounds to 2dp
sql_pool_rr=$(sql "
SELECT ROUND(SUM(runs) * 6.0 / SUM(balls), 2) FROM (
  SELECT SUM(d.runs_total) AS runs,
         SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_WHERE GROUP BY i.id
) sub
")
dom_pool_rr=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Pool RR\s*\n([\d.]+)/)?.[1] || ''")
assert_eq "Pool RR matches SQL" "$sql_pool_rr" "$dom_pool_rr"

# 4 RR chips — flipped polarity (low RR = INDIGO, high RR = OCHRE)
n_rr_leq7=$(unq "$(chip_n 'P(RR ≤7)')")
n_rr_geq10=$(unq "$(chip_n 'P(RR ≥10)')")
assert_eq "P(RR ≤7) chip denom == n_innings" "$sql_n" "$n_rr_leq7"
assert_eq "P(RR ≥10) chip denom == n_innings" "$sql_n" "$n_rr_geq10"

# Polarity-flipped tints — low RR is BAD for batter
assert_contains "P(RR ≤7) chip uses INDIGO tint (slow RR is bad)"  "rgba(112, 144, 168" "$(chip_bg 'P(RR ≤7)')"
assert_contains "P(RR ≥10) chip uses OCHRE tint (explosive RR is good)" "rgba(201, 135, 31" "$(chip_bg 'P(RR ≥10)')"

# Back to Runs — URL should DELETE dist_metric_t_bat
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Runs').click()" >/dev/null
settle 1
url_back=$(ab_eval "window.location.href" | tr -d '"')
case "$url_back" in
  *dist_metric_t_bat*) bad "Runs click DELETES dist_metric_t_bat — still present in: $url_back" ;;
  *) ok "Runs click DELETES dist_metric_t_bat param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 8 · Window toggle — Last 10 + sparkline rebar"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Last 10').click()" >/dev/null
settle 1
url_w=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_window_t=last_10" "dist_window_t=last_10" "\"$url_w\""

# Sparkline now ≤ 10 bars
last10_bars=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]').length")
if [ "$last10_bars" -le 10 ]; then ok "Last 10 sparkline ≤ 10 bars (got $last10_bars)"
else bad "Last 10 sparkline has $last10_bars bars (expected ≤ 10)"; fi

# Innings count drops to ≤ 10
inn_last10=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Innings\s*\n(\d+)/)?.[1] || ''" | tr -d '"')
if [ "$inn_last10" -le 10 ]; then ok "Last 10 stat-strip Innings ≤ 10 (got $inn_last10)"
else bad "Last 10 stat-strip Innings = $inn_last10 (expected ≤ 10)"; fi

# Back to Scope — URL should DELETE dist_window_t
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Scope').click()" >/dev/null
settle 1
url_w2=$(ab_eval "window.location.href" | tr -d '"')
case "$url_w2" in
  *dist_window_t*) bad "Scope click DELETES dist_window_t — still present in: $url_w2" ;;
  *) ok "Scope click DELETES dist_window_t param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 9 · Form-delta line — oxblood deltas, scope-baseline above"

# Two-line layout per CLAUDE.md "Delta lines need the baseline visible"
has_scope_baseline=$(ab_eval "/Scope average \/ innings/.test(document.querySelector('$PANEL_SEL').innerText)")
assert_eq "Form-delta line shows scope average above" "true" "$has_scope_baseline"

# Form deltas all in oxblood (#7A1F1F = rgb(122, 31, 31)) per CLAUDE.md
# "Form deltas in oxblood; sign carries direction".
oxblood_count=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL span.num')].filter(s => /^[+−][0-9]/.test(s.innerText) && s.style.color === 'rgb(122, 31, 31)').length")
non_oxblood=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL span.num')].filter(s => /^[+−][0-9]/.test(s.innerText) && s.style.color !== 'rgb(122, 31, 31)' && s.style.color !== '').length")
if [ "$oxblood_count" -gt 0 ]; then ok "Form deltas use oxblood ($oxblood_count signed values)"
else bad "Form deltas use oxblood — found 0 oxblood signed values"; fi
assert_eq "No green/red polarity on form deltas" "0" "$non_oxblood"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 10 · Mobile viewport (390x844) — panel renders without overflow"

ab set viewport 390 844
ab reload
settle 4

panel_overflow=$(ab_eval "(() => { const p = document.querySelector('$PANEL_SEL'); return p ? (p.scrollWidth > p.clientWidth + 1) : null; })()")
assert_eq "Panel has no horizontal overflow at 390px" "false" "$panel_overflow"

# Reset viewport
ab set viewport 1280 800

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────"
echo "Team-batting Distribution integration: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
