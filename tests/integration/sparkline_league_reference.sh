#!/bin/bash
# Tier 6 of internal_docs/spec-apples-to-apples-baselines.md.
#
# Asserts the forest-green `leagueReferenceValue` line renders on the
# distribution sparkline of every player-discipline panel (batting,
# bowling, fielding), and that the value matches the matching
# /summary scope_avg envelope on the API side (chip ↔ sparkline
# symmetry).
#
# Self-anchored per CLAUDE.md "Integration tests must self-anchor
# against SQL": the expected line value is read from the live
# /summary API (which is itself sanity-tested against SQL by
# tests/sanity/test_position_weighted_baselines.py), not hardcoded.

set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-3}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

KOHLI="ba607b88"
BUMRAH="462411b3"
DHONI="4a8a2e3b"

# Forest green from frontend/src/components/distribution/DistributionSparkline.tsx
LEAGUE_COLOR="#3F7A4D"

echo "=== Tier 6: sparkline leagueReferenceValue lines ==="

# ── /batting (Kohli IPL, runs tab) ──────────────────────────────
echo
echo "1. /batting?player=$KOHLI — runs tab, IPL scope"
ab open "$BASE/batting?player=$KOHLI&tournament=Indian%20Premier%20League&team_type=club&gender=male"
settle 4

green_count=$(ab_eval "document.querySelectorAll('.wisden-dist-sparkline line[data-ref=league]').length")
green_stroke=$(unq "$(ab_eval "document.querySelector('.wisden-dist-sparkline line[data-ref=league]')?.getAttribute('stroke') || ''")")
if [ "$green_count" = "1" ]; then ok "exactly 1 green line drawn"; else bad "expected 1 green line, got $green_count"; fi
if [ "$green_stroke" = "$LEAGUE_COLOR" ]; then ok "green line stroke is $LEAGUE_COLOR"; else bad "green stroke is '$green_stroke', expected $LEAGUE_COLOR"; fi

# Cross-check against API
api_sa=$(curl -sS "$API/api/v1/batters/$KOHLI/summary?gender=male&team_type=club&tournament=Indian%20Premier%20League" \
  | python3 -c "import json, sys; d=json.load(sys.stdin); v=d.get('runs_per_innings',{}).get('scope_avg'); print(f'{v:.1f}' if v is not None else '')")
legend_text=$(unq "$(ab_eval "document.body.innerText.match(/cohort at scope \([^)]+\)/)?.[0] || ''")")
if [[ "$legend_text" == *"$api_sa"* ]]; then ok "legend shows API scope_avg ($api_sa)"; else bad "legend text '$legend_text' lacks $api_sa"; fi

# ── /bowling (Bumrah IPL, wickets tab) ──────────────────────────
echo
echo "2. /bowling?player=$BUMRAH — wickets tab, IPL scope"
ab open "$BASE/bowling?player=$BUMRAH&tournament=Indian%20Premier%20League&team_type=club&gender=male"
settle 4

green_count=$(ab_eval "document.querySelectorAll('.wisden-dist-sparkline line[data-ref=league]').length")
green_stroke=$(unq "$(ab_eval "document.querySelector('.wisden-dist-sparkline line[data-ref=league]')?.getAttribute('stroke') || ''")")
if [ "$green_count" = "1" ]; then ok "exactly 1 green line drawn"; else bad "expected 1 green line, got $green_count"; fi
if [ "$green_stroke" = "$LEAGUE_COLOR" ]; then ok "green line stroke is $LEAGUE_COLOR"; else bad "green stroke is '$green_stroke', expected $LEAGUE_COLOR"; fi

api_sa=$(curl -sS "$API/api/v1/bowlers/$BUMRAH/summary?gender=male&team_type=club&tournament=Indian%20Premier%20League" \
  | python3 -c "import json, sys; d=json.load(sys.stdin); v=d.get('wickets_per_innings',{}).get('scope_avg'); print(f'{v:.2f}' if v is not None else '')")
legend_text=$(unq "$(ab_eval "document.body.innerText.match(/cohort at scope \([^)]+\)/)?.[0] || ''")")
if [[ "$legend_text" == *"$api_sa"* ]]; then ok "legend shows API scope_avg ($api_sa)"; else bad "legend text '$legend_text' lacks $api_sa"; fi

# ── /fielding (Dhoni IPL, catches tab) ──────────────────────────
echo
echo "3. /fielding?player=$DHONI — catches tab, IPL scope"
ab open "$BASE/fielding?player=$DHONI&tournament=Indian%20Premier%20League&team_type=club&gender=male"
settle 4

green_count=$(ab_eval "document.querySelectorAll('.wisden-dist-sparkline line[data-ref=league]').length")
green_stroke=$(unq "$(ab_eval "document.querySelector('.wisden-dist-sparkline line[data-ref=league]')?.getAttribute('stroke') || ''")")
if [ "$green_count" = "1" ]; then ok "exactly 1 green line drawn"; else bad "expected 1 green line, got $green_count"; fi
if [ "$green_stroke" = "$LEAGUE_COLOR" ]; then ok "green line stroke is $LEAGUE_COLOR"; else bad "green stroke is '$green_stroke', expected $LEAGUE_COLOR"; fi

api_sa=$(curl -sS "$API/api/v1/fielders/$DHONI/summary?gender=male&team_type=club&tournament=Indian%20Premier%20League" \
  | python3 -c "import json, sys; d=json.load(sys.stdin); v=d.get('catches_per_match',{}).get('scope_avg'); print(f'{v:.2f}' if v is not None else '')")
legend_text=$(unq "$(ab_eval "document.body.innerText.match(/cohort at scope \([^)]+\)/)?.[0] || ''")")
if [[ "$legend_text" == *"$api_sa"* ]]; then ok "legend shows API scope_avg ($api_sa)"; else bad "legend text '$legend_text' lacks $api_sa"; fi

echo
echo "=== Summary: $PASS pass / $FAIL fail ==="
if [ "$FAIL" -ne 0 ]; then echo -e "Failures:$FAILS"; exit 1; fi
