# Audit — aux-param (inning / toss / result) coverage across comparisons

**Date:** 2026-05-26. **Method:** every comparison-bearing endpoint hit at
no-filter / `inning=0` / `toss_outcome=won` / `result=won`; recorded whether
the **number (value)** and its **comparison baseline** ("vs typical/league/
cohort") each change. A comparison is **fair** only if BOTH narrow together.
Mosaic excluded (per request).

> **RE-VERIFIED 2026-05-26 with a robust method** — reproducible script
> `tests/aux_param_audit.py`. The first pass read array rows by POSITION,
> which mis-graded the by-inning band (a row-reorder artifact). The
> re-audit reads tile values/baselines as scalars and compares whole
> season/phase/innings-**keyed maps** for charts, so reordering/dropping
> rows can't fool it. Every cell below matches the re-audit output. Run
> `python3 tests/aux_param_audit.py` to reproduce against a live backend.

**Aux params:** `inning` (1st/2nd innings, Option B = batted-first),
`toss_outcome` (won/lost toss), `result` (won/lost match).

---

## TL;DR — the patterns

1. **Teams = fully fair.** Every team per-discipline tile, band, and chart
   narrows BOTH the number and its baseline for all 3 aux. ✅
   - One exception: the **Team header Win% tile** — value narrows, baseline frozen.
2. **Players = broken.** The player's own numbers narrow for **inning** and
   **result**, but:
   - the **"typical player" baseline never narrows** for ANY aux (every
     summary chip, every chart cohort line, every distribution chip), and
   - **toss does nothing at all** on player pages (not wired).
3. **Series / Venues leaderboards** narrow by **inning** only (no baseline to
   mismatch; toss/result not applied — arguably fine for ranked lists).

**Root cause of the player gap (single point):** every player cohort number
comes from `scope_averages.compute_players_*_cohort` / the
`/scope/averages/players/*` endpoints, which read the precomputed
`playerscopestats*` tables. Those tables are keyed ONLY by
gender / team_type / tournament / season / team_class / series_type. So the
player "typical" comparison **narrows for those six, but is FROZEN for any
filter not in that key — `filter_venue`, `filter_opponent`/`filter_team`,
AND all three aux (`inning`, `toss_outcome`, `result`)** (verified
2026-05-26: venue/opponent/aux all leave the cohort unchanged; tournament/
season/type do change it). There is no live fallback. Teams DO narrow for
venue/opponent/aux because `is_precomputed_scope` sends those to a live path
(`_option_b_team_inning` + `_cohort_outcome_clause`). That live fallback is
exactly what the player cohort lacks.

> **CORRECTION (2026-05-26):** an earlier draft said the player cohort is
> "frozen for the 3 aux." That UNDERSTATED it — it's frozen for **venue +
> opponent + the 3 aux** (5 filters), and narrows only for the 6
> precompute-scope-key filters. The §A "broken" rows below apply to those 5
> frozen filters, not just aux.

---

## §A — UI audit (tab · subtab · number/graph × aux)

`✓` = fair (value + baseline both narrow). `✗` = broken (see why). `n/a` =
no comparison baseline on this surface. `—` = filter intentionally absent.

### Teams page

| Subtab | Number / graph | inning | toss | result | URL (if broken) |
|---|---|:-:|:-:|:-:|---|
| Header | Win % tile (vs avg) | ✗ baseline frozen | ✗ | ✗ | `/teams?team=Chennai+Super+Kings&gender=male&inning=0` |
| Batting | Run-rate / Boundary% tiles | ✓ | ✓ | ✓ | — |
| Batting | By-season chart (+ cohort line) | ✓ | ✓ | ✓ | — |
| Batting | By-phase bands | ✓ | ✓ | ✓ | — |
| Batting | By-inning bands | ✓ | ✓ | ✓ | — (re-filters to the matching innings when a filter is on; shows both as a summary otherwise — verified in browser) |
| Bowling | Economy / Dot% tiles | ✓ | ✓ | ✓ | — |
| Bowling | By-season chart, By-phase bands | ✓ | ✓ | ✓ | — |
| Fielding | Catches/match tile, By-season chart | ✓ | ✓ | ✓ | — |
| Partnerships | Avg-runs / Best tiles | ✓ | ✓ | ✓ | — |
| Compare | columns + cohort + trajectory graph | ✓ | ✓ | ✓ | — |

### Player Batting page (`/batting?player=…`)

| Subtab | Number / graph | inning | toss | result | URL (if broken) |
|---|---|:-:|:-:|:-:|---|
| Summary | SR / Average / etc. tiles (vs cohort chip) | ✗ baseline frozen | ✗ no-op | ✗ baseline frozen | `/batting?player=ba607b88&gender=male&inning=0` |
| By Season | player line vs cohort line | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/batting?player=ba607b88&gender=male&tab=By+Season&inning=0` |
| By Phase | player vs cohort line | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/batting?player=ba607b88&gender=male&tab=By+Phase&inning=0` |
| By Over | player vs cohort line | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/batting?player=ba607b88&gender=male&tab=By+Over&inning=0` |
| Distribution | milestone chips (50+, etc.) vs cohort | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/batting?player=ba607b88&gender=male&inning=0` |

### Player Bowling page (`/bowling?player=…`)

| Subtab | Number / graph | inning | toss | result | URL (if broken) |
|---|---|:-:|:-:|:-:|---|
| Summary | Economy / SR tiles (vs cohort chip) | ✗ baseline frozen | ✗ no-op | ✗ baseline frozen | `/bowling?player=462411b3&gender=male&inning=0` |
| By Season | player vs cohort line | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/bowling?player=462411b3&gender=male&tab=By+Season&inning=0` |
| By Phase | player vs cohort line | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/bowling?player=462411b3&gender=male&tab=By+Phase&inning=0` |
| By Over | player vs cohort line | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/bowling?player=462411b3&gender=male&tab=By+Over&inning=0` |
| Distribution | milestone chips vs cohort | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/bowling?player=462411b3&gender=male&inning=0` |

### Player Fielding page (`/fielding?player=…`)

| Subtab | Number / graph | inning | toss | result | URL (if broken) |
|---|---|:-:|:-:|:-:|---|
| Summary | Catches/match tile (vs cohort) | ✗ baseline frozen | ✗ no-op | ✗ baseline frozen | `/fielding?player=ba607b88&gender=male&inning=0` |
| By Phase / By Season | player vs cohort line | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/fielding?player=ba607b88&gender=male&tab=By+Phase&inning=0` |
| Distribution | catches chips vs cohort | ✗ cohort frozen | ✗ no-op | ✗ cohort frozen | `/fielding?player=ba607b88&gender=male&inning=0` |

### Series dossier (`/series?tournament=…`) · Venues dossier

| Subtab | Number / graph | inning | toss | result | Note |
|---|---|:-:|:-:|:-:|---|
| Batting/Bowling/Fielding | leaderboards | ✓ (reorders) | ✗ no-op | ✗ no-op | ranked lists — no baseline; toss/result not applied |
| Batting/Bowling/Fielding | picked-player scope-stat tile | ✓ value | ✗ no-op | ✗ no-op | n/a baseline (raw series number, no "vs typical" chip) |
| Venues Batters/Bowlers/Fielders | leaderboards | ✓ (reorders) | ✗ no-op | ✗ no-op | reuse the standalone leaders |

---

## §B — API audit (endpoint × aux, value & baseline) + function used

| Endpoint | value: inn/toss/res | baseline: inn/toss/res | inning fn | toss/result fn |
|---|---|---|---|---|
| `teams/{t}/summary` (win%) | ✓/✓/✓ | ✗/✗/✗ | `_inning_match_filter` | `_result/_toss_match_filter` |
| `teams/{t}/{bat,bowl,field,pship}/summary` | ✓/✓/✓ | ✓/✓/✓ | `_option_b_team_inning` | `_result/_toss_match_filter` + `_cohort_outcome_clause` |
| `teams/{t}/{…}/by-season,by-phase` | ✓/✓/✓ | ✓/✓/✓ | `_option_b_team_inning` | same |
| `scope/averages/{bat,bowl,field,pship}/*` (team cohort) | ✓/✓/✓ | (is baseline) | `_option_b_team_inning` (cohort path) | `_cohort_outcome_clause` |
| `batters/{id}/*`, `bowlers/{id}/*`, `fielders/{id}/*` (value) | ✓/✗/✓ | n/a | `player_inning_match_clause` | result: `player_result_clause`; **toss: NONE** |
| `{batters,bowlers,fielders}/{id}/summary` scope_avg chip | — | ✗/✗/✗ | (cohort, see below) | (cohort) |
| `scope/averages/players/*` (player cohort: by-season/phase/over + summary chip) | ✗/✗/✗ | (is baseline) | **`build_scope_clauses` — NO aux** | **NONE** |
| `{batters,bowlers,fielders}/{id}/distribution` cohort | ✗/✗/✗ | ✗/✗/✗ | **`compute_players_*_cohort` → `build_scope_clauses` — NO aux** | **NONE** |
| `series/{bat,bowl,field}ers-leaders`, `bowlers/leaders` etc. | inn only | n/a | `splice_aux_join_clauses(side=)` | **NONE (toss/result not applied)** |

---

## §C — Function audit (the sprawl)

The goal is "all filtering through 2–3 functions." Reality: **~10 distinct
mechanisms**, with inconsistent aux coverage. Inventory:

| # | Function | Handles | Covers which aux | Used by |
|---|---|---|---|---|
| 1 | `FilterBarParams.build()` / `build_side_neutral()` | FilterBar fields + central inning (when `apply_inning`) | inning (central, mostly suppressed now) | everything (FilterBar) |
| 2 | `filters.player_inning_match_clause(side=)` | player inning (per-event) | inning | player value endpoints |
| 3 | `filters.player_result_clause` | player result | result | player value endpoints |
| 4 | **(player toss)** | — | **toss — NOT IMPLEMENTED** | — |
| 5 | `teams.py::_option_b_team_inning(side=)` | team inning (per-event, team-set + cohort) | inning | team value + team cohort |
| 6 | `teams.py::_inning_match_filter` | team match-level inning | inning | team header/summary/by-season/vs/match-list |
| 7 | `teams.py::_result_match_filter` / `_toss_outcome_match_filter` | team toss/result (team-set, keyed on `:team`) | toss, result | team value endpoints |
| 8 | `teams.py::_cohort_outcome_clause(side=)` | team cohort toss/result (keyed on `i.team`) | toss, result | team cohort (scope/averages/{disc}) |
| 9 | `aux_clauses.splice_aux_join_clauses(side=)` / `tournaments._inning_extras(side=)` | leaderboard inning | inning | series + venues + landing leaders |
| 10 | `scope_averages.build_scope_clauses(filters)` | FilterBar-only scope on `playerscopestats*` | **NONE of the 3 aux** | **ALL player cohorts** (summary chip + by-season/phase/over + distribution) |

### The gaps, ranked
1. **Player cohorts honor only the 6 precompute-scope-key filters** (#10) —
   biggest. Every "typical player" number (chip baselines, chart cohort
   lines, distribution chips) reads precomputed `playerscopestats*`, keyed
   only by gender/type/tournament/season/tier/series. So it's **frozen for
   `filter_venue`, `filter_opponent`/`filter_team`, AND all three aux**
   (5 filters). Fix: a live player-cohort path when any off-key filter is
   set (mirror the team `is_precomputed_scope` → live fallback via
   `_cohort_outcome_clause` + `_option_b_team_inning`).
2. **Toss is not wired for players at all** (#4) — player values ignore
   `toss_outcome` entirely. Fix: a `player_toss_clause` peer to
   `player_result_clause` (only if toss-by-player is wanted).
3. **Team header Win% tile baseline frozen** (#6 path) — the only team tile
   whose `scope_avg` doesn't narrow. Small, isolated.
4. **Leaderboards ignore toss/result** (#9) — likely acceptable (ranked
   lists, no baseline), but inconsistent if toss/result narrowing is wanted.

### Consolidation direction
- Player value: inning + result wired via 2 small clauses (#2, #3); add toss
  (#4) → players match teams' 3-aux value coverage.
- Player cohort (#10) is the real consolidation target: route it through a
  live aux-aware path so the baseline narrows like the team cohort does.
  After that, the per-discipline cohort math is the same shape team-side and
  player-side — fewer moving parts.

---

## §D — `filter_team` vs `filter_opponent` (semantics + where the UI sets them)

Verified 2026-05-26 (frontend grep + live hrefs). These two FilterBar
fields are distinct, and `team=` (the Teams page identity) is a THIRD,
different thing people conflate.

### What each means (from `api/filters.py::build`)
| Param | Meaning | SQL (match-level) | Example |
|---|---|---|---|
| `team=` (path, Teams page only) | **subject** of the page | n/a — it's the page identity | `/teams?team=RCB` = "this page is about RCB" |
| `filter_team=X` | games **team X was in** (X on either side) — absolute | `m.team1=X OR m.team2=X` | Ashwin pinned to CSK: 217 IPL → 115 |
| `filter_opponent=Y` | games **against Y**, relative to the subject (player/team) | `m.team1=Y OR m.team2=Y` + (innings: subject is the non-Y side) | Kohli vs Australia: 112 → 22 |

`team=RCB` ≠ `filter_team=RCB`: the first makes RCB the subject; the second
narrows a *player's* games to their RCB spell. The Teams page uses `team=`
and never carries `filter_team` in its own URL (it sets `filter_team` only
in the in-page scope context so child links inherit it).

### Where the UI actually SETS them (the only entry points)
| Filter combo | Set from | Lands on | Example URL |
|---|---|---|---|
| `filter_team` alone | Team → **Players** subtab (squad list); player's **"teams played for" strip** | player page | `/bowling?player=495d42a5&...&filter_team=Chennai+Super+Kings` (Ashwin's CSK-only line) |
| `filter_team` + `filter_opponent` (rivalry pair) | `SeriesLink` rivalry; **Head-to-Head → Teams mode**; `PlayerLink` (`keepRivalry=true`) riding through from a rivalry page | `/series` rivalry dossier; player page | `/series?filter_team=India&filter_opponent=Australia`; drill a player → `/batting?player=ba607b88&...&filter_team=India&filter_opponent=Australia` |
| `filter_opponent` alone | **NOT LINKED ANYWHERE** | — | (only reachable by hand-editing the URL) |

### Gap worth building: opponent-only on a player
"Ashwin (any team) vs RCB" = `filter_opponent=RCB` with no `filter_team` —
his record against RCB across all five franchises. Genuinely useful and
DISTINCT from the rivalry pair (which locks his team too). The site has no
link that sets opponent-only on a player today; the only opponent path is
the rivalry pair, which also pins the team. Candidate: a "vs opponents"
breakdown on player pages, or an opponent control in the FilterBar.

---

## §E — Plan (NEXT SESSION) — make player comparisons fair

Decided 2026-05-26: implement the player-side fixes next session. Scope:

1. **Player "typical" cohort must narrow by the off-key filters** (the big
   one). Today the cohort reads precomputed `playerscopestats*` keyed only
   by gender/type/tournament/season/tier/series, so it's frozen for
   `filter_venue`, `filter_opponent`, `filter_team`, `inning`,
   `toss_outcome`, `result`. Give it a LIVE fallback when any off-key
   filter is set — same shape as the team side (`is_precomputed_scope` →
   live via `_option_b_team_inning` + `_cohort_outcome_clause`). Covers
   the summary chip baselines, the by-season / by-phase / by-over chart
   cohort lines, and the distribution-panel cohort chips, ×3 disciplines.
2. **Wire toss for player values** — a `player_toss_clause` peer to
   `player_result_clause` (player values currently ignore toss entirely).
3. **Team header Win% tile baseline** — small, isolated; make its
   `scope_avg` narrow like the other team tiles.
4. **(Optional / product call)** opponent-only entry point on player pages
   (§D gap) so "Ashwin vs RCB across all teams" is reachable.

Spec/test ref: `spec-player-baseline-parity.md` §108 already REQUIRED the
cohort to narrow by every aux "identical to Teams" — this is closing the
gap between that spec and the shipped implementation. Reproduce current
state with `python3 tests/aux_param_audit.py`.
