/**
 * InningToggle — page-local 1st-innings / 2nd-innings filter pill.
 *
 * Three-state segmented control writing the URL `?inning=` param. NOT
 * a FilterBar field (the 10-key ceiling stands); it's an AuxParams aux
 * narrowing surfaced as a per-page toggle on player and team
 * Batting/Bowling/Fielding/Partnerships pages.
 *
 *   [ All innings | 1st innings | 2nd innings ]
 *
 * - "All innings"  → URL deletes `inning`
 * - "1st innings"  → `?inning=0` (innings_number=0 in the match)
 * - "2nd innings"  → `?inning=1`
 *
 * Reading convention (spec-inning-split.md §7.1): the label refers to
 * the MATCH'S innings_number, regardless of which side of the ball the
 * page focuses on. So "Bumrah, 1st innings" = his deliveries when the
 * opposition was batting first; "RCB, 1st innings" = their batting
 * when they batted first. NEVER use "bowling first" / "fielded first"
 * — those phrases are ambiguous (see design-decisions.md).
 *
 * Used as a primary control above the page's headline stats. Default
 * is "All innings" (no narrowing) — matches the convention of every
 * other narrowing field.
 */
import { useUrlParam } from '../hooks/useUrlState'

export default function InningToggle() {
  const [inning, setInning] = useUrlParam('inning')
  const segBtn = (active: boolean) => `wisden-seg${active ? ' is-active' : ''}`
  return (
    <div className="wisden-filter-group" style={{ marginBottom: '0.5rem' }}>
      <span className="wisden-filter-label">Innings</span>
      <button
        type="button"
        className={segBtn(inning === '')}
        onClick={() => setInning('')}
        title="Show all innings (no narrowing)."
      >
        All innings
      </button>
      <button
        type="button"
        className={segBtn(inning === '0')}
        onClick={() => setInning('0')}
        title="Restrict to inning_number=0 — for batting pages, matches where this team batted first; for bowling/fielding pages, matches where this team bowled first."
      >
        1st innings
      </button>
      <button
        type="button"
        className={segBtn(inning === '1')}
        onClick={() => setInning('1')}
        title="Restrict to inning_number=1 — for batting pages, matches where this team chased; for bowling/fielding pages, matches where this team defended."
      >
        2nd innings
      </button>
    </div>
  )
}
