/**
 * TossFilter — page-local won / lost toss-outcome filter pill row.
 *
 * Sibling of ResultFilter (won/lost/tied match result), built to the
 * same shape: a segmented pill row writing a URL aux param ("All"
 * resets just that key) with scope-wide counts on each pill so the
 * widget reads as a filter AND a stat card.
 *
 * Writes the `toss_outcome` aux param (`won` | `lost`). There is NO
 * "Tied" pill — a toss always has a winner. Matches with no recorded
 * toss are excluded from both buckets, so Won + Lost may be < the
 * all-matches count (the tooltip notes this).
 *
 * Presentational only — counts come from the caller (e.g. the player
 * /result-counts toss_won/toss_lost fields). Mount surface is TBD per
 * spec-player-baseline-aux-fallback.md §6.1 (built now, mounted later);
 * exercised today only on the unlisted /dev/toss-filter test surface.
 */
import { useUrlParam } from '../hooks/useUrlState'

interface Props {
  matches: number | null
  won: number | null
  lost: number | null
}

export default function TossFilter({ matches, won, lost }: Props) {
  const [toss, setToss] = useUrlParam('toss_outcome')
  const seg = (active: boolean) => `wisden-seg${active ? ' is-active' : ''}`
  const num = (n: number | null) => (
    <span style={{ marginLeft: '0.4em', color: 'var(--ink-faint)', fontWeight: 400 }} className="num">
      {n ?? 0}
    </span>
  )
  return (
    <div className="wisden-filter-group" style={{ marginBottom: '0.5rem' }}>
      <span className="wisden-filter-label">Toss</span>
      <button
        type="button"
        className={seg(toss === '')}
        onClick={() => setToss('')}
        title="Show all matches regardless of toss outcome (no narrowing)."
      >
        All matches{num(matches)}
      </button>
      <button
        type="button"
        className={seg(toss === 'won')}
        onClick={() => setToss('won')}
        title="Restrict to matches where the team won the toss."
      >
        Won toss{num(won)}
      </button>
      <button
        type="button"
        className={seg(toss === 'lost')}
        onClick={() => setToss('lost')}
        title="Restrict to matches where the team lost the toss. Matches with no recorded toss are excluded from both Won and Lost."
      >
        Lost toss{num(lost)}
      </button>
    </div>
  )
}
