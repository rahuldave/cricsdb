# Test catalog

Top-level index of every test in the repo, grouped by layer. Each
entry has: what it tests, how to invoke, when to run.

For deeper docs:
- `tests/regression/README.md` — md5-diff harness mechanics.
- `tests/integration/README.md` — agent-browser conventions.
- `tests/sanity/README.md` — populate-script sanity pattern.

## Three layers, three jobs

| Layer | Source | Tests against | When to run |
|---|---|---|---|
| **Sanity** | `tests/sanity/*.py` | DB tables directly (no HTTP) | After any `scripts/populate_*.py` change OR schema change |
| **Regression** | `tests/regression/<feature>/urls.txt` | Live API responses, HEAD vs patched md5-diff | Before shipping any backend refactor with high blast radius (FilterParams, shared helpers, SQL generators) |
| **Integration** | `tests/integration/*.sh` | Running app via agent-browser | After any frontend change OR backend change that affects an exposed page |

A backend-only change typically runs **sanity → regression**. A
frontend change typically runs **integration**. A populate refactor
that lands new schema + endpoint dispatch runs **all three**.

The TL;DR loop for backend perf work:

```bash
# 1. Sanity — populate produces correct numbers
uv run python tests/sanity/test_bucket_baseline.py
uv run python tests/sanity/test_dispatch_equivalence.py

# 2. Regression — endpoints stay byte-identical (or differ where intended)
bash tests/regression/run.sh teams
bash tests/regression/run.sh scope-averages

# 3. Integration — UI still works end-to-end
BASE=http://localhost:5174 bash tests/integration/team-compare-average.sh
```

## Sanity scripts (`tests/sanity/`)

Standalone Python — read the DB directly, no HTTP, no UI. Each
exits 0 on all-pass and 1 on any failure. All accept `--db` to
target an alternate DB (used to validate the prod-snapshot copy).

### `test_player_scope_stats.py`

What: pool-conservation + incremental round-trip + cross-scope
isolation for the `playerscopestats` denormalized table (built by
`scripts/populate_player_scope_stats.py`). Catches double-counting,
missed-wicket bugs, and drift between full + incremental populate
paths. See `internal_docs/spec-team-compare-average.md` for the
table's role.

When to run:
- After editing `scripts/populate_player_scope_stats.py`.
- Against a `/tmp` prod-snapshot copy when validating an
  incremental update before deploy.

```bash
uv run python tests/sanity/test_player_scope_stats.py
uv run python tests/sanity/test_player_scope_stats.py --db /tmp/cricket-prod-test.db
```

### `test_bucket_baseline.py`

What: the same pattern for `bucketbaseline_*` tables (built by
`scripts/populate_bucket_baseline.py` — see
`internal_docs/perf-bucket-baselines.md`). Five check groups:

1. **Pool conservation** — whole-DB SUM-over-cells from baseline
   league rows equals the live aggregator's whole-DB output for
   batting runs / legal balls / bowler-credited wickets / fielding
   catches / partnerships count. Catches schema-side miscounts.
2. **Per-team correctness** — for 3 sampled cells (RCB IPL'24,
   MI IPL'23, Aus T20WC'24), every batting counter byte-identical
   to live aggregator for the same scope.
3. **Identity columns** — `highest_inn_runs` + match identity,
   `fifties` / `hundreds` per cell match live computation.
4. **League-cell correctness** — matches + bowling wickets at the
   league row match live SQL.
5. **Incremental round-trip** — running `populate_incremental` on
   the match_ids of a small cell DELETEs + reINSERTs byte-identical
   rows.
6. **Cross-cell isolation** — `populate_incremental` on cell A
   leaves cell B untouched.

When to run:
- After any `scripts/populate_bucket_baseline.py` change.
- After any schema change to `BucketBaseline*` models.
- Against a `/tmp` prod-snapshot copy before deploying populate
  changes.

```bash
uv run python tests/sanity/test_bucket_baseline.py
uv run python tests/sanity/test_bucket_baseline.py --db /tmp/cricket-prod-test.db
```

### `test_dispatch_equivalence.py`

What: bulk endpoint dispatch equivalence — for every endpoint
covered by the `bucket_baseline_*` dispatch, calls
`_xxx_from_baseline` AND `_xxx_live` in-process with the same
FilterParams + AuxParams and diffs the returned dicts.

22 endpoints × 11 representative scopes = 212 pair-comparisons.
Scopes deliberately include sparse / unbounded ones (women's
international all-time, men's club all-time, BBL with `2024/25`
season strings, women's WBBL) that the URL inventory doesn't
exercise.

Diff is float-tolerant to 0.05 to absorb SQLite ROUND vs Python
round() rounding noise. Structural type / missing-key diffs are
exact.

This is the test that caught the pre-existing 4-kind vs 5-kind
bowler-wickets exclusion inconsistency that the URL inventory had
missed (IPL 2024 happens to have 0 retired-not-out wickets).

When to run:
- After any change to the dispatch helpers (`bucket_baseline_dispatch.py`).
- After any `_xxx_from_baseline` or `_xxx_live` implementation
  edit.
- Against a `/tmp` prod-snapshot copy to confirm both DBs agree.

```bash
uv run python tests/sanity/test_dispatch_equivalence.py
uv run python tests/sanity/test_dispatch_equivalence.py --db /tmp/cricket-prod-test.db
```

Expected output ends with `212 pairs equivalent, 0 failures` →
`ALL PASS`.

## Regression suites (`tests/regression/`)

URL-level md5-diff: stash uncommitted code, capture HEAD's response
for every URL, pop stash, capture patched response, diff. `REG`-
tagged URLs MUST match (drift is a regression); `NEW`-tagged URLs
SHOULD differ (byte-identical is suspicious — maybe the fix is
inert).

The runner discipline + the REG → NEW flip workflow are documented
in `internal_docs/regression-testing-api.md` and the in-tree
`tests/regression/README.md`.

### Running

```bash
bash tests/regression/run.sh <feature>
```

Where `<feature>` is one of the subdirectory names. Run with no
arg to list available suites.

### Suites

URL counts below are REG-only (the `REG matched` number from the
runner's output). Some suites also have `NEW` entries from past
shape-changing refactors that haven't been flipped back to REG.

| Suite | REG URLs | What it covers |
|---|---:|---|
| `teams`           | 38 | Teams landing + per-team summary / by-season / vs-opponent / opponents-matrix / batting / bowling / fielding / partnerships endpoints. |
| `batting`         | 22 | Player-batting endpoints (leaders, summary, vs-opponent, vs-bowler, by-season, innings-list). |
| `bowling`         | 20 | Player-bowling endpoints (leaders, summary, vs-batter, by-phase, innings-list). |
| `fielding`        | 19 | Player-fielding leaders + per-fielder + Keeper tab endpoints. |
| `head_to_head`    | 20 | Player batter-vs-bowler + team H2H (mode=team) + series_type toggling. |
| `matches`         | 10 | `/matches` list + scorecard endpoints + highlight params. |
| `players`         | 25 | The 4-way summary composer (`/players/{id}/summary` etc.) + playersearch. |
| `series`          | 15 | Series landing + dossier (summary, by-season, records, leaders, partnerships). 13 NEW from past refactors. |
| `venues`          | 31 | Phase-2 `filter_venue` fan-out — every page with FilterBar venue typeahead. 5 NEW from past refactors. |
| `filterbar_refs`  | 14 | The `/api/v1/tournaments` and `/api/v1/seasons` reference endpoints that drive FilterBar dropdowns. 7 NEW from past refactors. |
| `scope-averages`  | 50 | All 12 `/scope/averages/*` endpoints + per-team siblings refactored alongside. **Includes 14 live-fallback URLs** with `filter_venue` / `series_type` / rivalry filters that force `is_precomputed_scope=False` so the live path is exercised too. |

Every URL in `urls.txt` has a label (filesystem-safe) used as the
artefact filename. Drifted URLs print as `✗ <label>`; full JSON
artefacts land in `/tmp/regression-test-<feature>/{head,patched}/`
for `diff` inspection.

### When to run which

- Edit a shared helper like `FilterParams.build()` or
  `_team_innings_clause`: run **every** suite — the helper touches
  most endpoints transitively.
- Edit one endpoint: the suite owning that endpoint, plus
  `scope-averages` if the endpoint has a `/scope/averages/*` sibling.
- Edit `populate_bucket_baseline.py` or the dispatch helpers: at
  minimum `teams` + `scope-averages`. Sanity tests catch the rest.

A backend refactor with high blast radius can run all 11 suites
in ~5 minutes (each is parallel-curl friendly).

## Integration tests (`tests/integration/`)

End-to-end via [`agent-browser`](https://www.npmjs.com/package/agent-browser)
— drives the real Vite dev server (`http://localhost:5174` by
default) against the real FastAPI backend against the real
SQLite DB. Asserts at the URL + DOM level (snapshot text contains,
URL bar matches, etc.).

### Running

```bash
# Default — uses BASE=http://localhost:5173 if unset
BASE=http://localhost:5174 bash tests/integration/<script>.sh
```

Both Vite (5174) and uvicorn (8000) need to be running. See `CLAUDE.md`
"Running Locally" for setup.

### Per-tab scripts

| Script | What it covers |
|---|---|
| `teams.sh` | Teams landing → tabs (By Season / vs Opponent / Compare / Match List) → Compare grid; FilterBar auto-narrow on team selection; row-link to scorecard. |
| `team-compare-average.sh` | Compare tab average-team column: avg appears via auto-fill; phase bands (PP/Mid/Death) + partnership-by-wicket sub-rows render in every column; season-trajectory strip toggles per season span; ✕ removes correctly. (16 asserts.) |
| `batting.sh` | Batting leaders → player page → tabs (Innings List / vs Bowler / By Season); date-link to scorecard with `highlight_batter` param tints + scrolls. |
| `bowling.sh` | Bowling leaders + player page + Wickets + vs Batters tabs + innings-list highlight. |
| `fielding.sh` | Fielders leaders + per-fielder + Keeper tab (conditional on innings_kept > 0) + filter_team auto-narrow. |
| `series.sh` | Series landing → dossier (by-season / records / leaders / partnerships); series_type Show pill reset; legacy `/tournaments?…` redirect. |
| `head_to_head.sh` | mode=player (default) batter-vs-bowler + mode=team team-vs-team; series_type toggle; common-matchups tile suggestions. |
| `matches.sh` | `/matches` list + FilterBar push history; scorecard render; `highlight_batter` / `highlight_bowler` / `highlight_fielder` params tint + scroll. |
| `players.sh` | Players landing + tile click → single-player view + 2/3-way comparison + nav-group dropdown active class. |
| `players_hygiene.sh` | Companion to `players.sh` — mount/unmount under rapid nav (no React warnings, no uncaught page errors). |
| `venues.sh` | Venues landing tile-grid + per-venue dossier + `filter_venue` ambient propagation. |

### Cross-cutting scripts

| Script | What it covers |
|---|---|
| `cross_cutting_url_state.sh` | URL-as-default contract: `useUrlParam` push-vs-replace discipline, ScopeIndicator + PlayerLink reflect URL across tabs. |
| `cross_cutting_mount_unmount.sh` | React hygiene under rapid navigation, fast filter changes, in-flight searches. NEGATIVE assertions (no console errors, no stale-data warnings). |
| `cross_cutting_aux_filters.sh` | series_type aux filter propagation: useFilters reads it from URL, every API consumer passes it through, status strip surfaces it. End-to-end with explicit series_type=bilateral / icc / club assertions. |

### When to run which

- Frontend change to a single tab → that tab's script.
- Change to `useFilters` / `useUrlParam` / `FilterBar` →
  `cross_cutting_url_state.sh` + `cross_cutting_aux_filters.sh`.
- New populate / endpoint that backs a Compare-tab feature →
  `team-compare-average.sh`.
- Anything touching React mount lifecycle → `cross_cutting_mount_unmount.sh`.

The full integration sweep takes ~10 minutes (each script has 5-15
agent-browser navigations). Don't run all of them after every
change — pick what you touched.

## Frontend type-check + build

Not in `tests/` but part of the loop:

```bash
cd frontend && npx tsc -b              # type-check (USE THIS, not --noEmit)
cd frontend && npm run build           # full prod build (also typechecks)
```

`tsc --noEmit` does NOT work in this repo — root `tsconfig.json`
has `files: []` so it checks nothing. Use `tsc -b` (build mode)
which references the actual project configs.

Run after any `frontend/src/` edit. Type-check is fast (~1s);
build is ~700ms.

## Pre-deploy quick check

The minimum sanity before `bash deploy.sh`:

```bash
# Backend
bash tests/regression/run.sh teams
bash tests/regression/run.sh scope-averages
uv run python tests/sanity/test_bucket_baseline.py
uv run python tests/sanity/test_dispatch_equivalence.py

# Frontend
cd frontend && npx tsc -b
BASE=http://localhost:5174 bash tests/integration/team-compare-average.sh
```

If all green: ship. If anything red: diagnose before deploying.

The full audit (every regression suite + every sanity + every
integration) takes ~20 minutes. Worth it before a populate-pipeline
or schema change; overkill before a bug fix to a single endpoint.
