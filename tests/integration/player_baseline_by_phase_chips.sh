#!/bin/bash
# Player baseline — By Phase chip integration test.
#
# Spec: internal_docs/spec-player-baseline-parity.md §4.2/§4.3/§4.4
# + §6.3.
#
# Phase C ships /batting By Phase chips on SR, Dots, B/4 — each
# phase block renders a "vs base N.NN" subtitle anchored against
# /api/v1/scope/averages/players/batting/by-phase. Phase D extends
# to /bowling (Economy, SR, Dots); Phase E extends to /fielding
# (dismissals_per_match). Structure mirrors that order — each
# discipline gets its own block.
#
# Per CLAUDE.md "Integration tests anchor against /summary's
# scope_avg, not re-derived SQL": expecteds pull from the
# /by-phase endpoint, not a re-derived SQL query.
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_contains() {
  local label="$1" needle="$2" actual="$3"
  if [[ "$actual" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not found in: $actual"; fi
}

# Get the textContent of a phase block by phase title (case-insensitive).
# Returns the full grid text so chip subtitles can be substring-matched.
phase_block_text() {
  local phase_title="$1"
  agent-browser eval --json "(() => {
    const block = Array.from(document.querySelectorAll('.wisden-phaseblock'))
      .find(b => b.querySelector('h3') &&
                 b.querySelector('h3').textContent.trim().toLowerCase()
                   === '$phase_title'.toLowerCase());
    if (!block) return null;
    const grid = block.querySelector('.wisden-phaseblock-grid');
    return grid ? grid.textContent.replace(/\s+/g, ' ').trim() : null;
  })()" 2>/dev/null > /tmp/phase_probe.json
  python3 -c "
import json
d = json.load(open('/tmp/phase_probe.json'))
print(d['data']['result'] if d.get('success') else '')
"
}

# Pull a metric from the cohort by-phase response. Phase is the
# lowercase API name ('powerplay'/'middle'/'death').
cohort_phase_metric() {
  local url="$1" phase="$2" field="$3"
  curl -s "$url" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d.get('by_phase', []):
    if r.get('phase') == '$phase':
        v = r.get('$field')
        print(f'{v:.2f}' if isinstance(v, float) else v)
        sys.exit(0)
print('MISSING')
"
}

# ───────────────────────────────────────────────────────────────────
# /batting — Phase C (shipped)
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /batting — Kohli IPL By Phase ==="
KOHLI=ba607b88
SCOPE='gender=male&team_type=club&tournament=Indian+Premier+League'
SCOPE_URL='gender=male&team_type=club&tournament=Indian%20Premier%20League'

ab open "$BASE/batting?player=$KOHLI&$SCOPE_URL&tab=By%20Phase"
sleep 3

cohort_url="$API/api/v1/scope/averages/players/batting/by-phase?person_id=$KOHLI&$SCOPE"

for phase in powerplay middle death; do
  block=$(phase_block_text "$phase")
  if [ -z "$block" ]; then
    bad "/batting By Phase: $phase block not found"
    continue
  fi
  # Each block must show "vs base N.NN" three times (SR, Dots, B/4)
  vs_base_count=$(echo "$block" | grep -o "vs base " | wc -l | tr -d ' ')
  if [ "$vs_base_count" -ge 3 ]; then
    ok "/batting By Phase: $phase has ≥3 'vs base' chips (=$vs_base_count)"
  else
    bad "/batting By Phase: $phase has only $vs_base_count 'vs base' chips, expected ≥3"
  fi

  # Confirm the chip's scope_avg value matches the API response. The
  # MetricDelta renders the value with `fmt=1` (SR/Dots) or `fmt=2`
  # (B/4). API returns one decimal precision for SR/Dots already.
  api_sr=$(cohort_phase_metric "$cohort_url" "$phase" "strike_rate")
  api_sr_1=$(printf '%.1f' "$api_sr")
  assert_contains "/batting By Phase: $phase SR chip cites API base $api_sr_1" "vs base $api_sr_1" "$block"

  api_dot=$(cohort_phase_metric "$cohort_url" "$phase" "dot_pct")
  api_dot_1=$(printf '%.1f' "$api_dot")
  assert_contains "/batting By Phase: $phase Dots chip cites API base $api_dot_1" "vs base $api_dot_1" "$block"

  api_b4=$(cohort_phase_metric "$cohort_url" "$phase" "balls_per_four")
  api_b4_2=$(printf '%.2f' "$api_b4")
  assert_contains "/batting By Phase: $phase B/4 chip cites API base $api_b4_2" "vs base $api_b4_2" "$block"
done

# Helper for cohort by-phase metrics on the bowling endpoint.
cohort_phase_metric_bowling() {
  local url="$1" phase="$2" field="$3"
  curl -s "$url" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d.get('by_phase', []):
    if r.get('phase') == '$phase':
        v = r.get('$field')
        print(f'{v:.2f}' if isinstance(v, float) else v)
        sys.exit(0)
print('MISSING')
"
}

# ───────────────────────────────────────────────────────────────────
# /bowling — Phase D (shipped)
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /bowling — Bumrah IPL By Phase ==="
BUMRAH=462411b3

ab open "$BASE/bowling?player=$BUMRAH&$SCOPE_URL&tab=By%20Phase"
sleep 3

cohort_url="$API/api/v1/scope/averages/players/bowling/by-phase?person_id=$BUMRAH&$SCOPE"

# Sub-phase blocks ("1–3", "4–6") nested under Powerplay receive
# NO chips (cohort doesn't carry sub-phase data), so test only the
# three main blocks. phase_block_text matches case-insensitively.
for phase in powerplay middle death; do
  block=$(phase_block_text "$phase")
  if [ -z "$block" ]; then
    bad "/bowling By Phase: $phase block not found"
    continue
  fi
  vs_base_count=$(echo "$block" | grep -o "vs base " | wc -l | tr -d ' ')
  if [ "$vs_base_count" -ge 3 ]; then
    ok "/bowling By Phase: $phase has ≥3 'vs base' chips (=$vs_base_count)"
  else
    bad "/bowling By Phase: $phase has only $vs_base_count 'vs base' chips, expected ≥3"
  fi

  # Econ + SR are 2-decimal places (lower-is-better), Dots is 1.
  api_econ=$(cohort_phase_metric_bowling "$cohort_url" "$phase" "economy")
  api_econ_2=$(printf '%.2f' "$api_econ")
  assert_contains "/bowling By Phase: $phase Econ chip cites API base $api_econ_2" "vs base $api_econ_2" "$block"

  api_sr=$(cohort_phase_metric_bowling "$cohort_url" "$phase" "strike_rate")
  api_sr_2=$(printf '%.2f' "$api_sr")
  assert_contains "/bowling By Phase: $phase SR chip cites API base $api_sr_2" "vs base $api_sr_2" "$block"

  api_dot=$(cohort_phase_metric_bowling "$cohort_url" "$phase" "dot_pct")
  api_dot_1=$(printf '%.1f' "$api_dot")
  assert_contains "/bowling By Phase: $phase Dots chip cites API base $api_dot_1" "vs base $api_dot_1" "$block"
done

# Sanity — sub-phase blocks ("1–3", "4–6") must NOT carry chips,
# because the cohort only ships powerplay / middle / death and a
# bogus sub-phase chip would have been an accidental wiring.
for sub in "1–3" "4–6"; do
  block=$(phase_block_text "$sub")
  if [ -z "$block" ]; then
    bad "/bowling By Phase: sub-phase '$sub' block not found"
    continue
  fi
  vs_base_count=$(echo "$block" | grep -o "vs base " | wc -l | tr -d ' ')
  if [ "$vs_base_count" -eq 0 ]; then
    ok "/bowling By Phase: sub-phase '$sub' has no chips (=0)"
  else
    bad "/bowling By Phase: sub-phase '$sub' unexpectedly has $vs_base_count chips"
  fi
done

# Helper for cohort by-phase metrics on the fielding endpoint.
cohort_phase_metric_fielding() {
  local url="$1" phase="$2" field="$3"
  curl -s "$url" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d.get('by_phase', []):
    if r.get('phase') == '$phase':
        v = r.get('$field')
        print(f'{v:.3f}' if isinstance(v, float) else v)
        sys.exit(0)
print('MISSING')
"
}

# ───────────────────────────────────────────────────────────────────
# /fielding — Phase E (shipped)
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /fielding — Kohli IPL By Phase ==="

ab open "$BASE/fielding?player=$KOHLI&$SCOPE_URL&tab=By%20Phase"
sleep 3

cohort_url="$API/api/v1/scope/averages/players/fielding/by-phase?person_id=$KOHLI&$SCOPE"

# spec-rate-vs-volume-audit F5: chip moved from the Total (volume)
# row to a sibling Total/Match (rate) row. Each phase block STILL
# carries exactly one chip — just on the new row.
for phase in powerplay middle death; do
  block=$(phase_block_text "$phase")
  if [ -z "$block" ]; then
    bad "/fielding By Phase: $phase block not found"
    continue
  fi
  vs_base_count=$(echo "$block" | grep -o "vs base " | wc -l | tr -d ' ')
  if [ "$vs_base_count" -eq 1 ]; then
    ok "/fielding By Phase: $phase has exactly 1 'vs base' chip (Total/Match)"
  else
    bad "/fielding By Phase: $phase has $vs_base_count chips, expected exactly 1"
  fi

  # F5 — block must contain a "Total/Match" label (new row).
  if echo "$block" | grep -q "Total/Match"; then
    ok "/fielding By Phase: $phase block has Total/Match row"
  else
    bad "/fielding By Phase: $phase block missing Total/Match row"
  fi

  api_dpm=$(cohort_phase_metric_fielding "$cohort_url" "$phase" "dismissals_per_match")
  # The cohort API rounds to 4 decimals; the UI re-formats to 3 via
  # MetricDelta's fmt=3. Truncate the API value to 3 decimals.
  api_dpm_3=$(printf '%.3f' "$api_dpm")
  assert_contains "/fielding By Phase: $phase Total/Match chip cites API base $api_dpm_3" "vs base $api_dpm_3" "$block"
done

# ───────────────────────────────────────────────────────────────────
# Phase G — cohort tooltip threaded into By Phase chips
# ───────────────────────────────────────────────────────────────────
# Phase G refactored the per-page PhaseChip helpers into a shared
# BaselineChip + threaded each page's cohortTooltip (Position-mix /
# Over-mix / Keeper-binary phrasing) into the chip's hover title.
# Hovering any By Phase chip should now show the same cohort phrase
# the summary tile chips do. Spec §5.1 Q5.

echo
echo "=== Phase G — cohort tooltips on By Phase chips ==="

ab open "$BASE/batting?player=$KOHLI&$SCOPE_URL&tab=By%20Phase"
sleep 3
agent-browser eval --json "(() => {
  const pp = Array.from(document.querySelectorAll('.wisden-phaseblock'))
    .find(b => b.querySelector('h3')?.textContent?.toLowerCase() === 'powerplay');
  return pp
    ? Array.from(pp.querySelectorAll('span[title]')).map(s => s.getAttribute('title'))
    : [];
})()" > /tmp/tt.json 2>/dev/null
n=$(python3 -c "
import json
tt = json.load(open('/tmp/tt.json'))['data']['result']
print(len([t for t in tt if t and 'Position-mix' in t]))
")
if [ "$n" -ge 3 ]; then
  ok "/batting By Phase: ≥3 chips carry 'Position-mix baseline' tooltip (=$n)"
else
  bad "/batting By Phase: only $n chips have Position-mix tooltip, expected ≥3"
fi

ab open "$BASE/bowling?player=$BUMRAH&$SCOPE_URL&tab=By%20Phase"
sleep 3
agent-browser eval --json "(() => {
  const pp = Array.from(document.querySelectorAll('.wisden-phaseblock'))
    .find(b => b.querySelector('h3')?.textContent === 'Powerplay');
  return pp
    ? Array.from(pp.querySelectorAll('span[title]')).map(s => s.getAttribute('title'))
    : [];
})()" > /tmp/tt.json 2>/dev/null
n=$(python3 -c "
import json
tt = json.load(open('/tmp/tt.json'))['data']['result']
print(len([t for t in tt if t and 'Over-mix' in t]))
")
if [ "$n" -ge 3 ]; then
  ok "/bowling By Phase: ≥3 chips carry 'Over-mix baseline' tooltip (=$n)"
else
  bad "/bowling By Phase: only $n chips have Over-mix tooltip, expected ≥3"
fi

ab open "$BASE/fielding?player=$KOHLI&$SCOPE_URL&tab=By%20Phase"
sleep 3
agent-browser eval --json "(() => {
  const pp = Array.from(document.querySelectorAll('.wisden-phaseblock'))
    .find(b => b.querySelector('h3')?.textContent?.toLowerCase() === 'powerplay');
  return pp
    ? Array.from(pp.querySelectorAll('span[title]')).map(s => s.getAttribute('title'))
    : [];
})()" > /tmp/tt.json 2>/dev/null
n=$(python3 -c "
import json
tt = json.load(open('/tmp/tt.json'))['data']['result']
print(len([t for t in tt if t and ('Outfielder-cohort' in t or 'Keeper-cohort' in t)]))
")
if [ "$n" -ge 1 ]; then
  ok "/fielding By Phase: ≥1 chip carries fielding cohort tooltip (=$n)"
else
  bad "/fielding By Phase: $n chips with fielding cohort tooltip, expected ≥1"
fi

echo
echo "─────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "OK"
