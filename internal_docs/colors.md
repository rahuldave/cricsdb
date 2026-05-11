# Color discipline

Three palette systems live in `frontend/src/components/charts/palette.ts`. They are intentionally distinct — color is the page's vocabulary, and blurring vocabularies makes the reader's eye reset.

| System | Encodes | Where |
|---|---|---|
| **Magnitude tiers** (indigo / sage / ochre) | metric value (low / typical / high) | histograms, sparklines, ProbChips on Distribution panels |
| **Outcome traffic light** (`WISDEN_WL`: green / amber / red) | won / tied / lost | **Splits Mosaic only** |
| **Accent strokes** (oxblood, forest) | rolling-mean overlay + league reference | sparkline reference lines |

Reds are reserved across the whole codebase: oxblood for rolling-mean strokes, `WISDEN_WL.lost` for Mosaic cells. Nowhere else.

---

## Magnitude tiers (indigo / sage / ochre)

The shared 3-tier palette across histograms, sparklines, AND probability chips on every distribution panel. Never let chip colors drift from the histogram tier color of the same threshold — that "the chip is green but the bar at this value is gray" inconsistency is what the user flagged twice on 2026-05-06.

| Tier | Color | Reads |
|---|---|---|
| **INDIGO** | `#7090A8` | poor outcome for the player |
| **SAGE**   | `#7A8E6A` | typical |
| **OCHRE**  | `WISDEN.ochre` | really good ("hot") |

### Polarity convention

Color is tied to OUTCOME for the player, not bin index:
- Higher-is-better metrics (runs, wickets, SR): low→indigo, mid→sage, high→ochre.
- Lower-is-better metrics (economy, runs conceded): low→ochre, mid→sage, high→indigo (polarity flipped — low econ is good).

### Chip-tint helper

`WISDEN_TIER_TINTS` exports `{indigo, sage, ochre}` → `{bg: rgba, fg: hex}` pairs. The `ProbChip` component takes a `tint` prop directly (not a `polarity`); each chip caller picks the tier its threshold falls in. So `<ProbChip tint={T_OCHRE} ...>` for `P(≥3)` on the wickets tab matches the strike-tier histogram bar at value 3.

### Reds are NOT in this palette

The "failure"/"wicketless" tier was flipped from muted red to muted indigo on 2026-05-06 so red exclusively signals the rolling overlay. Do not re-introduce a red tier.

Spec: `spec-distribution-stats.md` §10.3 + §12.2.6.

---

## Outcome traffic light (WISDEN_WL) — Splits Mosaic only

```ts
export const WISDEN_WL = {
  won:   '#4B7A3B',  // muted green
  tied:  '#C9A636',  // muted amber
  lost:  '#B85450',  // brick red
}
```

**Reserved for outcome encoding in the Splits Mosaic ONLY.** The palette is intentionally chosen to NOT collide with anything else:
- Green here (`#4B7A3B`) is brighter than the forest reference line (`#3F7A4D`) so it reads as a fill at cell scale.
- Red here (`#B85450`) is distinct from oxblood (`#7A1F1F`) so a W/L cell and a rolling-mean overlay never visually collide.

### Tells you might be about to break this

- You're adding red as a fill anywhere else — STOP. Reds are oxblood (overlay strokes) and `WISDEN_WL.lost` (Mosaic cells). Nowhere else.
- You're adding a new Mosaic conditioning axis encoded by color instead of spatially — STOP. Color is OUTCOME's permanent slot; new axes must be spatial. The Splits Mosaic's fixed axis ordering (toss → inning → result) encodes this guarantee.
- You're tinting metric tiers with green/red — STOP. Magnitude tiers stay indigo/sage/ochre.

Spec: `spec-splits-mosaic.md` §2.2, §3.5. Discipline doc: `splits-mosaic-discipline.md`.

---

## Reference lines on distribution sparklines

The team distribution sparklines render up to four reference lines, three carrying distinct semantic meaning. Naming + color is fixed:

| Line | Color | Reads | Source |
|---|---|---|---|
| **Scope average** | black `#1A1714` 2px | THIS subject's mean over its actual innings in the active scope (1st + 2nd combined unless `?inning=` filter) | `lifetime.X.mean_per_innings` from distribution endpoint |
| **League avg** | forest `#3F7A4D` 1.5px | EVERY team's mean over its innings in the active scope (same-scope league baseline) | `summary.X.scope_avg` from `/summary` envelope — already fetched by parent tab; no new HTTP roundtrip |
| **Gender-global** | gray `#8A7D70` 1.5px | EVERY team's mean across ALL T20 cricket at gender grain (whole-number anchor; ignores other filters) | hard-coded constants in `globalBaselines.ts` (refresh yearly) |
| **Rolling-10 mean** | oxblood `#7A1F1F` 1.2px | 10-innings rolling-mean overlay on the Scope window only when n_innings ≥ 10 | derived from `observations[]` |

### Wiring discipline

When adding a new metric tab to a team panel, plumb the per-metric `scope_avg` from the parent's summary fetch into the panel's `leagueAvg` prop. Don't add a backend field for it on the distribution endpoint — the duplication forces a regression-suite churn AND mismatches the existing `MetricDelta withScopeAvg` plumbing pattern that all the StatCard subtitles use.

---

## Sparkline visual contract

Codified in `frontend/src/components/distribution/DistributionSparkline.tsx`:

- Bar opacity 0.8 (blue/indigo tier overrides to 1.0 — washes out worst at 0.8); per-bar `opacity` field on `SparklinePoint`.
- Reference lines per the table above (black + forest + gray + oxblood).
- Below-baseline 4px stub zone — every bar (including value=0) has a clickable footprint; the user-flagged "missing matches" bug was zero-height bars vanishing.
- Mobile (< 720px): bar `<a>`s get `pointer-events: none` — sparkline is impressionistic only; navigation via the season-tick axis context + the page's existing By Innings tab.

---

## Legend swatch alignment

When rendering a `<swatch> + <label>` pair inside a row that uses `align-items: baseline` (every distribution panel's sparkline caption row), do NOT wrap the pair in `<span style="display: inline-flex; align-items: center">`. The inline-flex baseline resolves to bottom-of-swatch (the inline-block child), which sits ABOVE the surrounding text baselines and pushes the label visibly lower than the leading caption on the same row.

Pattern (from commit b770918, applied to all 5 distribution panels 2026-05-08):

```jsx
<span>
  <span aria-hidden="true" style={{
    display: 'inline-block', width: 14, height: 1.5,
    background: COLOR,
    verticalAlign: 'middle',
    marginRight: '0.3rem',
    position: 'relative', top: '-0.1em',  // optical-centre nudge
  }} />
  label text
</span>
```

The `top: -0.1em` nudge sits the swatch at the optical centre of the text x-height (which differs from the geometric centre when the font has descenders).
