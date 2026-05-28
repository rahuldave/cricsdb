# Plan — Phase 3d: bowling live cohort under the six filters

> **✅ SHIPPED 2026-05-28.** All three slices landed: 3d-1 by-phase
> (`75730ea`), 3d-2 by-season (`3f0bc74`), 3d-3 summary+distribution
> (`1cf1bc7`), plus 2 REG→NEW pre-flips and a NEW→REG flip-back + docs.
> Live per-over aggregation verified byte-identical to
> `playerscopestatsover` at none-of-six (440 cells, 0 mismatches). The
> opponent/team flip + inning flip were SQL-anchored exact. Refactor
> sweep clean: `player_baseline_filter_matrix` adapted automatically
> (its bowling reference-line assertion keys off the cohort
> `below_support`). 3e fielding/keeping is next.

**Spec:** `internal_docs/spec-player-baseline-aux-fallback.md` Phase 3d
(picks up after 3b/3c shipped — batting summary + distribution +
by-season + by-phase all narrow live).

**Goal:** extend the live-fallback dispatch to the three bowling cohort
surfaces so the "typical bowler" comparison narrows under venue /
opponent / team / innings / toss / result, instead of staying frozen at
the all-axes-open scope read from `playerscopestatsover`.

| Surface | Function (`api/routers/scope_averages.py`) | Source today |
|---|---|---|
| summary chip + distribution | `compute_players_bowling_cohort` (~3212) | `playerscopestatsover` GROUP BY over_number |
| by-season chart overlay | `compute_players_bowling_by_season` (~3621) | same + season |
| by-phase chips | `compute_players_bowling_by_phase` (~3892) | same, phase-grouped in Python |

The over is the natural grain (1..20, 1-indexed); the bowler's over-mix
(legal balls per over) is the convex-combine weight — analogous to
batting's position-mix.

---

## 1. The hard part — per-spell columns

`playerscopestatsover` is NOT a per-ball rollup. Beyond the simple sums
(runs_conceded, legal_balls, wickets, dots, boundaries) it carries
columns computed per (innings × bowler) **spell** then attributed to
over buckets. The live SQL must reproduce each byte-identically (verify
with a 0-mismatch probe vs the precomputed table at none-of-six, like
3c's by-phase check). From `scripts/populate_playerscopestats_over.py`:

- **maidens** — per (innings, over_number_0idx, bowler): exactly 6 legal
  balls AND `SUM(runs_total)=0` → one maiden at that over bucket.
- **innings_bowled** — distinct innings the bowler delivered ≥1 legal
  ball at that over. Cohort = `COUNT(DISTINCT innings_id||'-'||bowler_id)`
  where legal, per over bucket.
- **four/three/five_wicket_hauls** — attributed to the over where the
  bowler's Nth valid wicket fell (running count within innings×bowler,
  ordered by over/delivery_index/id). `ROW_NUMBER()` window; pick rn=N.
- **innings_with_wicket / innings_with_two** — per-spell-touching: if the
  spell's total valid wickets ≥1 / ≥2, credit EVERY over bucket the
  bowler touched in that innings.
- **innings_qualifying + econ/runs bands** (`innings_econ_leq_6/7`,
  `innings_econ_geq_9/10`, `innings_runs_leq_15/25`, `innings_runs_geq_40/50`)
  — per-spell totals gate on ≥12 legal balls; credit every touched over
  when the spell's econ/runs cross the band.

Conventions (must match the populate exactly):
- runs_conceded = `SUM(runs_total)` over ALL deliveries (incl wides/no-balls).
- legal = `extras_wides=0 AND extras_noballs=0`.
- dot = `runs_batter=0 AND runs_total=0` (implies legal).
- boundary = `runs_batter IN (4,6)` (NO `runs_non_boundary` guard — the
  cohort tables count any 4 off the bat; matches the populate).
- valid wicket = `kind NOT IN ('run out','retired hurt','retired out',
  'obstructing the field')` (`BOWLER_WICKET_EXCLUDED`, 4 kinds — NOT the
  team-side's 5-kind set).
- over bucket = `delivery.over_number + 1` (table is 1-indexed).

## 2. The narrowing WHERE — bowling/fielding orientation

Reuse the team-side cohort clauses, side = bowling (= fielding for the
inning flip), team=None:

- **innings** — `_option_b_team_inning(None, "bowling", aux)` → flips:
  `i.innings_number = (1 - aux.inning)`.
- **toss / result** — `_cohort_outcome_clause("bowling", aux)` → keys the
  outcome on the OTHER team (the bowling side), not `i.team`.
- **venue / gender / type / tournament / season / tier / series** —
  `filters.build(has_innings_join=True, apply_inning=False, aux=aux)`,
  but with **team + opponent dropped from build** and re-added in
  bowling orientation:
  - **filter_team=X** (bowler's team) → `i.team != :bt AND (m.team1=:bt OR m.team2=:bt)`.
  - **filter_opponent=X** (bowled against X = X batting) → `i.team = :bo`.

  (build's native `i.team=:team` / against-clause is batting orientation;
  drop via `build(drop={"filter_team","filter_opponent"})` and add the
  flipped clauses, so the cohort narrows on the same axis as the
  bowler's OWN value — chip↔baseline symmetry.)

Factor this into `_bowling_live_where(filters, aux)` mirroring 3c's
`_batting_live_where`. VERIFY orientation: the integration test must
confirm the cohort and the bowler's own number both move under
filter_opponent (and SQL-anchor the cohort).

## 3. The live aggregation — nested SQL

Single helper `_bowling_over_live(db, filters, aux, *, by_season=False, person_id=None)`
returning rows with the SAME column names as the `playerscopestatsover`
SELECT so the downstream by_over builders stay identical. Shape:

```sql
WITH d AS (   -- filtered striker/bowler deliveries with over bucket
  SELECT d.innings_id, d.bowler_id, (d.over_number+1) AS ob,
         d.over_number AS ob0, d.runs_batter, d.runs_total,
         (d.extras_wides=0 AND d.extras_noballs=0) AS legal,
         m.season AS season
  FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
  WHERE <_bowling_live_where> AND d.bowler_id IS NOT NULL AND d.over_number BETWEEN 0 AND 19
),
spell AS (   -- per (innings, bowler): totals for thresholds + touch set
  SELECT innings_id, bowler_id,
         SUM(CASE WHEN legal THEN 1 ELSE 0 END) AS sp_balls,
         SUM(runs_total) AS sp_runs
  FROM d GROUP BY innings_id, bowler_id
),
wkt AS (   -- valid wickets with running per-spell count for attribution
  SELECT d2.innings_id, d2.bowler_id, (d2.over_number+1) AS ob,
         ROW_NUMBER() OVER (PARTITION BY d2.innings_id, d2.bowler_id
                            ORDER BY d2.over_number, d2.delivery_index, d2.id) AS rn
  FROM wicket w JOIN delivery d2 ON d2.id=w.delivery_id
  JOIN innings i ON ... JOIN match m ON ...
  WHERE <same where> AND w.kind NOT IN (BOWLER_WICKET_EXCLUDED)
)
-- then aggregate per (ob[, season]):
--   simple sums from d
--   maidens from (GROUP BY innings_id, ob0, bowler_id HAVING SUM legal=6 AND SUM runs_total=0)
--   innings_bowled = COUNT(DISTINCT innings_id||'-'||bowler_id) where legal
--   hauls = COUNT from wkt where rn IN (3,4,5) grouped by ob
--   innings_with_wicket/two + qualifying + bands = join spell to per-touch
--     (innings,bowler,ob) set, credit per band
```

Build incrementally — each commit's helper returns only the columns that
surface needs, with a parity probe for the added columns.

## 4. Sequencing — three commits + a pre-flip

0. **REG→NEW pre-flip** of any baselined bowling by-season/by-phase URL
   that hits the six (grep first). `pbsl_bowl_by_season_ipl_toss_won` is
   already NEW; `pbsl_bowl_by_phase_ipl_toss_won` already NEW. Check for
   REG ones.
1. **3d-1 by-phase** — smallest column set (runs/legal/wickets/dots/
   boundaries/maidens + n_players). Dispatch `compute_players_bowling_by_phase`.
2. **3d-2 by-season** — add innings_bowled + four_wicket_hauls + season
   grouping + parent `bowling_innings`. Dispatch `compute_players_bowling_by_season`.
3. **3d-3 summary + distribution** — add the full per-spell threshold set
   (innings_with_wicket/two, three/five_wicket_hauls, innings_qualifying,
   econ/runs bands). Dispatch `compute_players_bowling_cohort` (both
   batting.py call sites inherit). The hardest SQL — last.
4. **NEW→REG flip-back + docs** (mark 3d shipped; 3e fielding next).

Each commit: parity probe (live == precomputed at none-of-six, 0
mismatches) + extend `tests/integration/player_baseline_aux_fallback.sh`
with a bowling section (red→green narrowing + SQL anchor), mirroring the
batting §1/§5/§6 blocks. Filter-combination matrix per CLAUDE.md.

## 5. Tests

Anchor scope: J Bumrah (`462411b3`), IPL, closed seasons. Mirror the
batting tests:
- summary chip narrows + SQL-anchored vs live `delivery` aggregation.
- by-season overlay narrows; the `player_baseline_filter_matrix` bowling
  combos will START suppressing the reference line once bowling narrows —
  that test already keys off the cohort endpoint's `below_support`, so it
  adapts automatically (no rework needed — by design from the 3c fix).
- by-phase chips narrow.
- Parity sanity: an analog of `test_playerscopestatsposition_rollup.py`
  for `playerscopestatsover` (live vs precomputed at open scope).

## 6. Out of scope

- 3e fielding / keeping live (keeper-binary, `matchfielderperf`).
- Phase 4 docs sweep (whole-spec).
