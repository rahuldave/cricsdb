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
 * Three-tier coloring for distribution histograms + sparklines.
 * Spec: internal_docs/spec-distribution-stats.md §10.3 (revised
 * 2026-05-06 — collapsed from 5-tier to 3-tier to reduce
 * sparkline visual noise; the bin label still conveys the
 * exact range, the color tells you which tier).
 *
 * Polarity convention:
 *   higher-is-better (runs / wickets / SR): low = indigo (poor),
 *     mid = faint slate-tan (typical), high = sage or gold (strong)
 *   lower-is-better (economy / runs conceded): low = sage (tight),
 *     mid = faint slate-tan, high = ochre (loose / leaked)
 *
 * Reds are reserved for the rolling-mean overlay (oxbow) — not
 * used in tier coloring.
 */

export const WISDEN_RUN_TIERS: Record<
  'failure' | 'building' | 'impact', string
> = {
  failure:  '#7090A8',  // muted indigo — got out cheap (0-9)
  building: '#A8A091',  // faint slate-tan — typical (10-49)
  impact:   '#7A8E6A',  // sage green — match-shaping (50+)
}

export const WISDEN_WICKET_TIERS: Record<
  'wicketless' | 'building' | 'strike', string
> = {
  wicketless: '#7090A8',  // muted indigo — no impact (0)
  building:   '#A8A091',  // faint slate-tan — modest (1-2)
  strike:     '#9C6B17',  // deeper gold — strong spell (3+, cricket-iconic)
}

export const WISDEN_SR_TIERS: Record<
  'slow' | 'mid' | 'explosive', string
> = {
  slow:      '#7090A8',  // muted indigo — anchor / sub-100
  mid:       '#A8A091',  // typical T20 strike rate
  explosive: '#7A8E6A',  // sage — 150+ aggressor
}

export const WISDEN_LOWER_TIERS: Record<
  'tight' | 'mid' | 'loose', string
> = {
  tight: '#7A8E6A',  // sage — good
  mid:   '#A8A091',  // typical
  loose: WISDEN.ochre,  // ochre — bad
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
