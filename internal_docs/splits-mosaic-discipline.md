# Splits Mosaic — discipline

The Splits Mosaic is a filter widget that LOOKS like a stat chart. It encodes the joint distribution of toss × inning × result for a subject team, with a fixed axis ordering that lets the reader read color as outcome and position as conditioning.

Specs: `spec-splits-mosaic.md` (Teams-only — implemented 2026-05-11), `splits-mosaic-cross-page.md` (cross-page reuse design).

This doc captures the **inviolable rules**. The spec captures the **design**.

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
