/**
 * DormancyBadge — small italic badge that reads from DormancyContext
 * and renders the tiered '(0 in N)' label when the entity has been
 * inactive in scope for more than 60 days.
 *
 * Spec: internal_docs/design-decisions.md "Dormancy badge".
 */

import { useDormancy, dormancyGapDays, dormancyBadgeText } from './DormancyContext'

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
