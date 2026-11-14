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

## 2026-11-14: open issues in the database, the tests and deebase

These issues came up while the docs were fixed in November 2026. Nothing here is fixed yet. Each item
gives the facts, the evidence and the action. "The main checkout" is `~/Projects/cricsdb`, the folder that
`deploy.sh` runs from.

### deebase: production ships a hand-patched 0.6.1

- The `.venv` of the main checkout reports deebase 0.6.1, in
  `.venv/lib/python3.14/site-packages/deebase-0.6.1.dist-info`.
- Its `deebase/database.py` is patched by hand. The file's sha256 is
  `Qblgpa3oUJsPb-_ydf_so71IJz0gBcGdd5F3ASs6MFk`, but `RECORD` gives
  `7rBs9IJOklXPSxgvtc-m-MLwMBr41FeI5445ESYfQEU`. The patch adds the `params` argument to
  `Database.q(query, params)`, which the routers use. The published 0.6.1 has no `params`.
- `deploy.sh` does not install deebase from PyPI. Its comment at line 46 says "deebase itself is
  vendored", and the `requirements.txt` that it writes at lines 47-63 has no deebase. Lines 65-67 copy
  the package from the `.venv`:

  ```bash
  # Vendor deebase (requires Python 3.13+, plash has 3.12)
  cp -r .venv/lib/python3.14/site-packages/deebase "$BUILD_DIR/deebase"
  rm -rf "$BUILD_DIR/deebase/__pycache__" "$BUILD_DIR/deebase"/*/__pycache__
  ```

  So production runs the patched copy of 0.6.1.
- PR #8 moved `pyproject.toml`, `requirements.txt` and `uv.lock` to `deebase>=0.7.0`. Version 0.7.0 is
  published. Its `Database.q` is the same code as the patched copy, and it adds full-text search (the
  new `fts.py`). With `uv sync --frozen` and 0.7.0, the app runs.

**Action for Rahul:** run `uv sync` in the main checkout before the next deploy. Then `deploy.sh`
copies 0.7.0, and production ships a published release instead of a patched copy. Check it with
`uv pip show deebase`, which must say 0.7.0. Line 66 names `python3.14` in the path, so the copy breaks if
the `.venv` uses another Python.

### Four sanity tests fail, and none of the failures comes from deebase

The tests were re-run on 2026-11-14 on a copy of `cricket.db`, with deebase 0.7.0. The four tests
only read the database. All four still fail.

1. **`tests/sanity/test_dispatch_equivalence.py`**: "201 pairs equivalent, 11 failures". All 11 are
   `scope/fielding/by-season`, one for each of the 11 scopes. The error is
   `_fielding_by_season_live() missing 2 required positional arguments: 'filters' and 'aux'`.
   - Cause: `api/routers/scope_averages.py` defines `_fielding_by_season_live` twice. The second
     definition, at line 5094, takes `(db, person_id, filters, aux)`. It came with commit `e608da0` (Phase
     3e by-season). It replaces the first one, at line 1348, which takes `(filters, aux)`.
   - The app has the bug too. The endpoint `/api/v1/scope/averages/fielding/by-season`
     calls `_fielding_by_season_live(filters, aux)` at line 1288 for every scope that is not precomputed.
     So it returns HTTP 500 for those scopes. For example, `?tournament=Indian%20Premier%20League&inning=0`
     and `?...&filter_venue=Wankhede%20Stadium` both give 500. A plain IPL 2024 scope gives 200, because it
     is precomputed. The front end calls this endpoint, in `frontend/src/api.ts:972`.
2. **`tests/sanity/test_playerscopestats_position.py`**: `[FAIL] SUM(pssp.dismissals) == pss.dismissals`,
   "1 (person, scope) rows mismatch". The check is at lines 106-129.
   - The row is R Choden (`c0266a6e`) in the Asian Cricket Council Women's Premier Cup 2026 (scope key
     `9e00dd9c6878`). `playerscopestats` has `innings_batted = 2` and `dismissals = 3`. The position
     rows (`playerscopestatsposition`) have 2 innings and 2 dismissals.
   - The third dismissal is "timed out", in match 13370. She faced no ball in that match, so the
     position table has no innings for it. The parent table counts the dismissal. So the cause is the
     rule for a dismissal with no ball faced, and probably not a drift of the precomputed tables.
3. **`tests/sanity/test_team_class_club_baseline_numbers.py`**: 8 failures. The anchors are at lines 80
   and 102. The team anchors (T1-T5) date from 2026-04-30. INV1 and INV2 were refreshed in commit
   `fa346e5` on 2026-05-27.
   - The completeness check, at line 227, reports "6 untagged events". They are 'Vitality Blast Women' (56 matches),
     'Major Clubs T20 Tournament' (49), 'European T20 Premier League' (31), "Women's Caribbean Premier
     League" (8), 'Cricket Ireland Inter-Provincial Twenty20 Trophy' (7) and 'CSA Pro20' (6). All are
     from the 2026 or 2026/27 seasons. None is in `PRIMARY_CLUB_LEAGUES` or `SECONDARY_CLUB_LEAGUES`
     (`api/club_tiers.py:31` and `:49`). So these 157 matches are in neither club tier.
   - The other 7 failures are counts that grew with the new data. The checks are at lines 259-268, 366
     and 368. Each count is given with its anchor in brackets:
     - INV1, all club T20 matches, 8050 (7607)
     - INV2, primary, 4783 (4612), and INV3, secondary, 3110 (2995)
     - INV4, untagged events, 6 (0), and INV5, the partition sum, 4783 + 3110 = 7893 (7607)
     - T1, men's primary teams, 112 (105), and T3, women's primary teams, 30 (27)
4. **`tests/sanity/test_prob_baselines_batting.py`**: `[FAIL] p_50_given_30 scope_avg matches
   bucket-grain cv`, "expected≈0.4866, actual=0.4855". The assertion is at lines 229-234. It needs the
   API server; pass `--host`.
   - Cause: the SQL of the test, at lines 206-216, joins `playerscopestats` to
     `playerscopestatsposition` on `scope_key` only, with no `person_id`. So each position row counts once
     for every player in its scope. With `AND pss.person_id = pssp.person_id` added, the expected value
     is 0.48555, which is the endpoint's 0.4855. So the endpoint is right, and the test is wrong.
   - The query of test 4, at lines 172-181, has the same join. It passes today only because the
     difference stays inside the tolerance of 0.001.

### Regression URLs that match nothing

- `tests/regression/head_to_head/urls.txt:76-79` has four `NEW` rows for
  `/api/v1/head-to-head?team1=...&team2=...`. The API has only `/api/v1/head-to-head/{batter_id}/{bowler_id}`
  (`api/routers/head_to_head.py:30`), so these rows give 404. The team rivalry is at
  `/api/v1/rivalries/summary`. The front-end page `/head-to-head` exists; only these API URLs are wrong.
- `tests/regression/venues/urls.txt:83-84` asks for `/api/v1/venues/MA%20Chidambaram%20Stadium/summary`,
  which gives 404 "Venue not found". The canonical name in the database is
  "MA Chidambaram Stadium, Chepauk" (113 matches). The row in
  `tests/regression/fielder_distribution/urls.txt:49` already uses that name.

### Other docs that still claim the 400 on `/teams/splits`

The 400 for `?result=` or `?toss_outcome=` without `?team=` was lifted on 2026-05-11 (commit `37d6c1e`).
These places still state it, and need a fix:

- `CLAUDE.md:343`
- `docs/internal/splits-mosaic-cross-page.md:161-165`
- `docs/internal/spec-splits-mosaic.md:68-74`, `:285-286`, `:306` and `:321`. The code comment in
  `team_splits` says "Spec §1.4 amended", but the spec still says 400.
- `docs/internal/design-decisions.md:2297`, in the heading of its section.

### The venue worklist of 2026-10-26

- `docs/venue-worklist/unknowns-2026-10-26.csv` has the row
  `Complejo Municipal de Beisbol de Texcoco,Texcoco de Mora` twice.
- The likely cause is two runs of `scripts/fix_venue_names.py` on the same day. Line 164 opens
  `unknowns-<date>.csv` in append mode (`"a"`), and lines 163-167 write the header only when the file is
  new. So a second run on 2026-10-26 added the same unknown row again under the one header.
- A second, smaller cause is possible. The query groups by `venue, city, venue_country` (lines 77-84),
  and line 113 appends each unknown group with no dedupe. So one `(venue, city)` pair in two groups gives
  two rows in one run. On the copy of the database of 2026-11-14, the two Texcoco matches are in one
  group (`venue_country` NULL), so this cause does not apply to them now.
- The Texcoco venue is not yet in `VENUE_ALIASES` (`api/venue_aliases.py:38`). Its 2 matches have
  `venue_country` NULL.

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

`deploy.sh:115` does the path translation on upload (with `--first`):

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
