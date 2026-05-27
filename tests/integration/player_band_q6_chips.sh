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
#   Bndr/Inn, 30s/Inn, Dot%, B/Bndry — each with a "vs cohort N.NN" chip
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

# Inverse: pass when needle is absent from actual. Used by the rate-
# vs-volume audit assertions where the volume tile (Runs, 100s, 50s,
# Ducks) MUST NOT carry a per-innings rate chip (dimensional rule).
assert_not_contains() {
  local label="$1" needle="$2" actual="$3"
  if [[ "$actual" != *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' unexpectedly present in: $actual"; fi
}

# Pass when the tile exists. Used to confirm a newly-added tile is
# present on the page.
assert_tile_present() {
  local label="$1" expected_label="$2"
  if python3 -c "
import json, sys
rows = json.load(open('/tmp/tiles.json'))['data']['result']
sys.exit(0 if any(r['label'] == '$expected_label' for r in rows) else 1)
"; then ok "$label"
  else bad "$label — tile '$expected_label' not present"; fi
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

# Row 2 — new per-innings rate tiles. Each must carry "vs cohort N"
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
  assert_contains "Kohli /players Batting: $label chip cites base $api_f" "vs cohort $api_f" "$sub"
done

# spec-rate-vs-volume-audit F1 — volume tiles (Runs, 100s, 50s, Ducks)
# MUST NOT carry a per-innings rate chip. Each volume tile now has a
# sibling per-innings rate tile that carries the chip instead.
for label in "Runs" "100s" "50s" "Ducks"; do
  sub=$(tile_sub "$label")
  assert_not_contains "Kohli /players Batting: $label tile MUST NOT carry chip" "vs cohort" "$sub"
done

# F1 — new per-innings rate tiles MUST exist and chip-cite the cohort
# scope_avg from the matching envelope. 100s/Inn, 50s/Inn, Runs/Inn,
# Ducks/Inn — each is a sibling rate to a volume tile above.
for combo in \
    "Runs/Inn:runs_per_innings:%.2f" \
    "100s/Inn:hundreds_per_innings:%.3f" \
    "50s/Inn:fifties_per_innings:%.3f" \
    "Ducks/Inn:ducks_per_innings:%.3f"; do
  label=$(echo "$combo" | cut -d: -f1)
  field=$(echo "$combo" | cut -d: -f2)
  fmt=$(echo "$combo" | cut -d: -f3)
  assert_tile_present "Kohli /players Batting: $label tile exists" "$label"
  api_v=$(summary_scope_avg "$bat_url" "$field")
  api_f=$(printf "$fmt" "$api_v")
  sub=$(tile_sub "$label")
  assert_contains "Kohli /players Batting: $label chip cites base $api_f" "vs cohort $api_f" "$sub"
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
  assert_contains "Bumrah /players Bowling: $label chip cites base $api_f" "vs cohort $api_f" "$sub"
done

# spec-rate-vs-volume-audit F3 — new volume tiles (Maiden Overs,
# 4-fers) MUST exist and carry NO chip. New rate tile (4-fers/Inn)
# MUST exist and carry the cohort chip.
for label in "Maiden Overs" "4-fers"; do
  assert_tile_present "Bumrah /players Bowling: $label tile exists" "$label"
  sub=$(tile_sub "$label")
  assert_not_contains "Bumrah /players Bowling: $label tile MUST NOT carry chip" "vs cohort" "$sub"
done
assert_tile_present "Bumrah /players Bowling: 4-fers/Inn tile exists" "4-fers/Inn"
fwh_v=$(summary_scope_avg "$bowl_url" "four_wicket_hauls_per_innings")
fwh_f=$(printf "%.4f" "$fwh_v")
sub=$(tile_sub "4-fers/Inn")
assert_contains "Bumrah /players Bowling: 4-fers/Inn chip cites base $fwh_f" "vs cohort $fwh_f" "$sub"

# ───────────────────────────────────────────────────────────────────
# Test 3 — Kohli /players: Fielding band per-match chips (Phase F)
# ───────────────────────────────────────────────────────────────────

echo
echo "=== Kohli /players — Fielding band Phase F chips ==="
ab open "$BASE/players?player=$KOHLI&$SCOPE_URL"
sleep 3
snapshot_tiles
fld_url="$API/api/v1/fielders/$KOHLI/summary?$SCOPE"

# spec-rate-vs-volume-audit F2 — volume tiles (Catches, Run-outs,
# Stumpings) MUST NOT carry per-match-rate chips. The chip lives on
# the sibling per-match rate tile.
for label in "Catches" "Run-outs" "Stumpings"; do
  sub=$(tile_sub "$label")
  assert_not_contains "Kohli /players Fielding: $label tile MUST NOT carry chip" "vs cohort" "$sub"
done

# F2 — new per-match rate tiles must exist + carry the cohort chip.
# Stumpings/Match suppressed at value=0 (non-keeper), tested below.
for combo in \
    "Catches/Match:catches_per_match:%.3f" \
    "Run-outs/Match:run_outs_per_match:%.3f"; do
  label=$(echo "$combo" | cut -d: -f1)
  field=$(echo "$combo" | cut -d: -f2)
  fmt=$(echo "$combo" | cut -d: -f3)
  assert_tile_present "Kohli /players Fielding: $label tile exists" "$label"
  api_v=$(summary_scope_avg "$fld_url" "$field")
  api_f=$(printf "$fmt" "$api_v")
  sub=$(tile_sub "$label")
  assert_contains "Kohli /players Fielding: $label chip cites base $api_f" "vs cohort $api_f" "$sub"
done

# Kohli has 0 stumpings → Stumpings/Match tile must be absent
# (non-keeper gate). Use the python tile-list to verify absence.
if python3 -c "
import json, sys
rows = json.load(open('/tmp/tiles.json'))['data']['result']
sys.exit(0 if not any(r['label'] == 'Stumpings/Match' for r in rows) else 1)
"; then
  ok "Kohli /players Fielding: Stumpings/Match tile absent at stumpings=0"
else
  bad "Kohli /players Fielding: Stumpings/Match tile shouldn't render when stumpings=0"
fi

# Existing Dis/Match chip — unchanged, still tied to cohort scope_avg.
dm_v=$(summary_scope_avg "$fld_url" "dismissals_per_match")
dm_f=$(printf "%.3f" "$dm_v")
sub=$(tile_sub "Dis/Match")
assert_contains "Kohli /players Fielding: Dis/Match chip cites base $dm_f" "vs cohort $dm_f" "$sub"

# ───────────────────────────────────────────────────────────────────
# Test 4 — Kohli /fielding deep-dive: F4 stat-row mirror
# ───────────────────────────────────────────────────────────────────

echo
echo "=== Kohli /fielding — Deep-dive stat row (F4) ==="
ab open "$BASE/fielding?player=$KOHLI&$SCOPE_URL"
sleep 3
snapshot_tiles

# Volume tiles MUST NOT carry chips (mirror of F2 on the deep-dive).
for label in "Catches" "Run Outs" "Stumpings"; do
  sub=$(tile_sub "$label")
  assert_not_contains "Kohli /fielding: $label tile MUST NOT carry chip" "vs cohort" "$sub"
done

# New per-match rate tiles must exist + carry cohort chip.
for combo in \
    "Catches/Match:catches_per_match:%.3f" \
    "Run-outs/Match:run_outs_per_match:%.3f"; do
  label=$(echo "$combo" | cut -d: -f1)
  field=$(echo "$combo" | cut -d: -f2)
  fmt=$(echo "$combo" | cut -d: -f3)
  assert_tile_present "Kohli /fielding: $label tile exists" "$label"
  api_v=$(summary_scope_avg "$fld_url" "$field")
  api_f=$(printf "$fmt" "$api_v")
  sub=$(tile_sub "$label")
  assert_contains "Kohli /fielding: $label chip cites base $api_f" "vs cohort $api_f" "$sub"
done

# Stumpings/Match absent at stumpings=0.
if python3 -c "
import json, sys
rows = json.load(open('/tmp/tiles.json'))['data']['result']
sys.exit(0 if not any(r['label'] == 'Stumpings/Match' for r in rows) else 1)
"; then
  ok "Kohli /fielding: Stumpings/Match tile absent at stumpings=0"
else
  bad "Kohli /fielding: Stumpings/Match tile shouldn't render when stumpings=0"
fi

# ───────────────────────────────────────────────────────────────────
# Test 5 — Bumrah /bowling deep-dive: F6 new tiles
# ───────────────────────────────────────────────────────────────────

echo
echo "=== Bumrah /bowling — Deep-dive new tiles (F6) ==="
ab open "$BASE/bowling?player=$BUMRAH&$SCOPE_URL"
sleep 3
snapshot_tiles
bowl_url="$API/api/v1/bowlers/$BUMRAH/summary?$SCOPE"

# New tiles must exist.
for label in "Wkts/Inn" "Maiden Overs" "Maidens/Inn" "4-fers" "4-fers/Inn"; do
  assert_tile_present "Bumrah /bowling: $label tile exists" "$label"
done

# Volume tiles (Wickets, Maiden Overs, 4-fers) MUST NOT carry chips.
for label in "Wickets" "Maiden Overs" "4-fers"; do
  sub=$(tile_sub "$label")
  assert_not_contains "Bumrah /bowling: $label tile MUST NOT carry chip" "vs cohort" "$sub"
done

# Rate tiles MUST carry chips citing the matching envelope scope_avg.
for combo in \
    "Wkts/Inn:wickets_per_innings:%.2f" \
    "Maidens/Inn:maidens_per_innings:%.3f" \
    "4-fers/Inn:four_wicket_hauls_per_innings:%.4f"; do
  label=$(echo "$combo" | cut -d: -f1)
  field=$(echo "$combo" | cut -d: -f2)
  fmt=$(echo "$combo" | cut -d: -f3)
  api_v=$(summary_scope_avg "$bowl_url" "$field")
  api_f=$(printf "$fmt" "$api_v")
  sub=$(tile_sub "$label")
  assert_contains "Bumrah /bowling: $label chip cites base $api_f" "vs cohort $api_f" "$sub"
done

# ───────────────────────────────────────────────────────────────────
# Test 6 — Kohli /batting deep-dive: F7 new tiles
# ───────────────────────────────────────────────────────────────────

echo
echo "=== Kohli /batting — Deep-dive new tiles (F7) ==="
ab open "$BASE/batting?player=$KOHLI&$SCOPE_URL"
sleep 3
snapshot_tiles
bat_url="$API/api/v1/batters/$KOHLI/summary?$SCOPE"

# New tiles must exist.
for label in "Runs/Inn" "Bndr/Inn" "30s/Inn · 50s/Inn · 100s/Inn"; do
  assert_tile_present "Kohli /batting: $label tile exists" "$label"
done

# Volume tiles MUST NOT carry chips.
sub=$(tile_sub "Runs")
assert_not_contains "Kohli /batting: Runs tile MUST NOT carry chip" "vs cohort" "$sub"
sub=$(tile_sub "30s / 50s / 100s")
assert_not_contains "Kohli /batting: 30s/50s/100s combined volume tile MUST NOT carry chip" "vs cohort" "$sub"

# Runs/Inn chip cites the cohort.
api_v=$(summary_scope_avg "$bat_url" "runs_per_innings")
api_f=$(printf "%.2f" "$api_v")
sub=$(tile_sub "Runs/Inn")
assert_contains "Kohli /batting: Runs/Inn chip cites base $api_f" "vs cohort $api_f" "$sub"

# Bndr/Inn chip cites the cohort.
api_v=$(summary_scope_avg "$bat_url" "boundaries_per_innings")
api_f=$(printf "%.2f" "$api_v")
sub=$(tile_sub "Bndr/Inn")
assert_contains "Kohli /batting: Bndr/Inn chip cites base $api_f" "vs cohort $api_f" "$sub"

# Combined milestone per-Inn tile shows all 3 base values in subtitle.
hpi=$(summary_scope_avg "$bat_url" "hundreds_per_innings")
hpi_f=$(printf "%.3f" "$hpi")
sub=$(tile_sub "30s/Inn · 50s/Inn · 100s/Inn")
assert_contains "Kohli /batting: combined per-Inn tile cites hundreds_per_innings base $hpi_f" "$hpi_f" "$sub"

echo
echo "─────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "OK"
