/**
 * Wisden chart palette — colors that read well on the cream
 * (#FAF7F0) page background and harmonize with the editorial type.
 *
 * Use INK as the default single-series color so a one-off bar chart
 * looks like part of the page rather than a standalone widget. Use
 * OXBLOOD for anything wicket-related so wickets always pop in the
 * brand color. SLATE and OCHRE round out a 4-color categorical scale.
 */
export const WISDEN = {
  ink:     '#1A1714',
  oxblood: '#7A1F1F',
  indigo:  '#2E6FB5',  // bright primary, the new default fill
  ochre:   '#C9871F',  // warm gold, distinct from oxblood
  forest:  '#3F7A4D',  // mid green, distinct from indigo
  slate:   '#3C5B7A',
  faint:   '#8A7D70',
} as const

/** Default categorical scale — indigo first so single-series charts pop. */
export const WISDEN_PALETTE: string[] = [
  WISDEN.indigo, WISDEN.oxblood, WISDEN.ochre, WISDEN.forest, WISDEN.ink,
]

/** Phase trio for powerplay / middle / death over breakdowns. */
export const WISDEN_PHASES: string[] = [WISDEN.indigo, WISDEN.ochre, WISDEN.oxblood]

/**
 * Three-tier coloring SHARED across distribution histograms,
 * sparklines, AND probability chips. Spec:
 * internal_docs/spec-distribution-stats.md §10.3 (revised
 * 2026-05-06 — unified palette per user feedback that the chip
 * polarity scheme didn't match the histogram tier scheme).
 *
 * The 3-tier palette uses semantically-mapped colors:
 *   - INDIGO (#7090A8): poor outcome for the player
 *   - SAGE   (#7A8E6A): regular / typical
 *   - OCHRE  (#C9871F): really good — "hot"
 *
 * Polarity convention — colors are tied to OUTCOME for the player,
 * not to bin index. So the same color means "good for player" on
 * every tab, regardless of whether high-or-low values are good:
 *   higher-is-better (runs / wickets / SR):
 *     low value (poor)    → INDIGO
 *     mid value (typical) → SAGE
 *     high value (good)   → OCHRE
 *   lower-is-better (economy / runs conceded):
 *     low value (good)    → OCHRE
 *     mid value (typical) → SAGE
 *     high value (poor)   → INDIGO
 *
 * Reds are reserved for the rolling-mean overlay (oxbow) — not
 * used in tier coloring.
 */

export const WISDEN_RUN_TIERS: Record<
  'failure' | 'building' | 'impact', string
> = {
  failure:  '#7090A8',  // indigo — got out cheap (0-9)
  building: '#7A8E6A',  // sage — typical (10-49)
  impact:   WISDEN.ochre,  // ochre — match-shaping (50+) ★
}

export const WISDEN_WICKET_TIERS: Record<
  'wicketless' | 'building' | 'strike', string
> = {
  wicketless: '#7090A8',  // indigo — no impact (0)
  building:   '#7A8E6A',  // sage — modest impact (1-2)
  strike:     WISDEN.ochre,  // ochre — strong spell (3+, cricket-iconic) ★
}

export const WISDEN_SR_TIERS: Record<
  'slow' | 'mid' | 'explosive', string
> = {
  slow:      '#7090A8',  // indigo — anchor / sub-100
  mid:       '#7A8E6A',  // sage — typical T20 SR
  explosive: WISDEN.ochre,  // ochre — 150+ aggressor ★
}

export const WISDEN_LOWER_TIERS: Record<
  'tight' | 'mid' | 'loose', string
> = {
  tight: WISDEN.ochre,  // ochre — good (low econ / few runs conceded) ★
  mid:   '#7A8E6A',     // sage — typical
  loose: '#7090A8',     // indigo — poor outcome (high econ / many runs)
}

/**
 * Chip-tint pairs (background fill + foreground text color) for
 * each of the three semantic tiers. Used by ProbChip — each chip
 * caller picks the tier its threshold falls in and looks up the
 * matching tint. This is what makes the chip color match the
 * histogram + sparkline bar at the same outcome.
 */
export const WISDEN_TIER_TINTS: Record<
  'indigo' | 'sage' | 'ochre',
  { bg: string; fg: string }
> = {
  indigo: { bg: 'rgba(112, 144, 168, 0.18)', fg: '#3F5A78' },
  sage:   { bg: 'rgba(122, 142, 106, 0.18)', fg: '#3F5A2F' },
  ochre:  { bg: 'rgba(201, 135, 31, 0.18)',  fg: '#6B4710' },
}

/** Map a tier color (from any of the WISDEN_*_TIERS palettes) to
 *  its chip-tint pair. */
export function tintForTierColor(color: string): { bg: string; fg: string } {
  if (color === '#7090A8') return WISDEN_TIER_TINTS.indigo
  if (color === '#7A8E6A') return WISDEN_TIER_TINTS.sage
  if (color === WISDEN.ochre || color === '#C9871F') return WISDEN_TIER_TINTS.ochre
  // Fallback: faint slate (was the old neutral chip styling)
  return { bg: 'rgba(60, 91, 122, 0.10)', fg: '#3C5B7A' }
}

/**
 * High-contrast pair for two-innings charts (Worm, Manhattan) where the
 * default categorical palette runs ink+slate, which read too similarly
 * on cream. Pure ink against a saturated indigo gives a clear value
 * AND hue difference. Avoids oxblood so it doesn't clash with the
 * oxblood wicket markers on the worm.
 */
export const WISDEN_PAIR: string[] = [WISDEN.indigo, WISDEN.ochre]

/**
 * Semantic delivery palette for the per-ball innings grid. Each
 * category has its own hue family so a viewer can scan a wall of
 * cells and read the rhythm of the innings at a glance.
 *
 * Hue families:
 *   - Off-bat runs: forest green ramp (low → high saturation)
 *   - Wides / no-balls: ochre (extras off the bat)
 *   - Byes / leg-byes: slate (extras off the body / pad)
 *   - Wickets: oxblood (the brand wicket color)
 *   - At-crease stripes: faint cream tints, one slate-leaning, one ochre-leaning
 *
 * All harmonized with the cream page background — no Tailwind primaries.
 */
export const DELIVERY = {
  // Off-bat runs ramp. Index = runs scored.
  // The 0 cell is the cream-soft so dots fade into the page.
  // Muted compared to bright Tailwind greens; the gap between 4 and
  // 6 was widened (4 is a soft sage, 6 is a deeper sage with more
  // saturation) so the boundary cells stay distinguishable on cream.
  run0: '#F2EDE0',
  run1: '#E1E6D2',
  run2: '#C2D1AF',
  run3: '#9DBA82',
  run4: '#7AA063',
  run5: '#557A40',
  run6: '#3A5926',

  // Extras — ochre family (off-bat) and slate family (off-pad).
  wide:    '#E8D4A8',  // pale ochre
  noball:  '#D9B870',  // stronger ochre
  bye:     '#B8C7D5',  // pale slate
  legbye:  '#8FA5BC',  // medium slate

  // Wicket — always oxblood.
  wicket:  WISDEN.oxblood,

  // At-crease alternating stripes. Aged-manuscript pair — warm tan
  // and antique sage. Distinct enough to read at a glance, muted
  // enough to recede behind the saturated run/extras/wicket cells.
  atCreaseA: '#D9C5A0',  // warm tan / aged buff
  atCreaseB: '#B8C5C2',  // antique sage / blue-grey
} as const

/** Off-bat run color by runs scored. */
export const deliveryRunColor = (runs: number): string => {
  switch (runs) {
    case 0: return DELIVERY.run0
    case 1: return DELIVERY.run1
    case 2: return DELIVERY.run2
    case 3: return DELIVERY.run3
    case 4: return DELIVERY.run4
    case 5: return DELIVERY.run5
    default: return DELIVERY.run6  // 6+
  }
}
