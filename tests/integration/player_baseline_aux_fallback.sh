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

# ── §7 bowling by-phase cohort narrows under the six (Phase 3d-1) ──
# /scope/averages/players/bowling/by-phase read the precomputed per-over
# table (playerscopestatsover) until 3d — frozen under the six. After
# 3d-1 it dispatches to a live per-over aggregation over `delivery`
# (bowling orientation: inning flips to 1-N, toss/result key on the
# bowling side, filter_opponent=X → X batting). Anchor: J Bumrah IPL
# 2014-2018. Bowling econ is convex-combined over the bowler's per-over
# legal-ball mix within each phase.
echo
echo "=== bowling by-phase cohort narrows (3d) ==="
BUMRAH="462411b3"
BOWL_SCOPE="person_id=$BUMRAH&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018"

bowl_phase() {  # $1=filter  $2=phase name  → "econ n_balls below"
  curl -s "$API/api/v1/scope/averages/players/bowling/by-phase?$BOWL_SCOPE&$1" \
    | python3 -c "
import sys, json
d = json.load(sys.stdin); name='$2'
for r in d['by_phase']:
    if r['phase']==name:
        print(r.get('economy'), r.get('n_balls_in_phase'), r.get('below_support')); break
else:
    print('None None None')
"
}

read -r BW_U_E BW_U_N _ < <(bowl_phase "" powerplay)
read -r BW_I_E BW_I_N BW_I_BELOW < <(bowl_phase "inning=0" powerplay)
echo "  powerplay unfiltered: econ=$BW_U_E n_balls=$BW_U_N"
echo "  powerplay inning=0:   econ=$BW_I_E n_balls=$BW_I_N below=$BW_I_BELOW"
if [[ -z "$BW_I_N" || "$BW_I_N" == "None" ]]; then
  bad "bowling by-phase inning=0: n_balls null"
elif [[ "$BW_I_N" != "$BW_U_N" ]]; then
  ok "bowling by-phase cohort narrowed (n_balls $BW_U_N -> $BW_I_N; econ $BW_U_E -> $BW_I_E)"
else
  bad "bowling by-phase cohort FROZEN (n_balls=$BW_I_N == $BW_U_N) -- 3d not wired"
fi

# SQL anchor: live powerplay econ @ inning=0 == direct delivery aggregation
# at innings_number=1 (the bowling inning-flip of inning=0), convex-
# combined by Bumrah's narrowed per-over mix within the powerplay.
BW_EXPECTED=$(python3 <<'PY'
import sqlite3, json, urllib.request
DB="cricket.db"; API="http://localhost:8000"
BASE="person_id=462411b3&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018&inning=0"
d=json.load(urllib.request.urlopen(f"{API}/api/v1/scope/averages/players/bowling/by-phase?{BASE}"))
pp=[r for r in d['by_phase'] if r['phase']=='powerplay']
if not pp: print("None"); raise SystemExit
mix=pp[0]['mix']; overs=pp[0]['overs']
conn=sqlite3.connect(DB)
rows=conn.execute("""
 SELECT d.over_number+1 ob, SUM(d.runs_total) runs,
   SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) legal
 FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
 WHERE i.super_over=0 AND m.gender='male' AND m.team_type='club'
   AND m.event_name='Indian Premier League' AND m.season IN ('2014','2015','2016','2017','2018')
   AND i.innings_number=1 AND d.bowler_id IS NOT NULL AND d.over_number BETWEEN 0 AND 5
 GROUP BY d.over_number""").fetchall()
econ={ob:(runs*6/legal if legal else None) for ob,runs,legal in rows}
tot=0.0; tm=0.0
for i,o in enumerate(overs):
    w=mix[i]
    if w==0: continue
    v=econ.get(o)
    if v is None: continue
    tm+=w; tot+=w*v
print(round(tot/tm,2) if tm else "None")
PY
)
echo "  SQL-anchored powerplay inning=0 econ: $BW_EXPECTED  (API: $BW_I_E)"
if [[ "$BW_I_E" == "None" || "$BW_EXPECTED" == "None" ]]; then
  bad "bowling by-phase SQL anchor inconclusive (API $BW_I_E, expected $BW_EXPECTED)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$BW_I_E')-float('$BW_EXPECTED'))<=0.05 else 1)"; then
  ok "bowling by-phase live econ == SQL-anchored ($BW_I_E ~ $BW_EXPECTED)"
else
  bad "bowling by-phase live econ=$BW_I_E != SQL-anchored $BW_EXPECTED"
fi

# Opponent-flip orientation: filter_opponent=X means the bowler bowled
# AGAINST X (X batting → i.team = X), the mirror of batting. Anchor the
# powerplay econ against i.team='Chennai Super Kings'.
BW_OPP_API=$(bowl_phase "filter_opponent=Chennai+Super+Kings" powerplay | awk '{print $1}')
BW_OPP_EXPECTED=$(python3 <<'PY'
import sqlite3, json, urllib.request
DB="cricket.db"; API="http://localhost:8000"
BASE="person_id=462411b3&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018&filter_opponent=Chennai+Super+Kings"
d=json.load(urllib.request.urlopen(f"{API}/api/v1/scope/averages/players/bowling/by-phase?{BASE}"))
pp=[r for r in d['by_phase'] if r['phase']=='powerplay']
if not pp: print("None"); raise SystemExit
mix=pp[0]['mix']; overs=pp[0]['overs']
conn=sqlite3.connect(DB)
rows=conn.execute("""
 SELECT d.over_number+1 ob, SUM(d.runs_total) runs,
   SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) legal
 FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
 WHERE i.super_over=0 AND m.gender='male' AND m.team_type='club'
   AND m.event_name='Indian Premier League' AND m.season IN ('2014','2015','2016','2017','2018')
   AND i.team='Chennai Super Kings' AND d.bowler_id IS NOT NULL AND d.over_number BETWEEN 0 AND 5
 GROUP BY d.over_number""").fetchall()
econ={ob:(runs*6/legal if legal else None) for ob,runs,legal in rows}
tot=0.0; tm=0.0
for i,o in enumerate(overs):
    w=mix[i]
    if w==0: continue
    v=econ.get(o)
    if v is None: continue
    tm+=w; tot+=w*v
print(round(tot/tm,2) if tm else "None")
PY
)
echo "  filter_opponent=CSK powerplay econ: API=$BW_OPP_API  SQL(i.team=CSK)=$BW_OPP_EXPECTED"
if [[ "$BW_OPP_API" == "None" || "$BW_OPP_EXPECTED" == "None" ]]; then
  bad "bowling opponent-flip anchor inconclusive (API $BW_OPP_API, expected $BW_OPP_EXPECTED)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$BW_OPP_API')-float('$BW_OPP_EXPECTED'))<=0.05 else 1)"; then
  ok "bowling filter_opponent flips correctly (against X = X batting; $BW_OPP_API ~ $BW_OPP_EXPECTED)"
else
  bad "bowling filter_opponent orientation wrong (API $BW_OPP_API != i.team=CSK $BW_OPP_EXPECTED)"
fi

# ── §8 bowling by-season cohort narrows under the six (Phase 3d-2) ──
# /scope/averages/players/bowling/by-season read the precomputed per-over
# table until 3d-2 — frozen under the six. After 3d-2 it dispatches to a
# live per-(season, over) aggregation over `delivery` (bowling
# orientation). Anchor: J Bumrah IPL 2014-2018, season 2016, inning=0.
echo
echo "=== bowling by-season cohort narrows (3d) ==="
bowl_season() {  # $1=filter  $2=season  → "econ n_balls below"
  curl -s "$API/api/v1/scope/averages/players/bowling/by-season?$BOWL_SCOPE&$1" \
    | python3 -c "
import sys, json
d = json.load(sys.stdin); s='$2'
for r in d['by_season']:
    if r['season']==s:
        print(r.get('economy'), r.get('n_balls'), r.get('below_support')); break
else:
    print('None None None')
"
}
read -r BWS_U_E BWS_U_N _ < <(bowl_season "" 2016)
read -r BWS_I_E BWS_I_N _ < <(bowl_season "inning=0" 2016)
echo "  2016 unfiltered: econ=$BWS_U_E n_balls=$BWS_U_N"
echo "  2016 inning=0:   econ=$BWS_I_E n_balls=$BWS_I_N"
if [[ -z "$BWS_I_N" || "$BWS_I_N" == "None" ]]; then
  bad "bowling by-season inning=0: n_balls null"
elif [[ "$BWS_I_N" != "$BWS_U_N" ]]; then
  ok "bowling by-season cohort narrowed (n_balls $BWS_U_N -> $BWS_I_N; econ $BWS_U_E -> $BWS_I_E)"
else
  bad "bowling by-season cohort FROZEN (n_balls=$BWS_I_N == $BWS_U_N) -- 3d-2 not wired"
fi

# SQL anchor: live 2016 inning=0 econ == direct delivery aggregation at
# innings_number=1, convex-combined by Bumrah's narrowed per-over mix.
BWS_EXPECTED=$(python3 <<'PY'
import sqlite3, json, urllib.request
DB="cricket.db"; API="http://localhost:8000"
BASE="person_id=462411b3&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018&inning=0"
d=json.load(urllib.request.urlopen(f"{API}/api/v1/scope/averages/players/bowling/by-season?{BASE}"))
row=[r for r in d['by_season'] if r['season']=='2016']
if not row: print("None"); raise SystemExit
mix=row[0]['mix']
conn=sqlite3.connect(DB)
rows=conn.execute("""
 SELECT d.over_number+1 ob, SUM(d.runs_total) runs,
   SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) legal
 FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
 WHERE i.super_over=0 AND m.gender='male' AND m.team_type='club'
   AND m.event_name='Indian Premier League' AND m.season='2016' AND i.innings_number=1
   AND d.bowler_id IS NOT NULL AND d.over_number BETWEEN 0 AND 19
 GROUP BY d.over_number""").fetchall()
econ={ob:(runs*6/legal if legal else None) for ob,runs,legal in rows}
tot=0.0; tm=0.0
for o,w in enumerate(mix,1):
    if w==0: continue
    v=econ.get(o)
    if v is None: continue
    tm+=w; tot+=w*v
print(round(tot/tm,2) if tm else "None")
PY
)
echo "  SQL-anchored 2016 inning=0 econ: $BWS_EXPECTED  (API: $BWS_I_E)"
if [[ "$BWS_I_E" == "None" || "$BWS_EXPECTED" == "None" ]]; then
  bad "bowling by-season SQL anchor inconclusive (API $BWS_I_E, expected $BWS_EXPECTED)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$BWS_I_E')-float('$BWS_EXPECTED'))<=0.05 else 1)"; then
  ok "bowling by-season live econ == SQL-anchored ($BWS_I_E ~ $BWS_EXPECTED)"
else
  bad "bowling by-season live econ=$BWS_I_E != SQL-anchored $BWS_EXPECTED"
fi

# ── §9 bowling summary + distribution cohort narrows (Phase 3d-3) ──
# compute_players_bowling_cohort feeds the /bowlers/{id}/summary economy
# chip AND the /distribution wicket-ladder + econ/runs prob baselines.
# Read the precomputed per-over table until 3d-3 — frozen under the six.
# After 3d-3 it dispatches to the live full per-spell per-over
# aggregation. Note the mix it's weighted by comes from _over_distribution
# (scope-key grain, NOT narrowed by the six) — same established design as
# batting 3b's position_distribution — so the SQL anchor below uses the
# scope-key mix × the narrowed per-over cohort econ.
echo
echo "=== bowling summary + distribution cohort narrows (3d) ==="
BSUM="gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018"

sum_econ_cohort() {  # $1=filter → economy scope_avg
  curl -s "$API/api/v1/bowlers/$BUMRAH/summary?$BSUM&$1" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('economy',{}).get('scope_avg'))"
}
SE_U=$(sum_econ_cohort "")
SE_R=$(sum_econ_cohort "result=won")
echo "  summary economy cohort: none=$SE_U  result=won=$SE_R"
if [[ "$SE_U" == "None" || "$SE_R" == "None" ]]; then
  bad "bowling summary economy cohort null"
elif [[ "$SE_U" != "$SE_R" ]]; then
  ok "bowling summary economy cohort narrowed ($SE_U -> $SE_R under result=won)"
else
  bad "bowling summary economy cohort FROZEN ($SE_U == $SE_R) -- 3d-3 not wired"
fi

# SQL anchor: summary economy cohort @ inning=0 == scope-key over-mix
# (Bumrah's full-scope per-over legal balls) × per-over cohort econ at
# innings_number=1 (the inning=0 bowling flip).
SE_EXPECTED=$(python3 <<'PY'
import sqlite3, json, urllib.request
DB="cricket.db"; API="http://localhost:8000"
BASE="gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2014&season_to=2018&inning=0"
api=json.load(urllib.request.urlopen(f"{API}/api/v1/bowlers/462411b3/summary?{BASE}"))
conn=sqlite3.connect(DB)
mixrows=conn.execute("""
 SELECT psso.over_number ob, SUM(psso.legal_balls) lb
 FROM playerscopestatsover psso JOIN playerscopestats pss
   ON pss.scope_key=psso.scope_key AND pss.person_id=psso.person_id
 WHERE psso.person_id='462411b3' AND pss.tournament='Indian Premier League'
   AND pss.season IN ('2014','2015','2016','2017','2018') AND pss.gender='male' AND pss.team_type='club'
 GROUP BY psso.over_number""").fetchall()
tot=sum(lb for _,lb in mixrows); mix={ob:lb/tot for ob,lb in mixrows}
ec=conn.execute("""
 SELECT d.over_number+1 ob, SUM(d.runs_total) r,
   SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) lb
 FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
 WHERE i.super_over=0 AND m.gender='male' AND m.team_type='club' AND m.event_name='Indian Premier League'
   AND m.season IN ('2014','2015','2016','2017','2018') AND i.innings_number=1
   AND d.bowler_id IS NOT NULL AND d.over_number BETWEEN 0 AND 19
 GROUP BY d.over_number""").fetchall()
econ={ob:(r*6/lb if lb else None) for ob,r,lb in ec}
exp=sum(mix[o]*econ[o] for o in mix if econ.get(o) is not None)
print(round(exp,2))
PY
)
SE_I=$(sum_econ_cohort "inning=0")
echo "  SQL-anchored inning=0 summary econ: $SE_EXPECTED  (API: $SE_I)"
if [[ "$SE_I" == "None" || "$SE_EXPECTED" == "None" ]]; then
  bad "bowling summary SQL anchor inconclusive (API $SE_I, expected $SE_EXPECTED)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$SE_I')-float('$SE_EXPECTED'))<=0.1 else 1)"; then
  ok "bowling summary economy cohort == SQL-anchored ($SE_I ~ $SE_EXPECTED)"
else
  bad "bowling summary economy cohort=$SE_I != SQL-anchored $SE_EXPECTED"
fi

# Distribution prob baselines (driven by the per-spell columns) narrow.
dist_pgeq1() {  # $1=filter → wickets.milestones.p_geq_1.scope_avg
  curl -s "$API/api/v1/bowlers/$BUMRAH/distribution?$BSUM&$1" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['lifetime']['wickets']['milestones'].get('p_geq_1',{}).get('scope_avg'))"
}
DP_U=$(dist_pgeq1 "")
DP_R=$(dist_pgeq1 "result=won")
echo "  distribution p_geq_1 cohort: none=$DP_U  result=won=$DP_R"
if [[ "$DP_U" != "None" && "$DP_R" != "None" && "$DP_U" != "$DP_R" ]]; then
  ok "distribution wicket-prob baseline narrowed ($DP_U -> $DP_R) -- per-spell live path reaches distribution"
else
  bad "distribution wicket-prob baseline FROZEN ($DP_U vs $DP_R) -- 3d-3 not reaching distribution"
fi

# ── §10 fielding summary + distribution cohort narrows (Phase 3e) ──
# compute_players_fielding_cohort feeds /fielders/{id}/summary per-match
# chips AND /distribution catch ProbChips. It read the precomputed
# fielding children (frozen under the six) until 3e; now it dispatches to
# a live aggregation across matchplayer (matches_fielded denominator),
# fieldingcredit (numerator, Convention 3 + is_substitute=0, fielding
# orientation), and keeperassignment (keeper-binary partition). Anchor:
# MS Dhoni (a keeper → is_keeper=1 cohort), men's international.
echo
echo "=== fielding summary + distribution cohort narrows (3e) ==="
DHONI="4a8a2e3b"
FSUM="gender=male&team_type=international"

fld_cpm() {  # $1=filter → catches_per_match scope_avg
  curl -s "$API/api/v1/fielders/$DHONI/summary?$FSUM&$1" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('catches_per_match',{}).get('scope_avg'))"
}
FS_U=$(fld_cpm "")
FS_I=$(fld_cpm "inning=0")
echo "  summary catches/match cohort: none=$FS_U  inning=0=$FS_I"
if [[ "$FS_U" == "None" || "$FS_I" == "None" ]]; then
  bad "fielding summary catches/match cohort null"
elif [[ "$FS_U" != "$FS_I" ]]; then
  ok "fielding summary catches/match cohort narrowed ($FS_U -> $FS_I under inning=0)"
else
  bad "fielding summary catches/match cohort FROZEN ($FS_U == $FS_I) -- 3e not wired"
fi

# SQL anchor: keeper-cohort catches/match @ inning=0 == direct aggregation.
# inning=0 = batted first → fielding orientation = fielded in innings 1
# (1-0). Numerator: catches (Convention 3, non-sub, dismissed-position
# resolved via inningsbatterperf) over the keeper set in innings_number=1.
# Denominator: matches_fielded across the keeper set where the team fielded
# in innings 1.
FS_EXPECTED=$(python3 <<'PY'
import sqlite3
DB="cricket.db"
conn=sqlite3.connect(DB)
KEEP="""(SELECT DISTINCT ka.keeper_id FROM keeperassignment ka
  JOIN innings i ON i.id=ka.innings_id JOIN match m ON m.id=i.match_id
  WHERE m.gender='male' AND m.team_type='international' AND i.super_over=0
    AND i.innings_number=1 AND ka.keeper_id IS NOT NULL)"""
catches=conn.execute(f"""
 SELECT SUM(CASE WHEN fc.kind IN ('caught','caught_and_bowled') THEN 1 ELSE 0 END)
 FROM fieldingcredit fc JOIN delivery d ON d.id=fc.delivery_id
 JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
 JOIN wicket w ON w.id=fc.wicket_id
 JOIN inningsbatterperf ibp ON ibp.innings_id=i.id AND ibp.batter_id=w.player_out_id
 WHERE m.gender='male' AND m.team_type='international' AND i.super_over=0 AND i.innings_number=1
   AND fc.fielder_id IS NOT NULL AND COALESCE(fc.is_substitute,0)=0
   AND fc.fielder_id IN {KEEP}""").fetchone()[0] or 0
nm=conn.execute(f"""
 SELECT COUNT(*) FROM matchplayer mp JOIN match m ON m.id=mp.match_id
 WHERE m.gender='male' AND m.team_type='international'
   AND mp.person_id IN {KEEP}
   AND EXISTS (SELECT 1 FROM innings i2 WHERE i2.match_id=mp.match_id AND i2.super_over=0 AND i2.team!=mp.team)
   AND EXISTS (SELECT 1 FROM innings i3 WHERE i3.match_id=mp.match_id AND i3.super_over=0 AND i3.team!=mp.team AND i3.innings_number=1)""").fetchone()[0] or 0
print(round(catches/nm,3) if nm else "None")
PY
)
echo "  SQL-anchored inning=0 keeper catches/match: $FS_EXPECTED  (API: $FS_I)"
if [[ "$FS_I" == "None" || "$FS_EXPECTED" == "None" ]]; then
  bad "fielding summary SQL anchor inconclusive (API $FS_I, expected $FS_EXPECTED)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$FS_I')-float('$FS_EXPECTED'))<=0.01 else 1)"; then
  ok "fielding summary catches/match cohort == SQL-anchored ($FS_I ~ $FS_EXPECTED)"
else
  bad "fielding summary catches/match cohort=$FS_I != SQL-anchored $FS_EXPECTED"
fi

# Distribution catch ProbChip baselines narrow (same compute fn reaches
# /distribution). field_prob_zero is the cohort P(0 catches in a match).
fld_pzero() {  # $1=filter → lifetime catch P(=0) cohort scope_avg
  curl -s "$API/api/v1/fielders/$DHONI/distribution?$FSUM&$1" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['lifetime']['catches']['milestones'].get('p_zero',{}).get('scope_avg'))"
}
FD_U=$(fld_pzero "")
FD_I=$(fld_pzero "inning=0")
echo "  distribution catch P(=0) cohort: none=$FD_U  inning=0=$FD_I"
if [[ "$FD_U" != "None" && "$FD_I" != "None" && "$FD_U" != "$FD_I" ]]; then
  ok "fielding distribution catch-prob baseline narrowed ($FD_U -> $FD_I)"
else
  bad "fielding distribution catch-prob baseline FROZEN ($FD_U vs $FD_I) -- 3e not reaching distribution"
fi

# ── §11 fielding by-season cohort narrows under the six (Phase 3e) ──
# /scope/averages/players/fielding/by-season read the precomputed children
# until 3e — frozen under the six. Now live per-(season, keeper-flag).
# Anchor: Dhoni IPL, season 2016, inning=1 (keeper cohort).
echo
echo "=== fielding by-season cohort narrows (3e) ==="
FBS_SCOPE="person_id=$DHONI&gender=male&team_type=club&tournament=Indian+Premier+League"
fld_season() {  # $1=filter $2=season → "catches_per_match n_matches"
  curl -s "$API/api/v1/scope/averages/players/fielding/by-season?$FBS_SCOPE&$1" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin); s='$2'
for r in d['by_season']:
    if r['season']==s:
        print(r.get('catches_per_match'), r.get('n_matches')); break
else:
    print('None None')
"
}
read -r FBS_U_C FBS_U_N < <(fld_season "" 2016)
read -r FBS_I_C FBS_I_N < <(fld_season "inning=1" 2016)
echo "  2016 unfiltered: catches/m=$FBS_U_C n_matches=$FBS_U_N"
echo "  2016 inning=1:   catches/m=$FBS_I_C n_matches=$FBS_I_N"
if [[ -z "$FBS_I_N" || "$FBS_I_N" == "None" ]]; then
  bad "fielding by-season inning=1: n_matches null"
elif [[ "$FBS_I_N" != "$FBS_U_N" ]]; then
  ok "fielding by-season cohort narrowed (n_matches $FBS_U_N -> $FBS_I_N; catches/m $FBS_U_C -> $FBS_I_C)"
else
  bad "fielding by-season cohort FROZEN (n_matches=$FBS_I_N == $FBS_U_N) -- 3e not wired"
fi

# SQL anchor: 2016 inning=1 keeper cohort catches/match == direct
# aggregation. inning=1 = batted second → fielded in innings 0 (1-1).
FBS_EXPECTED=$(python3 <<'PY'
import sqlite3
DB="cricket.db"; conn=sqlite3.connect(DB)
KEEP="""(SELECT pid, kseason FROM (SELECT DISTINCT ka.keeper_id pid, m.season kseason
  FROM keeperassignment ka JOIN innings i ON i.id=ka.innings_id JOIN match m ON m.id=i.match_id
  WHERE m.gender='male' AND m.team_type='club' AND m.event_name='Indian Premier League'
    AND i.super_over=0 AND i.innings_number=0 AND ka.keeper_id IS NOT NULL))"""
c=conn.execute(f"""
 SELECT SUM(CASE WHEN fc.kind IN ('caught','caught_and_bowled') THEN 1 ELSE 0 END)
 FROM fieldingcredit fc JOIN delivery d ON d.id=fc.delivery_id
 JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
 JOIN wicket w ON w.id=fc.wicket_id
 JOIN inningsbatterperf ibp ON ibp.innings_id=i.id AND ibp.batter_id=w.player_out_id
 WHERE m.gender='male' AND m.team_type='club' AND m.event_name='Indian Premier League'
   AND m.season='2016' AND i.super_over=0 AND i.innings_number=0
   AND fc.fielder_id IS NOT NULL AND COALESCE(fc.is_substitute,0)=0
   AND (fc.fielder_id, m.season) IN {KEEP}""").fetchone()[0] or 0
nm=conn.execute(f"""
 SELECT COUNT(*) FROM matchplayer mp JOIN match m ON m.id=mp.match_id
 WHERE m.gender='male' AND m.team_type='club' AND m.event_name='Indian Premier League' AND m.season='2016'
   AND (mp.person_id, m.season) IN {KEEP}
   AND EXISTS (SELECT 1 FROM innings i2 WHERE i2.match_id=mp.match_id AND i2.super_over=0 AND i2.team!=mp.team)
   AND EXISTS (SELECT 1 FROM innings i3 WHERE i3.match_id=mp.match_id AND i3.super_over=0 AND i3.team!=mp.team AND i3.innings_number=0)""").fetchone()[0] or 0
print(round(c/nm,4) if nm else "None")
PY
)
echo "  SQL-anchored 2016 inning=1 catches/match: $FBS_EXPECTED  (API: $FBS_I_C)"
if [[ "$FBS_I_C" == "None" || "$FBS_EXPECTED" == "None" ]]; then
  bad "fielding by-season SQL anchor inconclusive (API $FBS_I_C, expected $FBS_EXPECTED)"
elif python3 -c "import sys; sys.exit(0 if abs(float('$FBS_I_C')-float('$FBS_EXPECTED'))<=0.001 else 1)"; then
  ok "fielding by-season live catches/match == SQL-anchored ($FBS_I_C ~ $FBS_EXPECTED)"
else
  bad "fielding by-season live catches/match=$FBS_I_C != SQL-anchored $FBS_EXPECTED"
fi

# ── §12 fielding by-phase cohort narrows under the six (Phase 3e) ──
# /scope/averages/players/fielding/by-phase frozen until 3e; now live
# per-(phase, keeper-flag), phase = the over the dismissal fell in.
echo
echo "=== fielding by-phase cohort narrows (3e) ==="
fld_phase() {  # $1=filter $2=phase → "catches_per_match n_matches"
  curl -s "$API/api/v1/scope/averages/players/fielding/by-phase?$FBS_SCOPE&$1" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin); name='$2'
for r in d['by_phase']:
    if r['phase']==name:
        print(r.get('catches_per_match'), r.get('n_matches')); break
else:
    print('None None')
"
}
read -r FBP_U_C FBP_U_N < <(fld_phase "" powerplay)
read -r FBP_I_C FBP_I_N < <(fld_phase "inning=1" powerplay)
echo "  powerplay unfiltered: catches/m=$FBP_U_C n_matches=$FBP_U_N"
echo "  powerplay inning=1:   catches/m=$FBP_I_C n_matches=$FBP_I_N"
if [[ -z "$FBP_I_N" || "$FBP_I_N" == "None" ]]; then
  bad "fielding by-phase inning=1: n_matches null"
elif [[ "$FBP_I_N" != "$FBP_U_N" ]]; then
  ok "fielding by-phase cohort narrowed (n_matches $FBP_U_N -> $FBP_I_N; catches/m $FBP_U_C -> $FBP_I_C)"
else
  bad "fielding by-phase cohort FROZEN (n_matches=$FBP_I_N == $FBP_U_N) -- 3e not wired"
fi

# ── §13 batting By Position bars narrow under the six (Tier-3 Phase B) ──
# /batters/{id}/summary position_distribution[] — the By Position tab.
# Tier-3 sweep: the player's OWN per-position performance (runs → SR/avg
# bars) AND the cohort per-position bars narrow under the six; the MIX
# histogram (innings per bucket = the weighting) STAYS COARSE. Anchor:
# Kohli men's international, opener bucket (1), inning=0.
echo
echo "=== batting By Position bars narrow, mix stays coarse (Phase B) ==="
bp_pos1() {  # $1=filter → "innings own_runs cohort_sr"
  curl -s "$API/api/v1/batters/ba607b88/summary?gender=male&team_type=international&$1" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
op=[e for e in d['position_distribution'] if e['bucket']==1]
if not op: print('None None None'); raise SystemExit
e=op[0]
print(e['innings'], e['runs'], e.get('cohort_strike_rate'))
"
}
read -r BPP_U_INN BPP_U_RUNS BPP_U_CSR < <(bp_pos1 "")
read -r BPP_I_INN BPP_I_RUNS BPP_I_CSR < <(bp_pos1 "inning=0")
echo "  opener unfiltered: innings(mix)=$BPP_U_INN own_runs=$BPP_U_RUNS cohort_SR=$BPP_U_CSR"
echo "  opener inning=0:   innings(mix)=$BPP_I_INN own_runs=$BPP_I_RUNS cohort_SR=$BPP_I_CSR"
# (a) own performance narrows
if [[ "$BPP_I_RUNS" != "None" && "$BPP_I_RUNS" != "$BPP_U_RUNS" ]]; then
  ok "By Position own runs narrowed ($BPP_U_RUNS -> $BPP_I_RUNS)"
else
  bad "By Position own runs FROZEN ($BPP_U_RUNS == $BPP_I_RUNS) -- Phase B not wired"
fi
# (b) cohort bar narrows
if [[ "$BPP_I_CSR" != "None" && "$BPP_I_CSR" != "$BPP_U_CSR" ]]; then
  ok "By Position cohort SR narrowed ($BPP_U_CSR -> $BPP_I_CSR)"
else
  bad "By Position cohort SR FROZEN ($BPP_U_CSR == $BPP_I_CSR) -- Phase B not wired"
fi
# (c) mix histogram (innings) STAYS COARSE (Tier-2-keep)
if [[ "$BPP_I_INN" == "$BPP_U_INN" ]]; then
  ok "By Position mix histogram stayed coarse (innings $BPP_U_INN == $BPP_I_INN)"
else
  bad "By Position mix histogram narrowed (innings $BPP_U_INN -> $BPP_I_INN) -- should stay coarse"
fi
# SQL anchor: opener inning=0 own runs == direct inningsbatterperf agg
# (batted first → innings_number=0, position_bucket=1).
BPP_EXPECTED=$(sqlite3 cricket.db "SELECT COALESCE(SUM(ibp.runs),0) FROM inningsbatterperf ibp JOIN innings i ON i.id=ibp.innings_id JOIN match m ON m.id=i.match_id WHERE ibp.batter_id='ba607b88' AND ibp.position_bucket=1 AND m.gender='male' AND m.team_type='international' AND i.super_over=0 AND i.innings_number=0;")
echo "  SQL-anchored opener inning=0 own runs: $BPP_EXPECTED  (API: $BPP_I_RUNS)"
if [[ "$BPP_I_RUNS" == "$BPP_EXPECTED" ]]; then
  ok "By Position own runs == SQL-anchored ($BPP_I_RUNS)"
else
  bad "By Position own runs=$BPP_I_RUNS != SQL-anchored $BPP_EXPECTED"
fi

# ── §14 bowling By Over bars narrow, over-mix stays coarse (Phase B) ──
# /bowlers/{id}/summary over_distribution[] — the By Over tab. Tier-3:
# the bowler's OWN per-over economy AND the cohort per-over economy narrow
# under the six; the over-mix histogram (mix_legal_balls = legal balls per
# over, the weighting) STAYS COARSE (D-B2/D-B3). Anchor: Bumrah IPL, over 6,
# inning=0 (bowled first → bowling innings_number=1).
echo
echo "=== bowling By Over bars narrow, over-mix stays coarse (Phase B) ==="
bo_over6() {  # $1=filter → "mix_balls own_balls own_econ cohort_econ"
  curl -s "$API/api/v1/bowlers/462411b3/summary?gender=male&team_type=club&tournament=Indian+Premier+League&$1" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
o=[e for e in d['over_distribution'] if e['over']==6]
if not o: print('None None None None'); raise SystemExit
e=o[0]
econ = round(e['runs_conceded']*6/e['legal_balls'],2) if e['legal_balls'] else None
print(e.get('mix_legal_balls'), e['legal_balls'], econ, e.get('cohort_economy'))
"
}
read -r BO_U_MIX BO_U_BALLS BO_U_E BO_U_CE < <(bo_over6 "")
read -r BO_I_MIX BO_I_BALLS BO_I_E BO_I_CE < <(bo_over6 "inning=0")
echo "  over6 unfiltered: mix_balls=$BO_U_MIX own_balls=$BO_U_BALLS own_econ=$BO_U_E cohort_econ=$BO_U_CE"
echo "  over6 inning=0:   mix_balls=$BO_I_MIX own_balls=$BO_I_BALLS own_econ=$BO_I_E cohort_econ=$BO_I_CE"
# (a) own economy narrows
if [[ "$BO_I_E" != "None" && "$BO_I_E" != "$BO_U_E" ]]; then
  ok "By Over own economy narrowed ($BO_U_E -> $BO_I_E)"
else
  bad "By Over own economy FROZEN ($BO_U_E == $BO_I_E) -- Phase B not wired"
fi
# (b) cohort economy narrows
if [[ "$BO_I_CE" != "None" && "$BO_I_CE" != "$BO_U_CE" ]]; then
  ok "By Over cohort economy narrowed ($BO_U_CE -> $BO_I_CE)"
else
  bad "By Over cohort economy FROZEN ($BO_U_CE == $BO_I_CE) -- Phase B not wired"
fi
# (c) over-mix (mix_legal_balls) STAYS COARSE
if [[ "$BO_I_MIX" == "$BO_U_MIX" ]]; then
  ok "By Over over-mix stayed coarse (mix_balls $BO_U_MIX == $BO_I_MIX)"
else
  bad "By Over over-mix narrowed (mix_balls $BO_U_MIX -> $BO_I_MIX) -- should stay coarse"
fi
# SQL anchor: own over-6 economy inning=0 == direct delivery agg at
# innings_number=1 (bowled first), over_number=5.
BO_EXPECTED=$(sqlite3 cricket.db "SELECT ROUND(SUM(d.runs_total)*6.0/SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END),2) FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE d.bowler_id='462411b3' AND d.over_number=5 AND m.gender='male' AND m.team_type='club' AND m.event_name='Indian Premier League' AND i.super_over=0 AND i.innings_number=1;")
echo "  SQL-anchored over6 inning=0 own econ: $BO_EXPECTED  (API: $BO_I_E)"
if [[ "$BO_I_E" == "$BO_EXPECTED" ]]; then
  ok "By Over own economy == SQL-anchored ($BO_I_E)"
else
  bad "By Over own economy=$BO_I_E != SQL-anchored $BO_EXPECTED"
fi

# ── §15 fielding By Dismissed Position bars narrow (Phase B) ──
# /fielders/{id}/summary dismissal_position_distribution[] — fielding is
# keeper-binary (no per-position weight), so the WHOLE tab narrows under
# the six: own per-position catches AND cohort bars AND the dismissals
# histogram (owner decision 2026-05-29). Per-match denom = matches_fielded
# (denominator B, both sides). Anchor: Dhoni men's intl, bucket 1 (openers),
# inning=0 (fielded first → fielding innings_number=1).
echo
echo "=== fielding By Dismissed Position bars narrow (Phase B) ==="
fd_b1() {  # $1=filter → "matches_fielded dismissals catches cohort_cpm"
  curl -s "$API/api/v1/fielders/4a8a2e3b/summary?gender=male&team_type=international&$1" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
mf=d.get('matches_fielded',{}).get('value')
b=[x for x in d['dismissal_position_distribution'] if x['bucket']==1]
if not b: print('None None None None'); raise SystemExit
e=b[0]
print(mf, e['dismissals'], e['catches'], e.get('cohort_catches_per_match'))
"
}
read -r FD_U_MF FD_U_DIS FD_U_C FD_U_CC < <(fd_b1 "")
read -r FD_I_MF FD_I_DIS FD_I_C FD_I_CC < <(fd_b1 "inning=0")
echo "  b1 unfiltered: matches_fielded=$FD_U_MF dismissals=$FD_U_DIS catches=$FD_U_C cohort_cpm=$FD_U_CC"
echo "  b1 inning=0:   matches_fielded=$FD_I_MF dismissals=$FD_I_DIS catches=$FD_I_C cohort_cpm=$FD_I_CC"
if [[ "$FD_I_C" != "None" && "$FD_I_C" != "$FD_U_C" ]]; then
  ok "By Dismissed Position own catches narrowed ($FD_U_C -> $FD_I_C)"
else
  bad "By Dismissed Position own catches FROZEN ($FD_U_C == $FD_I_C) -- Phase B not wired"
fi
if [[ "$FD_I_CC" != "None" && "$FD_I_CC" != "$FD_U_CC" ]]; then
  ok "By Dismissed Position cohort catches/match narrowed ($FD_U_CC -> $FD_I_CC)"
else
  bad "By Dismissed Position cohort FROZEN ($FD_U_CC == $FD_I_CC) -- Phase B not wired"
fi
if [[ "$FD_I_DIS" != "None" && "$FD_I_DIS" != "$FD_U_DIS" ]]; then
  ok "By Dismissed Position histogram narrowed (dismissals $FD_U_DIS -> $FD_I_DIS)"
else
  bad "By Dismissed Position histogram FROZEN ($FD_U_DIS == $FD_I_DIS) -- should narrow (no weight)"
fi
FD_EXPECTED=$(sqlite3 cricket.db "SELECT COUNT(*) FROM fieldingcredit fc JOIN delivery d ON d.id=fc.delivery_id JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id JOIN wicket w ON w.id=fc.wicket_id JOIN inningsbatterperf ibp ON ibp.innings_id=i.id AND ibp.batter_id=w.player_out_id WHERE fc.fielder_id='4a8a2e3b' AND fc.kind IN ('caught','caught_and_bowled') AND COALESCE(fc.is_substitute,0)=0 AND ibp.position_bucket=1 AND m.gender='male' AND m.team_type='international' AND i.super_over=0 AND i.innings_number=1;")
echo "  SQL-anchored b1 inning=0 own catches: $FD_EXPECTED  (API: $FD_I_C)"
if [[ "$FD_I_C" == "$FD_EXPECTED" ]]; then
  ok "By Dismissed Position own catches == SQL-anchored ($FD_I_C)"
else
  bad "By Dismissed Position own catches=$FD_I_C != SQL-anchored $FD_EXPECTED"
fi

# ── §16 batting By Over cohort reference line narrows (Phase B) ──
# /scope/averages/players/batting/by-over — the green SR/dot%/boundaries
# reference line on the batting By Over chart. Read a scope-key-only table
# (frozen) until Phase B; now the per-over cohort rates narrow live over
# delivery (batting orientation). The player's OWN bars already narrow.
# Over-MIX (ball_mix) stays coarse. Anchor: Kohli men's intl, over 1, inning=0.
echo
echo "=== batting By Over cohort reference line narrows (Phase B) ==="
bbo_over1() {  # $1=filter → "cohort_sr n_balls"
  curl -s "$API/api/v1/scope/averages/players/batting/by-over?person_id=ba607b88&gender=male&team_type=international&$1" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
o=[x for x in d['by_over'] if x['over']==1]
if not o: print('None None'); raise SystemExit
print(o[0].get('strike_rate'), o[0].get('n_balls'))
"
}
read -r BBO_U_SR BBO_U_N < <(bbo_over1 "")
read -r BBO_I_SR BBO_I_N < <(bbo_over1 "inning=0")
echo "  over1 unfiltered: cohort_SR=$BBO_U_SR n_balls=$BBO_U_N"
echo "  over1 inning=0:   cohort_SR=$BBO_I_SR n_balls=$BBO_I_N"
if [[ "$BBO_I_SR" != "None" && "$BBO_I_SR" != "$BBO_U_SR" ]]; then
  ok "batting By Over cohort SR narrowed ($BBO_U_SR -> $BBO_I_SR)"
else
  bad "batting By Over cohort SR FROZEN ($BBO_U_SR == $BBO_I_SR) -- Phase B not wired"
fi
BBO_EXPECTED=$(sqlite3 cricket.db "SELECT ROUND(SUM(d.runs_batter)*100.0/SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END),1) FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE d.over_number=0 AND d.batter_id IS NOT NULL AND m.gender='male' AND m.team_type='international' AND i.super_over=0 AND i.innings_number=0;")
echo "  SQL-anchored over1 inning=0 cohort SR: $BBO_EXPECTED  (API: $BBO_I_SR)"
if [[ "$BBO_I_SR" == "$BBO_EXPECTED" ]]; then
  ok "batting By Over cohort SR == SQL-anchored ($BBO_I_SR)"
else
  bad "batting By Over cohort SR=$BBO_I_SR != SQL-anchored $BBO_EXPECTED"
fi

# ── §17 fielding By Over cohort line narrows (Phase B) ──
# /fielders/{id}/by-over cohort_dismissals_per_match — the green reference
# line on the fielding By Over chart. Scope-key-only (frozen) until Phase B;
# now narrows live (fielding orientation) + matches_fielded denominator
# (denominator B). The player's OWN per-over bars already narrow. Anchor:
# Dhoni men's intl, over 1 (over_number=0), inning=0 (fielded first → innings 1).
echo
echo "=== fielding By Over cohort line narrows (Phase B) ==="
fbo_over1() {  # $1=filter → "own_dis cohort_dpm"
  curl -s "$API/api/v1/fielders/4a8a2e3b/by-over?gender=male&team_type=international&$1" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
o=[x for x in d['by_over'] if x['over_number']==1]
if not o: print('None None'); raise SystemExit
print(o[0].get('dismissals'), o[0].get('cohort_dismissals_per_match'))
"
}
read -r FBO_U_D FBO_U_C < <(fbo_over1 "")
read -r FBO_I_D FBO_I_C < <(fbo_over1 "inning=0")
echo "  over1 unfiltered: own_dis=$FBO_U_D cohort_dpm=$FBO_U_C"
echo "  over1 inning=0:   own_dis=$FBO_I_D cohort_dpm=$FBO_I_C"
if [[ "$FBO_I_C" != "None" && "$FBO_I_C" != "$FBO_U_C" ]]; then
  ok "fielding By Over cohort dis/match narrowed ($FBO_U_C -> $FBO_I_C)"
else
  bad "fielding By Over cohort dis/match FROZEN ($FBO_U_C == $FBO_I_C) -- Phase B not wired"
fi
FBO_EXPECTED=$(sqlite3 cricket.db "WITH keepers AS (SELECT DISTINCT ka.keeper_id pid FROM keeperassignment ka JOIN innings i ON i.id=ka.innings_id JOIN match m ON m.id=i.match_id WHERE m.gender='male' AND m.team_type='international' AND i.super_over=0 AND i.innings_number=1 AND ka.keeper_id IS NOT NULL), num AS (SELECT COUNT(*) dis FROM fieldingcredit fc JOIN delivery d ON d.id=fc.delivery_id JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE m.gender='male' AND m.team_type='international' AND i.super_over=0 AND i.innings_number=1 AND d.over_number=0 AND fc.fielder_id IS NOT NULL AND COALESCE(fc.is_substitute,0)=0 AND fc.fielder_id IN (SELECT pid FROM keepers)), den AS (SELECT COUNT(*) n FROM matchplayer mp JOIN match m ON m.id=mp.match_id WHERE m.gender='male' AND m.team_type='international' AND mp.person_id IN (SELECT pid FROM keepers) AND EXISTS (SELECT 1 FROM innings i2 WHERE i2.match_id=mp.match_id AND i2.super_over=0 AND i2.team!=mp.team) AND EXISTS (SELECT 1 FROM innings i3 WHERE i3.match_id=mp.match_id AND i3.super_over=0 AND i3.team!=mp.team AND i3.innings_number=1)) SELECT ROUND(CAST(num.dis AS REAL)/den.n,4) FROM num,den;")
echo "  SQL-anchored over1 inning=0 cohort dis/match: $FBO_EXPECTED  (API: $FBO_I_C)"
if [[ "$FBO_I_C" == "$FBO_EXPECTED" ]]; then
  ok "fielding By Over cohort dis/match == SQL-anchored ($FBO_I_C)"
else
  bad "fielding By Over cohort dis/match=$FBO_I_C != SQL-anchored $FBO_EXPECTED"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
