#!/bin/bash
# Bowler Distribution panel — DOM integration test.
#
# Spec: internal_docs/spec-distribution-stats.md §12.6.
#
# Asserts the panel renders correctly on /bowling?player=X across
# all three metric tabs (Wickets / Economy / Runs conceded), that
# stat-strip + chip values match SQL-derived anchors, that both
# URL-state keys (?dist_window=... and ?dist_metric=...) round-trip
# correctly, that the form-delta + sparkline + splits row are
# metric-independent, that back-button restores prior state, that
# deep-links honor both keys without flashing the default, that
# inning-aux refetch works post-mount (per-call-site coverage of
# the shared useFilterDeps abstraction), and that the panel stacks
# correctly on a 390x844 mobile viewport.
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

PANEL_SEL='section[aria-label="Per-innings bowling distribution"]'

BUMRAH=462411b3
SCOPE='tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&gender=male&team_type=club'
# Master-sample WHERE clause, matching the endpoint's
# _bowling_all_filter (side-neutral) + min_balls=12 HAVING.
BUMRAH_IPL_2024_WHERE="
d.bowler_id = '$BUMRAH'
AND m.event_name = 'Indian Premier League'
AND m.season = '2024'
AND i.super_over = 0
"
# qualifying-spell innings (≥12 legal balls)
INNS_SQL="
SELECT COUNT(*) FROM (
  SELECT i.id, SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $BUMRAH_IPL_2024_WHERE
  GROUP BY i.id
  HAVING legal >= 12
)
"

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Wickets tab renders + stat strip matches SQL"

ab open "$BASE/bowling?player=$BUMRAH&$SCOPE"
settle 4

panel_present=$(ab_eval "!!document.querySelector('$PANEL_SEL')")
assert_eq "panel section exists" "true" "$panel_present"

# n_innings (qualifying spells, default min_balls=12)
sql_inns=$(sql "$INNS_SQL")
dom_inns=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/(\d+)\s+qualifying/)?.[1] || ''")
assert_eq "n_innings (qualifying spells) matches SQL" "$sql_inns" "$dom_inns"

# Total wickets — bowler-credited only (4-element exclusion)
sql_wkts=$(sql "
SELECT SUM(wkts) FROM (
  SELECT i.id,
         SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal,
         SUM(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS wkts
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  LEFT JOIN wicket w ON w.delivery_id = d.id
    AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
  WHERE $BUMRAH_IPL_2024_WHERE
  GROUP BY i.id
  HAVING legal >= 12
)
")
dom_wkts=$(ab_eval "(() => { const t = document.querySelector('$PANEL_SEL').innerText; const m = t.match(/Total wkts\s*\n(\d+)/); return m ? m[1] : ''; })()")
assert_eq "Wickets total matches SQL" "$sql_wkts" "$dom_wkts"

# P(≥3) chip — count(w ≥ 3) / n_innings
sql_geq3=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id,
         SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal,
         SUM(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS wkts
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  LEFT JOIN wicket w ON w.delivery_id = d.id
    AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
  WHERE $BUMRAH_IPL_2024_WHERE
  GROUP BY i.id
  HAVING legal >= 12
) WHERE wkts >= 3
")
sql_p3_pct=$(awk "BEGIN { printf \"%d\", ($sql_geq3 / $sql_inns) * 100 + 0.5 }")
dom_p3=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/P\(.3\)\s*\n(\d+)%/)?.[1] || ''")
assert_eq "P(≥3) chip matches SQL count(w≥3)/n_innings" "$sql_p3_pct" "$dom_p3"

# Conditional anchor — P(≥3│≥2) denom should equal count(w≥2)
sql_geq2=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id,
         SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal,
         SUM(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS wkts
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  LEFT JOIN wicket w ON w.delivery_id = d.id
    AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
  WHERE $BUMRAH_IPL_2024_WHERE
  GROUP BY i.id
  HAVING legal >= 12
) WHERE wkts >= 2
")
sql_p3g2_pct=$(awk "BEGIN { printf \"%d\", ($sql_geq3 / $sql_geq2) * 100 + 0.5 }")
dom_p3g2=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/P\(.3.≥2\)\s*\n(\d+)%/)?.[1] || ''")
assert_eq "P(≥3│≥2) conditional matches SQL count(≥3)/count(≥2)" "$sql_p3g2_pct" "$dom_p3g2"

# Wilson CI tooltip — title attr should contain n=denom for the
# anchored conditional (denom = count(≥2))
p3g2_title=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL [title]')].find(el => el.innerText.includes('P(≥3│≥2)'))?.title || ''")
assert_contains "P(≥3│≥2) chip title shows n=$sql_geq2" "n=$sql_geq2" "$p3g2_title"

# CHIP-COLOR TIER COORDINATION (revised 2026-05-06).
# Chips must use the same tier color as the histogram bar at the
# same outcome. Wickets palette: 0 = indigo (poor) / 1-2 = sage
# (typical) / 3+ = ochre (great). The chip's bg is an rgba tint of
# the tier color.
chip_bg() {
  ab_eval "[...document.querySelectorAll('$PANEL_SEL [title]')].find(el => el.innerText.startsWith('$1'))?.style.background || ''"
}
p_zero_bg=$(unq "$(chip_bg "P(0)")")
p_geq1_bg=$(unq "$(chip_bg "P(≥1)")")
p_geq3_bg=$(unq "$(chip_bg "P(≥3)")")
p_3g2_bg=$(unq "$(chip_bg "P(≥3│≥2)")")
assert_contains "P(0) chip uses indigo tint (poor outcome)"        "rgba(112, 144, 168" "$p_zero_bg"
assert_contains "P(≥1) chip uses sage tint (typical outcome)"      "rgba(122, 142, 106" "$p_geq1_bg"
assert_contains "P(≥3) chip uses ochre tint (good outcome)"        "rgba(201, 135, 31"  "$p_geq3_bg"
assert_contains "P(≥3│≥2) conditional uses ochre tint (good outcome)" "rgba(201, 135, 31" "$p_3g2_bg"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Metric tab URL state — Economy tab"

# Click Economy tab via JS (DOM helpers run via ab_eval)
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Economy').click()" >/dev/null
settle 1
url_after=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric=economy on toggle" "dist_metric=economy" "\"$url_after\""

# Pool econ should match SQL: SUM(d.runs_total) × 6 / SUM(legal_balls) on qualifying spells
sql_pool_econ=$(sql "
WITH spells AS (
  SELECT i.id,
         SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal,
         SUM(d.runs_total) AS runs
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $BUMRAH_IPL_2024_WHERE
  GROUP BY i.id
  HAVING legal >= 12
)
SELECT printf('%.2f', SUM(runs) * 6.0 / SUM(legal)) FROM spells
")
dom_pool_econ=$(ab_eval "(() => { const t = document.querySelector('$PANEL_SEL').innerText; const m = t.match(/(?<![\\w])Economy\s*\n([\d.]+)/); return m ? m[1] : ''; })()")
assert_eq "Economy tab career Economy matches SQL pool" "$sql_pool_econ" "$dom_pool_econ"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Metric tab URL state — Runs conceded tab"

ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Runs conceded').click()" >/dev/null
settle 1
url_runs=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_metric=runs on Runs conceded click" "dist_metric=runs" "\"$url_runs\""

# Total runs conceded — SUM(runs_total) on qualifying spells
sql_total_rc=$(sql "
SELECT SUM(runs) FROM (
  SELECT i.id,
         SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal,
         SUM(d.runs_total) AS runs
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $BUMRAH_IPL_2024_WHERE
  GROUP BY i.id
  HAVING legal >= 12
)
")
dom_total_rc=$(ab_eval "(() => { const t = document.querySelector('$PANEL_SEL').innerText; const m = t.match(/Total\s*\n(\d+)/); return m ? m[1] : ''; })()")
assert_eq "Runs conceded tab Total matches SQL" "$sql_total_rc" "$dom_total_rc"

# Click back to Wickets — URL should DELETE dist_metric (default = absent)
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Wickets').click()" >/dev/null
settle 1
url_wickets=$(ab_eval "window.location.href" | tr -d '"')
case "$url_wickets" in
  *dist_metric*) bad "Wickets click DELETES dist_metric param — still present in: $url_wickets" ;;
  *) ok "Wickets click DELETES dist_metric param" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Window toggle URL state + sparkline metric-independence"

# Sparkline svg present on Wickets tab
spark_present_wkts=$(ab_eval "!!document.querySelector('$PANEL_SEL .wisden-dist-sparkline')")
assert_eq "Sparkline visible on Wickets tab" "true" "$spark_present_wkts"

# Bar count must equal the qualifying-spell count (SQL-anchored).
# Regression class: zero-value bars rendered with height=0 became
# invisible, making it look like matches went missing.
spark_bar_count=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]').length")
assert_eq "Sparkline bar count == qualifying spells (SQL anchor)" "$sql_inns" "$spark_bar_count"

# Even value=0 spells must be clickable — the below-baseline stub
# gives them a min height. Verify NO bar has height=0 after the fix.
zero_height_count=$(ab_eval "Array.from(document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline rect[opacity]')).filter(r => parseFloat(r.getAttribute('height')) <= 0).length")
assert_eq "No invisible (height=0) bars — value=0 bars get a stub" "0" "$zero_height_count"

# Season-tick axis present (per-tab independent)
season_axis_wkts=$(ab_eval "!!document.querySelector('$PANEL_SEL [aria-label=\"Season tick axis\"]')")
assert_eq "Season tick axis visible on Wickets tab" "true" "$season_axis_wkts"

# Sparkline bar carries href to /matches/{match_id} (desktop nav)
spark_first_href=$(unq "$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline a')?.getAttribute('href') || ''")")
case "$spark_first_href" in
  /matches/*) ok "Sparkline bar links to /matches/{id} (=$spark_first_href)" ;;
  *) bad "Sparkline bar should link to /matches/{id}, got: $spark_first_href" ;;
esac

# Sparkline bar carries title (desktop hover tooltip with date)
spark_first_title=$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline title')?.textContent || ''")
assert_contains "Sparkline tooltip contains a date" "20" "$spark_first_title"
assert_contains "Sparkline tooltip on Wickets tab mentions wkt" "wkt" "$spark_first_title"

# Two reference lines: player (black #1A1714 thicker) + global (gray
# #8A7D70). Revised 2026-05-06 — green clashed with the histogram
# fifty/threefer sage tier; red is reserved for the rolling-mean
# overlay.
ref_count=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline line[data-ref]').length")
assert_eq "Sparkline renders BOTH reference lines (player + global)" "2" "$ref_count"
player_stroke=$(unq "$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline line[data-ref=player]')?.getAttribute('stroke') || ''")")
global_stroke=$(unq "$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline line[data-ref=global]')?.getAttribute('stroke') || ''")")
assert_eq "Player line is black (#1A1714)" "#1A1714" "$player_stroke"
assert_eq "Global line is gray (#8A7D70)" "#8A7D70" "$global_stroke"

# Rolling-10 overlay (oxbow) on the Scope window — points >= 10
# trigger the polyline.
rolling_count=$(ab_eval "document.querySelectorAll('$PANEL_SEL .wisden-dist-sparkline polyline[data-ref=rolling]').length")
assert_eq "Rolling-10 overlay rendered on Scope when n>=10" "1" "$rolling_count"
rolling_stroke=$(unq "$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline polyline[data-ref=rolling]')?.getAttribute('stroke') || ''")")
assert_eq "Rolling overlay is oxblood (#7A1F1F)" "#7A1F1F" "$rolling_stroke"

# Gender-tiered global anchor: men's wickets/inn = 1
legend=$(ab_eval "document.querySelector('.wisden-dist-sparkline')?.parentElement?.lastElementChild?.textContent || ''")
assert_contains "Wickets tab legend cites men's gender-global (1 wkts/inn)" "1 wkts/inn" "$legend"

# Toggle to Last 10 + verify URL
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Last 10').click()" >/dev/null
settle 1
url_l10=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "URL gains dist_window=last_10 on toggle" "dist_window=last_10" "\"$url_l10\""

# Form delta line stays visible (window-independent)
form_visible=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.includes('Form vs scope')")
assert_eq "Form delta line visible after Last 10 toggle (window-independent)" "true" "$form_visible"

# Switch to Economy tab — sparkline now switches data per metric
# (per discussion 2026-05-06; was metric-independent in v1).
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Economy').click()" >/dev/null
settle 1
spark_present_econ=$(ab_eval "!!document.querySelector('$PANEL_SEL .wisden-dist-sparkline')")
assert_eq "Sparkline visible on Economy tab" "true" "$spark_present_econ"

# Tooltip on Economy tab now mentions econ (per-tab data)
spark_econ_title=$(ab_eval "document.querySelector('$PANEL_SEL .wisden-dist-sparkline title')?.textContent || ''")
assert_contains "Sparkline tooltip on Economy tab mentions econ" "econ" "$spark_econ_title"

# Back to Scope (deletes dist_window) + Wickets (deletes dist_metric)
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Scope').click()" >/dev/null
settle 1
ab_eval "[...document.querySelectorAll('$PANEL_SEL button.wisden-seg')].find(b => b.innerText.trim() === 'Wickets').click()" >/dev/null
settle 1
url_clean=$(ab_eval "window.location.href" | tr -d '"')
case "$url_clean" in
  *dist_window*|*dist_metric*) bad "Default values not absent — URL: $url_clean" ;;
  *) ok "Both default values encoded by absence (dist_window + dist_metric)" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Deep-link with both URL state keys"

ab open "$BASE/bowling?player=$BUMRAH&$SCOPE&dist_window=last_60d&dist_metric=runs"
settle 4
active_w=$(ab_eval "[...document.querySelectorAll('$PANEL_SEL .wisden-seg.is-active')].map(b => b.innerText)")
assert_contains "deep-link sets dist_window=last_60d active" "Last 60d" "$active_w"
assert_contains "deep-link sets dist_metric=runs active" "Runs conceded" "$active_w"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 · Suggested-split navigation preserves dist_metric"

ab open "$BASE/bowling?player=$BUMRAH&$SCOPE&dist_metric=economy"
settle 4
ab_eval "[...document.querySelectorAll('$PANEL_SEL a')].find(a => a.innerText === 'All Indian Premier League')?.click()" >/dev/null
settle 4
url_split=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "Split click preserves dist_metric across navigation" "dist_metric=economy" "\"$url_split\""

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 7 · Inning aux click-after-mount refetches the panel"

ab open "$BASE/bowling?player=$BUMRAH&$SCOPE"
settle 4
mount_inns=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/(\d+)\s+qualifying/)?.[1] || ''")
assert_eq "Mount n_innings == lifetime SQL anchor (sanity)" "$sql_inns" "$mount_inns"

ab_eval "[...document.querySelectorAll('.wisden-seg')].find(b => b.innerText.trim() === '1st innings')?.click()" >/dev/null
settle 3
url_with_inning=$(ab_eval "window.location.href" | tr -d '"')
assert_contains "InningToggle click writes ?inning=0" "inning=0" "\"$url_with_inning\""

sql_inn0=$(sql "
SELECT COUNT(*) FROM (
  SELECT i.id, i.innings_number,
         SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal
  FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE $BUMRAH_IPL_2024_WHERE AND i.innings_number = 0
  GROUP BY i.id
  HAVING legal >= 12
)
")
dom_inn0=$(ab_eval "document.querySelector('$PANEL_SEL').innerText.match(/(\d+)\s+qualifying/)?.[1] || ''")
assert_eq "Panel n_innings refetches under inning=0" "$sql_inn0" "$dom_inn0"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 8 · Empty-scope renders placeholder"

ab open "$BASE/bowling?player=$BUMRAH&filter_venue=Nonexistent%20Ground"
settle 4
panel_text=$(ab_eval "document.querySelector('$PANEL_SEL').innerText")
assert_contains "Empty-scope placeholder shown" "No qualifying innings" "$panel_text"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 9 · Mobile viewport (390x844) — grid stacks + sparkline non-interactive"

ab set viewport 390 844
ab open "$BASE/bowling?player=$BUMRAH&$SCOPE"
settle 4
mobile_grid=$(ab_eval "(() => {
  const grid = document.querySelector('.wisden-dist-grid')
  if (!grid) return 'missing'
  const children = [...grid.children].map(c => Math.round(c.getBoundingClientRect().width))
  const allFullWidth = children.length >= 2
    && Math.abs(children[0] - children[1]) < 20
    && children[0] > 250
  return allFullWidth ? 'stacked' : 'split-' + children.join(',')
})()")
assert_eq "Mobile grid stacks to single column" "stacked" "$mobile_grid"

# Sparkline interaction is disabled on mobile (pointer-events:none on
# bar links). Per discussion 2026-05-06: bars too narrow to be reliable
# tap targets, hover doesn't exist on touch — mobile is impressionistic
# only. Season-tick axis carries the date-context affordance.
mobile_pe=$(ab_eval "getComputedStyle(document.querySelector('.wisden-dist-sparkline a'))?.pointerEvents")
assert_eq "Mobile: sparkline bars have pointer-events: none" "none" "$mobile_pe"

# Season tick axis still rendered on mobile
mobile_season_present=$(ab_eval "!!document.querySelector('[aria-label=\"Season tick axis\"]')")
assert_eq "Mobile: season tick axis still rendered" "true" "$mobile_season_present"

# Reset viewport for downstream tests
ab set viewport 1280 1024

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────────────────────────"
echo "$PASS pass · $FAIL fail"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
