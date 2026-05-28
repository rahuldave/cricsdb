# Plan — Phase 3b: batting live cohort for the six aux/filter axes

**Spec:** `internal_docs/spec-player-baseline-aux-fallback.md` Phase 3b
(unblocked once the all-ball single-source spec landed —
`inningsbatterperf` is now convention-correct + complete and
`playerscopestatsposition` is its exact-integer rollup).

**Goal:** when any of the six (venue / opponent / team / innings / toss /
result) is set, the player batting "typical player" comparison narrows to
match. Today it's frozen at the all-axes-open scope. The own number
already narrows (Phase 1+2). Fairness rule D9 — both must move together.

---

## 1. Locations

- **Cohort fn (the one place):** `api/routers/scope_averages.py:1815`
  `compute_players_batting_cohort(db, filters, aux, mix, drop_set)`.
- **Call sites (both already pass `aux` — no plumbing change):**
  - `api/routers/batting.py:525` — `/batters/{id}/summary`'s cohort chip.
  - `api/routers/batting.py:1782` — `/batters/{id}/distribution`'s
    milestone enrichment.
- **Dispatch:** `api/routers/bucket_baseline_dispatch.py:21`
  `is_precomputed_scope(filters, aux)` — already returns False for
  exactly the six (venue / team / opponent / inning / result /
  toss_outcome). Reuse unchanged.
- **Reusable team-side cohort clauses** (no rewrite — same shape as the
  league-side aggregation keyed on each cohort player's own team):
  - `api/routers/teams.py:121` `_option_b_team_inning(team, side, aux)` —
    discipline-aware inning narrowing. For batting cohort, `side="batting"`
    binds `i.innings_number = :ob_inn`.
  - `api/routers/teams.py:221` `_cohort_outcome_clause(side, aux)` — per-row
    toss/result clause keyed on `i.team` (the batting team). Documents
    why won-toss ≈50% of matches but their STATS differ — the narrowed
    baseline is real, not tautological.
- **Standard match/innings clauses** via `FilterParams.build(
  has_innings_join=True, apply_inning=False, aux=aux)` — already returns
  WHERE for venue, filter_team (`i.team = :team`), filter_opponent
  (discipline-aware against `m.team1/m.team2` vs `i.team`), plus all the
  non-six axes.

## 2. Live aggregation shape (per spec §8.3)

The precomputed read groups `playerscopestatsposition` by
`position_bucket` after scope_key filtering. The live read replaces the
source — same column shape so the convex_combine / cliff gate / output
envelope downstream stay identical.

```sql
SELECT ib.position_bucket,
       COUNT(*)                                                              AS innings,
       SUM(ib.runs)                                                          AS runs,
       SUM(ib.balls)                                                         AS legal_balls,
       SUM(CASE WHEN ib.not_out = 0 THEN 1 ELSE 0 END)                       AS dismissals,
       SUM(ib.fours)                                                         AS fours,
       SUM(ib.sixes)                                                         AS sixes,
       SUM(ib.dots)                                                          AS dots,
       SUM(CASE WHEN ib.runs >= 30  AND ib.runs < 50  THEN 1 ELSE 0 END)     AS thirties,
       SUM(CASE WHEN ib.runs >= 50  AND ib.runs < 100 THEN 1 ELSE 0 END)     AS fifties,
       SUM(CASE WHEN ib.runs >= 100                   THEN 1 ELSE 0 END)     AS hundreds,
       SUM(CASE WHEN ib.runs =  0   AND ib.not_out = 0 THEN 1 ELSE 0 END)    AS ducks,
       SUM(CASE WHEN ib.runs <= 10                    THEN 1 ELSE 0 END)     AS failures_10,
       SUM(CASE WHEN ib.runs >= 70  AND ib.runs < 100 THEN 1 ELSE 0 END)     AS seventies,
       COUNT(DISTINCT ib.batter_id)                                          AS n_players
FROM inningsbatterperf ib
JOIN innings i ON i.id = ib.innings_id
JOIN match   m ON m.id = i.match_id
WHERE i.super_over = 0
  AND <FilterParams.build clauses>          -- gender/team_type/tournament/season + venue/team/opponent + team_class + series_type
  AND <_option_b_team_inning(None, 'batting', aux)>   -- innings
  AND <_cohort_outcome_clause('batting', aux)>        -- toss + result
GROUP BY ib.position_bucket
```

Pool query is the same skeleton without the GROUP BY, returning
`COUNT(DISTINCT batter_id) AS n_players` and `COUNT(*) AS n_innings_total`.

The covering index from 3a
(`ix_inningsbatterperf_innings_id_position_bucket_runs_balls_fours_sixes_dots_not_out`)
serves the GROUP BY; `innings(match_id)` + match indexes already exist.
**Measure first, add only if a number forces it** (CLAUDE.md perf rule).

## 3. The dispatch

```python
async def compute_players_batting_cohort(db, filters, aux, mix, drop_set=None):
    from .bucket_baseline_dispatch import is_precomputed_scope
    if is_precomputed_scope(filters, aux):
        rows, pool = await _batting_cohort_precomputed(db, filters, drop_set)
    else:
        rows, pool = await _batting_cohort_live(db, filters, aux)
    # ↓ unchanged below — same by_position[] build, cliff gate,
    #   convex_combine, envelope-wrap.
```

Split the existing function: the SQL pair becomes
`_batting_cohort_precomputed(...)` (the current scope-key form) and
`_batting_cohort_live(...)` (the new per-innings form). Everything from
`by_bucket = {...}` onwards is preserved exactly.

`drop_set` is precomputed-only (it masks the `playerscopestats` scope
columns — meaningless on the live path which queries the match table).
Live path ignores it; the live path inherently doesn't take cohort-pool-
masking drops (callers don't pass any today for the batting cohort, per
the grep at the two batting.py call sites).

## 4. Tests (red-then-green)

`tests/integration/player_baseline_aux_fallback.sh` — new file. For each
of the six filters, an `/batters/{PERSON_ID}/summary` curl returns a
cohort `scope_avg` that MUST move vs. the unfiltered-cohort baseline,
AND must equal the direct SQL aggregation over `inningsbatterperf` for
that filter (mix-weighted using the player's filtered position mix).

Stable scope: V Kohli (`be4d0e0c` — verify), `gender=male`,
`team_type=international`, `season_from=2016&season_to=2016` (closed
year). The six filters one at a time:

- `filter_venue=<a venue Kohli played at in 2016>`
- `filter_opponent=Australia`
- `filter_team=India` (subject team — both own + cohort narrow)
- `inning=0`
- `result=won`
- `toss_outcome=won`

Per assertion: read the cohort `strike_rate` from the response,
re-derive it from `inningsbatterperf` joined to innings+match with the
same WHERE, convex-combine by Kohli's filtered position-mix from
`/batters/{id}/distribution`'s `position_distribution[]`. Assert match
to 1dp. Plus assert ≠ the unfiltered scope's value (so the test catches
the "frozen" regression).

Companion sanity test for parity at none-of-six already exists
(`test_playerscopestatsposition_rollup.py` — exact integer; that pins
the precomputed path is identical to a live aggregation over the same
table at the open scope).

Filter-combination matrix (CLAUDE.md mandatory) — run via
`agent-browser` on the actual page at the URL:
- player + venue
- player + opponent
- player + team + opponent
- chained season + opponent
- bowling-tab innings flip — VERIFIES the dispatch passes through but
  3b only fixes batting. Bowling stays frozen until 3d. Document this
  in the test.

## 5. Sequencing — one commit

Per CLAUDE.md commit cadence + scope discipline, 3b ships in ONE commit:
1. Add `_batting_cohort_live(...)` + branch in
   `compute_players_batting_cohort`.
2. New `tests/integration/player_baseline_aux_fallback.sh` red-then-green.
3. This plan doc.

No deploy until 3c–3e + docs land (per spec §3 and the
all-ball spec held-local note).

## 6. Out of scope (deferred)

- 3c (by-season / by-phase / by-over batting) — separate function
  family; same dispatch pattern.
- 3d (bowling live) — different table; no `inningsbatterperf` analog.
- 3e (fielding/keeping live) — `matchfielderperf` + keeper flag.
- Sample-size tooltip wording (D7) — already populates via
  `cohort["cohort"]["n_innings_total"]`; if the live path returns the
  same shape the existing tooltip surfaces it for free.
- Confidence intervals (D6).
- Team-side support cliff (D8).
