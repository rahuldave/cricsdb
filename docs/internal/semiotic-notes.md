# Semiotic v3 — notes for this codebase

`semiotic@3.2.3`. Read this **before writing or modifying any Semiotic
chart wrapper code**. Every assertion here is anchored to a file path
or a minified-bundle grep — do not paraphrase from memory.

---

## Rendering target — canvas, not SVG

Semiotic v3 HOCs (`BarChart`, `DonutChart`, `PieChart`, `Scatterplot`,
etc.) paint to a `<canvas>` element, NOT to SVG `<rect>` / `<path>`.

Empirical verification (Dismissals tab, `/batting?tab=Dismissals`,
2026-05-23):
- DOM scan: `document.querySelectorAll('path').length === 0` for every
  Semiotic chart on the page.
- The donut wedges and bar chart bars live inside `<canvas>` elements
  of the right size (350×350, 778×360).
- Axis labels, gridlines, legends are in sibling SVGs — only the data
  marks themselves are canvas.

**Implication:** any "make bars translucent" plumbing that targets
`svg rect[fill]` via CSS is a silent no-op. The previously shipped
`.wisden-bar-translucent svg rect[fill] { opacity: ... }` rule in
`index.css` did nothing — there are no SVG rects to fade. Likewise any
CSS-variable / class-toggle approach against the canvas element will
not work (canvas pixels ignore CSS `opacity` set on parent containers
ONLY if the canvas itself has opaque pixels — actually CSS opacity on
the canvas's parent DOES fade the canvas as a whole, but this fades
text/axes drawn alongside the marks too, which is rarely what we
want).

## Per-chart opacity defaults

| HOC | Built-in opacity prop | Default |
|---|---|---|
| `BarChart` | **none** | **1.0** (fully opaque) |
| `PieChart` | **none** | **1.0** |
| `DonutChart` | **none** | **1.0** |
| `Scatterplot` | `pointOpacity` | 0.8 |
| `BubbleChart` | `bubbleOpacity` | 0.6 |
| `AreaChart` | `areaOpacity` | 0.7 |
| `LineChart` (area fill) | `areaOpacity` | 0.3 |
| `FunnelChart` (connector) | `connectorOpacity` | 0.3 |
| `CirclePack` | `circleOpacity` | (see source) |
| `ChoroplethMap` | `areaOpacity` | 1.0 |
| `FlowMap` (edge) | `edgeOpacity` | 0.6 |

Source: `frontend/node_modules/semiotic/CLAUDE.md`. The notable absence
is `BarChart` / `PieChart` / `DonutChart` — they have **no** opacity
prop and paint at full intensity by default.

The pre-2026-05-23 inline comment in `frontend/src/components/charts/BarChart.tsx`
that said *"Semiotic stamps each bar `<rect>` with opacity='0.8' by
default"* was wrong on two counts: (1) bars aren't `<rect>` elements;
(2) the default opacity is 1.0, not 0.8.

## `pieceStyle` — the canvas-aware style hook

`StreamOrdinalFrame` (the engine behind `BarChart`, `DonutChart`,
`PieChart`) exposes:

```ts
// frontend/node_modules/semiotic/dist/components/stream/ordinalTypes.d.ts:166
pieceStyle?: (d: any, category?: string) => Style
```

where `Style` (from `stream/types.d.ts:59`) is:

```ts
interface Style {
  stroke?: string
  strokeWidth?: number
  strokeOpacity?: number
  fill?: string | CanvasPattern
  fillOpacity?: number
  opacity?: number
}
```

Pass via the HOC's `frameProps`:

```jsx
<BarChart
  ...
  frameProps={{ pieceStyle: (d, t) => ({ fill: '#7A1F1F', fillOpacity: 0.8 }) }}
/>
```

The returned `Style.fillOpacity` flows through Semiotic's canvas
painter (it sets the appropriate `ctx.globalAlpha` / fill-style alpha
internally before stroking each piece).

## CRITICAL: `pieceStyle` REPLACES, it does not merge

This is the trap. From `ordinal.module.min.js` (deminified):

```js
if (this.config.pieceStyle) {
  const n = this.config.pieceStyle(e, t);
  return n && !n.fill && t
    ? Object.assign({}, n, { fill: this.getColorFromScheme(t) })
    : n;
}
// no-pieceStyle branch (resolved color comes from barColors first):
return this.config.barColors && t
  ? { fill: this.config.barColors[t] || "#007bff" }
  : t ? { fill: this.getColorFromScheme(t) }
      : { fill: "#007bff" };
```

Read the two branches side-by-side:

- **No `pieceStyle`** → Semiotic consults `this.config.barColors[t]`
  first. `barColors` is the map Semiotic builds from the caller's
  `colorScheme` + `colorBy` props (where `WISDEN.oxblood` /
  `WISDEN_PHASES` live).
- **`pieceStyle` set as function returning no `fill`** → Semiotic
  merges in `getColorFromScheme(t)`. This is its internal categorical
  fallback (d3-`schemeCategory10`-style). **`barColors` is bypassed.**

So a `pieceStyle: () => ({ fillOpacity: 0.8 })` callback erases the
caller's `colorScheme` resolution and gives every bar a different
color from Semiotic's default categorical palette. On the all-oxblood
"Dismissals by Over" chart this turned the bars rainbow when shipped
2026-05-23 (reverted same session).

## Correct shape for "opacity only" via `pieceStyle`

Because of the replace-not-merge behaviour, callers must also supply
`fill`. For single-color schemes that's trivial:

```jsx
// colorScheme={[WISDEN.oxblood]} — all bars oxblood
frameProps={{
  pieceStyle: () => ({ fill: WISDEN.oxblood, fillOpacity: 0.8 }),
}}
```

For `colorBy`-driven schemes (`colorBy="phase" colorScheme={WISDEN_PHASES}`),
you have to mirror Semiotic's `scaleOrdinal(unique colorBy values →
colorScheme[i] in encounter order)` mapping yourself — `barColors` is
not reachable from a consumer-supplied callback. This is **not** a
one-line fix at the wrapper level.

## Other styling hooks (for reference)

Also on `StreamOrdinalFrame` (`stream/ordinalTypes.d.ts`):

- `connectorStyle?: Style | ((d) => Style)` — for funnel / swimlane connectors
- `summaryStyle?: (d, category?) => Style` — for boxplot / violin summary marks

Each of them follows the same "function replaces, object merges" rule
unless documented otherwise. **Verify on the specific HOC before
relying.**

## Lookup workflow (mandatory)

Before writing or modifying any Semiotic-touching code:

1. Open `frontend/node_modules/semiotic/CLAUDE.md` — list of HOCs +
   their documented props + defaults.
2. Open the HOC's `.d.ts` under
   `frontend/node_modules/semiotic/dist/components/charts/<bucket>/<Hoc>.d.ts`
   — actual TypeScript prop interface.
3. For deeper hooks (`pieceStyle`, `summaryStyle`, frame internals),
   `frontend/node_modules/semiotic/dist/components/stream/ordinalTypes.d.ts`
   + `stream/types.d.ts`.
4. For runtime behavior (what semiotic actually DOES with a prop), grep
   the minified bundle:
   `grep -ao '.\{0,40\}<propName>[^,;}]\{0,400\}' frontend/node_modules/semiotic/dist/ordinal.module.min.js`

This file is the answer to "where do I look first." Update it when
new gotchas surface.
