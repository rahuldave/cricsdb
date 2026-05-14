# Session handoff — 2026-05-14 (follow-up session)

Phases B + A of `spec-series-precompute-followup.md` shipped this
session in five commits on `main`. Phase E permanently deferred.
Phases C + D punt to a NEW session. **No deploy yet** — see Deploy
gate section.

## Commits this session (all on `main`, nothing uncommitted)

```
e59e637 docs: mark Phases B + A SHIPPED in spec-series-precompute-followup.md
c10c869 perf: /series fielders-leaders via playerscopestats (Phase A, part 4/5)
228e5ba perf: /series batters-leaders + bowlers-leaders via playerscopestats (Phase A, parts 2-3/5)
f11b323 perf: /series top_scorer + top_wicket_taker via playerscopestats (Phase A, part 1/5)
d152ec2 perf: /series highest_team_total via bucketbaselinebatting.highest_inn_* (Phase B)
```

(Plus prior session's `0eb5ec9` — `bucketbaselinemoments` table —
which is the foundation for everything above.)

## Measured wall-clocks (HTTP, local DB, all-cricket scope)

| Endpoint | Before this session | After | Speedup |
|---|---|---|---|
| /series/summary | 6.4s | 0.33s | 19× |
| /series/batters-leaders | 5.2s | 0.31s | 17× |
| /series/bowlers-leaders | 3.6s | 0.27s | 13× |
| /series/fielders-leaders | 3.2s | 0.34s | 10× |

All four key /series tab endpoints now sub-second at all-cricket.

## Verification done this session

- ✅ `tests/sanity/test_bucket_baseline.py` ALL PASS (extended with
  `check_highest_team_total` × 5 scopes and
  `check_top_scorer_wicket_taker` × 5 scopes).
- ✅ `./tests/regression/run.sh series` — 0 REG drifted, 0 NEW changed
  across all 5 commits (output byte-identical to HEAD at every
  regression URL).
- ✅ Byte-identical full top-20 verified via direct diff at multiple
  scopes (all-cricket, IPL all-time, men's intl, women's intl, IPL
  2023, men's intl 2024) for batters/bowlers/fielders.
- ✅ Live SQL fallback paths verified (rivalry, venue) — same output
  as HEAD on `?filter_team=India&filter_opponent=Australia` and
  `?tournament=...&filter_venue=...`.
- ✅ New integration tests pass:
  - `tests/integration/series_highest_team_total.sh` (IPL 2023 + IPL
    all-time)
  - `tests/integration/series_top_scorer_wicket_taker.sh` (IPL
    all-time + Men's intl all-time)

## Deploy gate — `--first` still required, NOT YET deployed

The 2026-05-14 prior-session commit `0eb5ec9` introduced
`bucketbaselinemoments` (new table). Production DB does NOT have
that table. **Next deploy MUST be `bash deploy.sh --first`** to ship
the populated DB.

User decision 2026-05-14: hold the deploy until C + D are also done.
Phases C and D each introduce more schema changes — bundling all
schema changes into a single `--first` deploy is more efficient than
deploying twice.

If you DO need to ship B + A alone before C + D land, that's safe —
the code only reads from `bucketbaselinemoments` in the precomputed
regime, and the prior-session work already verified the table on
`/tmp/cricket-prod-snapshot.db`. But user preference is one combined
deploy after C + D.

## Phases C + D — what to do next session

Read `internal_docs/spec-series-precompute-followup.md` end-to-end
first. Specifically §Phase C and §Phase D — both are written with
schema + populate + endpoint + sanity + integration sub-sections.

### Phase C — Top partnerships per (cell, wicket)

**Target:** `/series/partnerships/top-by-wicket` 1.5s → ~50ms.

**Approach (spec recommends C2):** new table
`bucketbaselinepartnershiptop` keyed by (gender, team_type,
tournament, season, team, wicket_number, rank 1..10). Window
function ROW_NUMBER over `partnership` partitioned by (cell, team,
wicket_number) ordered by `partnership_runs DESC` picks top-10 per
combination. Est. ~1M rows total.

**Population:** new `_populate_partnership_top` in
`scripts/populate_bucket_baseline.py`. Wire into both `populate_full`
and `populate_incremental` (cell-filter DELETE + re-INSERT loop —
follow the existing pattern in `_populate_partnership`).

**Endpoint:** `api/routers/tournaments.py::tournament_partnerships_top_by_wicket`
— add `is_baseline` branch that reads from new table; live SQL fallback unchanged.

**Tests:** extend `test_bucket_baseline.py` with
`check_partnership_top_roundtrip` × 5 scopes (byte-identical
precompute-derived top-10 per wicket vs live SQL). Add
`tests/integration/series_partnerships_top_by_wicket.sh`. REG→NEW
flip in `tests/regression/series/urls.txt` if response ordering
changes at ties.

### Phase D — Per-team inning splits in bucketbaselinebatting/bowling

**Target:** `/teams/{team}/batting/by-inning` 865ms → ~50ms,
`/teams/{team}/bowling/by-inning` 1.46s → ~50ms.

**Approach:** add columns to `bucketbaselinebatting`:
`first_inn_legal_balls`, `first_inn_fours`, `first_inn_sixes`,
`first_inn_dots`, `second_inn_legal_balls`, `second_inn_fours`,
`second_inn_sixes`, `second_inn_dots`. Same shape for
`bucketbaselinebowling`: `first_inn_balls`, `first_inn_wickets`,
`first_inn_runs_conceded`, `first_inn_dots`, `second_inn_*`.

**Population:** extend `_populate_batting` and `_populate_bowling`
to compute inning splits via `CASE WHEN i.innings_number = 0 THEN ...
END` within the existing aggregation. No new tables, no new files —
just additive columns.

**Endpoint:** rewrite `/teams/{team}/batting/by-inning` and
`/bowling/by-inning` to SELECT directly from precomputed columns
(falls back to live SQL for venue/rivalry scopes).

**Tests:** sanity `check_inning_splits_roundtrip` × 5 scopes;
integration `tests/integration/teams_batting_by_inning.sh` and
`teams_bowling_by_inning.sh`.

### Cross-cutting carryover

- CLAUDE.md "perf changes — measure after every single change":
  every commit needs before/after timings in isolation.
- Sanity tests must run on local DB AND on
  `/tmp/cricket-prod-snapshot.db` (mirroring this session's
  discipline — populate_full + populate_incremental both must work
  on a DB that may or may not have existing bucket tables).
- REG→NEW flip discipline per `docs-sync.md` if response shape
  changes.
- Commit cadence: one feature per commit (spec estimates C = 3
  commits, D = 3 commits).

## Open files / tmp state

Nothing in the working tree (`git status` clean). `/tmp/` artifacts
from this session that can be deleted at will:

- `/tmp/preflight_phase_a.py` — first-pass pre-flight script (had
  bugs; superseded by v2).
- `/tmp/preflight_phase_a_v2.py` — corrected pre-flight, verified
  byte-identical at 5 scopes. Could be deleted or migrated into a
  proper sanity check if desired.
- `/tmp/trace_phase_a.py`, `/tmp/trace_summary.py` — debug helpers.
- `/tmp/head_*.txt`, `/tmp/a_*.txt` — diff inputs from byte-identical
  verification.
- `/tmp/sumA*.json` — HTTP capture artifacts.
- `/tmp/uvicorn_*.log` — server logs.

## See also

- `internal_docs/spec-series-precompute-followup.md` — the spec, now
  annotated with SHIPPED status for B + A and PERMANENTLY DEFERRED
  for E.
- `internal_docs/session-handoff-2026-05-14.md` — the prior-session
  handoff (moments work).
- `internal_docs/perf-bucket-baselines.md` — bucket baseline
  patterns + perf history.
