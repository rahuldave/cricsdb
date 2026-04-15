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
  filters.py          — FilterParams class (Depends), builds WHERE clauses with :param bind syntax
  routers/
    reference.py      — /api/v1/tournaments (canonicalized — variants merged), /seasons, /teams, /players
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
    tournaments.py    — Match-set dossier (enhancement M).
                         /api/v1/tournaments/landing (sectioned: ICC events, men's + women's
                          bilateral-rivalry tiles bilateral-only, club leagues, other)
                         /api/v1/tournaments/{summary,by-season,records,
                          batters-leaders,bowlers-leaders,fielders-leaders,
                          partnerships/by-wicket,partnerships/top,partnerships/heatmap}
                         — all accept optional tournament + series_type
                          (all/bilateral_only/tournament_only) + filter_team/filter_opponent.
                          Summary returns by_team per-team breakdowns when team-pair set.
                         /api/v1/tournaments/points-table (single-season; tournament required)
                         /api/v1/tournaments/other-rivalries (lazy-load expander)
                         /api/v1/rivalries/summary (legacy; new code uses dossier endpoints)
tournament_canonical.py — Shared canonical map (T20 WC variants → "T20 World Cup (Men)" etc.)
                         imported by filters.py + tournaments.py + reference.py for global
                         IN-variants expansion of tournament=X queries.
models/tables.py      — deebase models: Person, Match, Innings, Delivery, Wicket,
                        FieldingCredit, KeeperAssignment, Partnership
team_aliases.py       — Canonical team-name mapping (used by import + fix script)
event_aliases.py      — Canonical tournament-name mapping (same pattern as team_aliases)
fielder_aliases.py    — Canonical fielder-name mapping (married names, disambiguated names)
```

## Scripts

```
scripts/fix_team_names.py             — One-time UPDATE pass to canonicalize old team names in cricket.db
scripts/fix_event_names.py            — Same for tournament names (match.event_name)
scripts/populate_fielding_credits.py  — Builds fielding_credit table (auto-called by import + update pipelines)
scripts/populate_keeper_assignments.py — Builds keeper_assignment table + writes ambiguous worklist partitions (auto on import + update)
scripts/apply_keeper_resolutions.py   — Applies manual resolutions from docs/keeper-ambiguous/*.csv back into the DB
scripts/populate_partnerships.py      — Builds partnership table (auto on import + update)
```

## Pipelines

```
download_data.py      — Fetches cricsheet zips + people/names CSVs
import_data.py        — Full rebuild: downloads + imports into SQLite
                        (canonicalizes via team_aliases + event_aliases,
                         populates fielding_credit + keeper_assignment + partnership)
update_recent.py      — Incremental: imports new T20 matches + re-runs
                        all populate_* scripts on just those matches
```

## Frontend (React 19 + TypeScript + Tailwind v4 + Semiotic v3)

```
frontend/src/
  App.tsx                      — React Router: /, /teams, /batting, /bowling, /fielding,
                                   /tournaments, /head-to-head, /matches, /matches/:matchId
  api.ts                       — fetchApi<T> wrapper + all endpoint clients
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
  components/                  — Layout, FilterBar, PlayerSearch, TeamSearch, StatCard,
                                   DataTable, Spinner, ErrorBanner, Scorecard, InningsCard, charts/
    charts/                    — BarChart, LineChart, ScatterChart, DonutChart wrappers (responsive),
                                   HeatmapChart, BubbleMatrix,
                                   WormChart, ManhattanChart, InningsGridChart, MatchupGridChart
    tournaments/               — TournamentsLanding (sectioned grids + men's/women's rivalry tiles),
                                   TournamentDossier (shared dossier UI for tournament OR rivalry
                                   scope; reused by HeadToHead Team-vs-Team mode)
  pages/                       — Home, Teams, Batting, Bowling, Fielding, Tournaments,
                                   HeadToHead (mode=player|team), Matches, MatchScorecard,
                                   Help (/help), HelpUsage (/help/usage)
  content/                     — about-me.md + user-help.md. Imported as ?raw by the Help pages
                                   and rendered via react-markdown. Edit the .md, rebuild, ship.
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
