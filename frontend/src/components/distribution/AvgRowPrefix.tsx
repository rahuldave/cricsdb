/**
 * Single "vs avg" label that sits at the start of a team ProbChip row.
 *
 * Team-side sibling of CohortRowPrefix. Different comparison axis:
 *   - cohort = matched-peer position/over-mix (player chips)
 *   - avg    = scope-filtered league average (team chips)
 *
 * Per spec-prob-baselines-teams.md §6 + §11.2: two purpose-specific
 * components rather than one labelled-by-prop component, so each row
 * prefix stays tied to one comparison concept. Styling intentionally
 * duplicated from CohortRowPrefix so the two stay visually paired.
 */
export default function AvgRowPrefix() {
  return (
    <span
      style={{
        fontFamily: 'var(--serif)',
        fontStyle: 'italic',
        fontSize: '0.7rem',
        color: 'var(--ink-faint)',
        alignSelf: 'flex-end',
        whiteSpace: 'nowrap',
        marginRight: '0.1rem',
        paddingBottom: '0',
      }}
    >
      vs avg
    </span>
  )
}
