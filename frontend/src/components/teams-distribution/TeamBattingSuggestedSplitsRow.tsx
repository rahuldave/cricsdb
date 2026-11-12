/**
 * A "Compare to:" row of links that open the same team under a suggested scope.
 *
 * Suggested-splits navigation row for the team-batting Distribution
 * panel. Spec: internal_docs/spec-distribution-stats.md §17.3.
 *
 * Sibling of BowlerSuggestedSplitsRow. Navigates to the SAME /teams
 * page with the same team but the split's scope params applied.
 * Inning aux + tab + page-local URL state (`dist_window_t`,
 * `dist_metric_t_*`) are preserved so the user lands in the same
 * view mode under the broader scope.
 */

import { Link, useSearchParams } from 'react-router-dom'
import type { SuggestedSplit } from '../../types'

/** Props of `TeamBattingSuggestedSplitsRow`. */
interface Props {
  team: string // the team's name, kept as `team` in each link
  splits: SuggestedSplit[] // the suggested scopes, each a label and its URL params; nothing renders when empty
}

const PRESERVED_KEYS = [
  'inning', 'tab',
  'dist_window_t',
  'dist_metric_t_bat', 'dist_metric_t_bowl', 'dist_metric_t_field',
]

/**
 * Show a link to `/teams` for each suggested split, with the split's params applied and the inning, tab
 * and distribution window and metric kept from the current URL.
 */
export default function TeamBattingSuggestedSplitsRow({ team, splits }: Props) {
  const [searchParams] = useSearchParams()
  if (splits.length === 0) return null

  function buildHref(split: SuggestedSplit): string {
    const sp = new URLSearchParams()
    sp.set('team', team)
    for (const [k, v] of Object.entries(split.params)) sp.set(k, v)
    for (const key of PRESERVED_KEYS) {
      const v = searchParams.get(key)
      if (v !== null) sp.set(key, v)
    }
    return `/teams?${sp.toString()}`
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
