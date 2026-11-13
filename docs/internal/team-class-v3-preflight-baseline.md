# v3 Pre-flight Phase A — Green Baseline (2026-04-28)

Captured before commits 1-5 of `spec-filterbar-team-class-v3.md` start.
This document is the v3 reference state — anything failing in this
file is pre-existing baseline noise, NOT a v3 regression.

## Spec drift check

`git log --oneline --since="2026-04-28" -- api/filters.py
api/routers/teams.py api/routers/tournaments.py api/routers/reference.py
api/routers/bucket_baseline_dispatch.py
frontend/src/hooks/useCompareSlots.ts
frontend/src/components/FilterBar.tsx
frontend/src/components/ScopeStatusStrip.tsx
frontend/src/hooks/useFilters.ts frontend/src/components/scopeLinks.ts`
→ **zero commits**. v3's load-bearing files are byte-identical to
the state in which the spec was written.

## Code-assumption verification

| Spec assumption | Verified at | Status |
|---|---|---|
| `useCompareSlots:50` hard-codes `team_class: undefined` | `frontend/src/hooks/useCompareSlots.ts:50` | ✓ confirmed |
| `OVERRIDABLE_SLOT_KEYS` includes `'team_class'` | `frontend/src/hooks/useCompareSlots.ts:9-12` | ✓ confirmed |
| `tournaments.py::_build_filter_clauses` hand-rolls (no `filters.build()` call) | `api/routers/tournaments.py:52-91` | ✓ confirmed |
| `reference.py::_reference_clauses` hand-rolls | `api/routers/reference.py:19-74` | ✓ confirmed |
| `reference.py::list_teams` hand-rolls where_parts | `api/routers/reference.py:215-262` | ✓ confirmed |
| `aux.team_class` read in `filters.py:216` and `bucket_baseline_dispatch.py:42`; written in `teams.py:977` | grep | ✓ confirmed |

## Sanity tests (Python, DB-direct)

All run via `uv run python tests/sanity/<file>`. None require a server.

| Test | Result | Coverage |
|---|---|---|
| `test_chip_direction_invariant.py` | **13/13 PASS** | 13 (scope, team) pairs across IPL, T20WC, Aus/Ind intl, BBL, WPL |
| `test_avg_baseline_pools.py` | **5/5 PASS** | men_intl 2018 (unbounded / FM-only / scope_to_team=Aus), IPL 2018 (unbounded / scope_to_team=RCB) |
| `test_avg_baseline_numbers.py` | **ALL PASS** | Axis A (endpoint vs DB) + Axis B (chip vs avg col), incl. team_class FM mode + chip_team_class hint |
| `test_bucket_baseline.py` | **ALL PASS** | Bucket population correctness, cross-cell isolation |
| `test_dispatch_equivalence.py` | **212 pairs equivalent, 0 failures** | Live aggregation vs precomputed bucket dispatch |
| `test_player_scope_stats.py` | **ALL PASS** | Player-scope-stats correctness, cross-scope isolation |

**Summary: 6/6 sanity tests green.**

## Regression suites (HEAD vs HEAD diff — 0 drift expected)

All run via `bash tests/regression/run.sh <feature>`. Server: localhost:8000.

| Suite | REG matched | REG drifted | NEW unchanged (stale) |
|---|---|---|---|
| teams | 38 | 0 | 0 |
| scope-averages | 50 | 0 | 0 |
| batting | 22 | 0 | 0 |
| bowling | 20 | 0 | 0 |
| fielding | 19 | 0 | 0 |
| players | 25 | 0 | 0 |
| head_to_head | 20 | 0 | 0 |
| matches | 10 | 0 | 0 |
| venues | (count not captured — was redirected) | 0 | 5 |
| filterbar_refs | 14 | 0 | 7 |
| series | 15 | 0 | 13 |
| **TOTAL** | **~233** | **0** | **25** |

**Summary: 0 REG drift across all 11 suites.**

The 25 stale `NEW unchanged` entries (venues, filterbar_refs, series)
are pre-existing — URLs that were tagged NEW for past feature work
and never flipped to REG once they stabilised. They're not v3-related.
Worth a separate cleanup pass post-v3 ship.

## Integration scripts (agent-browser, DOM-grounded)

All run via `bash tests/integration/<file>`. Servers: localhost:8000 + localhost:5173.

| Script | Pass / Fail | Notes |
|---|---|---|
| `compare_avg_chips.sh` | **3 anchors PASS** | Proves Mode B + chip alignment baseline. Anchor A' exercises per-slot FM avg with chip_team_class hint. Critical v3 guardian. |
| `compare_filters.sh` | **18 PASS / 0 FAIL** | All 5 anchors incl. URL-B-style FM avg. |
| `cross_cutting_aux_filters.sh` | **3 PASS / 0 FAIL** | Proves series_type aux works (no interaction with team_class). |
| `cross_cutting_url_state.sh` | **12 PASS / 1 FAIL** | Pre-existing test rot — fails on "PlayerLink letter link" (the retired (e,t,s,b) tier model from 2026-04-20). NOT v3-related. |
| `teams.sh` | **13 PASS / 0 FAIL** | Teams page coverage. |
| `series.sh` | **18 PASS / 1 FAIL** | Pre-existing test rot — fails on "Records tab label" (UI label drift). NOT v3-related. |
| `team-compare-average.sh` | **30 PASS / 2 FAIL** | Pre-existing test rot — fails on "scope-computed avg label" / "tournament + season label" (UI label drift). NOT v3-related. |

**Summary: critical v3-relevant scripts all green. 4 pre-existing
failures that should be fixed but don't block v3.**

The pre-existing failures are documented here so v3 commits can
distinguish "this fail is mine" from "this fail was already there":

1. `cross_cutting_url_state.sh` Test 2 — "PlayerLink letter link"
   referencing the retired pre-2026-04-20 tier letter model.
2. `series.sh` — "Records tab label" missing.
3. `team-compare-average.sh` — "scope-computed avg label" missing.
4. `team-compare-average.sh` — "label shows tournament + season"
   missing.

## Server state

- uvicorn running on :8000 (--reload presumed)
- frontend dev running on :5173

These should remain up across Phase B / C / D / E. Shut down at end
of Phase E or carry into the next session.

## Decision: Phase A is complete; proceed to Phase B + C in parallel

All v3 spec assumptions confirmed. No drift. Critical regression and
integration paths green. Ready to derive ground truth (Phase B, DB-only
subagent) and capture the per-tab BEFORE snapshot (Phase C, agent-
browser). These can run concurrently.
