# Spec — make the player "typical" comparison follow the six filters it currently ignores (+ aux controls)
**Status:** DRAFT for review (Roughdraft). **Date:** 2026-05-26. **Closes:** `internal_docs/audit-aux-params.md` §E item 1 (frozen player comparison) + item 2 (toss not wired for the player's own numbers). **Supersedes** the caveat shipped with the "Versus" opponent filter (commit 45c58b7).

* * *
## 0. Terminology (so nothing below is undefined)
- **The own number** — the player's actual stat in the big bold tile (e.g. Kohli's strike rate 134.9).
  
- **The comparison** (a.k.a. the cohort number, the grey "vs cohort N" chip) — the "typical player" figure shown next to the own number.
  
- **The pool** — the set of players the comparison is computed from.
  
- **The six filters** — the only filters the comparison does NOT follow today: **venue, opponent, team** (filter bar) and **innings, toss, result** (aux toggles). Everything else (gender, club/intl, tournament, season, tier, competition-type) it already follows.
  
- **Position mix** — how often a batter bats in each position bucket (bucket 1 = opener = positions 1+2 merged; 2 = #3; … 10 = #11). The batting comparison is the all-batters average **blended to the player's own position mix**.
  
- **Over mix** — the bowling equivalent over overs 1..20.
  
- **Keeper-binary** — fielding has NO mix; the pool is "all keepers" or "all outfielders".
  
- **Per-innings table** — a precomputed table with one row per (player, innings), cheap to filter and group. The team side has `inningstotal`; the batting records family has `inningsbatterperf`.
  
- **The support cliff** — the current minimum-sample guard: each bucket has a floor; if the player's mix touches any bucket below it, the whole comparison blanks. Binary, no interval.
  
- **Precomputed vs live path** — precomputed = read pre-aggregated tables (fast, but only sliceable by the non-six axes). Live = compute on request so the six filters can apply.
  
- **The gate** — `is_precomputed_scope(filters, aux)` (exists, team side): True when none of the six is set (precomputed), False when any is set (live).
  
## 1. Goal (plain English)
When you narrow a player page by any of the six filters, the grey "typical player" comparison (and the chart reference line, and the distribution chips) should move to match, exactly as the player's own numbers already do. Today the comparison stays frozen, so "Kohli vs Australia" pits his real vs-Australia strike rate against a typical batter's _all-opponents_ strike rate. Make both sides narrow together.

Each filter answers a real question (pools in §4): _"Is Kohli the best top-order bat India has? Best against CSK? Best in games lost to MI, as an RCB player, batting first?"_
## 2. Decisions locked in review (2026-05-26)
| #   | Decision |
| --- | --- |
| D1  | **Order:** controls first (§6), then player's own toss (§7), then the per-innings table + live comparison (§8). |
| D2  | **Toss control:** build a reusable won/lost control patterned on the win/loss control; **mount surface TBD, NOT player pages.** Build now, mount later. Tested by mounting on a throwaway surface in an integration test (Q2). |
| D3  | **Result (win/loss) control:** mount the existing control on the 3 discipline pages (backend already works → immediately functional). |
| D4  | **Pools:** the six definitions in §4, weighted by the player's position/over mix (fielding = keeper-binary). |
| D5  | **Fielding stays keeper-binary** (cruder by design; unchanged here). |
| D6  | **No confidence intervals now** — later, cross-cutting (player + team). |
| D7  | **Sample size: tooltips only.** Cohort sample rides the existing comparison-chip tooltip with the narrowed counts; the own sample is already the Matches/Innings tiles → no new own-number tooltip. |
| D8  | **Team-side support cliff is later work.** |
| D9  | **Fairness rule:** for each filter, BOTH the own number and the comparison must narrow. |
| D10 | **Precompute, don't re-derive (perf).** Add `position_bucket` + `dots` to the per-innings batter table so the filtered comparison reads them instead of re-deriving batting order over 3M balls per request. Bowling needs no new table (over is stored per ball); fielding is keeper-binary per match. |
| D11 | **Schema change handled as a rebuild, not ALTER.** Back up the current DB, edit the model, DROP+CREATE on full populate, re-ingest. **Incremental loading must fill the new columns too** (`update_recent.py`). Add the indexes the filtered aggregation needs. |
| D12 | **Toss for player VALUES stays in scope (URL-settable, no widget yet)** so the comparison can be fair under toss (Q3). |
## 3. Phase plan (ordered per D1)
1. **Controls.** (a) Build the Toss control component (D2), mount deferred, tested on a throwaway surface. (b) Mount the win/loss control on the 3 discipline pages (D3).
  
2. **Player's own toss.** `player_toss_clause` wired at every player value call site (§7). Own numbers narrow by toss (URL-settable).
  
3. **Per-innings table + live comparison** (§8), commit-sliced:

  > **3b SHIPPED 2026-05-28** (commit `00ef3d1`). Dispatch wired in
  > `compute_players_batting_cohort` — none-of-six routes to the
  > precomputed read; any-of-six runs a live aggregation over
  > `inningsbatterperf` joined to innings+match using the team-side
  > cohort clauses (`_option_b_team_inning`, `_cohort_outcome_clause`).
  > `tests/integration/player_baseline_aux_fallback.sh` locks the
  > red→green narrowing. Regression annotations flipped REG→NEW for 6
  > URLs (`cf38935`). Plan doc: `internal_docs/plan-3b-batting-live-cohort.md`.
  > **3c next:** plan drafted at `internal_docs/plan-3c-batting-by-season-by-phase-live.md`.


- 3a. ✅ Extend `inningsbatterperf` (+`position_bucket`,+`dots`); rebuild populate + incremental + indexes + backup (§8.4). Parity-tested.

- 3b. ✅ Batting live comparison (summary chip + distribution) reading the extended table.

- 3c. ✅ **SHIPPED 2026-05-28.** Batting by-season + by-phase live. (No by-over for batting — that's bowling's 3d.) Dispatch wired into `compute_players_batting_by_season` (live aggregates `inningsbatterperf`→innings→match with `m.season` in the GROUP BY) and `compute_players_batting_by_phase` (live aggregates at the DELIVERY grain — over→phase, position off `inningsbatterperf`, all-ball convention; `(legal OR runs_batter<>0)` replicates the populate's wide-skip). Both split into `_by_{season,phase}_{precomputed,live}` and dispatch on `is_precomputed_scope`. 3b's WHERE-building factored into `_batting_live_where`. Live by-phase verified byte-identical to the precomputed phase×position table at none-of-six (26 cells, 0 mismatches). Q4 resolved: under `inning=0` all three phases keep ~1000+ innings, far above the 30-innings cliff. `tests/integration/player_baseline_aux_fallback.sh` §5+§6 lock the red→green narrowing + SQL anchors + Q4 guard. Commits: `321054a` (REG→NEW pre-flip), `886a220` (by-season), `d61c3e6` (by-phase). Plan: `internal_docs/plan-3c-batting-by-season-by-phase-live.md`.

- 3d. ✅ **SHIPPED 2026-05-28.** Bowling live (raw deliveries grouped by over — no new table). Three slices, each dispatch on `is_precomputed_scope`: 3d-1 `compute_players_bowling_by_phase`, 3d-2 `compute_players_bowling_by_season`, 3d-3 `compute_players_bowling_cohort` (summary chip + distribution prob baselines). Shared `_bowling_live_where` (bowling/fielding orientation: inning flips to 1-N, toss/result key on the bowling side, filter_team/opponent flipped) + `_bowling_over_cohort_live(by_season, with_spell_cols)` reproducing every `playerscopestatsover` column live, including the per-spell-touching set (maidens, 3/4/5-fer attribution via ROW_NUMBER, innings_with_wicket/two, qualifying + econ/runs bands via a touch/spell/spell_wkts CTE). Verified byte-identical to the precomputed table at none-of-six (20 overs × 22 cols = 440 cells, 0 mismatches). Tests: `player_baseline_aux_fallback.sh` §7-§9. Commits `75730ea` (by-phase) / `3f0bc74` (by-season) / `1cf1bc7` (summary+distribution) + 2 REG→NEW pre-flips. Plan: `internal_docs/plan-3d-bowling-live-cohort.md`.

- 3e. ✅ **SHIPPED 2026-05-28.** Fielding / keeping live (keeper-binary).
  `compute_players_fielding_cohort` (+ `_by_season` + `_by_phase`) each
  dispatch on `is_precomputed_scope`: none-of-six → precomputed children
  (unchanged); any-of-six → live aggregation across the three source
  tables. New helper `_fielding_denom_where` builds the matchplayer-grain
  `matches_fielded` denominator keyed on `mp.team` (fielding orientation);
  the numerator reuses `_bowling_live_where` (fieldingcredit lives in the
  opponent-batting innings = bowling orientation), Convention 3 +
  is_substitute=0, with the dismissed-batter bucket from `inningsbatterperf`
  so it stays byte-identical to `playerscopestatsfieldingposition`; the
  catch-dist (P chips) buckets the matchplayer master sample by per-match
  non-sub catch count (mirrors `playerscopestatsfieldingcatchdist`); the
  keeper/outfielder partition is "kept ≥1 in-scope innings"
  (`keeperassignment`, summary/by-phase use a single lifetime set,
  by-season a per-(person,season) set). Side-effect (consistency):
  team_class/series_type now narrow the fielding cohort too
  (`is_precomputed_scope` already rejects them), so fielding matches
  batting/bowling. **Parity:** live == precomputed byte-identical at
  none-of-six (IPL 2016 summary both cohorts + 10 dismissed-position
  buckets; by-season 18 seasons; by-phase 6 cells — 0 mismatches).
  SQL-anchored narrowing: Dhoni men's-intl inning=0 keeper catches/match
  0.576→0.5 (2365/4726); IPL 2016 inning=1 0.65 (39/60). Browser-confirmed:
  distribution P-chip cohort 58%→64% under inning=0 (both sides narrow).
  Tests: `player_baseline_aux_fallback.sh` §10-§12 (red→green). Commits:
  `11e6818` (REG→NEW pre-flip ×16) → `6ffd315` (summary+distribution) →
  `e608da0` (by-season) → `decc3d9` (by-phase) → `271ad45` (tests) →
  `031e0da` (NEW→REG flip-back). This also flipped the
  By-Dismissed-Position + By-Over TAB denominators to `matches_fielded`
  (both sides) — the deferred half of B.

  **Original re-scoped scope (2026-05-28), retained for reference —
  it is NOT the "cheap matchfielderperf mirror" the original §8.3 bullet
  assumed; it's the heaviest discipline slice. Detailed below.**

  **Denominator B — SHIPPED 2026-05-28 (commit `5341f67`), a prerequisite
  done ahead of 3e.** Fielding per-match rates + catch-dist prob chips now
  divide by `matches_fielded` (XI ∧ opponent batted), the activity unit —
  consistent with batting `innings_batted` / bowling `innings_bowled`.
  Parent gained `matches_fielded` (DROP+CREATE re-ingest); catch-dist
  master sample restricted to fielded matches; own (`/summary`,
  `/by-season`, `/by-phase`) + the three fielding cohort `n_matches_total`
  denominators all point at it. Displayed career "matches played" stays
  squad. The By-Dismissed-Position + By-Over TAB denominators stay squad
  (internally consistent) until they're made live here. So 3e's live
  denominator builds on `matches_fielded`, not `matches`.

  **3e live cohort — the real scope.** Unlike bowling's single delivery
  scan, the fielding cohort spans THREE source tables, and the numerator
  and denominator live at different grains:
  - **denominator** (matches_fielded): `matchplayer` ⋈ `innings`
    (`i.team != mp.team`, super_over=0) — match grain. The six narrow it
    per-fielder-**team** as a match-subset (keyed on `mp.team`), the
    fielding orientation.
  - **numerator** (catches/stumpings/run-outs): `fieldingcredit` ⋈
    delivery → innings → match, `kind IN ('caught','caught_and_bowled')`
    + `COALESCE(is_substitute,0)=0` (Convention 3) — innings grain,
    fielding orientation.
  - **keeper/outfielder partition**: `keeperassignment` — a cohort
    fielder is a "keeper in scope" iff they kept ≥1 in-scope innings
    (mirrors how the player's OWN value already decides `is_keeper`, so
    own↔cohort agree). RESOLVED — not ambiguous.
  - **summary/distribution extras**: dismissed-batter position bucket via
    join to `inningsbatterperf` on `player_out`; per-(fielder, match)
    catch-count distribution for the P(=0/1/≥2) chips.
  - No mix weighting (D5, keeper-binary). Parity-probe the live aggregation
    byte-identical to the precomputed fielding tables at none-of-six (like
    bowling's 440-cell check). Dispatch on `is_precomputed_scope` per
    surface (summary+distribution / by-season / by-phase), reusing the
    bowling-side orientation helpers. This also flips the
    By-Dismissed-Position + By-Over tab denominators to `matches_fielded`
    (both sides) — the deferred half of B.
  

4. **Docs** — flip audit §A player rows ✗→✓; `server-vs-client-calcs.md`, `how-stats-calculated.md`, `data-pipeline.md` (new columns). **API docs (**`docs/api.md`**) — carry the Phase 1+2 additions that have no entry yet:** the `toss_won`/`toss_lost` fields on `/players/{id}/result-counts` (Phase 1), and the `toss_outcome` aux param now narrowing every player VALUE endpoint via `player_toss_clause` (Phase 2 — document alongside the existing `result`/`inning` aux rows). Note `/players/{id}/result-counts` itself is currently undocumented in `docs/api.md`; add the endpoint while there. Plus `user-help.md` for any user-visible control once the toss control is actually mounted.
  
## 4. The six filters and what the pool becomes
Each pool is then weighted by the player's position mix (batting) / over mix (bowling); fielding uses keeper/outfielder, no weighting (D5).

| Filter | Pool becomes | Mechanism (reused, §8.2) |
| --- | --- | --- |
| **venue** | everyone who played **at that venue** | match-level `m.venue` |
| **opponent** | everyone who played **against that team** | cohort player's own team ≠ opponent (other side per row) |
| **team** | everyone who played **for that team** | cohort player's own team = X |
| **innings** | the 1st / 2nd-innings slice (Option-B, discipline-aware) | `_option_b_team_inning(side)` keyed on i.team |
| **result** | matches won / lost (own side) | `_cohort_outcome_clause(side)` keyed on i.team |
| **toss** | matches with toss won / lost (own side) | `_cohort_outcome_clause(side)` keyed on i.team |
## 5. Current architecture (verified 2026-05-26)
`compute_players_{batting,bowling,fielding,keeping}_cohort` (+ `_by_season` / `_by_phase` / `_by_over`) in `api/routers/scope_averages.py` read the precomputed child tables (`playerscopestatsposition` etc.) by `scope_key` via `build_scope_clauses(filters)` (non-six axes only), then `convex_combine(per_bucket_rates, mix)` blends by the player's mix; the support cliff guards thin pools. 11 `build_scope_clauses` call sites + in-process calls from the discipline routers. **All frozen for the six.**

Player VALUES already narrow by innings (`player_inning_match_clause`) + result (`player_result_clause`); NOT toss. Toss winner = `m.toss_winner`. Batting position is derived from ball order by `api/innings_positions.py::derive_positions(deliveries)` — already used by the populate scripts; reused in §8.4.
## 6. Phase 1 — controls
### 6.1 Toss control (build, mount deferred — D2)
New component patterned on the win/loss control (`PlayerResultFilter` → shared `ResultFilter`): a won/lost pill row writing the `toss_outcome` aux param. **Not mounted on player pages.** Mount surface decided later; component ships ready. **Tested by mounting it on a throwaway surface in an integration test** (renders, writes `toss_outcome`, counts reconcile) — Q2.
### 6.2 Win/loss control → discipline pages (D3)
`PlayerResultFilter` mounts only on `/players` today (its header even says "later session"). Mount it on `/batting`, `/bowling`, `/fielding` in the existing aux-filter row beside the innings toggle. Backend already wired across all four → immediately functional.
## 7. Phase 2 — player's own toss (D12)
Add `player_toss_clause(aux, person_id, params, match_id_expr, key)` to `api/filters.py`, modelled on `player_result_clause`:

```
'won'  → m.toss_winner = mp.team
'lost' → m.toss_winner IS NOT NULL AND m.toss_winner != mp.team
# no 'tied'; m.toss_winner IS NULL (un-recorded) excluded from both.
```

Wire at EVERY `player_result_clause` site (`grep -rn player_result_clause api/routers/` → batting ×3, bowling ×4, fielding ×3, keeping ×2). URL- settable on player pages; no widget until the toss control (§6.1) is mounted.
## 8. Phase 3 — per-innings table + live comparison
### 8.1 Dispatch (reuse the gate)
```
if is_precomputed_scope(filters, aux):   # none of the six set
    <existing precomputed read>          # unchanged fast path
else:
    <live aggregation>                   # §8.3, reads the per-innings table
# convex_combine(per_bucket, mix) + support cliff: IDENTICAL for both
```

`is_precomputed_scope` already returns False for exactly the six — **reuse unchanged.** Precomputed path never changes (parity test §10).
### 8.2 Narrowing — reuse the team-side cohort clauses
The player comparison is a league-side aggregation keyed on each cohort player's own team — same shape as the team comparison. Reuse, unchanged:

- `_cohort_outcome_clause(side, aux)` — toss + result, keyed on i.team, discipline-aware. Documents why won-toss ≈ 50% of matches but their STATS differ → narrowed comparison is real, not tautological.
  
- `_option_b_team_inning(side)` — innings, keyed on i.team.
  
- Standard match-level clauses for venue / team / opponent.
  

No new narrowing logic — only the per-bucket _source_ changes.
### 8.3 Live aggregation — reads the per-innings table (D10), not raw balls
**Why this matters (the perf fix).** The batting comparison must group each pool innings by the batter's position bucket. That position is not stored; deriving it live (order of appearance over ~3M deliveries, per request) is the multi-second risk. Fix: **precompute the position once into the per-innings batter table** (§8.4), so the live filtered query is a join+group over ~206k rows:

```
SELECT ibp.position_bucket, SUM(ibp.runs), SUM(ibp.balls), SUM(ibp.fours),
       SUM(ibp.sixes), SUM(ibp.dots), COUNT(*) AS innings,
       SUM(CASE WHEN NOT ibp.not_out THEN 1 ELSE 0 END) AS dismissals,
       <milestone counts derived from ibp.runs>, COUNT(DISTINCT ibp.batter_id)
FROM inningsbatterperf ibp
JOIN innings i ON i.id = ibp.innings_id
JOIN match   m ON m.id = i.match_id
WHERE <gender/type/tournament/season/tier/series>      -- on-key, via the join
  AND <venue / team / opponent>                        -- §8.2 match-level
  AND <_option_b_team_inning / _cohort_outcome_clause>  -- innings/toss/result
GROUP BY ibp.position_bucket
```

Milestones (30/50/100/duck/failures_10/seventies) derive from per-innings `runs`; dot% / boundary% from `dots`/`fours`/`sixes`/`balls`. This reproduces every column the precomputed child carries, now sliceable by the six. Then convex-combine over the player's mix (unchanged).

- **Bowling (3d):** the "spot" is the over, **stored on every ball** — no derivation. Live aggregation from `delivery` grouped by over with the §8.2 clauses is cheap (the team side aggregates raw deliveries live and is fine). No new table. Measure; add an over-grain intermediate only if a number forces it.
  
- **Fielding/keeping (3e):** keeper-binary, per match — from `matchfielderperf` + keeper flag. Cheap. Pool = outfielders/keepers who match the six filters.
  
### 8.4 Per-innings table extension + populate (D10, D11)
- **Model:** add `position_bucket: int` and `dots: int` to `InningsBatterPerf` (`models/tables.py:959`).
  
- **Full populate:** `scripts/populate_records_aggregates.py` (line ~187 builds `inningsbatterperf`; already fetches the innings' deliveries). Fill `position_bucket` via `innings_positions.derive_positions()` (merge positions 1+2 → bucket 1, matching the cohort convention) and `dots` from the same delivery scan. **DROP+CREATE, not ALTER** (`feedback_no_alter_drop_create`): edit model → rebuild table → re-ingest.
  
- **Backup first (D11):** copy the working DB (and the prod snapshot per `reference_prod_db_copy` — operate on a `/tmp` copy, never mutate Downloads) before the rebuild.
  
- **Incremental provision (D11) — the explicit ask:** `update_recent.py` calls `populate_records_aggregates` which already does a per-innings DELETE+reinsert (line ~358). Ensure the new columns are filled on that path too, so incrementally-ingested matches carry position+dots. Smoke- test via `update_recent.py --days N` against a `/tmp` DB (`reference_incremental_test`).
  
- **Indexes:** keep `ix_inningsbatterperf_innings_id` (the join key). Add a covering index to serve the group-by aggregation — `(innings_id, position_bucket, runs, balls, fours, sixes, dots, not_out)` — and confirm `innings(match_id)` + the `match` venue/team columns are indexed for the filter join. Final index set decided by measuring 3b (CLAUDE.md perf rule: one change, time it).
  
## 9. Sample-size reporting (D6, D7 — tooltips only)
- **Cohort sample → existing comparison-chip tooltip**, with the live path computing `n_players`/`n_innings_total` (etc.) on the **narrowed** pool → reads "vs CSK …; 412 players, 8,917 innings". No new UI.
  
- **Own sample → already the Matches/Innings tiles.** No new own-number tooltip.
  
- `sample_size` envelope field stays populated from the narrowed pool.
  
- **No CIs** (D6). The cliff still blanks too-thin comparisons; a thin own number shows with its innings count visible as a tile.
  
## 10. Test plan
- **Parity (no regression):** none-of-six → gate keeps precomputed; existing baseline suites stay green.
  
- **Populate parity (3a):** `inningsbatterperf.position_bucket` matches `derive_positions()`; aggregating the extended table by bucket at a broad scope == the precomputed `playerscopestatsposition` to 2dp (proves the table can stand in for the precompute). SQL-anchored.
  
- **Incremental (3a):** after `update_recent.py --days N` on a /tmp DB, the new columns are populated for the new innings (not null, correct).
  
- **Each filter narrows BOTH sides (red→green):**`tests/integration/player_baseline_aux_fallback.sh` — for each of the six × {batting summary chip, by-season line, distribution chip} (+ bowling/fielding), RED at HEAD = comparison == unfiltered (frozen); GREEN = comparison moved AND equals a direct live SQL aggregation of the narrowed pool, mix-weighted; own number also narrowed (D9).
  
- **Non-tautology:** `toss_outcome=won` comparison ≠ unfiltered and not ≈50%-degenerate; anchored to live SQL.
  
- **Sample size narrows:** cohort tooltip counts shrink under a filter, SQL-anchored.
  
- **Filter-combination matrix** (mandatory): player+venue, +opponent, +team+opponent, bowling-tab innings flip, chained season+opponent — in agent-browser, both numbers narrow at each combo.
  
- **Toss value:** player value at `toss_outcome=won` == sqlite won-toss count; red before the clause.
  
- **Controls (phase 1):** result control present+functional on all 3 discipline pages (red: absent); toss control renders + writes `toss_outcome` on the throwaway test surface.
  
- **Regression flip:** any REG baseline for a filtered player-cohort endpoint flips REG→NEW in a PRECEDING commit before the shape change (`feedback_regression_before_shape`).
  
## 11. Open questions (all prior ones resolved)
- Q1 (perf) — **RESOLVED:** precompute position+dots (§8.4), no live re-derivation.
  
- Q2 (toss control surface) — **DEFERRED by choice;** build + test on a throwaway surface now, mount later.
  
- Q3 (toss for player values) — **RESOLVED:** in scope, URL-only (D12).
  
- Q4 (by-phase/by-over under innings) — confirm the phase/over live path semantics aren't degenerate (the tables carry no innings dim; the live join handles it).
  
## 12. Non-goals
- Confidence intervals (D6) — later, player + team.
  
- Team-side support cliff (D8) — later.
  
- New precomputed tables keyed by venue/opponent/team — rejected; the per-innings table + live join is the answer.
  
- Position-weighting the fielding cohort (D5).
  
- Leaderboard toss/result; the Splits Mosaic (out per the audit).
