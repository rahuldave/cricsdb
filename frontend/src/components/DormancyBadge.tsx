/**
 * The badge in a page header that says how long ago the player or team last played in the scope.
 *
 * DormancyBadge — small italic badge that reads from DormancyContext
 * and renders the tiered label ("5 months since last match" or
 * "last match: Oct 2021") when the entity has been
 * inactive in scope for more than 60 days.
 *
 * Spec: internal_docs/design-decisions.md "Dormancy badge".
 */

import { useDormancy, dormancyGapDays, dormancyBadgeText } from './DormancyContext'

/**
 * Show the dormancy text for the last match date in `DormancyContext`, with the date and gap as a tooltip.
 * @returns the badge, or null when the gap is 60 days or less
 */
export default function DormancyBadge() {
  const { lastMatchDate } = useDormancy()
  const gap = dormancyGapDays(lastMatchDate)
  const text = dormancyBadgeText(gap, lastMatchDate)
  if (!text) return null
  return (
    <span
      className="wisden-dormancy-badge"
      title={`Last match in this scope: ${lastMatchDate} (${gap} days ago)`}
      style={{
        fontFamily: 'var(--serif)',
        fontStyle: 'italic',
        fontSize: '0.78rem',
        color: 'var(--ink-faint)',
        marginLeft: '0.4rem',
        cursor: 'help',
      }}
    >
      {text}
    </span>
  )
}
