# Spec — Unify the inning filter on "batted-first" semantics (Option B)

**Status:** PLAN — not yet implemented. Supersedes the per-discipline
"innings-number / bowled-first" framing in `spec-inning-split.md` §1,
§3.4, §7. Decision date: 2026-05-25.

## 1. The decision

Today the app uses **two clashing meanings** for `?inning=`:
- Match-level endpoints (teams `/summary`, By Season, vs Opponent,
  Match List) → `_inning_match_filter` → `inning=0` = **team batted
  first** (a match subset).
- Per-discipline surfaces (player `/batting`,`/bowling`,`/fielding`;
  teams Batting/Bowling/Fielding/Partnership bands; Compare slots) →
  central clause `i.innings_number = :inning` → `inning=0` = events in
  the match's first half, i.e. **bowled-first** for bowling/fielding.

Symptom (CSK Bowling, `inning=0`): scope strip says "batted first",
mosaic/toggle/chart say "bowled first", and the data is the 122
bowled-first matches (batted-first would be 144). One page, three
labels, one of them wrong.

**Unify on the match-level meaning everywhere:**

> `inning=0` ≡ the subject's team **batted first** (innings_number 0).
> `inning=1` ≡ the subject's team **batted second**.
> For bowling/fielding this is the team's activity in those matches —
> which is the *other* innings. So **"bowled first" = batted second =
> `inning=1`** and **"bowled second" = batted first = `inning=0`**.

### 1.1 Label ↔ value contract (the crux)

| POV (via `useDiscipline()`) | Pill "first" | writes | Pill "second" | writes |
|---|---|---|---|---|
| batting / neutral | "1st innings" / "Batted first" | `inning=0` | "2nd innings" / "Batted second" | `inning=1` |
| **bowling / fielding** | **"Bowled first"** | **`inning=1`** | **"Bowled second"** | **`inning=0`** |

So on bowling/fielding surfaces the toggle's *value is flipped* vs the
label's first/second — because the team bowls in the innings it did
NOT bat. Everywhere else the value matches the ordinal.

### 1.2 URL impact
- `inning` param key unchanged; values still `0|1`.
- **Batting** surfaces: meaning unchanged (`inning=0` was and stays
  batted-first). Old links stable.
- **Bowling/Fielding** surfaces: today's `inning=0` view (bowled-first)
  moves to `inning=1`. Old `inning=0` bowling links now show batted-
  first (2nd-innings) bowling. No errors, different numbers.

## 2. Backend mechanism

One shared idea: **inning narrows to the match subset where the
subject's team batted in innings_number = N**, never to the event's
own innings_number.

- **Teams** (subject = path team): already correct via
  `_inning_match_filter` (`api/routers/teams.py`). Audit that EVERY
  team discipline endpoint routes inning through it, not through the
  central `i.innings_number` clause.
- **Players** (subject = `matchplayer.team` per match): NEW
  `player_inning_match_clause(aux, person_id, params, match_id_expr)`
  in `api/filters.py`, sibling to `player_result_clause`:
  ```sql
  <match_id_expr> IN (
    SELECT i2.match_id FROM innings i2
    JOIN matchplayer mp2 ON mp2.match_id = i2.match_id
                        AND mp2.person_id = :pid AND mp2.team = i2.team
    WHERE i2.innings_number = :inn AND i2.super_over = 0)
  ```
  Inject into the 5 discipline filter helpers; REMOVE reliance on the
  central `i.innings_number = :inning` clause for player endpoints.
- **Central clause** (`FilterBarParams.build`) + `aux_clauses.InningClause`:
  must STOP emitting `i.innings_number = :inning` for these surfaces.
  Decide: gate it off for player/team discipline queries (they now use
  the match-subset clause) — keep only if a surface genuinely wants
  raw innings_number (none after this change; confirm none remain).

## 3. Call-site / tab table (USER-FACING — one integration test each)

Status legend: ☐ todo · ◑ code done · ✓ code+test green.

| # | Surface · tab | Widget | inning=0 today | inning=0 target | Label change | Integration test | Status |
|---|---|---|---|---|---|---|---|
| U1 | `/batting?player` (all tabs) | InningToggle | batted 1st | batted 1st | none (already "Batting first") | `inning_unify_players.sh` | ✓ toggle+summary; ◑ deep tabs (1b) |
| U2 | `/bowling?player` (all tabs) | InningToggle | bowled 1st | **batted 1st** (bowled 2nd) | "Bowling first" → inning=1 (value-flip) | `inning_unify_players.sh` | ✓ toggle+summary+by-X; ◑ vs-Batters (1b) |
| U3 | `/fielding?player` (all tabs) | InningToggle | fielded 1st | **batted 1st** (fielded 2nd) | "Bowling first" → inning=1 | `inning_unify_players.sh` | ✓ toggle+summary+matches; ◑ victims/keeping (1b) |
| U4 | `/players?player` summary | InningToggle (neutral) | mixed/polysemy | batted 1st (all 4 tiles + matches) | neutral "1st innings" = batted 1st | `inning_unify_players.sh` | ✓ (matches 206/190 = SQL) |

> **Phase 1 (players) progress — 2026-05-25:** A1 (clause+flag), the 5
> discipline filter helpers, fielding `matches`, batting dismissals,
> the toggle value-flip (U1–U4), ScopeStatusStrip + abbreviateScope POV
> (U16/U17) — all DONE + green (`inning_unify_players.sh` 5/5).
> **Phase 1b (players remainder) — DONE 2026-05-25:** the 5 person-scoped
> sites are routed through the match-subset clause — batting
> inter-wicket (1339) + records (1887); fielding keeping sub-stats
> (424); keeping summary-ambiguous (140) + ambiguous list (394).
> `inning_unify_players.sh` 12/12 green (records SQL-anchored 113/108;
> fielding innings_kept 166/152; keeping ambiguous 32/18; inter-wicket
> non-degenerate + narrows). Still per-event / out of Phase 1b:
> `_inter_wicket_cohort_sr` (batting 1286 — COHORT, no person_id → A8 /
> §8.5, NOT this recipe).
> **GAP FOUND while auditing siblings:** `bowlers/{id}/records` (1945) +
> `fielders/{id}/records` (1434) are inning-BLIND today
> (`build(has_innings_join=False)`, no clause — never honored inning,
> pre-Option-B). Now asymmetric with the just-wired `batters/{id}/records`.
> Per U2/U3 "all tabs" they should carry `player_inning_match_clause`
> too (one-line add each, `m.id` in scope). NOT yet done — pending
> scope confirmation. Phases 3–5 (teams/series/venues) untouched.
| U5 | `/teams?team` Batting | SplitsMosaic + scope strip | batted 1st | batted 1st | none | `inning_unify_teams_batting.sh` | ☐ |
| U6 | `/teams?team` Bowling | SplitsMosaic + scope strip | bowled 1st | **batted 1st** | scope strip + mosaic + chart all "batted first" | `inning_unify_teams_bowling.sh` | ☐ |
| U7 | `/teams?team` Fielding | SplitsMosaic + scope strip | bowled/fielded 1st | **batted 1st** | unify labels | `inning_unify_teams_fielding.sh` | ☐ |
| U8 | `/teams?team` By Season / vs Opp / Match List | (match-level) | batted 1st | batted 1st | none | covered by U5 harness | ☐ |
| U9 | `/teams?team` Partnerships | SplitsMosaic | batted 1st | batted 1st | none | `inning_unify_teams_pship.sh` | ☐ |
| U10 | `/teams?team` Players | SplitsMosaic | per-row inning | batted 1st (each row's team subset) | none | `inning_unify_teams_players.sh` | ☐ |
| U11 | `/teams?team` Compare | SlotScopeEditor | dual-meaning (§3.4) | single batted-1st subset per slot | drop dual-meaning tooltip | `inning_unify_compare.sh` | ☐ |
| U12 | `/series?tournament` Bowling/Fielding | InningToggle | bowled 1st | batted 1st | flip value | `inning_unify_series.sh` | ☐ |
| U13 | `/series?tournament` Batting/Pship/Records | InningToggle | batted 1st | batted 1st | none | (same harness) | ☐ |
| U14 | `/venues?venue` Bowlers/Fielders | InningToggle | bowled 1st | batted 1st | flip value | `inning_unify_venues.sh` | ☐ |
| U15 | `/venues?venue` Batters/Records | InningToggle | batted 1st | batted 1st | none | (same harness) | ☐ |
| U16 | ScopeStatusStrip (every tab) | label only | POV mislabel (CSK bug) | matches the toggle's POV phrase | fix POV derivation | asserted in each U* harness | ☐ |
| U17 | abbreviateScope (chart subtitles) | label only | POV "bowled first" | POV consistent w/ toggle | align | asserted in U2/U6 harnesses | ☐ |
| U18 | user-help.md "Innings toggle" | docs | bowled-first examples | batted-first examples | rewrite §Innings toggle | n/a (content) | ☐ |

## 4. API table (endpoint consistency — one regression test each)

Regression = `tests/regression/` URL list; DB-anchored = a sanity test
that re-derives the expected match subset from sqlite at runtime.

| # | Endpoint(s) | inning today | inning target | Change | Test | Status |
|---|---|---|---|---|---|---|
| A1 | `filters.player_inning_match_clause` (NEW) + `build(apply_inning=…)` flag | — | match subset (player team batted in N) | add helper + flag | `test_inning_clause.py` (DB-anchored) | ◑ inert (added, unwired) |
| A2 | `/batters/{id}/summary` (+ by-season/over/phase/innings/dismissals) | innings_number | match subset | inject A1, drop central inning | `regression/batting` + `inning_unify_batting.sh` | ☐ |
| A3 | `/bowlers/{id}/*` | innings_number (bowled 1st) | match subset | inject A1 | `regression/bowling` | ☐ |
| A4 | `/fielders/{id}/*` (+ keeping) | innings_number | match subset | inject A1 | `regression/fielding` | ☐ |
| A5 | `/teams/{team}/summary,by-season,vs,match-list` | batted 1st (`_inning_match_filter`) | unchanged | audit only | `regression/teams` | ☐ |
| A6 | `/teams/{team}/{batting,bowling,fielding,partnerships}/{summary,by-phase,by-season,top-*}` | innings_number | `_inning_match_filter` subset | route through match filter | `regression/teams` | ☐ |
| A7 | `/teams/{team}/{...}/by-inning` band endpoints | innings_number band | RE-FRAME: band keyed by team-batting-innings | redefine band axis | `inning_band.sh` | ☐ |
| A8 | `/scope/averages/...` cohort (inning-aware) | innings_number | match subset (cohort weighting) | audit + align | `regression/scope` | ☐ |
| A9 | `/tournaments/*` (series dossier leaderboards) | innings_number | match subset | inject | `regression/series` | ☐ |
| A10 | `/venues/*` leaderboards | innings_number | match subset | inject | `regression/venues` | ☐ |
| A11 | `aux_clauses.InningClause` | `i.innings_number=:inning` | remove/repurpose | retire for these surfaces | covered by A2-A10 | ☐ |
| A12 | `bucket_baseline_dispatch.py` | innings_number gate | match subset / live fallback | audit precompute path | `regression/*` drift | ☐ |

## 5. Resolved decisions (2026-05-25)

1. **`/by-inning` band charts (A7) — RESOLVED: label audit only.** The
   bands are a display of both halves (not toggle-driven). On
   bowling/fielding pages they read "Bowled first / Bowled second"
   (unambiguous per §1 discipline-page rule); on batting, "Batted
   first / second." No re-aggregation — just audit the bar label +
   order so "Bowled first" sits on the innings_number-0 bowling data.
2. **Cohort baselines under inning (A8) — RESOLVED: recompute to align
   language.** Precompute already exists; it may need re-running so the
   stored split matches the unified meaning. Acceptable to fall to the
   live path where precompute can't express the match-subset.
3. **Compare dual-meaning (U11/§3.4) — RESOLVED: DROP it.** A Compare
   slot is multi-discipline (same shape as the main `/players` page),
   so one slot = one batted-first/second **match subset** across batting
   AND bowling rows. To compare a team's 1st vs 2nd innings you set one
   slot `inning=0` and the other `inning=1` — unambiguous. The §3.4
   same-token cross-read is intentionally retired.

### Governing rule (locked)
- **Multi-discipline surfaces, one neutral toggle** (main `/players`;
  Teams Compare slots): "1st innings" = team **batted first**; bowling/
  fielding tiles draw from those matches = their 2nd-innings work
  (`inning=1` data). Verbally "1st innings" but bowling comes from the
  2nd innings — coherent because one toggle governs all disciplines.
- **Single-discipline pages** (`/batting`,`/bowling`,`/fielding` for
  players AND teams): POV-specific unambiguous labels — "Bat first/
  second" on batting, "Bowl first/second" on bowling+fielding.
  "Bowl first" = `inning=1`; "Bowl second" = `inning=0`.

## 6. Sequencing

1. Backend A1 + A2–A4 (players) + DB-anchored test → players coherent first.
2. Frontend U1–U4 (toggle value-flip + labels + scope strip) + tests.
3. Backend A5–A7 (teams) + A8.
4. Frontend U5–U11 (teams mosaic/scope/compare) + tests.
5. Series + venues A9/A10 + U12–U15.
6. Docs: rewrite `spec-inning-split.md` §1/§3.4/§7, CLAUDE.md inning rule,
   `inning-controls-mount-sites.md`, user-help.md (U18).
7. Regression REG→NEW flips (A2–A10) in a PRECEDING commit per the
   regression-before-shape rule.

## 8. NEW-SESSION CONTINUATION GUIDE — START HERE

Written 2026-05-25 for a fresh context. Read §1 (the contract) + §8.

### 8.0 State / quick-start
- Branch `main`. Commits this session (NOT pushed, no deploy):
  `1cf8d6a` (player result filter + match-count tiles + inning Phase 1),
  `6ed526b` (captaincy note), `58a5ffa` (Phase 1b dismiss subqueries).
- Run backend (ALWAYS --reload): `uv run uvicorn api.app:app --reload --port 8000`.
  Frontend: `cd frontend && npm run dev` (port 5173). Type-check: `cd frontend && npx tsc -b`.
- Test subject: Kohli `ba607b88` (gender=male). DB: `./cricket.db` (887 MB).
  **Watch cwd** — `cd frontend` persists across Bash calls; `cd` back before sqlite3/curl.
- Green tests already shipped: `tests/integration/inning_unify_players.sh` (5/5),
  `player_result_filter.sh` (8/8).

### 8.1 The mechanism (already built — reuse, don't reinvent)
- `api/filters.py::player_inning_match_clause(aux, person_id, params, match_id_expr="m.id", key="pim_pid")`
  → bare clause: matches where the player's team batted in `innings_number = aux.inning`
  (`mp2.team = i2.team`, `super_over=0`). Returns "" when inning unset.
- `api/filters.py::build(..., apply_inning=False)` + `build_side_neutral(..., apply_inning=False)`
  → suppress the per-event `i.innings_number=:inning` central clause.
- Teams already have `api/routers/teams.py::_inning_match_filter(team, aux)` = the
  team-POV equivalent (batted-first match subset). It's correct; the job is to ROUTE
  the per-discipline teams endpoints through it instead of the central clause.
- **Frontend value-flip contract (DONE for the global InningToggle):** in
  `InningToggle.tsx`, bowling/fielding POV → "first" pill writes `inning=1`,
  "second" writes `inning=0`; batting/neutral unchanged. `ScopeStatusStrip.tsx` +
  `scopeLinks.ts::abbreviateScope` POV labels flipped to match. The Splits Mosaic
  + SlotScopeEditor (teams/compare) still need the same treatment (Phase 2).

**Per-site wiring recipe** (each unwired `build(...has_innings_join=True, aux=aux)`):
1. add `apply_inning=False` to that build/build_side_neutral call;
2. add the clause to the query's WHERE:
   - parts-list site: `ri = player_inning_match_clause(aux, person_id, params); if ri: parts.append(ri)`;
   - string-concat site: `ri = player_inning_match_clause(aux, person_id, params); where = f"{where} AND {ri}" if ri else where` (match the existing where var name);
3. `match_id_expr` defaults to `m.id` — fine when the query `JOIN match m`. If the
   query has no `m`/different alias, pass the right match-id column.
Import is already added to all 4 player routers.

### 8.2 Phase 1b — players remainder (6 sites; each is the recipe above)
| File:line (will drift — re-grep) | Endpoint | Assembly | Notes |
|---|---|---|---|
| `batting.py` ~1339 | `batting_inter_wicket` | string `scope_where` | player SR-by-wickets-down; person-scoped |
| `batting.py` ~1887 | `batting_records` | string `base_filt` (has `ib`+`i`+`m`) | uses `ib.batter_id`; `m.id` ok |
| `fielding.py` ~424 | `fielding_summary` (keeping sub-stats) | parts `keeping_parts` | side-neutral; `JOIN match m` present |
| `keeping.py` ~140 | `keeping_summary` (ambiguous innings) | parts `amb_parts` | side-neutral |
| `keeping.py` ~394 | `keeping_ambiguous` | parts `parts` | side-neutral |
| `batting.py` ~1286 | `_inter_wicket_cohort_sr` | **COHORT, no person_id** | NOT this recipe → see §8.5 (A8 cohort) |
Re-grep before editing: `grep -n "build(has_innings_join=True, aux=aux)\|build_side_neutral(has_innings_join=True, aux=aux)" api/routers/{batting,bowling,fielding,keeping}.py | grep -v apply_inning`
Then add `inning_unify_players.sh` assertions for inter-wicket + keeping; re-run green.

**DONE 2026-05-25** — the 5 person-scoped sites wired + `inning_unify_players.sh`
12/12 green. Only `_inter_wicket_cohort_sr` (1286) remains in the
`has_innings_join=True` set (cohort → §8.5). NOTE the records-sibling gap
in the §3 progress box: `bowlers/{id}/records` (1945) + `fielders/{id}/records`
(1434) use `has_innings_join=False` and are inning-blind — not in this
table's grep, surfaced by an exhaustive sweep of ALL `build(...,aux=aux)`
calls. They need the clause too (pending scope confirmation).

### 8.3 Phase 2 — TEAMS (the next big one)
Teams `/summary`, By Season, vs Opponent, Match List already use `_inning_match_filter`
(batted-first) — correct, audit only. The work:
- **Per-discipline team endpoints** route inning through the central per-event clause
  today (bowled-first). Reroute `/teams/{team}/{batting,bowling,fielding,partnerships}/
  {summary,by-season,by-phase,top-*}` to use `_inning_match_filter(team, aux)` (add it to
  their WHERE) + `build(..., apply_inning=False)`. Grep `api/routers/teams.py` for
  `aux=aux` build calls in those handlers.
- **`/by-inning` band endpoints** (A7): label-audit only (bowling band bars = "Bowled
  first/second", batting = "Batted first/second"); data unchanged, may swap bar order.
- **Frontend:** `SplitsMosaic.tsx` (labels + the cell→aux value mapping must match the
  Option-B meaning; the mosaic sets `result`/`toss`/`inning`), the teams ScopeStatusStrip
  POV (currently shows "batted first" on Bowling tab — the CSK bug; needs `useDiscipline`
  to resolve to the bowling POV on teams, or the mosaic to drive it).
- **Compare slots (U11 / §3.4 / §5.3):** DROP the dual-meaning. `SlotScopeEditor.tsx` +
  `hooks/useCompareSlots.ts` — a slot's `inning=0` = that team batted first for ALL its
  rows. Remove the "batting row batted-first / bowling row bowled-first" split + its
  tooltip. To compare 1st vs 2nd innings, set the two slots to `inning=0` vs `inning=1`.
- Tests: `inning_unify_teams_{batting,bowling,fielding}.sh` + `inning_unify_compare.sh`,
  SQL-anchored against `_inning_match_filter` subsets; assert scope-strip/mosaic/chart
  labels AGREE (CSK regression guard: data=bowled-first ⇒ all labels say so).

### 8.4 Phase 3 — series + venues
`/series` (TournamentDossier Bowling/Fielding toggle) + `/venues` (VenueDossier
Bowlers/Fielders toggle) leaderboards apply inning via the central clause /
`splice_aux_join_clauses`. These leaderboards are scope-wide (not single-person), so they
need a **scope-POV** inning = "innings where the listed players' team batted in N". Decide:
(a) for a leaderboard the natural reading is per-event innings_number of the discipline
(bowled-first) — which CONTRADICTS Option B; or (b) reframe to batted-first. RESOLVE with
the user before coding (leaderboards have no single subject team). Frontend toggles
(`TournamentDossier.tsx`, `VenueDossier.tsx`) reuse `InningToggle` (already value-flipped).
Files: `api/routers/tournaments.py`, `api/routers/venues.py`,
`api/routers/bucket_baseline_dispatch.py`, `api/aux_clauses.py::InningClause`.

### 8.5 Cohort baselines (A8) — cross-cutting, do alongside whichever phase
`api/routers/scope_averages.py` has `inning_active` branches at ~1223/1268/1336/1379 that
filter the cohort by innings_number. Under Option B a cohort's inning = "matches where each
cohort player's team batted in N". The player ProbChip/cohort comparisons (DismissalCohort
charts, position/phase cohorts) need this to stay apples-to-apples. Precompute may need
re-running (user OK'd — §5.2); fall to live where it can't express the subset. The
`_inter_wicket_cohort_sr` site (§8.2) is part of this.

### 8.6 Docs to rewrite when the code is done
- `internal_docs/spec-inning-split.md` §1, §3.4, §7 — supersede with Option B.
- `CLAUDE.md` "Page conventions → Inning-toggle labels — POV-aware" rule.
- `internal_docs/inning-controls-mount-sites.md` — note label/value semantics.
- `frontend/src/content/user-help.md` §"Innings toggle" (currently bowled-first examples).
- Update the U/A status boxes in §3/§4 here as rows land.

### 8.7 Verification cheatsheet (DB-anchored)
Kohli match subsets (male): batted-first=206, batted-second=190 (super_over=0).
```sql
SELECT COUNT(DISTINCT mp.match_id) FROM matchplayer mp
 JOIN innings i ON i.match_id=mp.match_id AND i.team=mp.team
 JOIN match m ON m.id=mp.match_id
 WHERE mp.person_id='ba607b88' AND m.gender='male'
   AND i.innings_number=:N AND i.super_over=0;   -- N=0 →206, N=1 →190
```
Coherence invariant: for ANY player, fielding `matches` at inning=N == that subset count;
batting & bowling `matches` ≤ fielding (they're sub-events of the same matches). Bowling
wickets at `inning=1` == raw innings_number-0 bowling (bowled-first). Every per-discipline
total at inning=0 + inning=1 == the unfiltered total (complement check).

### 8.8 Gotchas
- The toggle value-flip is **POV-driven** (`useDiscipline()`): batting/neutral don't flip,
  bowling/fielding do. A surface with NO discipline context (neutral) must mean batted-first.
- `apply_inning=False` WITHOUT adding the clause = the endpoint IGNORES inning entirely
  (silent regression). Always do both in the same edit.
- `match_id_expr` must reference a match-id column the query actually has in scope.
- Don't double-filter: never leave the central clause on (apply_inning default True) AND
  add the match clause — for bowling they're contradictory → empty results.
- Cohort/scope_averages is a SEPARATE concern (no person_id) — don't use
  `player_inning_match_clause` there.

## 7. Test doctrine
- Every U-row: load the page in agent-browser at `inning=0` and
  `inning=1`, assert the rendered headline matches a sqlite-derived
  match-subset count, AND assert the toggle/scope-strip/mosaic labels
  agree with each other (the CSK-mismatch regression guard).
- Every A-row: curl endpoint at `inning=0|1`, assert value == sqlite
  match-subset re-derivation; add the URL to the matching
  `tests/regression/*/urls.txt` (flip REG→NEW first).
