# Next-session ideas — Tournaments, team-to-team, H2H scope

Capture of open design questions before the session closes. Pick up
next time. Dates and paths here reflect repo state at
commit b7634f1 (2026-04-14).

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
`docs/spec-team-stats.md` "Implication for tournaments" and
`docs/design-decisions.md` "Team metrics need tournament baselines"
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

## Small gotcha to remember

The **prod DB does not yet carry the new composite indexes**
(`ix_delivery_batter_agg`, `ix_delivery_bowler_agg`) because they
were added to `import_data.py` + `update_recent.py` after the last
`--first` push. They'll arrive on prod the next time someone runs
`update_recent.py` locally against `./cricket.db` and then
`bash deploy.sh --first`. Current prod perf is fine without them
(sub-400ms unfiltered) but the gap is worth being aware of.
