#!/bin/bash
# Team-fielding Distribution panel — DOM integration test.
#
# Spec: internal_docs/spec-distribution-stats.md §17.5 + §17.7.
#
# Asserts the panel renders correctly on /teams?team=X&tab=Fielding,
# that stat-strip + chip values match SQL-derived anchors across the
# three metric tabs (Catches default / Run-outs / Stumpings — the
# Stumpings tab ALWAYS renders at team grain even when count=0),
# that both URL-state keys (?dist_window_t and ?dist_metric_t_field)
# round-trip correctly, that the sparkline bar count matches SQL
# n_innings_fielded (codified per-item-chart rule), and that the
# panel renders without overflow on a 390x844 mobile viewport.
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

PANEL_SEL='section[aria-label="Per-innings team fielding distribution"]'

# Fixture — Mumbai Indians IPL scope. Same fixture as bowling test
# so SQL + endpoint stay consistent.
TEAM="Mumbai Indians"
TEAM_URL="Mumbai%20Indians"
SCOPE_URL='gender=male&team_type=club&tournament=Indian%20Premier%20League'

# WHERE fragment that mirrors _team_innings_clause(team='Mumbai Indians',
# side='fielding', filters={gender=male, team_type=club, tournament=IPL}).
# Fielding-side: innings where MI was in the field (i.team != 'MI'
# AND MI is one of the match teams).
MI_IPL_FIELD_WHERE="
i.team != '$TEAM'
AND (m.team1 = '$TEAM' OR m.team2 = '$TEAM')
AND i.super_over = 0
AND m.gender = 'male'
AND m.team_type = 'club'
AND m.event_name = 'Indian Premier League'
"

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Panel mounts; Catches-tab stat strip matches SQL"

ab open "$BASE/teams?team=$TEAM_URL&tab=Fielding&$SCOPE_URL"
settle 5

panel_present=$(ab_eval "!!document.querySelector('$PANEL_SEL')")
assert_eq "panel section exists" "true" "$panel_present"

# n_innings_fielded — count of innings MI fielded in scope.
sql_n=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_FIELD_WHERE
  GROUP BY i.id
) sub
")
dom_n=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Innings fielded\s*\n(\d+)/)?.[1] || ''")
assert_eq "Innings fielded count matches SQL" "$sql_n" "$dom_n"

# Total catches credited to MI matchplayers (substitutes excluded).
# Catch credits in fieldingcredit live in innings via delivery; filter
# by fielder being one of MI's matchplayers in that match.
# Convention 3: catches is inclusive — kind IN ('caught','caught_and_bowled').
sql_catches=$(sql "
SELECT COALESCE(SUM(c), 0) FROM (
  SELECT i.id, (
    SELECT COUNT(*) FROM fieldingcredit fc
    JOIN delivery dd ON dd.id = fc.delivery_id
    JOIN matchplayer mp ON mp.match_id = i.match_id
                        AND mp.team = '$TEAM'
                        AND mp.person_id = fc.fielder_id
    WHERE dd.innings_id = i.id
      AND fc.kind IN ('caught', 'caught_and_bowled')
      AND fc.is_substitute = 0
  ) AS c
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_FIELD_WHERE
  GROUP BY i.id
) sub
")
dom_catches=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Total\s*\n(\d+)/)?.[1] || ''")
assert_eq "Catches total matches SQL" "$sql_catches" "$dom_catches"

# Mean catches per innings — render rounds to 2dp.
sql_mean_c=$(awk "BEGIN { printf \"%.2f\", $sql_catches / $sql_n }")
dom_mean_c=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Mean \/ innings\s*\n([\d.]+)/)?.[1] || ''")
assert_eq "Mean catches / innings matches SQL" "$sql_mean_c" "$dom_mean_c"

# Substitute catches footer — only renders when > 0. API counts
# is_substitute=1 catches without a matchplayer filter (substitutes
# belong to the fielding side by construction).
sql_subs=$(sql "
SELECT COALESCE(SUM(c), 0) FROM (
  SELECT i.id, (
    SELECT COUNT(*) FROM fieldingcredit fc
    JOIN delivery dd ON dd.id = fc.delivery_id
    WHERE dd.innings_id = i.id
      AND fc.kind = 'caught'
      AND fc.is_substitute = 1
  ) AS c
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_FIELD_WHERE
  GROUP BY i.id
) sub
")
dom_panel_text=$(ab_eval "document.querySelector('$PANEL_SEL').innerText")
if [ "$sql_subs" -gt 0 ]; then
  assert_contains "Substitute catch footer renders ($sql_subs subs)" "substitute" "$dom_panel_text"
else
  case "$dom_panel_text" in
    *substitute*) bad "Substitute footer rendered with sql_subs=0 — should be hidden" ;;
    *) ok "Substitute footer hidden (sql_subs=0)" ;;
  esac
fi

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Catches chips — 4 chips with denoms == n_innings"

chip_n() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title*=\"95% CI\"]')].find(el => el.innerText.startsWith('$1'))?.title.match(/n=(\d+)/)?.[1] || ''"
}
chip_value() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title*=\"95% CI\"]')].find(el => el.innerText.startsWith('$1'))?.innerText.match(/(\d+)%/)?.[1] || ''"
}

n_eq0=$(unq "$(chip_n 'P(=0)')")
n_geq3=$(unq "$(chip_n 'P(≥3)')")
n_geq5=$(unq "$(chip_n 'P(≥5)')")
n_geq7=$(unq "$(chip_n 'P(≥7)')")
assert_eq "P(=0) chip denom == n_innings_fielded" "$sql_n" "$n_eq0"
assert_eq "P(≥3) chip denom == n_innings_fielded" "$sql_n" "$n_geq3"
assert_eq "P(≥5) chip denom == n_innings_fielded" "$sql_n" "$n_geq5"
assert_eq "P(≥7) chip denom == n_innings_fielded" "$sql_n" "$n_geq7"

# P(≥3) percentage matches SQL — render rounds to integer.
sql_n_ge3=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id, (
    SELECT COUNT(*) FROM fieldingcredit fc
    JOIN delivery dd ON dd.id = fc.delivery_id
    JOIN matchplayer mp ON mp.match_id = i.match_id
                        AND mp.team = '$TEAM'
                        AND mp.person_id = fc.fielder_id
    WHERE dd.innings_id = i.id
      AND fc.kind IN ('caught', 'caught_and_bowled')
      AND fc.is_substitute = 0
  ) AS c
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_FIELD_WHERE
  GROUP BY i.id
) sub WHERE c >= 3
")
sql_pct_ge3=$(awk "BEGIN { printf \"%d\", ($sql_n_ge3 * 100.0 / $sql_n) + 0.5 }")
dom_pct_ge3=$(unq "$(chip_value 'P(≥3)')")
assert_eq "P(≥3) percentage matches SQL" "$sql_pct_ge3" "$dom_pct_ge3"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Catches tab — chip tier-color coordination"

# Per spec §17.5: P(=0) INDIGO, P(≥3) SAGE, P(≥5) OCHRE, P(≥7) OCHRE.
chip_bg() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title]')].find(el => el.innerText.startsWith('$1'))?.style.background || ''"
}
assert_contains "P(=0) chip uses INDIGO tint"  "rgba(112, 144, 168" "$(chip_bg 'P(=0)')"
assert_contains "P(≥3) chip uses SAGE tint"    "rgba(122, 142, 106" "$(chip_bg 'P(≥3)')"
assert_contains "P(≥5) chip uses OCHRE tint"   "rgba(201, 135, 31"  "$(chip_bg 'P(≥5)')"
assert_contains "P(≥7) chip uses OCHRE tint"   "rgba(201, 135, 31"  "$(chip_bg 'P(≥7)')"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Sparkline bar count == n_innings_fielded (codified rule)"

dom_spark_n=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]').length")
assert_eq "Sparkline bar count == SQL n_innings_fielded" "$sql_n" "$dom_spark_n"

zero_h=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]')].filter(r => parseFloat(r.getAttribute('height')) <= 0).length")
assert_eq "No height=0 bars (would be invisible)" "0" "$zero_h"

# Tooltip enrichment per spec §17.5: "X catches of Y wickets — vs OPP".
first_tt=$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline a > title')?.textContent || ''")
assert_contains "First sparkline bar tooltip mentions 'catches of'" " catches of " "$first_tt"
assert_contains "First sparkline bar tooltip mentions 'wickets'" "wickets" "$first_tt"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Run-outs tab — URL state + 3 chips + partition"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Run-outs').click()" >/dev/null
settle 1
url_after=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric_t_field=run_outs" "dist_metric_t_field=run_outs" "\"$url_after\""

# Total run-outs credited to MI fielders.
sql_runouts=$(sql "
SELECT COALESCE(SUM(c), 0) FROM (
  SELECT i.id, (
    SELECT COUNT(*) FROM fieldingcredit fc
    JOIN delivery dd ON dd.id = fc.delivery_id
    JOIN matchplayer mp ON mp.match_id = i.match_id
                        AND mp.team = '$TEAM'
                        AND mp.person_id = fc.fielder_id
    WHERE dd.innings_id = i.id AND fc.kind = 'run_out'
  ) AS c
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_FIELD_WHERE
  GROUP BY i.id
) sub
")
dom_runouts=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Total\s*\n(\d+)/)?.[1] || ''")
assert_eq "Run-outs total matches SQL" "$sql_runouts" "$dom_runouts"

# 3-chip partition exhausts the sample (sum to 100%).
n_ro_eq0=$(unq "$(chip_n 'P(=0)')")
n_ro_eq1=$(unq "$(chip_n 'P(=1)')")
n_ro_geq2=$(unq "$(chip_n 'P(≥2)')")
assert_eq "Run-outs P(=0) denom == n_innings_fielded" "$sql_n" "$n_ro_eq0"
assert_eq "Run-outs P(=1) denom == n_innings_fielded" "$sql_n" "$n_ro_eq1"
assert_eq "Run-outs P(≥2) denom == n_innings_fielded" "$sql_n" "$n_ro_geq2"

# Polarity per spec §17.5 — P(=0) INDIGO, P(=1) SAGE, P(≥2) OCHRE
assert_contains "Run-outs P(=0) uses INDIGO tint" "rgba(112, 144, 168" "$(chip_bg 'P(=0)')"
assert_contains "Run-outs P(≥2) uses OCHRE tint"  "rgba(201, 135, 31"  "$(chip_bg 'P(≥2)')"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 · Stumpings tab — ALWAYS renders at team grain"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Stumpings').click()" >/dev/null
settle 1
url_st=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric_t_field=stumpings" "dist_metric_t_field=stumpings" "\"$url_st\""

# Stat strip mounts even when count=0 — per spec "honest, not hidden".
strip_present=$(ab_eval "/Innings fielded/.test(document.querySelector('$PANEL_SEL').innerText)")
assert_eq "Stumpings stat strip renders" "true" "$strip_present"

# Total stumpings credited to MI keepers.
sql_stumpings=$(sql "
SELECT COALESCE(SUM(c), 0) FROM (
  SELECT i.id, (
    SELECT COUNT(*) FROM fieldingcredit fc
    JOIN delivery dd ON dd.id = fc.delivery_id
    JOIN matchplayer mp ON mp.match_id = i.match_id
                        AND mp.team = '$TEAM'
                        AND mp.person_id = fc.fielder_id
    WHERE dd.innings_id = i.id AND fc.kind = 'stumped'
  ) AS c
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $MI_IPL_FIELD_WHERE
  GROUP BY i.id
) sub
")
dom_stumpings=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Total\s*\n(\d+)/)?.[1] || ''")
assert_eq "Stumpings total matches SQL" "$sql_stumpings" "$dom_stumpings"

# 3 chips render even if count is 0
chip_count=$(ab_eval "document.querySelectorAll('$PANEL_SEL [title*=\"95% CI\"]').length")
assert_eq "Stumpings tab renders 3 chips" "3" "$chip_count"

# Back to Catches — URL should DELETE dist_metric_t_field
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Catches').click()" >/dev/null
settle 1
url_back=$(ab_eval "window.location.href" | tr -d '"')
case "$url_back" in
  *dist_metric_t_field*) bad "Catches click DELETES dist_metric_t_field — still present in: $url_back" ;;
  *) ok "Catches click DELETES dist_metric_t_field param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 7 · Window toggle — Last 10 + sparkline rebar"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Last 10').click()" >/dev/null
settle 1
url_w=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_window_t=last_10" "dist_window_t=last_10" "\"$url_w\""

last10_bars=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]').length")
if [ "$last10_bars" -le 10 ]; then ok "Last 10 sparkline ≤ 10 bars (got $last10_bars)"
else bad "Last 10 sparkline has $last10_bars bars (expected ≤ 10)"; fi

inn_last10=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Innings fielded\s*\n(\d+)/)?.[1] || ''" | tr -d '"')
if [ "$inn_last10" -le 10 ]; then ok "Last 10 stat-strip Innings fielded ≤ 10 (got $inn_last10)"
else bad "Last 10 stat-strip Innings fielded = $inn_last10 (expected ≤ 10)"; fi

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
echo "Test 8 · Form-delta line — oxblood deltas, scope-baseline above"

has_scope_baseline=$(ab_eval "/Scope average \/ innings/.test(document.querySelector('$PANEL_SEL').innerText)")
assert_eq "Form-delta line shows scope average above" "true" "$has_scope_baseline"

oxblood_count=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL span.num')].filter(s => /^[+−][0-9]/.test(s.innerText) && s.style.color === 'rgb(122, 31, 31)').length")
non_oxblood=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL span.num')].filter(s => /^[+−][0-9]/.test(s.innerText) && s.style.color !== 'rgb(122, 31, 31)' && s.style.color !== '').length")
if [ "$oxblood_count" -gt 0 ]; then ok "Form deltas use oxblood ($oxblood_count signed values)"
else bad "Form deltas use oxblood — found 0 oxblood signed values"; fi
assert_eq "No green/red polarity on form deltas" "0" "$non_oxblood"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 9 · Mobile viewport (390x844) — panel renders without overflow"

ab set viewport 390 844
ab reload
settle 4

panel_overflow=$(ab_eval "(() => { const p = document.querySelector('$PANEL_SEL'); return p ? (p.scrollWidth > p.clientWidth + 1) : null; })()")
assert_eq "Panel has no horizontal overflow at 390px" "false" "$panel_overflow"

ab set viewport 1280 800

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 10 · League scope-comparison reference line + legend (Catches default)"

ab open "$BASE/teams?team=$TEAM_URL&tab=Fielding&$SCOPE_URL"
settle 4

API_BASE="${API_BASE:-http://localhost:8000}"
api_summary=$(curl -s "$API_BASE/api/v1/teams/$TEAM_URL/fielding/summary?$SCOPE_URL")
api_catches_sa=$(echo "$api_summary" | python3 -c "
import json, sys
r = json.load(sys.stdin)
v = r['catches']['scope_avg']
print(f'{v:.2f}' if v is not None else '')")

league_line=$(ab_eval "!!document.querySelector('$PANEL_SEL svg.wisden-dist-sparkline line[data-ref=\"league\"]')")
assert_eq "league reference line renders on Catches tab" "true" "$league_line"
league_stroke=$(ab_eval "document.querySelector('$PANEL_SEL svg.wisden-dist-sparkline line[data-ref=\"league\"]')?.getAttribute('stroke') || ''")
assert_eq "league line uses forest green (Catches)" "#3F7A4D" "$league_stroke"
legend_text=$(ab_eval "Array.from(document.querySelectorAll('$PANEL_SEL div,$PANEL_SEL span')).find(el => /league avg/.test(el.innerText) && el.children.length < 30)?.innerText || ''")
assert_contains "Catches legend includes league avg label" "league avg $api_catches_sa catches/inn" "$legend_text"

# Switch to Run-outs tab and verify the league line redraws with
# the run_outs scope_avg.
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Run-outs').click()" >/dev/null
settle 1
api_ro_sa=$(echo "$api_summary" | python3 -c "
import json, sys
r = json.load(sys.stdin)
v = r['run_outs']['scope_avg']
print(f'{v:.2f}' if v is not None else '')")
ro_legend=$(ab_eval "Array.from(document.querySelectorAll('$PANEL_SEL div,$PANEL_SEL span')).find(el => /league avg/.test(el.innerText) && el.children.length < 30)?.innerText || ''")
assert_contains "Run-outs legend includes league avg label" "league avg $api_ro_sa run-out/inn" "$ro_legend"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────"
echo "Team-fielding Distribution integration: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
