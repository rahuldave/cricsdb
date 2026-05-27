# Spec — all-ball batting-runs convention + single per-innings source of truth

**Status:** DRAFT for review (Roughdraft). **Date:** 2026-05-27. **Prereq for:** `internal_docs/spec-player-baseline-aux-fallback.md` Phase 3b (the live cohort fallback is PAUSED until this lands — see that spec §3). **Why it exists:** the cross-check requested while building 3a surfaced a latent batting-runs convention bug + a two-tables-two-conventions divergence that would make 3b's "typical player" comparison jump at the gate boundary.

* * *

## 0. Plain-English summary

A batsman's runs should be **runs off the bat over every delivery** (a four hit off a no-ball is theirs), and balls faced should be **legal balls only** (a no-ball is never a ball faced, even when you score off it). The extras — the wide run, the no-ball penalty — belong to the bowler/team, not the batter. Today the **player batting analytics** (the summary, the by-season / by-phase / by-over tabs, and the batting cohort tables) get this wrong: they filter no-ball deliveries out entirely *before* summing the batter's runs, so a batsman silently loses the runs he scored off no-balls. The **team side and the records table already do it right.** This spec fixes the player side to the correct convention, completes the per-innings batting table with the innings it currently misses, and makes that one table the single source the position-grain cohort is built from — so the live and precomputed comparison paths can never disagree again.

## 1. Evidence (verified 2026-05-27)

Worked example — scope **IPL 2016, men's** (closed, stable):

| metric | comparison table `playerscopestatsposition` | records table `inningsbatterperf` | delta | cause |
| --- | --- | --- | --- | --- |
| legal_balls | 13618 | 13618 | 0 | — (already agree) |
| dots | 4649 | 4649 | 0 | — |
| runs | 17899 | 17962 | **+63** | no-ball off-bat runs dropped by the comparison side |
| fours | 1624 | 1633 | **+9** | no-ball fours dropped |
| sixes | 638 | 639 | **+1** | no-ball sixes dropped |
| innings | 883 | 865 | **−18** | `inningsbatterperf` misses pure non-striker appearances |

Per-player: V Kohli's summary shows **13117** runs; his true off-the-bat total is **13166** — the summary drops the **49 runs he scored off no-balls** (`/batters/ba607b88/summary` == legal-only SQL, ≠ all-ball SQL). The team cohort precompute (`bucketbaselinebatting._populate_batting`) sums `runs_total` over **all** deliveries (no extras filter on the runs sum) and counts only legal balls — i.e. it never drops no-ball runs. So the player side is the outlier.

Reproduce: `tests/sanity/test_inningsbatterperf_position.py` already shows the table-side numbers; the deltas above are direct SQL.

## 2. The correct convention (the target everywhere on the player batting side)

For a batsman, per the cricket rules and consistent with the team side + records:

- **runs** = `SUM(runs_batter)` over **all** the batter's deliveries (includes runs off no-balls; a wide carries `runs_batter = 0` so it adds nothing).
- **fours / sixes** = `runs_batter = 4 / 6` over **all** deliveries (a boundary off a no-ball is the batter's boundary). (Keep the existing `runs_non_boundary = 0` guard on fours.)
- **balls faced** = legal balls only (`extras_wides = 0 AND extras_noballs = 0`). A no-ball is never a ball faced even when scored off.
- **dots** = legal ball with `runs_total = 0` (unchanged — already correct).
- **innings / dismissals** = include the non-striker: an innings where the player was only ever at the non-striker's end still counts (and a run-out there is his wicket). Already true in the summary via `_batting_innings_filter`'s `(batter_id OR non_striker_id)`; must become true in `inningsbatterperf` and the cohort.

Tell for a wrong site: `SUM(runs_batter)` (or a `runs_batter = 4/6` count) sitting under a `WHERE`/CASE that requires `extras_wides = 0 AND extras_noballs = 0`. Legitimate legal-filters (the `balls`/`dots` counts) stay.

## 3. Decisions locked in review (2026-05-27)

| # | Decision |
| --- | --- |
| D1 | **Fix the convention (option A), do not match the existing wrong one.** The player's own number, the cohort, the records, and the team cohort all end up counting a batsman's runs the same (correct) way. |
| D2 | **Single source of truth (option 2).** `inningsbatterperf` becomes THE per-innings batting table (all-ball runs — already correct — plus the missing non-striker innings). `playerscopestatsposition` is re-derived as a rollup of it, so live (3b) and precomputed paths are identical by construction. |
| D3 | **Phase/over batting cohorts can't be single-sourced** (they need ball-level over/phase, absent from a per-innings table). They keep their own delivery scan but get the same convention fix, via a shared rule so they can't drift. |
| D4 | **Records keeps reading `inningsbatterperf`** — its all-ball runs are already correct for official scores; the new non-striker rows (0 runs/0 balls) are harmless-to-correct for it (they're the non-striker ducks records currently misses), subject to the §6.2 audit. |
| D5 | **Schema change as a rebuild, not ALTER** (CLAUDE.md / `feedback_no_alter_drop_create`): back up first, edit model, DROP+CREATE on full populate, fill on incremental, re-baseline. |
| D6 | **The own number and the cohort must move together.** A commit that shifts the summary's runs without the cohort (or vice-versa) leaves the comparison chip transiently apples-to-oranges; sequence/test so each shipped step is self-consistent (§7). |

### Build deltas locked at implementation start (2026-05-27)
- **D3 form:** the "shared rule" is a **shared helper** — `batting_delivery_contrib(d)` returning `(runs, is_four, is_six, legal_ball, dot)` — called by the parent + `batting_over` / `batting_phase` / `batting_phase_position` populates. One definition, can't drift.
- **Populate ordering (augments §6.1):** the position cohort is currently built **before** `inningsbatterperf` in both `import_data.py` (position :528, records :592) and `update_recent.py` (position :349, records :405). The §5 rollup inverts that dependency, so records-aggregates must move **ahead of** the position populate in both chains.
- **Deploy:** **held local until 3b lands** — read queries fix on a code deploy alone, but the cohort tables + `inningsbatterperf` need a prod DB rebuild; one deploy + one rebuild covers both. (D6 sequencing: separate commits within one session; the own↔cohort consistency test is asserted after the read-query fix.)
- **Site enumeration (§7.1 output):** `internal_docs/allball-batting-sites.md`.

## 4. Scope — every surface that drops no-ball batting runs

### 4.1 Read queries (`api/routers/batting.py`)
The shared `_batting_filter` (line ~180) puts `extras_wides = 0 AND extras_noballs = 0` in the WHERE, so every consumer that sums `runs_batter`/boundaries under it drops no-ball runs. The fix pattern per site: widen the delivery set to all of the batter's balls, then gate **balls** (and dots) with `CASE WHEN legal`, leaving **runs/fours/sixes** ungated.

Candidate sites to convert (confirm each during build; separate true runs-drops from legitimate `balls`/`dots` legal-filters):
- `_batting_filter` (≈180) — the shared WHERE; summary core (≈428–443), and every tab that reuses it.
- by-season / by-phase / by-over / vs-bowlers / distribution runs aggregations (≈290–320, 459–462, 659, 763, 839, 914, 1035, 1058, 1320, 1365, 1391–1409, 1495) — audit which sum `runs_batter` under the legal WHERE vs which are `balls`/`dots` counts.

Build step 1 = enumerate these precisely (grep `runs_batter` in `batting.py`, classify each as runs-sum vs ball/dot-count) and convert only the runs-sums.

### 4.2 Batting cohort populates (the `if not legal: continue` before runs)
Each adds runs only on legal balls. Fix: count legal balls + dots as today, but add `runs_batter`/boundaries on **all** the batter's deliveries.
- `scripts/populate_player_scope_stats.py` — parent batting columns (`runs`, `fours`, `sixes`; `legal_balls`/`dots` unchanged).
- `scripts/populate_playerscopestats_position.py` — position-grain (**superseded by the rollup in §5; convention fix only needed if the rollup isn't adopted**).
- `scripts/populate_playerscopestats_batting_over.py` — over-grain (in-place fix; can't be rolled up).
- `scripts/populate_playerscopestats_batting_phase.py` — phase-grain (in-place).
- `scripts/populate_playerscopestats_batting_phase_position.py` — phase×position (in-place).

NOT in scope: `playerscopestatsover` (bowling by over), the fielding/keeping tables, and the team side — none drop batting runs.

### 4.3 The non-striker innings completion (`inningsbatterperf`)
`_populate_innings_batter_perf` groups by `d.batter_id` (striker), so a pure non-striker appearance (no striker delivery) has no row. Add a second insert pass: for each innings, for every `non_striker_id` with no striker row in that innings, insert a row with `runs=0, balls=0, fours=0, sixes=0, dots=0`, `position_bucket` from `derive_positions`, `not_out` from `EXISTS(wicket WHERE player_out_id = that person AND kind NOT IN retired)`. (18 such rows in the IPL-2016 scope; 615 diamond-duck innings DB-wide per `project_player_baselines_spec`.)

## 5. The single-source rollup (D2)
`inningsbatterperf` (completed per §4.3) carries, per (batter, innings): all-ball `runs`, legal `balls`, all-ball `fours`/`sixes`, `dots`, `not_out`, `position_bucket`. Every `playerscopestatsposition` column derives from it by grouping on **person × scope_key × position_bucket**:

| position-table column | derivation from `inningsbatterperf` rows in scope |
| --- | --- |
| innings | `COUNT(*)` |
| runs / legal_balls / dots / fours / sixes | `SUM(...)` |
| dismissals | `SUM(NOT not_out)` |
| thirties/fifties/hundreds/seventies/failures_10/ducks | per-innings `runs` thresholds |

scope_key comes from `make_scope_key(event_name, season, gender, team_type)` on the row's match (the same key the current populate assigns). So `populate_playerscopestats_position` becomes "group the per-innings table by scope_key × bucket" — convention-correct by construction, and the parity test becomes an exact-integer identity. The **parent** `playerscopestats` batting columns are reconciled to this rollup (its bowling/fielding/keeping columns are untouched). Phase/over batting cohorts (§4.2) stay separately computed with the shared convention rule (D3).

## 6. Repopulation + records audit
### 6.1 Rebuild order (back up `cricket.db` to gitignored `tmp/` first, D5)
1. Rebuild `inningsbatterperf` with the non-striker pass (`populate_records_aggregates.populate_full`).
2. Rebuild the batting cohort tables (position via rollup; parent + phase/over via the convention-fixed populates) — `import_data.py`'s full-populate chain.
3. Smoke incremental (`update_recent.py --days N` on a `/tmp` copy) — non-striker rows + all-ball runs fill on the incremental path too.
4. **Deploy note:** prod DB needs the same rebuild before this ships (re-run the populates or re-upload), per the NO-DEPLOYS gate.

### 6.2 Records audit (the non-striker rows must not corrupt records)
Enumerate every records query reading `inningsbatterperf` (`grep -rn inningsbatterperf api/routers/` → `tournaments.py`, `batting.py`, `teams.py`) and confirm behaviour with the new 0-ball rows:
- best-individual-batting `ORDER BY runs DESC` — safe (0-rows sort last).
- any innings / duck count — verify it should now include non-striker ducks (correct) or must exclude the new rows (e.g. `WHERE balls > 0 OR not_out = 0` or a dedicated guard). One assertion per call site (`feedback_test_every_call_site`).

## 7. Sequencing (commit-sliced; each shipped step self-consistent — D6)
1. **Enumerate + classify** the `batting.py` runs-drop sites (no code change; produces the §4.1 list).
2. **inningsbatterperf non-striker completion** + rebuild + parity (extends `test_inningsbatterperf_position.py`: non-striker rows present; innings count now matches the summary's `(batter_id OR non_striker_id)` count) + records audit (§6.2).
3. **Position cohort = rollup of `inningsbatterperf`** (§5). Parity flips to an **exact-integer** cross-check: `playerscopestatsposition` == aggregate of `inningsbatterperf` by scope_key × bucket (the check this whole spec came from).
4. **Convention fix in the read queries + parent + phase/over populates** (§4.1, §4.2), landed so the own number and the cohort move together. Red-then-green: Kohli summary 13117 → 13166; cohort runs shift by the same no-ball amount; the comparison chip stays consistent.
5. **Re-baseline + docs:** flip affected REG baselines REG→NEW in a preceding commit (`feedback_regression_before_shape`); update batting cohort sanity expecteds; `how-stats-calculated.md` (batting runs = off-the-bat over all balls), `server-vs-client-calcs.md`, `data-pipeline.md` (non-striker rows), `docs/api.md`.

## 8. Test plan
- **Exact-integer cross-check (the headline):** `playerscopestatsposition` == `inningsbatterperf` aggregated by scope_key × bucket, every column, every scope (men's IPL 2016 + women's WBBL 2018/19 at least). No `to-2dp` — integer counts are exact.
- **Own number:** `/batters/{id}/summary` runs == all-ball SQL (Kohli 13166), strictly greater than the old legal-only number; SR/avg recompute accordingly. Red before the fix.
- **Own ↔ cohort consistency:** the comparison chip's own and cohort sides both all-ball at every filter combination (the matrix in CLAUDE.md).
- **Non-striker innings:** summary innings count == `inningsbatterperf` row count for the player (now that pure non-striker rows exist); a known non-striker run-out (diamond duck) appears as an innings + dismissal.
- **Records unchanged where it should be:** best-individual-batting top-N identical pre/post; duck/innings records change only in the intended direction (§6.2).
- **Incremental:** new columns + non-striker rows fill after `update_recent.py --days N` on a `/tmp` copy.

## 9. Non-goals
- Bowling / fielding / keeping conventions (only batting runs are wrong).
- The team side (already correct).
- 3b itself — resumes in `spec-player-baseline-aux-fallback.md` once this lands; the per-innings table it reads will then be convention-correct and complete.
- Phase/over batting cohort *single-sourcing* (can't be derived from a per-innings table; they only get the convention fix).
