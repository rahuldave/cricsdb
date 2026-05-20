#!/bin/bash
# Player /players band — Phase F Q6 chip extensions integration test.
#
# Spec: internal_docs/spec-player-baseline-parity.md §4.1 + Q6 (ii)
# + §6.3.
#
# Phase F surfaces the per-innings rate envelopes session 1 shipped
# (commit 55c890a) on PlayerSummaryRow.tsx:
#
# - Batting band gains a second row of cols-6 tiles: 4s/Inn, 6s/Inn,
#   Bndr/Inn, 30s/Inn, Dot%, B/Bndry — each with a "vs base N.NN" chip
#   anchored against /batters/{id}/summary's envelope scope_avg.
# - 100s and 50s tiles (existing kernels in row 1) gain chip subtitles
#   citing hundreds_per_innings + fifties_per_innings scope_avg.
# - Bowling band widens cols-4 → cols-6 to fit Wkts/Inn + Maidens/Inn.
# - Fielding band's existing Catches/Stumpings/Run-outs volume tiles
#   gain per-match chip subtitles surfacing the envelopes Phase E
#   added to /fielders/{id}/summary.
#
# All assertions anchor against /summary endpoint scope_avg values
# (not re-derived SQL) — DOM ↔ API plumbing only.
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

# Snapshot every stat tile (label, value, sub) from the page into JSON.
snapshot_tiles() {
  agent-browser eval --json "(() => {
    return Array.from(document.querySelectorAll('.wisden-statrow .wisden-stat')).map(s => ({
      label: s.querySelector('.wisden-stat-label')?.textContent?.trim(),
      value: s.querySelector('.wisden-stat-value')?.textContent?.trim(),
      sub: s.querySelector('.wisden-stat-sub')?.textContent?.trim(),
    }));
  })()" 2>/dev/null > /tmp/tiles.json
}

# Find the subtitle text for a tile by label. Returns empty if the
# label isn't found OR the tile has no subtitle.
tile_sub() {
  local label="$1"
  python3 -c "
import json
rows = json.load(open('/tmp/tiles.json'))['data']['result']
for r in rows:
    if r['label'] == '$label':
        print(r.get('sub') or '')
        break
"
}

# Pull scope_avg for an envelope field from a /summary response.
summary_scope_avg() {
  local url="$1" field="$2"
  curl -s "$url" | python3 -c "
import json, sys
d = json.load(sys.stdin)
v = d['$field']['scope_avg']
print(v if v is not None else 'NULL')
"
}

SCOPE='gender=male&team_type=club&tournament=Indian+Premier+League'
SCOPE_URL='gender=male&team_type=club&tournament=Indian%20Premier%20League'
KOHLI=ba607b88
BUMRAH=462411b3

# ───────────────────────────────────────────────────────────────────
# Test 1 — Kohli /players: Batting band Q6 chip extensions
# ───────────────────────────────────────────────────────────────────

echo
echo "=== Kohli /players — Batting band Phase F chips ==="
ab open "$BASE/players?player=$KOHLI&$SCOPE_URL"
sleep 3
snapshot_tiles
bat_url="$API/api/v1/batters/$KOHLI/summary?$SCOPE"

# Row 2 — new per-innings rate tiles. Each must carry "vs base N"
# where N matches /batters/{id}/summary's envelope scope_avg.
for combo in \
    "4s/Inn:fours_per_innings:%.2f" \
    "6s/Inn:sixes_per_innings:%.2f" \
    "Bndr/Inn:boundaries_per_innings:%.2f" \
    "30s/Inn:thirties_per_innings:%.3f" \
    "Dot%:dot_pct:%.1f" \
    "B/Bndry:balls_per_boundary:%.2f"; do
  label=$(echo "$combo" | cut -d: -f1)
  field=$(echo "$combo" | cut -d: -f2)
  fmt=$(echo "$combo" | cut -d: -f3)
  api_v=$(summary_scope_avg "$bat_url" "$field")
  api_f=$(printf "$fmt" "$api_v")
  sub=$(tile_sub "$label")
  assert_contains "Kohli /players Batting: $label chip cites base $api_f" "vs base $api_f" "$sub"
done

# Row 1 — 100s / 50s tiles gain chip subtitles via per-innings rates.
for combo in \
    "100s:hundreds_per_innings:%.3f" \
    "50s:fifties_per_innings:%.3f"; do
  label=$(echo "$combo" | cut -d: -f1)
  field=$(echo "$combo" | cut -d: -f2)
  fmt=$(echo "$combo" | cut -d: -f3)
  api_v=$(summary_scope_avg "$bat_url" "$field")
  api_f=$(printf "$fmt" "$api_v")
  sub=$(tile_sub "$label")
  assert_contains "Kohli /players Batting: $label chip cites base $api_f" "vs base $api_f" "$sub"
done

# ───────────────────────────────────────────────────────────────────
# Test 2 — Bumrah /players: Bowling band Q6 chip extensions
# ───────────────────────────────────────────────────────────────────

echo
echo "=== Bumrah /players — Bowling band Phase F chips ==="
ab open "$BASE/players?player=$BUMRAH&$SCOPE_URL"
sleep 3
snapshot_tiles
bowl_url="$API/api/v1/bowlers/$BUMRAH/summary?$SCOPE"

for combo in \
    "Wkts/Inn:wickets_per_innings:%.2f" \
    "Maidens/Inn:maidens_per_innings:%.3f"; do
  label=$(echo "$combo" | cut -d: -f1)
  field=$(echo "$combo" | cut -d: -f2)
  fmt=$(echo "$combo" | cut -d: -f3)
  api_v=$(summary_scope_avg "$bowl_url" "$field")
  api_f=$(printf "$fmt" "$api_v")
  sub=$(tile_sub "$label")
  assert_contains "Bumrah /players Bowling: $label chip cites base $api_f" "vs base $api_f" "$sub"
done

# ───────────────────────────────────────────────────────────────────
# Test 3 — Kohli /players: Fielding band per-match chips (Phase F)
# ───────────────────────────────────────────────────────────────────

echo
echo "=== Kohli /players — Fielding band Phase F chips ==="
ab open "$BASE/players?player=$KOHLI&$SCOPE_URL"
sleep 3
snapshot_tiles
fld_url="$API/api/v1/fielders/$KOHLI/summary?$SCOPE"

for combo in \
    "Catches:catches_per_match:%.3f" \
    "Run-outs:run_outs_per_match:%.3f"; do
  label=$(echo "$combo" | cut -d: -f1)
  field=$(echo "$combo" | cut -d: -f2)
  fmt=$(echo "$combo" | cut -d: -f3)
  api_v=$(summary_scope_avg "$fld_url" "$field")
  api_f=$(printf "$fmt" "$api_v")
  sub=$(tile_sub "$label")
  assert_contains "Kohli /players Fielding: $label chip cites base $api_f" "vs base $api_f" "$sub"
done

# Stumpings tile chip is gated on value > 0; Kohli (non-keeper) has
# 0 stumpings, so the tile must NOT carry a "vs base" subtitle.
st_sub=$(tile_sub "Stumpings")
if [[ "$st_sub" != *"vs base"* ]]; then
  ok "Kohli /players Fielding: Stumpings tile (value=0) suppresses chip"
else
  bad "Kohli /players Fielding: Stumpings tile shouldn't carry chip at value=0"
fi

echo
echo "─────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "OK"
