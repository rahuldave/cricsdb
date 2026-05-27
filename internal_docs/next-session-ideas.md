# Next-session ideas — all-ball batting-runs convention + single source (then resume 3b)

> **NO DEPLOYS gate is OFF** as of 2026-04-21. Resume normal deploy
> cadence.

## NEXT SESSION — top of queue (2026-05-27)

**Resume `spec-player-baseline-aux-fallback.md` at Phase 3b — now
UNBLOCKED.** The all-ball convention prereq SHIPPED locally this session
(see below); `inningsbatterperf` is now all-ball + complete and the
position cohort is a rollup of it, so 3b's live aggregation over that
table matches the precomputed path by construction.

### SHIPPED this session — `spec-batting-allball-runs-single-source.md` (local, unpushed)

All-ball batting-runs convention + single per-innings source. Commits
a60dfd9 (enumerate sites) → 8f86314 (inningsbatterperf non-striker
completion + not_out excl. retired) → fa2cff3 (position cohort = rollup
of inningsbatterperf + parent all-ball via shared helper
`api/batting_convention.batting_delivery_contrib`; reorder records ahead
of position in both `import_data.py` + `update_recent.py`) → e798acd
(batting.py read queries all-ball: 9 Pattern-X + 5 Pattern-Y sites per
`internal_docs/allball-batting-sites.md`; phase/over populates via the
helper) → f8f2ef2 (head_to_head batter-vs-bowler, extended per scope
decision) → [Commit 5] (docs). Headline: V Kohli career runs 13117 →
13166 (the 49 no-ball off-bat runs), balls unchanged (legal), SR
recomputed. Local DB rebuilt (records + all cohorts). New tests:
`test_playerscopestatsposition_rollup.py` (exact-integer parity),
`test_batting_allball_runs.py` (own number + cross-tab + H2H, SQL-
anchored). Backup before rebuild: `tmp/cricket.db.bak-allball`.

**Deploy note:** held local until 3b lands — read queries fix on a code
deploy, but the cohort tables + `inningsbatterperf` need a prod DB
rebuild; one deploy + one rebuild covers both. The regression harness is
diff-on-demand (no checked-in goldens), so the committed change leaves no
stored baseline red; the red-then-green is the direct SQL-anchored
sanity test, not a REG→NEW flip (the flip window is pre-change-commit,
which a committed change can't retro-fill — feedback_regression_before_shape).

**THEN resume `spec-player-baseline-aux-fallback.md` at Phase 3b** (its §3
has a ⏸ PAUSED banner). Once the convention fix lands, `inningsbatterperf`
is convention-correct + complete, so 3b's live aggregation reading it
will match the precomputed path by construction. 3b–3e: route each cohort
compute fn through `is_precomputed_scope` → a live aggregation that reads
the per-innings table and reuses the team-side `_cohort_outcome_clause` /
`_option_b_team_inning` for the six-filter narrowing.

SHIPPED this session (commits eb52569→df62afc, unpushed/undeployed):
Phase 1 (Won/Lost filter on /batting,/bowling,/fielding + reusable
TossFilter on an unlisted /dev/toss-filter route + toss counts on
result-counts), Phase 2 (`player_toss_clause` at all 8 sites), Phase 3a
(`inningsbatterperf` + `position_bucket`/`dots`, rebuilt 206429 rows,
parity + incremental tests).

Key decisions locked for 3b (aux-fallback spec §2): no CIs now (later,
cross-cutting player + team); team-side support cliff later; fielding
stays keeper-binary; sample size in the existing comparison-chip tooltip
only; fairness rule = both own number AND comparison narrow together.

This session's shipped work (pushed, NOT deployed) — commits
3f744c6→04390c9: player "Teams played for" strip restructured to "N
matches @ Team" + mounted on the 3 discipline pages with a discipline-
scoped lead link; SCOPE subtitle enlarged; redundant scope-echo subtitle
dropped; **"Versus" opponent filter** on all 4 player pages backed by a
new `/players/{id}/opponents` endpoint.

---

### Superseded — was top of queue (2026-05-19, SHIPPED)

**`spec-player-compare-average.md` Phase 1 — `METRIC_DIRECTIONS`
audit + `drop=` plumbing.** Build-ready spec drafted 2026-05-19; 17-
commit rollout across 5 phases:

1. Phase 1 (1 commit): extend `api/metrics_metadata.py` with player-
   grain metric keys; add `FilterParams.build(drop=...)` masking.
2. Phase 2 (3 commits — one per discipline): child tables
   `playerscopestats_position` / `_over` / `_fielding_position` +
   populate-full + populate-incremental + add `*_distribution[]`
   array on the corresponding `/summary` endpoint (Q5 resolution —
   ships early so next-spec UI can prototype). Each commit deploys
   with `bash deploy.sh --first`.
3. Phase 3 (4 commits): `/scope/averages/players/*` endpoints
   (batting/bowling/fielding/keeping).
4. Phase 4 (8 commits — flip+migration per endpoint): envelope-
   migrate the 4 player summary endpoints (can batch flips → 5
   commits, decide at the time).
5. Phase 5 (1 commit): frontend inline-baseline rendering on
   `PlayerSummaryRow`.

Key design decisions baked in (see spec §13 Resolution log):
- Bucketed convex-combination cohort (not continuous-range filter).
- 10 batting buckets (Opener=pos 1+2; #3…#11 individual).
- 20 bowling per-over buckets.
- Fielding cohort is keeper/outfielder binary; per-position-of-
  dismissed-batter histogram surfaced for **next-spec impact-
  weighted analyses** (separate fielding spec).
- Per-bucket sample-support thresholds + renormalisation rule.
- `drop=` is per-endpoint structural plumbing (Surfaces 3a/4/6),
  NOT a user-facing toggle.
- 3 follow-up specs unblocked (purely UI/viz):
  `spec-batting-position-chart.md`, `spec-bowling-over-chart.md`,
  `spec-fielding-impact.md`.

Older spec-series-precompute queue is SHIPPED — see
`enhancements-roadmap.md` 2026-05-14 entries and project memory
`project_series_precompute_shipped.md`.

## OLDER NEXT-SESSION — `spec-series-precompute-followup.md` (SHIPPED 2026-05-14)

Original Phases C + D shipped in commits `d3ce8ef`, `2ead91c`,
`13cf56c`, `18e1b51`. Phase E permanently deferred. Local +
deployed `--first` on 2026-05-14.

Older queue (DOM-test rollout, series_type FilterBar) follows:

## OLDER QUEUE — DOM-test rollout (2026-04-28+)

`spec-filterbar-team-class-v3.md` shipped 2026-04-28 in 5 commits
(`a0773e5` … `87ad937`); `spec-avg-col-per-team-transform.md`
shipped 2026-04-28 same session in 2 commits (`6b393a1` flip,
`236eaf7` backend). v3's full ship report lives in
`enhancements-roadmap.md` "Shipped 2026-04-28". Top of queue now:

### Step 1 — `spec-dom-tests-series-teams.md` Batch 1 (NOW UNBLOCKED)

`internal_docs/spec-dom-tests-series-teams.md` (228 lines). 4
scripts to prove the lifted `_lib.sh` harness works. Anchor URLs
already assumed team_class v3 had shipped — they're now valid.

- `teams_compare_intl_fm.sh` — Aus / FM avg / Ind 2024-25 grid
  (closely mirrors `tests/integration/compare_avg_chips.sh`
  Anchor E1 which v3 already added; the DOM-test version will be
  the canonical home).
- `teams_compare_club.sh` — RCB + SRH IPL 2025 unchanged.
- `teams_match_list_intl_fm.sh` — Aus 22→16 visible end-to-end.
- `series_landing_intl_fm.sh` — tile counts narrow correctly.

Then Batch 2 (10 scripts) + Batch 3 (31 + cross-cutting) per the
spec.

Hard rule for every script: ground truth comes from a subagent
that did NOT read `api/` or `tests/sanity/` (gold-standard) OR a
committed `audit/<script>.sql` SQL file. NEVER copy expected
numbers from the running API.

### Step 2 — Sibling specs (BOTH WRITTEN 2026-04-28 — pick one to build)

Both written in the same session that shipped v3 + per-team
transform. Order recommendation: series_type first (mostly
mechanical, smaller scope); slot-override-chip-alignment second
(architectural, unblocks broader future work).

- **`internal_docs/spec-filterbar-series-type.md`** (286 lines)
  — promote `series_type` from AuxParams to FilterBarParams as
  the 10th key. Most slot plumbing already exists
  (`useCompareSlots.inheritedScope` already reads
  `primary.series_type`; `OVERRIDABLE_SLOT_KEYS` already
  includes it). Net work: backend field move, FilterBar widget
  (`<select>` recommended for compactness), `useFilters`
  special-case removal, ScopeStatusStrip chip replaces "Show:"
  sub-line, hand-rolled helper fan-out. ~8h. 5-commit rollout
  per spec §9.
- **`internal_docs/spec-slot-override-chip-alignment.md`**
  (322 lines) — generalises the per-slot override system. Two
  problems it fixes:
  1. **Override-to-empty URL serialization.** `useUrlParam`
     deletes params on falsy values, so a slot can't explicitly
     "override to (none)" while inheriting a non-empty primary.
     E.g.: with FilterBar `team_class=fm`, a user can't pin one
     compare slot's avg to "unbounded baseline regardless." Same
     limitation applies to `tournament` / `season_from` /
     `filter_venue` / `series_type` overrides. Needs a sentinel
     value (e.g. `__any__`) decoded at the read site.
  2. **Chip alignment under bidirectional override.** Today
     `chip_team_class` (and friends) can NARROW the league
     baseline (Mode B). They cannot BROADEN it. If a user sets the
     avg slot to differ from primary by REMOVING a narrowing
     (e.g. primary has tournament=IPL, avg slot has tournament=''
     for all-club), the chip on the team col baselines against
     primary's narrowing while the avg col displays the broader
     pool — chip math contradicts the displayed avg-col number.
     Generalised fix: compute league-side baseline using slot's
     resolved scope, not the request's filters.

  Spec specifies `__any__` URL sentinel + `chip_baseline_scope`
  serialization that generalises today's `chip_team_class` hint.
  ~16h estimated; risk medium-high (touches every overridable
  axis at every endpoint). 5-commit rollout per spec §8.

  Recommended order: build `spec-filterbar-series-type.md` FIRST
  (smaller, mechanical). The slot-override-chip-alignment work
  is architectural and unblocks broader future work.

### Step 3 — Optional commit-6 follow-up

After 1–2 weeks of stable HEAD on the v3 commits, flip the 121
NEW intl-FM regression URLs added in commit 4 (`65698ff`) to REG
so they become permanent guardrails. One commit, no shape change.
The `tests/regression/run.sh` runner currently flags these as
"NEW unchanged" because they're additive (no code-side patch);
flipping to REG matches the runner's design and stops the
suspicious-on-zero-NEW-changed exit-1.

### Step 3.5 (deferred — long-term refactor) — Compare-grid CSS subgrid

`internal_docs/spec-dom-tests-series-teams.md` (228 lines, build-
ready). The umbrella convention is in
`spec-dom-grounded-tests.md` (208 lines).

Three-batch rollout in the spec:

1. **Batch 1** (immediately after spec-d ships): 4 scripts to
   prove the lifted `_lib.sh` harness works.
   - `teams_compare_intl_fm.sh` (re-grounded compare_avg_chips for
     post-d Aus/India numbers)
   - `teams_compare_club.sh` (RCB+SRH IPL 2025 — unchanged from
     today)
   - `teams_match_list_intl_fm.sh` (Aus 22→16 visible end-to-end)
   - `series_landing_intl_fm.sh` (tile counts narrow correctly)

2. **Batch 2** (next session): 10 scripts covering team_overview,
   team_batting/bowling/fielding/partnerships, series_overview,
   series_records.

3. **Batch 3** (week 2): remaining 31 scripts + the cross-cutting
   `team_class_consistency.sh`.

Hard rule for every script: ground truth comes from a subagent
that did NOT read `api/` or `tests/sanity/` (gold-standard) OR a
committed `audit/<script>.sql` SQL file. NEVER copy expected
numbers from the running API.

### Skip / lower priority

- The DOM-test umbrella `spec-dom-grounded-tests.md` is reference
  material — no implementation. Read it before starting Batch 1
  so the per-script structure is consistent.

### Step 4 (deferred — long-term refactor) — Compare-grid CSS subgrid

Today the Compare grid uses three independent column blocks; alignment
across columns is forced by reserving fixed `min-height` on the column
header (`2.4em`) and on the chip-area sub-line slot (`1.4em`). It
works, but breaks down on edge cases — e.g. a slot with multiple
override fields (`SlotHeaderChip` accumulating "· 2025 · @ Wankhede ·
bilaterals · full members only") would make that column's chip-area
exceed the reserved space and push the body rows down.

The clean fix is **CSS subgrid**: hoist all rows (header, chip-area,
identity, RESULTS heading, Matches, W, L, …) to be top-level grid
children of the `.wisden-compare-columns` container, with each column
spanning all rows via `grid-row: 1 / -1`. Each row sizes to its tallest
cell across all columns, so when the avg col adds a column, all
columns advance to the next row in lockstep.

**Mobile plan** (must ship in the same commit — see "current state on
mobile" below for why it can't be a follow-up):

Today `.wisden-compare-columns` is `repeat(N, minmax(0, 1fr))` with no
breakpoint and `.wisden-compare-col { min-width: 0 }` — columns are
explicitly allowed to squeeze below their content's natural width. At
iPhone 13 width (390px), 3 columns become ~115px each, numbers wrap,
and long team names (`Royal Challengers Bengaluru`) blow past the
2.4em reserved header height — so the existing min-height alignment
hack is **already broken on mobile** for the 3-column case. The
subgrid refactor doesn't fix this on its own; subgrid still squeezes.

Plan: switch the grid template to `repeat(N, minmax(11rem, 1fr))` and
wrap the container in `overflow-x-auto`. At desktop widths, columns
behave as before (1fr each). At mobile widths, each column holds its
11rem floor and the grid overflows; the user pans horizontally. Same
pattern `MatchupGridChart` and `InningsGridChart` already use
(`design-decisions.md:306, 371`).

Side benefit: the subgrid refactor + min-width-floor together
eliminate the multi-override-chip pushdown bug AND the existing
mobile 3-col bug in one go.

Why deferred:
- ~80 lines of structural refactor in `TeamCompareGrid` + `CompareSlotColumn`.
- Adding a 3rd compare slot must force a recompute of the row tracks
  (cheap with `display: grid` but worth verifying — React doesn't need
  changes; CSS handles it).
- Browser support: Safari 16+, Chrome 117+, Firefox 71+ — all green
  for 2026, but worth a survey before starting.
- Not blocking — pragmatic min-height fix above is visually
  indistinguishable for the canonical 1-line / 2-line cases. Subgrid
  is the right tool when we hit a 3rd or 4th edge case.

When picking this up: the spec is in this file's commit history; no
separate spec doc needed for an ~80-line CSS-and-JSX restructure.

## DONE 2026-04-27 — avg-col baseline correction for internationals

Mechanism A (gate `scope_to_team` synthesis on `team_type='club'`)
and Mechanism B (`team_class=full_member` aux filter on the avg-
slot picker) both shipped. Sequence:

- Backend: `team_class` added to `AuxParams`; `full_member_clause()`
  in `api/full_members.py` (canonical ICC full-member list moved
  out of `routers/teams.py`); `_league_aux` gated on `team_type='club'`
  with `filters` threaded through every call site;
  `is_precomputed_scope` rejects `team_class` so dispatch falls
  back to live aggregation.
- Frontend: `TeamCompareGrid.fetchSlot` only synthesizes
  `scope_to_team` for clubs without a tournament override;
  `team_class` added to `FilterParams` + `OVERRIDABLE_SLOT_KEYS`
  + `SlotScopeEditor` (Class field, intl-only) + `AddCompareSlot`
  ("+ Full-member avg in current scope" quick-pick, intl-only);
  `scopeAvgLabel` produces "Men's T20I 2024-2025 avg" + "Men's
  T20I full-member 2024-2025 avg"; `slotLabel` falls through to
  `scopeAvgLabel` when the team-narrow doesn't apply.
- Tests: chip-direction invariant gained an `aus_ind_men_intl_2024_2025`
  row + a `league_avg_aux_for(team_type, team)` helper that mirrors
  the gate. New `tests/sanity/test_avg_baseline_pools.py` pins the
  three baseline modes (unbounded 104, full-member 20, scope-to-Aus 8)
  on a closed historical window (men_intl 2018). Regression suites
  re-classified: 4 URLs in scope-averages/urls.txt + 8 in teams/urls.txt
  flipped REG→NEW for the chip-baseline drift on intl team-side
  endpoints.
- Browser-agent verified: Aus + India 2024-25 avg col reads "Men's
  T20I 2024-2025 avg" + 870 matches; with `compare1_team_class=full_member`
  it reads "Men's T20I full-member 2024-2025 avg" + 140 matches; the
  RCB + SRH IPL 2025 club canary is unchanged at "Avg in Royal
  Challengers Bengaluru's leagues" + 74 matches.

**Open follow-ups** (deferred from this session):

- **`team_class` on the FilterBar.** User flagged this as wide-
  ranging — it'd change the global filter contract (FILTER_KEYS,
  scope-link URLs, status strip, etc.). Today it's a per-slot avg-
  picker control only. Decide later whether to elevate.
- **`team_class` invariant gap.** When a slot's avg uses
  `team_class=full_member`, the chip envelope on the team column
  baselines against the unbounded pool (`_league_aux` doesn't
  receive team_class). This is INTENTIONAL for the user's stated
  workflow ("Aus vs everyone" + "FM-only avg") but breaks the
  numerical chip-direction invariant when both are visible. Not
  in the test matrix today; revisit when team_class moves to the
  FilterBar (then the chip + avg col share the slot's scope by
  construction).
- **Re-flip NEW→REG.** The 12 URLs flipped to NEW in
  `scope-averages/urls.txt` + `teams/urls.txt` should be flipped
  back once the new hashes are stable in HEAD. One commit, no
  shape change.

## OLD top-of-queue entry — kept for diff context

**Avg-col baseline semantic for internationals — `scope_to_team`
narrow is wrong for open scopes.**

The `scope_to_team` auto-narrow (Phase 1 of the bucket-baseline
work) was designed for closed leagues: RCB plays in IPL → narrow
the avg-col baseline to IPL → "average of all 10 IPL teams across
74 matches" = symmetric, comparable to both RCB and SRH. ✓

For internationals it silently breaks. Australia in men_intl
2024-25 has a "tournament universe" of 6 events (the tours
Australia hosted/toured + ICC T20 WC). Narrowing the avg col to
those 6 events gives a 67-match baseline where Australia is one of
the two teams in EVERY match. Australia chips show as flatteringly
above-average by construction — Australia is half of the
"average". Comparing India to "Australia's tournament universe"
isn't meaningful either: India isn't in most of those tours.

**Two scopes the user wants the avg col to support:**

1. **All international matches in the period.** No team-narrow.
   For men_intl 2024-25 that's 870 matches across all teams —
   "what does an average international team's batting / bowling /
   fielding look like in this period". Both Australia and India
   compare against the SAME baseline. Apples-to-apples.

2. **All non-associate (= ICC full member) international
   matches.** Same period, but excluding associate team matches
   (Namibia, Nepal, Oman, USA, etc. — they dilute the baseline
   downward because the talent gap is wide). For users who think
   "average top-tier international" is the right comparand. The
   `ICC_FULL_MEMBERS` list already exists hardcoded in
   `api/routers/teams.py` for landing-page categorization — it'd
   become a filter param.

**The canonical international test URL needs both scopes to work**
(currently neither does on this URL):
```
http://localhost:5174/teams?team=Australia&gender=male&team_type=international&tab=Compare&compare1=__avg__&compare2=India&season_from=2024&season_to=2025
```

Today on this URL the avg col reads "Avg in Australia's leagues" =
the 67-match Australia-centered scope, with chips like "Australia
Run rate 9.91 ↑+27.7%" that LOOK impressive but are an artifact of
the baseline including Australia's own performance.

**Implementation sketch (next session):**

- **Mechanism A (broader default for internationals):** when
  `team_type=international` AND no tournament filter, the avg
  col's `scope_to_team` synthesis should NOT kick in — the
  baseline should be the full men_intl pool. The current behavior
  (auto-narrow) is correct for `team_type=club` (closed leagues)
  but wrong for international. One-line guard in the avg-slot
  fetcher in `frontend/src/components/teams/TeamCompareGrid.tsx`
  (`fetchSlot` → `if (slot.kind === 'avg' && !slot.scope.tournament)`
  branch). Test: Aus + Ind + men_intl 2024-25 should give an avg
  col baselined against 870 matches, with neither team being half
  of the pool.

- **Mechanism B (associate-excluding filter):** add a backend
  query param `team_class=full_member` (or similar) that filters
  to matches where BOTH teams are in `ICC_FULL_MEMBERS`. Plumb
  through `FilterParams` + filter clause. UI: a third toggle on
  the avg-slot picker — quick-picks become "League avg in current
  scope" / "Full members only" / "Same team, previous season" /
  ... User picks which baseline they want.

- **Audit the column header text.** "Avg in Australia's leagues"
  reads weirdly for internationals. With Mechanism A, the header
  for the international case becomes something like "Average
  international team" or "Men's T20I avg, 2024-25". The
  `scopeAvgLabel` in `frontend/src/components/teams/teamUtils.ts`
  needs to handle the no-narrow case.

- **Add the canonical international URL to test matrix.** Once
  Mechanism A lands, `aus_ind_men_intl_2024_2025` becomes a
  meaningful chip-direction invariant test scope alongside the
  existing IPL canonical reproducer (`ipl_2025_rcb_srh`).

**Why this is structural, not cosmetic:** the chip-direction
invariant test currently passes on `aus_unbounded` because the
self-centered baseline still satisfies ASSERT 1 (chip's scope_avg
= avg col displayed value, both computed the same way). The
invariant doesn't notice that the BASELINE ITSELF is a mirror —
the test is a value-consistency check, not a baseline-meaningfulness
check. We need a separate sanity gate or a UX call ("for
international avg-slot, the baseline should not be a function of
the primary team").

**Pickup notes for next session:**
- Read this entry first.
- The "weird text" the user noted on the canonical URL ("Avg in
  Australia's leagues") is part of this same fix — `scopeAvgLabel`
  handles club-team-with-many-leagues fine, internationals badly.
- The Conventions in `internal_docs/perf-bucket-baselines.md`
  Convention 4 + the `_scope_to_team_clause` COALESCE invariant
  are NOT what's broken here — those are correct. The structural
  issue is one layer up: WHEN to apply scope_to_team at all.

---

## NEXT SESSION — primary agenda

**Implement `internal_docs/spec-team-compare-scoped-slots.md`.**
Build-ready, 5 design decisions locked, 3-commit rollout plan in
the spec. Per-column scope override on Teams Compare so users can
do "RCB 2024 vs RCB 2025 vs IPL 2025 avg".

Pick-up notes (pre-flight checks, gotchas, international test
scenarios with the load-bearing Australia T20 WC biennial canary)
live in the `project_next_session.md` memory. Read that first; then
the spec.

3-commit rollout (in spec):

1. `useCompareSlots` hook + URL parsing + legacy migration (no UI
   change yet). Browser smoke: legacy URLs work identically.
2. TeamCompareGrid refactor + unified `CompareSlotColumn` + 3-col
   cap. Drop `t2`. SlotHeaderChip rendered always-empty.
3. `AddCompareSlot` picker + `SlotScopeEditor` + per-slot scope
   override end-to-end. Quick-picks (League-avg-current /
   Same-team-previous-season / Different-team-current /
   Same-team-all-time). Integration test additions.

Backend ZERO changes. Frontend-only feature.

## NEXT SESSION — secondary (after scoped-slots)

Compare-tab avg-column work **fully done 2026-04-24 + 2026-04-25**:
Spec 1 of `internal_docs/spec-team-compare-average.md` shipped end-
to-end across 4 phases + 2 quick wins + delta chips + halve-fielding-
rates fix. See `internal_docs/enhancements-roadmap.md` "Shipped
2026-04-24" + "Shipped 2026-04-25" entries. Tests green: regression
38+29 REG matched / 0 drifted, integration 16/16, sanity 5/5
(player_scope_stats pool conservation). NOT deployed to prod yet.

Series tab deep-dive **fully done 2026-04-20 (pm + evening) + 2026-04-21**:
- 2026-04-20: SeriesLink + Score + EdHelp + phraseLabel + (ed) across
  Matches / Records / Champions / Knockouts / /matches / Venue
  Matches; link-audit.md written.
- 2026-04-21 arc 1: Series tab migrated every remaining raw `<Link>`
  to `TeamLink`/`PlayerLink`/`SeriesLink` with `phraseLabel` +
  `subscriptSource`. Landing tile inversions dropped. Rivalry by-team
  tile title, Points tab team column, Partnerships whole tab, Records
  Largest-partnerships batters + Best-bowling bowler all cleaned up.
  Dead helpers (`renderBatter`, `renderVsTeams`, `teamLinkHref`, etc.)
  deleted.
- 2026-04-21 arc 2: feature expansion on each Series subtab. Records
  gained `best_individual_batting` table; Batters gained "By runs
  scored"; Bowlers gained "By wickets taken"; Partnerships gained
  "top 10 per wicket" (10 sub-tables from one backend query).
  Leaderboard caps standardized at 20 (batting/bowling/fielding/
  partnerships); Records stays at 10.
- **`internal_docs/links.md`** is the canonical contract for
  TeamLink / PlayerLink / SeriesLink and their `phraseLabel` +
  `subscriptSource` mechanisms — CLAUDE.md points future sessions at
  it. Read it before touching any `/teams` / player / `/series` link.

Next tabs to walk:

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

## Known deviations outside the Series tab (from 2026-04-21 spot-check)

Flagged at the top of `internal_docs/link-audit.md` as the same
pattern the Series refactor fixed. Pick these off as each tab gets
its turn — one commit per deviation, following `internal_docs/links.md`
as the contract:

- **`Home.tsx:20–87`** locally defines `TeamLink` + `PlayerLink`
  components that shadow the real ones. Raw `<Link>` with hand-rolled
  URL building; no `subscriptSource`, no phrases; the local
  `TeamLink` also inverts the name-is-all-time contract.
- **`venues/VenueDossier.tsx:38–40` + `VenueOverviewPanel.tsx:14`**
  have a local `teamLink()` helper used 10+ times in Records tables
  and Overview summary lines. Same pre-refactor pattern the Series
  dossier had. Fix: replace with `TeamWithEd`-style `TeamLink` with
  per-row edition subscriptSource.
- **`venues/VenueDossier.tsx:598–622`** — Records Largest-partnerships
  batter pair and Best-bowling bowler use `PlayerLink` but no
  `subscriptSource` so no (ed) phrase surfaces.
- **`Batting.tsx` / `Bowling.tsx` / `Fielding.tsx`** innings-list
  Opponent columns and matchup columns (bowler/batter cells) use raw
  `<Link>`. Tournament column is already `SeriesLink`. Team + player
  cells need the same conversion.
- **`Batting.tsx:507` / `Bowling.tsx:491` / `Fielding.tsx:487, 523`**
  landing-board leaderboards use raw `<Link>` via a local
  `playerLink()` URL helper, not `PlayerLink`.
- **`Teams.tsx:216, 755` (keeper lists), `1051–1054, 1083–1086,
  1178–1188` (partnerships), `1289–1296` (Players-tab roster)** —
  raw `<Link>` for player names throughout. Should be `PlayerLink`
  with compact (roster) or edition subscriptSource (partnerships).
- **`Teams.tsx` Match List columns (lines 135–139)** — Opponent /
  Venue / Tournament / Result are plain text, no links. Convention
  calls for TeamLink / venue link / SeriesLink respectively.

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
