# Enhancements roadmap

The A–O menu of cricsdb enhancements — shipped items stay here as
historical markers (with pointers to their specs), and the unshipped
items are triaged. CLAUDE.md keeps just a "next up" pointer.

The list is roughly ordered by value/effort. Pick the highest unshipped
one that fits the available time.

---

**A. Loading + error states across all pages.** _Done._ See
`docs/data-fetching.md` for the full pattern (useFetch hook, Spinner,
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
**innings grid** (see `docs/design-decisions.md` "Innings grid:
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
view) is shipped — see `docs/design-decisions.md` "Linking scatter
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
documentation in `docs/visual-identity.md`. Consistency rule: subject
in ink, connective in oxblood, hover to oxblood.

**K. Tournament-name canonicalization.** _Done._ Implemented in
`event_aliases.py` + `scripts/fix_event_names.py`, mirroring the
team-aliases pattern. Three competitions merged: NatWest T20 Blast /
Vitality Blast Men → Vitality Blast (English), MiWAY / Ram Slam → CSA
T20 Challenge (SA), HRV Cup / HRV Twenty20 → Super Smash (NZ). 784
rows updated; club-tournament count went from 27 to 21. See
`docs/design-decisions.md` "Team-name canonicalization across
renames" for the shared writeup.

**L. Fielding analytics page.** _Tier 1 + Tier 2 done._ `/fielding`
page with `fielding_credit` denormalized table (~118K rows),
`fielder_aliases.py`, `wicket.fielders` double-encoding fix, 7 API
endpoints (`api/routers/fielding.py`), frontend page with 6 tabs (By
Season, By Over, By Phase, Dismissal Types, Victims, Innings List).
Fielder search via `role=fielder` in `/api/v1/players`. Tier 1 spec:
`docs/spec-fielding.md`.

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
     auto-populate. Spec: `docs/spec-fielding-tier2.md`, worklist
     README: `docs/keeper-ambiguous/README.md`.

**M. Tournament analytics page.** _Next up._ New `/tournaments` page
with **two** route levels (decision made during the team-stats build —
flatten season into a filter rather than a separate route, mirroring
how Teams works): tournament listing → per-tournament overview that
scopes by season via FilterBar. Spec needs writing; first feasibility
cuts informed by the team-stats build are captured in
`docs/spec-team-stats.md`'s "Implication for tournaments" callout.
Tied to **enhancement O (baselines)** — the per-tournament-per-season
aggregates we compute here are exactly what the team tabs need for
tournament-mean comparison overlays.

**N. Team statistics — batting / bowling / fielding / partnerships.**
_Done (2026-04-14)._ Spec at `docs/spec-team-stats.md`, ~21h of build.
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
captured as "(revisit)" subsections in `docs/design-decisions.md`:
tournament baselines (enhancement O), win-% overlay on discipline
tabs, batter consistency stats (median / 30+ rate / dispersion),
batter × bowler-type and bowler × batter-handedness splits.

**O. Tournament-baseline comparisons across team / batter / bowler /
fielder pages.** Once enhancement M ships and we have
per-tournament-per-season aggregates, every team-tab chart should be
able to overlay the league mean as a reference line/band, every player
table should gain a "vs league avg" column, and the phase × season
heatmaps should support a "delta from league mean" colour mode. Detail
in `docs/design-decisions.md` "Team metrics need tournament baselines
(revisit when /tournaments ships)".

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
mount, writes to URL so FilterBar reflects it). FilterBar gained two
subtle text buttons — "all-time" clears just the season range,
"reset all" clears every filter — both appearing only when relevant.
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
`docs/perf-leaderboards.md` for the reusable pattern.
`update_recent.py --db <path>` flag added for smoke-testing against
a copy of the prod snapshot in `/tmp` before deploying (see
`docs/testing-update-recent.md`). Home-page gains two deep links:
"(players)" next to West Indies T20 WC 2016 and "MI men — players
over the years".
