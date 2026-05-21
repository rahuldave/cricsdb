/**
 * Small italic header above the ProbChip row signalling that the
 * chip VALUES are sliced by a `dist_window` (last 10 / last 60d /
 * last 6mo / last 1y), NOT by scope. Renders nothing when window
 * is the default 'scope'.
 *
 * The cohort baseline on each chip remains at the FilterParams
 * scope (the per-window cohort is deferred); this badge tells the
 * reader that what they're seeing is "player @ window" vs
 * "cohort @ scope" so they read the green/red deltas correctly.
 *
 * Place immediately above the chip row, BEFORE the row's leading
 * "vs cohort" prefix.
 */

export type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'

const WINDOW_LABELS: Record<DistWindow, string> = {
  scope: '',
  last_10:  'last 10 innings',
  last_60d: 'last 60 days',
  last_6mo: 'last 6 months',
  last_1yr: 'last year',
}

export default function WindowBadge({ window }: { window: DistWindow }) {
  if (window === 'scope') return null
  return (
    <div style={{
      fontFamily: 'var(--serif)',
      fontStyle: 'italic',
      fontSize: '0.78rem',
      color: 'var(--ink-faint)',
      marginTop: '0.6rem',
      marginBottom: '-0.2rem',
    }}>
      <span style={{
        fontVariant: 'all-small-caps',
        letterSpacing: '0.08em',
        fontWeight: 700,
        fontStyle: 'normal',
        color: 'var(--accent)',
        marginRight: '0.4rem',
      }}>window</span>
      {WINDOW_LABELS[window]}{' '}
      <span style={{ color: 'var(--ink-faint)' }}>
        — values below are this slice; the vs-cohort comparison stays at scope
      </span>
    </div>
  )
}
