#!/usr/bin/env python3
"""RE-AUDIT v2 — robust, no positional extraction.
- tile: read value + scope_avg scalars directly.
- array: build a KEY->value map (season/phase/over/inning_no keyed) and say
  'narrows' iff the map actually differs between no-filter and the filter.
This can't be fooled by row reordering/dropping (the bug in v1).
Prints, per surface: VALUE narrows (inn/toss/res) and BASELINE narrows.
"""
import json, urllib.request, urllib.parse as up

API="http://localhost:8000"
CSK=up.quote("Chennai Super Kings"); IPL=up.quote("Indian Premier League"); WANK=up.quote("Wankhede Stadium")
KOHLI="ba607b88"; BUMRAH="462411b3"
AUX=[("inn","inning=0"),("toss","toss_outcome=won"),("res","result=won")]

def get(u):
    try:
        with urllib.request.urlopen(u,timeout=25) as r: return json.load(r)
    except Exception as e: return {"__err__":str(e)}
def rnd(v): return round(v,3) if isinstance(v,(int,float)) else v
def scal(d,path):
    cur=d
    for p in path.split("."):
        cur = cur.get(p) if isinstance(cur,dict) else None
        if cur is None: return None
    return rnd(cur)

def amap(d, listkey, keyf, valf):
    """build {key: rounded value} from an array; robust to order.
    listkey may be a '|'-separated list of candidate keys (endpoints
    disagree: team uses 'seasons', player uses 'by_season')."""
    s = []
    for cand in listkey.split("|"):
        if isinstance(d.get(cand), list) and d.get(cand):
            s = d[cand]; break
    out={}
    for r in s:
        if not isinstance(r,dict): continue
        k = r.get(keyf)
        v = r.get(valf)
        if isinstance(v,dict): v=v.get("value")
        out[str(k)] = rnd(v)
    return out

def diff(a,b):  # True if changed (narrows)
    if a is None and b is None: return "?"
    return "✓" if a!=b else "✗"

print("## TILES (scalar value + scope_avg baseline) — robust\n")
print(f"{'surface':<46}{'VALUE inn/toss/res':<22}{'BASELINE inn/toss/res':<22}")
TILES=[
 ("TEAM Header Win%",            f"{API}/api/v1/teams/{CSK}/summary?gender=male","win_pct.value","win_pct.scope_avg"),
 ("TEAM Batting run_rate",       f"{API}/api/v1/teams/{CSK}/batting/summary?gender=male","run_rate.value","run_rate.scope_avg"),
 ("TEAM Bowling economy",        f"{API}/api/v1/teams/{CSK}/bowling/summary?gender=male","economy.value","economy.scope_avg"),
 ("TEAM Fielding catches/match", f"{API}/api/v1/teams/{CSK}/fielding/summary?gender=male","catches_per_match.value","catches_per_match.scope_avg"),
 ("TEAM Partnerships avg_runs",  f"{API}/api/v1/teams/{CSK}/partnerships/summary?gender=male","avg_runs.value","avg_runs.scope_avg"),
 ("PLAYER bat strike_rate",      f"{API}/api/v1/batters/{KOHLI}/summary?gender=male","strike_rate.value","strike_rate.scope_avg"),
 ("PLAYER bat average",          f"{API}/api/v1/batters/{KOHLI}/summary?gender=male","average.value","average.scope_avg"),
 ("PLAYER bowl economy",         f"{API}/api/v1/bowlers/{BUMRAH}/summary?gender=male","economy.value","economy.scope_avg"),
 ("PLAYER field catches/match",  f"{API}/api/v1/fielders/{KOHLI}/summary?gender=male","catches_per_match.value","catches_per_match.scope_avg"),
]
for name,base,vp,bp in TILES:
    sep="&" if "?" in base else "?"
    n=get(base); nv=scal(n,vp); nb=scal(n,bp)
    vs=[]; bs=[]
    for ak,av in AUX:
        d=get(f"{base}{sep}{av}")
        vs.append(diff(scal(d,vp),nv)); bs.append(diff(scal(d,bp),nb))
    print(f"{name:<46}{'/'.join(vs):<22}{'/'.join(bs):<22}")

print("\n## ARRAYS (season/phase/over/inning keyed map; narrows = map differs) — robust\n")
print(f"{'surface':<52}{'MAP narrows inn/toss/res':<26}")
ARRAYS=[
 ("TEAM bowling by-season (cohort? team value)", f"{API}/api/v1/teams/{CSK}/bowling/by-season?gender=male","seasons|by_season","season","wickets"),
 ("TEAM bowling by-phase",                       f"{API}/api/v1/teams/{CSK}/bowling/by-phase?gender=male","phases","phase","wickets"),
 ("TEAM bowling by-inning (rows re-filter?)",    f"{API}/api/v1/teams/{CSK}/bowling/by-inning?gender=male","innings","inning_no","wickets"),
 ("TEAMcohort bowling by-season (scope/avg)",    f"{API}/api/v1/scope/averages/bowling/by-season?gender=male&team_type=club&tournament={IPL}","by_season","season","economy"),
 ("TEAMcohort bowling by-phase (scope/avg)",     f"{API}/api/v1/scope/averages/bowling/by-phase?gender=male&team_type=club&tournament={IPL}","by_phase","phase","economy"),
 ("PLAYER bowl by-season (player's own line)",   f"{API}/api/v1/bowlers/{BUMRAH}/by-season?gender=male","by_season|seasons","season","wickets"),
 ("PLAYERcohort bowl by-season (scope/avg)",     f"{API}/api/v1/scope/averages/players/bowling/by-season?person_id={BUMRAH}&gender=male","by_season","season","economy"),
 ("PLAYERcohort bowl by-phase (scope/avg)",      f"{API}/api/v1/scope/averages/players/bowling/by-phase?person_id={BUMRAH}&gender=male","by_phase","phase","economy"),
 ("PLAYERcohort bat by-season (scope/avg)",      f"{API}/api/v1/scope/averages/players/batting/by-season?person_id={KOHLI}&gender=male","by_season","season","strike_rate"),
 ("PLAYERcohort field by-phase (scope/avg)",     f"{API}/api/v1/scope/averages/players/fielding/by-phase?person_id={KOHLI}&gender=male&team_type=international","by_phase","phase","catches_per_match"),
 ("SERIES bowlers-leaders (ranked list)",        f"{API}/api/v1/series/bowlers-leaders?tournament={IPL}&gender=male&team_type=club","by_economy","person_id","wickets"),
 ("VENUE bowlers/leaders (ranked list)",         f"{API}/api/v1/bowlers/leaders?filter_venue={WANK}&gender=male&team_type=club","by_economy","person_id","wickets"),
]
for name,base,lk,kf,vf in ARRAYS:
    sep="&" if "?" in base else "?"
    n=amap(get(base),lk,kf,vf)
    res=[]
    for ak,av in AUX:
        m=amap(get(f"{base}{sep}{av}"),lk,kf,vf)
        res.append("✓" if m!=n else "✗")
    print(f"{name:<52}{'/'.join(res):<26} (n_keys none={len(n)})")

print("\n## PLAYER toss no-op double-check (scalar match count)")
for who,url in [("bat Kohli",f"{API}/api/v1/batters/{KOHLI}/summary?gender=male"),
                ("bowl Bumrah",f"{API}/api/v1/bowlers/{BUMRAH}/summary?gender=male")]:
    n=get(url); base_m=scal(n,"matches.value")
    row=[]
    for ak,av in AUX:
        d=get(f"{url}&{av}"); row.append(f"{ak}={scal(d,'matches.value')}")
    print(f"  {who}: none={base_m} | "+" ".join(row))
