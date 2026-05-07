/**
 * Suggested-splits navigation row for the fielder Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §14.2.7.
 *
 * Sibling of components/bowling/BowlerSuggestedSplitsRow. Navigates to
 * the SAME /fielding page with the same player but the split's scope
 * params applied. Inning aux + page-local URL state (`dist_metric_f`,
 * `dist_window_f`) are preserved so the user lands in the same view
 * mode under the broader scope.
 */

import { Link, useSearchParams } from 'react-router-dom'
import type { SuggestedSplit } from '../../types'

interface Props {
  playerId: string
  splits: SuggestedSplit[]
}

const PRESERVED_KEYS = ['inning', 'dist_metric_f', 'dist_window_f']

export default function FielderSuggestedSplitsRow({ playerId, splits }: Props) {
  const [searchParams] = useSearchParams()
  if (splits.length === 0) return null

  function buildHref(split: SuggestedSplit): string {
    const sp = new URLSearchParams()
    sp.set('player', playerId)
    for (const [k, v] of Object.entries(split.params)) sp.set(k, v)
    for (const key of PRESERVED_KEYS) {
      const v = searchParams.get(key)
      if (v !== null) sp.set(key, v)
    }
    return `/fielding?${sp.toString()}`
  }

  return (
    <div style={{
      fontFamily: 'var(--serif)',
      fontStyle: 'italic',
      fontSize: '0.82rem',
      color: 'var(--ink-faint)',
      marginTop: '0.5rem',
      display: 'flex', flexWrap: 'wrap', alignItems: 'baseline',
      gap: '0.4rem',
    }}>
      <span>Compare to:</span>
      {splits.map((split, idx) => (
        <span key={split.label} style={{ display: 'inline-flex', alignItems: 'baseline', gap: '0.4rem' }}>
          <Link
            to={buildHref(split)}
            className="comp-link"
            style={{ color: 'var(--ink)', fontStyle: 'normal' }}
          >
            {split.label}
          </Link>
          {idx < splits.length - 1 && <span style={{ color: 'var(--ink-faint)' }}>·</span>}
        </span>
      ))}
    </div>
  )
}
