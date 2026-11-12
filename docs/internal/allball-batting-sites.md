# All-ball batting-runs convention — `batting.py` site enumeration

Commit-1 deliverable of `spec-batting-allball-runs-single-source.md` §7.1.
Every `runs_batter` / balls site in `api/routers/batting.py`, classified
**runs-sum-to-convert** vs **legitimate legal-filter to keep**, with the
balls/SR/HAVING denominator each pairs with. The Commit-4 fix and its
per-site assertions work off this list.

## The convention (target)
- runs / fours / sixes = over **all** the batter's deliveries (no-ball
  off-bat runs + boundaries included). Keep the `runs_non_boundary = 0`
  guard on fours.
- balls faced / dots / SR-denominator = **legal balls only**
  (`extras_wides = 0 AND extras_noballs = 0`).

## Two fix patterns

**Pattern X — WHERE-restricted sites.** The delivery row set is
legal-gated by the WHERE (`_batting_filter` or an inline gate). Fix:
drop the `extras_wides=0 AND extras_noballs=0` from the WHERE so
runs/fours/sixes go all-ball, then re-gate the balls denominator
(`COUNT(*)` → `SUM(CASE WHEN <legal> THEN 1 ELSE 0 END)`), the
`HAVING COUNT(*)`, and the SR `COUNT(*)`. dots already carry their own
`extras_wides=0 AND extras_noballs=0` in the CASE → unaffected. fours/
sixes already CASE on `runs_batter = 4/6` → become all-ball for free.

**Pattern Y — CASE-gated striker sites.** Use `_batting_innings_filter`
(no WHERE legal gate); striker contributions gated by a `_stk`
(`batter_id = :person_id AND legal`) CASE. Fix: split `_stk` into
`_stk_faced` (`batter_id` only — runs/fours/sixes) and `_stk_legal`
(`batter_id AND legal` — balls + SR denominator).

`_batting_filter` (`:167`) drops its legal gate (becomes the all-ball
faced filter); a module constant `_LEGAL = "d.extras_wides = 0 AND
d.extras_noballs = 0"` feeds the re-gated balls/dots CASEs.

## Pattern X sites (WHERE-restricted; widen WHERE + re-gate balls)

| # | fn / endpoint | lines | runs site | balls / HAVING / SR denominator to re-gate |
| --- | --- | --- | --- | --- |
| X1 | `batting_leaders` (filtered) | 288–300 | `SUM(d.runs_batter) AS runs` (290) | `COUNT(*) AS balls` (291); `HAVING COUNT(*) >= :min_balls` (299) |
| X2 | `batting_leaders` (unfiltered) | 313–322 | `SUM(d.runs_batter) AS runs` (315) | `COUNT(*) AS balls` (316); `HAVING COUNT(*)` (321) |
| X3 | `batting_summary` core | 428–443 | runs (432), fours (433), sixes (435) | `COUNT(*) as balls_faced` (431); dots (436) KEEP |
| X4 | `batting_by_innings` bowler_id path | 645–654 | `runs_expr`=`SUM(d.runs_batter)` (648); fours/sixes (650–653) | `balls_expr`=`COUNT(*)` (649); `sr_expr` `COUNT(*)` (654) |
| X5 | `batting_vs_bowlers` | 740–769 | runs (759), fours (760), sixes (762) | `COUNT(*) as balls` (758); `HAVING COUNT(*)` (769); dots (763) KEEP |
| X6 | `batting_by_over` | 828–839 | runs (835), fours (836), sixes (838) | `COUNT(*) as balls` (834); dots (839) KEEP |
| X7 | `batting_by_phase` | 899–914 | runs (910), fours (911), sixes (913) | `COUNT(*) as balls` (909); dots (914) KEEP |
| X8 | `batting_by_season` core | 1023–1035 | runs (1031), fours (1032), sixes (1034) | `COUNT(*) as balls` (1030); dots (1035) KEEP |
| X9 | `_inter_wicket_cohort_sr` | 1311–1320 | `SUM(COALESCE(runs_batter,0)) AS runs` (1317) | `COUNT(*) AS balls` (1318); inline `WHERE extras_wides=0 AND extras_noballs=0` (1320) |

## Pattern Y sites (CASE-gated striker; split `_stk`)

| # | fn / endpoint | lines | runs CASE (drop legal) | balls CASE (keep legal) |
| --- | --- | --- | --- | --- |
| Y1 | `batting_summary` innings agg | 458–463 | `innings_runs` gated `batter_id AND legal` (458–460) → `batter_id` only | `innings_balls` (461–463) KEEP |
| Y2 | `batting_by_innings` inclusive path | 657–668 | `runs_expr`/`fours`/`sixes` via `_stk` (660–665) | `balls_expr` (661) + `sr_expr` denom (667–668) KEEP |
| Y3 | `batting_by_season` innings agg | 1056–1059 | `innings_runs` gated `batter_id AND legal` (1058) → `batter_id` only | (innings_balls counterpart) KEEP |
| Y4 | `_innings_master_sample` | 1495–1523 | `_stk` runs/fours/sixes (1504–1510); phase `runs_pp/mid/death` (1513–1521) drop legal | `balls` (1505) + phase `balls_pp/mid/death` (1515–1523) KEEP |
| Y5 | `batting_distribution` per-innings | 1391–1410 | runs (1398), fours (1401–1404), sixes (1405–1408) gated `batter_id AND legal` → `batter_id` only | `balls` (1395) + dots (1409–1410) KEEP |

## NOT sites (read cohort tables / unrelated — no batting.py change)

- `_position_distribution` (35–164): `SUM(pssp.runs)` / `SUM(pssp.legal_balls)`
  (92, 109) read `playerscopestatsposition` — corrected by the Commit-3
  rollup, not here.
- Summary cohort comparison numbers (`wrap_metric(..., "bat_balls_faced", …)`
  etc.): cohort side reads the precomputed tables — Commit 3.
- `dism_sql` / dismissal `COUNT(*)` (302, 324, 795, 869, 950, 1156, 1179,
  1194, 1209): wicket counts, not runs/balls — unaffected.
- `i.super_over` / `_batting_innings_filter` row-set predicates: unchanged.

## Verification (Commit 4)
One assertion per X/Y site: own number == all-ball SQL at a stable scope;
SR denominator == legal-ball SQL (proves balls didn't silently absorb
no-balls). Kohli summary 13117 → 13166 is the headline red-then-green.
