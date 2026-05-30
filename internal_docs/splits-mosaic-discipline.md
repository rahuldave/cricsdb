# Splits Mosaic — discipline

The Splits Mosaic is a filter widget that LOOKS like a stat chart. It encodes the joint distribution of toss × inning × result for a subject team, with a fixed axis ordering that lets the reader read color as outcome and position as conditioning.

Specs: `spec-splits-mosaic.md` (Teams-only — implemented 2026-05-11), `splits-mosaic-cross-page.md` (cross-page reuse design).

This doc captures the **inviolable rules**. The spec captures the **design**.

## Two surfaces: navigation bar vs live readout (the dual-use split)

The Mosaic is both a *display* (what does this scope look like?) and a
*widget* (click to narrow). Those two jobs sit on two separate surfaces
so neither lies when the other is active:

| Surface | Source | Behaviour under a filter |
|---|---|---|
| **Reset / navigation bar** — one flex-wrap row: `All matches · N Δ`, `All toss · N`, `Both innings · N`, `All won / All tied / All lost · N (s%) Δ` | summed joint cells (`ResetBar`) | **Conditional.** Each entry shows the count of the slice you'd LAND ON: it drops/switches only its own axis and HOLDS the others. `All matches` is the full reset (clears all aux; volume delta). Mounted in **every** layout branch (2×2, 1D bar, 0-free strip). |
| **Northwest corner** — Won/Tied/Lost stacked one-per-line, colored swatch + count + share% + delta | aux-**filtered** (`data.marginals`) | **Live.** Under `result=won` reads Won N / Tied 0 / Lost 0. Clickable (filter result). Stacked vertically to survive the ~min-content corner track at 390w. |
| **Toss column-headers + inning row-headers** | aux-**filtered** (`data.marginals`) | **Live** — re-split within the slice (e.g. `result=won` takes the toss line 133/133 → 79/69), with live deltas. |

### Conditional counts + deltas are summed from the joint cells

`ResetBar` computes every entry by summing the **aux-stripped joint
cells** (`unauxData.cells`), holding the currently-active axes fixed and
freeing/switching its own. This works because each cell carries `share`
(= n / full total) AND `league_share` (the league's fraction in that
cell), and **both are additive** — so a conditional count is `Σ n`, its
share-of-all is `Σ share`, and its vs-typical-team delta is
`(Σ share − Σ league_share) / Σ league_share`. No extra fetch.

> **Invariant — `/teams/splits` must emit the FULL 12-cell joint in
> team-detail mode.** Zero-fill cells where the subject has 0 matches;
> each still carries its `league_share`. If you re-introduce the old
> "omit zero cells" optimisation, the client's per-slice `league_share`
> sum undercounts and the conditional deltas go wrong (a team with only
> 1 of 4 tied cells showed `All tied` at −35% instead of the correct
> −74%). Marginals are still built from the nonzero cells, so they're
> unaffected. Locked by `team_splits_mosaic.sh` Test 13 (asserts 12
> cells) + `test_team_splits.py`.

`All matches` carries the **volume** delta (match count vs a typical
team, from `/summary`'s matches envelope), not a share delta. Empty
slices (`All tied · 0`) and the whole scope (`All toss · 266` unfiltered)
drop the %/delta and read as a bare count.

This two-surface split **retired the old "confusing summary wording"
issue** (flagged 2026-05-26, fixed 2026-05-30): the header read "Of
**144** matches batting first:" while a W/T/L line below showed the
full-scope **266**-totalling counts, reading as a contradiction. There is
no longer any full-scope W/T/L line under a filtered header — the bar is
conditional and the corner is live. Don't reintroduce one. Tested by
`team_splits_mosaic.sh` Tests 12 + 13.

---

## Dimensionality is URL-derived

Three aux URL params drive the visual density. No internal state for expanded/collapsed — the URL IS the state. A share-link reproduces the exact view.

| URL params set | Layout |
|---|---|
| 0 | 2×2 (toss × inning) cells with W/T/L sub-rects per cell |
| 1 | 2×2 of the two free axes |
| 2 | 1D horizontal stacked bar of the one free axis |
| 3 | verbose colloquial status strip only — "Won toss · Batted first · Won the game — 3 matches" |

A share-link to a 0-free case reproduces the verbose strip; a share-link to a 3-free landing reproduces the full mosaic.

---

## `result` and `toss_outcome` aux filters require a subject team

Without `?team=`, the league-side query unpivots every match into 2 team-views — and "won" within that unpivot is tautologically 50% (every win has a loss). The `/teams/splits` endpoint returns **HTTP 400** when either aux is set without `?team=`, making the asymmetry observable instead of silently degenerate.

`aux.inning` works fine without `?team=` (each team-view independently batted first or second).

---

## Color is OUTCOME's permanent slot

The Mosaic uses `WISDEN_WL` (green/amber/red) for outcome encoding — full palette discipline in `colors.md`. New conditioning axes must be **spatial**, not color. The fixed axis ordering (toss → inning → result) is the codification of this guarantee.

---

## Shares + scope_total_n follow the FILTERED slice

When an aux narrowing is applied, the shares and the scope_total_n header must reflect the FILTERED slice so proportions sum to 1.0 within the narrowing. (Bug landed + fixed in commit 5f91ce2 — captured here so the next iteration doesn't re-introduce it.)

---

## Tells you might be about to break this

- You're tempted to add `result` / `toss_outcome` to FILTER_KEYS so they appear in the FilterBar UI. → DON'T. They're AuxParams (per `feedback_no_filterbar_explosion` discipline) and they have no canonical meaning on Series / Venues / Search pages where there's no team subject.
- You're tempted to compute "share" using the unfiltered total even after an aux narrowing is applied. → DON'T. See above — proportions must sum to 1.0 within the narrowing.
- You're adding an outcome dimension to a new chart and reaching for `WISDEN_WL`. → If the chart isn't the Mosaic, use magnitude tiers. `WISDEN_WL` is Mosaic-only.
- You're adding internal React state to remember the user's expanded/collapsed view. → DON'T. URL params are the state; `useUrlParam` + ABSENCE-encoded defaults.
