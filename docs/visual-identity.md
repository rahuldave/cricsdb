# Visual identity — Wisden editorial

The frontend uses a "Wisden almanack" editorial identity: cream page,
warm dark brown ink, oxblood as the only accent, serif display type
(Fraunces) for hierarchy and a humanist sans (Inter Tight) for body
and tabular numerals. No card chrome — hierarchy comes from rules,
whitespace, and typography.

This doc is the source of truth for **what's a token, where it's
defined, and what each color is for**. If you ever want to retune
the palette, the only files that need to change are the two
listed in [Token sources](#token-sources). Every consumer references
named tokens — there are no free-floating hex values anywhere else
in the codebase.

## Token sources

Two files, and only these two, contain raw color literals:

1. **`frontend/src/index.css`** — `:root` block at the top defines
   the page-level CSS variables (background, ink, rule, accent,
   highlight, tints).
2. **`frontend/src/components/charts/palette.ts`** — TypeScript
   constants for chart fills and the `DELIVERY` semantic ramp used
   by the per-delivery innings grid.

Anywhere else in the code (components, pages, inline styles)
references named tokens via `var(--name)` or imports from
`palette.ts`. A grep for `#[0-9a-fA-F]{3,6}` outside these two
files should return nothing.

## Page palette (`index.css` `:root`)

### Background and ink
| Token            | Value     | What it's for |
|------------------|-----------|---------------|
| `--bg`           | `#FAF7F0` | Cream page background. Set on `html, body` so every page edge-to-edge. |
| `--bg-soft`      | `#F2EDE0` | Faintly darker cream for hover, zebra rows, "no data" placeholder cells. |
| `--ink`          | `#2E2823` | Warm dark brown — primary text, page titles, stat values. Softer than near-black so it doesn't feel harsh on cream. |
| `--ink-soft`     | `#5C5048` | Body grey — secondary text, table cell content. |
| `--ink-faint`    | `#8A7D70` | Labels, metadata, italic captions, axis tick text. |

### Rules
| Token            | Value     | What it's for |
|------------------|-----------|---------------|
| `--rule`         | `#1A1714` | Primary rule — section dividers, masthead double-rule, statrow bottom border. |
| `--rule-soft`    | `#E0D8CC` | Hairline rule — between table rows, between fixture list items, soft cell borders. |

### Accent (oxblood)
| Token            | Value     | What it's for |
|------------------|-----------|---------------|
| `--accent`       | `#7A1F1F` | Oxblood — the only saturated brand color. Used for: active nav link underline, active filter, the `&` in the brand wordmark, the `v` in "Team1 v Team2", wicket markers, dismissal bars, link hover, the oxblood inset rule on highlighted scorecard rows. |
| `--accent-soft`  | `#A84545` | Lighter oxblood — used sparingly (currently the partnership-summary border accent in the innings grid). |

### State tints
Used for "scrolled-into-view" highlights and matchup-grid heatmap.
All derived from cream/oxblood/ochre family so they harmonize.

| Token              | Value     | What it's for |
|--------------------|-----------|---------------|
| `--highlight`      | `#F4E9C9` | The row/cell that the URL hash is pointing at (e.g. clicked from an innings list link). Used in `wisden-table`, `wisden-innings`, and `MatchupGridChart`. |
| `--highlight-hover`| `#EFE0B0` | Hover state on a highlighted row. |
| `--tint-wicket`    | `#E8C8C8` | Oxblood-tinted matchup-grid cell where the bowler took the batter's wicket. |
| `--tint-strong`    | `#E8D4A8` | Strong ochre for high SR (≥ 200). |
| `--tint-soft`      | `#F0E2BE` | Light ochre for medium SR (≥ 150). |

## Chart palette (`palette.ts`)

Defined as the `WISDEN` constant, with derived arrays for common
combinations. All chosen to harmonize with cream — no Tailwind
primaries.

### Core categorical colors
| Key       | Value     | What it's for |
|-----------|-----------|---------------|
| `ink`     | `#1A1714` | (Slightly darker than the page `--ink` — used for chart accents, not body text.) |
| `oxblood` | `#7A1F1F` | Wickets, dismissals, anything semantically wicket-related. |
| `indigo`  | `#2E6FB5` | Default primary. Single-series bar/line/scatter charts pick this up automatically. |
| `ochre`   | `#C9871F` | Warm gold, distinct from oxblood. |
| `forest`  | `#3F7A4D` | Mid green, distinct from indigo. |
| `slate`   | `#3C5B7A` | Reserved (currently unused as a primary). |
| `faint`   | `#8A7D70` | Same as page `--ink-faint`, available to chart code. |

### Derived arrays
- **`WISDEN_PALETTE`** = `[indigo, oxblood, ochre, forest, ink]` — default 5-color categorical scale used by `BarChart`, `LineChart`, `ScatterChart`, `DonutChart` when no `colorScheme` is passed.
- **`WISDEN_PHASES`** = `[indigo, ochre, oxblood]` — powerplay / middle / death over breakdowns.
- **`WISDEN_PAIR`** = `[indigo, ochre]` — high-contrast two-team palette for the Worm chart and Manhattan chart. Avoids oxblood so it doesn't clash with the oxblood wicket markers on the worm.

## Delivery palette (`palette.ts` `DELIVERY`)

Used exclusively by `InningsGridChart` to encode every delivery's
outcome in the per-ball grid. Each category has its own hue family
so a viewer can scan thousands of cells and read the rhythm of an
innings at a glance.

### Off-bat runs ramp (forest green family)
| Key   | Value     | Meaning |
|-------|-----------|---------|
| `run0`| `#F2EDE0` | Dot ball — fades into the cream page so dots recede. |
| `run1`| `#E1E6D2` | 1 run |
| `run2`| `#C2D1AF` | 2 runs |
| `run3`| `#9DBA82` | 3 runs |
| `run4`| `#7AA063` | 4 runs (boundary) |
| `run5`| `#557A40` | 5 runs (rare) |
| `run6`| `#3A5926` | 6 runs (six) |

The ramp is muted compared to bright Tailwind greens so it
harmonizes with cream, but the boundary cells (4, 6) still pop
against the dots and singles.

### Extras
| Key      | Value     | Meaning |
|----------|-----------|---------|
| `wide`   | `#E8D4A8` | Wide — pale ochre. |
| `noball` | `#D9B870` | No-ball — stronger ochre. |
| `bye`    | `#B8C7D5` | Bye — pale slate. |
| `legbye` | `#8FA5BC` | Leg-bye — medium slate. |

Ochre = "off the bat-ish extras" (wides, no-balls).
Slate = "off the body extras" (byes, leg-byes).

### Wickets
`wicket` = oxblood (`WISDEN.oxblood`) — always. Stays brand-consistent
with wicket markers everywhere else (worm chart, dismissal bars,
matchup grid wicket tint).

### At-crease stripes
| Key         | Value     | Meaning |
|-------------|-----------|---------|
| `atCreaseA` | `#D9C5A0` | Warm tan / aged buff — partnership slot A. |
| `atCreaseB` | `#B8C5C2` | Antique sage / blue-grey — partnership slot B. |

Both faint cream tints. They recede behind the saturated semantic
colors but are clearly distinct from each other. When a batter gets
out, the new batter inherits the slot (and shade) of the partner
they replaced — see `assignBatterSlots` in `InningsGridChart.tsx`.

## Typography

| Token   | Family                              | Use |
|---------|-------------------------------------|-----|
| `--serif` | Fraunces (variable, opsz axis)    | Display, page titles, stat values, chart titles, italic labels, dismissal text in innings cards, "v" connectives. |
| `--sans`  | Inter Tight                       | Body, nav links, filter labels, axis tick numbers, table cell numerics. |

Optical sizing: Fraunces uses `font-variation-settings: "opsz" N`
where N is the size class — 14 for body, 24 for medium headings,
36 for stat values, 60 for page titles, 144 for the home masthead.

Tabular numerals globally on `.num`, `<table> td/th`, and chart
axis text via the `font-variant-numeric: tabular-nums` rule.

## Consistency rule for page titles

> **Subject in ink. Connective in oxblood.**

Where:
- **Subject** = the main noun on the page (player name, team name,
  match teams, the brand wordmark `T20 CricsDB`).
- **Connective** = the small word that joins them (`v` between
  teams, `&` in the wordmark).

Applied at:
- Brand wordmark in nav (`.wisden-wordmark` + `.wisden-amp`)
- Home masthead (`.title` + `.title-amp`)
- Match scorecard header (`.wisden-match-header h2` + `.vs`)
- HeadToHead title (inline `<span style>` for the `v`)
- Player / team page titles (`.wisden-page-title`) — single noun, no connective

NOT applied to body lists like the Matches table rows or H2H
match-by-match — those stay ink so a 50-row table doesn't become
a wall of red. **The rule is for page-identity elements only.**

Hover state on inline links → oxblood. That's the live accent for
*interactive* elements, separate from the static identity rule.

## Where to look in the code

| What | Where |
|------|-------|
| Page tokens | `frontend/src/index.css` `:root` |
| Chart palette | `frontend/src/components/charts/palette.ts` |
| Page primitives (`.wisden-page-title`, `.wisden-statrow`, `.wisden-tabs`, etc.) | `frontend/src/index.css` |
| Semiotic SVG overrides (axis labels, tick text, gridlines) | `frontend/src/index.css` (`.axis text`, `.frame-title`, etc.) |
| Innings grid color helpers | `frontend/src/components/charts/InningsGridChart.tsx` (top of file aliases the `DELIVERY` tokens) |
