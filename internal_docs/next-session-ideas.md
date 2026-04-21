# Next-session ideas — Head-to-Head tab walk, Teams tab, cross-tab audit

> **NO DEPLOYS** until the Series + Teams + H2H deep-dive completes.
> Per session memory, last reaffirmed 2026-04-20.

## NEXT SESSION agenda (in order)

Series tab deep-dive completed 2026-04-20 (pm + evening) — SeriesLink
shipped, tile conventions set, TournamentDossier Overview/Editions/
Groups/Knockouts/Participating-teams cells converted. Evening arc:
Score + EdHelp components, TeamLink/PlayerLink `phraseLabel` prop,
(ed) row-scope convention adopted across Matches tab, Records tab,
Overview Knockouts + Champions by season, `/matches`, Venue Matches.
Small-caps ED styling applied. Pagination URL-shared. Status strip
full-width + always rendered. Comprehensive link audit saved to
`internal_docs/link-audit.md` — use as reference when walking
remaining tabs. Next tabs to walk:

1. **Head-to-Head tab walk.** `/head-to-head` is the polymorphic tab
   with `mode=player` and `mode=team`. Verify that:
   - All team names use `<TeamLink>`, all player names use
     `<PlayerLink>` (compact where the page context already expresses
     scope, inline where the cell is a pivot).
   - Tile convention applies to the Common-matchups suggestion tiles
     when no teams are picked (stretched-link + inner TeamLink/
     PlayerLink per the Series-landing template — see
     `internal_docs/design-decisions.md` "Series-landing tile
     convention").
   - Team-vs-team mode reuses TournamentDossier correctly with the
     rivalry scope threaded through.
   - Innings-list tournament column already migrated to `<SeriesLink>`
     (2026-04-20 session); verify visually in the browser agent.
2. **Teams tab deep dive.** `/teams?team=X` — every team-mention
   should be a `<TeamLink>`, every player-mention a `<PlayerLink>`.
   Apply the tile conventions to Compare tile, Players-in-team grid.
   Verify deep-links from Series (e.g. "India at T20 WC, 2025/26")
   arrive with right filters populated.
3. **Cross-tab name-link invariant audit.** Across every tab, the
   bare name-as-link text must go to the entity's overall page
   (identity only — gender + team_type for teams, gender for
   players). Hunt down inline `<Link>` calls with extra scope params
   and convert them, or phrase-wrap them per the 2026-04-20 Winner-
   line convention.
4. **Venue-cell sweep** (deferred from 2026-04-18, partially done on
   2026-04-20 — Series Knockouts shipped) — Matches venue cells,
   HeadToHead by-match venue, anywhere else venue text is plain.
   Link to `/venues?venue={venue}` (dossier) or `?filter_venue={venue}`
   where contextual.
5. **Scorecard linkability API batch** (deferred from 2026-04-18) —
   `/api/v1/matches/{match_id}` response shapes for `player_of_match`,
   dismissal text, did-not-bat, fall-of-wickets to return `PersonRef`s;
   frontend wraps each in a compact `PlayerLink`. See
   `internal_docs/design-decisions.md`.
6. **filterDeps refactor (Option B)** — partially done.
   `useFilterDeps()` returns `FILTER_KEYS.map(k => filters[k])`,
   stable-memoized. Pages can gradually adopt it to replace their
   hand-rolled arrays.

## Series deep-dive — DONE 2026-04-20 (kept as reference scenarios)

> Series tab cell migrations shipped 2026-04-20 (pm). SeriesLink
> component introduced, tile conventions set, TournamentDossier
> Overview/Editions/Groups/Knockouts/Participating-teams converted.
> Commits `9107ca3`..`4d9f0e1`, plus design-decisions.md "Series-
> landing tile convention" for the stretched-link + phrase-wraps-name
> + title-hoists-scope patterns. Below stays as the canonical
> reference-scenario set for HEAD-to-head and Teams walks.

### Three reference scenarios

The same three URLs should be revisited on every change. They cover
the three container modes the design distinguishes:

1. **Bilateral rivalry**: India vs Australia (or Aus vs India — same
   page). URLs to test:
   - `/series?filter_team=Australia&filter_opponent=India&series_type=all&gender=male&team_type=international` (no narrowing — no subscripts)
   - `/series?...&series_type=bilateral` (1 subscript "in bilaterals" per team)
   - `/series?...&series_type=bilateral&season_from=2025/26&season_to=2025/26` (auto-pins tournament; should still show "in bilaterals" + "in bilaterals, 2025/26", NOT "at India tour of Australia")
   - `/series?...&series_type=icc&tournament=T20+World+Cup+(Men)&season_from=2024&season_to=2024` (2 subscripts "at T20 World Cup (Men)" + "at T20 World Cup (Men), 2024")

2. **Club tournament — IPL**:
   - `/series?tournament=Indian+Premier+League&gender=male&team_type=club` (tournament dossier; H2 "Indian Premier League" — no team links in H2; team cells in tables get "at IPL")
   - `/series?...&season_from=2024&season_to=2024` (IPL 2024 — table team cells should subscript "at IPL" + "at IPL, 2024")

3. **ICC tournament — T20 World Cup**:
   - `/series?tournament=T20+World+Cup+(Men)&gender=male&team_type=international` (T20 WC dossier; team cells get "at T20 WC")
   - `/series?...&season_from=2024&season_to=2024` (T20 WC 2024 — "at T20 WC" + "at T20 WC, 2024")

### Series tab cell migrations (queued)

In `frontend/src/components/tournaments/TournamentDossier.tsx`:

- ~15 call sites use the local `teamLinkHref` helper instead of
  `<TeamLink>`: H2 (already migrated, compact mode), by-team tile
  headers, Knockouts table (team1/team2/winner), Participating-teams
  chip grid, Champions-by-season, Matches tab (team1/team2/winner),
  Records `teamCell` (highest totals / lowest all-out / biggest wins),
  Editions champion/runner-up. Convert each to `<TeamLink>` with
  appropriate layout: `inline` for table cells; `compact` for tile
  headers where the tile body already expresses the page scope.
- Raw `/batting?player=X` and `/bowling?player=X` `<Link>`s in
  Editions (top scorer / top wicket-taker), Records (best bowling
  figures), Partnerships (`renderBatter` helper) → convert to
  `<PlayerLink>` so they get the existing letter-subscript treatment.
- The local `teamLinkHref` helper itself can be retired once all call
  sites are converted.

### Teams tab walk

`/teams?team=X` is a major destination from Series scope-link clicks.
Verify:
- The H2 of a Teams page should use a `<TeamLink compact>` (the H2 is
  the team identity; subscripts redundant).
- Every team-mention in a child cell (Match List opponent, vs
  Opponent, Compare columns) should be a `<TeamLink>` with
  appropriate layout.
- Every player-mention should be a `<PlayerLink>`.
- Deep-link arrival from Series with `series_type=bilateral` must
  show the right narrowed counts (verified end-to-end by
  `tests/integration/cross_cutting_aux_filters.sh`; extend the script
  with more URL pairs if more pages need coverage).

### Cross-tab name-link invariant

Every bare-name link must go to the entity's overall page (identity
only — gender + team_type for teams, gender for players). Hunt down
inline `<Link>` calls with extra scope params and convert them.

### Suspected follow-ups discovered along the way

- The frontend's `useFilters` reads `series_type` as a special-case
  outside `FILTER_KEYS`. Once a second aux filter exists (e.g.
  `result_filter`), generalise into an `AUX_KEYS` registry so the
  hook iterates uniformly.
- Tournament metadata exposure — backend `/api/v1/tournaments`
  doesn't currently return `series_type` per tournament. If
  `TeamLink`'s container resolution starts hitting the
  "all/unset + tournament-set" ambiguity often enough, add the field
  so the frontend doesn't rely on the `series_type` filter being set.

---

## Original notes (2026-04-14) — Tournaments + H2H rollup design

Capture of open design questions from the older session. Most of the
tournaments/series rollup is now shipped via the Series-tab dossier.
H2H team-vs-team mode is shipped. The team-pair scope discussion
below is still relevant for thinking about future deep-dives.

Dates and paths here reflect repo state at commit b7634f1 (2026-04-14).

## The core insight

Most tabs today are scoped to a single entity (a team, a batter, a
bowler, a fielder). Two scopes have been hiding in the FilterBar
that don't yet have a home:

1. **A tournament, time-ranged or all-time.** Example: pick
   `tournament=Indian Premier League` + no season → "IPL all-time".
   Today this only shapes filters for other tabs; it has no tab of
   its own. The IPL has its own story: total runs, total wickets,
   most prolific partnership ever, the highest-scoring batter of all
   time, the tournament's highest team score, evolution of run rates
   per season, etc. None of that surfaces anywhere.

2. **A team pair, time-ranged or all-time.** Example:
   `team=India` + `vs=Australia` + no season → "India vs Australia
   all-time T20Is". The Teams > vs Opponent tab gives you the
   current season's head-to-head but doesn't treat the pair as its
   own first-class entity with a life of its own (batting averages
   across this matchup, favourite batter vs favourite bowler in
   this matchup, etc.).

Both are **rollup views across many matches**, scoped by something
FilterBar already captures. The question isn't whether to build them —
it's where they live.

## Scope A: tournament as its own tab

**The sketch** — a `/tournaments` route (currently nonexistent). Two
levels:

- Listing (`/tournaments`): all tournaments in scope, with headline
  stats per tournament — total matches, editions held, most-capped
  team, top batter, top bowler. Filter-sensitive on gender / team_type
  / season.
- Per-tournament (`/tournaments?tournament=Indian Premier League`):
  full dossier. Champions by season, all-time top-10 batters and
  bowlers and fielders (reusing `/batters/leaders` etc. with the
  tournament filter pre-applied), highest/lowest team scores,
  largest partnerships, most economical bowler, run-rate evolution
  chart, etc. If `season_from`/`season_to` is set, scope narrows.

**This is already partly designed** — see
`internal_docs/spec-team-stats.md` "Implication for tournaments" and
`internal_docs/design-decisions.md` "Team metrics need tournament baselines"
entries. Those were written with enhancement M (next-up) in mind.

**Open question 1:** Time-ranged vs all-time. The user's framing —
"if you leave a tournament open for all time then like the IPL then
it's the IPL all time" — suggests the default view (no season filter)
should show **all-time tournament stats**, and narrowing to a season
or range scopes the same view. That's consistent with what Teams
already does. Go with it unless a per-season-edition page turns out
to be obviously needed.

**Open question 2:** Which of the existing per-team endpoints should
be reused vs. rewritten? A lot of the math already exists in
`api/routers/teams.py` (scored by team). We need the equivalent
scored by tournament. Likely a new `api/routers/tournaments.py`
with filter-aware endpoints. Or generalize the team-stats helpers
so they take an optional tournament scope.

## Scope B: team-to-team rollup

**The sketch** — "India vs Australia all-time" as a browsable page.
Batting averages batter-by-batter *in this matchup*, leading
wicket-taker, largest-margin result, closest match, etc.

**Three placement options.** Pick one and own it:

### B1. Team > vs Opponent, promoted to first-class

What exists: `/teams?team=India&tab=vs%20Opponent&vs=Australia` ships
today (head-to-head at season / rollup level). It's a *subtab* of
Teams.

Change: make this the default answer. Expand the tab to include
per-player stats in the matchup, top batter/bowler IN THIS RIVALRY,
largest partnership in this rivalry, etc. Season_from/to narrows as
usual. All-time (no season) shows the full history.

Pros: no new route, builds on existing URL scheme, user already
reaches it via the Teams page flow.
Cons: vs Opponent is buried as a Teams sub-tab and is easy to miss;
discoverability is weak.

### B2. Head to Head becomes polymorphic

`/head-to-head` today is strictly *player-v-player* (batter + bowler).
Extend it to accept `team=X&opponent=Y` as well, render the matchup
dossier there when team+opponent is present, keep the existing
batter+bowler view when those are present.

Pros: "Head to Head" is already the right *conceptual* home for any
two-entity matchup. Route is discoverable from the nav bar.
Cons: the page becomes polymorphic (two distinct dossier layouts on
one route). Increases cognitive load for future contributors. The
player-v-player view has bespoke depth (phase breakdowns, season
trends) that doesn't translate to teams.

### B3. New /rivalries route

Stand up `/rivalries?team1=India&team2=Australia` as its own page.
Keep `/head-to-head` player-only. Keep `/teams > vs Opponent` as a
summary view that links into the rivalries page for depth.

Pros: clean separation of concerns. Each route is single-purpose,
easy to maintain.
Cons: most nav real estate, more code to maintain, one more concept
to teach users.

### My lean (not decided)

**B2 — abuse /head-to-head.** Reason: the conceptual meaning of
"head to head" is bigger than player-v-player. In cricket commentary
"head to head" naturally refers to any two entities. Users will type
`/head-to-head` and expect to find *both* options. The cost is a
polymorphic page, but we can mitigate with a clear picker UI at the
top ("Player vs Player" / "Team vs Team") and separate sub-components
underneath.

We should probably redirect `/teams > vs Opponent` to
`/head-to-head?team=X&opponent=Y` once /head-to-head is team-aware,
so there's a single canonical place.

Alternative lean: if B2 turns into a mess of conditional rendering,
pivot to B3 without much re-work since the team-stats math is
self-contained.

## Interaction between A and B

If Scope A (tournaments) ships first, some of Scope B
(team-to-team) gets easier — the tournament-scoped leader endpoints
can be reused with a second team filter applied. Suggests order:

1. A: tournament landing + dossier (enhancement M per roadmap).
2. O: tournament baselines overlaid on team/batter/bowler/fielder
   pages (depends on A).
3. B: team-to-team rollup, built on top of A's infrastructure
   (tournament-style aggregates reused with pair scope).

## Data pre-flight

Before building, a few open questions worth checking against the DB:

- How many matches exist per (team_pair, tournament, season) bucket
  at the tail end? A "Nepal vs Denmark" all-time rivalry is 2–3
  matches; "India vs Australia" is 30+. UI thresholds for "is this
  rivalry worth rendering a dossier for?" are worth thinking about.
- Tournament naming in cricsheet has some fuzz: "World T20" vs
  "ICC Men's T20 World Cup" are the same event at different years.
  We'd want a canonicalization map OR the user knows to pick
  explicitly. Worth inspecting `SELECT DISTINCT event_name` before
  designing the landing.
- `match.event_group`, `match.event_stage`, `match.event_match_number`
  columns exist and are likely unused — worth checking what's in
  them, may shortcut some structural work (group stages, finals).

## Perf implications

Tournament dossiers will do full-DB aggregates similar to the
Batting/Bowling leaders. If they're pre-filtered by `tournament`,
they're narrow — same perf shape as "IPL 2024 narrow" (30ms range).

Team-to-team dossiers filter by both teams, so also narrow. Both
should inherit the conditional-JOIN pattern and covering indexes
already in place; no new perf work expected.

## Landing-page perf on prod — three options to pick between

After the `--first` push at end-of-session 2026-04-14, prod steady-
state numbers are:

| Endpoint (unfiltered) | Prod | Local | Narrow-filter (both) |
|---|---:|---:|---:|
| Batting | 1.63s | 0.83s | 0.03s local / 0.32s prod |
| Bowling | 1.61s | 0.81s | — |
| Fielding | 1.34s | 0.67s | — |

Decomposition: the narrow-filter round-trip (0.32s) is essentially
pure network overhead (TLS + TCP + HTTP over internet to plash), so
prod server-side DB work unfiltered is ~1.3s vs ~0.83s local. The
composite indexes are working (without them we'd be at 3s+, which
is what we saw before the fix), but plash's container is
CPU/memory-constrained enough that the 575MB `delivery` scan still
takes about 1.5× longer than on the dev Mac.

User noted "a little bit slow" — 1.5s unfiltered is borderline for
a landing page. Three options, pick one next session:

### Option 1 — TTL cache on the unfiltered responses

The unfiltered `/batters/leaders`, `/bowlers/leaders`,
`/fielders/leaders`, `/teams/landing` responses change **only when
the DB is rebuilt or incrementally updated**. Nothing else
invalidates them. So a small in-process TTL cache (~15 LOC per
endpoint, or a shared decorator) gets us near-instant hits on
repeat visits.

Shape:
```python
from functools import wraps
from time import monotonic
_cache = {}  # key -> (expires_at, response)

def cache_if_unfiltered(ttl_sec=600):
    def deco(fn):
        @wraps(fn)
        async def wrapper(filters: FilterParams = Depends(), **kw):
            is_unfiltered = not any([filters.gender, filters.team_type,
                                     filters.tournament, filters.season_from,
                                     filters.season_to])
            if not is_unfiltered:
                return await fn(filters=filters, **kw)
            key = (fn.__name__, *sorted(kw.items()))
            entry = _cache.get(key)
            if entry and entry[0] > monotonic():
                return entry[1]
            result = await fn(filters=filters, **kw)
            _cache[key] = (monotonic() + ttl_sec, result)
            return result
        return wrapper
    return deco
```

Invalidate by restart (simplest) or with a hook in
`update_recent.py` that POSTs to an internal `/_cache/flush`
endpoint. Restart-based invalidation is fine given plash redeploys
on every `deploy.sh` run.

Pros: ~15 LOC per endpoint. Eliminates the 1.5s wait on every
repeat hit. Low risk, zero data-correctness concern.
Cons: first hit per TTL window is still 1.5s. Memory usage grows
slightly (response payloads are ~5–20KB each).

### Option 2 — Precomputed summary tables

Add `batter_career_totals`, `bowler_career_totals`,
`fielder_career_totals` tables refreshed by `update_recent.py`
after each incremental import. Columns: person_id + the aggregates
for each filter-axis combo we care about (all-time, per-gender,
per-team_type).

Pros: eliminates the full-table scan entirely. Even unfiltered
responses become O(10K rows) single-table scans, ~10ms on prod.
Cons: another populate script to maintain. Invalidation must be
correct on every DB mutation. Adds disk (maybe 1-2MB per table,
negligible). Filter combinations that aren't pre-aggregated still
fall back to full scan — so we'd need to decide which axes to
materialize.

### Option 3 — Accept current perf

1.5s unfiltered / 0.3s filtered is "borderline acceptable for a
landing page". If the user's actual usage skews heavily to
filtered (IPL 2024, India 2025) which they're most interested in
anyway — the fast path — then optimizing the slow path is
premature.

Mitigation if we take this path: show the spinner earlier with a
"Loading all-time leaders…" message so the wait feels intentional,
and set default filters (e.g. current season) so users rarely hit
the unfiltered slow path.

### My lean

**Option 1 (TTL cache)** — biggest ROI for the least code. Repeat
landing-page visits (the common case) become instant. First visit
per TTL-window still 1.5s but that's a single-use penalty. No
risk of stale data since the cache flushes on every deploy.

Option 2 is worth it if we end up with tournament-dossier
endpoints that would also benefit — those will do similar
full-table aggregates. Could batch the summary-table work with
the tournaments build.
