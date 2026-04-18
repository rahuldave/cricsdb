# Enhancements roadmap

The A–O menu of cricsdb enhancements — shipped items stay here as
historical markers (with pointers to their specs), and the unshipped
items are triaged. CLAUDE.md keeps just a "next up" pointer.

The list is roughly ordered by value/effort. Pick the highest unshipped
one that fits the available time.

---

**A. Loading + error states across all pages.** _Done._ See
`internal_docs/data-fetching.md` for the full pattern (useFetch hook, Spinner,
ErrorBanner, gated fetches, per-tab `<TabState>` helper, when NOT to
use useFetch, where loading/error sit relative to data). Rolled out to
Home, Matches list, MatchScorecard, Teams, Batting, Bowling, Head to
Head, PlayerSearch dropdown, FilterBar dropdowns.

**B. Mechanically-generated ball-by-ball commentary tab on the scorecard
page.** Cricsheet does NOT ship natural-language commentary like
Cricinfo's editorial feed — what we have is structured ball data. So
this would render each delivery as a feed line: `19.6 — Bumrah to Kohli
— 4 runs (FOUR)` or `19.4 — Bumrah to Sharma — OUT! caught Rohit b
Bumrah`. Useful and conventional, but be honest with users that it's
generated from data, not a writer's prose. Pairs naturally with the
**innings grid** (see `internal_docs/design-decisions.md` "Innings grid:
per-delivery visualization") — clicking a row in the grid could scroll
the commentary feed to the same ball, and vice versa.

**C. Fix `wicket.fielders` double-encoding at the source.** Currently
`import_data.py` calls `json.dumps(w_data.get("fielders"))`
redundantly — deebase's JSON column type also serializes, so the
stored value is a JSON string of a JSON string. The matches scorecard
router parses twice as a workaround
(`api/routers/matches.py:_build_dismissal_text`). Fix: drop the
`json.dumps(...)` wrapper in `import_data.py`, rebuild the DB with
`import_data.py`, then remove the double-decode branch. ~5-line code
change + 15-min DB rebuild.

**D. Bowling-vs-Batters scatter Y axis is counterintuitive.** _Done._
Switched the Y metric from bowling strike rate (balls/wicket) to
bowling average (runs/wicket), then flipped the Y axis via
`frameProps.yExtent = [maxAvg * 1.05, 0]` so low values (good for
bowler) sit at the TOP. The visually prominent top-left corner is now
where the bowler dominated. `ScatterChart` wrapper gained a
`frameProps` pass-through so any scatter can be axis-flipped.

**E. Identity ambiguity — players and teams.** Three related issues,
all about the same thing: cricsheet uses one name string for entities
that some users mentally model as separate, others as the same.

   1. **Player search returns abbreviated cricsheet names** ("V Kohli"
      not "Virat Kohli"). The `personname` table has alias variants —
      search ranking should prefer alias matches that include a longer
      /more familiar form when one exists. Backend change in
      `api/routers/reference.py` (`/api/v1/players`) plus a ranking
      heuristic.

   2. **Team names collide across genders.** ~110 team names appear in
      BOTH men's and women's matches: every international side (India,
      Australia, England, etc.), all IPL↔WPL franchises (Mumbai
      Indians, Delhi Capitals, RCB), all BBL↔WBBL franchises, all 8
      Hundred men/women pairs, NZ domestic sides. With Gender filter =
      "All", a team page aggregates both squads — statistically
      meaningless ("Mumbai Indians: 315 matches" = 278 IPL men + 37
      WPL women across two different leagues). _Partial fix shipped:_
      when a URL has `?tournament=X` but no gender, FilterBar auto-
      fills gender + team_type from the tournament metadata so deep
      links like `/matches?tournament=IPL` self-correct (commit
      8947f0c). As of enhancement N, FilterBar also auto-narrows
      team_type/gender when a team's tournament set is unambiguous
      (e.g. selecting MI → team_type=club). _Still TODO:_ direct team
      search on `/teams` with no filters and a gender-breakdown banner
      when both genders have matches in scope.

   3. **Player names can also collide across people.** Two separate "V
      Kohli"s could exist in the personname table (e.g. an Indian
      batter and a women's batter with the same initials + surname).
      Player IDs disambiguate everywhere internally, but the SEARCH
      dropdown shows names without context. Same fix shape as #2: when
      multiple people share a search-result name, append a small
      distinguishing tag (gender, primary team, era) so the user can
      pick the right one.

**F. Multi-player intersection filter on `/matches`.** Currently
single player only. Extend `player_id` to `player_ids` and `AND` the
EXISTS clauses. UI needs a multi-pill input. Useful but niche.

**G. Worm chart wicket markers as actual chart points.** _Done._ Each
wicket appears as a red dot on the worm line at the exact
(fractional-over, score) coordinate. Hover shows the dismissed batter
via the standard Semiotic tooltip. Strategy: combine over-end and
wicket data points into one sorted-by-over data array tagged with
`is_wicket: boolean`, then use Semiotic v3's `highlight` annotation
type which filters chart data by `field=value` and draws circles on
each match. The line draws through the wicket points naturally because
cumulative runs are monotonic. `LineChart` wrapper updated to pass
through `annotations` and `tooltip` props.

**H. Reverse direction of the scatter↔table linking on Batting/Bowling
vs-tabs.** The forward direction (click a row → highlight the matching
dot on the chart with an `enclose` annotation, scroll the row into
view) is shipped — see `internal_docs/design-decisions.md` "Linking scatter
charts to their data tables." The reverse direction (click a dot →
highlight the row, scroll the table to it) is missing because Semiotic
v3's high-level `Scatterplot` component does not expose `onClick` or
any per-point click handler.

**I. Responsive chart sizing.** _Done._
`frontend/src/hooks/useContainerWidth.ts` wraps a `ResizeObserver`.
`BarChart`, `LineChart`, and `ScatterChart` wrappers make `width`
optional and use the hook to fill their container when omitted.
`DonutChart` stays fixed-width (a circle doesn't usefully stretch).
All chart call sites now omit `width`; the dual-chart layouts that
used `flex gap-6 flex-wrap` were converted to `grid grid-cols-1
lg:grid-cols-2 gap-6` (or `grid-cols-[350px_minmax(0,1fr)]` for
donut+bar layouts) so each chart cell has a definite container width.
The previous mobile pass's `overflow-x-auto` workaround on chart cards
was stripped.

**J. Distinctive visual identity.** _Done._ Wisden editorial redesign
shipped. Cream background, Fraunces display serif + Inter Tight sans,
oxblood accent, rule-based layouts instead of card chrome. Full
documentation in `internal_docs/visual-identity.md`. Consistency rule: subject
in ink, connective in oxblood, hover to oxblood.

**K. Tournament-name canonicalization.** _Done._ Implemented in
`event_aliases.py` + `scripts/fix_event_names.py`, mirroring the
team-aliases pattern. Three competitions merged: NatWest T20 Blast /
Vitality Blast Men → Vitality Blast (English), MiWAY / Ram Slam → CSA
T20 Challenge (SA), HRV Cup / HRV Twenty20 → Super Smash (NZ). 784
rows updated; club-tournament count went from 27 to 21. See
`internal_docs/design-decisions.md` "Team-name canonicalization across
renames" for the shared writeup.

**L. Fielding analytics page.** _Tier 1 + Tier 2 done._ `/fielding`
page with `fielding_credit` denormalized table (~118K rows),
`fielder_aliases.py`, `wicket.fielders` double-encoding fix, 7 API
endpoints (`api/routers/fielding.py`), frontend page with 6 tabs (By
Season, By Over, By Phase, Dismissal Types, Victims, Innings List).
Fielder search via `role=fielder` in `/api/v1/players`. Tier 1 spec:
`internal_docs/spec-fielding.md`.

   - **Tier 2** — wicketkeeper identification via 4-layer algorithm
     (stumping → season-candidate → career N≥3 → team-ever-keeper).
     `keeper_assignment` table (one row per regular innings, 25,846
     rows) with `keeper_id` (nullable), `confidence` enum
     (`definitive/high/medium/low/NULL`), `method` tag, and
     `ambiguous_reason` + `candidate_ids_json` for the NULL rows.
     **Coverage**: 82.2% assigned (18.2% definitive, 43.2% high, 17.4%
     medium, 3.4% low), 17.8% NULL. Ambiguous rows exported to
     date-partitioned CSVs under `docs/keeper-ambiguous/<YYYY-MM-DD>
     .csv` (Hive-style; each innings_id appears in exactly one
     partition). Manual resolutions via `resolved_keeper_id` column +
     `scripts/apply_keeper_resolutions.py` — auto-applied at the end
     of every populate run so corrections survive rebuilds. New
     `api/routers/keeping.py` (4 endpoints) and Keeping sub-tab on
     `/fielding` with stumpings, keeping catches, byes conceded,
     confidence transparency. Scorecard shows per-innings keeper label
     (ambiguous rows render `"ambiguous — X or Y"` with both
     candidates clickable). Team pages show "Keepers used: X (N), Y
     (M)" rollup. Both `import_data.py` and `update_recent.py`
     auto-populate. Spec: `internal_docs/spec-fielding-tier2.md`, worklist
     README: `docs/keeper-ambiguous/README.md`.

**M. Tournament analytics page + match-set dossier.** _Done (2026-04-15)._
Spec at `internal_docs/spec-tournaments.md`. New `/tournaments` page with
sectioned landing (ICC events, men's + women's bilateral-rivalry tiles
bilateral-only, franchise / domestic / women's club leagues + other).
Tournament tile or rivalry tile both open the same dossier UI with tabs:
Overview, Editions, Points Table (single-edition only), Batters,
Bowlers, Fielders, Partnerships, Records, Matches. Single shared
`TournamentDossier` component handles three URL shapes:
`?tournament=X` (tournament dossier), `?filter_team=A&filter_opponent=B`
(rivalry dossier), or both (team pair within a tournament). Backend
endpoints all accept optional `tournament` + `series_type`
(all/bilateral_only/tournament_only) + filter_team/filter_opponent;
summary returns `by_team` per-team breakdowns when team-pair set.
Tournament canonicalization (e.g. T20 WC's three cricsheet variants)
moved to a shared `api/tournament_canonical.py` module so FilterParams
expands to IN-variants globally. The `_by_team` and tournament-scoped
endpoints set up enhancement O cleanly: any team page can fetch the
same endpoint without a team filter to get a tournament baseline.

**Polymorphic Head-to-Head** (shipped alongside M). `/head-to-head`
gained `?mode=team` for team-vs-team analysis, reusing the dossier
UI. Common-matchup suggestion grid (top-9 men's + women's) under the
picker. Teams > vs Opponent has a "See full rivalry →" link to it.
Originally listed as enhancement B (deferred); promoted in scope when
the unified rivalry-as-team-pair-filter model emerged.

**N. Team statistics — batting / bowling / fielding / partnerships.**
_Done (2026-04-14)._ Spec at `internal_docs/spec-team-stats.md`, ~21h of build.
New `partnership` table (~180K rows, populated by
`scripts/populate_partnerships.py`, auto-called by `import_data.py` +
`update_recent.py`). 16 new endpoints on `api/routers/teams.py`
covering: batting/bowling/fielding summary + by-season + by-phase +
top-N players, phase × season heatmaps with run-rate AND
wickets-per-innings, partnerships by-wicket + heatmap + top-10 +
best-pairs (top-3 ranked by total runs together), opponents-matrix
(rollup + cells), team-scoped tournaments + seasons
(`/api/v1/tournaments?team=X`,
`/api/v1/seasons?team=X&tournament=X&...`). Frontend: 4 new tabs on
`/teams` (Batting, Bowling, Fielding, Partnerships), redesigned
vs-Opponent tab (stacked-bar rollup + drill-in + bubble matrix instead
of one-opponent-at-a-time dropdown), new `BubbleMatrix` and
`HeatmapChart` components, win-% labels above wins-by-season bars
(oxblood, per-bar tracking), team-aware FilterBar (auto-narrows
team_type/gender + season list to team's actual matches), Match-list
tab moved to last for player-page consistency, Home-page additions
(RCB IPL 2025 / RCB Women WPL 2025/26 / Perth Scorchers BBL / MI Women
WPL champion links + Pollard/Mooney fielders in focus + WI 2016 T20
WC). Wisden style addition: `.wisden-section-title` for centered
editorial headings above charts (avoids the in-chart `title` prop
colliding with above-bar percentage labels). Several follow-on items
captured as "(revisit)" subsections in `internal_docs/design-decisions.md`:
tournament baselines (enhancement O), win-% overlay on discipline
tabs, batter consistency stats (median / 30+ rate / dispersion),
batter × bowler-type and bowler × batter-handedness splits.

**O. Tournament-baseline comparisons across team / batter / bowler /
fielder pages.** _Next up._ Enhancement M shipped the per-tournament
endpoints with explicit baseline reusability: call any
`/tournaments/{summary,batters-leaders,…}` without a team filter to get
the tournament-wide baseline, with a team filter for the team's
narrowed view. Both responses are shape-compatible. Now wire this up:
every team-tab chart should overlay the league mean as a reference
line/band, every player table should gain a "vs league avg" column,
phase × season heatmaps should support a "delta from league mean"
colour mode. Detail in `internal_docs/design-decisions.md` "Team metrics need
tournament baselines (revisit when /tournaments ships)".

**P. Search-tab landings + default season window + FilterBar resets.**
_Done (2026-04-15)._ Every search-bar tab (`/teams`, `/batting`,
`/bowling`, `/fielding`) gained a filter-sensitive landing component
shown when no entity is selected. Four endpoints:
`/api/v1/teams/landing` (international split regular/associate via a
hardcoded ICC full-member list + clubs grouped by tournament),
`/api/v1/batters/leaders` (top 10 by avg + SR, thresholded to 100
balls + 3 dismissals), `/api/v1/bowlers/leaders` (top 10 by SR + econ,
thresholded to 60 balls + 3 wickets), `/api/v1/fielders/leaders`
(top 10 fielders + top 10 designated keepers via `keeper_assignment`,
volume-based). Batting/Bowling/Fielding landings auto-scope to the
last 3 seasons via `hooks/useDefaultSeasonWindow.ts` (one-shot per
mount, writes to URL so FilterBar reflects it). FilterBar gained
three subtle text buttons — "all-time" clears the season range
(always visible, for consistency as a time reset on every page),
"latest" pins both ends to the latest season in the current filter
scope (respects gender/team_type/tournament), and "reset all" clears
every filter (shown when anything is set).
Teams landing stays all-time so defunct teams like Pune Supergiants
remain visible. Players tab on `/teams` gives per-season roster with
batting average / bowling SR / turnover-vs-previous-season; name
resolution uses the longest `personname` variant strictly longer than
`person.name` (so "V Kohli" → "Virat Kohli" where available). Perf
work: conditional-JOIN elimination when no match-level filter is set
+ two composite covering indexes (`ix_delivery_batter_agg`,
`ix_delivery_bowler_agg`) + ANALYZE, re-asserted idempotently in
both `import_data.py` and `update_recent.py`. Unfiltered landing
queries went from 3s+ to sub-second locally. See
`internal_docs/perf-leaderboards.md` for the reusable pattern.
`update_recent.py --db <path>` flag added for smoke-testing against
a copy of the prod snapshot in `/tmp` before deploying (see
`internal_docs/testing-update-recent.md`). Home-page gains two deep links:
"(players)" next to West Indies T20 WC 2016 and "MI men — players
over the years".


**Rivalry polish (shipped 2026-04-16).** Follow-ons to M:
- Player pages honour `filter_team` + `filter_opponent` end-to-end.
  `useFilters()` reads them; `FilterParams.build_side_neutral()` makes
  fielding/bowling/keeping queries apply team/opponent as match-level
  pair filters (their credits live in opponent-batting innings, so the
  default `i.team = :team` clause returns zero). Changes in
  `api/filters.py` + the three routers; 63-URL regression harness
  described in `internal_docs/regression-testing-api.md` proved the refactor
  inert on un-scoped paths.
- Team-page / rivalry-dossier context links now carry the active
  tournament through to the player's page so the lens is complete.
  `playerContext` in TournamentDossier merges team + tournament
  dimensions and flips filter_team/filter_opponent per player in
  rivalry mode (so India vs Australia gets the right "vs <opponent>"
  label depending on which side a given batter played for). Needs
  leaders endpoints to return `team` — done.
- Player pages show a "Scoped to X" oxblood pill (`ScopeIndicator`)
  with a CLEAR button when `filter_team` / `filter_opponent` is set.
- FilterBar auto-narrows team_type + gender from filter_team the
  same way `team=` on the Teams page does, and also auto-sets
  `tournament` when filter_team + filter_opponent collapse to exactly
  one shared competition (MI × CSK → IPL). `/api/v1/tournaments`
  gained an `opponent` query param for the pair-intersection lookup.
- `/tournaments` → `/series` rename (route, nav label, API paths, page
  title). The word "tournament" was doing double duty — the filter-bar
  dropdown _and_ the catalog page. "Series" is cricket-native for
  both bilateral tours and tournament editions, so it covers the
  catalog's real scope. `/tournaments` redirects to `/series` for
  back-compat.

**R. Players tab — person-focused overview + N-way comparison.**
_Done, 2026-04-16._ `/players` is the new nav group parent — a fifth
top-level tab. Three modes driven by the URL:
- `/players` → curated landing (popular profiles + popular
  comparisons) with filter-sensitive one-line stat strips.
- `/players?player=X` → single-player stack: identity line
  ("specialist batter · 388 matches"), Batting → Bowling → Fielding
  → Keeping bands, each with a `→ Open <discipline> page` link
  that carries every active filter. Bands hide when the player has
  no data for that discipline in the current scope.
- `/players?player=X&compare=Y[,Z]` → 2-way or 3-way compare. Rows
  stay vertically aligned via placeholders ("— no bowling in scope —")
  when one column is empty; compare columns use a compact label/value
  layout so narrow widths don't overflow. Cross-gender adds are
  refused in-place.

Nav restructure: Batting / Bowling / Fielding collapse into a
`Players ▾` group — desktop hover-dropdown + persistent mobile sub-
row (Players · Batting · Bowling · Fielding) whenever the route is
in the group. The three discipline URLs are unchanged; only their
nav presentation moves. Home-page `PlayerLink` primary names now
route to `/players?player=X` with small italic `b · bw · f`
subscripts deep-linking to the discipline pages.

No backend endpoints. `getPlayerProfile` in `frontend/src/api.ts`
composes four existing summary calls per player in parallel, with
`.catch(() => null)` per discipline so 404s don't abort the bundle.
Role classifier (`components/players/roleUtils.ts`) tuned to exclude
tail-end batting (balls/inn ≥ 5 + avg ≥ 10) and one-over-a-season
bowling (balls/total-match ≥ 3, using `fielding.matches` — the true
career-match count — as denominator). Integration tests live in
`integration_tests/players_tab.sh` + `players_hygiene.sh`. Spec at
`internal_docs/spec-players.md`.

**S. Venues — canonicalization + filter + landing + dossier.** _Phases 1
+ 2 done, 2026-04-17._ Three-phase delivery (spec at
`internal_docs/spec-venues.md`). **Phase 1** (DB cleanup + insert hooks)
shipped: 676 raw `(venue, city)` pairs from cricsheet canonicalized to
456 distinct venues across 88 countries via
`api/venue_aliases.py::resolve_or_raw()`. Worklist round-trip (generator
script → human-reviewed CSV at `docs/venue-worklist/2026-04-17-worklist.csv`
→ `venue_aliases.py` ingester) handles name renames (Chittagong →
Chattogram, Bangalore → Bengaluru, Port Elizabeth → Gqeberha, Sheikh
Zayed Nursery 1/2 → Tolerance Oval / Mohan's Oval) and same-ground-
multi-label duplicates (Wankhede / Wankhede Stadium, Mumbai etc. collapse
to one). Paren-disambiguate form for genuinely ambiguous bare names (six
"County Ground"s, National Stadium Karachi vs Hamilton, University
Oval Dunedin vs Hobart, etc.). Sibling grounds at multi-oval complexes
(Alur I/II/III, ICC Academy Ground No 2 vs Oval 2, Eden Park vs Outer
Oval) deliberately kept separate. `match.venue_country` TEXT NULL added
to the schema; `import_data.py` and `update_recent.py` apply the alias
on insert so the DB stays clean from day 1. Soft-fail: unknown venues
pass through as raw with `venue_country` NULL and get logged to
`docs/venue-worklist/unknowns-<date>.csv` for the next review cycle.
`scripts/fix_venue_names.py` is the idempotent retrofit tool — rerun it
any time the alias dict grows. **Phase 2** added `filter_venue` as an
ambient filter (`FilterParams.build()` + two hand-rolled pickers),
`GET /api/v1/venues` (typeahead with `q` substring match; top-50 cap)
and `GET /api/v1/venues/landing` (country-grouped tile directory),
plus the `/venues` route, a Venues nav slot (7 → 8 top-level tabs),
and a FilterBar Venue typeahead (`components/VenueSearch.tsx`) that
flips to a chip with "× Clear venue" when active. Every page's
`filterDeps` array + 5 carry functions were patched to include
`filter_venue` (SPA navigation refetches + back-button works). Regression
harness: 18/18 REG byte-identical, 9/9 NEW queries differ. **Phase 3**
(per-venue dossier with Overview / Batters / Bowlers / Fielders /
Matches / Records) is opt-in after Phase 2 proves thin or sufficient.

**T. Launch identity — favicon, OG card, tweet thread, help-page
walkthrough.** _Done, 2026-04-16._ Replaced the default Vite bolt with
an italic oxblood Fraunces `&` on cream — the masthead's signature
glyph — scaled to favicon.svg, apple-touch-icon (180), icon-192,
icon-512, and embedded in a 1200×630 Open Graph card (rendered at
headless-Chrome because `rsvg-convert` ignores Fraunces's variable-
axis settings — see `design-decisions.md` "Fraunces variable-font
axes need Chrome, not rsvg-convert"). `index.html` gained the full
OG + Twitter (`summary_large_image`) tag set with `@rahuldave` as
the creator. A `manifest.webmanifest` makes the site installable
as a PWA. 18 curated screenshots shipped at
`frontend/public/social/`, doubled as (a) image manifest for a
12-tweet launch thread saved at `social/tweet-thread.md` and
(b) inline walkthroughs embedded into `user-help.md` so the Help
page now has visual examples for Teams, Series, Players, H2H,
Matches, and the filter scope pill. Source HTML files for the
brand assets live in `frontend/scripts/assets-source/` so the
icons + OG card are reproducible.

**Q. Batter-pair profile page (deferred).** Partnerships are
consistently scoped everywhere they appear — team page > partnerships
tab, tournament dossier > partnerships tab, rivalry dossier > by_team.
The gap: no dedicated "Kohli × ABD across all contexts" view. Their
combined aggregate only surfaces inside RCB's team page via
`/partnerships/best-pairs` — a user has to know they played at RCB.
Proposed: new `/pairs/:a/:b` route + backend endpoint returning
combined runs/balls/average across all contexts, phase splits, and
a match-by-match list. Surfaced via a new context link on partnership
rows' batter cells: `· with <other batter> ›`. Not urgent — flagged
so we remember. Design in the chat transcript around the time the
PlayerLink two-link pattern shipped.
