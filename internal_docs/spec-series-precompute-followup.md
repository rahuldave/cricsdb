# Spec: /series precompute follow-up (Phases B → A → C → D → E)

**Status: B + A SHIPPED 2026-05-14. C / D / E remaining.**

| Phase | Status | Commits |
|---|---|---|
| B (ht_q via bucketbaselinebatting) | SHIPPED | `d152ec2` |
| A pt 1 (ts_q + tw_q via playerscopestats) | SHIPPED | `f11b323` |
| A pt 2-3 (batters + bowlers leaders) | SHIPPED | `228e5ba` |
| A pt 4 (fielders leaders) | SHIPPED | `c10c869` |
| C (partnerships top per (cell, wicket)) | PENDING — next session | — |
| D (per-team inning splits) | PENDING — next session | — |
| E (distribution lifetime) | PERMANENTLY DEFERRED 2026-05-14 | — |

End-to-end /series at all-cricket — all four key endpoints under 0.4s
each (was 3-6s):
- `/series/summary`: 6.4s → 0.33s
- `/series/batters-leaders`: 5.2s → 0.31s
- `/series/bowlers-leaders`: 3.6s → 0.27s
- `/series/fielders-leaders`: 3.2s → 0.34s

Builds on the bucketbaselinemoments work shipped earlier
(`0eb5ec9`). That commit dropped `/series/summary` at all-cricket
from 6.4s → 4.6s by precomputing `highest_individual`,
`best_bowling`, `best_fielding` per cell. This spec covers the
remaining slow paths identified by HAR-measured page loads in the
same session.

## Measured baselines (post-moments, 2026-05-14)

HAR-captured page-load wall-clocks (prod build, all-cricket scope):

| Page | Wall-clock | Dominant API call |
|---|---|---|
| /series Overview (no filter) | 4.76s | /series/summary 4.76s + /series/landing 1.97s |
| /series Batting | **5.25s** | /series/batters-leaders 5.25s + /series/summary 5.17s |
| /series Bowling | 5.00s | /series/summary 5.00s + /series/bowlers-leaders 3.58s |
| /series Partnerships | 4.95s | /series/summary 4.95s + /partnerships/top-by-wicket 1.53s |
| /series IPL 2023 (any tab) | 30-50ms | Precompute already pays off |
| /teams MI Batting | 865ms | /teams/{t}/batting/by-inning 865ms |
| /teams India Bowling | **1.46s** | /teams/{t}/bowling/by-inning 1.46s |

Per-query timing inside `/series/summary`'s gather (raw sqlite3 CLI):

| Query | Status | Time |
|---|---|---|
| meta_q / bat_q / wkt_q / top_teams_q | precomputed | <100ms each |
| hi_q / bb_q / bf_q | precomputed (just shipped) | <100ms each |
| **ts_q (top scorer)** | LIVE | **2.78s** ← new bottleneck |
| tw_q (top wicket-taker) | LIVE | 0.28s |
| ht_q (highest team total) | LIVE | 0.35s |
| lp_q / finals_q | LIVE (small) | <100ms |

## Goal

Drop `/series` Overview / Batting / Bowling / Partnerships at
all-cricket to **<1s** page-load. Drop `/teams/{team}` Batting and
Bowling at international scope to **<300ms**.

## Phase order (shippable independently, in this order)

```
B → A → C → D → E
```

Each phase = one or more commits. Each commit measures before/after
isolation (CLAUDE.md "perf changes — measure after every single
change"). Each commit ships sanity + integration tests written
red-then-green for any new bug surface.

---

## Phase B — Wire highest_team_total from existing bucketbaselinebatting

**The free win.** No schema change, no population work — the data
already exists.

### Why

`bucketbaselinebatting` already stores:
- `highest_inn_runs` — MAX over per-innings totals in cell
- `highest_inn_match_id` — identity of the cell's highest innings
- `highest_inn_team` — team that scored it
- `highest_inn_innings_number` — which innings

But `/series/summary` still runs ht_q live (~0.35s at all-cricket).

### Schema changes
None.

### Population changes
None — `_populate_batting` already writes these columns.

### Endpoint integration

In `api/routers/tournaments.py`, inside the `is_baseline` branch
(where moments is now wired), replace `ht_q`:

```python
ht_q = db.q(
    f"""SELECT highest_inn_team AS team,
               MAX(highest_inn_runs) AS total,
               highest_inn_match_id AS match_id,
               highest_inn_innings_number AS innings_number,
               (SELECT MIN(date) FROM matchdate WHERE match_id = highest_inn_match_id) AS date
        FROM bucketbaselinebatting
        {bl_where} AND team != '{LEAGUE_TEAM_KEY}'
        ORDER BY highest_inn_runs DESC, highest_inn_match_id ASC
        LIMIT 1""",
    bl_params,
)
```

The result row needs a per-row `opponent`. Approach: post-process —
look up match.team1 / team2 from match table for the winning row
(single-row scalar lookup, fast). OR include via a sub-select in
the same query.

### Tests

**Sanity (new):** Extend `tests/sanity/test_bucket_baseline.py`
with a `check_highest_team_total` function — for 5 scopes
(all-cricket, men's club, women's intl, IPL 2023, men's
international 2024), assert that the bucket-derived
highest_team_total tuple (team, runs, match_id, innings_number)
matches the live SQL output byte-for-byte.

**Regression:** `tests/regression/series/urls.txt` already covers
/series/summary at multiple scopes. After wiring:
1. Run the harness, verify it reports `0 NEW changed, N REG drifted`
   IF the response shape changes (no expected change — just a faster
   path to the same result).
2. If output is byte-identical (expected), no REG→NEW flip needed.

**Integration (new):** `tests/integration/series_highest_team_total.sh`:
```bash
expected=$(sql "SELECT i.team, SUM(d.runs_total) FROM ... ORDER BY ... LIMIT 1")
dom=$(ab_eval "...highest team total tile innerText...")
assert_eq "highest team total" "$expected" "$dom"
```
Cover all-cricket + IPL 2024 scopes.

### Expected speedup
~0.35s off /series/summary at all-cricket. Won't move the
wall-clock much (ts_q at 2.78s still dominates) until Phase A.

### Acceptance criteria
- ht_q individual query time <50ms at all-cricket via raw sqlite3
- Sanity test passes at 5 scopes
- Integration test passes
- `/series/summary` HTTP response byte-identical to pre-change for
  ALL urls in `tests/regression/series/urls.txt`

---

## Phase A — Leaderboards via existing playerscopestats

**The big win.** ~3.6-5.2s off /series Batting/Bowling subtabs at
all-cricket.

### Critical insight: the table already exists

`playerscopestats` (67,033 rows on local DB) holds
per-(person_id, scope_key) aggregates. `scope_key` is
`blake2b(tournament || season || gender || team_type, 6)`. The
table also stores the raw scope columns
(`tournament`, `season`, `gender`, `team_type`), so the same WHERE-
clause shape as bucketbaseline_* works.

Columns present:
- Batting: matches, innings_batted, runs, legal_balls, dots,
  fours, sixes, dismissals, avg_batting_position
- Bowling: balls_bowled, runs_conceded, wickets, bowling_dots,
  boundaries_conceded, powerplay/middle/death_overs
- Fielding: catches, runouts, stumpings, catches_as_keeper,
  matches_as_keeper

Population script: `scripts/populate_player_scope_stats.py`
(populate_full + populate_incremental already in place, called
from `update_recent.py`).

**No API router currently reads from this table.** Phase A is
purely wiring.

### Endpoints to migrate

In `api/routers/tournaments.py`:
1. `/series/summary` → `ts_q` (top scorer) — `SELECT person_id, SUM(runs) FROM playerscopestats WHERE {scope} GROUP BY person_id ORDER BY SUM(runs) DESC LIMIT 1`
2. `/series/summary` → `tw_q` (top wicket-taker) — same shape, `SUM(wickets)`
3. `/series/batters-leaders` — `SELECT person_id, SUM(runs), SUM(legal_balls), SUM(fours), ..., SUM(dismissals) FROM playerscopestats WHERE {scope} GROUP BY person_id HAVING SUM(matches) >= 1 ORDER BY SUM(runs) DESC LIMIT 20`
4. `/series/bowlers-leaders` — same shape for wickets, runs_conceded, balls_bowled
5. `/series/fielders-leaders` — same shape for catches, stumpings, run_outs

Gated by `is_precomputed_scope(filters, aux)` — fall back to live
SQL for rivalry / venue / aux.inning / series_type ≠ 'all'.

### Schema changes
None.

### Population changes
None — verify `populate_player_scope_stats.py` runs in the
incremental hook (it does, per `update_recent.py:340-343`).

### Tournament canonicalization

`bucket_baseline_dispatch.baseline_where()` already handles
`is_canonical_with_variants` to expand canonical names (e.g. "IPL"
→ all variant event_names). It writes `tournament IN (...)` against
the bucket table. The same helper works against `playerscopestats`
since the schema is identical for the scope columns. **No new code
in baseline_where.**

### Output-shape question

`/series/batters-leaders` currently returns:
- `person_id`, `name`, `team`, `runs`, `balls_faced`, `strike_rate`,
  `batting_average`, `dismissals`, `fours`, `sixes`, plus rank-style
  fields.

`playerscopestats` has runs / legal_balls / dismissals / fours /
sixes. NAME and TEAM are NOT in playerscopestats — need a JOIN to
`person` for name and a JOIN to `matchplayer` (or similar) for team.

**Resolution:** JOIN to person at query time (LIMIT 20 + indexed
lookup = trivial). For team, the leaderboard endpoint shows the
player's "primary team in scope" — defined as the team they
appeared for most often in the scope. Either:

(a) Precompute primary_team_in_scope into playerscopestats (one new
column). Requires schema migration + repopulate.

(b) Derive at query time: for each of top 20, run a sub-query
finding their most-frequent team in scope. 20 sub-queries × <10ms
each = <200ms. Acceptable.

Recommend (a) — cleaner long-term, repopulate is incremental-safe.
Cost: one VARCHAR column per row × 67K rows ≈ 1 MB.

### Tests

**Pre-flight (one-shot, not committed):** Run live SQL vs
playerscopestats-derived top-20 at 5 scopes. Must be byte-identical
(modulo column order). If divergent, the population script has a
bug that needs fixing FIRST.

**Sanity (new):** Extend `tests/sanity/test_bucket_baseline.py`
with `check_leaders_roundtrip` — for 5 scopes, assert
playerscopestats SUM-across-cells matches live SQL leaderboard
output for batters / bowlers / fielders.

**Regression — REG→NEW flip required:** The response order MAY
change at ties (tie-breaker columns differ). Workflow per
`docs-sync.md`:
1. Audit `tests/regression/series/urls.txt` lines covering
   batters-leaders / bowlers-leaders / fielders-leaders. Flip them
   from REG to NEW in a **separate, earlier commit**.
2. Ship the wiring change.
3. Run `./tests/regression/run.sh series` — expect `0 REG drifted,
   N NEW changed`.

**Integration (new):** `tests/integration/series_leaders_*.sh` for
each discipline. SQL-anchored DOM assertion that the top row in the
leaderboard matches the SUM-from-playerscopestats top row at
multiple scopes (no scope, men's club, IPL all-time, IPL 2023).

Reference pattern: `tests/integration/team_class_club_per_page_refetch.sh`.

### Expected speedup
- /series/batters-leaders at all-cricket: **5.2s → ~50ms** (~100×)
- /series/bowlers-leaders at all-cricket: **3.6s → ~50ms**
- /series/fielders-leaders: similar
- /series/summary ts_q + tw_q: **2.8s + 0.3s → ~50ms total**

Page-load impact: /series Batting / Bowling / Overview at
all-cricket drop from ~5s to **<2s** (bounded by
/series/landing at ~1.9s — separate concern, see Phase deferred
section below).

### Acceptance criteria
- ts_q / tw_q individual query time <50ms at all-cricket via raw
  sqlite3
- Leaderboard endpoints return byte-identical top-20 (modulo
  documented tie-break ordering changes) for 5 scopes
- Sanity test passes at 5 scopes
- Integration tests pass
- Regression run: 0 REG drifted, N NEW changed

---

## Phase C — Top partnerships per (cell, wicket)

**Mid-impact.** ~1.5s off /series Partnerships at all-cricket.

### Current state

`bucketbaselinepartnership` stores per-(cell, team, wicket_number):
- aggregates: n, total_runs, total_balls
- identity: best_pair_partnership_id (single best)
- 50+/100+ counts

`/series/partnerships/top-by-wicket` returns top N per wicket (currently
`per_wicket=10`). Live SQL runs a window-function over the partnership
table — 1.5s at all-cricket.

### Schema changes

**Option C1 (simple):** Add `top_3_partnership_ids JSON` to
`bucketbaselinepartnership` — top-3 partnership IDs per (cell, team,
wicket_number). At query time, scope SUM-merge: collect all top-3 IDs
across matching cells, JOIN to partnership for full details, sort,
return top N.

**Option C2 (correct for top-10):** New table
`bucketbaselinepartnershiptop` keyed by (gender, team_type, tournament,
season, team, wicket_number, rank) with rank 1..10. Allows top-10
correctness without merging.

Recommend **C2** — `per_wicket=10` is the actual frontend default;
storing top-10 means scope-SUM doesn't need to re-rank within cell
(only across cells).

Row count estimate: ~5K cells × 2 teams × 10 wickets × 10 ranks =
1M rows. Small.

### Population

New `_populate_partnership_top(db, cells=None)` function in
`populate_bucket_baseline.py`. Window-function ROW_NUMBER over
partnership table partitioned by (cell, team, wicket_number),
ordered by partnership_runs DESC.

Wire into `populate_full` after `_populate_partnership`. Wire into
`populate_incremental` cell-filter DELETE + re-INSERT loop.

### Endpoint integration

`/series/partnerships/top-by-wicket` reads new table when in
`is_precomputed_scope` regime. Falls back to live SQL otherwise.

### Tests

**Sanity:** Extend `test_bucket_baseline.py` with
`check_partnership_top_roundtrip` — for 5 scopes, assert
precompute-derived top-10 per wicket matches live SQL.

**Regression:** `tests/regression/series/urls.txt` partnerships
URLs — REG→NEW flip if response ORDER changes.

**Integration:** `tests/integration/series_partnerships_top_by_wicket.sh`
— DOM-assert that top row per wicket matches SQL.

### Expected speedup
- /series/partnerships/top-by-wicket at all-cricket: **1.5s → ~50ms**
- Page-load /series Partnerships at all-cricket: ~4.95s → ~3.5s
  (still bounded by /series/summary 4.95s and /series/landing 1.9s,
  but partnership tile arrives faster)

### Acceptance criteria
- per-wicket top-10 byte-identical to live SQL at 5 scopes
- Sanity + integration tests pass
- Regression: 0 REG drifted

---

## Phase D — Per-team inning splits in bucketbaselinebatting/bowling

**Mid-impact.** ~600ms-1.5s off /teams Batting/Bowling subtabs.

### Current state

`bucketbaselinebatting` stores `first_inn_runs_sum`,
`first_inn_count`, `second_inn_runs_sum`, `second_inn_count` — but
ONLY for runs. The endpoint `/teams/{team}/batting/by-inning`
returns runs, legal_balls, fours, sixes, dots split by 1st/2nd
innings.

The missing columns force the endpoint to run a live aggregation
over `delivery` filtered by `innings.innings_number`.

### Schema changes

Add columns to `bucketbaselinebatting`:
- `first_inn_legal_balls`, `first_inn_fours`, `first_inn_sixes`,
  `first_inn_dots`
- `second_inn_legal_balls`, `second_inn_fours`, `second_inn_sixes`,
  `second_inn_dots`

Same shape for `bucketbaselinebowling`:
- `first_inn_balls`, `first_inn_wickets`, `first_inn_runs_conceded`,
  `first_inn_dots`
- `second_inn_*`

### Population

Extend `_populate_batting` and `_populate_bowling` to compute
inning splits via `CASE WHEN i.innings_number = 0 THEN ... END`
within the existing aggregation. No new tables, no new files.

### Endpoint integration

Rewrite `/teams/{team}/batting/by-inning` and `/bowling/by-inning`
to SELECT directly from the precomputed columns. Falls back to live
SQL for venue/rivalry scopes.

### Tests

**Sanity:** Extend `test_bucket_baseline.py` with
`check_inning_splits_roundtrip` — for 5 scopes, assert
bucket-derived per-team inning splits match live SQL.

**Regression:** Flip relevant URLs in
`tests/regression/teams/urls.txt` if needed.

**Integration:** `tests/integration/teams_batting_by_inning.sh` and
`teams_bowling_by_inning.sh` — DOM-anchored against SQL.

### Expected speedup
- /teams/{team}/batting/by-inning at all-time: **865ms → ~50ms**
- /teams/{team}/bowling/by-inning at all-time: **1.46s → ~50ms**
- Page-load /teams Batting / Bowling tabs: drop ~500ms-1s

### Acceptance criteria
- Sanity + integration tests pass at 5 scopes
- Regression: 0 REG drifted (or NEW after flip)
- Populate full + incremental still pass `test_bucket_baseline.py`
  for all 7 (now 8 with new columns) tables

---

## Phase E — Per-team distribution lifetime totals (PERMANENTLY DEFERRED 2026-05-14)

**Small win.** ~200ms off /teams Distribution panels.

Endpoint `/teams/{team}/{discipline}/distribution` computes
lifetime totals + 4 form windows (last_10, last_60d, last_6mo,
last_1yr) live. Form windows are calendar-anchored and harder to
precompute (the anchor moves daily).

Lifetime totals could be precomputed but the per-team bucket tables
already have lifetime data — just need wiring. Estimated <200ms
win.

**Permanently deferred** — the lifetime-only half doesn't move the
needle (200ms) enough to justify the wiring touch, and the
form-window half is genuinely hard to precompute because the
calendar anchor moves daily. Revisit only if a future spec adds
form-window precompute as part of a broader effort, in which case
the lifetime wiring becomes a natural side-effect.

---

## Phase deferred — /series/landing

At all-cricket, `/series/landing` takes ~1.9s. After Phase A,
/series Overview is bounded by `/series/landing` rather than
`/series/summary`. Separate spec — `landing-pages.md` already
covers this surface.

Out of scope for this spec. Note for future: same precompute logic
applies; landing returns scope-narrowed catalog tiles which could
SUM from bucketbaselinematch.

---

## Cross-cutting requirements (apply to every phase)

### Measurement discipline (CLAUDE.md "perf changes")

Every commit must include before/after timings in the commit
message. One change per commit. Vague claims like "this should be
faster" are not acceptable.

Baseline + delta format (mirror `internal_docs/perf-bucket-baselines.md`):
```
Before (raw sqlite3):
  ts_q all-cricket: 2.78s

After (raw sqlite3):
  ts_q all-cricket: 0.04s (-2.74s / -98%)

Before HTTP /series/summary all-cricket: 4.6s avg (3 runs: 4.61, 4.57, 4.58)
After  HTTP /series/summary all-cricket: 2.1s avg (3 runs: 2.10, 2.08, 2.12)
```

### Sanity test discipline

Every phase extends `tests/sanity/test_bucket_baseline.py` (or
adds a sibling test file) with a roundtrip check: precompute-derived
value equals live SQL byte-identical for 5+ scope samples.

Run on local DB AND on `/tmp/cricket-prod-snapshot.db` (copied from
`~/Downloads/t20-cricket-db_download/data/cricket.db`). Per this
session's discipline — both populate_full and populate_incremental
must work on a DB that may or may not have existing bucket tables.

### Regression discipline (REG→NEW flip)

Every phase that COULD change response shape (e.g. row order on
ties) must flip applicable URLs in
`tests/regression/{series,teams,batting,bowling,fielding}/urls.txt`
from REG → NEW in a **separate, earlier commit**, per
`docs-sync.md` section "Regression-shape changes".

Workflow:
1. Commit REG→NEW flip on affected URLs (no code change).
2. Commit the wiring change.
3. Run `./tests/regression/run.sh <feature>` — expect
   `0 REG drifted, N NEW changed, 0 NEW unchanged`.

### Integration test discipline (CLAUDE.md "integration tests")

Every phase adds `tests/integration/<feature>.sh` that:
- Loads the actual page in `agent-browser` at desktop AND mobile
  (`set viewport 390 844`).
- Asserts DOM cell values via `assert_eq`.
- Pulls expected values from SQL via `sqlite3 $DB "SELECT ..."` —
  **NEVER hardcoded numerics** (CLAUDE.md "SQL-anchored").
- Exercises every call site of the changed endpoint
  (CLAUDE.md "tests must cover EVERY call site of a shared
  abstraction").

For Phase A specifically: integration must cover ALL THREE leader
endpoints (batting, bowling, fielding) AND BOTH usages in
/series/summary (ts_q's top_scorer tile, tw_q's top_wicket_taker
tile).

### Red-then-green discipline (CLAUDE.md)

For each integration test, run it against HEAD BEFORE the change
to confirm it fails (red). Then ship the change. Then run again to
confirm it passes (green). Report both phases in the commit
message.

### Production deploy gate

`bucketbaselinemoments` (this session) and any new bucket tables
shipped via this spec do NOT exist on the production DB. **Every
phase that adds or modifies a bucket table requires
`bash deploy.sh --first`** for the next deploy — uploading the
locally-populated DB.

Add to commit message: `Deploy: requires --first (new schema)` OR
`Deploy: code-only OK (no schema change)`.

### Update memory + handoff at end

After each phase ships, update:
- `internal_docs/spec-series-precompute-followup.md` — mark phase
  SHIPPED with commit shas + measured delta
- `internal_docs/enhancements-roadmap.md` — add ship entry under
  current month
- `internal_docs/perf-bucket-baselines.md` — append "Phase X
  (2026-MM-DD)" summary
- `MEMORY.md` — update project memory pointer

---

## Estimated effort

| Phase | LOC | Commits | Test work | Risk |
|---|---|---|---|---|
| B (ht_q wiring) | ~30 | 1 | small | low (data exists) |
| A (leaders wiring) | ~150 | 5 (one per endpoint + 1 prep) | medium (5 sanity + 4 integration) | medium (response-shape match) |
| C (partnerships top) | ~150 | 3 (schema, populate, endpoint) | medium | low (new table, additive) |
| D (inning splits) | ~250 | 3 (schema, populate, endpoint) | medium (covers /teams pages) | low (additive columns) |
| E (distribution lifetime) | (defer) | — | — | — |

Total: ~600 LOC, ~12 commits, 3-5 hours work.

---

## Handoff to next session

1. **First action:** read this doc top-to-bottom + `MEMORY.md`
   pointer `project-series-precompute-followup`.
2. **Begin with Phase B** — the free win. Verifies the spec's
   measurement + commit discipline before tackling the big phase A.
3. **Critical pre-flight for Phase A** — run live-SQL vs
   playerscopestats top-20 comparison at 5 scopes BEFORE writing
   any wiring code. If they diverge, the population script has a
   bug that must be fixed first.
4. **Production deploy:** the current session's bucketbaselinemoments
   table needs `bash deploy.sh --first` to land on plash. Plan that
   first — without it, /series/summary baseline path will return
   null for hi/bb/bf.
5. **Stop after each phase** — measure, write tests, commit, then
   re-evaluate before starting the next phase.
