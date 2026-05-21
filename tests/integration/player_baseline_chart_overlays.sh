#!/bin/bash
# Player baseline — chart-overlay integration test.
#
# Spec: internal_docs/spec-player-baseline-parity.md §5 + §6.3.
#
# Phase C+D+E of the spec wire scope-baseline reference lines onto
# every by-season LineChart on /batting, /bowling, /fielding. The
# overlay is sourced from /api/v1/scope/averages/players/<disc>/
# by-season (a position-mix / over-mix / keeper-binary cohort), and
# the legend names the reference line "base" (Q5 — distinct from the
# team-side "avg" wording).
#
# Asserts per discipline tab:
#   - LineChart renders (not BarChart) when player has season data
#   - Legend contains both the player name (primary) and "base" (ref)
#   - Reference-line segment count matches non-null cohort seasons
#     from the API endpoint (chip ↔ chart symmetry rule)
#   - Cohort shifts when narrowing on a scope_key axis (season_from)
#
# Per CLAUDE.md: integration tests must self-anchor; sql() pulls
# from cricket.db at runtime, but the chart-overlay assertions
# anchor against /scope/averages/.../by-season directly because the
# API endpoint is the authoritative cohort baseline (the dual-query
# is covered by sanity tests).
#
# Phase C lands /batting. Phase D extends to /bowling; Phase E to
# /fielding. The structure mirrors that order — each discipline
# gets its own block; the helpers (chart_legend_texts,
# cohort_nonnull_count) are reused.
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
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
  else bad "$label — '$needle' not found in: $au"; fi
}

# Pull the joined text of every legend / chart series label currently
# rendered on the page. Semiotic renders legend items as <text>
# inside a <g class="legend"> group; the wrapping LineChart also
# annotates the chart container with the title.
chart_legend_texts() {
  ab_eval "
    Array.from(document.querySelectorAll('text'))
      .map(t => t.textContent?.trim())
      .filter(Boolean)
      .join('|')
  "
}

# Count rows in a cohort by-season response whose given metric field
# is non-null. (Backend Q4: rows under threshold null out per metric.)
cohort_nonnull_count() {
  local url="$1" field="$2"
  curl -s "$url" | python3 -c "
import json, sys
d = json.load(sys.stdin)
rows = d.get('by_season', [])
print(sum(1 for r in rows if r.get('$field') is not None))
"
}

# Single representative cohort value (first row's metric) for the
# shift-on-narrow assertion. Picks a deterministic season.
cohort_metric_at_season() {
  local url="$1" field="$2" season="$3"
  curl -s "$url" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d.get('by_season', []):
    if r.get('season') == '$season':
        print(r.get('$field'))
        sys.exit(0)
print('MISSING')
"
}

# ───────────────────────────────────────────────────────────────────
# /batting — Phase C (shipped)
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /batting — Kohli IPL By Season ==="
KOHLI=ba607b88
SCOPE='gender=male&team_type=club&tournament=Indian+Premier+League'
SCOPE_URL='gender=male&team_type=club&tournament=Indian%20Premier%20League'

ab open "$BASE/batting?player=$KOHLI&$SCOPE_URL&tab=By%20Season"
sleep 3

# Test 1 — Legend names both series (primary = player name, ref = base).
legend=$(chart_legend_texts)
assert_contains "/batting By Season: legend names player as primary" "V Kohli" "$legend"
assert_contains "/batting By Season: legend names cohort as 'base'" "base" "$legend"

# Test 2 — Chart contains "Runs by Season" and "Strike Rate by Season"
# titles (the swap from BarChart → LineChart preserves the titles).
titles=$(ab_eval "
  Array.from(document.querySelectorAll('h2,h3,h4'))
    .map(e => e.textContent?.trim())
    .filter(Boolean)
    .join('|')
")
assert_contains "/batting By Season: 'Runs by Season' chart title present" "Runs by Season" "$titles"
assert_contains "/batting By Season: 'Strike Rate by Season' chart title present" "Strike Rate by Season" "$titles"

# Test 3 — Cohort baseline has enough rows for a meaningful chart
# AND the rendered chart actually has the bi-series (primary + ref)
# wiring. Semiotic v3 draws line data into <canvas> overlays so DOM
# <path> probes don't apply; instead we count `.stream-xy-frame`
# containers, the canvas-per-frame count (2 = primary + reference),
# and the per-frame legend-item text count (must include both
# series labels).
cohort_url="$API/api/v1/scope/averages/players/batting/by-season?person_id=$KOHLI&$SCOPE"
sr_nonnull=$(cohort_nonnull_count "$cohort_url" "strike_rate")
if [ "$sr_nonnull" -ge 5 ]; then
  ok "/batting cohort by-season has ≥5 SR rows (=$sr_nonnull)"
else
  bad "/batting cohort by-season SR rows too few (=$sr_nonnull)"
fi
# Two LineCharts (Runs + SR), each with two series → 2 frames,
# 2 canvases per frame, both legend items present.
# ab_eval --json returns the raw JS value as JSON. Easier than
# trying to undo string-encoding in shell.
agent-browser eval --json "(() => {
  const frames = Array.from(document.querySelectorAll('.stream-xy-frame'));
  return {
    n_frames: frames.length,
    canvas_counts: frames.map(f => f.querySelectorAll('canvas').length),
    legend_texts: frames.map(f =>
      Array.from(f.querySelectorAll('g.legend-item text'))
        .map(t => t.textContent && t.textContent.trim())
    ),
  };
})()" > /tmp/chart_probe.json 2>/dev/null
n_frames=$(python3 -c "import json;print(json.load(open('/tmp/chart_probe.json'))['data']['result']['n_frames'])")
assert_eq "/batting By Season: 2 stream-xy-frame containers (Runs + SR)" "2" "$n_frames"
# spec-rate-vs-volume-audit C1: Runs by Season is a volume chart →
# overlay dropped. SR by Season is a rate → overlay kept. Test now
# asserts asymmetric series counts: SR chart has both series, Runs
# chart has player only.
sr_has_both=$(python3 -c "
import json
d = json.load(open('/tmp/chart_probe.json'))['data']['result']
# At least one frame (SR chart) must carry both series.
ok = any('V Kohli' in lbls and 'base' in lbls for lbls in d['legend_texts'])
print('yes' if ok else 'no')
")
assert_eq "/batting By Season: SR chart legend names both series" "yes" "$sr_has_both"
runs_no_base=$(python3 -c "
import json
d = json.load(open('/tmp/chart_probe.json'))['data']['result']
# At least one frame (Runs chart) must NOT carry 'base'.
ok = any('base' not in lbls for lbls in d['legend_texts'])
print('yes' if ok else 'no')
")
assert_eq "/batting By Season: Runs chart legend MUST NOT carry 'base' (C1 volume-chart rule)" "yes" "$runs_no_base"

# Test 4 — Cohort baseline shifts on a scope_key axis (season window).
# Kohli SR cohort at IPL 2016 vs IPL 2018 must differ — both seasons
# are well-populated; if both rounded equally that's a regression.
sr_2016=$(cohort_metric_at_season "$cohort_url&season_from=2016&season_to=2016" "strike_rate" "2016")
sr_2018=$(cohort_metric_at_season "$cohort_url&season_from=2018&season_to=2018" "strike_rate" "2018")
if [ "$sr_2016" != "MISSING" ] && [ "$sr_2018" != "MISSING" ] && [ "$sr_2016" != "$sr_2018" ]; then
  ok "/batting cohort shifts on season window (IPL 2016 SR=$sr_2016, 2018 SR=$sr_2018)"
else
  bad "/batting cohort did NOT shift on season window (2016=$sr_2016, 2018=$sr_2018)"
fi

# ───────────────────────────────────────────────────────────────────
# /bowling — Phase D (shipped)
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /bowling — Bumrah IPL By Season ==="
BUMRAH=462411b3

ab open "$BASE/bowling?player=$BUMRAH&$SCOPE_URL&tab=By%20Season"
sleep 3

legend=$(chart_legend_texts)
assert_contains "/bowling By Season: legend names player as primary" "JJ Bumrah" "$legend"
assert_contains "/bowling By Season: legend names cohort as 'base'" "base" "$legend"

titles=$(ab_eval "
  Array.from(document.querySelectorAll('h2,h3,h4'))
    .map(e => e.textContent?.trim())
    .filter(Boolean)
    .join('|')
")
assert_contains "/bowling By Season: 'Wickets by Season' chart title present" "Wickets by Season" "$titles"
assert_contains "/bowling By Season: 'Bowling Strike Rate by Season' chart title present" "Bowling Strike Rate by Season" "$titles"

cohort_url="$API/api/v1/scope/averages/players/bowling/by-season?person_id=$BUMRAH&$SCOPE"
sr_nonnull=$(cohort_nonnull_count "$cohort_url" "strike_rate")
if [ "$sr_nonnull" -ge 5 ]; then
  ok "/bowling cohort by-season has ≥5 SR rows (=$sr_nonnull)"
else
  bad "/bowling cohort by-season SR rows too few (=$sr_nonnull)"
fi

agent-browser eval --json "(() => {
  const frames = Array.from(document.querySelectorAll('.stream-xy-frame'));
  return {
    n_frames: frames.length,
    canvas_counts: frames.map(f => f.querySelectorAll('canvas').length),
    legend_texts: frames.map(f =>
      Array.from(f.querySelectorAll('g.legend-item text'))
        .map(t => t.textContent && t.textContent.trim())
    ),
  };
})()" > /tmp/chart_probe.json 2>/dev/null
n_frames=$(python3 -c "import json;print(json.load(open('/tmp/chart_probe.json'))['data']['result']['n_frames'])")
assert_eq "/bowling By Season: 2 stream-xy-frame containers (Wickets + SR)" "2" "$n_frames"
# C1: Wickets by Season volume → overlay dropped. SR rate → kept.
sr_has_both=$(python3 -c "
import json
d = json.load(open('/tmp/chart_probe.json'))['data']['result']
ok = any('JJ Bumrah' in lbls and 'base' in lbls for lbls in d['legend_texts'])
print('yes' if ok else 'no')
")
assert_eq "/bowling By Season: SR chart legend names both series" "yes" "$sr_has_both"
wkts_no_base=$(python3 -c "
import json
d = json.load(open('/tmp/chart_probe.json'))['data']['result']
ok = any('base' not in lbls for lbls in d['legend_texts'])
print('yes' if ok else 'no')
")
assert_eq "/bowling By Season: Wickets chart legend MUST NOT carry 'base' (C1)" "yes" "$wkts_no_base"

# Cohort shifts on season-window narrowing — same axis as batting.
sr_2018=$(cohort_metric_at_season "$cohort_url&season_from=2018&season_to=2018" "strike_rate" "2018")
sr_2021=$(cohort_metric_at_season "$cohort_url&season_from=2021&season_to=2021" "strike_rate" "2021")
if [ "$sr_2018" != "MISSING" ] && [ "$sr_2021" != "MISSING" ] && [ "$sr_2018" != "$sr_2021" ]; then
  ok "/bowling cohort shifts on season window (IPL 2018 SR=$sr_2018, 2021 SR=$sr_2021)"
else
  bad "/bowling cohort did NOT shift on season window (2018=$sr_2018, 2021=$sr_2021)"
fi

# ───────────────────────────────────────────────────────────────────
# /fielding — Phase E (shipped)
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /fielding — Kohli IPL By Season ==="

ab open "$BASE/fielding?player=$KOHLI&$SCOPE_URL&tab=By%20Season"
sleep 3

titles=$(ab_eval "
  Array.from(document.querySelectorAll('h2,h3,h4'))
    .map(e => e.textContent?.trim())
    .filter(Boolean)
    .join('|')
")
assert_contains "/fielding By Season: 'Dismissals by Season' chart title present" "Dismissals by Season" "$titles"

cohort_url="$API/api/v1/scope/averages/players/fielding/by-season?person_id=$KOHLI&$SCOPE"
dpm_nonnull=$(curl -s "$cohort_url" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(sum(1 for r in d.get('by_season', []) if r.get('dismissals_per_match') is not None))
")
if [ "$dpm_nonnull" -ge 5 ]; then
  ok "/fielding cohort by-season has ≥5 dismissals_per_match rows (=$dpm_nonnull)"
else
  bad "/fielding cohort by-season rows too few (=$dpm_nonnull)"
fi

# spec-rate-vs-volume-audit C1: Dismissals by Season is a volume
# chart — overlay dropped. The C2 follow-up adds a sibling
# Dis/Match by Season chart with the cohort overlay.
agent-browser eval --json "(() => {
  const frames = Array.from(document.querySelectorAll('.stream-xy-frame'));
  return {
    n_frames: frames.length,
    canvas_counts: frames.map(f => f.querySelectorAll('canvas').length),
    legend_texts: frames.map(f =>
      Array.from(f.querySelectorAll('g.legend-item text'))
        .map(t => t.textContent && t.textContent.trim())
    ),
  };
})()" > /tmp/chart_probe.json 2>/dev/null
n_frames=$(python3 -c "import json;print(json.load(open('/tmp/chart_probe.json'))['data']['result']['n_frames'])")
assert_eq "/fielding By Season: 1 stream-xy-frame container (Dismissals)" "1" "$n_frames"
dis_no_base=$(python3 -c "
import json
d = json.load(open('/tmp/chart_probe.json'))['data']['result']
ok = d['legend_texts'] and all('base' not in lbls for lbls in d['legend_texts'])
print('yes' if ok else 'no')
")
assert_eq "/fielding By Season: Dismissals chart legend MUST NOT carry 'base' (C1)" "yes" "$dis_no_base"

# F4 dropped chips on volume tiles (Catches, Run Outs); their per-
# match rate siblings (Catches/Match, Run-outs/Match) carry the
# chip now — covered by player_band_q6_chips.sh. This test keeps
# the Dis/Match check (rate tile, unchanged behaviour).
api_summary=$(curl -s "$API/api/v1/fielders/$KOHLI/summary?$SCOPE")
agent-browser eval --json "(() => {
  return Array.from(document.querySelectorAll('.wisden-statrow .wisden-stat')).map(s => ({
    label: s.querySelector('.wisden-stat-label')?.textContent?.trim(),
    sub: s.querySelector('.wisden-stat-sub')?.textContent?.trim(),
  }));
})()" > /tmp/fld_row.json 2>/dev/null

api_base=$(echo "$api_summary" | python3 -c "
import json, sys
v = json.load(sys.stdin)['dismissals_per_match']['scope_avg']
print(f'{v:.3f}' if v is not None else 'NULL')
")
sub_text=$(python3 -c "
import json
rows = json.load(open('/tmp/fld_row.json'))['data']['result']
for r in rows:
    if r['label'] == 'Dis/Match':
        print(r.get('sub') or '')
        break
")
assert_contains "/fielding stat-row: Dis/Match chip cites API base $api_base" "vs base $api_base" "$sub_text"

echo
echo "─────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "OK"
