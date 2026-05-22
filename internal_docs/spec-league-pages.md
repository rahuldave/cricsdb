# Spec: League pages — above-tournament scope dossiers

Status: SHIPPED + DEPLOYED 2026-05-13. /league route + 4 endpoints +
prose-scope H2 ("Men's primary-tier club cricket, …") + By-tier cards
on /series. 10 commits per memory `project_league_pages_shipped.md`.
Depends on: `/api/v1/scope/averages/{batting,bowling,fielding}/{summary,by-season,by-phase}` (shipped), `Series*TileRow` / `Series*ChartStrip` components shipped in `spec-series-trend-charts.md` (today). Three small new endpoints (§API).
Related: `spec-series-trend-charts.md` (the tile/chart strip pattern this page reuses), `spec-team-compare-average.md` (the `/scope/averages/*` pool-weighted-baseline pattern), `internal_docs/series-type-anchor-numbers.md` (tier definitions).

## Overview

CricsDB has destination pages for every scope BELOW tournament — `/teams/<team>` (team), `/series?tournament=X` (tournament), `/series?tournament=X&season_from=Y` (tournament-season), `/matches/<id>` (match). It has NO destination page for scopes ABOVE tournament: "men's club" (everything in the men's-club pool), "men's club, primary tier" (IPL + BBL + PSL + CPL + SA20 + ILT20 + LPL + MLC + The Hundred Men's), "men's international" (everything in men's intl), "men's international, ICC events" (T20 World Cup + Asia Cup + ...), etc.

That gap matters because:

- The `/scope/averages/*` endpoints already pool-weight at every such scope. Their consumers today are the Compare tab's avg slot, the Teams chart green-line overlay, and the Series tab's tile rows — but never as the primary subject of a page.
- When the user has the FilterBar set to "men's · club" with no team or tournament picked, there's nowhere to land that surfaces "what does cricket look like at this tier" beyond the indirect green line in someone's team page.
- Tier-level identity (which clubs are competing in this tier, who won what each season across all the marquee leagues, where the records sit) is invisible.

This spec adds **League pages** — a new route `/league` parameterized purely by FilterBar scope (gender + team_type + team_class + season range + series_type + venue, no team / tournament / opponent). The page chrome mirrors `TournamentDossier`: tabs for Overview / Batting / Bowling / Fielding. Batting/Bowling/Fielding subtabs are pure reuse of the Series-tab tile rows + chart strips shipped today. Overview is the only meaningfully new component — tier-level identity content that doesn't apply at single-tournament grain.

A natural framing: Series pages are about "what happened at this tournament across editions." League pages are about "what happened across this whole class of cricket across tournaments and editions."

## Scope

**In scope:**

- New route `/league`. Page component `LeagueDossier` mirrors `TournamentDossier` structurally — tab bar, FilterBar gating, `ScopedPageHeader`.
- Tab set: **Overview / Batting / Bowling / Fielding**. No Editions tab (no single tournament to slice by), no Partnerships tab (deferred — adds a `partnerships/by-season` page complexity that's not load-bearing for v1), no Matches tab (the existing `/matches` filtered view already covers it), no Records tab in v1 (the Overview's "biggest wins / highest totals" carries the records story for now).
- Batting/Bowling/Fielding subtabs: **direct reuse** of `SeriesBattingTileRow` + `SeriesBattingChartStrip` (and bowling/fielding equivalents) shipped today in `spec-series-trend-charts.md`. The data is already pool-weighted; the only difference is that these subtabs don't carry a player-leaderboard grid below the tiles. Player leaderboards across the pool become a sortable, paginated DataTable at the bottom of each subtab (consuming a new `/league/leaders/*` endpoint).
- New **Overview tab** content (§UX) — five blocks: headline counts strip, **Tournaments-in-scope tile grid (full reuse of `TournamentTile` from `TournamentsLanding`)**, Champions-across-(tournament, season) sortable DataTable, top teams by win %, best moments (highest totals / lowest all-outs / biggest wins / most sixes in a match).
- Three new backend endpoints (§API): `/league/champions`, `/league/leaders/{batting,bowling,fielding}`, `/league/extrema`. All accept the full `FilterParams` envelope.
- Entry points: TournamentsLanding gets a new "By tier" section with link cards for the major scope buckets above the per-tournament list. Compare tab's "Add avg slot" picker grows a link to the matching League page.

**Not in scope:**

- League Partnerships subtab — the by-season partnership trend across multiple tournaments needs a new aggregation pattern; deferred.
- League Records subtab — the v1 Overview "Biggest wins / Highest totals / Lowest all-outs" carries the records story. A full Records page (most fifties, longest winning streaks, etc.) is a follow-up.
- League Matches tab — `/matches` already supports the same FilterParams and gives the user the list view.
- Sub-tournament leaderboards (e.g. "top scorers in primary-tier club in 2024 only") — already covered by `/league/leaders/*` accepting season filters.
- SEO-friendly URL slugs (`/league/mens-club-primary` vs `/league?gender=male&team_type=club&team_class=primary_club`) — v1 ships query-params only, matching how Teams/Series/Venues work. Slug routes can be added later as 301 aliases.
- Crawl/sitemap generation for the new pages.

## Decisions (locked)

### D1. Route name — `/league`. *Locked.*

Evaluated: `/league` (most evocative for the cricket-tier framing), `/scope` (technically accurate but generic — the "scope" framing is internal jargon), `/aggregate` (engineering-flavoured, not user-facing language).

`/league` reads naturally: "what's happening in the men's club league," "show me the women's intl league across all ICC events." Crucially it's singular — there's one league page per FilterBar configuration, parameterized by FilterParams. Plural ("leagues") would imply a listing, which `TournamentsLanding` already does.

### D2. Champions display — sortable DataTable, primary view. *Locked.*

Evaluated three shapes:

- **(a) Sortable DataTable** with columns Season · Tournament · Champion · Runner-up · Margin · Scorecard. Click-to-sort flips between "season cross-section" (default, newest first) and "by tournament" (one league's history). Most flexible, most mobile-friendly, lowest visual weight.
- **(b) Per-season blocks** — mirrors Series→Editions's per-edition mini-section pattern inverted. Each season heading is followed by a row per tournament with champion + runner-up + final. Visually denser, harder to skim across seasons.
- **(c) Tournament × season matrix grid** — rows = tournaments, columns = seasons, cells = champion logo/name. Visually striking but degrades on mobile (matrix grids with N > 4 columns wrap badly) and doesn't surface runner-up / margin without hover.

Ship (a). The data source is the existing `/api/v1/series/by-season` shape, just unioned across tournaments-in-scope.

Future expansion: (c) could become an optional "expand to matrix" toggle on desktop if user demand surfaces. Out of scope here.

### D3. Player leaderboards on the discipline subtabs — paginated DataTable. *Locked.*

The Series-tab discipline subtabs render player leaderboards as a 2×2 grid (Picked-player slot + 3 sort-axis tables). Pure reuse on League pages would awkwardly host a per-LEAGUE picker that doesn't make sense (which player are you picking, scoped to all of men's club?).

For League pages: keep the 3 by-axis leaderboards (by runs / by average / by strike rate for Batting; by wickets / by economy / by strike rate for Bowling; by catches / by run-outs / by dismissals for Fielding) but drop the picker. The picked-player slot is a Series-specific feature (you're picking a player IN that tournament). At league grain the user's question shifts to "who's at the top across the pool," which the leaderboards answer directly.

Implementation: extract `<LeaderboardTriple>` from BattersTab / BowlersTab / FieldersTab (just the by-axis tables, no PickerSlot, no MosaicProvider) — narrow refactor in `TournamentDossier.tsx`. Or: write the three small tables fresh inside LeagueDossier (~50 lines each). The refactor is preferred (CLAUDE.md "Extend existing abstractions") but acceptable to ship duplicates and refactor in a follow-up if the extraction is messy.

### D4. URL hierarchy — FilterBar query-params only in v1. *Locked.*

`/league?gender=male&team_type=club&team_class=primary_club` — matching how Teams/Series/Venues work. No `/league/mens-club-primary` slug aliases in v1.

Rationale:
- Consistent with the rest of the app — no special-case routing.
- The FilterBar IS the source of truth; introducing slug aliases creates a redirect / canonical-URL surface that doesn't pay for itself until SEO becomes a priority.
- Share-link reproducibility (CLAUDE.md URL-clean rule) works the same way — copy URL, paste URL, lands on the same scope.

Follow-up: slug aliases as 301s once SEO matters; the FilterParams parse stays canonical.

### D5. Entry point — TournamentsLanding tier cards. *Locked.*

The user reaches `/league?gender=male&team_type=club` via a new "By tier" section on `TournamentsLanding`, positioned ABOVE the per-tournament list (men's franchise leagues, men's domestic leagues, women's franchise leagues sections). The new section has 4-6 cards:

- Men's club (broadest)
- Men's club · primary tier
- Men's club · secondary tier
- Men's international
- Women's club
- Women's international

Each card → link to `/league?...` with the matching FilterParams. Sub-tier-specific cards can be added once team_class becomes more granular.

Secondary entry points: the avg-slot picker on Teams Compare tab gets a "browse league page" link next to each scope option. Deferred to follow-up — out of v1 scope.

### D6. What if no FilterParams are set? — redirect to broadest. *Locked.*

Deep-linking to `/league` with no params (or only e.g. `?season_from=2024`) lands on `/league?gender=male&team_type=club` after a one-shot replace-mode URL normalisation. The page CANNOT meaningfully render with zero scope axes (the data would be "all cricket ever" — ambiguous; the UI is calibrated to a specific tier story). Default to the most-trafficked tier (men's club) and let the user re-filter.

URL-clean rule allows the redirect because `/league` with no params is non-canonical by construction.

### D7. Mosaic on League pages — defer. *Locked.*

The Splits Mosaic device is being rolled out cross-page (see `splits-mosaic-cross-page.md`, ongoing). On League pages the `result` axis = "subject won" has no obvious subject (no team, no player). Mosaic mounts deferred until the cross-page rollout has settled on a Win/Loss semantic for subjectless scopes (bat-first-won vs bat-second-won is a candidate). Track in `[[project_next_session]]`.

### D8. Tab subtitles — `abbreviateScope` everywhere. *Locked.*

Every tile, chart, and section header on League pages uses `abbreviateScope(filters, { discipline })` for the auto-subtitle exactly as today — the chart green-line overlay is irrelevant here because the PRIMARY line IS the scope average (the team-side line is absent; there is no team). All charts on League pages are single-series (no `referenceData`). Skipping the overlay keeps the chart legend clean and avoids self-comparison.

## UX

### Header

`ScopedPageHeader` with title = `abbreviateScope(filters)` (e.g. "men's · club · primary clubs · 2020–2025"). No subject team → no dormancy badge. Standard `ScopeStatusStrip` below the header surfaces the URL scope (same component the rest of the app uses).

### Overview tab

Five blocks, top-to-bottom:

```
┌──────────────────────────────────────────────────────────────┐
│  Headline strip                                              │
│  Matches · Innings · Teams · Tournaments                     │
│  (4 StatCards — counts only, no σ, no Δ)                    │
├──────────────────────────────────────────────────────────────┤
│  Tournaments in <scope> (N)                                  │
│  ┌────────────────────┐ ┌────────────────────┐ ┌──────────┐ │
│  │ Indian Premier     │ │ Pakistan Super     │ │ Big Bash │ │
│  │ League             │ │ League             │ │ League   │ │
│  │ 18 ed · 1234 mat   │ │ 9 ed · 567 mat     │ │ ...      │ │
│  │ Most titles: MI(5) │ │ Most titles: ISL(2)│ │ ...      │ │
│  │ Latest: 2025       │ │ Latest: 2024–25    │ │ ...      │ │
│  │ Winner: RCB        │ │ Winner: Islamabad  │ │ ...      │ │
│  └────────────────────┘ └────────────────────┘ └──────────┘ │
│  Grid of `wisden-tile` cards — full reuse of TournamentTile  │
│  from TournamentsLanding (canonical name + editions + matches│
│  + most titles team + latest edition + latest winner). Each  │
│  card is a SeriesLink to the tournament's all-editions page. │
├──────────────────────────────────────────────────────────────┤
│  Champions across <scope>                                    │
│  ┌────────┬──────────────┬───────────┬───────────┬────────┐ │
│  │ Season │ Tournament   │ Champion  │ Runner-up │ Final  │ │
│  ├────────┼──────────────┼───────────┼───────────┼────────┤ │
│  │ 2025   │ IPL          │ RCB       │ PBKS      │ 190/9 …│ │
│  │ 2025   │ BBL          │ Hobart    │ Sydney    │ 198/8 …│ │
│  │ 2025   │ PSL          │ Lahore    │ Multan    │ ...    │ │
│  │ 2024   │ IPL          │ KKR       │ SRH       │ ...    │ │
│  │ ...    │              │           │           │        │ │
│  └────────┴──────────────┴───────────┴───────────┴────────┘ │
│  Sortable by Season (default desc) and Tournament           │
│  Team names → TeamLink scoped to that (tournament, season)   │
├──────────────────────────────────────────────────────────────┤
│  Top teams by win %  (Top 10 teams in scope)                 │
│  ┌─────────────┬───┬───┬───┬──────┐                          │
│  │ Team        │ P │ W │ L │ Win% │                          │
│  │ Mumbai Ind. │ … │ … │ … │ 56.3 │                          │
│  │ ...                                                       │
│  └─────────────┴───┴───┴───┴──────┘                          │
├──────────────────────────────────────────────────────────────┤
│  Best moments                                                │
│  Highest total | Lowest all-out | Biggest run-margin win    │
│  | Biggest wickets-margin win | Most sixes in a match        │
│  (5 StatCards with match-link subtitles)                     │
└──────────────────────────────────────────────────────────────┘
```

The blocks fade out gracefully when empty (single-season scope with 0 finals → no Champions table renders; sparse scopes degrade to "Best moments not enough data" placeholders).

### Batting / Bowling / Fielding subtabs

Direct reuse — same tile row + chart strip as Series subtabs, sourced from `/scope/averages/{discipline}/{summary,by-season}`:

```
┌──────────────────────────────────────────────────────────────┐
│  <Series*TileRow component> — 5 tiles incl. σ on rates       │
│  (no MetricDelta vs league — this PAGE is the league;        │
│   the chip would be self-comparison)                         │
├──────────────────────────────────────────────────────────────┤
│  <Series*ChartStrip component> — 4-6 charts by season        │
│  (no `referenceData` overlay for the same reason)            │
├──────────────────────────────────────────────────────────────┤
│  Top batters/bowlers/fielders in <scope>                     │
│  ┌────────────┬─────┬───┬───┬─────┐                          │
│  │ <by runs / by wickets / by catches table>                 │
│  │ <by average / by economy / by run-outs table>             │
│  │ <by SR / by SR / by dismissals table>                     │
│  └────────────┴─────┴───┴───┴─────┘                          │
│  (paginated, 50 rows/page)                                   │
└──────────────────────────────────────────────────────────────┘
```

The tile-row + chart-strip components need a small extension: their `MetricDelta` subtitles can be conditionally suppressed when the page is the league itself (no scope-vs-league delta makes sense; you'd be comparing the pool to itself). New optional prop on the existing components — `suppressDelta?: boolean` — defaults to false (Series tab unchanged), set true by the League page caller.

### Empty / sparse scopes

- Zero matches in scope → "No matches at this scope" empty state, no tabs.
- 1 match in scope → tab bar renders, but charts hide (need ≥2 seasons), tile values render from the single-match aggregate (per-innings averages still meaningful even at N=1).
- 1 tournament in scope (e.g. `?gender=male&team_type=club&tournament=IPL`) — page redirects to `/series?tournament=IPL` since that's the more specific destination. Spec: do not maintain `/league` as a duplicate-of-Series page when a tournament is set. Replace-mode redirect.

### Mobile (390px)

Tile rows: existing `wisden-statrow.cols-5` already drops to 3+2 on narrow screens (proven on Teams and Series). Champions DataTable: standard `DataTable` mobile handling (horizontal scroll, no override). Chart strip: existing 2-up grids collapse to 1-up via existing `@media (max-width: 720px)` rules. No new mobile work for League pages — the components are mobile-tested already.

## API

### Already shipped (consume as-is)

| Endpoint | Returns | Drives |
|---|---|---|
| `/api/v1/scope/averages/batting/summary` | Per-metric flat values (per-innings averages). | League → Batting tile row. |
| `/api/v1/scope/averages/batting/by-season` | Per-season same metrics. | League → Batting chart strip. |
| `/api/v1/scope/averages/bowling/summary` + `by-season` | Same pattern for bowling. | League → Bowling subtab. |
| `/api/v1/scope/averages/fielding/summary` + `by-season` | Same for fielding. | League → Fielding subtab. |
| `/api/v1/series/landing` | `TournamentLandingEntry[]` — canonical name + editions + matches + most-titles team + latest edition + latest winner per tournament. | **League → Overview "Tournaments in <scope>" tile grid** (full reuse of `TournamentTile` from `TournamentsLanding`). Accepts FilterParams already. |
| `/api/v1/matches` | FilterParams-aware match list. | Linked from Overview's "Best moments" cards. |

### New (this spec — three endpoints)

| Endpoint | Returns | Notes |
|---|---|---|
| `/api/v1/league/overview` | `{matches, innings, teams_count, top_teams: [{team, played, wins, losses, win_pct}], best_moments: {highest_total, lowest_all_out, biggest_win_runs, biggest_win_wickets, most_sixes_match}}` | Composite call for the 3 non-tournaments, non-Champions Overview blocks (headline counts + top teams + best moments). The Tournaments tile grid uses the existing `/series/landing`; the Champions table uses its own endpoint below. Accepts full FilterParams. |
| `/api/v1/league/champions` | `{rows: [{season, tournament, champion, runner_up, final_match_id, final_score}]}` | Cross-tournament unionized version of `/series/by-season`'s champion-per-season data. Sortable on the frontend. Accepts FilterParams. |
| `/api/v1/league/leaders/{batting,bowling,fielding}` | Mirror of `/series/{discipline}-leaders` shape (`{by_runs, by_average, by_strike_rate}` etc.) but with NO tournament restriction. | Accepts the full FilterParams. Pagination support (`limit` + `offset`) since the leader pool is much larger than per-tournament. |

Each new endpoint mirrors an existing tournament-grain sibling — implementation is "drop the `WHERE m.event_name = :tournament` clause and rely on FilterParams alone." Sanity-test pattern: assert `len(rows) ≥ sum_over_tournaments_in_scope(rows_for_that_tournament)` (the unioned set is at least as large as any one tournament's slice).

### Not new

- No new `/scope/averages/*` endpoints. The discipline subtabs reuse what `spec-team-compare-average.md` shipped.
- No new tile-row / chart-strip components. The Series-tab versions extend via `suppressDelta` prop.

## Implementation order

1. **`suppressDelta` prop on Series tile/chart components** — extend `SeriesBattingTileRow` / `SeriesBowlingTileRow` / `SeriesFieldingTileRow` (and the chart strips' subtitle handling) to conditionally suppress the auto-rendered `MetricDelta` against league. Defaults to false (Series tab unchanged). Tiny diff, ships green.
2. **`/api/v1/league/overview` endpoint** — single composite payload covering Overview's 4 non-Champions blocks. Frontend type in same commit (CLAUDE.md API↔frontend contract).
3. **`/api/v1/league/champions` endpoint** — cross-tournament champions table.
4. **`/api/v1/league/leaders/{batting,bowling,fielding}` endpoints** — three sibling endpoints + frontend types.
5. **`LeagueDossier` page shell + routing** — `/league` route added to `App.tsx`. Page renders header + tab bar + empty-tab placeholders. URL-normalise-to-default effect (D6). Single-tournament redirect (UX §Empty/sparse).
6. **Overview tab content** — assemble the 5 blocks. Headline strip + Tournaments tile grid (reuse `TournamentTile` from `TournamentsLanding.tsx`, fetch from existing `/api/v1/series/landing`) + Champions DataTable + Top teams table + Best moments cards. The TournamentTile reuse may need a small extraction so the component is importable outside `TournamentsLanding` (currently a module-local function); narrow refactor — move to `components/tournaments/TournamentTile.tsx` and re-export.
7. **Batting subtab** — mount existing `SeriesBattingTileRow` + `SeriesBattingChartStrip` with `suppressDelta`; add Top batters leaderboard (3 by-axis tables, paginated).
8. **Bowling subtab** — same shape for bowling.
9. **Fielding subtab** — same shape for fielding.
10. **TournamentsLanding "By tier" cards** — 6 link cards above the per-tournament list. Each card → `/league?...` with FilterParams.
11. **Sanity + integration tests** — listed below.

Each step its own commit per CLAUDE.md commit-cadence. Steps 1-4 ship backend value before any League-page UI lands; steps 5-9 are the page build; step 10 is discoverability.

## Testing

### Sanity (SQL ↔ API)

- `test_league_overview.py` — top_teams row count ≥ 10 (or all teams if pool < 10), tournaments list matches `SELECT DISTINCT event_name FROM match WHERE …` at scope, best_moments highest_total matches max(runs) cross-checked against the existing extrema queries.
- `test_league_champions.py` — `len(rows)` equals `SELECT COUNT(DISTINCT (season, event_name)) FROM match WHERE event_stage='Final' AND outcome_winner IS NOT NULL AND <scope>`.
- `test_league_leaders.py` — top batter by_runs matches `SELECT SUM(runs_batter) FROM delivery JOIN … WHERE <scope> GROUP BY batter ORDER BY runs DESC LIMIT 1`.

### Integration (SQL-anchored DOM)

- `tests/integration/league_overview.sh` — at `/league?gender=male&team_type=club`: tournaments tile grid count matches the `/series/landing` payload's row count at scope, each tile shows canonical name + editions + matches + latest winner, top-teams row count matches SQL, biggest-win-runs match SQL.
- `tests/integration/league_champions.sh` — Champions DataTable row count matches the API's `/league/champions`; default sort is season desc; click-to-sort by Tournament re-orders.
- `tests/integration/league_batting_subtab.sh` — at `/league?...&tab=Batting`: tile values match `/scope/averages/batting/summary`; chart count ≥ 6; leaderboard top-row by_runs matches `/league/leaders/batting`.
- `tests/integration/league_single_tournament_redirect.sh` — deep-link `/league?tournament=Indian+Premier+League` redirects to `/series?tournament=Indian+Premier+League`.
- `tests/integration/league_empty_scope_redirect.sh` — deep-link `/league` (no params) redirects to `/league?gender=male&team_type=club`.

### Filter-combination matrix

Per CLAUDE.md "Filter-combination testing — the matrix is mandatory," exercise:

- `gender=male&team_type=club` (broadest male tier)
- `gender=male&team_type=club&team_class=primary_club` (tier 1 clubs)
- `gender=male&team_type=international&series_type=icc` (ICC events only)
- `gender=female&team_type=club` (women's tier)
- Above + `season_from=2024&season_to=2025` (narrowed window)
- Above + `filter_venue=Wankhede+Stadium` (venue-narrowed)

For each: tile values + chart strip + Champions table + leaderboards must all reflect the same scope SQL-anchored.

### Mobile viewport

`agent-browser set viewport 390 844` then reload at the broadest scope. Champions DataTable must scroll horizontally cleanly; tile row drops to 3+2; chart strip drops to 1-up. No new mobile work expected (all components are mobile-tested), but the matrix above runs once on 390px to lock it.

### Red-then-green

Every new endpoint + subtab gets a red-then-green pair per CLAUDE.md discipline. Notably: write the `league_champions.sh` test BEFORE the endpoint ships — assert champion count = SQL-derived expected, watch it fail with 404, then ship the endpoint, watch it pass.

## Cricket invariants (preserved)

- **DLS-truncated innings INCLUDED** — `/scope/averages/*` already handles this; League page inherits. No filter changes.
- **Catches include caught-and-bowled (Convention 3)** — fielding leaderboard consumers MUST use `kind IN ('caught', 'caught_and_bowled')`. New `/league/leaders/fielding` endpoint must honour this; its sanity test asserts via `assert_leaders_substitute_leak` algebraic identity (cross-check with `/scope/averages/fielding/summary`).
- **Substitute fielders INCLUDED in /leaders** — same rule that applies to `/fielders/leaders`. `/league/leaders/fielding` is a volume leaderboard → leave subs in.
- **Scope-anchored seasons** — `/seasons?gender=male&team_type=club` returns the seasons array filtered to the scope. League FilterBar's season quick-select reads from this (already implemented). No new work.
- **Inning aux POV** — the Batting/Bowling/Fielding subtabs honour `?inning=0/1`; `useDiscipline()` returns the right POV from `?tab=Batting` etc. on `/league`. The hook already maps tab values (`Batting/Bowling/Fielding`) → discipline (commit `af1e258`); no extension needed.

## Open follow-ups (out of v1)

- **Partnerships subtab** — per-season partnership trends across tournaments.
- **Records subtab** — fuller records pageful (most fifties, most centuries, longest winning streaks, etc.).
- **SEO slug aliases** — `/league/mens-club-primary` 301 → `/league?gender=male&team_type=club&team_class=primary_club`.
- **Splits Mosaic mounts** — defer per D7 until cross-page Win/Loss semantic settles.
- **Champions matrix view** — desktop-only "expand to matrix" toggle on the Champions table.
- **Avg-slot picker integration** — Teams Compare tab's avg-slot picker grows a "browse league page →" link next to each scope option.
- **Tier link cards on Home** — beyond `TournamentsLanding`, the Home page may want a tier-card row for immediate jump-in.
