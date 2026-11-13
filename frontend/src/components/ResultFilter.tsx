/**
 * The All / Won / Lost / Tied pills, with match counts, that set the `?result=` filter on a page.
 *
 * ResultFilter — page-local won / lost / tied filter pill row.
 *
 * Mirrors InningToggle's structure (segmented pills writing a URL aux
 * param, "All" resets just that key) but shows scope-wide counts on
 * each pill so the widget reads as a filter AND a stat card.
 *
 * URL semantic — `?result=tied` collapses true ties + no-results into
 * one bucket (see types.ts FilterParams comment on `result`). The Tied
 * pill therefore shows `ties + no_results` and the tooltip surfaces
 * the collapse explicitly.
 *
 * Counts come from an aux-stripped summary fetch so they stay stable
 * when the user clicks Mosaic cells (which set toss/inning/result aux
 * params). Same approach as the Mosaic's `unauxSummaryFetch`-driven
 * marginal counts — consistent affordance across the page.
 *
 * Where this mounts: subtabs where the full Mosaic chart is overkill
 * but result-only narrowing is still useful. First mount site: Teams
 * Match List. See `docs/internal/inning-controls-mount-sites.md`.
 */
import { useUrlParam } from '../hooks/useUrlState'

/** Props of `ResultFilter`: the counts shown on the pills; null shows 0. */
interface Props {
  matches: number | null // all matches in scope, on the All pill
  wins: number | null // matches won
  losses: number | null // matches lost
  ties: number | null // ties, added to `noResults` on the Tied pill
  noResults: number | null // no-results, added to `ties` on the Tied pill
}

/** Show the result pills with their counts and write the choice to `?result=`. */
export default function ResultFilter({ matches, wins, losses, ties, noResults }: Props) {
  const [result, setResult] = useUrlParam('result')
  const tiedTotal = (ties ?? 0) + (noResults ?? 0)
  const seg = (active: boolean) => `wisden-seg${active ? ' is-active' : ''}`
  const num = (n: number | null) => (
    <span style={{ marginLeft: '0.4em', color: 'var(--ink-faint)', fontWeight: 400 }} className="num">
      {n ?? 0}
    </span>
  )
  return (
    <div className="wisden-filter-group" style={{ marginBottom: '0.5rem' }}>
      <span className="wisden-filter-label">Result</span>
      <button
        type="button"
        className={seg(result === '')}
        onClick={() => setResult('')}
        title="Show all results (no narrowing)."
      >
        All matches{num(matches)}
      </button>
      <button
        type="button"
        className={seg(result === 'won')}
        onClick={() => setResult('won')}
        title="Restrict to matches the team won."
      >
        Won{num(wins)}
      </button>
      <button
        type="button"
        className={seg(result === 'lost')}
        onClick={() => setResult('lost')}
        title="Restrict to matches the team lost."
      >
        Lost{num(losses)}
      </button>
      <button
        type="button"
        className={seg(result === 'tied')}
        onClick={() => setResult('tied')}
        title="Restrict to ties and no-results. URL bucket result=tied collapses both."
      >
        Tied{num(tiedTotal)}
      </button>
    </div>
  )
}
