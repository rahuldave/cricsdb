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
 * Run-tier coloring for the per-innings runs histogram (batter
 * Distribution panel, spec-distribution-stats.md §9.2.2).
 *
 * Tiers (revised 2026-05-06 — failure flipped from red→indigo
 * because red is reserved for the rolling-mean overlay):
 *  - failure   : 0–9 runs    (muted indigo — got out cheap)
 *  - building  : 10–49 runs  (faint slate — "got going")
 *  - fifty     : 50–99 runs  (sage green — match-shaping innings)
 *  - century   : 100–149     (ochre gold — match-winning)
 *  - rare      : 150+        (deeper gold — exceptional)
 *
 * Keys MUST match the strings emitted by `binTier()` in
 * components/batting/distributionBins.ts.
 */
export const WISDEN_RUN_TIERS: Record<
  'failure' | 'building' | 'fifty' | 'century' | 'rare',
  string
> = {
  failure:  '#7090A8',  // muted indigo (was muted oxblood — red reserved for oxbow)
  building: '#A8A091',  // faint slate-tan
  fifty:    '#7A8E6A',  // sage green
  century:  WISDEN.ochre,
  rare:     '#9C6B17',  // deeper gold
}

/**
 * Lower-is-better tier coloring used by the bowler economy + runs-
 * conceded sparklines. Same five colors as the wicket-tier ladder,
 * but mapped with REVERSED polarity — sage (good) at the low end,
 * deeper gold (bad) at the high end. Spec §12.2.6.
 */
export const WISDEN_LOWER_IS_BETTER_TIERS: Record<
  'tight' | 'decent' | 'neutral' | 'expensive' | 'leaked',
  string
> = {
  tight:     '#7A8E6A',  // sage — good
  decent:    '#A8A091',  // faint slate-tan
  neutral:   '#3C5B7A',  // default slate
  expensive: WISDEN.ochre,
  leaked:    '#9C6B17',  // deeper gold — bad
}

/**
 * Wicket-tier coloring for the bowler distribution histogram (spec
 * §12.2.2). Discrete bars at integer wickets 0..6+; tiers ladder
 * up the rarity spectrum.
 *
 * Tiers:
 *  - wicketless : 0   (muted slate — empty spell)
 *  - building   : 1-2 (faint slate — modest impact)
 *  - threefer   : 3   (sage green — "got going")
 *  - fourfer    : 4   (ochre — match-shaping)
 *  - fivefer    : 5+  (deeper gold — career-marker)
 */
export const WISDEN_WICKET_TIERS: Record<
  'wicketless' | 'building' | 'threefer' | 'fourfer' | 'fivefer',
  string
> = {
  wicketless: '#A8A091',  // faint slate-tan, distinct from active bars
  building:   '#7090A8',  // muted indigo (1-2 wickets — modest)
  threefer:   '#7A8E6A',  // sage — "got going"
  fourfer:    WISDEN.ochre,
  fivefer:    '#9C6B17',  // deeper gold
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
