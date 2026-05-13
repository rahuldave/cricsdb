/**
 * League page — above-tournament scope dossier.
 *
 * The destination for FilterBar configurations broader than a single
 * tournament: "men's club cricket," "men's primary-tier clubs,"
 * "women's international ICC tournaments," etc. Mirrors the
 * Tournament dossier shape (Overview / Batting / Bowling / Fielding
 * tabs) but the subject IS the scope itself.
 *
 * The H2 title renders the scope in prose English (Men's club
 * Twenty20 cricket) via `scopeToProse` rather than the dot-separated
 * abbreviation used elsewhere — there's no separate page subject to
 * pair the abbreviation with, so the abbreviation becomes the title.
 * Spec: internal_docs/spec-league-pages.md §D8 + user 2026-05-13.
 *
 * URL normalisation (Spec §D6 + UX §Empty/sparse):
 *  - Zero scope params → redirect to ?gender=male&team_type=club.
 *  - tournament=X set  → redirect to /series?tournament=X (the more
 *    specific destination; /league shouldn't duplicate Series).
 */
import { useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useFilters } from '../hooks/useFilters'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { scopeToProse } from '../components/scopeLinks'
import InningToggle from '../components/InningToggle'

type TabName = 'Overview' | 'Batting' | 'Bowling' | 'Fielding'
const TABS: TabName[] = ['Overview', 'Batting', 'Bowling', 'Fielding']

export default function League() {
  const filters = useFilters()
  const setUrlParams = useSetUrlParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [activeTab, setActiveTab] = useUrlParam('tab', 'Overview')
  const currentTab: TabName = TABS.includes(activeTab as TabName)
    ? (activeTab as TabName)
    : 'Overview'

  // D6: deep-link /league with no scope params lands on the broadest
  // tier (men's club). The page can't meaningfully render without at
  // least gender + team_type — "all cricket" is too unspecific to
  // calibrate the UI to. URL-clean rule exception: /league with no
  // params is non-canonical by construction; the replace lands a
  // canonical URL the user can share.
  useEffect(() => {
    if (!filters.gender && !filters.team_type && !filters.tournament) {
      setUrlParams({ gender: 'male', team_type: 'club' }, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Single-tournament redirect: /league?tournament=IPL → /series?tournament=IPL.
  // /league is the above-tournament destination; once tournament is
  // pinned, the user's actually asking for the per-tournament dossier
  // and Series is the canonical home.
  useEffect(() => {
    if (filters.tournament) {
      navigate(`/series${location.search}`, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.tournament])

  const docTitle = scopeToProse(filters)
  useDocumentTitle(docTitle)

  return (
    <div>
      {/* H2 = prose scope. No right-side italic abbreviation here —
          the H2 IS the abbreviation, expressed in English. */}
      <h2 className="wisden-page-title" style={{ margin: 0 }}>
        {docTitle}
      </h2>

      <div className="wisden-tabs mt-4">
        {TABS.map(tab => (
          <button
            key={tab}
            type="button"
            className={`wisden-tab${currentTab === tab ? ' is-active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {currentTab !== 'Overview' && <InningToggle />}

      {currentTab === 'Overview' && (
        <div className="wisden-tab-help mt-4">Overview content lands in step 6.</div>
      )}
      {currentTab === 'Batting' && (
        <div className="wisden-tab-help mt-4">Batting content lands in step 7.</div>
      )}
      {currentTab === 'Bowling' && (
        <div className="wisden-tab-help mt-4">Bowling content lands in step 8.</div>
      )}
      {currentTab === 'Fielding' && (
        <div className="wisden-tab-help mt-4">Fielding content lands in step 9.</div>
      )}
    </div>
  )
}
