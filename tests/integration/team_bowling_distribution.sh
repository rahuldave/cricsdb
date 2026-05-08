#!/bin/bash
# Team-bowling Distribution panel — DOM integration test.
#
# Spec: internal_docs/spec-distribution-stats.md §17.4 + §17.7.
#
# Asserts the panel renders correctly on /teams?team=X&tab=Bowling,
# that stat-strip + chip values match SQL-derived anchors across the
# three metric tabs (Wickets default / Runs Conceded / Economy), that
# both URL-state keys (?dist_window_t and ?dist_metric_t_bowl)
# round-trip correctly, that the sparkline bar count matches SQL
# n_innings (codified per-item-chart rule), and that the panel
# renders without overflow on a 390x844 mobile viewport.
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

PANEL_SEL='section[aria-label="Per-innings team bowling distribution"]'

# Fixture — Mumbai Indians IPL scope. Mirrors regression URL set so
# SQL + endpoint stay consistent.
TEAM="Mumbai Indians"
TEAM_URL="Mumbai%20Indians"
SCOPE_URL='gender=male&team_type=club&tournament=Indian%20Premier%20League'

# WHERE fragment that mirrors _team_innings_clause(team='Mumbai Indians',
# side='fielding', filters={gender=male, team_type=club, tournament=IPL}).
# Bowling-side: innings where MI was in the field (i.team != 'MI'
# AND MI is one of the match teams).
MI_IPL_BOWL_WHERE="
i.team != '$TEAM'
AND (m.team1 = '$TEAM' OR m.team2 = '$TEAM')
AND i.super_over = 0
AND m.gender = 'male'
AND m.team_type = 'club'
AND m.event_name = 'Indian Premier League'
"

# Team-credited wicket exclusion list — matches §16.3.1 spec
# (run-outs counted; retired/obstructing dropped).
WKT_EXCLUDE="('retired hurt','retired not out','retired out','obstructing the field')"

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Panel mounts; Wickets-tab stat strip matches SQL"

ab open "$BASE/teams?team=$TEAM_URL&tab=Bowling&$SCOPE_URL"
settle 5

panel_present=$(ab_eval "!!document.querySelector('$PANEL_SEL')")
assert_eq "panel section exists" "true" "$panel_present"

# n_innings — count of innings MI bowled in scope
sql_n=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_BOWL_WHERE
  GROUP BY i.id
) sub
")
dom_n=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Innings bowled\s*\n(\d+)/)?.[1] || ''")
assert_eq "Innings bowled count matches SQL" "$sql_n" "$dom_n"

# Total wickets credited (team-credited; 4-kind exclusion)
sql_wkts=$(sql "
SELECT COALESCE(SUM(wkts), 0) FROM (
  SELECT i.id, (
    SELECT COUNT(*) FROM wicket w
    JOIN delivery dd ON dd.id = w.delivery_id
    WHERE dd.innings_id = i.id AND w.kind NOT IN $WKT_EXCLUDE
  ) AS wkts
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_BOWL_WHERE
  GROUP BY i.id
) sub
")
dom_wkts=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Wickets total\s*\n(\d+)/)?.[1] || ''")
assert_eq "Wickets total matches SQL" "$sql_wkts" "$dom_wkts"

# Mean wickets — render rounds to 2dp
sql_mean_wkts=$(awk "BEGIN { printf \"%.2f\", $sql_wkts / $sql_n }")
dom_mean_wkts=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Mean wickets\s*\n([\d.]+)/)?.[1] || ''")
assert_eq "Mean wickets matches SQL" "$sql_mean_wkts" "$dom_mean_wkts"

# Pool SR (balls/wkt) — derived field, computed at render-time from
# economy.pool + runs_conceded.total + wickets.total.
sql_total_runs=$(sql "
SELECT COALESCE(SUM(runs), 0) FROM (
  SELECT i.id, SUM(d.runs_total) AS runs FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_BOWL_WHERE GROUP BY i.id
) sub
")
sql_total_balls=$(sql "
SELECT COALESCE(SUM(balls), 0) FROM (
  SELECT i.id, SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_BOWL_WHERE GROUP BY i.id
) sub
")
sql_pool_sr=$(awk "BEGIN { printf \"%.1f\", $sql_total_balls / $sql_wkts }")
dom_pool_sr=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Pool SR \(balls\/wkt\)\s*\n([\d.]+)/)?.[1] || ''")
assert_eq "Pool SR (balls/wkt) matches SQL" "$sql_pool_sr" "$dom_pool_sr"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Wickets tab — 8 chips render with correct denoms"

# Four simples + two ≥5-conditionals + two over-aware (≥3 at 10 +
# =10│≥3 at 10).
chip_n() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title*=\"95% CI\"]')].find(el => el.innerText.startsWith('$1'))?.title.match(/n=(\d+)/)?.[1] || ''"
}
chip_value() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title*=\"95% CI\"]')].find(el => el.innerText.startsWith('$1'))?.innerText.match(/(\d+)%/)?.[1] || ''"
}

n_leq3=$(unq "$(chip_n 'P(≤3)')")
n_geq5=$(unq "$(chip_n 'P(≥5)')")
n_geq7=$(unq "$(chip_n 'P(≥7)')")
n_eq10=$(unq "$(chip_n 'P(=10)')")
assert_eq "P(≤3) chip denom == n_innings" "$sql_n" "$n_leq3"
assert_eq "P(≥5) chip denom == n_innings" "$sql_n" "$n_geq5"
assert_eq "P(≥7) chip denom == n_innings" "$sql_n" "$n_geq7"
assert_eq "P(=10) chip denom == n_innings" "$sql_n" "$n_eq10"

# Conditional anchored at ≥5 — denom = SQL count(wkts ≥ 5)
sql_n_ge5=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id, (
    SELECT COUNT(*) FROM wicket w
    JOIN delivery dd ON dd.id = w.delivery_id
    WHERE dd.innings_id = i.id AND w.kind NOT IN $WKT_EXCLUDE
  ) AS wkts
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_BOWL_WHERE GROUP BY i.id
) sub WHERE wkts >= 5
")
n_cond1=$(unq "$(chip_n 'P(≥7│≥5)')")
assert_eq "P(≥7│≥5) chip denom == count(wkts ≥ 5)" "$sql_n_ge5" "$n_cond1"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Wickets chip percentages match SQL anchors"

# P(≥5) value — render rounds to integer percent
sql_pct_ge5=$(awk "BEGIN { printf \"%d\", ($sql_n_ge5 * 100.0 / $sql_n) + 0.5 }")
dom_pct_ge5=$(unq "$(chip_value 'P(≥5)')")
assert_eq "P(≥5) percentage matches SQL" "$sql_pct_ge5" "$dom_pct_ge5"

# Over-aware: P(opp ≥3 at 10) — denom = innings reaching 10 overs;
# num = innings where opp had ≥3 wkts down at end of over 10.
sql_reached10=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id, SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                         AND d.extras_wides=0 AND d.extras_noballs=0
                         THEN 1 ELSE 0 END) AS legal_balls_first_10
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_BOWL_WHERE GROUP BY i.id
) sub WHERE legal_balls_first_10 >= 60
")
n_at10=$(unq "$(chip_n 'P(≥3 at 10)')")
assert_eq "P(≥3 at 10) chip denom == reached-10 count" "$sql_reached10" "$n_at10"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Chip tier-color coordination"

# Wickets tab: ≤3 INDIGO (poor), ≥5 SAGE (typical), ≥7 OCHRE
# (strong). Tints from WISDEN_TIER_TINTS.
chip_bg() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title]')].find(el => el.innerText.startsWith('$1'))?.style.background || ''"
}
assert_contains "P(≤3) chip uses INDIGO tint"  "rgba(112, 144, 168" "$(chip_bg 'P(≤3)')"
assert_contains "P(≥5) chip uses SAGE tint"    "rgba(122, 142, 106" "$(chip_bg 'P(≥5)')"
assert_contains "P(≥7) chip uses OCHRE tint"   "rgba(201, 135, 31"  "$(chip_bg 'P(≥7)')"

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

# First MI bowling innings — match_id is the bar's <a href>
sql_first=$(sql "
SELECT i.match_id FROM (
  SELECT i.id, i.match_id, MIN(md.date) AS d
  FROM delivery dd
  JOIN innings i ON i.id = dd.innings_id
  JOIN match m ON m.id = i.match_id
  JOIN matchdate md ON md.match_id = m.id
  WHERE $MI_IPL_BOWL_WHERE
  GROUP BY i.id
  ORDER BY d ASC, i.innings_number ASC
  LIMIT 1
) AS i
")
dom_first_href=$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline a')?.getAttribute('href') || ''")
assert_contains "first sparkline bar links to first match" "/matches/$sql_first" "$dom_first_href"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 7 · Runs Conceded tab — URL state + 9 chips + escalation"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Runs Conceded').click()" >/dev/null
settle 1
url_after=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric_t_bowl=runs_conceded" "dist_metric_t_bowl=runs_conceded" "\"$url_after\""

# Total conceded — render rounds to integer
dom_total_rc=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Total\s*\n(\d+)/)?.[1] || ''")
assert_eq "Total runs conceded matches SQL" "$sql_total_runs" "$dom_total_rc"

# Mean / innings — render rounds to 1dp
sql_mean_rc=$(awk "BEGIN { printf \"%.1f\", $sql_total_runs / $sql_n }")
dom_mean_rc=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Mean \/ innings\s*\n([\d.]+)/)?.[1] || ''")
assert_eq "Mean / innings (conceded) matches SQL" "$sql_mean_rc" "$dom_mean_rc"

# 9 chips (5 simples + 3 chain-ladder + 1 doubling)
n_lt100=$(unq "$(chip_n 'P(<100)')")
n_geq200=$(unq "$(chip_n 'P(≥200)')")
assert_eq "P(<100) chip denom == n_innings" "$sql_n" "$n_lt100"
assert_eq "P(≥200) chip denom == n_innings" "$sql_n" "$n_geq200"

# Chip polarity FLIPPED — low conceded = OCHRE (good), high = INDIGO
assert_contains "P(<100) chip uses OCHRE tint (low conceded is good)"  "rgba(201, 135, 31"  "$(chip_bg 'P(<100)')"
assert_contains "P(≥200) chip uses INDIGO tint (heavy leakage is bad)" "rgba(112, 144, 168" "$(chip_bg 'P(≥200)')"

# Doubling-at-10 cross-check: chip value × denom ≈ num
sql_doubling_denom=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id,
         SUM(d.runs_total) AS final_runs,
         SUM(CASE WHEN d.over_number BETWEEN 0 AND 9 THEN d.runs_total ELSE 0 END) AS runs_at_10,
         SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                  AND d.extras_wides=0 AND d.extras_noballs=0
                  THEN 1 ELSE 0 END) AS legal_balls_first_10
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_BOWL_WHERE GROUP BY i.id
) sub WHERE legal_balls_first_10 >= 60 AND runs_at_10 > 0
")
sql_doubling_num=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id,
         SUM(d.runs_total) AS final_runs,
         SUM(CASE WHEN d.over_number BETWEEN 0 AND 9 THEN d.runs_total ELSE 0 END) AS runs_at_10,
         SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                  AND d.extras_wides=0 AND d.extras_noballs=0
                  THEN 1 ELSE 0 END) AS legal_balls_first_10
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_BOWL_WHERE GROUP BY i.id
) sub WHERE legal_balls_first_10 >= 60 AND runs_at_10 > 0 AND final_runs >= 2.0 * runs_at_10
")
n_doubling=$(unq "$(chip_n 'P(2× final│at 10)')")
assert_eq "doubling chip denom == reached-10 count" "$sql_doubling_denom" "$n_doubling"
sql_doubling_pct=$(awk "BEGIN { printf \"%d\", ($sql_doubling_num * 100.0 / $sql_doubling_denom) + 0.5 }")
dom_doubling_pct=$(unq "$(chip_value 'P(2× final│at 10)')")
assert_eq "doubling chip percentage matches SQL" "$sql_doubling_pct" "$dom_doubling_pct"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 8 · Economy tab — URL state + 4 chips + Pool RPO"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Economy').click()" >/dev/null
settle 1
url_econ=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric_t_bowl=economy" "dist_metric_t_bowl=economy" "\"$url_econ\""

# Pool RPO — total_runs × 6 / total_balls; render rounds to 2dp
sql_pool_rpo=$(awk "BEGIN { printf \"%.2f\", $sql_total_runs * 6.0 / $sql_total_balls }")
dom_pool_rpo=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Pool RPO\s*\n([\d.]+)/)?.[1] || ''")
assert_eq "Pool RPO matches SQL" "$sql_pool_rpo" "$dom_pool_rpo"

# 4 RPO chips — bowler-conventional polarity (low RPO = OCHRE, high = INDIGO)
n_econ_leq6=$(unq "$(chip_n 'P(econ ≤6)')")
n_econ_geq10=$(unq "$(chip_n 'P(econ ≥10)')")
assert_eq "P(econ ≤6) chip denom == n_innings" "$sql_n" "$n_econ_leq6"
assert_eq "P(econ ≥10) chip denom == n_innings" "$sql_n" "$n_econ_geq10"

# Conventional polarity — low RPO is OCHRE (good for bowler)
assert_contains "P(econ ≤6) chip uses OCHRE tint (tight is good)"     "rgba(201, 135, 31"  "$(chip_bg 'P(econ ≤6)')"
assert_contains "P(econ ≥10) chip uses INDIGO tint (loose is bad)"    "rgba(112, 144, 168" "$(chip_bg 'P(econ ≥10)')"

# Back to Wickets — URL should DELETE dist_metric_t_bowl
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Wickets').click()" >/dev/null
settle 1
url_back=$(ab_eval "window.location.href" | tr -d '"')
case "$url_back" in
  *dist_metric_t_bowl*) bad "Wickets click DELETES dist_metric_t_bowl — still present in: $url_back" ;;
  *) ok "Wickets click DELETES dist_metric_t_bowl param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 9 · Window toggle — Last 10 + sparkline rebar"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Last 10').click()" >/dev/null
settle 1
url_w=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_window_t=last_10" "dist_window_t=last_10" "\"$url_w\""

# Sparkline now ≤ 10 bars
last10_bars=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]').length")
if [ "$last10_bars" -le 10 ]; then ok "Last 10 sparkline ≤ 10 bars (got $last10_bars)"
else bad "Last 10 sparkline has $last10_bars bars (expected ≤ 10)"; fi

# Innings count drops to ≤ 10
inn_last10=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Innings bowled\s*\n(\d+)/)?.[1] || ''" | tr -d '"')
if [ "$inn_last10" -le 10 ]; then ok "Last 10 stat-strip Innings bowled ≤ 10 (got $inn_last10)"
else bad "Last 10 stat-strip Innings bowled = $inn_last10 (expected ≤ 10)"; fi

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
echo "Test 10 · Form-delta line — oxblood deltas, scope-baseline above"

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
echo "Test 11 · Mobile viewport (390x844) — panel renders without overflow"

ab set viewport 390 844
ab reload
settle 4

panel_overflow=$(ab_eval "(() => { const p = document.querySelector('$PANEL_SEL'); return p ? (p.scrollWidth > p.clientWidth + 1) : null; })()")
assert_eq "Panel has no horizontal overflow at 390px" "false" "$panel_overflow"

# Reset viewport
ab set viewport 1280 800

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 12 · League scope-comparison reference line + legend (Wickets default)"

# Reload at default viewport on the default tab.
ab open "$BASE/teams?team=$TEAM_URL&tab=Bowling&$SCOPE_URL"
settle 4

API_BASE="${API_BASE:-http://localhost:8000}"
api_summary=$(curl -s "$API_BASE/api/v1/teams/$TEAM_URL/bowling/summary?$SCOPE_URL")
api_wickets_sa=$(echo "$api_summary" | python3 -c "
import json, sys
r = json.load(sys.stdin)
v = r['wickets']['scope_avg']
print(f'{v:.2f}' if v is not None else '')")

league_line=$(ab_eval "!!document.querySelector('$PANEL_SEL svg.wisden-dist-sparkline line[data-ref=\"league\"]')")
assert_eq "league reference line renders on Wickets tab" "true" "$league_line"
league_stroke=$(ab_eval "document.querySelector('$PANEL_SEL svg.wisden-dist-sparkline line[data-ref=\"league\"]')?.getAttribute('stroke') || ''")
assert_eq "league line uses forest green (Wickets)" "#3F7A4D" "$league_stroke"
legend_text=$(ab_eval "Array.from(document.querySelectorAll('$PANEL_SEL div,$PANEL_SEL span')).find(el => /league avg/.test(el.innerText) && el.children.length < 30)?.innerText || ''")
assert_contains "Wickets legend includes league avg label" "league avg $api_wickets_sa wkts/inn" "$legend_text"

# Switch to Economy tab and verify the league line redraws with
# the economy scope_avg.
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Economy').click()" >/dev/null
settle 1
api_econ_sa=$(echo "$api_summary" | python3 -c "
import json, sys
r = json.load(sys.stdin)
v = r['economy']['scope_avg']
print(f'{v:.2f}' if v is not None else '')")
econ_legend=$(ab_eval "Array.from(document.querySelectorAll('$PANEL_SEL div,$PANEL_SEL span')).find(el => /league avg/.test(el.innerText) && el.children.length < 30)?.innerText || ''")
assert_contains "Economy legend includes league avg label" "league avg $api_econ_sa RPO" "$econ_legend"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────"
echo "Team-bowling Distribution integration: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
