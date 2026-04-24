# Outlook: Cross-App Comparison Surfaces

Status: idea doc, not a spec. Collects the surfaces where the same
"vs scope-average" lens — first shipped in
`spec-team-compare-average.md` — is worth extending, and what each one
costs. Each surface below will become its own spec when prioritised.

The shared dependency: the `/api/v1/scope/averages/*` endpoint family
and the response-envelope contract (`value`, `scope_avg`, `delta_pct`,
`direction`, `sample_size`) introduced in Spec 1. Every surface below
reuses that contract so there's one way to render a delta across the
whole app.

Also shared: the `player_scope_stats` table, populated alongside Spec 1
but not consumed there. Several of the surfaces below depend on it —
which is why it exists now, even though Teams Compare doesn't need it.

## The Kohli-at-#3 constraint

The idea "compare Kohli against other batsmen" sounds obvious but
doesn't hold up: a #11 tailender's SR dragging down the baseline against
which Kohli is measured produces a meaningless comparison. The matching
dimension has to be **batting position** (or a position band).

Average batting position is defined per-player-per-scope as:

```
avg_batting_position = SUM(position × innings_at_position) / total_innings
```

A player whose scope gives Kohli `avg_batting_position = 3.1` is
baselined against other in-scope batters with `avg_batting_position`
in (say) [2.5, 3.5] — the "average top-middle-order batter" in the same
scope.

This is why `player_scope_stats` carries both `avg_batting_position`
and the full `innings_by_position_json` array: the matching window is a
UI-tunable band, and the per-position histogram lets the backend
answer "how many innings did this player bat at position ≤3" without a
full delivery scan.

Bowlers get an analogous match-dimension: **phase usage**. A
death-specialist (bowls 70% of their overs in overs 15-19) shouldn't be
baselined against a powerplay opener. `player_scope_stats` carries
`powerplay_overs / middle_overs / death_overs` per scope so a phase-mix
band can be the match window.

Fielders are simpler: the "role" is binary (designated keeper vs
outfielder), already captured via `keeper_assignment`.
`player_scope_stats.matches_as_keeper` and `catches_as_keeper` drive
the keeper-vs-keeper baseline cleanly; non-keeper baseline is the
remainder.

## Surface 1 — Player compare with position-matched average

**Highest-value surface.** Mirrors Teams Compare's new average column
into `/players?player=X&compare=Y`. Add a slot: "+ Add average batter /
bowler / fielder in scope". The match dimension auto-derives from the
primary player's role (batting-primary → position-matched batting
baseline; bowling-primary → phase-mix-matched bowling baseline).

Data dependency: `player_scope_stats` (the reason it exists).

New endpoints: `/scope/averages/players/batting/summary?position_band=2.5,3.5`,
equivalents for bowling with a phase-mix band, and for fielding with a
keeper/outfield flag. All read from `player_scope_stats` +
`METRIC_DIRECTIONS`.

UX shape: same grid as Teams Compare's average column — raw value,
scope_avg, (future) delta_pct. Position band defaulted from primary's
`avg_batting_position ± 0.5`; a small control lets the user widen /
narrow the band.

Scope of work: ~1 spec, medium (schema already in place; endpoint +
UI work). Biggest design question is the band-width UX.

## Surface 2 — Leaderboard Δ columns

On `/batting`, `/bowling`, `/fielding` landing pages, add a Δ column
to every ranking table showing each row's `delta_pct` against the
in-scope average. Same `direction`-driven coloring as the Compare grid
will eventually use.

Data dependency: one call per page load to
`/scope/averages/{batting|bowling|fielding}/summary`. Join client-side.
No new tables.

UX shape: one extra column per ranking table. Compact. Optional (hide
via a preference) for users who want the raw leaderboard.

Scope of work: small (1 endpoint + 1 column per table × 3 tables).
Spec-lite.

## Surface 3 — Venues baseline

Venue dossier (`/venues?venue=X`) already computes in-venue averages
for match-level stats (avg 1st-innings total, chase-win %, etc.). Two
extensions:

**3a. Venue vs global.** A strip at the top of the dossier:
"Chinnaswamy death-over econ 9.1 · league 8.4 · Δ +8.3% (batting-friendly
death)". Tells the user at a glance whether this venue skews batting
or bowling relative to the wider scope.

**3b. Player at venue vs league at venue.** The per-player leaderboards
inside the dossier (batters / bowlers / fielders tabs) pick up the same
Δ column as Surface 2, but scoped to the venue. Answers "does Kohli do
better than the average top-order batter *at this venue specifically*"
— the "home specialist" signal.

Data dependency: Surface 3a uses the plain `/scope/averages/*` family
with and without `filter_venue`. Surface 3b uses
`/scope/averages/players/*` (same as Surface 1) with `filter_venue`
scoped.

**Footgun**: "in scope" has two meanings at venues. For 3a, the
comparison is venue-scoped vs not-venue-scoped — we need a way to ask
for a baseline that drops the venue constraint. Name it:
`/scope/averages/.../unconstrained-by=venue` (or a query flag). Mirror
the same for H2H — baseline baseline batter vs a bowler means scope
minus the batter identity. Nail this in the per-surface spec.

Scope of work: medium. 3a is small; 3b is the same work as Surface 1.

## Surface 4 — Head-to-head baseline

`/head-to-head?mode=player` (Kohli vs Starc). Two extensions:

**4a. Batter vs baseline-bowler.** How does Kohli's SR vs Starc compare
to Kohli's SR vs the *average bowler in scope*? Answers "does Starc
specifically trouble Kohli, or does everyone".

**4b. Bowler vs baseline-batter.** Mirror: how does Starc's econ vs
Kohli compare to Starc's econ vs the *average top-order batter in
scope*? Answers "does Kohli specifically own Starc, or does everyone".

Data dependency: `player_scope_stats` (for the baseline side) + the
existing matchup endpoint (for the actual H2H side).

Same `unconstrained-by` footgun as Venues: baseline batter =
scope-minus-this-batter-identity. Needs a principled way to express
"aggregate across all batters in scope *except* this one".

Scope of work: small-to-medium. The data exists; the endpoint flag is
the interesting part.

## Surface 5 — Scorecard expected-SR

`/matches/{match_id}`. For each batter row, show alongside their actual
SR an "expected SR given phase / position / venue" derived from league
averages. "Rohit 55 (40) · SR 137.5 · +12% vs phase-typical".

Fantasy-stats energy; nice-to-have.

Data dependency: heavier than the others. Per-ball contextual baseline
(phase × position × venue) requires either (a) a materialised
`delivery_expected_sr` rollup keyed by (phase, position, venue, scope),
or (b) on-the-fly query per match load.

Option (b) is the pragmatic first cut: at a per-scorecard level, the
number of rows needing a baseline is ~22 (XI × 2). Per row it's one
lookup. No new tables; reuse `player_scope_stats` for the position
dimension and plain delivery aggregation for the phase × venue
dimension.

Scope of work: medium. The per-metric "expected X" UX design is more
interesting than the backend.

**Park until Surfaces 1-4 land.** It's a long-tail feature; the
cost-benefit only justifies once the baseline machinery is well-worn.

## Surface 6 — Tournament era framing

Tournament dossier (`/series?tournament=X`). One-line framing at the
top: "IPL 2024 · avg RR 8.6 · all-time IPL avg 7.9 · Δ +8.9%
(high-scoring era)".

Data dependency: two scope-average calls — one with the season filter,
one without.

The `unconstrained-by=season` footgun shows up here too. Same fix as
Venues + H2H; the API flag should cover all three.

Scope of work: tiny. One or two lines of copy, one extra fetch per
dossier load. Could ship as a sub-task of any of the larger specs.

## Cross-cutting: the `unconstrained-by` footgun

Three of the six surfaces above (Venues, H2H, Tournament) all hit the
same ambiguity: "in scope" has two valid interpretations, and the
baseline side often wants the broader one. The scope-averages API
family needs a clean way to express "aggregate with this one filter
dropped".

Recommended shape: a query parameter `drop=venue|player|team|season`
(or a list: `drop=venue,season`) on every `/scope/averages/*` endpoint.
Backend `FilterParams.build()` gets a `drop` argument that masks the
specified filter axis before clause construction.

Lock this in before Surface 3 so it's not retrofitted into three
endpoints separately.

## Suggested prioritisation

Ordered by ROI (value / effort):

1. **Surface 2 — Leaderboard Δ columns**. Smallest and highest-touch
   — every user of batting/bowling/fielding rankings sees it. Minimal
   effort; no new tables; same endpoint family.
2. **Surface 1 — Player compare with position-matched average**.
   Biggest conceptual payoff; consumes `player_scope_stats`
   (already built during Spec 1); medium effort.
3. **Surface 4 — H2H baseline**. Small-to-medium. Unlocks the
   "does X specifically own Y" question that's otherwise unanswerable.
4. **Surface 3 — Venues baseline (3a + 3b)**. Medium. 3b is the same
   engine as Surface 1; 3a is a freebie on top.
5. **Surface 6 — Tournament era framing**. Tiny. Slot into whichever
   larger spec ships first.
6. **Surface 5 — Scorecard expected-SR**. Park until 1-4 are battle-
   tested.

Each surface becomes its own spec at scheduling time. This document's
job is done once those specs exist — at which point it becomes a
historical marker of the design arc, same way
`internal_docs/enhancements-roadmap.md` tracks shipped features.

## What's deliberately NOT here

- **Ratio heatmap view** (the "single colored cell per metric" compare
  mode) is a UX refinement on top of any of the above surfaces, not a
  surface of its own. It lives as a v2 toggle on each surface where it
  earns its keep. Mentioned so nobody treats it as its own spec.
- **Cross-format comparisons** (e.g. "Kohli's T20 SR vs his ODI SR")
  are a different feature — the format is part of scope, not of
  baseline. Out of scope for this doc.
- **Team-level summary tables** (`team_scope_stats`,
  `team_scope_phase_stats`). Spec 1 explicitly defers these; revisit
  only if measured perf demands.
