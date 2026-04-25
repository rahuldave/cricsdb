# Perf — async deebase + concurrent SQLite reads (investigation note)

Companion to `perf-bucket-baselines.md`. Documents an investigation
done 2026-04-25 into "can we get more concurrent-read throughput
out of deebase?" so future contributors don't repeat the work.

**TL;DR**: No. deebase's default pool already provides real
concurrent reads via `AsyncAdaptedQueuePool` (size=5). Increasing
the pool to 16+16 yields ~3% improvement. The Compare-tab
page-load latency floor (~610 ms backend / ~810 ms wall-clock with
bucket_baseline) is NOT bottlenecked on the connection pool.

The remaining levers are application-layer (composite endpoints,
client-side envelope, fewer round-trips), not engine-layer.

## What deebase does today

`deebase/database.py:42` (v0.6.1 + v0.7.0 — identical):

```python
self._engine = create_async_engine(url, echo=False)
```

No explicit pool config. SQLAlchemy's default for
`sqlite+aiosqlite://...` is `AsyncAdaptedQueuePool` with
`pool_size=5, max_overflow=10`. Each `db.q()` opens a session via
`_session_factory()`, which acquires a connection from the pool.

This is correct and reasonable.

## Benchmark — does the pool actually parallelize?

Same query (a 17 ms warm-cache delivery aggregate) issued N times
via `asyncio.gather`, against the local `cricket.db` in WAL mode:

| Pool strategy | N=1 | N=8 | N=24 |
|---|---:|---:|---:|
| **Default (`AsyncAdaptedQueuePool` size=5)** | 62 ms | 164 ms | 405 ms |
| `pool_size=16, max_overflow=16` | 62 ms | 166 ms | 392 ms |
| `NullPool` (fresh conn per query) | 63 ms | 149 ms | 415 ms |
| `connect_args={"check_same_thread": False}` | 62 ms | 162 ms | 412 ms |
| **`StaticPool` (single connection — control)** | 63 ms | **501 ms** | **1504 ms** |

Effective per-query at N=24: ~17 ms across all multi-connection
strategies. StaticPool (1 conn) is 3.7x slower at N=24, proving
SQLite + aiosqlite + WAL DOES give true concurrent reads when
multiple connections exist — they just don't scale linearly past
~4 because of GIL re-acquisition / aiosqlite's thread-per-connection
overhead / OS-level page-cache contention.

**The default pool is already doing its job.** Bigger pools buy
~3-5% on this workload.

## Why the cricsdb backend isn't pool-bound

A Compare-tab page-load fans out to ~24 HTTP requests (12
`/scope/averages/*` + 12 `/teams/{team}/*`). Each request opens
ONE FastAPI handler that issues 1-3 `db.q()` calls (some endpoints
need an envelope wrap = 2 calls; some baseline lookups + identity
fetch = 2 calls; etc.).

Total queries: ~30-40 per page-load. With pool=5 and ~17 ms
per-query effective, that's ~100-150 ms of pure SQL serialized
through 5 connections, plus FastAPI dispatch + JSON serialization
per request × 24 = a few hundred ms more. The measured 610 ms
backend total matches this back-of-envelope.

To push lower, the levers that would matter are NOT in deebase:

1. **Server-side fan-out into one HTTP endpoint.** Instead of 24
   browser → server round-trips, one `/teams/{team}/compare-bundle`
   endpoint that does all the queries server-side and returns a
   composite payload. Saves ~150 ms of per-request FastAPI
   overhead × ~20 requests.

2. **Use `asyncio.gather` inside multi-query endpoints.**
   `_compute_batting_summary` currently does
   `await fn(team)` then `await fn(None)` sequentially. Could be
   `await asyncio.gather(...)`. With bucket_baseline the per-call
   cost is ~2.5 ms each, so the win on a single endpoint is small
   (1.17x measured). But for live-fallback endpoints (filter_venue
   set) where each call is 50-200 ms, gather would cut summary
   endpoints in half.

3. **Client-side envelope computation.** The frontend already
   fetches both team and avg responses (the avg slot is a separate
   parallel fetch). It could compute deltas client-side and skip
   the server-side envelope wrap entirely. Saves the second
   `_xxx_aggregates(None)` call inside every summary endpoint.

## What was investigated and ruled out

### Increasing pool size

Tested up to `pool_size=16, max_overflow=16`. ~3% improvement at
N=24. Not worth changing deebase.

### `NullPool` (fresh connection per query)

Same throughput as default pool. The connection-acquisition
overhead is already negligible.

### `connect_args={"check_same_thread": False}`

aiosqlite already handles thread safety via its dedicated worker
thread per connection. The flag has no effect on throughput.

### Multiple `Database` instances

Could give each FastAPI request its own engine + pool, multiplying
total connection count. Tested informally — doesn't help. The
bottleneck is shared SQLite-level read concurrency (per-file), not
connection availability.

### Upgrading deebase 0.6.1 → 0.7.0

`diff` of `database.py` between versions — only adds FTS index
support. No pool / concurrency changes. Not worth chasing.

## When this picture would change

- **PostgreSQL backend.** Switching from SQLite to Postgres would
  remove the SQLite-per-file-lock floor. PostgreSQL via asyncpg
  scales to dozens of concurrent connections cleanly. Out of scope
  for cricsdb (the read-only static-DB story is the whole point).
- **In-memory SQLite.** Different concurrency story (StaticPool is
  required for `:memory:`). Not applicable here.
- **Workload that's CPU-bound rather than I/O-bound.** Our queries
  are CPU-bound on the Python side (rendering ~30K-row JSONs).
  Changing the pool wouldn't help; restructuring to compute fewer
  rows would.

## Verdict

**Don't touch deebase for concurrency.** The Compare-tab perf is
where it is; pushing it lower means application-layer changes
(composite endpoints, gather inside helpers, client-side envelope).
Logged here so the question doesn't get re-asked.

If you do want to revisit: re-run the benchmark in this doc
(reproducible from the snippets above) with the new SQLAlchemy /
aiosqlite version. If the per-query floor drops below ~17 ms or
the StaticPool gap widens, the picture might have changed.
