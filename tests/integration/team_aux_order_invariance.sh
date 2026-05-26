#!/bin/bash
# Teams aux-order invariance + narrowing (CSK) — spec-inning-unify-option-b.md /
# audit-aux-params.md. Applying the aux filters (inning, toss) in DIFFERENT
# orders must land at the SAME numbers, and BOTH the team value AND its
# "vs average" baseline must narrow along each trajectory (chip↔baseline
# symmetry — guards the win% baseline fix 3d802a2 + per-discipline cohort).
#
# Two trajectories to the same final state (inning=0 AND toss=won):
#   A: base -> +inning=0 -> +toss=won   (inning first)
#   B: base -> +toss=won -> +inning=0   (toss first; param order swapped)
# Assert A_final ~ B_final (approx) for value AND baseline on 3 metrics
# (win%, bowling economy, batting run-rate); and that each step narrowed
# (value + baseline moved off base — not frozen).
#
# Approx equality (rounding-tolerant): |a-b| <= TOL. No associative arrays
# (macOS bash 3.2). Prereqs: FastAPI dev (8000).
set -u
API="${API:-http://localhost:8000}"
TE=$(python3 -c "import urllib.parse;print(urllib.parse.quote('Chennai Super Kings'))")
BASE="gender=male&team_type=club&season_from=2024&season_to=2026"
TOL=0.15
PASS=0; FAIL=0; FAILS=""
ok(){ PASS=$((PASS+1)); echo "  PASS: $1"; }
bad(){ FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# fetch: <endpoint> <field> <value|scope_avg> <extra-qs>
fetch(){ curl -s "$API/api/v1/teams/$TE/$1?$BASE&$4" \
  | python3 -c "import sys,json
d=json.load(sys.stdin); f=d.get('$2')
v=(f.get('$3') if isinstance(f,dict) else (f if '$3'=='value' else None))
print(v if v is not None else 'null')" 2>/dev/null; }
aeq(){ python3 -c "a,b='$1','$2';print('Y' if a not in('null','') and b not in('null','') and abs(float(a)-float(b))<=$TOL else 'N')"; }
amoved(){ python3 -c "a,b='$1','$2';print('Y' if a not in('null','') and b not in('null','') and abs(float(a)-float(b))>$TOL else 'N')"; }

Q_INN="inning=0"
Q_TOSS="toss_outcome=won"
Q_A="inning=0&toss_outcome=won"
Q_B="toss_outcome=won&inning=0"

echo "=== Teams aux-order invariance + narrowing — CSK (club, 2024-26) ==="
# integer strictly-less (sample shrank). "" / null → N.
ilt(){ python3 -c "a,b='$1','$2';print('Y' if a not in('null','') and b not in('null','') and float(a)<float(b) else 'N')"; }

check_metric(){
  local lbl="$1"
  local ep="$2"
  local fld="$3"
  local vA=$(fetch "$ep" "$fld" value "$Q_A")
  local bA=$(fetch "$ep" "$fld" scope_avg "$Q_A")
  local vB=$(fetch "$ep" "$fld" value "$Q_B")
  local bB=$(fetch "$ep" "$fld" scope_avg "$Q_B")
  # sample_size = the team's own sample for this metric; it strictly
  # shrinks under a real filter (rounded rates may not move, but the
  # subset always does). This is the robust "filter was applied" signal.
  local sbase=$(fetch "$ep" "$fld" sample_size "")
  local sinn=$(fetch "$ep" "$fld" sample_size "$Q_INN")
  local stoss=$(fetch "$ep" "$fld" sample_size "$Q_TOSS")
  local sA=$(fetch "$ep" "$fld" sample_size "$Q_A")
  local sB=$(fetch "$ep" "$fld" sample_size "$Q_B")
  echo "--- $lbl ($ep . $fld) ---"
  echo "    value A=$vA B=$vB | baseline A=$bA B=$bB"
  echo "    sample base=$sbase inn=$sinn toss=$stoss | A=$sA B=$sB"

  # 1. ORDER INVARIANCE — reach the same place regardless of order (value AND baseline)
  [ "$(aeq "$vA" "$vB")" = Y ] && ok "$lbl value order-invariant (A=$vA ~ B=$vB)" || bad "$lbl value ORDER-DEPENDENT (A=$vA vs B=$vB)"
  [ "$(aeq "$bA" "$bB")" = Y ] && ok "$lbl baseline order-invariant (A=$bA ~ B=$bB)" || bad "$lbl baseline ORDER-DEPENDENT (A=$bA vs B=$bB)"

  # 2. NARROWS in BOTH trajectories — the team's subset strictly shrinks at each step
  [ "$(ilt "$sinn" "$sbase")" = Y ]  && ok "$lbl narrows base->inning (sample $sbase->$sinn)" || bad "$lbl sample did NOT shrink base->inning ($sbase->$sinn)"
  [ "$(ilt "$sA" "$sinn")" = Y ]     && ok "$lbl narrows inning->+toss (A) (sample $sinn->$sA)" || bad "$lbl sample did NOT shrink inning->+toss ($sinn->$sA)"
  [ "$(ilt "$stoss" "$sbase")" = Y ] && ok "$lbl narrows base->toss (sample $sbase->$stoss)" || bad "$lbl sample did NOT shrink base->toss ($sbase->$stoss)"
  [ "$(ilt "$sB" "$stoss")" = Y ]    && ok "$lbl narrows toss->+inning (B) (sample $stoss->$sB)" || bad "$lbl sample did NOT shrink toss->+inning ($stoss->$sB)"
}

check_metric "win%"     "summary"          "win_pct"
check_metric "bowl econ" "bowling/summary" "economy"
check_metric "bat RR"    "batting/summary" "run_rate"

# Chip<->baseline symmetry: win% has a large, clear effect, so its
# baseline must visibly narrow under the aux (the 3d802a2 fix). Guards
# against the baseline silently re-freezing.
echo "--- win% baseline narrows (chip<->baseline symmetry, the fix) ---"
wb_base=$(fetch "summary" "win_pct" scope_avg "")
wb_inn=$(fetch "summary" "win_pct" scope_avg "$Q_INN")
echo "    win% baseline base=$wb_base inn=$wb_inn"
[ "$(amoved "$wb_base" "$wb_inn")" = Y ] && ok "win% baseline narrows base->inning ($wb_base->$wb_inn) — not frozen" || bad "win% baseline FROZEN base->inning ($wb_base->$wb_inn)"

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
