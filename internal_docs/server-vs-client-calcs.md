# Server-vs-client calculation inventory (Phase 1 audit)

> **Status:** Phase 1 of the cricket-invariants audit
> (`project_invariants_audit` memory). NO APP CHANGES — this doc
> only catalogues what's there and flags divergence risk. Phase 2
> (cross-endpoint sanity tests) and Phase 3 (variant matrix tests)
> follow once findings are reviewed.
>
> **Origin:** 2026-05-08 C&B incident. Two distribution endpoints
> silently dropped `caught_and_bowled` from their catches counts;
> /summary and /distribution diverged in semantics for the same
> field name. Goal of this audit: surface the next C&B-style
> divergence before it ships.
>
> **Generated:** 2026-05-09 by walking
> `api/routers/*.py`, `api/wilson.py`, `api/form_windows.py`,
> `api/metrics_metadata.py`, and `frontend/src/components/**/*.tsx`
> (+ pages/Teams.tsx) at HEAD `6a42808`. File:line citations
> below were valid at that commit; check `git blame` if you find a
> drift.

---

## How to read this doc

The audit answers two questions for every derived metric in the
project:

1. **Where is it computed?** — server-side SQL, server-side Python,
   or client-side TypeScript.
2. **Could it diverge from a sibling computation?** — same metric
   computed by another endpoint (server↔server) or by the
   frontend (server↔client).

Each row of the inventory carries a **formula** (math notation) and
a **file:line citation** so you can spot-check.

Sections:
- **§1 Server-side metric inventory** — by router/file, every
  formula and edge-case predicate.
- **§2 Client-side derivation inventory** — by component, what the
  browser computes and from which API fields.
- **§3 Cross-endpoint divergence flags** ⚠️ — same concept,
  different sites; ranked by risk.
- **§4 Server↔client duplication flags** ⚠️ — same value
  recomputed in the browser; divergence risk.
- **§5 Predicate inconsistencies** ⚠️ — same idea (e.g. "dot
  ball"), different SQL across files.
- **§6 Recommendations for Phase 2** — concrete sanity-test
  assertions that would catch each ⚠️ flag.

⚠️ marks divergence-risk findings worth Phase 2 follow-up. Items
without ⚠️ are inventory rows for completeness; the user should
still skim them for unfamiliar formulas.

---

## §1. Server-side metric inventory

### §1.1 Wilson CI helper — `api/wilson.py`

Single source of truth for every probability shipped by a
`/distribution` endpoint.

| Field | Formula | File:line | Edge cases |
|---|---|---|---|
| `value` | `num / denom` | `api/wilson.py:48` | Returns `None` when `denom <= 0` |
| `ci_low`, `ci_high` | Wilson 95% score-test inversion (z=1.96) | `api/wilson.py:16-32` | `(None, None)` when `denom <= 0`; clamped to [0, 1] |
| Rounding | All numerics rounded to 4 dp on the response | `api/wilson.py:50-52` | `round(x, 4)` — banker's rounding |

**Used by:** every `prob_record(num, denom)` call in
`api/routers/{batting,bowling,fielding,teams}.py`. The rounding to
4 dp is what makes the JS `toFixed(1)` boundary-rounding land at
`.5` and produces the binary-float oddities documented in
`tests/integration/batter_distribution.sh` Test 10.

### §1.2 Form-window anchor — `api/form_windows.py`

Computes the cutoff date for last_60d / last_6mo / last_1yr
windows on `/distribution`.

| Field | Formula | File:line |
|---|---|---|
| `scope_anchor(observations, today)` | `min(today, max_obs_date)` (where `max_obs_date` = max date string in observations) | `api/form_windows.py:14-41` |

**Why scope-anchored, not today-anchored:** for retired subjects
(Gayle, ABdV) and tightly-scoped subjects (Kohli@IPL 2016), the
windows mean "the last N calendar days OF SCOPE." Today-direct
cutoffs produced empty windows and were fixed 2026-05-08 — see
CLAUDE.md "Scope-anchored form-window cutoffs."

### §1.3 Batter metrics — `api/routers/batting.py`

| Metric | Endpoint | Formula | File:line | Predicates |
|---|---|---|---|---|
| `average` | `/leaders` | `runs / dismissals` | `batting.py:147` | dismissals > 0; legal balls (extras_wides=0 AND extras_noballs=0); super_over=0 (auto via filters) |
| `strike_rate` | `/leaders` | `runs * 100 / balls` | `batting.py:148` | balls >= min_balls (100 default); legal balls |
| `average` | `/{id}/summary` | `runs / dismissals` | `batting.py:298` | dismissals > 0 |
| `strike_rate` | `/{id}/summary` | `runs * 100 / balls` | `batting.py:299` | legal balls |
| `dot_pct` | `/{id}/summary` | `dots * 100 / balls` (1 dp) | `batting.py:309` | dots predicate `runs_batter=0 AND runs_extras=0` (line 234) |
| `boundary_pct` | `/{id}/summary` | `(fours+sixes) * 100 / balls` (1 dp) | `batting.py:201` | fours: `runs_batter=4 AND COALESCE(runs_non_boundary,0)=0`; sixes: `runs_batter=6` |
| `balls_per_four/_six/_boundary` | `/{id}/summary` | `balls / count` | `batting.py:310-312` | count > 0 |
| `mean_per_innings` | `/{id}/distribution` | `sum(runs) / n_innings` (2 dp) | `batting.py:1089, 1123` | n>=1 → number; n=0 → null |
| `median` | `/{id}/distribution` | `statistics.median(runs_list)` | `batting.py:1090, 1124` | n=0 → null |
| `variance`, `std` | `/{id}/distribution` | `statistics.variance(runs_list)`; `sqrt(variance)` | `batting.py:1092-1093, 1125-1126` | n>=2 → variance; n=1 → 0; n=0 → null |
| `runs.average` | `/{id}/distribution` | `total_runs / n_dismissals` (2 dp) | `batting.py:1094, 1127` | n_dismissals > 0 |
| `p_failure_10` | `/{id}/distribution` | `prob_record(count(runs<=10), n_innings)` | `batting.py:1132` | denom = n_innings |
| `p_25_plus` / `_30_plus` / `_50_plus` / `_100_plus` | `/{id}/distribution` | `prob_record(count(runs>=T), n_innings)` | `batting.py:1133-1136` | denom = n_innings |
| `p_50_given_30` | `/{id}/distribution` | `prob_record(count(>=50), count(>=30))` | `batting.py:1140` | denom = count(>=30); null shape when denom=0 |
| `p_70_given_50` | `/{id}/distribution` | `prob_record(count(>=70), count(>=50))` | `batting.py:1141` | denom = count(>=50); null shape when denom=0 |
| `phase.{powerplay,middle,death}.runs_total` | `/{id}/distribution` | `sum(o.runs_pp/mid/death)` per phase | `batting.py:1110-1114` | Phase ranges: PP=overs 0-5, Mid=6-14, Death=15-19 (0-indexed) |
| `delta.last_10_mean_minus_lifetime` (etc.) | `/{id}/distribution` | `window_mean - lifetime_mean` (2 dp) | `batting.py:1175-1196` | None if either side null |

**Per-innings observation derivation** (`api/routers/batting.py::_per_innings_observations`):
- `strike_rate` per innings = `runs * 100 / balls` — `batting.py:366`
- `dismissed` boolean = wicket row exists for innings, kind ∉ retired

### §1.4 Bowler metrics — `api/routers/bowling.py`

| Metric | Endpoint | Formula | File:line | Predicates |
|---|---|---|---|---|
| `strike_rate` | `/leaders` | `legal_balls / wickets` | `bowling.py:132` | wickets >= min_wickets; **wicket kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')** — bowler is NOT credited for these |
| `economy` | `/leaders` | `runs_conceded * 6 / legal_balls` | `bowling.py:133` | legal_balls >= min_balls (60 default) |
| `average` | `/{id}/summary` | `runs_conceded / wickets` | `bowling.py:387` | wickets > 0 |
| `economy` | `/{id}/summary` | `runs_conceded * 6 / legal_balls` | `bowling.py:388` | legal balls only |
| `strike_rate` | `/{id}/summary` | `legal_balls / wickets` | `bowling.py:389` | wickets > 0 |
| `dot_pct` | `/{id}/summary` | `dots * 100 / balls` (1 dp) | `bowling.py:215, 396` | dots = `runs_total=0` (line 251) — see ⚠️ §5.1 |
| `economy` per spell | `/{id}/by-innings` | `runs_conceded * 6 / balls` | `bowling.py:491` | **all_deliveries** (NOT legal-balls) — note the asymmetry vs /summary |
| Distribution metrics (mean/median/std/p_*/phase/form delta) | `/{id}/distribution` | Analogous to batter, on per-spell `runs_conceded` and `wickets` observations | (analogous lines) | wicket-kind exclusions as above |

### §1.5 Fielder metrics — `api/routers/fielding.py`

| Metric | Endpoint | Formula | File:line | Predicates |
|---|---|---|---|---|
| `catches` | `/leaders` | `count(fc.kind IN ('caught','caught_and_bowled'))` | `fielding.py:96` | ✅ INCLUSIVE per Convention 3 (post-2026-05-09) |
| `c_and_b` | `/leaders` | `count(fc.kind = 'caught_and_bowled')` | `fielding.py:99` | exposed as sibling — total = catches+stumpings+run_outs+c_and_b |
| `stumpings` | `/leaders` | `count(fc.kind = 'stumped')` | `fielding.py:97` | |
| `run_outs` | `/leaders` | `count(fc.kind = 'run_out')` | `fielding.py:98` | |
| `total_dismissals` | `/{id}/summary` | `catches + stumpings + run_outs + caught_and_bowled` | `fielding.py:222` | siblings sum cleanly because `catches` here is non-inclusive |
| `dismissals_per_match` | `/{id}/summary` | `total_dismissals / matches` | `fielding.py:275` | matches > 0 |
| `substitute_catches` | `/{id}/summary` | `count(kind='caught' AND is_substitute=1)` | `fielding.py:212` | reconciliation scalar; NOT included in `catches` |
| `catches.total` | `/{id}/distribution` | `sum_per_innings(count(kind IN ('caught','caught_and_bowled') AND is_substitute=0))` | `api/routers/fielding.py` distribution slice | ✅ INCLUSIVE per Convention 3 (post-2026-05-08 fix) |

### §1.6 Keeper metrics — `api/routers/keeping.py`

| Metric | Endpoint | Formula | File:line | Predicates |
|---|---|---|---|---|
| `keeping_catches` | `/keeping/summary` | `count(kind IN ('caught','caught_and_bowled'))` | `keeping.py:113` | ✅ INCLUSIVE per Convention 3 (sibling `/fielders/{id}/summary` also inclusive post-2026-05-09 §3.1) |
| `byes_per_innings` | `/keeping/summary` | `byes_conceded / innings_kept` | `keeping.py:170` | innings_kept > 0 |
| `keeping_dismissals_per_innings` | `/keeping/summary` | `(stumpings + keeping_catches + run_outs) / innings_kept` | `keeping.py:172` | innings_kept > 0 |

### §1.7 Team metrics — `api/routers/teams.py`

| Metric | Endpoint | Formula | File:line | Predicates |
|---|---|---|---|---|
| `win_pct` | `/{team}/summary` | `wins * 100 / matches` (1 dp) | `teams.py:299` | matches > 0; outcome_winner = team |
| `bat_first_win_pct` | (scope_averages) | `bat_first_wins * 100 / decided` | `scope_averages.py:169, 224` | decided > 0 (excludes ties + no-results) |
| Scope envelope — `s_matches`, `s_decided`, `s_win_pct` | `/{team}/summary` | Per-team divisor: `pool_value / unique_teams` (×2 for match-count metrics — see `how-stats-calculated.md §Per-TEAM`) | `teams.py:350-369` | unique_teams > 0 — see §1.10 caveat |
| `win_pct` | `/{team}/vs/{opponent}` | `wins * 100 / matches` | `teams.py:695` | matches > 0; both teams in match |
| `win_pct` (per cell) | `/opponents-matrix` | `wins * 100 / matches` | `teams.py:733` | matches > 0 |
| `run_rate` | `/teams/{team}/batting/summary` | `runs * 6 / legal_balls` (envelope value) | `api/routers/teams.py` (delegates to scope_averages helpers) | legal_balls > 0 |
| `boundary_pct`, `dot_pct` | `/teams/{team}/batting/summary` | Same as batter | (same) | (same) |
| `avg_1st_innings_total`, `avg_2nd_innings_total` | `/teams/{team}/batting/summary` | `sum(1st-inn-runs) / count(1st-innings)`; same for 2nd | (analogous in scope_averages.py) | inning-aware; null when no innings of that side |

### §1.8 Scope-averages — `api/routers/scope_averages.py`

The dual-query pattern: compute the metric on `team=None` (whole
scope = league baseline) vs `team=:team` (this team) and return
both in the envelope. Used by every `MetricEnvelope` field
across `/summary` endpoints.

| Concept | Formula | File:line |
|---|---|---|
| `scope_avg` (league side of envelope) | Same formula as the value, run with `team=None` filter | `scope_averages.py:184-236` |
| `delta_pct` (server-computed, not in this router) | `(value - scope_avg) / scope_avg * 100` (1 dp) | `api/metrics_metadata.py::wrap_metric` |
| `direction` | Map lookup `METRIC_DIRECTIONS[key]` → 'higher_better' / 'lower_better' / None | `api/metrics_metadata.py` |
| Per-team normalization (`s_matches`, etc.) | `pool / unique_teams` (or ×2 for match counts) | `scope_averages.py::_apply_results_per_team` |
| Per-innings normalization (batting) | `pool_runs_in_phase / innings_in_phase` | `scope_averages.py::_apply_batting_per_innings` |

**Variants covered:** `gender`, `team_type`, `tournament`,
`season_from`/`_to`, `filter_team`, `filter_opponent`,
`filter_venue`, `team_class`, `series_type`, `inning` (aux). All
flow through `api/filters.py::FilterParams.build()`.

### §1.9 MetricDelta envelope helper — `api/metrics_metadata.py`

Every `MetricEnvelope` field on a `/summary` response comes from
`wrap_metric(value, scope_avg, key, sample_size)`:

| Field | Formula | File:line |
|---|---|---|
| `delta_pct` | `(value - scope_avg) / scope_avg * 100` (1 dp) | `api/metrics_metadata.py::wrap_metric` |
| `direction` | `METRIC_DIRECTIONS.get(key)` | (same) |
| Null behavior | Returns `delta_pct = None` if `value`, `scope_avg`, or `direction` is None, OR if direction is the informational sentinel (count metrics like `n_innings`) | (same) |

### §1.10 Filter-injection invariants — `api/filters.py`

Predicates injected automatically by `FilterParams.build()`:

| Predicate | When applied | File:line |
|---|---|---|
| `i.super_over = 0` | Whenever `has_innings_join=True` | `api/filters.py:245` |
| `m.gender = :gender` | When gender param set | `api/filters.py:248-251` |
| `m.team_type = :team_type` | When team_type param set | `api/filters.py:252-255` |
| `m.event_name IN (...)` (canonical-tournament expansion) | When tournament param set | `api/filters.py:259-264` |
| `m.season >= / <= :season` | When season_from / season_to set | (later in same method) |
| Team / opponent / venue filters | Per-param, with innings-level vs match-level semantics depending on `has_innings_join` | (same) |

**What's NOT auto-injected:**
- DLS (target_runs / target_overs columns): no router currently
  filters or branches on these. ⚠️ verify in §3.5.
- Forfeited / declared innings (`i.forfeited`, `i.declared`):
  no auto-filter.
- Substitute fielders (`fc.is_substitute`): each fielding query
  applies it explicitly; verify per-call-site.

---

## §2. Client-side derivation inventory

### §2.1 Probability chip rendering — `components/distribution/ProbChip.tsx`

| What's rendered | Formula | File:line |
|---|---|---|
| Percentage value | `(record.value * 100).toFixed(0) + '%'` | `ProbChip.tsx:42` |
| Tooltip text | `` `95% CI [${(ci_low*100).toFixed(1)}–${(ci_high*100).toFixed(1)}], n=${denom}` `` | `ProbChip.tsx:47-49` |
| Null handling | `value=null` or `denom<=0` → "—"; tooltip → "n=0 (no qualifying innings)" | `ProbChip.tsx:46, 53` |
| Low-n fade | `denom < smallNFloor` (default 10) → opacity 0.55 | `ProbChip.tsx:54, 65` |

⚠️ JS `Number.toFixed(1)` operates on the raw IEEE 754 double, which for some 4dp-rounded API values lands a hair below or above the printed `.5` decimal. Python `%.1f` and `Decimal HALF_UP` will disagree on these values — see `tests/integration/batter_distribution.sh` Test 10 for the JS-on-both-sides workaround.

### §2.2 Batter Distribution panel — `components/batting/`

| What's rendered | Formula | File:line | API field used |
|---|---|---|---|
| Career SR (Strike-Rate tab) | `runs.total * 100 / runs.balls_total` (2 dp) | `BatterDistributionPanel.tsx:85` | `lifetime.runs.total`, `lifetime.runs.balls_total` |
| Per-innings SR for SR-tab observations | `o.runs * 100 / o.balls` (1 dp; 0 if `balls=0`) | `BatterDistributionPanel.tsx:124-128`, `distributionBins.ts:82-84` | `observations[].runs`, `observations[].balls` |
| SR distribution mean / median / std (SR-tab) | Mean `Σ srs / n`; median sorted-middle; std `sqrt(Σ(x-mean)² / (n-1))` | `BatterDistributionPanel.tsx:124-174` | derived from per-innings SR list |
| CV (Coefficient of Variation) | `std / mean` if both > 0 else null | `DistributionStatStrip.tsx:57-59` | `runs.std`, `runs.mean_per_innings` |
| Runs-bin index (histogram) | `Math.floor(runs / 10)` clamped to [0, 20] | `distributionBins.ts:31-35` | `observations[].runs` |
| Runs-bin tier ("failure" / "building" / "impact") | `idx===0 ? 'failure' : idx<5 ? 'building' : 'impact'` | `distributionBins.ts:45-49` | (same) |
| SR-bin index | `Math.floor(sr / 25)` clamped to [0, 8] | `distributionBins.ts:63-67` | per-innings SR |
| SR-bin tier ("slow" / "mid" / "explosive") | `idx<4 ? 'slow' : idx<6 ? 'mid' : 'explosive'` (thresholds at SR 100, SR 150) | `distributionBins.ts:75-79` | (same) |

### §2.3 Bowler Distribution panel — `components/bowling/`

| What's rendered | Formula | File:line | API field used |
|---|---|---|---|
| Pool SR (balls/wkt) | `(runs_conceded.total * 6) / economy.pool / wickets.total` | `BowlerStatStrips.tsx` (and `TeamBowlingStatStrips.tsx:86-88`) | `runs_conceded.total`, `economy.pool`, `wickets.total` |
| Per-spell economy | `runs_conceded * 6 / balls` (2 dp; 0 if balls=0) | `BowlerDistributionPanel.tsx:114` | `observations[].runs_conceded`, `observations[].balls` |
| Wickets-bin index | `w >= 6 ? 6 : max(0, w)` | `bowling/distributionBins.ts:27-31` | `observations[].wickets` |
| Wickets-bin tier | `idx===0 ? 'wicketless' : idx<=2 ? 'building' : 'strike'` | `bowling/distributionBins.ts:38-42` | (same) |
| Economy-bin tier | `rpo<7 ? 'tight' : rpo<9 ? 'mid' : 'loose'` | `bowling/distributionBins.ts:144-148` | per-spell economy |

### §2.4 Team Batting / Bowling / Fielding panels — `components/teams-distribution/`

| What's rendered | Formula | File:line | API field used |
|---|---|---|---|
| Pool SR (balls/wkt) on Wickets strip | `(runs_conceded_total * 6) / economy_pool / block.total` | `TeamBowlingStatStrips.tsx:85-88` | (same as bowler) |
| Avg innings total (StatCard) | `total_runs.value / innings_batted.value` (1 dp) | `Teams.tsx:651-653` | `total_runs.value`, `innings_batted.value` |
| Avg-innings-total subtitle (`MetricDelta withScopeAvg`) | Synthetic envelope: `value=runs/innings`, `scope_avg=total_runs.scope_avg` (server), `delta_pct=(value-scope_avg)/scope_avg*100` | `Teams.tsx:654-674` | mixes client value with server `scope_avg` |
| Milestone ratio (50s+100s)/innings | `(fifties + centuries) / innings_batted` | `Teams.tsx:631-632` | summary fields |
| Wickets-per-innings by phase | `wickets_lost / innings_batted` | `Teams.tsx:710-712` | summary phase fields |
| Team RR tier (FLIPPED polarity vs bowler) | `rr<7 ? 'low' : rr<9 ? 'mid' : 'high'` (high = good for batter) | `teams-distribution/distributionBins.ts:110-114` | per-innings RR |

### §2.5 Sparkline rendering — `components/distribution/DistributionSparkline.tsx`

| What's rendered | Formula | File:line |
|---|---|---|
| Bar y-coordinate | `baselineY - (v / max) * valueZone` where `max = max(dataMax, globalRef, playerRef, leagueRef)` | `DistributionSparkline.tsx:118-139` |
| Bar width | `VB_W / points.length` | `DistributionSparkline.tsx:118-139` |
| Rolling-N mean overlay | At each i ≥ N-1: `Σ(points[i-N+1..i].value) / N` | `DistributionSparkline.tsx:127-139` |
| Reference-line stroke colors | `playerRef='#1A1714'`, `globalRef='#8A7D70'`, `leagueRef='#3F7A4D'`, `rolling='#7A1F1F'` (oxblood) | (same component) |

### §2.6 Dormancy badge — `components/DormancyContext.tsx`

| What's rendered | Formula | File:line |
|---|---|---|
| Days-since-last-match | `Math.floor((today - lastMatchDate) / 86400000)` | `DormancyContext.tsx:49-58` |
| Months-text (61–364 days) | `Math.max(2, Math.round(gapDays / 30.5))` + " months since last match" | `DormancyContext.tsx:72-96` |
| Calendar form (≥365 days) | `MONTHS[d.getUTCMonth()] + ' ' + d.getUTCFullYear()` | `DormancyContext.tsx` (same block) |
| Hidden | gap ≤ 60 days → null | (same) |

### §2.7 ScopeStatusStrip + abbreviateScope — `components/`

| What's rendered | Formula | File:line |
|---|---|---|
| Derived "all-time" season range | `seasons[0]` and `seasons[seasons.length-1]` joined with `–` (or single value if equal) | `ScopeStatusStrip.tsx:201-208` |
| Abbreviated scope text (page header) | Composition of every scope axis (gender/tournament/team_type/seasons/team_class/inning/...) | `scopeLinks.ts:177-223` |

⚠️ `inning` is an AuxParam, not in `FILTER_KEYS` — but IS included
in abbreviation. Per CLAUDE.md the post-2026-05-06 audit pattern:
"for every axis in `FilterParams`, ask 'does setting this change
what data is shown?' If yes, it's in scope and belongs in the
abbreviation."

### §2.8 MetricDelta — `components/MetricDelta.tsx`

| What's rendered | Formula | File:line |
|---|---|---|
| Delta arrow | `d > 0 ? '↑' : d < 0 ? '↓' : '·'` (server-supplied `env.delta_pct`) | `MetricDelta.tsx:24-31` |
| Delta value text | `env.delta_pct.toFixed(1) + '%'` | `MetricDelta.tsx:33, 47` |
| Color | `direction='higher_better'` × `d>0` → green; `lower_better` × `d>0` → oxblood | (same) |

`delta_pct` is **server-computed** in the standard envelope path
(`api/metrics_metadata.py::wrap_metric`). Exception: the
"Avg innings total" subtitle on `Teams.tsx:654-674` builds a
**synthetic envelope** with client-computed `value` + client-
computed `delta_pct` — see ⚠️ §4.2.

---

## §3. Cross-endpoint divergence flags ⚠️

Same metric, multiple endpoints. Ranked by user-impact risk.

### §3.1 ✅ RESOLVED 2026-05-09 — `catches` now inclusive across all fielding endpoints

**Resolution:** every fielding endpoint that surfaces a `catches`
headline now uses `count(kind IN ('caught','caught_and_bowled'))`
per CLAUDE.md Convention 3. `caught_and_bowled` is exposed as a
sibling sub-count for transparency. Backend change in commit
`5b52fd9`; frontend de-double-count fix in `0b541f5`.

**Live evidence — Bumrah's all-scope fielding summary:**
```
Pre-fix:  catches=27, caught_and_bowled=10, total=43
          (user reading `summary.catches` undercounts by 10)
Post-fix: catches=37, caught_and_bowled=10, total=43
          (user reads inclusive 37; sub-count visible in c_and_b)
```

**Pages now showing the corrected number:**
- `/fielding?player=X` page-header "Catches" StatCard
- `/players?player=X` Players-page summary row
- `/series` Fielders sub-tab leaderboards
- Tournament dossier "best fielding in single match"

**Endpoint coverage (all updated):**
- `api/routers/fielding.py`: `/leaders`, `/{id}/summary`,
  `/by-season`, `/by-phase`, `/by-innings` (paired SQL+python
  collapse), `/keeping/leaders` (cosmetic — keepers don't bowl).
- `api/routers/tournaments.py`: `/series/fielders-leaders`
  (by_dismissals + by_run_outs + by_keeper_dismissals),
  best-fielding-in-single-match, /tournament-personal-fielding.

**Substitute exception preserved.** `fielding.py:712` substitute
catches predicate still uses `kind = 'caught'` only — substitutes
can't bowl by Law (per CLAUDE.md exception note). Zero functional
impact.

**Tested by:** `tests/sanity/test_catches_convention3.py` —
algebraic identity simplified to
`summary.catches - distribution.substitute_catches == distribution.catches.total`
plus Convention 3 lock-down `summary.catches >= summary.caught_and_bowled`
on every (player, scope) tuple including Bumrah. 51 pass.

**Regression coverage:** 33 URL flips (REG→NEW→REG dance) across
`tests/regression/fielding/urls.txt` and
`tests/regression/players/urls.txt`. 0 REG drifted post-fix; new
shape locked.

### §3.2 ✅ RESOLVED 2026-05-09 — `dots` predicate canonicalised

**Resolution:** all 14 inline-variant dots predicates across
`api/routers/{batting,bowling,head_to_head}.py` converted to the
canonical defensive form already used by 14 other sites in
`teams.py`, `scope_averages.py`, `venues.py`, `tournaments.py`:

```sql
SUM(CASE WHEN d.runs_total = 0
         AND d.extras_wides = 0
         AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS dots
```

The canonical form is self-documenting (any reader sees
"no run AND not a wide AND not a noball" → unambiguous "legal
dot ball") and robust to a hypothetical schema change that splits
`runs_total` into multiple components. Equivalence to the prior
forms is locked by `tests/sanity/test_predicate_invariants.py`
(asserts the three variant forms count identical rows on the
current DB).

**Sites converted:**
- `batting.py` 6 SQL sites (5 + 1 in distribution path)
- `bowling.py` 6 SQL sites (the bare `runs_total = 0` form)
- `head_to_head.py` 1 site
- `bowling.py:974` already canonical (clauses reordered, semantically identical)

**Regression:** 0 REG drifted across batting + bowling + head_to_head
(118 REG matched). Pure refactor — no response-shape or value
changes; just the SQL text.

**Backstop:** `tests/sanity/test_predicate_invariants.py` continues
to assert all three predicate forms count identical rows. Any
future drift surfaces immediately.

### §3.3 ❌ NOT A BUG (audit error, retracted 2026-05-09)

**Original Phase-1 claim:** `/bowlers/{id}/by-innings.economy` uses
all-deliveries denominator, `/summary.economy` uses legal-balls
→ different numbers for wide-heavy bowlers.

**Verification (2026-05-09):** FALSE. Both endpoints use legal balls.
The audit-generating Explore agent saw `_safe_div(runs, balls, 6)`
at `bowling.py:491` and assumed `balls` was all-deliveries — but
the SQL upstream at `bowling.py:451` aliases:
```sql
SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
         THEN 1 ELSE 0 END) as balls
```
i.e. `balls` IS already legal-balls. The python local variable
name is misleading but the value is correct.

**Live evidence (Bumrah recent spells):** every per-innings
`economy` value matches `runs * 6 / legal_balls` exactly across
10 spells; none match the all-deliveries formula.

```
date         runs balls wides   API_econ  legal_calc  all_calc
2026-03-08    15    24     1     3.75       3.75       3.6
2026-03-05    33    24     1     8.25       8.25       7.92
2026-02-22    15    24     0     3.75       3.75       3.75
...
```

**Lesson:** the Phase-1 inventory agent read variable names without
tracing back to the SQL aliases. The audit doc baked in this error;
my own follow-up explanation perpetuated it. CLAUDE.md "DO NOT
SPECULATE — verify before proposing a fix or explanation" applies
to audit findings too — verify each before treating it as actionable.

**Optional follow-up (not a bug, low priority):** rename the python
local + response field `balls` → `legal_balls` in `/by-innings`
response shape to remove the variable-name confusion. Pure
cosmetics; would require a regression-flip dance for the rename.
Skip unless cleanup pass.

### §3.4 ✅ verified — Wicket-attribution exclusions BY DESIGN (re-verified 2026-05-09)

| Caller | Excluded `wicket.kind` | File:line |
|---|---|---|
| Batter dismissals (`/{id}/summary`, `/distribution`, etc.) | `('retired hurt', 'retired out')` | `batting.py:106, 125, 259, 458, 529, 601, 685, 729` (consistent) |
| Bowler wickets (any) | `('run out', 'retired hurt', 'retired out', 'obstructing the field')` | `bowling.py:93, 113, 192, 463, 1009` (consistent) |

This IS by design — bowlers are NOT credited with run-outs (the
fielder gets the run-out credit, not the bowler) and obstructing-
the-field is rare and ambiguous. Batter dismissals legitimately
include run-outs (the batter IS dismissed) and obstructing.

**Documented?** `internal_docs/how-stats-calculated.md §Bowler
wicket attribution` covers this. ✅ — flagged here only as an
inventory completeness item.

### §3.5 ✅ RESOLVED 2026-05-09 — DLS / forfeited / declared

**Resolution:** keep the current behaviour (no filter, no
branch on `target_overs`). Codified in
`how-stats-calculated.md` "DLS-truncated innings (target_overs
< 20) — INCLUDED everywhere."

**Reasoning:**
- Overs/balls-denominator stats are DLS-safe by construction —
  they use actual legal-ball counts from the `delivery` table,
  never assume 20 overs. Verified by grep: zero hardcoded `20`
  or `20.0` denominators in `api/routers/`.
- Innings-denominator stats correctly include DLS innings as
  one innings each. A 90-run DLS chase that ended in over 12
  is structurally identical to a 90-run fast chase that ended
  in over 12 of a normal 20-over game — both are one innings
  of 90 runs in cricket terms. Filtering DLS without also
  filtering fast chases would be inconsistent.
- `declared` and `forfeited` columns exist but have zero rows
  in the T20 data. The Phase-2 sanity test asserts they stay
  at zero — non-zero would surface a schema/data change
  warranting a re-decision.

Concrete impact (MI/IPL): 0.36 runs/innings swing on "Avg
innings total" from including DLS — small at scale, larger on
narrow scopes; accepted as the correct cricket story.

**Tested by:** `tests/sanity/test_predicate_invariants.py` —
prints the variant inventory (super_over / DLS / declared /
forfeited counts) at every run, and asserts declared+forfeited
remain at zero.

### §3.6 ✅ verified — Helpers shared between team `/summary` and `/scope/averages/*` (re-verified 2026-05-09)

Both compute the league-side aggregate via the same `team=None`
dual-query pattern. They share helpers — `scope_averages.py:31-35`
imports `_apply_batting_per_innings`, `_apply_bowling_per_innings`,
`_apply_fielding_per_innings`, `_apply_partnerships_per_innings`,
`_apply_results_per_team` from `teams.py` (originally lived in
teams.py; the audit said scope_averages.py — wrong location, right
conclusion).

**Currently synchronised** — verified live, helpers cross-imported.
Flagged as a watch-item: any future refactor of these helpers
applies to both endpoints automatically.

---

## §4. Server↔client duplication flags ⚠️

Same value computed on BOTH server AND client. Each is a candidate
divergence-bug surface.

### §4.1 + §4.5 ✅ RESOLVED 2026-05-09 — SR now server-side on /distribution

**Verified real:** `/batters/{id}/distribution.lifetime.runs` does
NOT include a `strike_rate` field (keys: `total, balls_total,
mean_per_innings, median, variance, std, average, observations`).
The frontend computes `poolSR = runs.total * 100 / balls` at
`BatterDistributionPanel.tsx:134` and renders as "Career SR" at
line 162. Same player page also shows server-computed
`/summary.strike_rate` at the top.

- **Server:** `/batters/{id}/summary.strike_rate` = `runs * 100 / balls`
- **Client (Distribution panel SR-tab):** `runs.total * 100 / runs.balls_total` from `BatterDistributionPanel.tsx:134`

Both compute strike rate. Different code paths, both rounded
differently (server: 2 dp via `_safe_div(..., 2)`; client:
2 dp via `.toFixed(2)`). Currently the API doesn't surface
`strike_rate` on `/distribution`, so the client computes it
from the `runs.total` + `runs.balls_total` it already received.

**Divergence risk.** A future change to one predicate (e.g.
super_over filtering, legal-ball definition) without updating the
other produces two different SR numbers on the same player page —
the summary card on top vs the SR-tab strip below.

**Phase-2 sanity test:** on a fixed scope, curl
`/{id}/summary.strike_rate` and `/{id}/distribution.runs.total *
100 / runs.balls_total`; assert agreement to 2 dp.

### §4.2 ✅ RESOLVED 2026-05-09 — "Avg innings total" now server-side envelope

**Resolution:** added `avg_innings_total` envelope to
`/teams/{team}/batting/summary` via commit `a0b9c0a` (backend) +
frontend simplification in the same arc. Both the team value and
the league `scope_avg` now flow through `_batting_aggregates` →
`_apply_batting_per_innings` — single code path, no divergence
surface. Frontend `Teams.tsx:651-674` simplified from a 24-line
synthetic-envelope construction to a 5-line plain `MetricDelta`
consumer.

**Live verification (MI/IPL post-fix):**
```
avg_innings_total.value      = 163.4   ← server-computed (matches pre-fix client compute exactly)
avg_innings_total.scope_avg  = 161.2   ← server league baseline
avg_innings_total.delta_pct  = +1.4%   ← server-computed via wrap_metric
```

**Pre-fix description (kept for context):** Client computed
`value = total_runs.value / innings_batted.value` and
`delta_pct = (value - scope_avg) / scope_avg * 100` using the
server-supplied `total_runs.scope_avg`. The two sides flowed
through different code paths — a future change to per-innings
normalisation on the server would not propagate symmetrically to
the client's value.

**Tested by:** `tests/integration/team_batting_distribution.sh`
Test 14 (added 2026-05-09). Asserts across 3 teams (MI, CSK, RCB)
that:
- DOM-rendered Avg innings total == API `avg_innings_total.value`
- Subtitle contains the API `scope_avg`
- Arrow direction matches sign of `delta_pct`
- `scope_avg(avg_innings_total)` IDENTICAL across teams (cross-team
  league-baseline lock-down)
- `avg_innings_total.value == total_runs.value / innings_batted.value`
  (legacy-compat anchor — proves the server-side computation matches
  what the client used to do)

11 NEW assertions; 0 fail.

**Regression coverage:** 5 team-batting-summary URL flips
(REG→NEW→REG dance) in `tests/regression/teams/urls.txt`.
0 REG drifted; new shape locked.

### §4.3 ✅ RESOLVED 2026-05-09 — pool_strike_rate now server-side on team-bowling /distribution

**Verified real:** team-bowling `/distribution.lifetime` keys
include `wickets, runs_conceded, economy, phase, last_match_date`
— no `balls.total` or `strike_rate`. The frontend reconstructs
balls via the algebra cascade.

- **Server:** `economy.pool` (RPO) and `total_wickets` (count).
- **Client (`TeamBowlingStatStrips.tsx:85-87`):**
  ```
  poolSR = (runs_conceded.total * 6) / economy.pool / wickets.total
  ```
  This is algebra: `economy.pool = runs * 6 / balls` ⇒ `balls
  = runs * 6 / economy.pool` ⇒ `pool_sr = balls / wickets`.

The API doesn't surface a direct `strike_rate` (balls/wkt) on the
bowler distribution endpoints. The frontend reconstructs it from
existing fields.

**Divergence risk.** Floating-point cascades through three
multiplications/divisions. A 4dp rounding of `economy.pool` in
the API plus a 4dp rounding of `runs_conceded.total` produce a
poolSR that's not bit-exact to a server-computed `total_balls /
total_wickets`. For typical values (economy=7.5, wickets=200,
runs=2400) the divergence is sub-tenth-percent — harmless. But
it's an unnecessary derivation; the API could just surface
`balls.total` directly and the client could compute SR cleanly.

**Phase-2 fix:** add `balls.total` (or `strike_rate`) to the
bowler distribution endpoint envelope. Eliminates the
reconstruction.

### §4.4 ✅ verified — CV is single-site client computation (re-verified 2026-05-09)

- **Server:** Doesn't compute CV directly; surfaces `std` and
  `mean_per_innings` as siblings.
- **Client (`DistributionStatStrip.tsx:57-59`):** `cv = std /
  mean if both > 0 else null`.

Single client computation; no server counterpart. Listed here for
completeness — a future decision to surface CV server-side should
delete the client-side computation.

### §4.5 ✅ RESOLVED 2026-05-09 — see §4.1 (combined fix)

**Re-verification update:** the original audit said "single client
computation, no duplication." That was **wrong**. The same
per-innings SR is computed in TWO places:

- **Server (`/by-innings.strike_rate`):** server-computed at
  `batting.py:366`. Powers the per-match innings table on
  `/batting?player=X`.
- **Client (`distributionBins.ts:82-84` + `BatterDistributionPanel.tsx:124-128`):**
  `sr = runs * 100 / balls` per innings, derived from
  `/distribution.observations`. Powers histogram binning + SR-tab
  stat strip on the Distribution panel.

Same player page surfaces both: the per-match innings table reads
the server's per-innings SR, the Distribution panel SR-tab reads
the client-derived per-innings SR. Today they agree (same SQL
formula, same inputs). Future predicate drift on either side
breaks the agreement silently.

**Cost to fix:** Same pattern as §4.1 — surface
per-innings SR on `/distribution.observations` so the frontend
reads instead of recomputes. Combine with §4.1 fix in one arc
(both are "/distribution should expose SR").

### §4.6 ✅ verified — Rolling-10 mean overlay client-only (no duplication)

Verified 2026-05-09: no `rolling`/`moving_mean` field anywhere in
`api/`. Computed entirely client-side at
`DistributionSparkline.tsx`. UI smoothing layer; not a derived
metric in the data sense. By design.

---

## §5. Predicate inconsistencies ⚠️

### §5.1 Already covered above

- **§3.2** dots predicate (batting `runs_batter=0 AND runs_extras=0` vs bowling `runs_total=0` vs bowling-distribution `runs_total=0 AND extras_wides=0 AND extras_noballs=0`)
- **§3.4** wicket-kind exclusions (batting 2 kinds; bowling 4 kinds — by design)

### §5.2 ✅ RESOLVED 2026-05-09 — Substitute asymmetry is intentional (documented)

| Caller | `is_substitute` predicate | File:line |
|---|---|---|
| `/distribution` catches | `COALESCE(fc.is_substitute, 0) = 0` | (post-2026-05-08 fix) |
| `/{id}/summary.substitute_catches` | `is_substitute = 1` (reconciliation scalar) | `fielding.py:212` |
| `/leaders.catches` | No is_substitute filter — substitute catches counted in the catches column | `fielding.py:96` ⚠️ |
| `/keeping/summary.keeping_catches` | Implicit: only innings where person was the keeper, so by definition not substitute | `keeping.py:113` |

**Resolution:** the asymmetry is **kept by design**, not patched
to uniformity. The audit's original framing of "/distribution
excludes subs" gave the impression that /distribution was making
a value judgment about substitutes. It isn't — /distribution's
`is_substitute=0` filter is a sample-denominator consistency
guard. The master sample is `matchplayer`-based (matches the
player was in the squad); substitute appearances aren't in that
sample. Counting substitute catches against the matchplayer
denominator would miscalibrate per-match averages.

`/leaders` doesn't have a matchplayer join — it's pure
volume-counting over `fieldingcredit`. Counting substitute
catches there is consistent with the data: a sub who took 5
catches took 5 catches, leaderboard ranks accordingly.

So the two endpoints answer **different questions**:
- `/leaders` — "who took the most catches in scope?" (volume) → subs counted
- `/distribution` per-match — "what's your fielding pattern in your matches?" (per-match rate) → subs excluded
- `/distribution.substitute_catches` — sibling reconciliation scalar so consumers can see the gap

**Practical impact ≈ 0.** Top-N fielding leaderboards are
dominated by full-time keepers and outfielders who don't sub.
Players with non-trivial substitute counts (Mohammad Nawaz 10,
CJ Dala 8, J Suchith 8, RK Singh 7, DJ Hooda 7) are nowhere near
top-N total-dismissal leaders. The asymmetry is invisible in
the rendered UI.

**Codified in:** `internal_docs/how-stats-calculated.md` §Fielding
"Substitute fielders — INCLUDED in /leaders, EXCLUDED in
/distribution (intentional asymmetry)" with the full predicate
table and reasoning. Future readers won't re-litigate.

**Tested by:** `tests/sanity/test_catches_convention3.py::assert_leaders_substitute_leak`
locks the algebraic identity
`leaders.catches - distribution.catches.total == distribution.substitute_catches`.
Any future predicate change that breaks the asymmetry surfaces
immediately.

### §5.3 Legal-balls definition

- **Batting:** `extras_wides = 0 AND extras_noballs = 0` (everywhere).
- **Bowling /summary:** Same predicate.
- **Bowling /by-innings:** Uses legal-balls (the python local `balls` is misleadingly named but the SQL alias is the legal-balls count). See §3.3 for verification — the original audit claim of all-deliveries was wrong.
- **Fielding:** No legal-balls filter — a catch on a wide is still a catch. ✅ correct.

---

## §6. Recommendations for Phase 2

Each recommendation is a concrete sanity-test assertion that
catches one ⚠️ flag.

### §6.1 Cross-endpoint catches inclusivity (catches highest-risk)

**Tested by:** `tests/sanity/test_catches_convention3.py` —
shipped 2026-05-09. 24 assertions across 6 (player, scope) tuples
including Bumrah (the C&B incident's marquee subject who was
missing from the existing reconciliation). All pass currently —
locks down the agreement so any future predicate drift on either
side surfaces immediately.

```python
# For 5 fixed (player_id, scope) tuples covering bowlers + batters:
summary = await get('/fielders/{pid}/summary?{scope}')
distribution = await get('/fielders/{pid}/distribution?{scope}')
assert summary['catches'] + summary['caught_and_bowled'] \
       == distribution['lifetime']['catches']['total']

# Also for /leaders aggregate:
leaders = await get('/fielders/leaders?{scope}&limit=50')
for row in leaders[:10]:
    dist = await get(f'/fielders/{row["person_id"]}/distribution?{scope}')
    assert row['catches'] + row['c_and_b'] == dist['lifetime']['catches']['total']
```

This either passes (and confirms the divergence is at the field-
naming level only — semantics consistent if you sum the siblings)
OR it fails (and surfaces a real undercount). Either way the
assertion is durable.

### §6.2 Server-vs-client value agreement on the batter SR-tab

**Tested by:** `tests/integration/batter_distribution.sh` Test 11
— shipped 2026-05-09. Asserts both:
- Server `/summary.strike_rate` == `/distribution.runs.total*100/balls_total` (cross-endpoint)
- DOM "Career SR" == JS-formatted client SR (DOM-vs-derived)

Both formatted via `ab_eval` so JS rounding agrees on both sides.

```bash
api_summary_sr=$(curl -s "$API/batters/$KOHLI/summary?$SCOPE" \
  | python3 -c "import json, sys; print(json.load(sys.stdin)['strike_rate'])")
dom_career_sr=$(ab_eval "...read 'Career SR' value from SR-tab strip...")
# Server returns ##.# format; DOM does too. Compare to 1 dp.
assert_eq "Server SR == DOM SR-tab Career SR" "$api_summary_sr" "$dom_career_sr"
```

### §6.3 "Avg innings total" delta-pct against league-side

**Tested by:** `tests/integration/team_batting_distribution.sh`
Tests 12 + 13 (Test 12 was pre-existing; Test 13 added 2026-05-09).
Test 12 asserts `dom_value == round(runs/innings, 1)` (DOM matches
client computation). Test 13 adds the cross-team lock-down:
`scope_avg` MUST be identical for `/teams/MI/batting/summary` and
`/teams/CSK/batting/summary` in the same scope, since scope_avg is
the LEAGUE mean and team-independent. Catches the "team filter
leaking into scope_avg" bug class.

```bash
# Server: total_runs.scope_avg is per-innings (already verified by Test 11/12)
# Client: synthetic envelope value = team_runs / team_innings
api=$(curl -s "$API/teams/$TEAM/batting/summary?$SCOPE")
team_runs=$(echo "$api" | python3 -c "...total_runs.value...")
team_innings=$(echo "$api" | python3 -c "...innings_batted.value...")
expected_value=$(python3 -c "print(round($team_runs / $team_innings, 1))")
dom_value=$(ab_eval "...read Avg innings total stat card value...")
assert_eq "Avg innings total = total_runs/innings_batted" "$expected_value" "$dom_value"
```

### §6.4 Dots-predicate semantic-equivalence sanity (SQL-level)

**Tested by:** `tests/sanity/test_predicate_invariants.py` —
shipped 2026-05-09. Asserts all three predicate counts are equal
on `cricket.db`, AND asserts the underlying schema invariant
`runs_total = runs_batter + runs_extras` holds for every row.
On the current DB: 1,125,498 dots match all three predicates;
0 schema violations.

```python
# Assert that the three different dot predicates count the same rows
# on cricket.db. If they ever diverge, either a schema change happened
# or one predicate was wrong.
db = open()
n1 = db.q("SELECT COUNT(*) FROM delivery WHERE runs_batter=0 AND runs_extras=0")
n2 = db.q("SELECT COUNT(*) FROM delivery WHERE runs_total=0")
n3 = db.q("SELECT COUNT(*) FROM delivery WHERE runs_total=0 AND extras_wides=0 AND extras_noballs=0")
assert n1 == n2 == n3
```

### §6.5 DLS / forfeited audit (one-time inventory query)

**Tested by:** `tests/sanity/test_predicate_invariants.py` —
shipped 2026-05-09. Prints variant inventory at every run AND
asserts:
- super_over fraction stays under 5% (auto-filtered).
- target_overs > 20 NEVER (T20 schema invariant).
- declared / forfeited stay at 0 (non-zero means schema changed
  and we need to re-decide filter policy).
- DLS-truncated count stays under 10% of 2nd innings (audit
  framing stays accurate as DB grows).

**Current numbers (2026-05-09):**
- 26,234 total innings; 194 super_over (0.74%); 11,524 full-T20
  chases; **724 DLS-truncated chases** (5.91% of 2nd innings —
  NON-trivial and currently unfiltered everywhere); 0 declared;
  0 forfeited.

**Decision (2026-05-09):** keep DLS innings counted as 1 innings
each in per-innings denominators. Overs-denominator stats are
already DLS-safe (they use actual legal-ball counts, not assumed
20 overs). The cricket logic: a DLS-shortened chase is
structurally identical to a fast chase that ended early — both
played one innings, both scored runs. Filtering DLS but not
fast-chase innings would be inconsistent. Codified in
`how-stats-calculated.md` "DLS-truncated innings — INCLUDED
everywhere."

### §6.6 Substitute catches in /leaders

**Tested by:** `tests/sanity/test_catches_convention3.py::assert_leaders_substitute_leak`
— shipped 2026-05-09. Walks top-10 of `/fielders/leaders` and
asserts the algebraic identity:
```
leaders.catches - (distribution.catches.total - leaders.c_and_b)
  == distribution.substitute_catches
```
which decomposes the leak: leaders.catches = (non-sub C + sub C)
while distribution.catches.total - c_and_b = non-sub C only. The
difference is exactly the substitute leak.

Confirmed currently: /leaders DOES count substitute catches in
its `catches` column. Whether to filter them out is a product
decision pending — the assertion locks down the current behaviour
either way.

---

## §7. Maintenance rule — when to update this doc

Update this doc when **any** of the following happens:

- A new `/distribution` or `/summary` endpoint ships.
- A new client-side derivation lands (a new `useMemo`, a new
  `.toFixed(...)` over a computed value, a new synthetic
  envelope).
- A predicate changes in a router (legal-balls, super-over,
  retired exclusions, substitute fielders, etc.).
- A `MetricEnvelope` field is added or removed.

Each ⚠️ flag is a Phase-2 follow-up item. As Phase-2 sanity
tests land, add a "Tested by:" line under the flag pointing to
the new assertion.

If a finding is closed (e.g. a divergence is fixed), keep the
flag entry but add a "Resolved YYYY-MM-DD" line — historical
markers help future maintainers understand WHY a particular
predicate or shape is the way it is.
