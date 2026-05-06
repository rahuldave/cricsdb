/**
 * Batter Distribution panel — top-level orchestrator for the §9
 * frontend slice. Spec: internal_docs/spec-distribution-stats.md §9.
 *
 * Mounted on /batting?player=X between stat row 1 (Avg sits there)
 * and stat row 2 (boundaries / dots / etc.) — proximity to the
 * Average tile is the user's anchoring requirement.
 *
 * Window selection is URL-encoded as ?dist_window=lifetime|last_10|
 * last_60d (default = absent param → lifetime). Toggle clicks land
 * in browser history (back-button restores prior window). Per
 * §9.7 + feedback_state_location.md — share-link reproducibility.
 */

import { useUrlParam } from '../../hooks/useUrlState'
import RunsHistogram from './RunsHistogram'
import DistributionStatStrip, { MilestoneChipsRow } from './DistributionStatStrip'
import RunsSparkline from './RunsSparkline'
import FormDeltaLine from './FormDeltaLine'
import SuggestedSplitsRow from './SuggestedSplitsRow'
import type { BatterDistribution, DistributionDossier } from '../../types'

type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'

const WINDOW_OPTIONS: { key: DistWindow; label: string; param: string; tooltip: string }[] = [
  { key: 'scope',    label: 'Scope',    param: '',
    tooltip: 'All innings under the active filter scope (NOT necessarily lifetime — IPL 2024 is "scope" when that filter is set).' },
  { key: 'last_10',  label: 'Last 10',  param: 'last_10',
    tooltip: 'Most recent 10 innings under the active filter scope.' },
  { key: 'last_60d', label: 'Last 60d', param: 'last_60d',
    tooltip: 'Innings in the last 60 days — current form.' },
  { key: 'last_6mo', label: 'Last 6mo', param: 'last_6mo',
    tooltip: 'Innings in the last 180 days — medium-term arc.' },
  { key: 'last_1yr', label: 'Last 1y',  param: 'last_1yr',
    tooltip: 'Innings in the last 365 days — annual / loss-of-form gauge.' },
]

function pickDossier(dist: BatterDistribution, window: DistWindow): DistributionDossier {
  if (window === 'last_10') return dist.form.last_10
  if (window === 'last_60d') return dist.form.last_60d
  if (window === 'last_6mo') return dist.form.last_6mo
  if (window === 'last_1yr') return dist.form.last_1yr
  return dist.lifetime
}

const VALID_WINDOWS: ReadonlyArray<DistWindow> = ['last_10', 'last_60d', 'last_6mo', 'last_1yr']

interface Props {
  playerId: string
  distribution: BatterDistribution | null
  loading: boolean
  error: string | null
}

export default function BatterDistributionPanel({
  playerId, distribution, loading, error,
}: Props) {
  const [windowParam, setWindowParam] = useUrlParam('dist_window')
  const window: DistWindow = (VALID_WINDOWS as ReadonlyArray<string>).includes(windowParam)
    ? (windowParam as DistWindow)
    : 'scope'

  // Hide entirely on initial load + on hard error — caller's main
  // loading spinner / error banner already cover the page-level UX.
  if (loading || error || !distribution) return null

  const dossier = pickDossier(distribution, window)
  const lifetimeEmpty = distribution.lifetime.n_innings === 0
  const windowEmpty = dossier.n_innings === 0

  return (
    <section
      className="wisden-statrow"
      style={{
        display: 'block',
        padding: '1.25rem 0.5rem 0.75rem',
        borderTop: '1px solid var(--rule)',
        borderBottom: '1px solid var(--rule)',
      }}
      aria-label="Per-innings runs distribution"
    >
      <header style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: '0.5rem',
        marginBottom: '0.75rem',
      }}>
        <div>
          <div style={{
            fontFamily: 'var(--serif)',
            fontStyle: 'italic',
            fontSize: '0.78rem',
            color: 'var(--ink-faint)',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}>
            Per-innings runs distribution
          </div>
        </div>
        <div className="wisden-filter-group">
          {WINDOW_OPTIONS.map(opt => (
            <button
              key={opt.key}
              type="button"
              className={`wisden-seg${window === opt.key ? ' is-active' : ''}`}
              onClick={() => setWindowParam(opt.param)}
              title={opt.tooltip}
            >{opt.label}</button>
          ))}
        </div>
      </header>

      {lifetimeEmpty ? (
        <div style={{
          padding: '1.5rem 0',
          textAlign: 'center',
          fontFamily: 'var(--serif)',
          fontStyle: 'italic',
          color: 'var(--ink-faint)',
        }}>
          No innings under this filter — try widening the scope.
        </div>
      ) : windowEmpty ? (
        <>
          <div style={{
            padding: '1rem 0',
            textAlign: 'center',
            fontFamily: 'var(--serif)',
            fontStyle: 'italic',
            color: 'var(--ink-faint)',
          }}>
            No innings in the {window === 'last_10' ? 'last 10' : 'last 60 days'} under this filter.
          </div>
          <FormDeltaLine dossier={distribution} />
        </>
      ) : (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) minmax(220px, 320px)',
            gap: '1.5rem',
            alignItems: 'start',
          }}>
            <RunsHistogram dossier={dossier} />
            <DistributionStatStrip dossier={dossier} />
          </div>
          <MilestoneChipsRow dossier={dossier} />
          <div style={{ marginTop: '0.75rem' }}>
            <RunsSparkline
              observations={dossier.runs.observations}
              rollingWindow={window === 'scope' ? 10 : undefined}
              referenceRuns={20}
            />
            <div style={{
              fontFamily: 'var(--serif)', fontStyle: 'italic',
              fontSize: '0.7rem', color: 'var(--ink-faint)',
              marginTop: '0.25rem',
            }}>
              oldest ← bars (one per innings) → most recent
              {' · '}
              <span style={{ color: 'var(--ink)' }}>—</span>{' 20-run line'}
              {window === 'scope' && (
                <>
                  {' · '}
                  <span style={{ color: '#7A1F1F' }}>—</span>{' 10-innings rolling mean'}
                </>
              )}
            </div>
          </div>
          <FormDeltaLine dossier={distribution} />
        </>
      )}

      <SuggestedSplitsRow playerId={playerId} splits={distribution.suggested_splits} />
    </section>
  )
}
