#!/bin/bash
# Fielder Distribution panel — DOM integration test.
#
# Spec: internal_docs/spec-distribution-stats.md §14.6.
#
# Asserts the panel renders correctly on /fielding?player=X across
# Catches / Run-outs / Stumpings tabs, that stat-strip + chip values
# match SQL-derived anchors, that the conditional Stumpings tab
# appears iff innings_kept > 0, that both URL-state keys
# (?dist_window_f=... and ?dist_metric_f=...) round-trip correctly,
# that the sparkline bar count matches SQL (codified per-item-chart
# rule), and that the panel renders without overflow on a 390x844
# mobile viewport.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL"
# — every numeric expected value derives from cricket.db at runtime.
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

PANEL_SEL='section[aria-label="Per-match fielding distribution"]'

# Fixtures:
#   Dhoni  (4a8a2e3b)  — keeper, IPL career, large sample
#   Kohli  (ba607b88)  — non-keeper outfielder
DHONI=4a8a2e3b
KOHLI=ba607b88
SCOPE='tournament=Indian%20Premier%20League&gender=male&team_type=club'

# Match-level scope clause for SQL anchors. Per-match grain — drop
# the innings join. Side-neutral team filter not exercised here.
DHONI_IPL_WHERE="
mp.person_id = '$DHONI'
AND m.event_name = 'Indian Premier League'
"

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Catches tab renders + stat strip matches SQL"

ab open "$BASE/fielding?player=$DHONI&$SCOPE"
settle 4

panel_present=$(ab_eval "!!document.querySelector('$PANEL_SEL')")
assert_eq "panel section exists" "true" "$panel_present"

# n_matches — distinct matches Dhoni played in IPL
sql_matches=$(sql "
SELECT COUNT(DISTINCT mp.match_id)
FROM matchplayer mp
JOIN match m ON m.id = mp.match_id
WHERE $DHONI_IPL_WHERE
")
dom_matches=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Matches\s*\n(\d+)/)?.[1] || ''")
assert_eq "n_matches matches SQL" "$sql_matches" "$dom_matches"

# Total catches — non-substitute, scope-bound
sql_catches=$(sql "
SELECT COUNT(*)
FROM fieldingcredit fc
JOIN delivery d ON d.id = fc.delivery_id
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
JOIN matchplayer mp ON mp.match_id = m.id AND mp.person_id = fc.fielder_id
WHERE fc.fielder_id = '$DHONI'
  AND fc.kind = 'caught'
  AND COALESCE(fc.is_substitute, 0) = 0
  AND m.event_name = 'Indian Premier League'
")
dom_catches=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Total catches\s*\n(\d+)/)?.[1] || ''")
assert_eq "Total catches matches SQL" "$sql_catches" "$dom_catches"

# Catches tab shows Mean / match — Std without a centre is incoherent
# (revised 2026-05-07; uniform schema across all three tabs).
sql_mean=$(awk "BEGIN { printf \"%.2f\", $sql_catches / $sql_matches }")
dom_mean=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Mean\s\/\smatch\s*\n([\d.]+)/)?.[1] || ''")
assert_eq "Catches tab shows Mean / match (matches SQL)" "$sql_mean" "$dom_mean"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Histogram has exactly 3 bars (fixed-bin contract)"

# semiotic renders bars on a canvas with aria-label "bar chart, N bars"
hist_aria=$(ab_eval "document.querySelector('$PANEL_SEL canvas[aria-label*=\"bar chart\"]')?.getAttribute('aria-label') || ''")
assert_contains "Histogram canvas reports 3 bars" "3 bars" "$hist_aria"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Three milestone chips partition the match sample"

# Sum of chip n's must equal n_matches (P=0 + P=1 + P≥2 = 1.0).
# Chip titles carry n=denom — denom is constant across the three
# (all share n_matches). Pull all three and verify.
chip_n() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title*=\"95% CI\"]')].find(el => el.innerText.startsWith('$1'))?.title.match(/n=(\d+)/)?.[1] || ''"
}
n_zero=$(unq "$(chip_n 'P(=0)')")
n_one=$(unq "$(chip_n 'P(=1)')")
n_geq2=$(unq "$(chip_n 'P(≥2)')")
assert_eq "P(=0) chip denom == n_matches" "$sql_matches" "$n_zero"
assert_eq "P(=1) chip denom == n_matches" "$sql_matches" "$n_one"
assert_eq "P(≥2) chip denom == n_matches" "$sql_matches" "$n_geq2"

# CHIP-COLOR TIER COORDINATION
# 0 = indigo (poor) / 1 = sage (typical) / ≥2 = ochre (impactful).
chip_bg() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title]')].find(el => el.innerText.startsWith('$1'))?.style.background || ''"
}
p_zero_bg=$(unq "$(chip_bg 'P(=0)')")
p_one_bg=$(unq "$(chip_bg 'P(=1)')")
p_geq2_bg=$(unq "$(chip_bg 'P(≥2)')")
assert_contains "P(=0) chip uses indigo tint (poor outcome)"  "rgba(112, 144, 168" "$p_zero_bg"
assert_contains "P(=1) chip uses sage tint (typical outcome)" "rgba(122, 142, 106" "$p_one_bg"
assert_contains "P(≥2) chip uses ochre tint (impactful)"      "rgba(201, 135, 31"  "$p_geq2_bg"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Sparkline bar count == n_matches (codified per-item-chart rule)"

dom_spark_n=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]').length")
assert_eq "Sparkline bar count == SQL n_matches" "$sql_matches" "$dom_spark_n"

# No height=0 bars (would be invisible) — every match should
# have a clickable footprint via the 4px stub zone.
zero_h=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]')].filter(r => parseFloat(r.getAttribute('height')) <= 0).length")
assert_eq "No height=0 bars (would be invisible)" "0" "$zero_h"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Run-outs tab — URL state + chip schema"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Run-outs').click()" >/dev/null
settle 1
url_after=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric_f=run_outs on toggle" "dist_metric_f=run_outs" "\"$url_after\""

# Run-outs tab also shows Mean / match (uniform schema)
has_mean_ro=$(ab_eval "!!document.querySelector('$PANEL_SEL').innerText.match(/Mean\s\/\smatch/)")
assert_eq "Run-outs tab shows Mean / match" "true" "$has_mean_ro"

# Total run-outs matches SQL
sql_runouts=$(sql "
SELECT COUNT(*)
FROM fieldingcredit fc
JOIN delivery d ON d.id = fc.delivery_id
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE fc.fielder_id = '$DHONI'
  AND fc.kind = 'run_out'
  AND COALESCE(fc.is_substitute, 0) = 0
  AND m.event_name = 'Indian Premier League'
")
dom_runouts=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Total run-outs\s*\n(\d+)/)?.[1] || ''")
assert_eq "Total run-outs matches SQL" "$sql_runouts" "$dom_runouts"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 · Stumpings tab (keeper-only) — visibility + Mean shown"

# Click Stumpings tab — Dhoni is a keeper, tab should exist
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Stumpings').click()" >/dev/null
settle 1
url_st=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric_f=stumpings" "dist_metric_f=stumpings" "\"$url_st\""

# Mean / match IS shown on stumpings tab (per spec §14.2.4)
has_mean=$(ab_eval "!!document.querySelector('$PANEL_SEL').innerText.match(/Mean\s\/\smatch/)")
assert_eq "Stumpings tab shows Mean / match" "true" "$has_mean"

# Total stumpings matches SQL
sql_stumpings=$(sql "
SELECT COUNT(*)
FROM fieldingcredit fc
JOIN delivery d ON d.id = fc.delivery_id
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE fc.fielder_id = '$DHONI'
  AND fc.kind = 'stumped'
  AND m.event_name = 'Indian Premier League'
")
dom_stumpings=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/Total stumpings\s*\n(\d+)/)?.[1] || ''")
assert_eq "Total stumpings matches SQL" "$sql_stumpings" "$dom_stumpings"

# Back to Catches — URL should DELETE dist_metric_f
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Catches').click()" >/dev/null
settle 1
url_back=$(ab_eval "window.location.href" | tr -d '"')
case "$url_back" in
  *dist_metric_f*) bad "Catches click DELETES dist_metric_f — still present in: $url_back" ;;
  *) ok "Catches click DELETES dist_metric_f param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 7 · Window toggle URL state — Last 10 + sparkline rebar"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Last 10').click()" >/dev/null
settle 1
url_w=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_window_f=last_10" "dist_window_f=last_10" "\"$url_w\""

# Sparkline now ≤ 10 bars
last10_bars=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]').length")
if [ "$last10_bars" -le 10 ]; then ok "Last 10 sparkline ≤ 10 bars (got $last10_bars)"
else bad "Last 10 sparkline has $last10_bars bars (expected ≤ 10)"; fi

# Back to "At scope" — URL should DELETE dist_window_f. The pill was
# renamed "Scope" → "At scope".
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'At scope').click()" >/dev/null
settle 1
url_w2=$(ab_eval "window.location.href" | tr -d '"')
case "$url_w2" in
  *dist_window_f*) bad "'At scope' click DELETES dist_window_f — still present in: $url_w2" ;;
  *) ok "'At scope' click DELETES dist_window_f param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 8 · Non-keeper player — Stumpings tab absent"

ab open "$BASE/fielding?player=$KOHLI"
settle 4

# Stumpings tab should not be in the DOM at all
stumpings_btn=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Stumpings') ? 'present' : 'absent'" | tr -d '"')
assert_eq "Stumpings tab absent for non-keeper Kohli" "absent" "$stumpings_btn"

# Catches and Run-outs tabs DO render
catches_btn=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Catches') ? 'present' : 'absent'" | tr -d '"')
assert_eq "Catches tab present for non-keeper" "present" "$catches_btn"
runouts_btn=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Run-outs') ? 'present' : 'absent'" | tr -d '"')
assert_eq "Run-outs tab present for non-keeper" "present" "$runouts_btn"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 9 · Mobile viewport (390x844) — panel renders without overflow"

ab set viewport 390 844
ab reload
settle 3

panel_overflow=$(ab_eval "(() => { const p = document.querySelector('$PANEL_SEL'); return p ? (p.scrollWidth > p.clientWidth + 1) : null; })()")
assert_eq "Panel has no horizontal overflow at 390px" "false" "$panel_overflow"

# Reset viewport
ab set viewport 1280 800

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────"
echo "Fielder Distribution integration: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
