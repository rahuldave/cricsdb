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

> ## ✅ RESOLVED 2026-05-29 — the player gap (§E items 1 + 2) is CLOSED
>
> Everything marked ✗ below was the **2026-05-26 snapshot**. The player-side
> live cohort fallback shipped in 3b/3c/3d/3e + denominator B + Tier-3 Phase B
> (commits `00ef3d1..7a3e6a1`, the player-baseline-aux-fallback arc), and the
> player toss clause was wired. **Now:**
> - the player "typical player" cohort **narrows live** for all six off-key
>   filters (venue, opponent, team, inning, toss, result) — dispatch on
>   `is_precomputed_scope` → live `compute_players_{batting,bowling,fielding}_cohort`
>   / `_by_season` / `_by_phase` in `scope_averages.py` (mirrors the team side);
> - **toss is wired for player values** too;
> - the per-position / per-over MIX histogram intentionally stays coarse
>   (Tier-2 design) — only the per-bucket cohort VALUES narrow.
>
> Every ✗ in §A / §B below should read ✓ as of 2026-05-29 (flipped inline,
> with the old state struck through). DOM-verified surface-by-surface in
> `narrowing-audit-coverage.md`; locked by `tests/integration/` (the
> `player_baseline_*`, `sparkline_narrowing`, `player_toss_value`,
> `prob_chip_baselines`, per-tab chart suites — all green). The exception
> (coarse mix) is by design. §C/§E gaps 1+2 are DONE.

---

## TL;DR — the patterns

1. **Teams = fully fair.** Every team per-discipline tile, band, and chart
   narrows BOTH the number and its baseline for all 3 aux. ✅
   - ~~One exception: the Team header Win% tile — baseline frozen.~~ **FIXED
     2026-05-26** (commit 3d802a2): the Win% "vs average" now narrows too
     (recomputed from the Mosaic's per-team-view split under the aux).
2. ~~**Players = broken.**~~ **Players = fixed (2026-05-29).** The player's own
   numbers narrow for inning, result **and now toss**, and the **"typical
   player" baseline now narrows live for all six off-key filters** (every
   summary chip, every chart cohort line, every distribution chip, every
   sparkline). The MIX histogram on By Position / By Over stays coarse by
   design (Tier 2). The 2026-05-26 snapshot below described the pre-fix state.
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
| Header | Win % tile (vs avg) | ✓ (fixed 3d802a2) | ✓ | ✓ | — (was frozen; now narrows from the per-team-view split) |
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
| Summary | SR / Average / etc. tiles (vs cohort chip) + sparkline cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed 3b) |
| By Season | player line vs cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed 3c) |
| By Phase | player vs cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed 3c) |
| By Over | player vs cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed Tier-3 Phase B; mix histogram stays coarse) |
| By Position | per-position cohort bars | ✓ | ✓ | ✓ | — (cohort bars narrow; position MIX coarse by design) |
| Distribution | milestone chips (50+, etc.) vs cohort | ✓ | ✓ | ✓ | — (was ✗; fixed 3b/3c) |

### Player Bowling page (`/bowling?player=…`)

| Subtab | Number / graph | inning | toss | result | URL (if broken) |
|---|---|:-:|:-:|:-:|---|
| Summary | Economy / SR tiles (vs cohort chip) + sparkline cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed 3d) |
| By Season | player vs cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed 3d) |
| By Phase | player vs cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed 3d) |
| By Over | per-over cohort bars | ✓ | ✓ | ✓ | — (was ✗; fixed Tier-3 Phase B; over MIX stays coarse) |
| Distribution | milestone chips vs cohort | ✓ | ✓ | ✓ | — (was ✗; fixed 3d) |

### Player Fielding page (`/fielding?player=…`)

| Subtab | Number / graph | inning | toss | result | URL (if broken) |
|---|---|:-:|:-:|:-:|---|
| Summary | Catches/match tile (vs cohort) + sparkline cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed 3e) |
| By Phase / By Season | player vs cohort line | ✓ | ✓ | ✓ | — (was ✗; fixed 3e) |
| By Dismissed Position / By Over | per-bucket cohort bars | ✓ | ✓ | ✓ | — (keeper-binary, no mix → narrows fully; Tier-3 Phase B + 3e) |
| Distribution | catches chips vs cohort | ✓ | ✓ | ✓ | — (was ✗; fixed 3e) |

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
| `teams/{t}/summary` (win%) | ✓/✓/✓ | ✓/✓/✓ (fixed 3d802a2) | `_inning_match_filter` | `_splits_cells` + `_cell_label_for_aux` (baseline) |
| `teams/{t}/{bat,bowl,field,pship}/summary` | ✓/✓/✓ | ✓/✓/✓ | `_option_b_team_inning` | `_result/_toss_match_filter` + `_cohort_outcome_clause` |
| `teams/{t}/{…}/by-season,by-phase` | ✓/✓/✓ | ✓/✓/✓ | `_option_b_team_inning` | same |
| `scope/averages/{bat,bowl,field,pship}/*` (team cohort) | ✓/✓/✓ | (is baseline) | `_option_b_team_inning` (cohort path) | `_cohort_outcome_clause` |
| `batters/{id}/*`, `bowlers/{id}/*`, `fielders/{id}/*` (value) | ✓/✓/✓ | n/a | `player_inning_match_clause` | result: `player_result_clause`; toss: now wired |
| `{batters,bowlers,fielders}/{id}/summary` scope_avg chip | — | ✓/✓/✓ | (cohort, see below) | (cohort) |
| `scope/averages/players/*` (player cohort: by-season/phase/over + summary chip) | ✓/✓/✓ | (is baseline) | live `compute_players_*_{cohort,by_season,by_phase}` when any off-key filter set (else precomputed) | `_*_live_where` (inning Option-B flip + toss/result clause) |
| `{batters,bowlers,fielders}/{id}/distribution` cohort | ✓/✓/✓ | ✓/✓/✓ | `compute_players_*_cohort` → live aux-aware path | dispatch on `is_precomputed_scope` |
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
| 4 | `filters.player_toss_clause` | player toss | toss | player value endpoints (wired 2026-05-29) |
| 5 | `teams.py::_option_b_team_inning(side=)` | team inning (per-event, team-set + cohort) | inning | team value + team cohort |
| 6 | `teams.py::_inning_match_filter` | team match-level inning | inning | team header/summary/by-season/vs/match-list |
| 7 | `teams.py::_result_match_filter` / `_toss_outcome_match_filter` | team toss/result (team-set, keyed on `:team`) | toss, result | team value endpoints |
| 8 | `teams.py::_cohort_outcome_clause(side=)` | team cohort toss/result (keyed on `i.team`) | toss, result | team cohort (scope/averages/{disc}) |
| 9 | `aux_clauses.splice_aux_join_clauses(side=)` / `tournaments._inning_extras(side=)` | leaderboard inning | inning | series + venues + landing leaders |
| 10 | `scope_averages.compute_players_*_cohort` / `_by_season` / `_by_phase` (dispatch on `is_precomputed_scope`) | FilterBar scope + the six off-key filters via a live path; precomputed `playerscopestats*` read only at none-of-six | inning (Option-B flip) + toss + result (live path) | **ALL player cohorts** (summary chip + by-season/phase/over + distribution). Was `build_scope_clauses` (no aux); replaced by the live fallback 2026-05-29 |

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

### Path convergence / duplication check (2026-05-26)
Where "Kohli vs Australia" is linked from, and whether team-vs-team paths
duplicate:
- **Kohli vs Australia entry point** = the player leaderboards on the
  **rivalry dossier** (`TournamentDossier` in rivalry mode). Its `PlayerLink`s
  default `keepRivalry=true`, so clicking a player carries
  `filter_team`+`filter_opponent` onto the player page →
  `/batting?player=ba607b88&...&filter_team=India&filter_opponent=Australia`.
  Reached via EITHER `/series?filter_team=India&filter_opponent=Australia`
  OR Head-to-Head → Teams mode (both render the same dossier).
- **No dossier duplication.** Head-to-Head Teams mode is a thin team-picker
  wrapper that renders the SAME `TournamentDossier(filterTeam, filterOpponent)`
  (HeadToHead.tsx:432-437), pinning the pair in `ScopeContext`. `/series`
  rivalry and `/head-to-head` Teams mode therefore CONVERGE on one component
  + one filter mechanism (`filter_team`/`filter_opponent`). Good — they're
  effectively already merged; no action needed.
- **The one separate surface:** the Teams **"vs Opponent"** subtab uses a
  distinct endpoint `getTeamVs` → `/api/v1/teams/{team}/vs/{opponent}` (a
  lighter in-page head-to-head summary, not the dossier). It does NOT use
  `filter_opponent`. If we ever unify team-vs-team surfaces, this is the one
  to reconcile — but it's a smaller/different view, arguably fine as-is.
- **Future player-vs-team head-to-head should REUSE `filter_opponent`** (the
  same substrate H2H Teams mode reuses for the dossier) — i.e. a control
  that wraps the player page with `filter_opponent`, NOT a new endpoint. That
  keeps player-vs-team on the one filter mechanism, no duplicate data path.

### Gap worth building: opponent-only on a player — SHIPPED 2026-05-26
"Ashwin (any team) vs RCB" = `filter_opponent=RCB` with no `filter_team` —
his record against RCB across all five franchises. Genuinely useful and
DISTINCT from the rivalry pair (which locks his team too).

**Built (commit 45c58b7):** a "Versus" typeahead on /players + /batting +
/bowling + /fielding (after a player is chosen), under the teams strip.
Backed by `GET /players/{id}/opponents` (opponent = other side of each
match by `matchplayer.team`, with counts). Drops `filter_opponent` from
its own build so the active pick doesn't collapse the menu; re-applies
`filter_team` at `mp.team` so pinning a team shrinks the menu to that
spell (Kohli@RCB → IPL franchises only). Picking sets `filter_opponent`;
the player value endpoints already honor it. Test:
`tests/integration/player_vs_team.sh`. NOTE: the player "typical" baseline
still does NOT narrow by `filter_opponent` (the §E item-1 frozen-cohort
gap) — the own-numbers narrow, the comparison doesn't yet.

---

## §E — Plan — make player comparisons fair — ✅ DONE 2026-05-29

Decided 2026-05-26; **implemented across 3b/3c/3d/3e + denom-B + Tier-3
Phase B (commits `00ef3d1..7a3e6a1`) and verified 2026-05-29.** Scope:

1. ✅ **Player "typical" cohort narrows by the off-key filters** (the big
   one). It now reads precomputed `playerscopestats*` ONLY at none-of-six;
   when `filter_venue` / `filter_opponent` / `filter_team` / `inning` /
   `toss_outcome` / `result` is set it falls back to a LIVE path — same shape
   as the team side (`is_precomputed_scope` → live via the discipline's
   `_*_live_where` with the Option-B inning flip + toss/result clause).
   Covers the summary chip baselines, the by-season / by-phase / by-over
   chart cohort lines, the sparkline cohort line, and the distribution-panel
   cohort chips, ×3 disciplines. The per-position/per-over MIX histogram
   stays coarse by design (Tier 2). DOM-verified in `narrowing-audit-coverage.md`.
2. ✅ **Toss wired for player values** — `player_toss_clause` peer to
   `player_result_clause`. Locked by `tests/integration/player_toss_value.sh`.
3. ~~**Team header Win% tile baseline**~~ — **DONE 2026-05-26 (3d802a2).**
   Recomputed from the Mosaic per-team-view split under the aux.
4. ~~**(Optional / product call)** opponent-only entry point on player
   pages (§D gap)~~ — **SHIPPED 2026-05-26 (45c58b7).** "Versus" typeahead
   on the 4 player pages → `filter_opponent`. The value narrows; the
   "typical player" baseline does NOT yet (that's item 1 above).

Spec/test ref: `spec-player-baseline-parity.md` §108 already REQUIRED the
cohort to narrow by every aux "identical to Teams" — this is closing the
gap between that spec and the shipped implementation. Reproduce current
state with `python3 tests/aux_param_audit.py`.
