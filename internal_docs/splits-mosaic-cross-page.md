# Splits Mosaic — cross-page reuse + broader-scope baselines

**Status:** DESIGN DOC — not implemented. Captures user thinking
2026-05-11 about extending the Teams Splits Mosaic to other pages,
and a related question about what "league average" should mean
when the Mosaic is viewed on a landing (subject-less) page.

The existing implementation (`internal_docs/spec-splits-mosaic.md`)
is Teams-only. It splits matches by `(toss × inning × result)`,
computes team-vs-league deltas at the current FilterBar scope, and
lays out a 4-rect mosaic where each rectangle is sized by joint
count (sqrt-of-count → linear area).

This doc captures three open questions:

1. **Where else should the Mosaic live?** Series, Venues, Players,
   H2H — and what subject/baseline does each page imply?
2. **What's the right baseline on the LANDING (subject-less) view?**
   Currently no deltas show; the user wants meaningful comparisons.
3. **How does the FilterBar interact with the Mosaic on each page?**
   The natural baseline differs per page.

## 1. Pages the Mosaic could live on

### 1.1 Teams (shipped)

Subject = team. Baseline = "league at same FilterBar scope" (per-
team-view unpivot across all teams in scope). Deltas: team-vs-league.

### 1.2 Series (not shipped) ← motivated by 2026-05-11 user
            "is Wankhede better for chasing" insight

Series page currently has no analog. A Series-grain Mosaic would
answer: "in IPL, do toss-winners tend to chase? what's the bat-
first win rate?"

Subject = the series itself (tournament + season). Baseline = all
series at gender grain, OR all-time at gender grain. Deltas:
this-series-vs-all-T20.

Use case: "Was IPL 2018 unusually chase-friendly?" or "Are T20
World Cups bat-first-friendly?"

Mosaic mount: on the series dossier page (top, similar to Teams).
Aux filters: `toss_outcome` / `inning` / `result` still apply.
`filter_venue` is meaningful (filter to a stadium WITHIN the
series).

### 1.3 Venues (not shipped) ← directly motivated by the
            Wankhede landing question

A Venue-grain Mosaic would directly answer the user's "is Wankhede
better for chasing" question. Subject = venue (e.g. Wankhede).
Baseline = all-venues-at-FilterBar-scope (e.g. all IPL matches).

Mount: on the Venues dossier page. Aux filters: same as Teams.

This is the cleanest home for the venue-vs-broader-IPL comparison
the user asked about — the page subject IS the venue, the baseline
is the rest of the venues, and there's no ambiguity about what
"this is special vs the league" means.

### 1.4 Players (deferred per existing §5 of teams spec)

Already tracked. Subject = player. Baseline = per-team-of-player /
overall-T20. Substitute exclusion concerns. See
`spec-splits-mosaic-player.md` (not yet written).

### 1.5 Head-to-Head (deferred)

Subject = team1 vs team2 (specific pair). Baseline = team1's all-
matches OR team2's all-matches OR all-IPL. Default subject =
team1 with per-cell-flip toggle.

### 1.6 Compare-slot (deferred)

Slot-aware mini-mosaic inside compare cards. Each slot has its own
subject; baseline is the side-by-side comparison itself.

## 2. The baseline question on landing (subject-less) views

The user's specific complaint 2026-05-11: at
`/teams?...&filter_venue=Wankhede+Stadium` (no team), the Mosaic
shows counts but no deltas. They want to know "is Wankhede
special".

Without a team subject, the current API can't answer that — the
"league" side of the dual-query IS the data shown. There's no
implicit second scope to compare against.

Three possible baselines:

### 2a. Strip the narrowing filters from the baseline

Compare current scope to `current FilterBar with narrowing filters
stripped`. For Wankhede + IPL: compare to all-IPL.

Pro: no design choice — strip "secondary" filters (filter_venue,
opponent, season range narrower than tournament), keep "primary"
scope (gender + tournament).

Con: defining "narrowing" vs "primary" is fuzzy.

Implementation: sibling `/teams/splits` fetch with narrowing
filters stripped. Frontend computes deltas as `(current_share -
baseline_share) / baseline_share`.

### 2b. Subject-of-page baseline

Use the page subject as the baseline. On Venues page, baseline =
all venues. On Series page, baseline = all series. On Teams
landing, baseline = all teams (which is what the current league
side already is — so no extra baseline, no deltas, current
behavior).

Pro: per-page semantics are obvious. Each page is "this X vs all
Xs at FilterBar scope".

Con: doesn't help with the Teams landing case (where there's no
single subject — it's already showing "all teams"). User's
Wankhede question simply doesn't fit Teams landing.

### 2c. Refuse to show deltas on subject-less views

Current behavior. Treat the landing as a navigational starting
point, not a comparison view. Push users toward a subject page
(Teams/Venues/Series) where deltas make sense.

## 3. Cross-cutting design choices

### 3.1 Component reuse

The existing `SplitsMosaic` component is data-shape-driven (consumes
a `TeamSplits` object). For Series / Venues / Players to reuse, we
need:

- A common response shape: `{ scope_total_n, league_total_n,
  cells[], marginals, subject, matchesEnvelope_equivalent }`.
- Page-specific endpoints (`/series/{tournament}/{season}/splits`,
  `/venues/{name}/splits`, `/players/{id}/splits`).

Likely refactor: rename `TeamSplits` to `Splits` or `MosaicData`;
each page provides its own data via its own fetcher. The component
itself is largely subject-agnostic.

### 3.2 Inning POV

Teams Mosaic flips inning POV on Bowling/Fielding tabs (see
spec-splits-mosaic.md §3.2). Venues / Series don't have
discipline tabs in the same way — inning POV is unambiguous (the
match's `innings_number`). No flip needed.

### 3.3 Aux filter portability

`toss_outcome` / `inning` / `result` are aux filters today,
defined in `FilterParams` but kept out of `FILTER_KEYS` so they
don't pollute scope-link URLs. If we mount the Mosaic on
Venues / Series / Players, those pages need to handle the same
aux filters (already do, since aux is part of `FilterParams`).

The `result` and `toss_outcome` aux filters require a subject
team in Teams (see CLAUDE.md "Splits Mosaic — dimensionality is
URL-derived; aux outcome filters need ?team="). On Venues /
Series the subject is the page itself; the same gate applies but
the subject is different.

### 3.4 Cell delta semantics per page

| Page | Subject | Baseline | Cell delta means |
|---|---|---|---|
| Teams (team selected) | this team | league at scope | "Does this team over-/under-perform in this quadrant vs all teams in scope?" |
| Venues (selected) | this venue | all venues at scope | "Does this stadium produce more / fewer X-outcomes vs all stadiums in scope?" |
| Series (selected) | this series | all series at scope | "Was this season unusually X?" |
| Players (selected) | this player | per-team-aggregate at scope | "Does this player over-/under-perform their team's pattern?" |
| Teams landing + venue narrowing | (no team) | all-venues at scope (if we strip filter_venue) | "Is Wankhede special vs all-IPL?" — option 2a above |

### 3.5 Where the user's "is Wankhede better for chasing"
       question actually belongs

The cleanest answer is **Venues page** — the page subject IS the
venue, the baseline IS all-venues. No design ambiguity.

A secondary answer is **Teams landing with filter_venue applied**
+ option 2a baseline. Both work; Venues is purer.

The Teams page implementation is unchanged; user goes to Venues
for that question.

## 4. Next steps (not committed)

1. Write `spec-splits-mosaic-venues.md` — Venues-grain Mosaic.
2. Write `spec-splits-mosaic-series.md` — Series-grain Mosaic.
3. Refactor `SplitsMosaic.tsx` to be data-shape-driven (small —
   the props interface already takes generic-ish shapes).
4. Add the broader-scope baseline (option 2a) to Teams landing
   as an interim until Venues / Series pages exist.

User direction 2026-05-11: "make a mention of it there [Series],
and maybe we'll support it here as an all teams thing. I want
users to be able to get at such information from anywhere."
