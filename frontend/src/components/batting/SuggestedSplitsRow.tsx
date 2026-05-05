/**
 * Suggested-splits navigation row for the batter Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §9.2.6.
 *
 * Reads `dossier.suggested_splits` (server-emitted). Each split is a
 * (label, params) pair — clicking navigates to the SAME /batting page
 * with the same player but the split's scope params applied. The
 * inning aux (NOT in split.params; it's a page-local AuxParam) is
 * preserved across the navigation so the toggle state survives.
 *
 * Hidden when no splits — e.g. user is already at all-time + no
 * narrowing axes set.
 */

import { Link, useSearchParams } from 'react-router-dom'
import type { SuggestedSplit } from '../../types'

interface Props {
  playerId: string
  splits: SuggestedSplit[]
}

export default function SuggestedSplitsRow({ playerId, splits }: Props) {
  const [searchParams] = useSearchParams()
  if (splits.length === 0) return null

  const inheritedInning = searchParams.get('inning')

  function buildHref(split: SuggestedSplit): string {
    const sp = new URLSearchParams()
    sp.set('player', playerId)
    for (const [k, v] of Object.entries(split.params)) sp.set(k, v)
    if (inheritedInning !== null) sp.set('inning', inheritedInning)
    return `/batting?${sp.toString()}`
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
