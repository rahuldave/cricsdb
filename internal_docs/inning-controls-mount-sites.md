# Inning controls — InningToggle + Splits Mosaic mount-site inventory

**Status:** Source-of-truth inventory as of 2026-05-15. Updated when a mount site moves.

**Purpose:** A single place to look up where the inning-narrowing affordance — `InningToggle` (the 3-pill row) or `SplitsMosaic` (the 4-quadrant chart) — currently mounts on each route × subtab, so future redesign / rollout decisions don't depend on recall.

Companion docs:
- `spec-splits-mosaic.md` — the shipped Teams Mosaic spec
- `splits-mosaic-discipline.md` — Mosaic rules (palette, share-denominator-follows-filter, aux gating)
- `splits-mosaic-cross-page.md` — DESIGN doc for the cross-page rollout
- `spec-inning-split.md` — the original inning-toggle spec (§3.3 + §6.1 govern where the toggle mounts; §3.3 also notes the toggle is deferred for deprecation on pages where the Mosaic takes over)

CLAUDE.md "Page conventions → Inning-toggle labels — POV-aware via `useDiscipline()`" is the rule about pill *labels*; this doc tracks *mount locations*.

---

## 1. Inventory

Auto-verifiable: `grep -rn "InningToggle\|SplitsMosaic" frontend/src --include='*.tsx'` plus each page's `tabs` / `TABS` / `BASE_TABS` constant. Anything in this table that disagrees with the source has been moved — update the table.

| Page / route | Subtab | InningToggle | Splits Mosaic | Mount location in source |
|---|---|:-:|:-:|---|
| `/teams` (landing — no team) | (n/a) | – | ✓ | `Teams.tsx:394` (cross-team landing variant) |
| `/teams?team=X` | By Season | – | ✓ | `Teams.tsx:492` — page-level, above the tab bar |
| `/teams?team=X` | vs Opponent | – | ✓ | (same mount) |
| `/teams?team=X` | Compare | – | ✓ | (same mount) |
| `/teams?team=X` | Batting | – | ✓ | (same mount) |
| `/teams?team=X` | Bowling | – | ✓ | (same mount) |
| `/teams?team=X` | Fielding | – | ✓ | (same mount) |
| `/teams?team=X` | Partnerships | – | ✓ | (same mount) |
| `/teams?team=X` | Players | – | ✓ | (same mount) |
| `/teams?team=X` | Match List | – | ✓ | (same mount) |
| `/batting` (landing) | (n/a) | ✓ | – | `Batting.tsx:211` — page-level (covers landing + profile) |
| `/batting?player=Y` | By Season | ✓ | – | (same mount) |
| `/batting?player=Y` | By Over | ✓ | – | (same mount) |
| `/batting?player=Y` | By Phase | ✓ | – | (same mount) |
| `/batting?player=Y` | vs Bowlers | ✓ | – | (same mount) |
| `/batting?player=Y` | Dismissals | ✓ | – | (same mount) |
| `/batting?player=Y` | Inter-Wicket | ✓ | – | (same mount) |
| `/batting?player=Y` | Innings List | ✓ | – | (same mount) |
| `/bowling` (landing) | (n/a) | ✓ | – | `Bowling.tsx:192` — page-level |
| `/bowling?player=Y` | By Season | ✓ | – | (same mount) |
| `/bowling?player=Y` | By Over | ✓ | – | (same mount) |
| `/bowling?player=Y` | By Phase | ✓ | – | (same mount) |
| `/bowling?player=Y` | vs Batters | ✓ | – | (same mount) |
| `/bowling?player=Y` | Wickets | ✓ | – | (same mount) |
| `/bowling?player=Y` | Innings List | ✓ | – | (same mount) |
| `/fielding` (landing) | (n/a) | ✓ | – | `Fielding.tsx:240` — page-level |
| `/fielding?player=Y` | By Season | ✓ | – | (same mount) |
| `/fielding?player=Y` | By Over | ✓ | – | (same mount) |
| `/fielding?player=Y` | By Phase | ✓ | – | (same mount) |
| `/fielding?player=Y` | Dismissal Types | ✓ | – | (same mount) |
| `/fielding?player=Y` | Victims | ✓ | – | (same mount) |
| `/fielding?player=Y` | Innings List | ✓ | – | (same mount) |
| `/fielding?player=Y` | Keeping | ✓ | – | (same mount; tab itself conditional on `innings_kept > 0`) |
| `/players` (landing) | (n/a) | – | – | Toggle gated on `playerId` |
| `/players?player=Y` | (no inner tabs) | ✓ | – | `Players.tsx:43` — page-level above SinglePlayerView |
| `/series?series=…` | Overview | – | – | Toggle gated to "statistical" subtabs |
| `/series?series=…` | Editions | – | – | (gated out) |
| `/series?series=…` | Batting | ✓ | – | `TournamentDossier.tsx:640` (conditional render) |
| `/series?series=…` | Bowling | ✓ | – | (same mount, gated to subtab list) |
| `/series?series=…` | Fielding | ✓ | – | (same) |
| `/series?series=…` | Partnerships | ✓ | – | (same) |
| `/series?series=…` | Records | ✓ | – | (same) |
| `/series?series=…` | Matches | – | – | Calendar list, no innings axis |
| `/venues?venue=…` | Overview | – | – | Toggle gated; Overview already splits natively |
| `/venues?venue=…` | Batters | ✓ | – | `VenueDossier.tsx:197` (conditional render) |
| `/venues?venue=…` | Bowlers | ✓ | – | (same) |
| `/venues?venue=…` | Fielders | ✓ | – | (same) |
| `/venues?venue=…` | Matches | – | – | Calendar list |
| `/venues?venue=…` | Records | ✓ | – | (same conditional mount) |
| `/head-to-head` | (any) | – | – | Rivalry page, neither widget |
| `/matches`, `/league`, `/help`, `/` | (any) | – | – | Neither widget |

Counts:
- **13 distinct InningToggle mount sites** (page-level on `/batting`, `/bowling`, `/fielding`, `/players`; subtab-gated on `/venues` × 4 + `/series` × 5).
- **1 Splits Mosaic mount site** (`/teams`, with landing + selected variants of the same component).
- **0 co-mount today**, **12 planned** (see §3).

---

## 2. Why they are mutually exclusive today

The Mosaic *includes* the inning-narrowing affordance: clicking a W/T/L cell writes `?inning=` (plus `toss_outcome`, `result`) on the URL. The InningToggle's 3-pill row is the same affordance with one axis of choice; the Mosaic is the 3-axis superset.

When the Mosaic mounted on `/teams` (2026-05-11 ship), the InningToggle on `/teams` was removed in commit `1b61cca` (2026-05-12) — same reasoning: the Mosaic owns inning narrowing on any page where it's mounted, so the toggle would be redundant UI clutter.

This precedent governs the cross-page rollout: at every site where the Mosaic lands, the InningToggle on that site comes out **in the same commit**. They co-mount only transiently inside a PR diff, never in shipped state.

Spec reference: `spec-inning-split.md §3.3` flags this as "toggle deprecation deferred"; the deprecation rule has been applied site-by-site as the Mosaic rolls out.

---

## 3. Cross-page rollout queue (12 sites)

The 12 InningToggle sites currently without the Mosaic are exactly the queue. Design doc: `splits-mosaic-cross-page.md` (open questions: subject, baseline, aux semantics per page).

| Site | Page POV (`useDiscipline()`) | Mosaic subject | Open design Q |
|---|---|---|---|
| `/batting` landing + profile | `batting` | Player or aux'd player | What's "won" when the subject is a player not a team? Likely `player_team` aux → "the team the player played for won" |
| `/bowling` landing + profile | `bowling` | Same | Same |
| `/fielding` landing + profile | `fielding` | Same | Same — fielding inherits bowling POV |
| `/players?player=Y` | `null` (ambiguous) | Player | Multi-discipline mount — neutral POV; what does W/T/L mean? Likely `player_team` aux applies symmetrically |
| `/venues?venue=…` Batters | `batting` | The venue itself | "Won" probably becomes "bat-first won" (no subject team; the original axis is venue-conditional) |
| `/venues?venue=…` Bowlers | `bowling` | Same | Same |
| `/venues?venue=…` Fielders | `fielding` | Same | Same |
| `/venues?venue=…` Records | `null` | Same | Same; multi-discipline like Players |
| `/series?series=…` Batting | `batting` | The series | "Won" = bat-first won (no subject team), OR the result axis collapses (most series aren't 50/50) |
| `/series?series=…` Bowling | `bowling` | Same | Same |
| `/series?series=…` Fielding | `fielding` | Same | Same |
| `/series?series=…` Partnerships | `batting` | Same | Partnerships is a batting concept |
| `/series?series=…` Records | `null` | Same | Multi-discipline |

(The 12-vs-13 reconciliation: `/series` has 5 statistical subtabs and `/venues` has 4, summing to 9; plus 1 Players + 3 discipline-page pairs that each count as 1 mount, but the discipline pages each have a single page-level mount serving landing + profile = 3, not 6 — total 9 + 3 + 1 = 13 toggle sites today, of which Teams shipped 1 cross-over = 12 remaining.)

Win/Loss semantic per page is the key blocker for the rollout — see `splits-mosaic-cross-page.md §2`.

---

## 4. Decision support — where SHOULD each widget live?

This is the question this doc is here to support. The matrix to think about for any candidate site:

1. **Is the page's data axis "per-match" or "per-innings"?** If it's `delivery`-grained aggregations (batting / bowling / fielding stats), per-innings narrowing is meaningful → InningToggle or Mosaic candidate. If it's calendar/event-grained (Matches lists, Editions, Overview cards), inning narrowing is not meaningful → neither widget (this is why /venues Matches and /series Editions are gated out today).

2. **Does the page have a subject the Mosaic can attribute "won/lost" to?** Teams → team (clean). Players → `player_team` aux works. Venues / Series → bat-first-won is the natural fallback. If even the fallback is incoherent (e.g. cross-format aggregates), Mosaic is wrong; InningToggle is still fine.

3. **Mobile budget.** The Mosaic is now ≈ a 2× quadrant (cf606d8 shrink-fit); the InningToggle is a 3-pill row. On already-dense pages (Players profile, with many sections), an additional Mosaic may overwhelm. Consider this when deciding.

4. **Filter affordance vs. data display.** The Mosaic is both: it shows the 4-cell breakdown AND writes `?toss + inning + result` on click. If the page already exposes those URL params via FilterBar / Aux row, the Mosaic is the richer affordance. If the page has no need for toss/result narrowing in scope, an InningToggle alone is sufficient.

Quick rule: **whenever both fit, prefer the Mosaic** (the toggle is a strict subset) — unless mobile density says otherwise.

### 4.1 Standalone result-only filter (`ResultFilter.tsx`)

A leaner `<ResultFilter />` component exists at `frontend/src/components/ResultFilter.tsx` — 4 pills (All / Won / Lost / Tied) with scope-wide counts, writing only `?result=`. Tied collapses ties + no-results to mirror the Mosaic and the API's `?result=tied` predicate.

**Current mount sites: zero.** It was briefly mounted on Teams Match List subtab (commits `e880abd` / `ce430b2`) but unmounted in the next iteration after we decided the Mosaic's cross-axis quadrant-click affordance ("won the toss, batted first, AND won") is uniquely useful above the match list — the chronological list is exactly the materialization the user wants to scan after picking a slice. The component file stays warm for future placements:

- `/head-to-head` — per-side W/L pill row is the natural rivalry framing; Mosaic doesn't fit cleanly (two subjects).
- `/matches` with `filter_team=X` — pure list filter; no Mosaic queued there.
- `/players?player=Y` and the discipline-page profiles — once `player_team` aux ships, ResultFilter is the lighter alternative to the full Mosaic for player-grain result narrowing.

The decision rule: **mount ResultFilter where there's a clear W/L subject but the Mosaic's 3-axis chart would be overkill or has no clean baseline.** Don't co-mount with the Mosaic — they both write `?result=` and the duplication is confusing UI.

---

## 5. Maintenance

When a mount site moves:

```bash
grep -rn "InningToggle\|SplitsMosaic" frontend/src --include='*.tsx'
```

Cross-check the table. If the source disagrees with the table, the source is right — update the table in the same commit as the move.

For new pages with an innings-level data axis, this doc is the place to record the decision (toggle / mosaic / neither) and the reason. The decision lives here, not in spec-* files (those describe behavior; this describes placement).
