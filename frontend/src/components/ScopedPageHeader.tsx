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
import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import type { FilterParams } from '../types'
import { abbreviateScope } from './scopeLinks'
import DormancyBadge from './DormancyBadge'
import { useDiscipline } from '../hooks/useDiscipline'


/** Build a /players?player=X URL that preserves every active filter
 *  axis so the cross-discipline link round-trips the user's scope.
 *  Suppresses the link entirely when playerId is unset. */
function allDisciplinesHref(playerId: string, filters: FilterParams): string {
  const qs = new URLSearchParams({ player: playerId })
  for (const [k, v] of Object.entries(filters)) {
    if (v != null && v !== '') qs.set(k, String(v))
  }
  return `/players?${qs.toString()}`
}


/** Inline small-caps oxblood "SCOPE" marker — same visual style as the
 *  large SCOPE label on the row above so the reader's eye links the
 *  word back to the scope phrase. Used inside the comparison line
 *  via the `{scope}` token (see Props.comparison below). */
function ScopeWord() {
  return (
    <span style={{
      fontVariant: 'all-small-caps',
      letterSpacing: '0.08em',
      fontWeight: 700,
      fontStyle: 'normal',
      color: 'var(--accent)',
    }}>scope</span>
  )
}


/** Split a comparison-line template on the `{scope}` token, returning
 *  the alternating text + <ScopeWord /> as a ReactNode list. Caller
 *  feeds the result into the small italic phrase span. */
function renderComparisonText(template: string): ReactNode {
  const parts = template.split('{scope}')
  return parts.map((part, i) => (
    <Fragment key={i}>
      {part}
      {i < parts.length - 1 && <ScopeWord />}
    </Fragment>
  ))
}

interface Props {
  filters: FilterParams
  /** Axes to exclude from the abbreviated scope — typically the
   *  page's subject axis when it's already in the title. e.g. the
   *  Series dossier omits 'tournament' (its H2 IS the tournament
   *  name, so showing it again in the scope is redundant). */
  omit?: (keyof FilterParams)[]
  /** Suppress the right-side italic abbreviation entirely. Set when
   *  the H2 already contains the full scope (e.g. /series at broad
   *  scope renders "Men's club Twenty20 cricket, 2024–2025" — the
   *  abbreviation would just repeat the title). */
  hideAbbrev?: boolean
  /** Optional comparison-anchor line that wraps to its own row below
   *  the SCOPE pill. `label` is the small-caps accent prefix (e.g.
   *  "COHORT" on player pages, "AVG" on team pages); `text` is the
   *  one-line phrase describing what the chip baselines compare
   *  against. Same italic / muted-grey styling as the SCOPE phrase
   *  so the two lines read as a paired anchor.
   *
   *  Use the literal token `{scope}` inside `text` to embed an
   *  inline small-caps oxblood "scope" marker — visually links the
   *  comparison phrase back to the SCOPE line above. */
  comparison?: { label: string; text: string } | null
  /** When set, render a small italic "{Discipline} (all)" tag next to
   *  the title where "all" links to /players?player=X at the current
   *  filter scope. Set on Batting / Bowling / Fielding when a player
   *  is selected; /players itself never sets it (it IS the
   *  destination). User-asked 2026-05-22. */
  playerId?: string
  children: ReactNode
}

export default function ScopedPageHeader({ filters, omit, hideAbbrev, comparison, playerId, children }: Props) {
  const discipline = useDiscipline()
  const scoped: FilterParams = omit && omit.length > 0
    ? { ...filters, ...Object.fromEntries(omit.map(k => [k, undefined])) }
    : filters
  const abbrev = hideAbbrev ? '' : abbreviateScope(scoped)
  const disciplineLabel = discipline
    ? discipline.charAt(0).toUpperCase() + discipline.slice(1)
    : null
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
        <DormancyBadge />
        {playerId && disciplineLabel && (
          <span style={{
            fontSize: '0.55em',
            fontStyle: 'italic',
            fontWeight: 'normal',
          }}>
            {disciplineLabel} (<Link to={allDisciplinesHref(playerId, filters)} className="comp-link">all</Link>)
          </span>
        )}
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
      {comparison && (
        <span style={{
          fontFamily: 'var(--serif)',
          fontStyle: 'italic',
          fontSize: '0.95rem',
          color: 'var(--ink-faint)',
          // Sits inline with the SCOPE pill on wide viewports; the
          // outer flex container's flex-wrap lets the whole pill
          // drop to its own row when there isn't horizontal room.
          // Text inside this pill wraps normally (no nowrap pin).
        }}>
          <span style={{
            fontVariant: 'all-small-caps',
            letterSpacing: '0.08em',
            fontWeight: 700,
            fontStyle: 'normal',
            color: 'var(--accent)',
            marginRight: '0.4rem',
          }}>{comparison.label}</span>
          {renderComparisonText(comparison.text)}
        </span>
      )}
    </div>
  )
}
