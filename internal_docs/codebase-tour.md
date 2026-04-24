# Codebase tour

Full file-by-file overview. The short "entry points" cheat-sheet
lives in `CLAUDE.md`; this file is the long version.

## Backend (Python, FastAPI, deebase)

```
api/
  app.py              — FastAPI app, CORS, admin, SPA fallback (registered in lifespan after routers).
                         docs_url/redoc_url/openapi_url overridden to /api/docs, /api/redoc, /api/openapi.json
                         so the Vite dev-server proxy forwards them.
  dependencies.py     — Database init (WAL mode, PLASH_PRODUCTION-aware path)
  filters.py          — FilterBarParams (8 FilterBar UI fields) + AuxParams (page-local;
                          currently series_type) classes for FastAPI Depends().
                          FilterBarParams.build(aux=aux) threads aux clauses centrally so
                          routers don't hand-wire series_type_clause individually. FilterParams
                          alias preserved for incremental migration. See
                          internal_docs/design-decisions.md "FilterBarParams + AuxParams".
  routers/
    reference.py      — /api/v1/tournaments (FilterBar dropdown; canonicalized,
                         accepts team + opponent for rivalry-pair intersection),
                         /seasons, /teams, /players
    teams.py          — /api/v1/teams/landing (two-column directory, filter-sensitive)
                         /api/v1/teams/{team}/summary|results|vs/{opponent}|by-season
                         /api/v1/teams/{team}/players-by-season (roster + bat avg + bowl SR + turnover)
                         plus batting/bowling/fielding/partnerships endpoints + opponents-matrix
    batting.py        — /api/v1/batters/leaders (top 10 by avg + by SR, filter-sensitive)
                         /api/v1/batters/{id}/summary|by-innings|vs-bowlers|by-over|by-phase|by-season|dismissals|inter-wicket
    bowling.py        — /api/v1/bowlers/leaders (top 10 by SR + by economy, filter-sensitive)
                         /api/v1/bowlers/{id}/summary|by-innings|vs-batters|by-over|by-phase|by-season|wickets
    fielding.py       — /api/v1/fielders/leaders (top 10 fielders + top 10 keepers, volume-based)
                         /api/v1/fielders/{id}/summary|by-season|by-phase|by-over|dismissal-types|victims|by-innings
    keeping.py        — /api/v1/fielders/{id}/keeping/summary|by-season|by-innings|ambiguous (Tier 2)
    head_to_head.py   — /api/v1/head-to-head/{batter_id}/{bowler_id}
    matches.py        — /api/v1/matches list, /matches/{id}/scorecard, /matches/{id}/innings-grid
    tournaments.py    — Series catalog + match-set dossier (enhancement M).
                         Router renamed /tournaments/* → /series/* on 2026-04-16
                          to disambiguate from FilterBar's "Tournament" dropdown;
                          file name kept to preserve git blame.
                         /api/v1/series/landing (sectioned: ICC events, men's + women's
                          bilateral-rivalry tiles bilateral-only, club leagues, other)
                         /api/v1/series/{summary,by-season,records,
                          batters-leaders,bowlers-leaders,fielders-leaders,
                          batter-scope-stats,
                          partnerships/by-wicket,partnerships/top,partnerships/heatmap}
                         — all accept optional tournament + series_type
                          (all/bilateral_only/tournament_only) + filter_team/filter_opponent.
                          Leaders rows carry `team` (dominant side) so rivalry-dossier
                          context links flip filter_team/filter_opponent per row.
                          Summary returns by_team per-team breakdowns when team-pair set.
                         /api/v1/series/batter-scope-stats (person_id + same scope
                          params) returns one BattingLeaderEntry row for the picked
                          player, or {entry:null} if out of scope — backs the Series
                          > Batters "Picked batter" tile. /api/v1/series/bowler-scope-stats
                          and /api/v1/series/fielder-scope-stats are the siblings for
                          the Bowlers / Fielders pickers.
                         /api/v1/series/points-table (single-season; tournament required)
                         /api/v1/series/other-rivalries (lazy-load expander)
                         /api/v1/rivalries/summary (legacy; new code uses dossier endpoints)
    venues.py         — Venues Phase 2. /api/v1/venues (typeahead; q substring match
                         on venue OR city + standard FilterParams; top-50 when q absent)
                         and /api/v1/venues/landing (country-grouped tile grid). Both
                         strip filter_venue from their own filter chain (self-
                         referential).
tournament_canonical.py — Shared canonical map (T20 WC variants → "T20 World Cup (Men)" etc.)
                         imported by filters.py + tournaments.py + reference.py for global
                         IN-variants expansion of tournament=X queries.
models/tables.py      — deebase models: Person, Match, Innings, Delivery, Wicket,
                        FieldingCredit, KeeperAssignment, Partnership
team_aliases.py       — Canonical team-name mapping (used by import + fix script)
event_aliases.py      — Canonical tournament-name mapping (same pattern as team_aliases)
fielder_aliases.py    — Canonical fielder-name mapping (married names, disambiguated names)
api/venue_aliases.py  — Canonical venue mapping: (raw_venue, raw_city) → (canonical_venue, canonical_city, country).
                        676 raw pairs → 456 canonical venues. Generated from docs/venue-worklist/2026-04-17-worklist.csv.
```

## Scripts

```
scripts/fix_team_names.py             — One-time UPDATE pass to canonicalize old team names in cricket.db
scripts/fix_event_names.py            — Same for tournament names (match.event_name)
scripts/fix_venue_names.py            — Same for venues: canonicalizes match.venue / city + fills match.venue_country via api/venue_aliases.resolve_or_raw. Idempotent.
scripts/generate_venue_worklist.py    — Emits docs/venue-worklist/YYYY-MM-DD-worklist.csv for human review when new unknown venues appear in cricsheet data.
scripts/sweep_venue_punctuation_collisions.py — Scans api/venue_aliases.py for canonical-vs-canonical collisions that only differ by punctuation (dots, commas, hyphens, whitespace). Run it after big incremental imports. Prints merge-candidate groups with match counts; doesn't modify anything — human resolves by editing api/venue_aliases.py + rerunning fix_venue_names.py.
scripts/populate_fielding_credits.py  — Builds fielding_credit table (auto-called by import + update pipelines)
scripts/populate_keeper_assignments.py — Builds keeper_assignment table + writes ambiguous worklist partitions (auto on import + update)
scripts/apply_keeper_resolutions.py   — Applies manual resolutions from docs/keeper-ambiguous/*.csv back into the DB
scripts/populate_partnerships.py      — Builds partnership table (auto on import + update)
scripts/populate_player_scope_stats.py — Builds player_scope_stats table — denormalized per-(person, scope_key) aggregates. Built but NOT consumed by any endpoint in Spec 1 of internal_docs/spec-team-compare-average.md; exists as Path-A infrastructure for Spec 2 (internal_docs/outlook-comparisons.md). Auto on import + update.
```

Sanity / data-layer tests live in `tests/sanity/` (separate from
`tests/regression/` URL md5-diff and `tests/integration/`
agent-browser flows). One per denormalized table; assert
pool-conservation + populate_full ↔ populate_incremental
round-trip. Run after any change to a populate script.

## Pipelines

```
download_data.py      — Fetches cricsheet zips + people/names CSVs
import_data.py        — Full rebuild: downloads + imports into SQLite
                        (canonicalizes via team_aliases + event_aliases + venue_aliases
                         [soft-fail — unknown venues logged to docs/venue-worklist/unknowns-<date>.csv],
                         populates fielding_credit + keeper_assignment + partnership + player_scope_stats)
update_recent.py      — Incremental: imports new T20 matches + re-runs
                        all populate_* scripts on just those matches.
                        Same venue canonicalization + unknown-logging hook as import_data.py.
```

## Frontend (React 19 + TypeScript + Tailwind v4 + Semiotic v3)

```
frontend/src/
  App.tsx                      — React Router: /, /teams, /players, /batting, /bowling,
                                   /fielding, /series, /head-to-head, /matches,
                                   /matches/:matchId. /tournaments → /series redirect preserves
                                   old deep links.
  api.ts                       — fetchApi<T> wrapper + all endpoint clients, including
                                   getPlayerProfile (composes 4 summary fetches in parallel
                                   for the /players tab; .catch-to-null per discipline so a
                                   specialist's missing row doesn't blow up the page)
  types.ts                     — All request/response interfaces
  index.css                    — Wisden editorial styles (cream, oxblood, Fraunces/Inter Tight,
                                   .wisden-page-title, .wisden-section-title, .wisden-statrow,
                                   .wisden-table, .wisden-tabs, etc.)
  hooks/useUrlState.ts         — useUrlParam + useSetUrlParams (atomic URL state updates)
  hooks/useFetch.ts            — { data, loading, error, refetch } wrapper around an async fn
  hooks/useContainerWidth.ts   — ResizeObserver wrapper used by responsive chart wrappers
  hooks/useDefaultSeasonWindow.ts — Batting/Bowling/Fielding landings auto-default to last 3
                                    seasons in scope when no season filter is set (one-shot
                                    per mount via useRef). Writes to URL so FilterBar reflects.
  components/                  — Layout (now hosts a Players ▾ group with desktop hover-dropdown
                                   + persistent mobile sub-row while any /players, /batting,
                                   /bowling, /fielding route is active; mounts FilterBar +
                                   ScopeStatusStrip below it on every non-home, non-scorecard,
                                   non-help route), FilterBar, PlayerSearch
                                   (role prop optional; `scope` prop passes FilterBar + aux
                                   through to the server so the Series-tab discipline pickers
                                   exclude players with no data in the current match-set —
                                   e.g. "AB" on T20 WC Men 2022-2026 won't surface de Villiers),
                                   TeamSearch, StatCard, DataTable, Spinner, ErrorBanner,
                                   Scorecard, InningsCard,
                                   PlayerLink + TeamLink (unified phrase-subscript model: name
                                   link = all-time identity; named-phrase subscripts driven by
                                   series_type container resolution. Both components take the
                                   same prop surface — subscriptSource (per-row override),
                                   keepRivalry, team_type, seriesType, maxTiers, phraseLabel
                                   (string or function that replaces rendered phrase text while
                                   keeping the computed href, used for compact "ed" tokens),
                                   phraseClassName (e.g. "scope-phrase-ed" for small-caps
                                   styling); layout inline|block, compact mode for H2 / tile
                                   headers — see internal_docs/design-decisions.md),
                                   Score (compact two-score renderer "185/6 │ 180/5" with muted
                                   U+2502 separator; optional matchId makes the whole score a
                                   scorecard link. Used on Matches tab, Records Final, Champions
                                   by season Final, Knockouts Date+Score cells),
                                   EdHelp (small italic-serif caption explaining the per-row
                                   "ed" subscript — mounted above any DataTable whose columns
                                   carry TeamLink phraseLabel="ed"),
                                   SeriesLink (thin Link wrapper that builds /series?... URLs
                                   from an explicit scope spec — tournament, season, seriesType,
                                   team1, team2, gender, team_type, filter_venue. Used by tile
                                   stretched-link primaries, innings-list tournament cells,
                                   TournamentDossier by-season rows),
                                   ScopeStatusStrip (one-line read-mode mirror of active filters
                                   below the FilterBar; SHOWING: GENDER/TYPE/TOURNAMENT/TEAM/...
                                   prose summary + COPY LINK clipboard button; surfaces aux
                                   filter series_type as "Show: bilateral T20Is" etc. on every
                                   tab where it's set),
                                   ScopeIndicator (oxblood pill for filter_team/_opponent
                                   lens on player pages — narrowing-announcement banner, not
                                   the same as ScopeStatusStrip), FlagBadge,
                                   scopeLinks.ts (shared PlayerLink/TeamLink model: FILTER_KEYS
                                   registry, ScopeContext for path identity, nameParams +
                                   resolveScopePhrases — series_type-driven container
                                   resolution; seasonTag helper for "2024" / "2023–2024"
                                   range formatting), charts/
    charts/                    — BarChart, LineChart, ScatterChart, DonutChart wrappers (responsive),
                                   HeatmapChart, BubbleMatrix,
                                   WormChart, ManhattanChart, InningsGridChart, MatchupGridChart
    tournaments/               — TournamentsLanding (sectioned grids + men's/women's rivalry tiles),
                                   TournamentDossier (shared dossier UI for tournament OR rivalry
                                   scope; reused by HeadToHead Team-vs-Team mode)
    players/                   — Players tab (R) internals:
                                   PlayerProfile         single-player layout
                                   PlayerSummaryRow      one discipline band (batting/bowling/
                                                          fielding/keeping), compact mode for
                                                          narrow compare columns
                                   PlayerCompareGrid     N-column side-by-side grid, fixed-arity
                                                          useFetch slots, aligned placeholder bands
                                   PlayerCompareColumn   inlined in PlayerCompareGrid as CompareColumn
                                   AddComparePicker      "+ Add another player to compare" input
                                                          with cross-gender add rejection
                                   PlayersLanding        curated profile tiles + compare pair tiles
                                   CuratedLists.ts       PROFILE_MEN / PROFILE_WOMEN /
                                                          COMPARE_MEN / COMPARE_WOMEN seeds
                                   roleUtils.ts          classifyRole (specialist batter / specialist
                                                          bowler / all-rounder / keeper-batter /
                                                          wicketkeeper / fielder), hasBatting/hasBowling/
                                                          hasFielding/hasKeeping gates, carryFilters,
                                                          matchesInScope
    teams/                     — Teams → Compare tab internals (sibling of players/ with a
                                   one-for-one structural parity):
                                   TeamCompareGrid       N-column side-by-side grid, fixed-arity
                                                          useFetch on getTeamProfile(team, filters)
                                                          per slot, FlagBadge on each column head
                                                          (null for franchise sides)
                                   TeamSummaryRow        one discipline band — Results / Batting /
                                                          Bowling / Fielding / Partnerships —
                                                          compact label/value layout only
                                   AddTeamComparePicker  TeamSearch wrapper, refuses candidates
                                                          whose in-scope match count is zero
                                                          (FilterBar auto-narrow is the upstream
                                                          cross-type/cross-gender gate)
                                   teamUtils.ts          teamDisciplineHasData (drives per-row
                                                          band visibility + placeholders),
                                                          teamMatchesInScope (uses summary.matches
                                                          as canonical — fielding.matches is
                                                          currently unfiltered), carryTeamFilters
  pages/                       — Home, Teams, Players, Batting, Bowling, Fielding, Tournaments,
                                   HeadToHead (mode=player|team), Matches, MatchScorecard,
                                   Venues (Phase 2 landing — country-grouped tile grid;
                                   landing + per-venue dossier, mode flips on ?venue=),
                                   Help (/help), HelpUsage (/help/usage)
  components/VenueSearch.tsx   — Debounced typeahead for the FilterBar Venue slot.
                                   Mirrors TeamSearch.tsx structurally. Renders an input
                                   when no venue is selected; flips to a chip + "× Clear
                                   venue" button when filter_venue is set.
  components/venues/           — VenuesLanding.tsx (country-grouped accordion, top-3
                                   countries open by default; tile click opens the
                                   Phase-3 dossier via ?venue=). VenueDossier.tsx
                                   (Phase 3 — 6 tabs Overview/Batters/Bowlers/Fielders/
                                   Matches/Records, mirrors TournamentDossier's
                                   fetch-gating). VenueOverviewPanel.tsx (Overview:
                                   StatCards + toss panel + phase table + ground-record
                                   tiles + matches-by-tournament-gender-season table).
  content/                     — about-me.md + user-help.md. Imported as ?raw by the Help pages
                                   and rendered via react-markdown. Edit the .md, rebuild, ship.
                                   user-help.md embeds screenshots from /social/*.png.
  scripts/                     — Dev-only tooling (NOT shipped with the frontend):
    assets-source/             — favicon.html + og-card.html + README. Render the brand
                                   assets (favicon PNGs, OG card PNG) via headless Chrome
                                   because rsvg-convert ignores font-variation-settings,
                                   which Fraunces's variable axes depend on. Regen steps
                                   in the README; commit the resulting PNGs in public/.
public/
  favicon.svg                  — italic Fraunces "&" on cream (masthead glyph)
  apple-touch-icon.png / icon-192.png / icon-512.png — PNG versions rendered from
                                   scripts/assets-source/favicon.html via headless Chrome
  og-card.png                  — 1200×630 Open Graph + Twitter card (summary_large_image),
                                   rendered from scripts/assets-source/og-card.html
  manifest.webmanifest         — PWA manifest pointing at the icons
  social/                      — Curated screenshots (01–18) + tweet-thread.md for the
                                   launch thread. Referenced by user-help.md for the
                                   Help page's inline walkthrough images. Ships to prod —
                                   live at https://t20.rahuldave.com/social/<file>.
```

## Infrastructure / docs

```
deploy.sh                              — Stages build_plash/ dir and runs plash_deploy
SPEC.md                                — Full specification with all API schemas and SQL queries
docs/
  frontend-build-pipeline.md           — Vite 8 + Tailwind v4 + TypeScript config notes
  design-decisions.md                  — All the invariants + "(revisit)" follow-on notes
  local-development.md                 — Prereqs, project layout, type-check/build commands,
                                          troubleshooting, Python-REPL DB query pattern
  data-pipeline.md                     — Full rebuild + incremental update flow and dry-run output
  deploying.md                         — What ships, deebase vendoring quirk, .plash identity,
                                          troubleshooting
  admin-interface.md                   — /admin/ Basic Auth, tables exposed, compat fixes
  visual-identity.md                   — Wisden redesign (fonts, palette, consistency rules)
  data-fetching.md                     — useFetch / Spinner / ErrorBanner pattern
  spec-fielding.md                     — Fielding Tier 1 (fielding_credit) spec
  spec-fielding-tier2.md               — Wicketkeeper identification (keeper_assignment) spec
  spec-team-stats.md                   — Team batting/bowling/fielding/partnerships spec (enhancement N)
  spec-tournaments.md                  — Tournaments tab + match-set dossier + polymorphic H2H spec
                                          (enhancement M, plus the unified rivalry/tournament model)
  enhancements-roadmap.md              — The A–O menu of shipped + planned items
  perf-leaderboards.md                 — Why /batters/leaders etc. are fast: conditional-JOIN
                                          elimination, composite covering indexes, ANALYZE.
                                          Reusable pattern for full-table aggregate endpoints.
  testing-update-recent.md             — Smoke-test update_recent.py against a copy of prod
                                          via the --db flag before deploying.
  next-session-ideas.md                — Open design questions: /tournaments tab, team-to-team
                                          H2H placement, landing-page perf options.
  api.md                               — Practical API reference with example curls + responses.
  keeper-ambiguous/                    — Date-partitioned CSVs of innings where keeper inference
                                          is ambiguous; resolutions fed back by
                                          apply_keeper_resolutions.py
```
