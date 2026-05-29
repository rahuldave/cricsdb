#!/bin/bash
# Narrowing-audit gap-filler (internal_docs/narrowing-audit-coverage.md).
#
# sparkline_league_reference.sh asserts the green "cohort at scope" line is
# PRESENT and matches /summary scope_avg at a FIXED scope. It does NOT assert
# the line MOVES when one of the six filters (venue/opponent/team/inning/
# toss/result) is applied. The 2026-05-29 DOM audit confirmed the green line
# narrows (it reads the same scope_avg envelope as the headline chip, which
# 3b/3d/3e made live); this test LOCKS that behaviour so a future regression
# that re-freezes the sparkline cohort line goes red.
#
# Per CLAUDE.md "integration tests must self-anchor against SQL/API": the
# expected values are read from the live /summary API at each scope (itself
# SQL-sanity-tested), never hardcoded. Covers every call site of the green
# sparkline line: batting, bowling, fielding (the three player Distribution
# panels). Toggling axis = inning (0 vs unset) on a stable IPL scope.

set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-4}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

KOHLI="ba607b88"
BUMRAH="462411b3"
DHONI="4a8a2e3b"
SCOPE="gender=male&team_type=club&tournament=Indian%20Premier%20League"

# Read the green league line's y1 (rendered position) for the active page.
spark_y1() { unq "$(ab_eval "document.querySelector('.wisden-dist-sparkline line[data-ref=league]')?.getAttribute('y1') || ''")"; }
# Read the "cohort at scope (… )" legend text.
spark_legend() { unq "$(ab_eval "document.body.innerText.match(/cohort at scope \([^)]+\)/)?.[0] || ''")"; }

# Pull scope_avg for a discipline at a given query string.
# $1=batters|bowlers|fielders  $2=field  $3=extra-qs  $4=printf-fmt
api_sa() {
  curl -sS "$API/api/v1/$1/$5/summary?$SCOPE$3" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); v=d.get('$2',{}).get('scope_avg'); print(('$4'%v) if v is not None else '')"
}

# $1=label $2=batters/.. $3=id $4=field $5=fmt $6=legend-unit-substring
check_discipline() {
  local label="$1" disc="$2" id="$3" field="$4" fmt="$5"
  echo
  echo "── $label ($disc/$id) ──"

  # none-of-six
  ab open "$BASE/${label}?player=$id&$SCOPE"; settle
  local y1_none; y1_none=$(spark_y1)
  local leg_none; leg_none=$(spark_legend)
  local api_none; api_none=$(api_sa "$disc" "$field" "" "$fmt" "$id")

  # inning=0 (batted first)
  ab open "$BASE/${label}?player=$id&$SCOPE&inning=0"; settle
  local y1_inn; y1_inn=$(spark_y1)
  local leg_inn; leg_inn=$(spark_legend)
  local api_inn; api_inn=$(api_sa "$disc" "$field" "&inning=0" "$fmt" "$id")

  # 1. API itself must narrow (sanity — otherwise the DOM test is vacuous)
  if [ -n "$api_none" ] && [ -n "$api_inn" ] && [ "$api_none" != "$api_inn" ]; then
    ok "$label API scope_avg narrows under inning ($api_none → $api_inn)"
  else
    bad "$label API scope_avg did not narrow ($api_none vs $api_inn) — cannot test DOM move"
  fi

  # 2. the rendered green line MOVES (the core assertion)
  if [ -n "$y1_none" ] && [ -n "$y1_inn" ] && [ "$y1_none" != "$y1_inn" ]; then
    ok "$label sparkline green line y1 moves ($y1_none → $y1_inn)"
  else
    bad "$label sparkline green line y1 FROZEN ($y1_none vs $y1_inn)"
  fi

  # 3. legend tracks the API scope_avg at EACH scope (chip↔sparkline symmetry)
  if [[ -n "$api_none" && "$leg_none" == *"$api_none"* ]]; then
    ok "$label legend matches API at none-of-six ($api_none)"
  else
    bad "$label legend '$leg_none' lacks API none value $api_none"
  fi
  if [[ -n "$api_inn" && "$leg_inn" == *"$api_inn"* ]]; then
    ok "$label legend matches API under inning=0 ($api_inn)"
  else
    bad "$label legend '$leg_inn' lacks API inning value $api_inn"
  fi
}

echo "=== sparkline green cohort line — narrowing under inning ==="
# batting legend prints 1 decimal (runs/inn); bowling/fielding 2 decimals.
check_discipline "batting"  "batters"  "$KOHLI"  "runs_per_innings"   "%.1f"
check_discipline "bowling"  "bowlers"  "$BUMRAH" "wickets_per_innings" "%.2f"
check_discipline "fielding" "fielders" "$DHONI"  "catches_per_match"  "%.2f"

# ── Team distribution panels (Batting / Bowling / Fielding tabs) ─────────
# Same green league-reference line (leagueReferenceValue) on the three team
# panels. Team legend format differs ("League (…)"), so assert the robust,
# format-independent core: the rendered line y1 MOVES under inning. Teams are
# Tier 1 (no mix). Anchor team = Mumbai Indians, IPL.
TEAM="Mumbai%20Indians"
for TAB in Batting Bowling Fielding; do
  echo
  echo "── team $TAB ($TEAM) ──"
  ab open "$BASE/teams?team=$TEAM&$SCOPE&tab=$TAB"; settle
  ty_none=$(spark_y1)
  ab open "$BASE/teams?team=$TEAM&$SCOPE&tab=$TAB&inning=0"; settle
  ty_inn=$(spark_y1)
  if [ -n "$ty_none" ] && [ -n "$ty_inn" ] && [ "$ty_none" != "$ty_inn" ]; then
    ok "team $TAB sparkline green line y1 moves ($ty_none → $ty_inn)"
  else
    bad "team $TAB sparkline green line y1 FROZEN ($ty_none vs $ty_inn)"
  fi
done

echo
echo "=== Summary: $PASS pass / $FAIL fail ==="
if [ "$FAIL" -ne 0 ]; then echo -e "Failures:$FAILS"; exit 1; fi
