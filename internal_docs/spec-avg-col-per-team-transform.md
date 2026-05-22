# Spec — Per-team transform for the avg column's RESULTS metrics

> **Status:** PARTIAL. Backend shipped 2026-04-28 (`236eaf7` "backend:
> avg col returns per-team averages for results metrics") —
> `_per_team_one` / `_per_team_two` helpers live in
> `api/routers/teams.py:680-686`. **Verify whether frontend consumes
> the new per-team transform** before treating this as fully done — no
> dedicated frontend follow-up commit was visible in the audit.

The Compare-tab avg column displays pool totals where it should
display per-team averages for RESULTS metrics (matches, wins, losses,
ties, no_results, toss_wins, bat_first_wins, field_first_wins,
win_pct). User-flagged after seeing **`matches.scope_avg = 140`** on
the Aus + Full-member avg + India URL — comparing Aus's 16 matches to
"league avg of 140" is meaningless because no team plays 140 matches.

This spec extends the existing per-INNINGS transform convention
(documented in CLAUDE.md "**'Average' means per-innings, NOT pool**")
with a parallel **per-TEAM** transform for team-level results metrics.

---

## 1. The bug, in concrete numbers

Closed scope: men's intl 2024-25, full-member-only.

| Metric | Pool total | Per-team avg (correct) | Today's `scope_avg` |
|---|---|---|---|
| matches | 140 (count) | 140 × 2 / 11 = **25.5** | 140 (BUG) |
| wins | 134 (= decided) | 134 / 11 = **12.2** | null (not surfaced as scope_avg) |
| toss_wins | 140 (= toss_decided) | 140 / 11 = **12.7** | 140 (BUG) |
| bat_first_wins | 64 | 64 / 11 = **5.8** | 64 (BUG) |
| field_first_wins | 70 | 70 / 11 = **6.4** | 70 (BUG) |
| ties | 2 | 2 × 2 / 11 = **0.36** | 2 (BUG) |
| no_results | 4 | 4 × 2 / 11 = **0.73** | 4 (BUG) |
| win_pct | n/a | 134 × 100 / (140 × 2) = **47.86%** | 47.8% (`bat_first_win_pct` substitution — close but wrong semantic) |

Why each metric divides differently:

- **Matches** count once in the pool but each involves 2 teams, so per-
  team total is `pool × 2 / unique_teams`.
- **Wins / losses / toss_wins / bat_first_wins / field_first_wins**
  generate exactly 1 instance per match (not 2 — a match has 1 winner,
  not 2). Per-team total is `pool / unique_teams`.
- **Ties / no_results** each generate 2 instances per match (both teams
  share the outcome). Per-team total is `pool × 2 / unique_teams`.
- **win_pct** for an individual team is `wins / (wins + losses + ties +
  no_results)`. Averaged over the league, this collapses to
  `decided / (matches × 2) × 100` (algebra: each match contributes 1
  to the numerator if decided + 0 else, and 2 to the denominator
  unconditionally).

The current code (`api/routers/teams.py:225-228`) substitutes
`bat_first_win_pct` for `win_pct.scope_avg` with an explanatory
comment ("collapses to ~50% by construction; render the bat-first
share as the informative league signal"). That substitution is
honest but the value is labeled `win_pct` end-to-end, so consumers
read "Aus 81.2% vs league win% 47.8%, +69.9% above league" — the
chip is comparing Aus's actual win rate to the league's bat-first
win share, which are different things. The numerical correction is
small (47.86% vs 47.76% on this scope) but the SEMANTIC label is
wrong.

---

## 2. Why this is latent until v3

Pre-v3 (before 2026-04-27), the international avg column used the
`scope_to_team` auto-narrow: Aus + avg col on intl 2024-25 showed
"avg in Aus's leagues" with 67 matches. That was already
team-centric (the "avg team" was implicitly Aus-shaped), so
the pool-total-as-scope_avg was less obviously wrong.

After 2026-04-27 mech A killed `scope_to_team` for internationals,
the avg col went to the full pool (870 matches). After v3 added
FM-only as the alternative narrow (140 matches), the gap is
smaller but still 5.6× too big.

The /scope/averages/* per-INNINGS transform (`_apply_batting_per_innings`
etc.) covered batting/bowling/fielding rates correctly. The team-
level RESULTS transform was just never written — the convention
stops at the discipline boundary.

---

## 3. Mental model

Three classes of metrics with different aggregation semantics:

| Class | Example | Per-X transform | Scope-avg endpoint |
|---|---|---|---|
| Per-innings rates | run_rate, boundary%, dot% | `pool ÷ innings_count` | `/scope/averages/batting/summary`, etc. |
| Per-team RESULTS counts | matches, wins, toss_wins | `pool × {1, 2} ÷ unique_teams` | `/scope/averages/summary` |
| Per-team RESULTS rates | win_pct, bat_first_win_pct | `decided ÷ (matches × 2) × 100` (win_pct) or `bat_first_wins ÷ decided × 100` (bf_pct) | same |

Multiplier is 2 for metrics where each match generates 2 instances
(matches, ties, no_results) and 1 for metrics where each match
generates 1 instance (wins, toss_wins, bat_first_wins,
field_first_wins).

The TEAM endpoint (`/teams/{team}/summary`) returns POOL counts for
the team itself (Aus's actual 16 matches) — those don't change.
Only the `scope_avg` field in each metric's envelope shifts to per-
team averages.

---

## 4. Surface changes

### 4.1 `api/routers/scope_averages.py::scope_summary`

Add a `_unique_teams` query alongside the pool totals. Apply per-
team divisor in a new helper `_apply_results_per_team(d, unique_teams)`
called at the end of both `_summary_from_baseline` and
`_summary_live`.

Response shape change (BREAKING for chip baselines that key on these
fields):

| Field | Before | After |
|---|---|---|
| `matches` | int (pool) | float (per-team) |
| `decided` | int (pool) | float (per-team) — wins/losses share |
| `ties` | int (pool) | float (per-team) |
| `no_results` | int (pool) | float (per-team) |
| `toss_decided` | int (pool) | float (per-team) |
| `bat_first_wins` | int (pool) | float (per-team) |
| `field_first_wins` | int (pool) | float (per-team) |
| `bat_first_win_pct` | float | float (unchanged — already a percentage) |
| `win_pct` | (NEW) | float — per-team avg = decided / (matches × 2) × 100 |
| `unique_teams_in_scope` | (NEW) | int — diagnostic / divisor |

Round to 1 decimal for display consistency.

### 4.2 `api/routers/teams.py::team_summary`

The scope_query already returns pool totals; add `unique_teams_in_scope`
to it. Apply per-team divisor when stuffing `scope_avg` into each
envelope. Replace the `s_win_pct = round(s_bf * 100 / s_decided, 1)`
substitution with the true per-team average:
`s_win_pct = round(s_decided * 100 / (s_matches * 2), 1)`.

For metrics where the comment "scope_avg collapses to ~50% — render
bat-first instead" was load-bearing UX, surface a SEPARATE `bat_first_win_pct`
field on the response if the avg col wants to display the tactical
bias signal. Today the avg col displays only what's in `/scope/averages/summary`,
so the rename happens there.

### 4.3 Frontend (Compare grid + Avg col)

`getScopeAverageProfile` consumes the new shape; `TeamCompareGrid`
renders whatever `summary` returns. No frontend code change required —
the values just shift downward. The displayed labels stay ("Matches",
"Toss wins", etc.).

The chip envelope's `scope_avg` lands at per-team on both sides; the
chip-direction invariant (`tests/sanity/test_chip_direction_invariant.py`
ASSERT 1) is automatically maintained because both consumers (avg
col + team chip) read from the same backend math.

### 4.4 No /scope/averages/summary spec consumers external to the app

`/scope/averages/summary` is consumed by the Compare grid only. No
external clients today. So we can change its response shape without
versioning.

---

## 5. Test plan

### 5.1 Sanity (closed-window pinned numbers)

`tests/sanity/test_chip_direction_invariant.py` already enforces
`chip.scope_avg == displayed_avg` on `matches`. Post-fix it'll pass
naturally because both sides go to per-team. **Re-running it will
catch regressions in either direction.**

`tests/sanity/test_team_class_baseline_numbers.py` — A1, A2, D1,
D2 anchors check `matches` from `/scope/averages/summary`. Post-
fix, those need re-pin to the per-team value:
- A1 (men_intl 2024-25 unbounded): was 870 → now `870 × 2 / N_teams`
- A2 (men_intl 2024-25 FM): was 140 → now 140 × 2 / 11 ≈ 25.5
- D1 (women_intl 2024-25): was 596 → now `596 × 2 / N_teams_women`
- D2 (women_intl 2024-25 FM): was 97 → now 97 × 2 / 12 ≈ 16.2 (or 11)

Or: keep A1/A2 anchored on pool totals via a SEPARATE endpoint /
SQL-direct path, and add NEW per-team anchors. Cleanest is to
re-pin in place — the anchor file documents that the pin is
"per-team avg as displayed in the avg col."

### 5.2 Regression

URLs hitting `/scope/averages/summary` and `/teams/{team}/summary`
will drift. Affected suites:
- `scope-averages/urls.txt` — every URL hitting the summary endpoint.
- `teams/urls.txt` — every URL hitting `/teams/{team}/summary` (envelope
  fields' `scope_avg` shift).
- `players/urls.txt`, `batting/urls.txt`, etc. — only if they hit
  either endpoint indirectly. Likely none, but check.

Workflow:
1. Identify drifted REG URLs.
2. Flip them to NEW in a prior commit.
3. Ship the backend change.
4. Re-run; expect `0 REG drifted, N NEW changed, 0 NEW unchanged`.
5. After 1-2 weeks of stable HEAD, flip back to REG.

### 5.3 Browser verify

URL E1 (Aus + FM avg + India, FilterBar fm 2024-25) post-fix:
- Aus matches col: 16 (unchanged).
- Avg col matches: ~25.5 (was 140).
- India col matches: 31 (unchanged).
- Aus chip on matches reads "16 vs 25.5, -37%" (below avg — Aus
  played fewer matches than the typical FM team in 24-25).
- India chip on matches reads "31 vs 25.5, +22%" (above avg — Ind
  played more).

Same for toss_wins, bat_first_wins, etc. — all chip baselines now
match per-team logic.

---

## 6. Migration

Single commit (no need to split, since the test failures all
self-resolve once the consumer math agrees with the producer):

1. Backend: `_apply_results_per_team` helper + `unique_teams`
   subquery in both endpoints. Replace `s_win_pct` formula. Update
   chip-direction invariant if any field-name renames happen.
2. Test suite: re-pin anchor numbers. Re-run regression — flip
   drifted REG URLs to NEW (same workflow as the v3 commit-4
   pattern). The flip can ride in the same commit if it's small
   (<20 URLs); split if larger.
3. Browser-verify URL E1 + a club URL (defensive — IPL avg should
   still produce sensible per-team averages, not get distorted).
4. Docs: log under `enhancements-roadmap.md` "Shipped 2026-04-28"
   continuation; add a CLAUDE.md convention bullet pinning the
   per-team transform alongside per-innings.

---

## 7. Out of scope

- The two parked sibling specs from v3 (`spec-slot-override-chip-alignment.md`
  and `spec-filterbar-series-type.md`) are unrelated and stay parked.
- DOM-tests Batch 1 stays unblocked — anchor URLs assumed v3, not
  this transform; numbers shift but the structural assertions
  (column count, header text, narrowing direction) hold.

---

## 8. Estimated effort

~2 hours focused work:
- 30 min: backend change + helper.
- 30 min: chip-invariant + baseline-numbers test re-pin.
- 30 min: regression diff + REG↔NEW flips.
- 30 min: browser verify + doc updates + commit.

Risk: low. The transform is mechanical, the bug is universally agreed,
and the test infrastructure already enforces the consumer-side
invariant.

---

*Spec written 2026-04-28 in the same session that ships it.*
