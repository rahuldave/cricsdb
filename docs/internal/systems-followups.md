# Systems-level state + perf follow-ups

A living catch-all for systems-side knowledge accumulated during
2026-04-25's Compare-tab Phase 2 work. Use as the entry point when
you come back cold to "what's the perf situation? what's safe to
touch? what's the next lever?".

Pairs with:
- `perf-bucket-baselines.md` — the bucket_baseline_* table runbook.
- `perf-async-deebase.md` — the deebase pool / async SQLite
  investigation (with reproducible benchmarks).
- `perf-leaderboards.md` — the older leaderboard-index perf doc.
- `tests.md` — the catalog of how to verify nothing regresses.

## Three cricket.db files (DO NOT confuse them)

```
./cricket.db                                          ← THE ACTIVE LOCAL DB
  - Project root. ~648 MB after Phase 2 (was ~435 MB pre-baseline).
  - Uvicorn reads this when PLASH_PRODUCTION is unset (the dev case).
  - This is what `bash deploy.sh --first` ships to plash's
    data/cricket.db.
  - Mutate freely — re-runs of import_data.py / update_recent.py /
    populate_*.py target this.

data/cricket.db                                       ← only-read-on-prod path
  - Empty/missing locally. Stale Apr 5 leftover was moved to
    /tmp/cricket-stale-backup-2026-04-25/ on 2026-04-25.
  - Uvicorn reads this when PLASH_PRODUCTION=1 (the prod case on
    plash). Locally never read unless you set that env var.

~/Downloads/t20-cricket-db_download/data/cricket.db   ← prod export snapshot
  - Apr 6 vintage. Used as the read-only "known-good" reference
    DB for testing populate scripts against an older shape.
  - Per CLAUDE.md memory: never mutate. Copy via
    `sqlite3 source.db ".backup /tmp/dest.db"` (NOT `cp` — WAL
    sidecars matter) and mutate only the /tmp copy.
  - Has 12,940 matches; empty fieldingcredit + partnership tables
    (predates those populate pipelines).
```

The `api/dependencies.py:19-22` switch:

```python
if os.environ.get("PLASH_PRODUCTION") == "1":
    db_path = "data/cricket.db"
else:
    db_path = "./cricket.db"
```

`deploy.sh:89` does the path translation on upload:

```bash
cp cricket.db "$BUILD_DIR/data/cricket.db"
```

## Where we are on Compare-tab perf

Measured wall-clock to "avg column visible" on the canonical
unbounded URL `/teams?team=Royal+Challengers+Bengaluru&gender=male
&team_type=club&tab=Compare&compare1=__avg__`:

| Phase | DEV (StrictMode 2x) | PROD |
|---|---|---|
| Pre-everything | 5 s | 4 s |
| Phase 1 (auto-scope-team + ix_matchplayer_team) | ~5 s | ~4 s |
| Phase 2 P2-A/B/C (8/12 + 2/12 dispatched) | 2.9 s | 1.7 s |
| **Phase 2 complete (D/E/F + bug fixes)** | ~2.5 s | **0.81 s** |

**5x prod speedup.** Backend 24-endpoint parallel sum: ~610 ms.
SQLite per-query effective floor at high N: ~17 ms.

## Where the next 600 ms could come from (application-layer)

deebase is NOT the bottleneck (see `perf-async-deebase.md`). The
remaining levers, ranked by expected impact:

### 1. Composite Compare-tab endpoint (high impact)

A single `/teams/{team}/compare-bundle?...` that fans out to all
the queries server-side and returns one composite payload. Saves:

- ~40 ms of FastAPI dispatch overhead per request × 24 requests
  collapsed to 1 = ~1 s of overhead saved (rough order).
- Browser side: 1 fetch instead of 24 = simpler error handling,
  one cache entry, one loading state.

Frontend impact: `getTeamProfile` + `getScopeAverageProfile` → one
call. Minimal UI change since the data shape can mirror what the
two existing composers produce.

Backend impact: write the route handler that calls the existing
`_xxx_aggregates` helpers via `asyncio.gather` and assembles the
result. ~150-200 lines including the response model.

Estimated prod page-load after: 0.81 s → 0.35-0.45 s.

### 2. `asyncio.gather` inside multi-query helpers (low impact post-baseline)

`_compute_batting_summary` does:

```python
t = await _batting_aggregates(team, filters, aux)
s = await _batting_aggregates(None, filters, aux)
```

Could be:

```python
t, s = await asyncio.gather(
    _batting_aggregates(team, filters, aux),
    _batting_aggregates(None, filters, aux),
)
```

Measured speedup post-bucket-baseline: 1.17x (each call is ~2.5 ms;
gather barely helps). Pre-baseline / on live-fallback paths the win
is much bigger (~2x). Worth doing if we touch these helpers anyway,
not worth a dedicated pass.

### 3. Client-side envelope computation (medium impact, big refactor)

Today every team-side summary endpoint internally does the team
call + the `team=None` league call to build the `{value, scope_avg,
delta_pct, ...}` envelope server-side.

The frontend ALREADY fetches both — `getTeamProfile(team, scope)`
AND `getScopeAverageProfile(scope)` in parallel. It could compute
the envelope in `MetricDelta` / `wrap_metric` JS instead of taking
both server-side payloads pre-wrapped.

Saves: every team summary endpoint becomes ~half the work
internally. ~200 ms saved off the backend total.

Cost: bigger refactor — every consumer of the envelope shape
shifts client-side. Touches `types.ts`, every chip-rendering
component. Worth ~1 day.

### 4. Cleanup of `/teams/{team}/partnerships/summary` (best_pair)

The lone holdout from the bucket_baseline dispatch. Returns
`best_pair` (top pair by total runs together — needs per-(batter1,
batter2) aggregation). Two ways:

- Sidecar table `bucket_baseline_top_pairs(g, tt, t, s, team,
  batter1_id, batter2_id, n, total_runs, best_runs)`. ~50K rows.
  Populate routine canonicalizes the pair as `min(id), max(id)`.
- Or just leave it on live — it's only ~300 ms and rarely hit.

## What's already populated locally (skip if you don't deploy)

After this session, `./cricket.db` has:

- 13,026 matches (latest 2026-04-16).
- 6 bucketbaseline_* tables with ~96K rows total.
- ix_matchplayer_team index.
- All previously-existing tables/indexes.

To deploy, ship via `bash deploy.sh --first` — uploads the whole
647 MB DB. Subsequent deploys without `--first` ship code only;
prod's bucket_baseline tables update via `update_recent.py` running
on plash (it auto-calls `populate_bucket_baseline.populate_incremental`).

**First deploy after Phase 2 MUST be `--first`** so prod gets the
populated baseline tables. After that, incremental works.

## Reproducible benchmarks (run anytime)

```bash
# Deebase pool / async SQLite concurrency
# (cuts to ~1 minute, paste into terminal)
uv run python <<'PY'
import asyncio, time
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy import text

SQL = """SELECT COUNT(*), SUM(d.runs_total) FROM delivery d
JOIN innings i ON i.id = d.innings_id JOIN match m ON m.id = i.match_id
WHERE i.super_over = 0 AND m.gender='male' AND m.team_type='club'
AND m.event_name='Indian Premier League'"""

async def time_n(eng, n):
    async def q():
        async with eng.connect() as c:
            r = await c.execute(text(SQL))
            return r.fetchall()
    await q()
    t0 = time.time()
    await asyncio.gather(*[q() for _ in range(n)])
    return (time.time()-t0)*1000

async def main():
    e_default = create_async_engine("sqlite+aiosqlite:///cricket.db")
    e_static  = create_async_engine("sqlite+aiosqlite:///cricket.db", poolclass=StaticPool)
    for n in (1, 8, 24):
        print(f"N={n:2d}  default={await time_n(e_default, n):4.0f} ms  static={await time_n(e_static, n):5.0f} ms")
    await e_default.dispose(); await e_static.dispose()
asyncio.run(main())
PY
```

Expected output (numbers vary ±20%):

```
N= 1  default=  60 ms  static=   60 ms
N= 8  default= 165 ms  static=  500 ms
N=24  default= 405 ms  static= 1500 ms
```

If StaticPool's N=24 isn't ~3x default's N=24, something has
changed in deebase / SQLAlchemy / aiosqlite — re-investigate.

```bash
# End-to-end Compare-tab page-load (prod build)
cd frontend && npm run build && npm run preview -- --port 4173 &
sleep 2
agent-browser open "http://localhost:4173/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tab=Compare&compare1=__avg__"
# Watch for "Avg in Royal Challengers Bengaluru's leagues" to appear
# Expected: < 1 s
```

## Things that are SAFE to ignore

- `./data/cricket.db` is gone (moved to /tmp backup). If something
  weirdly tries to read it, the fix is to fix that something —
  don't restore the file.
- The `NEW unchanged` markers in `tests/regression/run.sh` output
  for `series` / `venues` / `filterbar_refs` suites are pre-existing
  bookkeeping from past refactors. Not related to Phase 2.
- The 4-kind vs 5-kind bowler-wickets debate is settled at 5-kind.
  Don't reintroduce 4-kind anywhere.

## Things to NOT touch without thinking

- The `_session_factory` in `deebase/database.py:48-52`. We
  validated the default pool config works correctly. Bigger pools
  yield ~3%. Don't rabbit-hole.
- The bucket_baseline schema column ordering. Tests rely on
  byte-identical SELECT * ordering in some places. Add new columns
  at the END.
- The 5 conventions in `perf-bucket-baselines.md` (5-kind exclusion,
  wides count vs runs, catches incl/excl c_a_b, NULL tournament =
  '', empty-fielding emit zero rows). Each is documented because
  it's non-obvious; future-you might try to "fix" them.

## When to re-open this doc

- "Page-load feels slow" — check `perf-bucket-baselines.md`
  conventions first; if they're intact, the lever is application-
  layer (composite endpoint).
- "Async deebase" / "concurrent reads" / "connection pool" —
  re-read `perf-async-deebase.md` before changing anything.
- "What's actually deployed?" — see Three-cricket.db-files section
  above; check `bash deploy.sh` history.
- "Tests are weird" — see `tests.md`.
