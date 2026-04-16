# Performance: batting & bowling leaderboards

The `/api/v1/batters/leaders` and `/api/v1/bowlers/leaders` endpoints
power the landing pages under `/batting` and `/bowling` (shown when no
player is selected). Each returns two top-10 lists (avg + SR for
batting; SR + econ for bowling) that are filter-aware.

Unfiltered these endpoints aggregate over the full 2.95M-row `delivery`
table. This doc captures the three fixes that brought the no-filter
response from **3+ seconds → sub-second**, and the reasoning so the
pattern can be re-applied to future leaderboard endpoints.

## Measured impact

| Scope                          | Before | After  | Speedup |
| ------------------------------ | -----: | -----: | ------: |
| Batting leaders (unfiltered)   |  3.22s |  0.83s |    3.9× |
| Bowling leaders (unfiltered)   |  3.04s |  0.81s |    3.7× |
| Batting, IPL 2024 narrow range |   33ms |   29ms |       — |

Narrow filters were already fast — `EXPLAIN QUERY PLAN` shows SQLite
correctly starts from the small match set (~74 matches) and walks
outward. The slow case was the no-filter query where the planner
started from `delivery` and did 2.95M × 2 PK probes into innings/match.

## Fix 1 — conditional JOIN elimination

`FilterParams.build(has_innings_join=True)` always injects
`i.super_over = 0`, which forces innings + match joins even when no
match-level filter is active. For the leaderboards we switched to
`filters.build(has_innings_join=False)` and branch on whether the
returned clause is non-empty:

```python
match_where, params = filters.build(has_innings_join=False)
has_filters = bool(match_where)
if has_filters:
    # full join path — filters require match
    sql = "... FROM delivery d JOIN innings i ... JOIN match m ... WHERE ..."
else:
    # no filters — skip joins entirely
    sql = "... FROM delivery d WHERE d.batter_id IS NOT NULL ..."
```

**Trade-off:** super-over deliveries leak into the no-filter
leaderboard. In practice that's 1066 deliveries out of 2.95M (0.04%) —
imperceptible given the min-balls thresholds filter out small samples
anyway.

## Fix 2 — composite covering indexes

The grouping aggregate needs `batter_id` (for the group), `runs_batter`
(for SUM), and `extras_wides` + `extras_noballs` (for the legal-balls
predicate). The existing single-column `ix_delivery_batter_id` covers
only the grouping column; every row still required a heap lookup for
the other three columns.

Added two composite covering indexes:

```sql
CREATE INDEX IF NOT EXISTS ix_delivery_batter_agg
  ON delivery(batter_id, extras_wides, extras_noballs, runs_batter);
CREATE INDEX IF NOT EXISTS ix_delivery_bowler_agg
  ON delivery(bowler_id, extras_wides, extras_noballs, runs_total);
```

These turn the aggregate into an index-only scan: SQLite never touches
the `delivery` heap. Same write cost as any new index, fine for a
read-heavy analytics workload.

Both indexes are created idempotently in `import_data.py` (full
rebuild) and re-asserted in `update_recent.py` (incremental), so they
survive any rebuild.

## Fix 3 — ANALYZE

The bowling wicket query was picking a bad join order — scanning
2.95M deliveries then probing wickets row-by-row. `sqlite_stat1` was
stale so the planner didn't know that `wicket` is ~160K rows vs.
`delivery` at 2.95M. After `ANALYZE`, the planner correctly starts
from the smaller side.

Added `await db.q("ANALYZE")` to both `import_data.py` and
`update_recent.py` so planner stats stay fresh after every data load.

## Secondary: deferred name lookup

Minor but worth noting. The original leaders code fetched
`person.name` for every batter that cleared the `min_balls` HAVING
clause (thousands). Rewrote to sort + limit to top 10 first, then
look up names only for the ~20 survivors (possibly overlapping across
the two leaderboards). Avoids a thousand-parameter `IN` clause.

## When to apply this pattern again

Any endpoint that (a) aggregates across the full `delivery` table and
(b) may run without match-level filters should use the same shape:

1. `filters.build(has_innings_join=False)` to get a pure match clause.
2. Branch on `bool(where)` — skip the join-chain when no filters.
3. If SUM/COUNT is over a predicate, add a composite index with the
   predicate columns after the grouping key.
4. Defer expensive lookups (names, derived fields) to post-sort, when
   the candidate set is small.

If the aggregate becomes the bottleneck even with indexes (i.e. the
scan itself is slow), the next lever is a materialized summary table
(e.g. `batter_career_totals`) refreshed on DB update. We haven't needed
this yet; sub-second is acceptable for a landing page.

## When NOT to apply

For endpoints where match-level filters are always non-empty (e.g.
per-player pages, which always have `person_id`), the join elimination
gives nothing — the full-join path is already fast.
