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
  slate:   '#3C5B7A',
  ochre:   '#A87935',
  forest:  '#3F5E3D',
  faint:   '#8A7D70',
} as const

/** Default 4-color categorical scale. */
export const WISDEN_PALETTE: string[] = [
  WISDEN.ink, WISDEN.oxblood, WISDEN.slate, WISDEN.ochre, WISDEN.forest,
]

/** Phase trio for powerplay / middle / death over breakdowns. */
export const WISDEN_PHASES: string[] = [WISDEN.slate, WISDEN.ochre, WISDEN.oxblood]

/**
 * High-contrast pair for two-innings charts (Worm, Manhattan) where the
 * default categorical palette runs ink+slate, which read too similarly
 * on cream. Pure ink against a saturated indigo gives a clear value
 * AND hue difference. Avoids oxblood so it doesn't clash with the
 * oxblood wicket markers on the worm.
 */
export const WISDEN_PAIR: string[] = ['#1A1714', '#1E5A8A']
