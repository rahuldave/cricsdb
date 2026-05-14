# Session handoff — 2026-05-14 perf session

Working tree at session end. **Nothing committed yet.** Read this
plus `spec-series-precompute-followup.md` to resume.

## Diff in working tree (uncommitted)

```
 M api/routers/bucket_baseline_dispatch.py   +17 / -3
 M api/routers/tournaments.py                +171 / -55
 M models/tables.py                          +51 / 0
 M scripts/populate_bucket_baseline.py       +195 / -10
 M tests/sanity/test_bucket_baseline.py      +24 / -12
?? internal_docs/spec-series-precompute-followup.md
?? internal_docs/session-handoff-2026-05-14.md  (this file)
 M internal_docs/next-session-ideas.md       +17 / -2
```

All changes belong to a SINGLE feature: **bucketbaselinemoments
precompute**. Recommended commit shape — ONE commit covering all
five `M` source files (modeled on the existing bucket-baseline
spec's pattern), plus the new spec + handoff doc as a SECOND commit
or merged.

## What the diff does

1. **`models/tables.py`** — adds `BucketBaselineMoments` class:
   per (gender, team_type, tournament, season) cell with hi_* /
   bb_* / bf_* columns for highest_individual / best_bowling /
   best_fielding. No `team` column — rivalry-scoped requests fall
   back to live SQL.

2. **`scripts/populate_bucket_baseline.py`** — imports the new
   model, adds it to `BUCKET_TABLES`, adds index in
   `_ensure_tables`, adds `_populate_moments(db, cells=None)`
   function (3-step: INSERT hi_* via window-function pick,
   UPDATE bb_* via UPDATE…FROM, UPDATE bf_* via UPDATE…FROM),
   wires into `populate_full` + `populate_incremental` (DELETE +
   re-INSERT loop).

3. **`api/routers/bucket_baseline_dispatch.py`** — modifies
   `baseline_where` to accept `team=None` (skip the team clause).
   Used by the moments path since the new table has no team
   column.

4. **`api/routers/tournaments.py`** — adds `is_baseline` branch in
   `/series/summary`'s hi_q/bb_q/bf_q construction. Baseline mode
   reads from `bucketbaselinemoments` (3 small queries, ~1ms each).
   Non-baseline mode (rivalry, venue, aux.inning, series_type ≠
   'all') keeps the live GROUP BY (person, match) SQL unchanged.

5. **`tests/sanity/test_bucket_baseline.py`** — extends
   `check_incremental_roundtrip` to cover bucketbaselinemoments in
   the incremental round-trip check.

6. **`internal_docs/next-session-ideas.md`** — top-of-queue
   entry pointing at `spec-series-precompute-followup.md`.

7. **`internal_docs/spec-series-precompute-followup.md`** — new
   spec for Phases B → A → C → D → E.

## Verification done this session

- ✅ `populate_full` on local DB (30.7s for moments step, 1159 rows)
- ✅ Bucket-derived hi/bb/bf byte-identical to live SQL at 3 scopes
  (all-cricket, men's club, women's intl)
- ✅ Single-cell incremental on `/tmp/cricsdb_incremental_test.db`
  (IPL 2025) — row byte-identical to full rebuild
- ✅ Multi-cell incremental (8 random cells) — all cells
  byte-identical, untouched cells unchanged
- ✅ `tests/sanity/test_bucket_baseline.py` ALL PASS including
  new moments coverage
- ✅ `populate_full` + `populate_incremental` on prod-snapshot DB
  at `/tmp/cricket-prod-snapshot.db` (414 MB Downloads DB with NO
  prior bucket tables) — both work end-to-end, 1136 moments rows,
  5-cell incremental in 1.52s byte-identical
- ✅ `/series/summary` HTTP at all-cricket: 6.4s → 4.6s (3 runs)
- ✅ `/series` page-load (prod build): ~6.5s → ~5.0s

## Open items the next session should address

1. **Commit the diff** — single commit (or split sensibly).
   Suggested message: `perf: precompute /series moments
   (highest_individual / best_bowling / best_fielding) per cell`.
2. **Deploy `--first`** — bucketbaselinemoments doesn't exist on
   prod yet.
3. **Begin Phase B** (free win) per `spec-series-precompute-followup.md`.

## Files left in /tmp (not in project)

- `/tmp/cricsdb_incremental_test.db` — copy of project DB used for
  incremental tests. Delete when done if desired.
- `/tmp/cricket-prod-snapshot.db` — copy of prod-snapshot DB used
  for end-to-end populate test. Now has all 7 bucket tables
  populated. Delete when done.
- HAR captures `/tmp/h*.har`, `/tmp/t_*.har`, `/tmp/series_load.har` —
  page-load network traces.
- `/tmp/perf_baseline.sql` — the SQL test harness used for the
  abandoned indexes experiment.

## Performance summary table

Page-load /series at all-cricket (prod build):

| State | Wall-clock | Notes |
|---|---|---|
| Start of session | ~7.5s | Pre-everything |
| After option 2 indexes only | ~6.5s | Rolled back after option 1 superseded |
| **End of session (option 1 shipped)** | **~5.0s** | Bound by /series/landing 2s + new bottleneck ts_q 2.8s |

`/series/summary` HTTP at all-cricket:

| State | Time |
|---|---|
| Pre-everything | 6.4s avg |
| After option 2 indexes only | 5.9s avg |
| **After option 1 precompute (current)** | **4.6s avg** |

Per-query gather timings post-moments (raw sqlite3):

- meta_q / bat_q / wkt_q / top_teams_q / hi_q / bb_q / bf_q: <100ms each (precomputed)
- **ts_q: 2.78s** ← next bottleneck (Phase A target)
- tw_q: 0.28s (Phase A also)
- ht_q: 0.35s (Phase B target)
- lp_q / finals_q: small

See `spec-series-precompute-followup.md` for the phase plan.
