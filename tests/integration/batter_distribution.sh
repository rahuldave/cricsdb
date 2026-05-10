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
echo "Test 8 · Sparkline tier colors + dual ref lines + rolling overlay (Runs tab)"

ab open "$BASE/batting?player=$KOHLI&gender=male&tournament=Indian%20Premier%20League"
settle 4

# Tier coloring: bars colored by milestone tier — collapsed to 3-tier
# 2026-05-06 (failure=indigo / building=slate-tan / impact=sage).
# At least 2 unique fills should be visible (most players span 2+ tiers).
unique_colors=$(ab_eval "[...new Set(Array.from(document.querySelectorAll('.wisden-dist-sparkline rect')).map(r => r.getAttribute('fill')))].length")
case "$unique_colors" in
  2|3) ok "Runs sparkline tier-colored ($unique_colors unique colors)" ;;
  *) bad "Runs sparkline expected 2 or 3 tier colors, got: $unique_colors" ;;
esac
# Failure tier indigo (NOT red) — red reserved for rolling overlay
fills=$(ab_eval "JSON.stringify([...new Set(Array.from(document.querySelectorAll('.wisden-dist-sparkline rect')).map(r => r.getAttribute('fill')))].sort())")
case "$fills" in
  *'#7090A8'*) ok "Runs sparkline includes indigo (failure tier)" ;;
  *) bad "Runs sparkline missing indigo tier (failure should be #7090A8) — got: $fills" ;;
esac
case "$fills" in
  *'#A03B3B'*) bad "Runs sparkline includes red — red is reserved for rolling overlay (palette regression)" ;;
  *) ok "Runs sparkline has NO red bars (red reserved for oxbow)" ;;
esac

# CHIP-COLOR TIER COORDINATION — chip backgrounds must match the
# histogram tier of their threshold (revised 2026-05-06).
chip_bg() {
  ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] [title]')].find(el => el.innerText.startsWith('$1'))?.style.background || ''"
}
p_le10_bg=$(unq "$(chip_bg "P(≤10)")")
p_geq30_bg=$(unq "$(chip_bg "P(≥30)")")
p_geq50_bg=$(unq "$(chip_bg "P(≥50)")")
p_geq100_bg=$(unq "$(chip_bg "P(≥100)")")
p_50g30_bg=$(unq "$(chip_bg "P(≥50│≥30)")")
assert_contains "P(≤10) chip uses indigo tint (poor)"            "rgba(112, 144, 168" "$p_le10_bg"
assert_contains "P(≥30) chip uses sage tint (typical)"           "rgba(122, 142, 106" "$p_geq30_bg"
assert_contains "P(≥50) chip uses ochre tint (impact)"           "rgba(201, 135, 31"  "$p_geq50_bg"
assert_contains "P(≥100) chip uses ochre tint (impact)"          "rgba(201, 135, 31"  "$p_geq100_bg"
assert_contains "P(≥50│≥30) conditional uses ochre tint (impact)" "rgba(201, 135, 31" "$p_50g30_bg"

# Reference lines: player black + global gray
player_stroke=$(unq "$(ab_eval "document.querySelector('.wisden-dist-sparkline line[data-ref=player]')?.getAttribute('stroke') || ''")")
global_stroke=$(unq "$(ab_eval "document.querySelector('.wisden-dist-sparkline line[data-ref=global]')?.getAttribute('stroke') || ''")")
assert_eq "Player line is black (#1A1714)" "#1A1714" "$player_stroke"
assert_eq "Global line is gray (#8A7D70)" "#8A7D70" "$global_stroke"

# Bar count must equal SQL-anchored innings count (catches the
# zero-height bar regression — ducks rendered with height=0 used
# to vanish entirely). The current scope is Kohli/men/IPL (no
# season filter), broader than the Test 1 scope.
sql_kohli_men_ipl_inns=$(sql "
SELECT COUNT(DISTINCT i.id)
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.batter_id = '$KOHLI'
  AND d.extras_wides = 0 AND d.extras_noballs = 0
  AND m.gender = 'male'
  AND m.event_name = 'Indian Premier League'
  AND i.super_over = 0
")
spark_bar_count=$(ab_eval "document.querySelectorAll('.wisden-dist-sparkline rect[opacity]').length")
assert_eq "Sparkline bar count == lifetime n_innings (SQL anchor)" "$sql_kohli_men_ipl_inns" "$spark_bar_count"

# No invisible bars — every value=0 (duck) bar gets the stub.
zero_h=$(ab_eval "Array.from(document.querySelectorAll('.wisden-dist-sparkline rect[opacity]')).filter(r => parseFloat(r.getAttribute('height')) <= 0).length")
assert_eq "No height=0 sparkline bars — ducks get a stub" "0" "$zero_h"

# Rolling-10 overlay on Scope window
rolling_count=$(ab_eval "document.querySelectorAll('.wisden-dist-sparkline polyline[data-ref=rolling]').length")
assert_eq "Rolling-10 overlay rendered on Scope window" "1" "$rolling_count"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 9 · Strike Rate metric tab"

# Click SR tab
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button.wisden-seg')].find(b => b.innerText.trim() === 'Strike Rate')?.click()" >/dev/null
settle 1
url_sr=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric=sr on SR tab click" "dist_metric=sr" "\"$url_sr\""

# SR tab now has its OWN histogram (post 2026-05-06 — was hidden in
# v1; re-added with 3-tier coloring matching the SR sparkline).
sr_hist_visible=$(ab_eval "!!document.querySelector('.wisden-dist-grid')")
assert_eq "SR-specific histogram rendered on SR tab" "true" "$sr_hist_visible"

# Sparkline rendered with SR-specific tooltip
sr_tip=$(ab_eval "document.querySelector('.wisden-dist-sparkline title')?.textContent || ''")
assert_contains "SR tab tooltip mentions SR" "SR" "$sr_tip"

# SR stat strip computed client-side: "Career SR" label visible
sr_strip_visible=$(ab_eval "document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText.includes('Career SR')")
assert_eq "SR stat strip visible (client-side computed)" "true" "$sr_strip_visible"

# Click back to Runs — URL deletes dist_metric
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button.wisden-seg')].find(b => b.innerText.trim() === 'Runs')?.click()" >/dev/null
settle 1
url_runs=$(ab_eval "window.location.href" | tr -d '"')
case "$url_runs" in
  *dist_metric*) bad "Runs click should DELETE dist_metric param: $url_runs" ;;
  *) ok "Runs (default) click DELETES dist_metric param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 10 · Wilson-CI tooltips on milestone chips (§15 retrofit)"
# Per spec §15 / §11.3: every milestone ProbRecord ships
# {value, num, denom, ci_low, ci_high}. The chip's `title` attr
# carries `95% CI [lo%–hi%], n=denom`. Anchor expected text
# against the API at runtime — never re-derive Wilson in shell.

# Re-open with Runs tab default + Lifetime window for a stable scope
# (test 9 may have left the panel on the SR tab).
ab open "$BASE/batting?player=$KOHLI&$SCOPE"
settle 4

# Pull raw API floats — formatting happens in JS via ab_eval so the
# expected text and the rendered DOM tooltip both pass through V8's
# Number.toFixed. Anything else (Python %.1f, ROUND_HALF_UP, etc.)
# drifts on .5-boundary binary-float values where the IEEE 754
# representation isn't actually the printed decimal — JS reads the
# binary truth.
api_raw=$(curl -s "http://localhost:8000/api/v1/batters/$KOHLI/distribution?$SCOPE" \
  | python3 -c "
import json, sys
m = json.load(sys.stdin)['lifetime']['milestones']
for k, label in [('p_failure_10','P(≤10)'), ('p_30_plus','P(≥30)'),
                 ('p_50_plus','P(≥50)'), ('p_100_plus','P(≥100)'),
                 ('p_50_given_30','P(≥50│≥30)'), ('p_70_given_50','P(≥70│≥50)')]:
    pr = m[k]
    if pr['denom'] > 0:
        # tab-separated: label, ci_low_raw, ci_high_raw, denom
        print(f'{label}\t{pr[\"ci_low\"]}\t{pr[\"ci_high\"]}\t{pr[\"denom\"]}')
    else:
        print(f'{label}\t\t\t0')
")

while IFS=$'\t' read -r label ci_low ci_high denom; do
  [ -z "$label" ] && continue
  if [ "$denom" = "0" ]; then
    expected="n=0 (no qualifying innings)"
  else
    fmt_lo=$(unq "$(ab_eval "(${ci_low} * 100).toFixed(1)")")
    fmt_hi=$(unq "$(ab_eval "(${ci_high} * 100).toFixed(1)")")
    expected="95% CI [${fmt_lo}%–${fmt_hi}%], n=${denom}"
  fi
  dom_title=$(unq "$(ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] [title]')].find(el => el.innerText.startsWith('$label'))?.getAttribute('title') || ''")")
  assert_eq "$label tooltip = API Wilson CI" "$expected" "$dom_title"
done <<< "$api_raw"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 11 · Server SR (/summary.strike_rate) == client-derived Career SR (§6.2)"
# Phase-2 audit (project_invariants_audit §6.2): the batter
# /distribution endpoint doesn't return strike_rate, so the SR-tab
# computes it client-side from runs.total * 100 / balls_total. The
# /summary endpoint has its OWN strike_rate computation. If the two
# code paths ever diverge in their predicates (legal-balls,
# super_over, …), the player page would silently show two different
# SR numbers. Lock down the agreement.

ab open "$BASE/batting?player=$KOHLI&$SCOPE"
settle 4
# Click into the SR tab so the Career SR strip is visible
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button')].find(b => b.innerText.trim() === 'Strike Rate')?.click()" >/dev/null
settle 1

# Server SR — fetch from /summary
api_summary_sr=$(curl -s "http://localhost:8000/api/v1/batters/$KOHLI/summary?$SCOPE" \
  | python3 -c "import json, sys; print(json.load(sys.stdin)['strike_rate'])")
# Server runs + balls — fetch from /distribution
api_dist_runs=$(curl -s "http://localhost:8000/api/v1/batters/$KOHLI/distribution?$SCOPE" \
  | python3 -c "import json, sys; d=json.load(sys.stdin)['lifetime']['runs']; print(d['total'])")
api_dist_balls=$(curl -s "http://localhost:8000/api/v1/batters/$KOHLI/distribution?$SCOPE" \
  | python3 -c "import json, sys; d=json.load(sys.stdin)['lifetime']['runs']; print(d['balls_total'])")

# Cross-endpoint sanity (§6.2): /summary.strike_rate should equal
# /distribution.runs.total * 100 / balls_total to within 1 dp.
sr_from_dist=$(python3 -c "print(round($api_dist_runs * 100 / $api_dist_balls, 1))")
assert_eq "Server /summary.strike_rate == /distribution.runs.total*100/balls_total" \
  "$api_summary_sr" "$sr_from_dist"

# DOM "Career SR" value — client-rendered (.toFixed(2)). Match
# expected via the same JS path so the boundary-rounding agrees.
expected_sr_2dp=$(unq "$(ab_eval "($api_dist_runs * 100 / $api_dist_balls).toFixed(2)")")
dom_career_sr=$(unq "$(ab_eval "(() => { const t = document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText; const m = t.match(/Career SR\s*\n([\d.]+)/); return m ? m[1] : ''; })()")")
assert_eq "DOM Career SR == JS-formatted (runs*100/balls).toFixed(2)" \
  "$expected_sr_2dp" "$dom_career_sr"

# Click back to Runs tab to leave the page in default state
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button.wisden-seg')].find(b => b.innerText.trim() === 'Runs')?.click()" >/dev/null
settle 1

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 12 · /distribution.lifetime.runs.strike_rate present + matches DOM (§4.1+§4.5)"
# Audit §4.1+§4.5 fix: SR is now server-side on /distribution
# (lifetime.runs.strike_rate + per-observation strike_rate).
# Assert the new fields exist AND DOM reads them (not the old
# client recomputation).

api_dist=$(curl -s "http://localhost:8000/api/v1/batters/$KOHLI/distribution?$SCOPE")

# Server now exposes strike_rate on lifetime.runs — verify presence + value
api_lifetime_sr=$(echo "$api_dist" | python3 -c "
import json, sys
sr = json.load(sys.stdin)['lifetime']['runs'].get('strike_rate')
print(sr if sr is not None else 'MISSING')")
case "$api_lifetime_sr" in
  MISSING) bad "lifetime.runs.strike_rate field present" ;;
  *)       ok "lifetime.runs.strike_rate field present (=$api_lifetime_sr)" ;;
esac

# Identity: lifetime.runs.strike_rate must equal runs.total*100/balls_total
expected_lifetime_sr=$(echo "$api_dist" | python3 -c "
import json, sys
d = json.load(sys.stdin)['lifetime']['runs']
print(round(d['total'] * 100 / d['balls_total'], 2))")
assert_eq "lifetime.runs.strike_rate matches runs.total*100/balls_total" \
  "$expected_lifetime_sr" "$api_lifetime_sr"

# Server now exposes strike_rate per observation — verify shape
api_obs_sr_present=$(echo "$api_dist" | python3 -c "
import json, sys
obs = json.load(sys.stdin)['lifetime']['runs']['observations']
print('all_have_field' if all('strike_rate' in o for o in obs) else 'MISSING_ON_SOME')")
assert_eq "every observation has strike_rate field" "all_have_field" "$api_obs_sr_present"

# Per-observation identity: o.strike_rate ≈ o.runs * 100 / o.balls
api_obs_sr_correct=$(echo "$api_dist" | python3 -c "
import json, sys
obs = json.load(sys.stdin)['lifetime']['runs']['observations']
ok = True
for o in obs:
    if o['balls'] == 0:
        if o['strike_rate'] is not None: ok = False; break
    else:
        expected = round(o['runs'] * 100 / o['balls'], 2)
        if abs((o['strike_rate'] or 0) - expected) > 1e-9: ok = False; break
print('all_correct' if ok else 'MISMATCH')")
assert_eq "per-observation strike_rate matches runs*100/balls" "all_correct" "$api_obs_sr_correct"

# DOM Career SR should match the server's new lifetime.runs.strike_rate.
# Already covered by Test 11 (which compares to JS-formatted compute) but
# this is the structural lock — DOM is reading the new field directly.
ab open "$BASE/batting?player=$KOHLI&$SCOPE"
settle 4
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button')].find(b => b.innerText.trim() === 'Strike Rate')?.click()" >/dev/null
settle 1
expected_sr_2dp=$(unq "$(ab_eval "(${api_lifetime_sr}).toFixed(2)")")
dom_career_sr=$(unq "$(ab_eval "(() => { const t = document.querySelector('section[aria-label=\"Per-innings runs distribution\"]').innerText; const m = t.match(/Career SR\s*\n([\d.]+)/); return m ? m[1] : ''; })()")")
assert_eq "DOM Career SR == server lifetime.runs.strike_rate (2dp)" \
  "$expected_sr_2dp" "$dom_career_sr"

# Click back to Runs tab
ab_eval "[...document.querySelectorAll('section[aria-label=\"Per-innings runs distribution\"] button.wisden-seg')].find(b => b.innerText.trim() === 'Runs')?.click()" >/dev/null
settle 1

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────────────────────────"
echo "$PASS pass · $FAIL fail"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
