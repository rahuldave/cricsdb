# Spec: Series — Trend charts on Batting/Bowling/Fielding subtabs, Teams pages get tournament-baseline overlay

Status: PARTIAL — main rollout SHIPPED (Teams overlay landed,
`/scope/averages/.../by-season` endpoints live, tile/chart strip
components in use). **D3 (phase × season heatmaps on Series) explicitly
DEFERRED** — needs two new endpoints + a heatmap component.
Depends on: `/api/v1/scope/averages/{batting,bowling,fielding}/{summary,by-season,by-phase}` (already shipped — `scope_averages.py`). One small API addition: a `boundaries_conceded` MetricEnvelope on `/teams/{t}/bowling/summary` and its `/scope/averages` sibling (§API). One new endpoint pair deferred for D3 phase × season heatmaps.
Related: `spec-team-compare-average.md` (established the `/scope/averages/*` pool-weighted-baseline pattern that this spec consumes), `spec-team-stats.md`.

## Overview

Series Overview today carries two line charts — **Run rate by season** and **Boundary % by season** — that hide when `trend.length === 1` (i.e. a single edition is in scope). That's the only by-season visualisation on the Series tab; everything else on Overview is text-and-tiles. The Batters / Bowlers / Fielders subtabs are pure player leaderboards (picker + by-runs / avg / SR tables).

Two things are wrong with this:

1. **Overview is the wrong home for these charts.** They're discipline-specific (batting metrics), and the Overview's mental model is "what happened across the tournament, briefly." A run-rate trend belongs under the batting story, not the meta-summary.
2. **There's only batting representation.** Bowling and fielding trends across editions don't exist anywhere on the Series tab — yet the data layer already has them (`/scope/averages/bowling/by-season`, `/scope/averages/fielding/by-season` ship today).

This spec moves the two existing Overview charts to a new **Series → Batting** subtab and adds the matching Bowling and Fielding subtabs, each carrying the same density of season-trajectory charts that already lives on **Teams → Batting/Bowling/Fielding** (`pages/Teams.tsx`:758-826, 961-1019, 1139-1160).

A natural consequence: the per-season aggregate that Series tabs plot **is** the pool-weighted baseline a team competing in that tournament should be measured against. So Teams batting/bowling/fielding charts gain an opt-in **tournament-baseline overlay line** (only when `filters.tournament` is set) — driven by exactly the same data the Series subtabs render. One dataset, two surfaces.

A separate observation that frames the layout: on **Teams → Batting** today with a single-season scope (`pages/Teams.tsx:680-840`), the tab is not empty — the distribution panel, 15 scalar tiles with delta-vs-league subtitles, phase bars, inning bands, and Top 5 Batters all still render. What hides is just the by-season chart strip and the phase × season heatmaps (both guarded by `seasons.length >= 2`). The tile row IS the single-season story; the chart strip is the multi-season story. This spec mirrors that pattern on Series subtabs (which today have no per-discipline tile row at all) and **extends both sets of pages** to surface across-season dispersion on the tiles via inline std-dev for rate/average metrics.

## Scope

**In scope (Series tab):**

- Rename Series subtabs `Batters` → `Batting`, `Bowlers` → `Bowling`, `Fielders` → `Fielding` (URL aliases for back-compat — old `?tab=Batters` redirects).
- Move Overview's two LineCharts (`run_rate`, `boundary_pct` by season) into the new Batting subtab.
- Retire the `trend.length > 1` hide-on-single-season block from Overview entirely.
- Add a **tile row** at the top of each new Series subtab (Batting, Bowling, Fielding) — mirrors the corresponding Teams tile row 1:1 plus the two new tiles added by this spec (see Teams scope below). Source: `/api/v1/scope/averages/{discipline}/summary?tournament=X` (already shipped). **Always renders, regardless of N.**
- Add a full chart strip below the tile row on each Series subtab — list in §UX. Source: `/api/v1/scope/averages/{discipline}/by-season?tournament=X` (already shipped). **Hides when seasons-in-scope < 2**, matching the Teams pattern.
- Player leaderboard sections on the renamed Series subtabs **stay where they are** — the new tile row + chart strip render above them. Picker slot stays the top-left grid cell.

**In scope (Teams tab):**

- Add **two new tiles** to plug the existing chart-axis-without-tile gaps:
  - Teams → Bowling: new `Boundaries conceded` tile (counterpart to the bar chart at `pages/Teams.tsx:975`).
  - Teams → Fielding: new `Total dismissals` tile (counterpart to the line chart at `pages/Teams.tsx:1141`).
- Add **inline std-dev across in-scope seasons** to every rate/average tile on both Teams and Series tile rows (rule table in §Tile composition). Volume tiles and extremum tiles get no std (§Decisions D4).
- Add tournament-baseline overlay on **every existing per-season chart on Teams → Batting/Bowling/Fielding** when `filters.tournament` is non-empty. Driven by the same `/scope/averages/{discipline}/by-season` payload, no extra Teams-side API.

**Not in scope:**

- New trend metrics that don't exist on Teams pages today (e.g. "false-shot %", "expected RR"). Mirror what Teams already has; widening the catalogue is a separate spec.
- Phase × season heatmaps on Series (deferred per D3) — needs two new `/scope/averages/.../phase-season-heatmap` endpoints; ship line-chart strip first and revisit.
- Partnerships subtab — already has dedicated `partnerships/by-wicket` and heatmap content; no need to add a by-season trend here unless a follow-up surfaces demand.
- Cross-tournament comparison (IPL vs CPL run-rate side-by-side) — out of scope; that's `outlook-comparisons.md` territory.
- Player-leaderboard restructuring inside Batting/Bowling/Fielding subtabs.
- Std-dev on volume tiles (Runs, 4s, 6s, Wickets, Catches, etc.) and extremum tiles (Highest total, Lowest all-out, Worst conceded, Best defence) — see D4.

## Decisions (locked)

### D1. Single-season collapse — mirror the Teams pattern. *Locked.*

Teams → Batting/Bowling/Fielding already handles this cleanly today: tile rows always render with the in-scope value + delta-vs-league subtitle; chart blocks hide on `seasons.length < 2`. Single-season scope is not an empty tab — the distribution panel, ~15 tiles, phase bars, inning bands, and Top-5 tables all still render.

This spec adopts the same pattern on Series subtabs. The earlier "stat strip with mean ± std above each chart" idea is dropped in favour of putting std on the tiles themselves (see D4).

### D2. Subtab rename — Batters → Batting. *Locked.*

`Batters / Bowlers / Fielders` → `Batting / Bowling / Fielding`. URL `?tab=Batters` aliases to `?tab=Batting` in `TournamentDossier.tsx`'s currentTab resolution so deep-links don't break. Picker URL keys (`batter` / `bowler` / `fielder`) stay unchanged.

### D3. Phase × season heatmaps on Series subtabs — defer. *Locked.*

Out of scope here. Ship line-chart strips first; revisit heatmaps in a follow-up once the tab has been used. When revisited: `/scope/averages/batting/phase-season-heatmap` + bowling sibling (mirror of `teams.py:2942` and `:4325` with the team filter stripped).

### D4. Std-dev applicability per tile class. *Locked.*

Three tile classes, three rules:

- **Rates / per-match averages** — inline std on the value: `8.21 ± 0.34`. Examples: Run rate, Boundary %, Dot %, Avg innings total, Economy, Bowling Average, Bowling SR, Avg opp total, Wides/match, Catches/match, Stumpings/match, Run-outs/match, Catches per match (Fielding chart equivalent).
- **Volume counts** — no std. Headline is a sum across the scope, not a per-season mean. Examples: Runs, 4s, 6s, 50s, 100s, Wickets, Runs conceded, Catches, Stumpings, Run-outs, C&B, Boundaries conceded (new), Total dismissals (new). Across-season dispersion for these is read off the bar chart when N≥2.
- **Extrema** — no std. Single-observation cells; std of season-maxes is a weird stat. Examples: Highest total, Lowest all-out, Worst conceded, Best defence.

Std is hidden when N=1 (a single season has no spread). When N≥2, std is computed client-side from the matching `/scope/averages/{discipline}/by-season` (Series) or `/teams/{team}/{discipline}/by-season` (Teams) payload — same fetch the chart strip already needs.

Rendering: `value ± std` on the tile's headline line, replacing the bare value. Delta-vs-league `MetricDelta` stays on its own subtitle line below. So a Run rate tile becomes:

```
Run rate
 8.21 ± 0.34
 +0.32 vs league
```

instead of today's:

```
Run rate
 8.21
 +0.32 vs league
```

## UX

### Series → Overview (after)

Strict reduction. Today's structure:
- Headline tiles (matches, editions, champions, etc.)
- "Best moments" strip
- Teams chip row
- → **2 LineCharts (run_rate / boundary_pct by season) — REMOVED**
- Per-team breakdown (rivalry)
- Champions-by-season chart (KEEP — this one IS overview-y; it's about identity, not metrics)
- Mini per-edition sections

The removed block frees ~600px of vertical space — Overview becomes tighter.

### Series → Batting (new tile row + chart strip above existing leaderboards)

```
[ Tile row 1 (5-up): Innings · Runs · Run rate ± σ · Boundary % ± σ · Dot % ± σ ]
[ Tile row 2 (5-up): 4s · 6s · 50s · 100s · 50s/100s per inn ± σ ]
[ Tile row 3 (5-up): Avg 1st-inn total ± σ · Avg 2nd-inn total ± σ · Highest total · Lowest all-out · Avg innings total ± σ ]

──── (the chart strip below hides on N<2) ────
[ LineChart: Run rate by season ]   [ LineChart: Avg innings total by season ]
[ BarChart: Fours by season ]       [ BarChart: Sixes by season ]
[ LineChart: Boundary % by season ] [ LineChart: Dot % by season ]
[ BarChart: Run rate by phase ]     [ BarChart: Wickets lost per innings by phase ]

(existing) Picker slot · By runs · By average · By strike rate
```

Tile row mirrors Teams → Batting (`pages/Teams.tsx:700-751`) 1:1 — same 15-tile layout. Chart strip mirrors `pages/Teams.tsx:755-793` 1:1.

Single-season scope: tile row stays (std hidden); all chart blocks hide; leaderboards still render. By-phase bar charts use the `phases.length > 0` guard like Teams does, so they also still render on single-season scope.

### Series → Bowling (new tile row + chart strip)

```
[ Tile row 1: Innings · Overs · Wickets · Runs conceded ]
[ Tile row 2: Economy ± σ · Average ± σ · Strike rate ± σ · Dot % ± σ ]
[ Tile row 3: Avg opp total ± σ · Worst conceded · Best defence · Wides/match ± σ · Boundaries conceded (NEW) ]

──── (the chart strip below hides on N<2) ────
[ LineChart: Economy by season ]            [ LineChart: Avg opposition total by season ]
[ BarChart: Wickets by season ]             [ BarChart: Runs conceded by season ]
[ LineChart: Dot % by season ]              [ BarChart: Boundaries conceded by season ]
[ BarChart: Economy by phase ]              [ BarChart: Boundaries conceded by phase ]

(existing) Picker slot · By wickets · By economy · By strike rate
```

Mirrors `pages/Teams.tsx:913-1019`. The `Boundaries conceded` tile is new on **both** Teams and Series Bowling (closes the existing chart-axis-without-tile gap at `:975`).

### Series → Fielding (new tile row + chart strip)

```
[ Tile row 1: Matches · Catches · Stumpings · Run-outs ]
[ Tile row 2: Catches/match ± σ · Stumpings/match ± σ · Run-outs/match ± σ · C&B · Total dismissals (NEW) ]

──── (the chart strip below hides on N<2) ────
[ LineChart: Catches per match by season ]  [ LineChart: Total dismissals by season ]
[ BarChart: Catches by season ]             [ BarChart: Run outs by season ]

(existing) Picker slot · Fielders by catches · By run-outs · By dismissals
```

Mirrors `pages/Teams.tsx:1111-1151`. The `Total dismissals` tile is new on **both** Teams and Series Fielding (closes the chart-axis-without-tile gap at `:1141`).

### Teams → Batting/Bowling/Fielding (two changes)

1. **Tile-row enrichment** — same tile rows as today **plus** the inline std-dev on rate/average tiles (D4) **plus** the two new tiles (`Boundaries conceded` on Bowling, `Total dismissals` on Fielding). Std is hidden on N=1; visible as `value ± σ` on N≥2.
2. **Scope-baseline overlay on rate LineCharts** — every rate-rate chart in `BattingTab` / `BowlingTab` / `FieldingTab` gains a second series at **every scope**: the pool-weighted by-season baseline (the same `scope_avg` source the chip-deltas above the chart already use), rendered as a forest-green reference overlay (`internal_docs/colors.md` reserves forest for league-avg reference lines). With `tournament=IPL` the legend reads "men's · Indian Premier League avg"; without it, "men's · club avg" — `abbreviateScope` derives the label so the legend always identifies the exact pool.

Implementation: extend `LineChart` with three narrow props — `referenceData`, `referenceLabel` (optional; auto-derived from `abbreviateScope(filters, { discipline }) + " avg"` when omitted), and `primaryLabel` for the team-side legend entry. When both `data` and `referenceData` are passed and `lineBy` isn't set, the component combines them into a `_series`-tagged array. `lineBy` callers (SeasonTrajectoryStrip, WormChart) keep their existing multi-series behavior.

BarCharts are trickier — proposal: render the baseline as a small horizontal reference line at each season-x position, not a second bar. Decide concretely during the overlay commit. (Deferred in the current commit.)

Why always-on (not tournament-gated): the chip deltas on the tile row above already compare against the same pool-weighted `scope_avg` at every scope — gating the chart visualisation differently from the chip would create an asymmetry where the number tells you the delta but the chart doesn't show what's being subtracted. Overlay hides only when the team has 0/1 seasons in scope (no chart drawn anyway).

## Tile composition (std-dev rules per D4)

Reference table for every tile on every affected page. `σ` = inline std-dev across in-scope seasons (N≥2). `Δ` = existing `MetricDelta` subtitle line (`±delta vs league scope_avg`).

### Batting (Teams + Series)

| Tile | Class | Std? | Delta line? |
|---|---|---|---|
| Innings | volume | — | — |
| Runs | volume | — | — |
| Run rate | rate | σ | Δ |
| Boundary % | rate | σ | Δ |
| Dot % | rate | σ | Δ |
| 4s / 6s | volume | — | — |
| 50s / 100s | volume | — | — |
| 50s/100s per inn | rate | σ | — |
| Avg 1st-inn total | rate | σ | Δ |
| Avg 2nd-inn total | rate | σ | Δ |
| Highest total | extremum | — | — |
| Lowest all-out | extremum | — | — |
| Avg innings total | rate | σ | Δ |

### Bowling (Teams + Series)

| Tile | Class | Std? | Delta line? |
|---|---|---|---|
| Innings | volume | — | — |
| Overs | volume | — | — |
| Wickets | volume | — | — |
| Runs conceded | volume | — | — |
| Economy | rate | σ | Δ |
| Average | rate | σ | Δ |
| Strike rate | rate | σ | Δ |
| Dot % | rate | σ | Δ |
| Avg opp total | rate | σ | Δ |
| Worst conceded | extremum | — | — |
| Best defence | extremum | — | — |
| Wides/match | rate | σ | Δ |
| Boundaries conceded (NEW) | volume | — | — |

### Fielding (Teams + Series)

| Tile | Class | Std? | Delta line? |
|---|---|---|---|
| Matches | volume | — | — |
| Catches | volume | — | — |
| Stumpings | volume | — | — |
| Run-outs | volume | — | — |
| Catches/match | rate | σ | Δ |
| Stumpings/match | rate | σ | Δ |
| Run-outs/match | rate | σ | Δ |
| C&B | volume | — | — |
| Total dismissals (NEW) | volume | — | — |

The "no Δ" cases on volume + extremum tiles match what's already on Teams today — this spec doesn't add delta-vs-league to tiles that lacked it.

## API

### Already shipped (consume as-is)

| Endpoint | Returns | Drives |
|---|---|---|
| `/api/v1/scope/averages/batting/summary?tournament=X` | Per-metric MetricEnvelope. | Series → Batting tile row. |
| `/api/v1/scope/averages/bowling/summary?tournament=X` | Per-metric MetricEnvelope. | Series → Bowling tile row. **Needs one new field — see below.** |
| `/api/v1/scope/averages/fielding/summary?tournament=X` | Per-metric MetricEnvelope incl. `total_dismissals_contributed`. | Series → Fielding tile row. |
| `/api/v1/scope/averages/batting/by-season?tournament=X` | `{by_season: [{season, run_rate, boundary_pct, dot_pct, fours, sixes, ...}]}`. | Series → Batting charts + Teams overlay + tile std-dev source. |
| `/api/v1/scope/averages/bowling/by-season?tournament=X` | Same shape, bowling metrics (incl. `boundaries_conceded`). | Series → Bowling charts + Teams overlay + tile std-dev source. |
| `/api/v1/scope/averages/fielding/by-season?tournament=X` | catches_per_match, total_dismissals_contributed, etc. | Series → Fielding charts + Teams overlay + tile std-dev source. |
| `/api/v1/scope/averages/batting/by-phase?tournament=X` | Per-phase aggregate (PP / Middle / Death). | Series → Batting by-phase bar charts. |
| `/api/v1/scope/averages/bowling/by-phase?tournament=X` | Same. | Series → Bowling by-phase bar charts. |
| `/teams/{team}/bowling/summary` | Existing per-metric envelope. | Teams → Bowling tile row. **Needs one new field — see below.** |

All accept the full FilterParams envelope, so they respect `gender`, `team_type`, `season_from/to`, etc. consistently with the rest of the app.

### New (small additions)

| Change | Where | Notes |
|---|---|---|
| Add `boundaries_conceded` to `_compute_bowling_summary` MetricEnvelope. | `api/routers/teams.py:3320` (and the matching `/scope/averages/bowling/summary` builder in `scope_averages.py`). | The aggregate already computes `fours_conceded + sixes_conceded` upstream — add one `wrap_metric(...)` line. Otherwise the new Bowling tile has no scope_avg delta. |

### Deferred (D3)

| Endpoint | Notes |
|---|---|
| `/api/v1/scope/averages/batting/phase-season-heatmap` | Mirror of `teams.py:2942` with team filter stripped. Ship in follow-up if/when Series subtabs grow heatmaps. |
| `/api/v1/scope/averages/bowling/phase-season-heatmap` | Mirror of `teams.py:4325`. Same condition. |

### Retired (cleanup)

`/series/by-season`'s `run_rate` / `boundary_pct` / `total_sixes` fields are no longer consumed by Overview after the move. Two options:
- Keep them; they're cheap.
- Drop them and rely on `/scope/averages/batting/by-season` everywhere.

**Recommendation: keep them.** The Editions tab still renders `by_season` rows; pruning fields would force a separate cleanup pass. Mark in `docs-sync.md` that the Overview chart consumers moved.

## Implementation order

1. **`boundaries_conceded` MetricEnvelope** — add to `_compute_bowling_summary` in `teams.py` + the matching builder in `scope_averages.py`. Update `TeamBowlingSummary` TypeScript type in same commit (CLAUDE.md "API ↔ frontend type contract"). Unblocks the new Bowling tile on both tabs.
2. **`StatCard` std-dev support** — narrow extension to `StatCard` to render inline `value ± σ` on the headline line when an optional `stdDev` prop is set. Don't fork a `StatCardWithStd`. Threshold for showing σ: N≥2 (`stdDev=null` hides it).
3. **Teams → Bowling tile change** — add the `Boundaries conceded` tile to row 3 + wire `bySeason` to compute std for each rate tile and pass to `StatCard`. Single commit; visible win on Teams without touching Series yet.
4. **Teams → Fielding tile change** — add `Total dismissals` tile (use existing envelope) + std wiring. Single commit.
5. **Teams → Batting tile std wiring** — no new tiles; just wire std for the 6 rate tiles. Single commit.
6. **Series subtab rename + URL alias** — rename `Batters/Bowlers/Fielders` → `Batting/Bowling/Fielding` in `BASE_TABS`, add the `?tab=Batters` alias in `currentTab` resolution. Single commit, no content changes yet.
7. **Series → Batting subtab rebuild** — fetch `/scope/averages/batting/summary` + `by-season` + `by-phase`, render 3 tile rows (mirror Teams) above existing leaderboards, render 8 chart blocks below (hide on N<2). Move the two existing Overview charts here.
8. **Series → Bowling subtab additions** — tile rows + chart strip above existing leaderboards. Same shape as step 7.
9. **Series → Fielding subtab additions** — tile rows + chart strip above existing leaderboards.
10. **Series → Overview cleanup** — delete the 2 LineCharts (`run_rate` / `boundary_pct` by season). Update tests/integration that reference them.
11. **Teams chart tournament-baseline overlay** — extend `LineChart` (and `BarChart` strategy per §UX) with a `referenceData` prop; wire each Teams tab to fetch `/scope/averages/{discipline}/by-season?tournament=X` when `filters.tournament` is set, pass to charts. Hidden otherwise.
12. **(deferred / D3)** — phase × season heatmap endpoints + Series subtab heatmaps.

Each step is its own commit per the commit-cadence rule. Steps 1-5 ship visible value on Teams without touching Series; steps 6-10 are the Series rebuild; step 11 closes the loop.

## Testing

Per the integration discipline (CLAUDE.md):

- **SQL-anchored**: every chart-bar count and tile std anchors against `sqlite3 cricket.db`. For Series subtabs, the canonical API anchor is `/scope/averages/{discipline}/by-season` and `/summary` — fetch the API JSON, compare DOM-rendered values/std to the API payload (NOT re-derived SQL — feedback memory: "Integration tests anchor against `/summary`'s scope_avg, not re-derived SQL"). The std assertion is `round(stddev(by_season.map(s => s.run_rate)), 2)` vs the rendered `± σ` text.
- **Tile std rule by class**: assert rate tiles show `± σ` for N≥2; assert volume + extremum tiles do NOT show `± σ` regardless of N (lock D4).
- **Tile rendering on N=1**: deep-link a single-season scope; assert every rate tile shows the value with no `± σ`, every volume tile shows the total, no chart renders.
- **New tile presence**: assert `Boundaries conceded` tile renders on Teams → Bowling (and Series → Bowling); assert `Total dismissals` tile renders on Teams → Fielding (and Series → Fielding) — both at default scope and at `?tournament=IPL`.
- **Every call site for tournament overlay**: Teams overlay touches 3 tabs × 6-8 charts each. Test must exercise each chart with `filters.tournament=IPL` and assert the baseline-line exists in the DOM (and is absent without `tournament`).
- **Mobile viewport**: 6-chart grids on the new Series subtabs must reflow on 390px. `wisden-chart-grid` class with `@media (max-width: 720px) { grid-template-columns: 1fr }` per the codebase idiom.
- **Tab-rename URL alias**: deep-link `?tab=Batters` lands on Batting subtab without an extra history entry.
- **Filter-combination matrix**: tile std + chart strip exercised at `team=X`, `team=X&filter_venue=Y`, `team=X&tournament=Z`, `team=X&tournament=Z&toss_outcome=won`, and bowling-tab `inning=0/1` flip — per the CLAUDE.md matrix mandate.

## Cricket invariants to respect

- **DLS-truncated innings**: per-innings denominators (avg_innings_total) must use real innings counts; overs denominators use real legal-ball counts. `/scope/averages/*/by-season` already does this — no per-chart override needed.
- **Catches include C&B (Convention 3)**: `/scope/averages/fielding/by-season` already applies the inclusive predicate; the new Fielding charts inherit.
- **Substitute fielders INCLUDED for volume / EXCLUDED for per-match**: catches-by-season is volume (subs in); catches-per-match is rate (subs out). `/scope/averages/fielding/by-season` already handles this asymmetry — verify before consuming.
