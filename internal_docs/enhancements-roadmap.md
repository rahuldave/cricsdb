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
`tests/integration/players.sh` + `players_hygiene.sh`. Spec at
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
harness: 18/18 REG byte-identical, 9/9 NEW queries differ. **Phase 3
shipped 2026-04-18** — per-venue dossier at `/venues?venue=X` with
Overview / Batters / Bowlers / Fielders / Matches / Records tabs.
One new backend endpoint (`GET /api/v1/venues/{venue}/summary`) for
the Overview bundle — avg 1st-inn total, bat-first vs chase win %,
toss-decision split + win correlation, boundary % and dot % per
phase, highest total, lowest all-out, matches hosted by tournament ×
gender × season. Other tabs reuse `/batters,/bowlers,/fielders/leaders`
+ `/matches` + `/series/records` with `filter_venue=X` — no shape
change required. Landing tile click now opens the dossier rather
than a bare `/matches?filter_venue=X` list; a "view all matches →"
escape hatch preserves the old drilldown. Sanity: Wankhede bat-first
43% (dew-heavy ✓), Chepauk bat-first 54% (spin-friendly ✓).
Regression 18/18 REG byte-identical; integration 49/49 asserts.

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

---

## Session logs (chronological)

These dated blocks were lifted out of CLAUDE.md when it was trimmed
on 2026-04-19. They cover work that doesn't slot into a single A–Q
letter (cross-cutting refactors, audit walks, infra fixes, follow-up
batches) and serves as the "what shipped on day X" history.

### Shipped 2026-04-17 / 2026-04-18

- **llms.txt** at `/llms.txt` pointing to api.md, Swagger, OpenAPI JSON, user-help — lets an LLM interact with the public API without scraping.
- **Teams landing cross-gender link bug fix**: clicking a gendered tile now atomically sets both `team` and `gender` in the URL (was dropping gender via a raw `history.replaceState` race). Same architectural fix rippled into a codebase-wide **"derive don't mirror" refactor** on every search input — PlayerSearch, TeamSearch, Teams.tsx, Matches.tsx — replacing `useState(urlParam || '')` mirrors with a typing-buffer pattern (`internal_docs/url-state.md` "Search inputs" section).
- **Teams landing gender labeling**: "Franchise leagues" → "Men's franchise leagues"; Domestic section splits Men's / Women's; "Other tournaments" → "Other men's tournaments" / "Other women's tournaments". Per-tile gender badges already present; now section headers also disambiguate.
- **Teams → Compare tab (T)**: up to 3 teams side-by-side across Results / Batting / Bowling / Fielding / Partnerships rows. Mirrors Players compare architecturally. New endpoint `/api/v1/teams/{team}/partnerships/summary` for aggregate counts + highest + top pair. Cross-gender / cross-type blocked via FilterBar auto-narrow + scope-match probe in the picker.
- **Pre-existing fielding/summary filter bug fixed**: the matches-count sub-query wasn't applying `FilterParams`, so `catches_per_match` etc. had a diluted denominator. Surfaced by Compare, fixed in the same batch.
- **Venues Phase 1 (S)** — DB canonicalization + insert hooks. 676 raw `(venue, city)` cricsheet pairs collapse to 456 canonical venues across 88 countries via `api/venue_aliases.py::resolve_or_raw()`. New column `match.venue_country` TEXT NULL. Full worklist round-trip via `scripts/generate_venue_worklist.py` → human-reviewed CSV at `docs/venue-worklist/2026-04-17-worklist.csv` → regenerated alias module. Idempotent retrofit via `scripts/fix_venue_names.py` (can be re-run whenever the alias dict grows). `import_data.py` + `update_recent.py` canonicalize on insert; unknown venues soft-fail to raw pass-through and log to `docs/venue-worklist/unknowns-<date>.csv`.
- **Venues Phase 2 (S)** — FilterBar `filter_venue` param, `/api/v1/venues` typeahead endpoint, `/api/v1/venues/landing` country-grouped directory, `/venues` route, 8th top-level nav slot between Players ▾ and Head to Head. FilterBar gets a typeahead Venue search (mirrors TeamSearch — `components/VenueSearch.tsx`) that flips to a chip + "× Clear venue" button when a venue is active. Every tab (Teams / Players / H2H / Series / Matches / Batting / Bowling / Fielding / Keeping) respects the filter: 68 endpoints via `FilterParams.build()`; `reference.py::list_teams` + `tournaments.py::_build_filter_clauses` (13 Series endpoints) got 3-line additions for the venue clause. Regression harness: 18/18 REG byte-identical, 9/9 NEW queries differ. Also fixed a fan-out landmine: every page's `filterDeps` array + 5 carry functions hand-patched to include `filters.filter_venue` so SPA navigation triggers refetches (not just reloads). Option B (auto-derive filterDeps from `Object.values(filters)`) captured as follow-up in `internal_docs/design-decisions.md`.
- **Venue punctuation-collision sweep** — new permanent tool `scripts/sweep_venue_punctuation_collisions.py`. Slugifies each canonical venue (strip non-alphanumeric, lowercase, strip city suffix) + groups by `(slug, country)` to catch canonical-vs-canonical collisions that differ only by punctuation. Five caught on 2026-04-17: `M.Chinnaswamy → M Chinnaswamy Stadium, Bengaluru` (+17 matches), `ACA VDCA → ACA-VDCA` (+24), `Casey Fields No. 4 → No 4, Melbourne` (+6), `Gahanga … period → …, comma` (+77), `Grand Prairie Stadium, Dallas → Grand Prairie Stadium / Grand Prairie` (+41). 175 rows retrofitted; idempotent on re-run. Run this after every big incremental import (rare — new stadiums are uncommon).
- **tests/ folder restructured** — `integration_tests/` → `tests/integration/` (history preserved via git mv), new sibling `tests/regression/` with a generalised runner at `tests/regression/run.sh` that takes a feature name and runs the HEAD-vs-patched md5-diff cycle previously described only in `internal_docs/regression-testing-api.md` with ad-hoc `/tmp` scripts. Phase-2 inventory checked in at `tests/regression/venues/urls.txt`; matching browser-level suite at `tests/integration/venues.sh` (25/25 asserts pass). Runner uses `mkdir -p` in `capture()` so its output dir is owned by the function. Integration assertions use base64-wrapped `document.body.innerText.toLowerCase()` to sidestep shell-quoting + accessibility-tree gaps + CSS text-transform gotchas.
- **Tests backfill — every tab (2026-04-18).** Every top-level route now has a `tests/regression/<tab>/urls.txt` (all-REG endpoint inventory, 181 new URLs on top of the existing 28 venues URLs, across teams / batting / bowling / fielding / series / head_to_head / matches / players — 209 total) plus a `tests/integration/<tab>.sh` happy-path. Cross-cutting integration tests were reorganised: page-specific URL-state assertions moved from the old `back_button_history.sh` into the relevant per-tab scripts (e.g. `/matches` filter push → `matches.sh`; `/batting` gender auto-fill + default season window + tab switches → `batting.sh`; `/fielding` filter_team auto-narrow → `fielding.sh`; `/series` series_type reset + `/tournaments` redirect + `rivalry=` migration → `series.sh`); the file itself was renamed `cross_cutting_url_state.sh` and kept only ScopeIndicator + PlayerLink (true cross-tab widgets). `mount_unmount.sh` was renamed `cross_cutting_mount_unmount.sh`. `players_tab.sh` was renamed `players.sh` to match the per-tab convention. End-to-end run on 2026-04-18: **180 / 180 asserts pass across 12 scripts** (one selector miss on `matches.sh` Test 1 — `/matches` date cells aren't links, row-click navigates instead — fixed by targeting `tr.is-clickable`). `tests/README.md` + both subdir READMEs describe the new layout.
- **Linking + navigation audit (2026-04-18).** Page-by-page walk of every top-level route against the "match-list date convention", "two-link name + context pattern", and "links up / dead ends" rules in CLAUDE.md. 21 findings seeded as a survey, then worked through tab-by-tab in the same session (see below).
- **Linking + navigation audit — tab-by-tab follow-up (2026-04-18, same day as the survey).** Walked the audit with the user finding-at-a-time, shipping at the end of each page. Outcome across ~25 individual fixes:
  - **Home**: #16 withdrawn on re-read (the fixture row is already a `<Link>`; audit was wrong).
  - **Teams**: 4 shipped — Keepers strip `<a href>` → `<Link>`; Players-tab grid names route to `/players?player=X&filter_team={team}` (ScopeIndicator pill on arrival instead of a per-row suffix); opponent stacked-bar name becomes a rivalry link (`/head-to-head?mode=team`) with `stopPropagation` preserving the bar-click selector and `justifySelf: start` trimming the underline to text-width; **NEW bug caught during the walk**: tab-switch was leaking tab-local `vs=` into other tabs — fixed with `setUrlParams({ tab, vs: '' })`.
  - **Players**: 0 items. Re-verified independently; all name renderings already use `<Link>` / `PlayerLink`, ScopeIndicator handles `filter_team` arrivals.
  - **Batting**: 3 shipped — #3 `vs Bowlers` hybrid (name → `/bowling?player=X` as `comp-link`; `(stats)` dropped; `HEAD TO HEAD` micro-suffix at 0.55rem uppercase opacity 0.65 replaces the old `(stats · h2h)` parenthetical), innings-list opponent → `/teams`, innings-list tournament → `/series`. Long-name-in-suffix concern led to the opacity-based faint style (vs inline `color: var(--ink-faint)`) — opacity doesn't fight `:hover`'s color rule on specificity.
  - **Bowling**: 3 shipped — mirror of Batting (#4 hybrid + opponent + tournament columns).
  - **Fielding**: 3 shipped — #5 Victims name → `<Link>` to `/batting?player=X`; dropped the `(stats · h2h)` micro-menu entirely (no meaningful player-vs-player H2H for a fielder), which naturally fixed #6 broken `&bowler=` hardcode. Opponent + tournament columns linked in BOTH the fielding and keeping innings-list tables.
  - **Series**: 5 buckets (~11 cells) shipped. New `renderBatterPair(b1, b2)` + `renderVsTeams(t1, t2)` + `renderVsTeamsFromString(s)` helpers inline at top of `TournamentDossier.tsx`. Records tab: all four cells linked. Partnerships tabs (By-Wicket + Top): batter pair + match team pair linked. Editions table (not in original audit): champion / runner-up → `/teams`, top scorer → `/batting`, top wicket-taker → `/bowling`. Shortened per-row tournament context — `playerContext()` drops the long tournament name from the label when on a tournament dossier page; shows `· tournament ›` alone when that's the only scope, drops entirely when team/rivalry is also set (tournament still flows through URL params).
  - **HeadToHead**: 2 shipped — CSS reset on `.wisden-tile` (`text-align: left; cursor: pointer; font: inherit; width: 100%`) so button-based tiles render identically to anchor-based tiles used on Series landing; by-match tournament column linked.
  - **Matches + Scorecard**: 6 shipped — Matches list date cell is now a `<Link>` (cmd-click opens new tab); Matches list venue cell uses the canonical venue name linked via `filter_venue`; Scorecard meta-line venue linked; Scorecard breadcrumb above the h2 (`Tournament › Season › All matches`); toss-winner team linked; innings-header team prefix linked in `InningsCard` (defensive split on label prefix).
  - **Venues**: deferred pending Phase 3 walk.
- **Two architectural follow-ups documented** in `internal_docs/design-decisions.md`:
  1. **Team-name link scope ambiguity** — the scope attached to a team link varies by origin page (Teams landing `?team=X` vs Matches/Scorecard `?team=X&tournament=Y`), and bilateral-series `tournament` values are transient. Proposed fix: introduce a `TeamLink` component parallel to `PlayerLink` with name → overall + optional context suffix; bilateral+season disambiguates the specific tour the same way tournament+season disambiguates a tournament edition. (Shipped 2026-04-19 — see below.)
  2. **Scorecard linkability: API response-shape follow-up** — four scorecard fields (`player_of_match`, dismissal text, did-not-bat, fall-of-wickets) currently return strings/pre-rendered text; they need `PersonRef`-shaped responses so the frontend can link the names. Single-PR batch on the matches router when we pick this up.

### Shipped 2026-04-18 (later in same day)

- **Venues Phase 3 — per-venue dossier** at `/venues?venue=X`. Tabs: Overview / Batters / Bowlers / Fielders / Matches / Records. One new backend endpoint `/api/v1/venues/{venue}/summary` (avg 1st-inn, bat-first vs chase win %, toss decision + win correlation, boundary % and dot % per phase, highest total, lowest all-out, matches hosted by tournament × gender × season). Other tabs reuse `/batters,/bowlers,/fielders/leaders` + `/matches` + `/series/records` with `filter_venue=X` — no shape change required. Landing tile click flips from "open match list" to "open dossier"; dossier has a "view all matches →" escape hatch back to the bare list. Regression harness: 18/18 REG byte-identical + 5 new summary-endpoint URLs. Integration: 49/49 asserts pass. Sanity-checked Wankhede (avg 170.5, bat-first 43% — dew-heavy) and Chepauk (avg 165, bat-first 54% — spin-friendly) against the spec gut checks. Also exposed `_strip_venue` with a `has_innings_join` kwarg so the summary endpoint can reuse the same self-referential strip for delivery-level queries.

### Shipped 2026-04-19

- **TeamLink phrase model** (replaces letter model for team links). Container resolution is `series_type`-driven: bilateral drops tournament from URL, icc/club keeps it, all/unset + rivalry pair drops it. H2 layout `block` (small-caps stacked); table layout `inline`. See CLAUDE.md "Critical Design Decisions → Scope-link architecture" and `frontend/src/components/scopeLinks.ts::resolveScopePhrases`.
- **FilterBarParams + AuxParams backend split** + frontend `useFilters` surfacing `series_type`. All 7 routers (matches, teams, batting, bowling, fielding, keeping, venues) now apply `series_type` via `AuxParams`. Pre-existing silent-drop bug in matches.py that had been there since the series_type pill landed; fixed alongside.
- **ScopeStatusStrip** — one-line scope summary below FilterBar with COPY LINK button. Reads filters + aux + path identity. Auto-hidden when nothing narrowed.
- **TournamentsLanding rivalry tile** opens on `series_type=all` (was `bilateral`) — wider scope for landing arrival; user can narrow via the pill.
- **FilterBar back-button race fixed** — auto-narrow `useEffect` was firing with stale `tournaments` state during back-navigation, re-pinning a previous tournament via `replace`. Replaced async `setStale` flag with a synchronous scope-signature check (`fetchedScope !== currentScope`).
- **Series tab Aus-v-Ind audit** through 4 scenarios (rivalry-only, rivalry+series_type, rivalry+tournament+season, IPL/T20WC dossiers). H2 of rivalry dossier renders correctly across all four.
- **FilterBar dropdown narrowing respects every FilterBar field.** `getTournaments` and `getSeasons` receive the full FilterParams payload plus page-local `series_type`; backend `/api/v1/tournaments` + `/api/v1/seasons` accept and narrow by `season_from` / `season_to` / `filter_venue` / `series_type` via the same `_reference_clauses` helper. Effect: on `/series?series_type=bilateral&filter_team=India&filter_opponent=Australia`, the tournament dropdown hides T20 World Cup and shows only bilateral series between the two teams. Regression harness at `tests/regression/filterbar_refs/` pins 14 REG byte-identical + 7 NEW differs. Integration tests in `tests/integration/series.sh` Tests 5a/5b.

### Shipped 2026-04-20

- **PlayerLink phrase cutover + tier order reversed.** Retired `(e, t, s, b)` letter model. `resolveScopePhrases` extended with `keepRivalry: boolean`; PlayerLink + TeamLink now share the same resolver. Tiers now render narrow→broad so the first phrase adjacent to a stat matches the stat's scope ("794 runs at IPL, 2024, at IPL" — 794 is the 2024 number). Added `trailingContent` prop to PlayerLink for name → stat → phrase composition. Removed `border-bottom-width:0` override on `.scope-phrase` so the link is visible without hover.
- **Tournament-dossier Overview rich StatCards + Best moments prose section.** Top-of-Overview cards (Most titles / Top scorer / Top wicket-taker) now have linked names + all-tier scope phrases in the subtitle. Row 1 aggregate cards gained a Fours card (parallel to Sixes). Single-match highlights (Best batting / Best bowling / Highest partnership / Best fielding / Highest total) live in a prose "Best moments" section under a `wisden-section-title` — tried cards first, backed out because five multi-part tiles read as too busy.
- **Backend `/series/summary` enriched.** `top_scorer_alltime` / `top_wicket_taker_alltime` / `best_bowling` gained `team` field for rivalry orientation. `highest_individual` (new — best single-match batting), `best_fielding` (new — most dismissals in a single match, over `fieldingcredit`), `largest_partnership` enriched to match the rivalry `by_team` shape (batter1/batter2 PersonRefs + team + opponent + date). `knockouts[]` gained `tournament` so multi-tournament scopes can render a linked "<Tournament> <Season>" Edition cell.
- **Orientation fix for rivalry-scope StatCards.** Batter playing FOR India no longer reads "vs India" — phrases flip per the player's team via `orientedSource()` helper, same pattern as leaderboard tables' `rowSubscriptSource`.
- **`_partnership_filter` 500 fix (pre-existing).** `api/routers/teams.py` helper was calling `filters.build(aux=aux)` with `aux` as a free variable — silent at import, 500 at every Teams > Partnerships request. Threaded `aux: AuxParams | None = None` through helper + 5 call sites. CLAUDE.md now carries a discipline note: grep `filters\.build\(` before shipping a helper refactor.
- **ScopeStatusStrip now has `--bg-soft` background.** Visual separator between nav/filter chrome and page content. Considered tinting the whole nav bar same color; rejected — the strip earns its tint because it's the last band before content.
- **API health sweep** — ran bash probe across ~70 endpoints × several param combinations including `series_type=icc` / `series_type=bilateral`. Zero 500s after the partnership fix. Probe script at `/tmp/api_sweep.sh`; worth committing under `tests/` if we hit a third aux-threading class bug.

### Shipped 2026-04-20 (pm — Series tab deep-dive)

Walk down the Series tab, tile-by-tile, establishing the scope-link
conventions for subsequent tabs. Commits `9107ca3`…`4d9f0e1`.

- **SeriesLink component.** Mirror of TeamLink/PlayerLink but with a
  `/series?...` destination. Takes an explicit scope spec
  (tournament, season, seriesType, team1, team2, gender, team_type,
  filter_venue) — no FilterBar context, since tiles describe row-
  intrinsic scope. Migrated five existing raw-Link call sites
  (Batting/Bowling/Fielding/HeadToHead innings-list tournament cells,
  TournamentDossier by-season edition rows).
- **Series-landing tile redesign.** Tournament + rivalry tiles now
  use a stretched-link pattern (CSS `.tile-stretched` + pointer-
  events-none siblings + z-index) so the tile body is clickable
  without nesting `<a>` inside `<a>`, while inner TeamLink/SeriesLink
  affordances capture their own clicks + cmd-clicks. Tournament
  tiles carry new "Most titles: [TeamLink India] (3)" (name →
  all-time, count → scoped) and split "Latest: 2025/26" + "Winner:
  India · all-time" lines — scope hoisted on the Winner line as
  a whole-phrase link so the bare "India" never means scoped.
- **Rivalry tile Latest + Winner lines.** Backend `latest_match`
  extension — scoped across all-international (not bilateral-only)
  so T20 WC 2024 beats a 2023 bilateral when it's the most recent
  meeting. Returns `tournament` (canonical name for ICC-event
  meetings, `null` for bilateral tours) + `season`. Frontend renders
  Latest as a SeriesLink to the appropriate scoped dossier and
  Winner as a whole-phrase link with `keepRivalry=true` on TeamLink.
- **TeamLink opt-in props.** `keepRivalry`, `seriesType`, `team_type`,
  `maxTiers` — all defaults preserve today's behavior. Used on home-
  tab rivalry tiles to override scope without the caller's URL
  having to carry aux filters.
- **Dossier pill rename.** "Bilateral T20Is" → "only bilaterals"
  (reads cleaner next to "All international" / "ICC events" /
  "Club tournaments").
- **Participating teams refactor.** Section title hoists the scope
  once ("Teams at T20 World Cup (Men), 2025/26 (19)"). Each chip
  splits: TeamLink compact (name → all-time) + " · " + Link on the
  count (→ team at tournament + season). Convention-correct.
- **Groups tile fix.** Removed phantom `cursor: pointer` (tile had
  no click handler). Each team row now splits into TeamLink + scoped
  count link. Groups only render on single-edition scope (`editions
  === 1`).
- **Knockouts venue cell.** Linked to `/venues?venue=X` dossier.
- **Editions tab bracketed counts.** Champion / Runner-up /
  Top scorer / Top wicket-taker columns now render "<name> (<count>)"
  where `<name>` is TeamLink/PlayerLink compact (all-time) and
  `<count>` is a Link scoped to the edition. Backend `/series/by-
  season` extended with `champion_record` + `runner_up_record`
  `{played, won}` per season via a UNION-ALL participations CTE.
- **Editions tab dropped Run rate column.** Every remaining column
  is actionable (drill into a team / player / scorecard / season
  narrow); run rate was a read-only meta-stat better suited to
  Records or the Overview trend chart (both untouched).
- **Discipline landings default to all-time.** Removed the
  `useDefaultSeasonWindow(filters, true)` one-shot on Batting /
  Bowling / Fielding — landings now open all-time. User opt-in via
  FilterBar "last 3" button replaces the auto-apply.
- **FilterBar "last 3 seasons" button.** Scope-aware quick-select.
  Respects every FilterBar field (gender / team_type / tournament /
  filter_team / filter_opponent / filter_venue / series_type). On
  `Ind v Aus ICC` → last 3 WC meetings (2013/14, 2015/16, 2024), not
  last 3 calendar seasons.
- **Teams page search bug.** Swapped inline `<input>` for the
  existing `<TeamSearch>` component (matches `/players` pattern). No
  more "Pakistan" appearing twice when on `/teams?team=Pakistan`.
- **Commit cadence + REG→NEW flip workflow notes.** Two new CLAUDE.md
  sections: "Commit cadence" (commit as feature completes, not in
  bulk) and "Intentionally changed response shape?" docs hook under
  Keeping docs in sync — the regression runner reads HEAD-side
  `urls.txt`, so an uncommitted REG→NEW flip is invisible.
- **Matches-tab pagination on Series + Venue dossiers.** Both tabs
  previously hard-coded `limit: 50, offset: 0` with no controls, so a
  334-match T20 World Cup or 178-match Wankhede Stadium silently
  truncated. Added prev/next controls mirroring the `/matches` page
  pattern: local `matchesOffset` state in each dossier, reset on
  `filterDeps` change, range text now reads "Showing 51–100 of 334" not
  just "Showing 50 of 334". Offset is component-local (not in URL)
  matching Matches.tsx.
- **Matches-tab polish follow-ups.** Four tightly-scoped fixes:
  (1) `/venues` viewport — the page was using `.wisden-page` (42rem
  max) while every other data page uses `max-w-6xl` (72rem); swapped.
  (2) Pagination now lives in the URL as `?page=N` on both dossiers —
  tabs already URL-share, so pages should too. Deep-linked `?page=3`
  survives via a prev-deps-key ref (a simple first-render skip ref
  gets clobbered by React StrictMode's double effect-invocation in
  dev, falsely treating the remount as a filter change and resetting
  the page).
  (3) `ScopeStatusStrip` gains Tab + Page segments so you can see
  where you are without reading the URL bar, and the copy-link button
  carries those parts too.
  (4) New **per-row `(ed)` link** after each team name on both
  dossiers' Matches tab — muted italic, scoped to THAT match's
  tournament + season (independent of the FilterBar season window).
  Essential for rivalries: an Ind vs Aus row inside T20 WC 2024
  resolves its (ed) to "India at T20 World Cup, 2024", not to the
  rivalry window. Rivalry `Tournament` column renamed `Edition` to
  match this framing (dropped entirely in single-tournament context,
  as before).

### Shipped 2026-04-20 (evening — Matches + Records + row-scope polish)

Follow-up arc on the (ed) convention, unified through TeamLink /
PlayerLink phraseLabel, propagated into every dense table that
surfaces row-specific context. Commits `74c5666` … `5708f56`.

- **Score component.** Shared `<Score team1Score team2Score matchId?
  title?>` renderer ("185/6 │ 180/5" with a muted U+2502 vertical).
  Replaces ad-hoc score strings across `/matches`, dossier Matches
  tabs, Records Final column, Champions Final column, Knockouts
  Date-and-Score cell. When `matchId` is passed the whole score is
  a scorecard link; when it isn't (row is already inside a
  click-through `<tr>`) the score is plain text. Score separator
  gets its own muted class so the numbers carry the weight.
- **(ed) unified through TeamLink.phraseLabel.** Initial `teamEdHref`
  + `EdTag` sibling helpers retired after user pushback on mechanism
  proliferation. TeamLink grows a `phraseLabel` prop (string OR
  `(tier, i) => string`) that swaps the rendered phrase text while
  keeping the href + tooltip from `resolveScopePhrases`. `TeamWithEd`
  local wrappers in TournamentDossier + VenueDossier call TeamLink
  with `{ subscriptSource: { tournament, season, team1: null, team2:
  null }, maxTiers: 1, phraseLabel: "ed", phraseClassName:
  "scope-phrase-ed" }`. The explicit `team1/team2: null` clears any
  FilterBar rivalry pair — without it, the bilateral-series concern
  in `resolveScopePhrases` drops the tournament from the URL in
  rivalry mode (wrong for a single-team destination). New CSS
  `.scope-phrase.scope-phrase-ed` renders small-caps +
  letter-spacing, mirroring the H2 block-subscript style that already
  reads as a scope marker ("AT INDIAN PREMIER LEAGUE").
- **Pagination in URL.** Matches tab offset moved from component
  `useState` to `useUrlParam('page')`. Deep-linked `?page=3` survives
  because the filter-change reset uses a prev-deps-key ref (a naive
  `isFirstRender` boolean gets clobbered by React StrictMode's dev
  double effect-invocation and wipes the page).
- **ScopeStatusStrip always-render + full-width.** Was hidden when no
  filter was narrowed (the copy-link button disappeared alongside);
  now always renders when FilterBar is visible, empty state reads
  "Showing: all-time". Outer `.wisden-scope-strip-wrap` carries the
  tinted bg so the strip sits flush at any viewport. Tab + Page
  segments added.
- **/venues viewport.** Was `.wisden-page` (42rem, editorial) while
  every other data page uses `max-w-6xl` (72rem); swapped.
- **Records tab.** Backend `/series/records` rows gain `tournament`
  + `season` per row (scalar additions to each SELECT; best-bowling
  gets a new outer `LEFT JOIN match m2` since its CTE didn't carry
  event_name). Partnership + most-sixes rows additionally split
  `teams` into explicit `team1`/`team2`. Frontend adds an **Edition**
  column (season alone in single-tournament mode, "Tournament,
  Season" in rivalry) + `(ed)` after every team name in all 7 tables
  via the same `TeamWithEd` helper.
- **Overview Knockouts + Champions by season.** Knockouts now carries
  `team1_score` / `team2_score` per row (scalar subqueries, same
  pattern as records). Date column renamed "Date and Score" —
  single-cell `<date-link> · <Score>` inline composition with a muted
  middle-dot separator, both linked to the scorecard. Champions by
  season gains `team1` / `team2` / `team1_score` / `team2_score` /
  `date` on every row. Table columns settled at Season · **Final**
  (team1 ED v team2 ED) · Champion · **Date and Score**. Champion /
  Winner cells drop the (ed) subscript — those teams already appear
  in the Match column's (ed) pair, so duplication is removed.
- **/matches Edition column + (ed).** The md+ Tournament column
  renamed Edition (cell is season alone when FilterBar has a
  tournament pinned, otherwise `Tournament, Season`, linked to that
  edition's `/series?tournament=X&season_from=Y&season_to=Y`). Team
  links swap to TeamLink with the same subscriptSource +
  phraseLabel="ed" pattern. Wrapping span `onClick={stop}` preserves
  row-click-to-scorecard.
- **EdHelp caption.** New `<EdHelp />` component emits a small
  italic-serif-muted caption explaining the convention ("<ed> after a
  team name opens that team's page scoped to the row's edition…").
  Mounted under Knockouts / Champions H3s, at the top of the Records
  tab (covers all 7 tables), below the Matches-tab pagination line,
  and above the /matches table.
- **PlayerLink structural parity with TeamLink.** PlayerLink gains
  the four TeamLink props it didn't have: `maxTiers`, `phraseLabel`,
  `phraseClassName`, `seriesType`, `keepRivalry` (default true to
  preserve prior behavior). Defaults preserve every existing call
  site; the addition primes Batters / Bowlers / Fielders per-row
  (ed) when we walk those tabs.
- **Cross-cutting principle written down.** New top-level section in
  `internal_docs/design-decisions.md`: *Filters scope the summary;
  rows link to their own edition.* FilterBar narrows cumulative
  stats; row-specific cells raise to their own nearest edition. Also
  saved as a feedback auto-memory entry.
- **Regression choreography.** Four REG↔NEW flips landed as separate
  earlier commits ahead of each shape change: `7013f1d` (records
  REG→NEW, by_season NEW→REG), `8912c67` (3 tournament summaries
  REG→NEW for champions_by_season + knockouts extensions),
  `f2eb5d7` (3 rivalry summaries REG→NEW once knockouts populated).
  `./tests/regression/run.sh series` final report: 21 REG matched,
  0 drifted, 6 NEW changed, 0 NEW unchanged.
- **Link audit.** End of session: `internal_docs/link-audit.md`
  — complete page-by-page walk of every main tab + subtab, what
  every Link/navigate() target is, what scope it carries, whether
  the scope flows from ambient FilterBar / row override / hard-coded
  tile. Reference document for comparing future work against the
  established conventions.

### Shipped 2026-04-21 (later — Series > Batters "Picked batter" tile)

- **Series dossier Batters subtab gained a "Picked batter" slot** in
  the upper-left of a new 2×2 grid. Restructured from a 3-cell
  asymmetric grid (By runs / By average / By strike rate) to 4 cells:
  Picked batter · By runs · By average · By strike rate.
- **Picker UX:** scope-aware typeahead feeds the upper-left card; once
  a batter is picked, the search input empties and the player's
  scoped stats render as a one-row `DataTable` with the same columns
  as the leaderboards (Runs / Balls / Outs / Avg / SR). URL param
  `series_batter=<person_id>` makes the pick share-linkable.
  Out-of-scope case (user tweaks filters after picking) renders an
  italic empty-state card with an "× clear" affordance, keeping the
  pick addressable rather than silently dropping it.
- **Backend — scope-aware player search.** `/api/v1/players` extended
  to accept FilterBar + aux scope (same param set as
  `/series/*-leaders`). When any field is set, narrows to people who
  appeared on either team in scope matches. `scope_where` is computed
  from raw filter fields (not the WHERE clause) because
  `filters.build(has_innings_join=True)` emits a baseline
  `i.super_over = 0` clause; treating a baseline-only clause as
  "scoped" would have slowed every unscoped search AND flipped
  `innings` counts vs the legacy query (Kohli 378 → 375 on the first
  pass — REG harness caught it before ship).
- **Backend — new `GET /api/v1/series/batter-scope-stats`** (person_id
  required + the same scope params). Returns one BattingLeaderEntry
  row, or `{entry: null}` when the player has no deliveries in scope.
  Shaped identically to `/series/batters-leaders` rows so the
  frontend card reuses the leaderboard cell renderers.
- **Frontend — `PlayerSearch` gained optional `scope` prop.** Forwarded
  to `searchPlayers(q, role, scope)` → `/api/v1/players` querystring.
  Scope is `JSON.stringify`-keyed in the debounce effect so mid-type
  scope changes (e.g. filter tweak while dropdown open) refetch.
- **Regression: 25/25 REG matched on players suite, 16/16 REG on
  series suite.** Picker browser-verified end-to-end (scope exclusion
  for "Villiers" on T20 WC 2022-2026, deep-link round-trip,
  out-of-scope empty state, clear button).
- **Bowlers + Fielders tabs deliberately unchanged this commit** —
  follow-on commits 2/3/4 will add the matching pickers there, plus
  the fielders layout reshuffle and a new by-run-outs leaderboard.
- **Bowlers picker (follow-on commit).** Same shape as Batters:
  2x2 grid (Picked bowler + By wickets + By strike rate + By
  economy); URL param `series_bowler`; new endpoint
  `/api/v1/series/bowler-scope-stats`. `PickerSlot` component
  factored out in the previous commit handles the UI; only a new
  endpoint + URL-wire + 2x2 restructure needed here.
- **Fielders picker + layout reshuffle (follow-on commit).** Picker
  upper-left; "By dismissals (all)" moved from its previous row-1-left
  slot to row-1-right; "By keeper dismissals" moved from row-1-right
  to row-2-left. Row-2-right is intentionally blank in this commit —
  the next commit adds a new "By run-outs" leaderboard there. URL
  param `series_fielder`; new endpoint
  `/api/v1/series/fielder-scope-stats` returning a
  FieldingLeaderEntry with the full breakdown (Total / C / St / RO / C&B).
- **By run-outs leaderboard (follow-on commit).** `fielders-leaders`
  response gains a `by_run_outs` array — same aggregate shape as
  `by_dismissals`, sorted by `run_outs DESC` with tiebreak on total,
  HAVING `run_outs > 0` so the tail isn't padded with zeros. Lands
  in the Fielders tab lower-right slot, completing the 2x2 grid.
  REG flip for `series_fielders_leaders_ipl` (REG→NEW) was landed
  in a preceding commit per the project convention on shape changes.
- **Fielder scoped search: broadened to matchplayer (post-deploy
  fix).** Issue caught on prod: typing "jadeja" in Fielders picker
  at T20 WC Men 2021/22+ returned no results, because the scoped
  `/players?role=fielder` path required ≥1 `fieldingcredit` in
  scope and Jadeja's 11 WC matches yielded zero dismissals. Fix:
  for `has_scope=True` fielder searches, join `matchplayer` instead
  (fielding is universal — everyone in the XI fields regardless of
  whether they took a catch). `/series/fielder-scope-stats` now
  zero-fills the entry for squad members with no credits rather
  than returning `{entry: null}`. Out-of-scope players (no
  matchplayer entry at all) still null. Batter/bowler scope logic
  unchanged — role-specific activity is still the natural universe
  there.
- **Active-URL / dormant-session picker model.** User observation:
  `series_batter`/`series_bowler`/`series_fielder` were all
  co-habiting the URL regardless of which subtab was active, leaking
  inactive picks into share links. New model: the URL carries ONLY
  the active tab's pick; the other two live in `sessionStorage`
  (keys `cricsdb:series_{batter,bowler,fielder}`). Tab-switch
  migration effect (keyed on `currentTab`, `replace` mode — it's
  finishing the tab-switch, not a new history step) strips
  non-current picks from URL (stashing to session) and restores
  the incoming tab's pick from session. User-initiated picks /
  clears push the URL AND mirror to session via the
  `pickBatter`/`pickBowler`/`pickFielder` wrappers. Back-button
  walks every real user step with no dupe dead-entries. Deep-link
  self-correction: a URL carrying picks for the wrong tab (e.g.
  `?tab=Fielders&series_batter=X`) has the non-current param
  stripped on mount, stashed to session so it's still there if the
  recipient clicks Batters. New `× clear` affordance always visible
  next to the search input when a pick is active (was previously
  only in the out-of-scope empty state). Documented in
  `internal_docs/url-state.md` under "Active-URL / dormant-session
  state (the Series picker model)".

### Shipped 2026-04-21 (Series tab refactor + Partnerships/Records expansion)

Continuation of 2026-04-20's (ed)/phraseLabel arc. Two arcs this day:
first a cleanup pass where the Series tab dropped every remaining raw
`<Link>` in favour of TeamLink / PlayerLink / SeriesLink, then a
feature pass on Records + Batters + Bowlers + Fielders + Partnerships
subtabs. Commits `5179683` … `ca0b785`.

- **`internal_docs/links.md` — canonical link-component contract.**
  New reference doc pinning the "name-is-all-time, phrase-is-scoped"
  invariant, the `SubscriptSource` per-row override model, and the
  `phraseLabel` rendering-only override (used for `"ed"`, `"(6)"`
  bracketed counts, `"N m"` Groups counts, `"(won/played)"` Editions
  counts, etc.). Documents anti-patterns: raw `<Link to="/teams…">`,
  local URL helpers, inverting the name/phrase direction. CLAUDE.md
  gained a pointer directing future sessions to read it before
  touching any `/teams` / player / `/series` navigation.
- **Series refactor.** Migrated every remaining non-TeamLink/PlayerLink
  cell on `/series` to the shared components. Specifically:
  - Landing `TournamentTile` "Most titles (N)" and "Winner: X" —
    inversions retired; name goes all-time, bracketed-count / (ed)
    rides `phraseLabel`. Same fix on `RivalryTile` Winner.
  - Overview rivalry by-team tile title (was `teamLinkHref` + raw
    Link) → `TeamLink` with `keepRivalry` + rivalry-oriented source.
  - Overview Groups "N m" and Participating-teams "(N)" use
    `phraseLabel`.
  - Editions "(won/played)" + "(runs)" + "(wickets)" → phraseLabel.
  - Points tab team column (was plain text) → `TeamLink` with
    phraseLabel="ed".
  - Partnerships tab (biggest deviation pre-refactor): both tables
    now render batter pair via `PlayerLink compact` × 2 and match
    teams via `TeamWithEd` × 2 through two local closures
    `batterPair()` / `matchTeams()` that share scope computation.
  - Records: Largest-partnerships batter pair → `PlayerLink` × 2
    rivalry-oriented; Best bowling bowler cell → `PlayerLink` with
    edition subscriptSource + phraseLabel="ed".
  - Dead helpers deleted: `renderBatter`, `renderBatterPair`,
    `renderVsTeams`, `teamLinkHref`, `teamUrl`. File-level comment
    at `TournamentsLanding.tsx:11–16` that defended the inversion
    removed along with it.
- **Records — best individual batting + cap bump.** New backend SQL
  in `/series/records` returns `best_individual_batting` (top-N
  single-innings scores, tie-break by balls ASC so 87(40) ranks above
  87(60), formatted as `"175* (65)"` with not-out asterisk). Frontend
  renders a sibling table in RecordsTab mirroring Best bowling's
  column shape (Score | Batter | Edition | Date). Records top-N cap
  bumped 5 → 10 so the tab reads more as a leaderboard than a
  podium.
- **Series subtab caps standardized at 20 (up from 10).** Batters,
  Bowlers, Fielders, Partnerships-top all pushed to 20 rows. Records
  stays at 10 — it's still a podium-feel table. Rationale captured in
  `design-decisions.md`.
- **Batters tab — "By runs scored".** New primary table, placed first
  in BattersTab to match the Orange-Cap mental model. Same
  min_balls=100 threshold as the other two lists, tie-break by balls
  ASC. Extract `batterCell()` closure so all three tables share the
  `PlayerLink` render.
- **Bowlers tab — "By wickets taken".** Mirror of Batters' By-runs:
  placed first, Purple-Cap framing. Tie-break by economy ASC.
  `bowlerCell()` closure extracted.
- **Partnerships tab — top 10 per wicket.** New backend endpoint
  `/series/partnerships/top-by-wicket` returns the top-N partnerships
  **per wicket number** (1–10) in a single round-trip using
  `ROW_NUMBER() OVER (PARTITION BY wicket_number)`. Rendered as ten
  h4 sub-tables ("1st wicket" through "10th wicket") below the
  existing "Top partnerships" section. All sub-tables share the
  `batterPair()` / `matchTeams()` closures so the per-row ed phrase
  applies identically.
- **Partnerships polish.** "Avg" column header expanded to "Average".
  Batter-pair cells gained the `ed` phrase after each name (matching
  the team-pair `ed` convention on the same row); initial parens
  were removed on user feedback for visual symmetry — row now reads
  `V Kohli ed & AB de Villiers ed | RCB ed v Gujarat Lions ed`.
- **`internal_docs/link-audit.md` re-audit (Series section only).**
  Previous audit was stale against the refactor; rewrote the Series
  section line-cited against current files. Top of doc gained a
  verification-status banner + a grep-only spot-check of parallel
  deviations STILL live outside Series — Home.tsx's locally-shadowed
  `TeamLink`/`PlayerLink`, Venues dossier's `teamLink()` helper,
  Batting/Bowling/Fielding innings-list Opponent + matchup cells,
  Teams.tsx partnerships + roster. Flagged for the next session.
- **Regression discipline.** Missed the REG→NEW flip before shipping
  shape changes (three endpoints gained new top-level keys: records
  `best_individual_batting`, batters-leaders `by_runs`, bowlers-
  leaders `by_wickets`). Verified retroactively by
  `git checkout <pre-session> -- api/routers/tournaments.py`, curl
  capture, Python dict diff → stripped-of-new-keys HEAD == OLD for
  all three. Harness run with realigned urls.txt: 16 REG matched, 0
  drifted. Next backend change: flip REG→NEW in a preceding commit.
- **Commit cadence.** User flagged twice that batched commits weren't
  landing per-feature. Ten+ clean commits landed after that, one
  logical change per commit. `git add -p` (or revert-restore when the
  commits share a file) is the splitting mechanism going forward
  — not large end-of-session dump commits.

### Shipped 2026-04-25 (Teams Compare — Scoped Slots: per-column scope override)

Implementation of `internal_docs/spec-team-compare-scoped-slots.md`
in five clean commits:

- **Commit 1** (`82b8538`) — `useCompareSlots` hook + URL parsing +
  legacy migration. New `compareN` / `compareN_<filter>` URL shape
  resolved into per-slot `{kind, entity, scope, overrides}`. Legacy
  `compare=A,B` / `avg_slot=1` URLs auto-rewrite via a one-shot
  useRef-gated useEffect (`replace:true`). Slot contiguity also
  normalized (`compare2` alone shifts to `compare1`). 3-column cap
  enforced in the picker.
- **Commit 2** (`ed231b8`) — TeamCompareGrid refactor + unified
  `CompareSlotColumn`. Drops the old `CompareColumn` /
  `AvgCompareColumn` split; one component handles both kinds.
  Three useFetch slots iterating over `[primary, slot1, slot2]`,
  each fetcher discriminating on `slot.kind`. Each slot fetches
  against its RESOLVED scope, not primary's — wiring in place for
  per-slot scope override without further refactoring. Legend
  reworded to "in each column's scope".
- **Commit 3a** (`53d1e2a`) — `SlotHeaderChip` diff rendering.
  Italic sub-line under team-slot names showing what differs from
  primary (e.g. "· 2025" or "· IPL 2025 · @ Wankhede"). Avg slots
  suppress chip (label already encodes scope).
- **Commit 3b** (`8d28c9c`) — Default first-load auto-fill
  `compare1=__avg__`. Once-per-mount via useRef gate; ✕ within
  session does NOT bring it back; reload re-fires.
- **Commit 3c** (`737b6c3`) — `AddCompareSlot` (replaces
  `AddTeamComparePicker`) with 4 quick-picks + "Different team"
  TeamSearch. `SlotScopeEditor` inline panel with the 5
  overridable filters mounted under each non-primary column when
  ✎ is clicked. End-to-end: load-bearing canary verified —
  Australia at ICC Men's T20 World Cup primary 2024 → "Same team,
  previous season" lands at `compare1_season_from=2022/23` (NOT
  calendar-prior 2023). The "previous season" lookup walks
  `/api/v1/seasons` backward by one — handles biennial events,
  BBL `2024/25` strings, sparse associate teams uniformly.

**Backend zero-touch.** Every endpoint already takes `FilterParams`
per-request via `Depends`; each slot's request is independent and
computes its own `scope_avg` against the slot's scope. No new SQL,
no new endpoints, no envelope shape changes.

**Tests**: `tests/integration/team-compare-average.sh` 16/16
(Test 2 retargeted to walk the new add-panel: open the picker,
click the quick-pick). All four pre-flight regressions and
integration suites green.

**Known follow-ups**:
- `SlotScopeEditor`'s tournament dropdown uses
  `/api/v1/tournaments?team=X` which can return a different
  canonical `event_name` than the URL carries (e.g. "T20 World Cup
  (Men)" vs "ICC Men's T20 World Cup"). Pre-existing data
  inconsistency the editor surfaces but doesn't cause; non-blocking.
- The picker's "Custom" form (type toggle + 5-field scope editor
  in the SAME panel as quick-picks) was deferred to a follow-up.
  Today's flow: add via quick-pick (e.g. Different team), then
  click ✎ to override scope. Two clicks instead of one but covers
  every workflow.
- Docs sync for this commit also touched CLAUDE.md, codebase-tour,
  design-decisions, url-state, user-help.

### Shipped 2026-04-25 (Teams tabs — delta chips on StatCards + by-phase / by-wicket envelope)

Two post-Spec-1 quick wins exploiting the per-metric envelope shipped
in Phase 2B:

**Quick Win 1 — single-team Teams tab StatCards.** Previously the
delta_pct + scope_avg fields on the 5 compare endpoints were only
consumed by the Compare grid. Wired up `MetricDelta` (new shared
component, frontend/src/components/MetricDelta.tsx) as StatCard
subtitles on the per-discipline tabs (Batting / Bowling / Fielding /
default summary). Single-team views now show "vs avg X.YZ ↑ +N.N%"
under each rate / average StatCard, color-coded by direction. Counts
(Wickets, Catches, Hundreds) stay flat — direction=null on the
envelope, MetricDelta returns null.

Backend bug fix surfaced: wides_per_match + noballs_per_match's
scope_avg was double the team-comparable value (league pool counts
both bowling sides per match). Moved `_half()` helper to module-
level near `_safe_div`, applied it to wides/noballs in addition to
catches/stumpings/run_outs. RCB IPL 2024 wides went from -44% delta
to a sensible +11.2%.

**Quick Win 2 — by-phase + by-wicket envelope.** Migrated
`/teams/{team}/batting/by-phase`, `/bowling/by-phase`, and
`/partnerships/by-wicket` to envelope-shape per phase / wicket row.
Each row's numeric rate metrics (run_rate / economy / boundary_pct /
dot_pct / avg_runs / n) wrap_metric'd against the in-scope league
baseline. Counts on those rows (runs / balls / wickets / fours /
sixes / best_runs) stay flat — same direction-null treatment as the
summary endpoints' counts. New per-phase / per-wicket aggregator
helpers (`_batting_by_phase_aggregates`, `_bowling_by_phase_aggregates`,
`_partnerships_by_wicket_aggregates`) take `team: str | None` and
get called twice per endpoint for team + scope_avg.

Frontend types split: TeamBattingPhase / TeamBowlingPhase /
PartnershipByWicket gain MetricEnvelope on metric fields; new
ScopeBattingPhaseFlat / ScopeBowlingPhaseFlat preserve the unchanged
flat shape on `/scope/averages/*/by-phase` (which intentionally
stays flat — it IS the baseline). PhaseBandsRow + PartnershipByWicketRows
handle both shapes via `rv()` (read value) + `env()` (extract
envelope) helpers — same component renders team chips AND avg-column
raw numbers without dispatch.

Verified RCB IPL 2024 Compare:
- PP RR 9.73 ↑+2.7%, Mid RR 9.26 ↑+4.9%, Death RR 12.55 ↑+12.0%
- PP Econ 9.77 ↑+3.2%, Mid Econ 9.53 ↑+7.9%, Death Econ 10.93 ↓-2.5%
- 1st wkt 47.1 ↑+33.1% (RCB openers way above league)
- 3rd wkt 46.7 ↑+41.1% (Kohli at 3 — strong)
- 2nd wkt 17.1 ↓-38.3%, 8th wkt 7.6 ↓-27.6% (clear weakness)

Regression: REG→NEW flip on 5 affected URLs (commit `e03aaff`),
shape change (`2d9e335`), NEW→REG cleanup (`12424c3`). Final state:
38 REG / 0 NEW in teams/, 29 REG / 0 NEW in scope-averages/.
Integration: 16/16 still pass.

### Shipped 2026-04-24 (Teams Compare — Spec 1 / Phase 2B: envelope migration)

- **`api/metrics_metadata.py`** — single-source-of-truth direction
  map + `wrap_metric()` helper that produces the per-metric envelope
  `{value, scope_avg, delta_pct, direction, sample_size}`. Counts
  (`fours`, `wickets`, `total_runs`, etc.) get `direction=null` so
  delta_pct stays null — team-count-vs-league-total is ~10x scaled
  and the percentage misleads. Rates / averages (`run_rate`,
  `economy`, `boundary_pct`, etc.) get the real direction.
- **5 team-compare summary endpoints migrated** to envelope shape:
  `team_summary`, `team_batting_summary`, `team_bowling_summary`,
  `team_fielding_summary`, `team_partnerships_summary`. Each runs an
  extra "scope_avg" SQL pass (helpers extracted into
  `_batting_aggregates`, `_bowling_aggregates`, `_fielding_aggregates`
  that take `team: str | None`; team=None produces the league pool).
  Identity-bearing nested objects stay flat. Per-match fielding rates'
  `scope_avg` is halved (`_half()` helper) because the league pool
  counts both fielding sides per match — team-side comparable is /2.
- **Frontend types + every consumer updated**: `types.ts` adds the
  `MetricEnvelope` interface and wraps the 5 summary interfaces' metric
  fields. Consumers (`TeamSummaryRow`, `Teams.tsx` per-discipline
  tabs, `AddTeamComparePicker` probe, `teamUtils.ts` discipline gates)
  read `.value` off the envelope. Mechanical `s.field` → `s.field.value`
  refactor surfaced ~50 call sites via the typechecker; `tsc -b`
  green.
- **Regression**: REG→NEW flip on 15 affected URLs landed in a
  preceding commit (`ee78b7f`). Teams suite: 29 REG matched, 9 NEW
  changed, 0 drifted, 0 NEW unchanged. Scope-averages suite: 4 REG
  matched, 6 NEW changed (the team-control URLs that just shape-
  changed), 0 drifted; 19 "NEW unchanged" entries are Phase 2A
  introductions that are now stable in HEAD — flipped to REG in a
  follow-up cleanup commit.
- **Integration**: `tests/integration/team-compare-average.sh`
  16/16 still pass — the UI consumes `.value` everywhere now and
  renders identically (envelope is invisible to Spec-1 UI).
- **Spec 2 ready**: every consumer can now read `delta_pct` /
  `direction` / `sample_size` off the envelope without an endpoint
  migration. Player compare with position-matched baseline (Surface
  1 of `outlook-comparisons.md`) is the next natural pickup.

### Shipped 2026-04-24 (Teams Compare — Spec 1 / Phases 2A + 3: API + UI)

- **Phase 2A — `/api/v1/scope/averages/*` router family** (12 new
  endpoints) mirrors `/teams/{team}/*` with the team filter dropped —
  pool-weighted league baselines for the same FilterBar scope. Plus
  the missing `/teams/{team}/partnerships/by-season`. Helpers
  `_team_innings_clause` + `_partnership_filter` in `teams.py`
  refactored to accept `team: str | None`; team=None drops the team
  clause cleanly. Behaviour-preserving when team is given: regression
  10/10 REG matched byte-identical, 19/19 NEW changed.
- **Phase 3 — Average-team column on Teams > Compare.** New URL param
  `avg_slot=1` adds a fourth column whose label is scope-computed
  ("Indian Premier League 2024 avg"). `AddTeamComparePicker` gets a
  "+ Add league average" button. `getScopeAverageProfile()` mirrors
  `getTeamProfile()`, fetching all 12 endpoints in parallel.
  `AvgSummaryRow.tsx` renders rows with the same labels as
  `TeamSummaryRow.tsx` so columns vertically align — fields that
  don't apply at scope (Wins, Losses, Best pair) render `-`. The
  "Win %" row in the avg column is repurposed to bat-first win
  percentage — the most informative league-level signal at that row
  position.
- **Phase 3 — Phase bands** (PP / Mid / Death) render as sub-rows
  under Batting and Bowling in every column via
  `PhaseBandsRow.tsx`. Backed by existing
  `/teams/{team}/{batting,bowling}/by-phase` + new scope-avg
  siblings.
- **Phase 3 — Partnership-by-wicket expansion** (1st-10th wicket)
  renders as 10 sub-rows under the Partnerships row in every column
  via `PartnershipByWicketRows.tsx`. Small-sample suppression: when
  fewer than 30 partnerships at a wicket position have formed in
  scope, the average column shows `—` (with tooltip explaining); team
  columns never suppress.
- **Phase 3 — Season-trajectory strip** (`SeasonTrajectoryStrip.tsx`)
  renders below the grid: two `LineChart` panels — Batting RR by
  season and Bowling Econ by season — with one line per compare
  column (teams + avg). Hidden under single-season filters (no
  trajectory to draw). Multi-season scope via `season_from <
  season_to` lights it up.
- **No envelope migration in Spec 1.** Each metric on the 5 existing
  compare endpoints stays flat (`run_rate: 9.59` not
  `run_rate: {value: 9.59, scope_avg: 9.56, …}`). Phase 1 UI doesn't
  render `delta_pct` / `direction` / `sample_size`, and migrating
  envelope would touch every existing UI consumer of the 5 endpoints
  for zero rendered benefit. Phase 2B (envelope migration + REG→NEW
  flip + frontend consumer updates) sequences before Spec 2 starts —
  see `internal_docs/outlook-comparisons.md` for the consumers that
  will need it.
- **Test coverage**: `tests/regression/scope-averages/urls.txt`
  (29 entries, 19 NEW + 10 REG control); `tests/integration/team-
  compare-average.sh` (16/16 asserts pass) — exercises base compare
  grid, avg-add via picker, phase bands, partnership-by-wicket,
  trajectory strip visibility under single vs multi-season,
  scope-computed label respecting gender + team_type.

### Shipped 2026-04-24 (Teams Compare — Spec 1 / Phase 1: schema + populate)

- **Two specs written first.** `internal_docs/spec-team-compare-average.md`
  (build-ready, ~560 lines) covers the Teams Compare average-team
  column, phase bands, season-by-season trajectory, response envelope
  (`value` + `scope_avg` + `delta_pct` + `direction` + `sample_size`),
  the `METRIC_DIRECTIONS` single-source-of-truth module, and the
  three-commit rollout. `internal_docs/outlook-comparisons.md` (~240
  lines) is the looser doc collecting the six cross-app surfaces
  (player compare with position matching, leaderboard Δ columns,
  venues baseline, H2H baseline, scorecard expected-SR, tournament
  era framing) that share the same baseline API. Path A chosen for
  scheduling: Spec-1 schema + populate landed alongside, Spec-1 API
  + UI to follow.
- **`player_scope_stats` table.** New deebase table with composite PK
  `(person_id, scope_key)`, where scope_key = blake2b/12-hex hash of
  `(tournament || season || gender || team_type)`. Covers batting
  (runs, legal_balls, dots, 4s, 6s, dismissals, avg_batting_position,
  innings_by_position_json), bowling (balls, runs_conceded, wickets,
  dots, boundaries, powerplay/middle/death overs), fielding (catches,
  runouts, stumpings, catches_as_keeper, matches_as_keeper). Indexes
  on `(scope_key, avg_batting_position)` + `scope_key`.
- **`scripts/populate_player_scope_stats.py`** with `populate_full()`
  + `populate_incremental()`. Auto-called by `import_data.py` (after
  partnerships) and `update_recent.py` (after partnership_incr).
  Position derivation: per innings, position N is the order of
  appearance — striker on first delivery is position 1, non-striker
  is 2, each subsequent newcomer is N+1. Bowler `wickets` excludes
  run out / retired hurt / retired out / obstructing the field;
  batter `dismissals` excludes retired hurt / retired out — matches
  existing batting/bowling routers.
- **Incremental strategy: scope-replace, not delta-upsert.** When
  matches in scopes {A, B} are added, identify the touched
  scope_keys, delete every PSS row for those scope_keys, and
  re-aggregate from scratch over ALL matches in those scopes. Exact
  and avoids drift if a future match correction lands in an already-
  populated scope. Cost: ~22 affected (person, scope_key) cells per
  new match — negligible against the existing `update_recent.py`
  budget.
- **NOT consumed by any endpoint in Spec 1.** The table is built and
  maintained but no API code reads it. Spec 1's user-visible feature
  (Teams Compare average-team column + phase bands + season
  trajectory) runs entirely on the existing delivery + partnership
  + covering indexes. The table exists so Spec 2 (cross-app
  comparisons) starts with hot schema. Documented in
  `internal_docs/design-decisions.md` under "Path A".
- **Sanity tests.** New `tests/sanity/` subdir for data-layer
  pool-conservation + round-trip tests on denormalized tables (sibling
  to `tests/regression/` URL md5-diff and `tests/integration/`
  agent-browser flows). `tests/sanity/test_player_scope_stats.py`
  covers (a) pool conservation across batting runs / legal balls /
  runs_conceded / bowler wickets / dismissals — verified PSS sum
  equals delivery+wicket sum byte-for-byte; (b) populate_incremental
  on a scope's match_ids reproduces populate_full's rows exactly;
  (c) cross-scope isolation — touching scopes A,B leaves an
  unrelated scope C byte-identical. All-pass on prod-snapshot DB
  copied to /tmp.
- **Validated against prod snapshot.** Copied
  `~/Downloads/t20-cricket-db_download/data/cricket.db` to
  `/tmp/cricket-prod-test.db`, ran populate_full → 65,026 rows in
  20.4s. Pool conservation matched on all 5 metrics. Round-trip and
  cross-scope isolation pass. Cross-checked V Kohli's IPL 2016: PSS
  reports 966 runs / 637 balls; existing batting-router-equivalent
  SQL agrees byte-identical (the 7-run delta from the popular 973
  record is in cricsheet's source, not our code path).

---

## Build-ready specs (queue)

(Empty — `spec-team-compare-scoped-slots.md` shipped 2026-04-25,
see session log.)

## Known issues / live TODO

Lifted from CLAUDE.md L182-189 on 2026-04-19. Items here are
acknowledged-but-deferred bugs and small follow-ups that don't yet
warrant their own letter; the live items at the top of the file
remain the primary source for in-flight enhancements.

- **`wicket.fielders` is double-JSON-encoded in the DB.** `import_data.py` calls `json.dumps(w_data.get("fielders"))`, but deebase's JSON column type also serializes, so the stored string is e.g. `'"[{\"name\": \"SL Malinga\"}]"'` — a JSON string whose contents are themselves a JSON-encoded list. The matches scorecard router (`api/routers/matches.py:_build_dismissal_text`) works around this with `json.loads` twice. Fix: drop the `json.dumps(...)` wrapper in `import_data.py`, rebuild the DB, remove the double-decode branch. Tracked as enhancement C above.
- Bowling scatter chart (vs Batters) — enhancement D was partial; see roadmap.
- Player search returns abbreviated cricsheet names ("V Kohli" not "Virat Kohli"). Tracked as enhancement E.1 above.
- Inter-wicket analysis is Python-side processing (~200ms for top players) — could be slow under load. Consider moving to SQL or caching.
- Consider adding compound indexes on `(delivery.bowler_id, delivery.innings_id)` for bowling queries, and `(partnership.innings_id, partnership.wicket_number)` (already has both separately).
- Admin at `/admin/` is behind HTTP Basic Auth (`ADMIN_USERNAME` + `ADMIN_PASSWORD` from `.env`). Fail-closed: missing env → 503. See `internal_docs/admin-interface.md`.

---

## Deferred / later-queue

Lifted from CLAUDE.md L248-253 on 2026-04-19. These are flagged-but-
not-scheduled enhancements; pull them up into the lettered list when
ready to ship.

- **More filters on `/matches`.** `filter_venue` already lands from Phase 2. Also consider result filter (won/lost/tied/NR from a team perspective), close-match filter, super-over filter, toss-outcome filter. Confirm scope with user before building.
- **O — Tournament-baseline comparison overlays** on team / batter / bowler / fielder pages. M shipped the per-tournament endpoints with explicit baseline reusability — call any `/api/v1/series/{summary,batters-leaders,…}` without a team filter to get the tournament-wide baseline, with one for the team's narrowed view (responses are shape-compatible). Frontend wiring needed: overlay league means on team-tab charts, add "vs league avg" columns to player tables, support "delta from league mean" colour mode on heatmaps. Design sketch in `internal_docs/design-decisions.md` "Team metrics need tournament baselines (revisit when /tournaments ships)".
- **Other "(revisit)" items** (see `internal_docs/design-decisions.md` for detail): win-% overlay on discipline tabs (correlates performance with winning), batter consistency stats (median / 30+ rate / dispersion), batter × bowler-type splits + bowler × batter-handedness splits (requires person-table enrichment from Cricinfo).
