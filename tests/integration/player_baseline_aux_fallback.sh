#!/bin/bash
# Phase 3b of spec-player-baseline-aux-fallback.md.
#
# When any of the SIX filters (venue / opponent / team / innings / toss /
# result) is set, the player batting "typical player" comparison (the grey
# scope_avg chip on /batters/{id}/summary) MUST narrow with the player's
# own number. Before 3b it stayed frozen at the all-axes-open value — so
# "Kohli vs Mumbai" pitted his real-vs-MI strike rate against an unfiltered
# typical-batter strike rate.
#
# Red-then-green: every assertion in §1 FAILS at HEAD pre-3b (the cohort is
# frozen → `filtered == unfiltered`) and PASSES after the dispatch in
# `compute_players_batting_cohort` branches on `is_precomputed_scope`.
#
# Anchor scope: V Kohli at IPL 2016 (closed, stable; matches the
# `test_playerscopestatsposition_rollup.py` headline scope so the
# rollup-parity invariant + this live-path test compare against the same
# truth).
#
# Prereqs: FastAPI dev on :8000, sqlite3 cricket.db at repo root.
set -u

API="${API:-http://localhost:8000}"
DB="${DB:-cricket.db}"
KOHLI="ba607b88"
SCOPE="gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2016&season_to=2016"

PASS=0; FAIL=0; FAILS=""
ok(){ PASS=$((PASS+1)); echo "  PASS: $1"; }
bad(){ FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# Extract (cohort_sr, cohort_n_innings, own_sr) from /batters/{id}/summary.
read_summary() {
  curl -s "$API/api/v1/batters/$KOHLI/summary?$SCOPE&$1" \
    | python3 -c "
import sys, json
d = json.load(sys.stdin)
sr   = d['strike_rate']['scope_avg']
nin  = d['cohort']['n_innings_total'] if d.get('cohort') else None
own  = d['strike_rate']['value']
print(sr, nin, own)
"
}

echo "=== Player batting cohort — aux/filter narrowing (3b) ==="
echo "Scope: V Kohli @ IPL 2016 (male, club)"

# Unfiltered baseline — the frozen value the bug locks every filter to.
read -r U_SR U_N U_OWN < <(read_summary "")
echo "  unfiltered:  cohort_sr=$U_SR  n_innings=$U_N  own_sr=$U_OWN"
if [[ "$U_SR" == "None" || -z "$U_SR" ]]; then
  bad "unfiltered cohort_sr is null — scope is dead, pick a different anchor"
  echo "PASS=$PASS  FAIL=$FAIL"; exit 1
fi

# ── §1 Each of the six narrows BOTH the own number AND the cohort ──
# Each block: own_sr must change vs unfiltered (proves own narrowing works,
# Phase 1+2 ground state) AND cohort_sr must change OR n_innings must drop
# (proves 3b narrowed the cohort). At HEAD the cohort line FAILS.

check_filter() {
  local name="$1" qs="$2"
  read -r SR N OWN < <(read_summary "$qs")
  echo "  $name:  cohort_sr=$SR  n_innings=$N  own_sr=$OWN"
  # Cohort narrowing (the 3b headline). Own-side narrowing is Phase 1+2
  # and isn't this test's concern — some filters (e.g. filter_team=RCB
  # when Kohli only batted for RCB in IPL 2016) are no-ops for the
  # player's own slice but MUST still move the cohort pool.
  #
  # SR==None when the pool drops below the support cliff is legitimate
  # (the cliff is designed to blank thin comparisons) — what matters is
  # that the pool size n_innings_total moved off the frozen baseline.
  if [[ -z "$N" || "$N" == "None" ]]; then
    bad "$name: n_innings is null/missing"
  elif [[ "$N" != "$U_N" ]]; then
    ok "$name: cohort pool narrowed (n_inn ${U_N} -> ${N}; SR ${U_SR} -> ${SR})"
  else
    bad "$name: cohort FROZEN (n_inn=$N == unfiltered $U_N; SR=$SR == $U_SR) -- 3b not wired"
  fi
}

WANKHEDE="filter_venue=Wankhede+Stadium"
MI="filter_opponent=Mumbai+Indians"
RCB="filter_team=Royal+Challengers+Bengaluru"

check_filter "filter_venue=Wankhede"   "$WANKHEDE"
check_filter "filter_opponent=MI"      "$MI"
check_filter "filter_team=RCB"         "$RCB"
check_filter "inning=0"                "inning=0"
check_filter "result=won"              "result=won"
check_filter "toss_outcome=won"        "toss_outcome=won"

# ── §2 SQL anchor: cohort SR @ inning=0 matches direct live aggregation ──
# Independent rederivation: aggregate inningsbatterperf by position_bucket
# over the same WHERE the dispatch runs, convex-combine by Kohli's
# filtered position mix, compare to the API's cohort SR.
#
# Anchor uses inning=0 (not filter_opponent=MI) because the inning slice
# keeps the pool fat (473 innings) — fat enough that no bucket in
# Kohli's mix falls below the support cliff, so the cohort SR is a real
# number we can compare against. Filter_opponent / filter_venue / RCB-
# narrowing all push the IPL-2016 pool below the cliff for bucket 1,
# blanking SR (correct behaviour, but useless as an exact anchor).
echo
echo "=== SQL anchor — inning=0 (Kohli filtered mix, IPL 2016) ==="

EXPECTED_SR=$(python3 <<'PY'
import sqlite3, json, urllib.request

DB = "cricket.db"
API = "http://localhost:8000"
KOHLI = "ba607b88"
QS = "gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2016&season_to=2016&inning=0"

# Player's filtered position mix (the response's position_distribution[]
# is what the cohort fn convex-combines against internally).
with urllib.request.urlopen(f"{API}/api/v1/batters/{KOHLI}/summary?{QS}") as r:
    d = json.load(r)
pd = d["position_distribution"]
total = sum(p["innings"] for p in pd)
mix = [p["innings"] / total if total else 0 for p in pd]

# Per-bucket SR over inningsbatterperf with the live WHERE: IPL 2016,
# male, club, innings_number=0 (Option-B "batted first" for batting side).
conn = sqlite3.connect(DB)
rows = conn.execute("""
    SELECT ib.position_bucket AS bk,
           SUM(ib.runs)  AS runs,
           SUM(ib.balls) AS balls
    FROM inningsbatterperf ib
    JOIN innings i ON i.id = ib.innings_id
    JOIN match   m ON m.id = i.match_id
    WHERE i.super_over = 0
      AND m.gender = 'male'
      AND m.team_type = 'club'
      AND m.event_name = 'Indian Premier League'
      AND m.season = '2016'
      AND i.innings_number = 0
    GROUP BY ib.position_bucket
""").fetchall()
per_bucket_sr = {bk: (runs / balls * 100) if balls else None for bk, runs, balls in rows}

# Convex-combine over the player's filtered mix (matches convex_combine
# in api/scope_averages_players.py).
total = 0.0; total_mix = 0.0
for b, w in enumerate(mix, start=1):
    if w == 0:
        continue
    total_mix += w
    v = per_bucket_sr.get(b)
    if v is None:
        continue
    total += w * v
expected = total if total_mix else None
print(round(expected, 1) if expected is not None else "None")
PY
)

read -r API_SR _ _ < <(read_summary "inning=0")
echo "  expected (SQL-anchored, mix-weighted): $EXPECTED_SR"
echo "  API cohort SR:                         $API_SR"
if [[ "$API_SR" == "None" || "$EXPECTED_SR" == "None" ]]; then
  bad "SQL anchor inconclusive -- one side is null (API $API_SR, expected $EXPECTED_SR)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$API_SR')-float('$EXPECTED_SR')) <= 0.2 else 1)"; then
  ok "API cohort SR == SQL-anchored expected (delta <= 0.2)"
else
  bad "API cohort SR=$API_SR != SQL-anchored $EXPECTED_SR (delta > 0.2)"
fi

# ── §3 /distribution endpoint also narrows (same compute fn) ──
# Spec §10: "summary chip + distribution" — both consumers of
# compute_players_batting_cohort must see the cohort narrow.
echo
echo "=== /distribution milestone scope_avg also narrows ==="

dist_pfifty() {
  curl -s "$API/api/v1/batters/$KOHLI/distribution?$SCOPE&$1" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['lifetime']['milestones'].get('p_50_plus',{}).get('scope_avg'))"
}
U_DP=$(dist_pfifty "")
I_DP=$(dist_pfifty "inning=0")
echo "  unfiltered p_50_plus.scope_avg: $U_DP"
echo "  inning=0   p_50_plus.scope_avg: $I_DP"
if [[ "$U_DP" != "None" && "$I_DP" != "None" && "$U_DP" != "$I_DP" ]]; then
  ok "/distribution p_50_plus.scope_avg narrowed ($U_DP -> $I_DP)"
else
  bad "/distribution p_50_plus.scope_avg FROZEN ($U_DP vs $I_DP) -- live path not reaching distribution caller"
fi

# ── §4 Filter-combination matrix (CLAUDE.md mandatory) ──
# Single combined narrowing must move the cohort too.
echo
echo "=== Filter-combination matrix ==="
check_filter "MI + inning=0"                  "$MI&inning=0"
check_filter "MI + Wankhede"                  "$MI&$WANKHEDE"
check_filter "RCB + MI"                       "$RCB&$MI"
check_filter "RCB + result=won + toss=won"    "$RCB&result=won&toss_outcome=won"

# ── §5 by-season cohort narrows under the six (Phase 3c) ──
# /scope/averages/players/batting/by-season's per-season cohort overlay
# read off the precomputed scope-key table until 3c — frozen under the
# six. After 3c it dispatches to a live inningsbatterperf aggregation
# with m.season in the GROUP BY. Anchor: Kohli IPL 2014-2018, season
# 2016. inning=0 keeps the per-season pool fat enough that bucket 1
# clears the support cliff, so SR is a real number to anchor.
echo
echo "=== by-season cohort narrows (3c) ==="
BS_SCOPE="person_id=$KOHLI&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018"

# Read (strike_rate, n_innings) for a given season row under a filter.
bs_row() {  # $1=filter qs  $2=season
  curl -s "$API/api/v1/scope/averages/players/batting/by-season?$BS_SCOPE&$1" \
    | python3 -c "
import sys, json
d = json.load(sys.stdin); s='$2'
for r in d['by_season']:
    if r['season']==s:
        print(r.get('strike_rate'), r.get('n_innings')); break
else:
    print('None None')
"
}

read -r BS_U_SR BS_U_N < <(bs_row "" 2016)
read -r BS_I_SR BS_I_N < <(bs_row "inning=0" 2016)
echo "  2016 unfiltered: SR=$BS_U_SR n_inn=$BS_U_N"
echo "  2016 inning=0:   SR=$BS_I_SR n_inn=$BS_I_N"
if [[ -z "$BS_I_N" || "$BS_I_N" == "None" ]]; then
  bad "by-season inning=0: n_innings null"
elif [[ "$BS_I_N" != "$BS_U_N" ]]; then
  ok "by-season cohort narrowed (n_inn $BS_U_N -> $BS_I_N; SR $BS_U_SR -> $BS_I_SR)"
else
  bad "by-season cohort FROZEN (n_inn=$BS_I_N == $BS_U_N) -- 3c not wired"
fi

# SQL anchor: live by-season SR @ 2016 inning=0 == direct inningsbatterperf
# aggregation, convex-combined by Kohli's narrowed per-season mix.
BS_EXPECTED=$(python3 <<'PY'
import sqlite3, json, urllib.request
DB="cricket.db"; API="http://localhost:8000"
BASE="person_id=ba607b88&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018&inning=0"
d=json.load(urllib.request.urlopen(f"{API}/api/v1/scope/averages/players/batting/by-season?{BASE}"))
row=[r for r in d['by_season'] if r['season']=='2016']
if not row: print("None"); raise SystemExit
mix=row[0]['mix']
conn=sqlite3.connect(DB)
rows=conn.execute("""
 SELECT ib.position_bucket bk, SUM(ib.runs) runs, SUM(ib.balls) balls
 FROM inningsbatterperf ib JOIN innings i ON i.id=ib.innings_id JOIN match m ON m.id=i.match_id
 WHERE i.super_over=0 AND m.gender='male' AND m.team_type='club'
   AND m.event_name='Indian Premier League' AND m.season='2016' AND i.innings_number=0
 GROUP BY ib.position_bucket""").fetchall()
sr={bk:(runs/balls*100 if balls else None) for bk,runs,balls in rows}
tot=0.0; tm=0.0
for b,w in enumerate(mix,1):
    if w==0: continue
    v=sr.get(b)
    if v is None: continue
    tm+=w; tot+=w*v
print(round(tot/tm,1) if tm else "None")
PY
)
echo "  SQL-anchored 2016 inning=0 SR: $BS_EXPECTED  (API: $BS_I_SR)"
if [[ "$BS_I_SR" == "None" || "$BS_EXPECTED" == "None" ]]; then
  bad "by-season SQL anchor inconclusive (API $BS_I_SR, expected $BS_EXPECTED)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$BS_I_SR')-float('$BS_EXPECTED'))<=0.2 else 1)"; then
  ok "by-season live SR == SQL-anchored ($BS_I_SR ~ $BS_EXPECTED)"
else
  bad "by-season live SR=$BS_I_SR != SQL-anchored $BS_EXPECTED"
fi

# ── §6 by-phase cohort narrows under the six (Phase 3c) ──
# /scope/averages/players/batting/by-phase's per-phase chip baseline read
# off the precomputed phase×position table until 3c — frozen under the
# six. After 3c it dispatches to a live delivery-grain aggregation
# (over_number → phase, position off inningsbatterperf, all-ball
# convention). Q4: under inning=0 all three phases keep ~1000 innings,
# well above the 30-innings support cliff — not degenerate.
echo
echo "=== by-phase cohort narrows (3c) ==="
BP_SCOPE="person_id=$KOHLI&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018"

# Read "SR n_inn below" for a given phase under a filter.
bp_phase() {  # $1=filter  $2=phase name
  curl -s "$API/api/v1/scope/averages/players/batting/by-phase?$BP_SCOPE&$1" \
    | python3 -c "
import sys, json
d = json.load(sys.stdin); name='$2'
for r in d['by_phase']:
    if r['phase']==name:
        print(r.get('strike_rate'), r.get('n_innings_in_phase'), r.get('below_support')); break
else:
    print('None None None')
"
}

read -r BP_U_SR BP_U_N _ < <(bp_phase "" powerplay)
read -r BP_I_SR BP_I_N BP_I_BELOW < <(bp_phase "inning=0" powerplay)
echo "  powerplay unfiltered: SR=$BP_U_SR n_inn=$BP_U_N"
echo "  powerplay inning=0:   SR=$BP_I_SR n_inn=$BP_I_N below=$BP_I_BELOW"
if [[ -z "$BP_I_N" || "$BP_I_N" == "None" ]]; then
  bad "by-phase inning=0: n_innings_in_phase null"
elif [[ "$BP_I_N" != "$BP_U_N" ]]; then
  ok "by-phase cohort narrowed (n_inn $BP_U_N -> $BP_I_N; SR $BP_U_SR -> $BP_I_SR)"
else
  bad "by-phase cohort FROZEN (n_inn=$BP_I_N == $BP_U_N) -- 3c not wired"
fi
# Q4 guard: all three phases must stay supported under the inning narrow.
for PH in powerplay middle death; do
  read -r _ PN PB < <(bp_phase "inning=0" "$PH")
  if [[ "$PB" == "False" ]]; then
    ok "Q4: $PH non-degenerate under inning=0 (n_inn=$PN, supported)"
  else
    bad "Q4: $PH degenerate under inning=0 (n_inn=$PN, below_support=$PB)"
  fi
done

# SQL anchor: live by-phase powerplay SR @ inning=0 == direct delivery
# aggregation, convex-combined by Kohli's per-phase position mix.
BP_EXPECTED=$(python3 <<'PY'
import sqlite3, json, urllib.request
DB="cricket.db"; API="http://localhost:8000"
BASE="person_id=ba607b88&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018&inning=0"
d=json.load(urllib.request.urlopen(f"{API}/api/v1/scope/averages/players/batting/by-phase?{BASE}"))
row=[r for r in d['by_phase'] if r['phase']=='powerplay']
if not row: print("None"); raise SystemExit
mix=row[0]['mix']
conn=sqlite3.connect(DB)
LEGAL="(d.extras_wides=0 AND d.extras_noballs=0)"
rows=conn.execute(f"""
 SELECT ib.position_bucket pb, SUM(d.runs_batter) runs,
   SUM(CASE WHEN {LEGAL} THEN 1 ELSE 0 END) balls
 FROM delivery d
 JOIN inningsbatterperf ib ON ib.innings_id=d.innings_id AND ib.batter_id=d.batter_id
 JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
 WHERE i.super_over=0 AND d.over_number<=5
   AND m.gender='male' AND m.team_type='club'
   AND m.event_name='Indian Premier League'
   AND m.season IN ('2014','2015','2016','2017','2018')
   AND i.innings_number=0 AND ({LEGAL} OR d.runs_batter<>0)
 GROUP BY pb""").fetchall()
sr={pb:(runs/balls*100 if balls else None) for pb,runs,balls in rows}
tot=0.0; tm=0.0
for b,w in enumerate(mix,1):
    if w==0: continue
    v=sr.get(b)
    if v is None: continue
    tm+=w; tot+=w*v
print(round(tot/tm,1) if tm else "None")
PY
)
echo "  SQL-anchored powerplay inning=0 SR: $BP_EXPECTED  (API: $BP_I_SR)"
if [[ "$BP_I_SR" == "None" || "$BP_EXPECTED" == "None" ]]; then
  bad "by-phase SQL anchor inconclusive (API $BP_I_SR, expected $BP_EXPECTED)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$BP_I_SR')-float('$BP_EXPECTED'))<=0.2 else 1)"; then
  ok "by-phase live SR == SQL-anchored ($BP_I_SR ~ $BP_EXPECTED)"
else
  bad "by-phase live SR=$BP_I_SR != SQL-anchored $BP_EXPECTED"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
