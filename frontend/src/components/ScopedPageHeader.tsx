/**
 * ScopedPageHeader — page-level title bar with the active filter
 * scope rendered inline as an italic abbreviation. Used on every
 * scoped page (Batting / Bowling / Fielding / Players / Teams /
 * Series / Venues / HeadToHead) so the user sees both the page
 * subject (the title content — name + flag etc.) AND the active
 * scope at a glance, without consulting the status strip.
 *
 * Layout: flex container; title content on the left, "SCOPE
 * <abbreviation>" on the right. Wraps to a second row on narrow
 * viewports so the abbreviation drops below the title on mobile.
 *
 * Spec: internal_docs/spec-distribution-stats.md §9.1 (the language
 * established for the batter Distribution panel) — promoted here
 * to a cross-page component.
 */

import type { ReactNode } from 'react'
import type { FilterParams } from '../types'
import { abbreviateScope } from './scopeLinks'

interface Props {
  filters: FilterParams
  children: ReactNode
}

export default function ScopedPageHeader({ filters, children }: Props) {
  const abbrev = abbreviateScope(filters)
  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'baseline',
      columnGap: '1rem',
      rowGap: '0.25rem',
      marginBottom: '1rem',
    }}>
      <h2 className="wisden-page-title" style={{
        margin: 0,
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: '0.6rem',
      }}>
        {children}
      </h2>
      {abbrev && (
        <span style={{
          fontFamily: 'var(--serif)',
          fontStyle: 'italic',
          fontSize: '0.95rem',
          color: 'var(--ink-faint)',
        }}>
          <span style={{
            fontVariant: 'all-small-caps',
            letterSpacing: '0.08em',
            fontWeight: 700,
            fontStyle: 'normal',
            color: 'var(--accent)',
            marginRight: '0.4rem',
          }}>scope</span>
          {abbrev}
        </span>
      )}
    </div>
  )
}
