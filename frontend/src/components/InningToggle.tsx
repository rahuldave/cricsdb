/**
 * InningToggle — page-local 1st-innings / 2nd-innings filter pill.
 *
 * Three-state segmented control writing the URL `?inning=` param. NOT
 * a FilterBar field (the 10-key ceiling stands); it's an AuxParams aux
 * narrowing surfaced as a per-page toggle on player and dossier pages.
 *
 *   [ All innings | 1st innings | 2nd innings ]   (ambiguous pages)
 *   [ All innings | Batting first | Batting second ]   (batting POV)
 *   [ All innings | Bowling first | Bowling second ]   (bowling/fielding POV)
 *
 * URL semantics are constant across all POVs — `?inning=0` ALWAYS
 * means `innings.innings_number = 0` (the match's 1st innings half).
 * The visible label is POV-aware via `useDiscipline()`:
 *
 *   - batting (incl. Partnerships) → "Batting first / second"
 *   - bowling | fielding          → "Bowling first / second"
 *     (fielding inherits bowling terminology — NEVER "fielded first")
 *   - null (ambiguous: Records, single-player profile) → keep neutral
 *     "1st innings / 2nd innings". A single `?inning=0` on these pages
 *     simultaneously means "batted first" for batting stats, "bowled
 *     first" for bowling stats, and "fielded first" for fielding stats
 *     — no single POV label can be accurate for all three.
 *
 * Source-of-truth doc: `internal_docs/spec-inning-split.md` §7.1.
 * Polysemy lock: `tests/integration/inning_toggle_pov_labels.sh`.
 */
import { useUrlParam } from '../hooks/useUrlState'
import { useDiscipline } from '../hooks/useDiscipline'

export default function InningToggle() {
  const [inning, setInning] = useUrlParam('inning')
  const discipline = useDiscipline()

  const isBatting = discipline === 'batting'
  const isBowlOrField = discipline === 'bowling' || discipline === 'fielding'
  const firstLabel  = isBatting ? 'Batting first'  : isBowlOrField ? 'Bowling first'  : '1st innings'
  const secondLabel = isBatting ? 'Batting second' : isBowlOrField ? 'Bowling second' : '2nd innings'

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
        title="Restrict to innings_number=0 — the match's 1st innings half. Batting stats reflect batting-first; bowling/fielding stats reflect bowling-first."
      >
        {firstLabel}
      </button>
      <button
        type="button"
        className={segBtn(inning === '1')}
        onClick={() => setInning('1')}
        title="Restrict to innings_number=1 — the match's 2nd innings half. Batting stats reflect chasing; bowling/fielding stats reflect defending."
      >
        {secondLabel}
      </button>
    </div>
  )
}
