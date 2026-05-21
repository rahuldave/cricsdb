/**
 * Single "vs cohort" label that sits at the start of a ProbChip row.
 *
 * After PT5.F follow-up (2026-05-21): each ProbChip caption renders
 * just "N% ↑+Δ%" without repeating "vs cohort" on every chip; this
 * component supplies the row-level prefix once. Vertically centered
 * to the chip pills via baseline alignment.
 *
 * Place inline as the first child of the chip-row flex container,
 * immediately before the first <ProbChip>. The whole chip row remains
 * flex-wrap so the prefix wraps with the chips on narrow viewports.
 *
 * Spec: internal_docs/spec-prob-baselines.md §5 Option C.
 */
export default function CohortRowPrefix() {
  return (
    <span
      style={{
        fontFamily: 'var(--serif)',
        fontStyle: 'italic',
        fontSize: '0.7rem',
        color: 'var(--ink-faint)',
        // Align with the caption row (bottom of each chip's flex-column),
        // NOT centered between pill + caption. Each ProbChip is a flex-
        // column (pill on top, caption below) so the row's baseline is
        // ambiguous; alignSelf: 'flex-end' pins this prefix to the
        // caption baseline.
        alignSelf: 'flex-end',
        whiteSpace: 'nowrap',
        marginRight: '0.1rem',
        // Bottom-pad to match the caption's top-margin so it sits at
        // exactly the caption's visual y.
        paddingBottom: '0',
      }}
    >
      vs cohort
    </span>
  )
}
