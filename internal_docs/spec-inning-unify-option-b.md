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

> **CORRECTED 2026-05-25 (per-event, NOT match-subset).** The original
> "narrow to the match subset where the team BATTED in N" idea below was
> wrong for bowling/fielding: it silently DROPS matches the team bowled
> in but never batted (e.g. a rain-abandoned game where the team fielded
> first and the chase never started — real wickets/balls that MUST count
> toward the bowling average and its denominator). The implemented (and
> correct) rule is **per-event + discipline-aware**:
>
> - **batting**: `i.innings_number = N` (the team batted in N).
> - **bowling / fielding / keeping / bowling-partnerships**:
>   `i.innings_number = (1 - N)` (the team FIELDED in the OTHER innings;
>   bowled-first = innings 0 = `inning=1`). The `i.team` / `i.team != :team`
>   side discriminator already in each query routes batting vs fielding
>   EVENTS; this clause just picks the innings number.
>
> Consequence: batting and bowling legitimately span DIFFERENT match
> counts at the same inning value (CSK `inning=1`: batted-second 121 vs
> bowled-first 122 — the +1 is a bowled-but-didn't-bat game). Tested:
> teams `_option_b_team_inning` (per-event for team-set AND cohort,
> commit d9d8c66); players `player_inning_match_clause(..., side=…)` keys
> on the FIELDING innings for non-batting sides (commit 9de5863).
>
> EXCEPTION — match-level team endpoints (`/teams/{team}/summary`,
> by-season, vs-opponent, match-list) keep the **batted-in-N** match
> subset via `_inning_match_filter` (a match RECORD is batting-POV; a
> game the team never batted has no batting-first/second record). So the
> team header tiles (121 at inning=1) and the Bowling tab (122) differ by
> that one game — by design.
>
> The struck-through text below is the original (match-subset) plan, kept
> for history.

~~One shared idea: **inning narrows to the match subset where the
subject's team batted in innings_number = N**, never to the event's
own innings_number.~~

- ~~**Teams**: via `_inning_match_filter`.~~
- ~~**Players**: `player_inning_match_clause` keyed on `mp2.team = i2.team`
  / `innings_number = N` (match subset). REPLACED by the side-aware
  per-event form above.~~
- **Central clause** (`FilterBarParams.build`) + `aux_clauses.InningClause`:
  discipline callers pass `apply_inning=False` and add the per-event
  clause themselves (teams `_option_b_team_inning`, players
  `player_inning_match_clause(side=…)`). Confirmed no surface still wants
  the raw central `i.innings_number = :inning`.

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
> **Sibling gap FIXED 2026-05-25** (user-approved, folded into 1b):
> `bowlers/{id}/records` (1945) + `fielders/{id}/records` (1434) were
> inning-BLIND (`build(has_innings_join=False)`, no clause — never
> honored inning, pre-Option-B; byte-identical across inning=0/1/none).
> Now carry `player_inning_match_clause(side='bowling'/'fielding')` — the
> fielded-in-(1-N) per-event form (CORRECTED 2026-05-25 from the initial
> batted-in-N subset, which dropped bowled-but-didn't-bat games). Composes
> with the matchbowlerperf / matchfielderperf per-match grain. Harness
> green; records subtab consistent across all 3 discipline profiles
> (U2/U3 "all tabs").
> **STILL OPEN → A8/§8.5 (NOT Phase 1b):** `fielders/{id}/distribution`
> is inning-blind (`_match_master_sample_fielder`, 1026 — docstring
> claims "inning no-op for fielder per §13.1", which is the stale
> per-EVENT rationale). Batting + bowling distribution already honor
> inning; fielding is the lone holdout, now inconsistent with fielding
> `matches` (206/190) on the SAME page. NOT a quick mechanical fix: the
> panel carries `scope_avg` baselines, so per chip↔baseline-symmetry the
> player master sample and its baseline must move TOGETHER — and the
> baseline is the deferred cohort/scope_averages concern. Do it WITH A8.
> Phases 3–5 (teams/series/venues) untouched.
| U5 | `/teams?team` Batting | SplitsMosaic + scope strip | batted 1st | batted 1st (inning=0) | none | `inning_unify_teams.sh` | ✓ (71b0b59) |
| U6 | `/teams?team` Bowling | SplitsMosaic + scope strip | bowled 1st @inn0 | bat-1st @inn0 = "bowled second" | mosaic+header+strip all agree (POV bowled second @inn0) | `inning_unify_teams.sh` | ✓ (71b0b59) |
| U7 | `/teams?team` Fielding | SplitsMosaic + scope strip | bowled/fielded 1st | bat-1st = "bowled second" | unify labels (bowling POV) | `inning_unify_teams.sh` | ✓ (71b0b59) |
| U8 | `/teams?team` By Season / vs Opp / Match List | (match-level union) | batted 1st | union batted-N OR fielded-(1-N) | none | covered by `inning_unify_teams.sh` header | ✓ (fc8a502) |
| U9 | `/teams?team` Partnerships | SplitsMosaic | batted 1st | batted 1st (bat side) / flip (bowl side) | none (bat) | `inning_unify_teams.sh` | ✓ (43310ec/71b0b59) |
| U10 | `/teams?team` Players | SplitsMosaic | per-row inning | per-event via shared mosaic | none | (same harness) | ◑ mosaic code done; subtab not browser-verified |
| U11 | `/teams?team` Compare | SlotScopeEditor | dual-meaning (§3.4) | single batted-1st subset per slot | drop dual-meaning tooltip | `inning_unify_compare.sh` | ✓ (fda37c1) — also fixed primarySlotOf dropping inning (primary col ignored carried-over inning while slots inherited it); toss/result deliberately NOT carried (cohort can't express them) |
| U12 | `/series?tournament` Bowling/Fielding | InningToggle | bowled 1st | bat-1st @inn0 (bowl/field flip to 1-N) | flip value (toggle done; backend A9) | `inning_unify_series.sh` | ✓ (a1dfa09/c9bd5d9) — toggle "Bowling first/second" + active pill ↔ inning agree; DOM flips & matches flipped API |
| U13 | `/series?tournament` Batting/Pship/Records | InningToggle | batted 1st | batted 1st | none | (same harness) | ✓ (no backend change; batters/records left at innings_number=N) |
| U14 | `/venues?venue` Bowlers/Fielders | InningToggle | bowled 1st | bat-1st @inn0 (flip to 1-N) | flip value (toggle done; backend A10) | `inning_unify_venues.sh` | ✓ (a1dfa09/c9bd5d9) |
| U15 | `/venues?venue` Batters/Records | InningToggle | batted 1st | batted 1st | none | (same harness) | ✓ (batters leaders unchanged) |
| U16 | ScopeStatusStrip (every tab) | label only | POV mislabel (CSK bug) | matches the toggle's POV phrase | fix POV derivation | asserted in `inning_unify_*` harnesses | ✓ (Phase 1) |
| U17 | abbreviateScope (chart subtitles) | label only | POV "bowled first" | POV consistent w/ toggle | align | asserted in harnesses | ✓ (Phase 1) |
| U18 | user-help.md "Innings toggle" | docs | bowled-first examples | batted-first examples | rewrite §Innings toggle | n/a (content) | ☐ |

## 4. API table (endpoint consistency — one regression test each)

> **CORRECTED 2026-05-25 — the "match subset" target below is SUPERSEDED by
> per-event discipline-aware (see the §2 correction box).** A batting-keyed
> "matches the team batted in N" subset wrongly drops matches the team
> BOWLED in but never batted, dropping real wickets/balls from the bowling
> average. The implemented rule:
> - **innings-grain discipline stats**: batting `innings_number = N`;
>   bowling / fielding / keeping `innings_number = (1 - N)`.
> - **match-level / overall-count surfaces** (team header, player
>   result-counts): the **union** "batted in N OR fielded in (1-N)" — count
>   the match by whichever role was played.
> Status marks updated to current.

Regression = `tests/regression/` URL list; DB-anchored = a sanity test
that re-derives the expected slice from sqlite at runtime.

| # | Endpoint(s) | inning today | inning target (per-event) | Change | Test | Status |
|---|---|---|---|---|---|---|
| A1 | `filters.player_inning_match_clause` (now `side=`-aware) + `build(apply_inning=…)` | — | side='batting' → batted-in-N; bowling/fielding/keeping → fielded-in-(1-N); 'match' → union | helper + flag | `inning_unify_players.sh` | ✓ (9de5863, 771ca34) |
| A2 | `/batters/{id}/*` | innings_number | batted-in-N (unchanged) | side='batting' | `inning_unify_players.sh` | ✓ |
| A3 | `/bowlers/{id}/*` | innings_number (bowled 1st) | fielded-in-(1-N) — incl. bowled-but-didn't-bat games | side='bowling' | `inning_unify_players.sh` | ✓ (9de5863) |
| A4 | `/fielders/{id}/*` (+ keeping) | innings_number | fielded-in-(1-N) | side='fielding'/'keeping' | `inning_unify_players.sh` | ✓ |
| A4b | `/players/{id}/result-counts` (overall matches tile) | inning-blind | union (batted-N OR fielded-(1-N)) | side='match' | `inning_unify_players.sh` | ✓ (771ca34) |
| A5 | `/teams/{team}/summary,by-season,vs,match-list` | batted-in-N | **union** batted-in-N OR fielded-in-(1-N) (count the match by role) | `_inning_match_filter` → union | `inning_unify_teams.sh` | ✓ (fc8a502) |
| A6 | `/teams/{team}/{batting,bowling,fielding,partnerships}/{summary,by-phase,by-season,top-*,distribution}` | innings_number | per-event (`_option_b_team_inning`): bat N, bowl/field 1-N | apply_inning=False + helper | `inning_unify_teams.sh` + `regression/teams,team_*_distribution` | ✓ (c4e62fb, 43310ec, d9d8c66) |
| A7 | `/teams/{team}/{...}/by-inning` band endpoints | innings_number band | label-audit only (bowling band = "Bowled first/second") | audit bar labels/order | `team_by_inning.sh` | ✓ (4d565b4) — `InningBandsRow.bandLabel(discipline, inning_no)`: bowling/fielding "Bowled first/second", batting/pship "Batted first/second". Frontend-only (no API drift); SQL anchors confirm label↔innings_number |
| A8 | `/scope/averages/...` cohort (inning-aware) | innings_number | per-event by side (same as A6 cohort path) | done for teams via `_option_b_team_inning`; fielder-distribution master sample now per-event (96644c1) | `regression/scope*` + `fielder_distribution` | ✓ — fielder dist master sample narrows (397→205/191 == matches tile); cohort baseline stays full-scope (playerscopestats has no innings dim — shared accepted behavior w/ batting/bowling dist). `_inter_wicket_cohort_sr` already correct (batting keeps N). A live per-event dist cohort across all 3 panels = separate follow-up |
| A9 | `/tournaments/*` (series dossier leaderboards) | innings_number | per-event: bowling/fielding leaderboards `innings_number=(1-N)`, batting `N` | per-discipline flip in `_inning_extras` call sites | `regression/series` + `inning_unify_series.sh` | ✓ (a1dfa09) — `_inning_extras(side=)` + 4 series sites (bowlers/fielders leaders+scope-stats) flip; batters/records/summary/by_season/rivalry unchanged |
| A10 | `/venues/*` leaderboards | innings_number | per-event: bowlers/fielders `(1-N)`, batters `N` | per-discipline flip | `regression/venues` + `inning_unify_venues.sh` | ✓ (a1dfa09) — venues reuse standalone `/bowlers,/fielders/leaders`; flipped via `splice_aux_join_clauses(side=)`. No venues.py change needed |
| A11 | `aux_clauses.InningClause` / central `i.innings_number=:inning` | central clause | discipline callers pass `apply_inning=False` + own per-event clause | retired for player/team disc surfaces | covered by A2-A6 | ✓ |
| A12 | `bucket_baseline_dispatch.py` | innings_number gate | n/a — `is_precomputed_scope=False` when inning set ⇒ always live path | audit only (no recompute) | `regression/*` 0 drift | ✓ |

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
> **CORRECTED 2026-05-25 — read §2's correction box first.** The clause is now
> DISCIPLINE-AWARE per-event, NOT a batted-in-N match subset (the subset dropped
> bowled-but-didn't-bat games from bowling averages). batting → innings_number=N;
> bowling/fielding/keeping → innings_number=(1-N) via the fielding-innings form.
- `api/filters.py::player_inning_match_clause(aux, person_id, params, match_id_expr="m.id", key="pim_pid", side="batting")`
  → side='batting' (default): matches the player's team BATTED in N
  (`mp2.team = i2.team`, `innings_number=N`). side bowling/fielding/keeping:
  matches the player's team FIELDED in (1-N) (`mp2.team != i2.team`,
  `innings_number=1-N`) — retains bowled-but-didn't-bat games. Returns "" when
  inning unset. Teams use `_option_b_team_inning(team, side, aux)` (per-event,
  same rule, for team-set AND cohort).
- `api/filters.py::build(..., apply_inning=False)` + `build_side_neutral(..., apply_inning=False)`
  → suppress the per-event `i.innings_number=:inning` central clause.
- Teams (DONE): per-discipline endpoints use `teams.py::_option_b_team_inning(team, side, aux)`
  (per-event: bat N, bowl/field 1-N — team-set AND cohort). Match-level endpoints use
  `_inning_match_filter` (now the batted-N OR fielded-(1-N) **union**, so the header counts a
  match by role). Both via `build(..., apply_inning=False)`.
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

> **Phase 2 BACKEND DONE 2026-05-25** (commits 719cd0b flip · c4e62fb core ·
> 43310ec partnerships; main, unpushed). A5 audit + A6 reroute + A8 cohort +
> A11/A12 all landed:
> - New `api/routers/teams.py::_option_b_team_inning(team, side, aux)` — the
>   replacement for the central per-event clause. team-set → `i.match_id IN
>   (matches :team batted in N)` (one clause, both sides — the `i.team`/`!=`
>   discriminator routes events); cohort (team None) → live per-event
>   `innings_number N` (batting) / `1-N` (fielding|bowling).
> - Wired into `_team_innings_clause` (~25 call sites: batting/bowling/
>   fielding summary·by-season·by-phase·top-*·**distribution** + 2 scope-avg
>   cohort calls), the inline `team_summary` keepers subquery, and
>   `_partnership_filter`. All take `build(..., apply_inning=False)`.
> - **CSK bug fixed at the data layer:** bowling inning=0 flips 702/122
>   (bowled-first) → 814/144 (batted-first); scope_avg flips 8.05→7.91 in
>   lockstep (team + cohort share the helper ⇒ no chip↔baseline asymmetry).
>   Batting byte-identical. A12: precompute bypassed under inning
>   (`is_precomputed_scope=False`) so NO recompute needed.
> - Tests: `tests/integration/inning_unify_teams.sh` 7/7 (red 3→green;
>   bowling/fielding matches 122/144→144/121 == batted-in-N subset; batting
>   + batting-partnership partition unchanged; bowling-partnership flips;
>   cohort scope_avg flips). Filter matrix SQL-anchored (inn0+Wankhede=12,
>   inn1=15, inn0+toss_won=61). Regression: 0 REG drift across teams /
>   team_batting_distribution / team_splits / scope-averages; the 4 bowling/
>   fielding distribution inning URLs flipped REG→NEW in preceding 719cd0b
>   (verified correct: MI bowling-dist n_innings 140→150 = batted-first).
> - **STILL OPEN (Phase 2 FRONTEND + A7):** the data is now batted-first but
>   the teams Bowling/Fielding **mosaic + chart labels still say "bowled
>   first"** → now WRONG (the CSK three-labels bug has moved: scope strip is
>   accidentally right, mosaic/chart are stale). Needs SplitsMosaic labels +
>   cell→aux mapping, teams ScopeStatusStrip POV, Compare dual-meaning drop
>   (U5–U11), A7 band-label audit, docs. NONE of this shipped — see below.

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
- Tests: consolidated `inning_unify_teams.sh` (DONE — batting/bowling/fielding +
  partnerships + header, per-event SQL-anchored, 10/10) + `inning_unify_compare.sh`
  (TODO, U11). Assert scope-strip/mosaic/header all AGREE (CSK regression guard:
  Bowling inning=0 → 144 "bowling second" everywhere; inning=1 → 122 "bowling first").

### 8.4 Phase 3 — series + venues  (A9/A10, U12–U15) — NOT YET DONE
> **POV decision RESOLVED 2026-05-25 by the per-event correction (§2 box).**
> The old framing below asked whether a leaderboard should read per-event
> bowled-first ("contradicts Option B") or reframe to batted-first. Under
> per-event discipline-aware that dissolves: a leaderboard's discipline is
> known (a Bowling leaderboard is bowling), so it uses the SAME rule as
> players/teams — bowling/fielding leaderboards filter `innings_number=(1-N)`,
> batting leaderboards `innings_number=N`. The InningToggle already
> value-flips per `useDiscipline()` (tab-based), so the toggle is correct;
> the job is the BACKEND per-discipline flip. No new user decision needed.

`/series` (TournamentDossier) + `/venues` (VenueDossier) leaderboards apply inning via
`_inning_extras` → `splice_aux_join_clauses` (un-flipped `i.innings_number=:inning`).
**Currently MISMATCHED**: the toggle writes inning=1 for "Bowling first" but the backend
returns innings_number=1 = bowled second. Fix = the per-event `(1-N)` flip applied
PER-DISCIPLINE across the leaderboard query sites (enumerate each `_inning_extras` call
in `tournaments.py` (~9 sites) + `venues.py` and pass the discipline; batting queries
stay N, bowling/fielding flip to 1-N — do NOT regex; audit each site). Then add
`inning_unify_series.sh` / `inning_unify_venues.sh` (SQL-anchored: bowling leaderboard
inning=1 == bowled-first / innings_number-0; incl. bowled-but-didn't-bat games) and flip
any REG-locked series/venues inning URLs REG→NEW in a preceding commit.
Files: `api/routers/tournaments.py`, `api/routers/venues.py`,
`api/routers/aux_clauses.py` (or a discipline-aware `_inning_extras`). Frontend toggles
(`TournamentDossier.tsx`, `VenueDossier.tsx`) already reuse the flipped `InningToggle`.

### 8.5 Cohort baselines (A8) — cross-cutting, do alongside whichever phase
`api/routers/scope_averages.py` has `inning_active` branches at ~1223/1268/1336/1379 that
filter the cohort by innings_number. Under Option B (per-event, §2 box) a cohort's inning =
the discipline's own innings: batting cohort `innings_number=N`, bowling/fielding cohort
`innings_number=(1-N)` — same rule as the teams `_option_b_team_inning` cohort path (which
is DONE). The player ProbChip/cohort comparisons (DismissalCohort charts, position/phase
cohorts) need this to stay apples-to-apples with the (now per-event) player value. No
precompute recompute needed — `is_precomputed_scope=False` under inning ⇒ live path. The
`_inter_wicket_cohort_sr` site (§8.2) is part of this.
**Also part of A8 (found 2026-05-25):** `fielders/{id}/distribution` is inning-blind
(`_match_master_sample_fielder`, fielding.py:1026 — `build_side_neutral(has_innings_join=
False)`, no clause; docstring's "inning no-op for fielder per §13.1" is the stale
per-EVENT rationale). Batting + bowling distribution already honor inning. The fix is NOT
just adding `player_inning_match_clause(...,match_id_expr="mp.match_id")` to the
`player_matches` CTE — the panel surfaces `scope_avg` baselines, so the player master
sample AND its baseline must move together (chip↔baseline symmetry) or the histogram
shifts under inning while its reference line doesn't. Wire the master sample + the
scope_avg baseline in the same change.

### 8.6 Docs to rewrite when the code is done
- `internal_docs/spec-inning-split.md` §1, §3.4, §7 — supersede with Option B.
- `CLAUDE.md` "Page conventions → Inning-toggle labels — POV-aware" rule.
- `internal_docs/inning-controls-mount-sites.md` — note label/value semantics.
- `frontend/src/content/user-help.md` §"Innings toggle" (currently bowled-first examples).
- Update the U/A status boxes in §3/§4 here as rows land.

### 8.7 Verification cheatsheet (DB-anchored, PER-EVENT)
Per-event, discipline-aware (the implemented rule). For a player `:pid`:
```sql
-- BATTING matches (batted in N): mp2.team = i2.team, innings_number = N
SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN matchplayer mp ON mp.match_id=i.match_id
 JOIN match m ON m.id=i.match_id
 WHERE mp.person_id=:pid AND mp.team=i.team AND m.gender='male'
   AND i.innings_number=:N AND i.super_over=0;
-- BOWLING/FIELDING matches (fielded in 1-N): mp2.team != i2.team, innings_number = 1-N
SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN matchplayer mp ON mp.match_id=i.match_id
 JOIN match m ON m.id=i.match_id
 WHERE mp.person_id=:pid AND mp.team!=i.team AND m.gender='male'
   AND i.innings_number=(1-:N) AND i.super_over=0;
-- OVERALL match-count tile / team header (union): the two above OR'd together.
```
Worked numbers — Kohli (`ba607b88`, male): batting 206/178 (N=0/1); fielding 205/191.
CSK teams: batting innings 144/121; bowling/fielding matches 144/122 (incl. 1 bowled-but-
never-batted game, match 5845, +7 wkts at inning=1); header/union 144/122. DL Chahar
bowling 65/80 (inning=0/1). Coherence: bowling matches and batting matches DIFFER by
bowled-but-didn't-bat (or batted-but-didn't-field) games — they are NOT forced equal, and
inning0+inning1 need NOT sum to the unfiltered total (abandoned games belong to one slice
of one discipline only). The old "complement check" no longer holds — that was the
match-subset assumption.

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
