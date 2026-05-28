# Spec — narrow the remaining frozen player cohort comparisons (Tier 3 → Tier 1), after completing fielding (3e)

**Status:** DRAFT 2026-05-28, ready for review.
**Depends on:** `spec-player-baseline-aux-fallback.md` (3a/3b/3c/3d shipped).
**Companion:** the "tier" framing below came out of the post-3d audit of
every average/cohort surface across the Players and Teams pages.

---

## 0. The three tiers (how a cohort surface responds to the six filters)

The six = venue / opponent / team / innings / toss / result.

- **Tier 1 — fully narrows.** Both the cohort AND its weighting follow all
  six. (Player by-season / by-phase / by-over scope endpoints that 3c/3d
  wired live; ALL team-side surfaces, since teams have no mix.)
- **Tier 2 — cohort narrows, MIX stays coarse.** The comparison group
  narrows by the six, but it's weighted by the player's tournament/season
  position-mix (batting) / over-mix (bowling), read from the precomputed
  per-player tables (`_position_distribution` / `_over_distribution`,
  scope-key grain only). Surfaces: the page-header "vs cohort" tiles +
  the Distribution panel prob-chips + the green cohort sparkline line, on
  the batting & bowling pages.
- **Tier 3 — does not narrow at all.** Reads a scope-key-only precomputed
  source; venue/opponent/team/innings/toss/result have zero effect.

## 1. Decision: KEEP Tier 2 (do NOT narrow the mix)

The position/over MIX (the weighting vector) stays at the
tournament/season grain. Rationale (owner, 2026-05-28): at the deepest
narrowings there isn't enough data to estimate a stable per-position /
per-over mix; a coarse-but-stable role profile is the right weighting.

**Distinguish two things that both live on the By Position / By Over
tabs** (this is the crux):

- the **mix histogram** (what fraction of the player's innings/balls fall
  in each position/over) → **the weighting → KEEP coarse (Tier 2)**.
- the **per-bucket cohort comparison values** (the "typical opener's SR",
  "typical death-over economy" bars/lines) → **Tier 3 today → make Tier 1**.

So "keep Tier 2" applies to the weighting, NOT to the per-bucket
comparison values. Narrowing the latter is consistent with the Tier 2
decision; the thin-data concern is handled by the per-bucket support
cliff (below-support buckets blank out — fewer bars, never wrong ones),
exactly as the existing cohort cliff already does.

## 2. Tier 3 inventory — every surface found (each line is a CHECK item)

Verified frozen this session unless marked "verify". Each must be
re-confirmed frozen at HEAD (red) before the fix and narrowing (green)
after.

### Batting page
- [ ] **By Position** — perf-vs-cohort bars. Source: `/batters/{id}/summary`
  `position_distribution[].cohort_*`. VERIFIED frozen (cohort SR 133.98 /
  133.88 / 136.16 identical under `inning=0`). MIX histogram stays coarse;
  cohort bars → narrow.
- [ ] **By Over** — SR / Dot% / Boundaries-per-over cohort overlay.
  Source: `/scope/averages/players/batting/by-over`
  (`compute_players_batting_by_over`). VERIFIED frozen (SR@over1 94.7
  identical under `inning=0`). 3c deliberately skipped batting by-over;
  this finishes it. → narrow live (per-over, no cross-over mix to keep).

### Bowling page
- [ ] **By Over** — mix histogram + perf-vs-cohort bars. Source:
  `/bowlers/{id}/summary` `over_distribution[].cohort_*`
  (`_over_distribution`, scope-key only). VERIFY frozen, then narrow the
  cohort bars (keep the over-mix histogram coarse).

### Fielding page — ALL of it is frozen pre-3e (these fold into Phase A / 3e)
- [ ] **By Season** line — `/scope/averages/players/fielding/by-season`.
  VERIFIED frozen (dis/match 0.75 / 0.9916 identical under `inning=0`).
- [ ] **By Phase** chips + bars — `/scope/averages/players/fielding/by-phase`.
- [ ] **By Dismissed Position** bars — `/fielders/{id}/summary`
  `dismissal_position_distribution[].cohort_*`. (Fielding is keeper-binary,
  NO position mix — so there is no Tier 2 here; the bars narrow fully.)
- [ ] **By Over** — `/fielders/{id}/by-over` `cohort_dismissals_per_match`.
  VERIFY frozen.
- [ ] page-header tiles + Distribution panel (catches/run-outs/stumpings
  per match, prob-chips, sparkline cohort line) —
  `/fielders/{id}/summary` + `/distribution`
  (`compute_players_fielding_cohort`). VERIFIED frozen (catches/match
  cohort 0.541 identical under `inning=0`). Keeper-binary, no mix → after
  3e these are Tier 1 (NOT Tier 2).

### Confirmed NOT Tier 3 (already Tier 1 — leave alone)
- Batting **Inter-Wicket** SR-by-wickets-down cohort line — narrows
  (129.2 → 125.7). Batting **Dismissals** scope cohort — narrows
  (3450 → 1820). Batting/Bowling **By Season** + **By Phase** — narrow
  (3c/3d). All **Teams** surfaces — narrow (no mix).

### The gender-global grey sparkline reference line
- Static all-T20 anchor by design — NOT in scope (it is intentionally
  scope-independent).

## 3. Sequencing — 3e first, then the Tier-3 sweep

**Phase A = 3e (do first).** Fielding cohort live — `compute_players_fielding_cohort`
(summary chip + distribution) + `_by_season` + `_by_phase`, dispatch on
`is_precomputed_scope`, fielding orientation via a `_fielding_live_where`
mirroring `_bowling_live_where`. Keeper-binary partition (`is_keeper=0|1`),
no mix weighting (D5). Catches convention: `kind IN ('caught',
'caught_and_bowled')` AND `COALESCE(is_substitute,0)=0` (Convention 3).
Reads `matchfielderperf`. Parity-probe live == precomputed at none-of-six
(like bowling's 440-cell check). This clears 4 of the fielding Tier 3
rows (by-season, by-phase, summary, distribution) AND makes the fielding
side ready for the bar fix.

Why first: the fielding By Dismissed Position / By Over bars can't narrow
cleanly until the fielding per-bucket cohort is computed live; doing 3e
first lets Phase B treat batting/bowling/fielding bars with one pattern.

**Phase B = Tier-3 bar + by-over sweep.** For each discipline's
"distribution-array" tab, narrow the per-bucket cohort values while
keeping the mix histogram coarse:
- batting By Position cohort bars, batting By Over chart,
- bowling By Over cohort bars,
- fielding By Dismissed Position + By Over bars (keeper-binary, full narrow).

**Key design choice to resolve in Phase B (CHECK):** the narrowed
per-bucket cohort the bars need *already exists* — `compute_players_batting_cohort`
returns `by_position[]` and `compute_players_bowling_cohort` returns
`by_over[]` with live-narrowed per-bucket rates (3b/3d). So the bars may
just read the cohort block's `by_position[]` / `by_over[]` (already on the
summary response?) instead of `position_distribution[].cohort_*`. VERIFY
whether the summary response exposes the narrowed `cohort.by_position` /
`cohort.by_over`; if so, Phase B is largely a frontend re-point + a
support-cliff blank, no new SQL. If not, add the narrowed per-bucket
fields to the summary payload (or a small by-position scope endpoint).
The mix histogram keeps reading `position_distribution` / `over_distribution`.

## 4. Per-surface implementation pattern (reuse, don't fork)

1. Reuse `_batting_live_where` / `_bowling_live_where` / new
   `_fielding_live_where`. Dispatch on `is_precomputed_scope`.
2. Parity probe: live aggregation == precomputed source at none-of-six,
   byte-identical (0 mismatches), before wiring.
3. SQL-anchor each narrowed value against a direct delivery/match query
   (incl. the inning-flip + opponent-flip orientations).
4. Per-bucket support cliff: below-threshold buckets return null → the bar
   / chart point is absent, not wrong.
5. One commit per surface; REG→NEW pre-flip in the preceding commit.

## 5. Test plan — expect rot, sweep up front

Some integration + regression tests WILL fail when these narrow — this is
expected and is the red→green signal. Do the sweep BEFORE shipping each
slice (the lesson from the 3c `filter_matrix` rot):

- **Grep first:** `grep -rln` the affected endpoints + the asserted frozen
  values across `tests/integration/*.sh`. Re-run every hit.
- **Rewrite frozen assertions to be `below_support`-aware** — present when
  the cohort is supported, absent when thin (the pattern
  `player_baseline_filter_matrix` already uses). Candidate tests to check:
  `position_distribution_chart.sh`, `over_distribution_chart.sh`,
  `dismissed_position_chart.sh`, `batting_by_over_charts.sh`,
  `fielding_by_over_charts.sh`, `fielding_by_phase_charts.sh`,
  `player_baseline_chart_overlays.sh`, `player_baseline_by_phase_chips.sh`,
  `player_baseline_filter_matrix.sh`, plus the fielding distribution/summary
  suites for 3e.
- **Regression:** enumerate every REG URL hitting the affected endpoints
  with one of the six (grep `tests/regression/*/urls.txt`), flip REG→NEW
  in the preceding commit, ship, flip back. The fielding parity-spec URLs
  are already staged NEW.
- **Extend** `tests/integration/player_baseline_aux_fallback.sh` with a
  fielding section (mirror §7-§9) for 3e, and By-Position/By-Over
  narrowing assertions for Phase B.
- Re-run the FULL player + relevant team regression + integration suite
  after each phase; treat any unexplained REG drift as a real failure.

## 6. Out of scope
- Tier 2 (the coarse mix) — KEPT by decision §1.
- The gender-global static sparkline reference line.
- Team surfaces — already Tier 1.
