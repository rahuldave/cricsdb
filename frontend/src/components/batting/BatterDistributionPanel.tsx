/**
 * Batter Distribution panel — top-level orchestrator. Spec
 * internal_docs/spec-distribution-stats.md §9 + §12.2.6 sparkline
 * conventions.
 *
 * Mounted on /batting?player=X between stat row 1 and stat row 2
 * — proximity to the Average tile is the user's anchoring need.
 *
 * URL state — both keys default to absent (canonical-default
 * discipline; share-link reproducibility):
 *   ?dist_window=scope|last_10|last_60d|last_6mo|last_1yr
 *   ?dist_metric=runs|sr
 *
 * Sparkline now uses the lifted DistributionSparkline with:
 *   - Tier-coloured bars on the Runs tab (matching the histogram
 *     bins — failure/building/fifty/century/rare).
 *   - Dual reference lines: black scope baseline + gray gender-
 *     global anchor (BATTING_GLOBAL_* in distribution/globalBaselines).
 *   - Rolling-10 mean overlay (oxblood/red) on the Scope window
 *     when n ≥ 10.
 */

import { useUrlParam } from '../../hooks/useUrlState'
import RunsHistogram from './RunsHistogram'
import DistributionStatStrip, { MilestoneChipsRow } from './DistributionStatStrip'
import DistributionSparkline, { type SparklinePoint } from '../distribution/DistributionSparkline'
import SeasonTickAxis from '../distribution/SeasonTickAxis'
import { pickBattingBaseline, type GlobalBattingBaselines } from '../distribution/globalBaselines'
import { binIndex, binTier } from './distributionBins'
import { WISDEN_RUN_TIERS } from '../charts/palette'
import FormDeltaLine from './FormDeltaLine'
import SuggestedSplitsRow from './SuggestedSplitsRow'
import type { BatterDistribution, DistributionDossier, InningsObservation } from '../../types'

type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'
type DistMetric = 'runs' | 'sr'

const WINDOW_OPTIONS: { key: DistWindow; label: string; param: string; tooltip: string }[] = [
  { key: 'scope',    label: 'Scope',    param: '',
    tooltip: 'All innings under the active filter scope.' },
  { key: 'last_10',  label: 'Last 10',  param: 'last_10',
    tooltip: 'Most recent 10 innings under the active filter scope.' },
  { key: 'last_60d', label: 'Last 60d', param: 'last_60d',
    tooltip: 'Innings in the last 60 days — current form.' },
  { key: 'last_6mo', label: 'Last 6mo', param: 'last_6mo',
    tooltip: 'Innings in the last 180 days — medium-term arc.' },
  { key: 'last_1yr', label: 'Last 1y',  param: 'last_1yr',
    tooltip: 'Innings in the last 365 days — annual / loss-of-form gauge.' },
]

const METRIC_OPTIONS: { key: DistMetric; label: string; param: string; tooltip: string }[] = [
  { key: 'runs', label: 'Runs',        param: '',
    tooltip: 'Per-innings runs distribution. Bars colored by milestone tier (duck / building / fifty / century / rare).' },
  { key: 'sr',   label: 'Strike Rate', param: 'sr',
    tooltip: 'Per-innings strike rate (runs × 100 / balls faced).' },
]

function pickDossier(dist: BatterDistribution, window: DistWindow): DistributionDossier {
  if (window === 'last_10') return dist.form.last_10
  if (window === 'last_60d') return dist.form.last_60d
  if (window === 'last_6mo') return dist.form.last_6mo
  if (window === 'last_1yr') return dist.form.last_1yr
  return dist.lifetime
}

const VALID_WINDOWS: ReadonlyArray<DistWindow> = ['last_10', 'last_60d', 'last_6mo', 'last_1yr']
const VALID_METRICS: ReadonlyArray<DistMetric> = ['sr']

interface SparklineConfig {
  point: (o: InningsObservation) => SparklinePoint
  playerReferenceValue: number | null
  globalReferenceValue: number
  caption: string
  globalLegend: string
}

function sparklineFor(
  metric: DistMetric,
  scopeLifetime: DistributionDossier,
  globals: GlobalBattingBaselines,
): SparklineConfig {
  if (metric === 'sr') {
    const balls = scopeLifetime.runs.balls_total
    const playerSR = balls > 0 ? +(scopeLifetime.runs.total * 100 / balls).toFixed(2) : null
    return {
      point: o => {
        const sr = o.balls > 0 ? +(o.runs * 100 / o.balls).toFixed(1) : 0
        return {
          date: o.date, matchId: o.match_id, value: sr,
          tooltip: `${o.date} · SR ${sr.toFixed(1)} (${o.runs}r in ${o.balls}b${o.dismissed ? '' : '*'})`,
        }
      },
      playerReferenceValue: playerSR,
      globalReferenceValue: globals.sr,
      caption: 'oldest ← bars (one per innings, height = SR) → most recent',
      globalLegend: `${globals.sr} SR`,
    }
  }
  return {
    point: o => ({
      date: o.date, matchId: o.match_id, value: o.runs,
      tooltip: `${o.date} · ${o.runs}r (${o.balls}b${o.dismissed ? '' : '*'})`,
      color: WISDEN_RUN_TIERS[binTier(binIndex(o.runs))],
    }),
    playerReferenceValue: scopeLifetime.runs.mean_per_innings,
    globalReferenceValue: globals.runs,
    caption: 'oldest ← bars (one per innings, height = runs) → most recent',
    globalLegend: `${globals.runs} runs/inn`,
  }
}

function SparklineLegend({ globalLegend, showRolling }: {
  globalLegend: string; showRolling: boolean
}) {
  const Swatch = ({ color, h = 1.5 }: { color: string; h?: number }) => (
    <span aria-hidden="true" style={{
      display: 'inline-block', width: 14, height: h,
      background: color, verticalAlign: 'middle',
    }} />
  )
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap',
      columnGap: '0.85rem', rowGap: '0.15rem',
      fontFamily: 'var(--serif)', fontStyle: 'italic',
      fontSize: '0.7rem', color: 'var(--ink-faint)',
    }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <Swatch color="#1A1714" h={2} /> scope baseline
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <Swatch color="#8A7D70" /> gender-global ({globalLegend})
      </span>
      {showRolling && (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <Swatch color="#7A1F1F" /> rolling-10 mean
        </span>
      )}
    </span>
  )
}

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
  const [metricParam, setMetricParam] = useUrlParam('dist_metric')

  const window: DistWindow = (VALID_WINDOWS as ReadonlyArray<string>).includes(windowParam)
    ? (windowParam as DistWindow)
    : 'scope'
  const metric: DistMetric = (VALID_METRICS as ReadonlyArray<string>).includes(metricParam)
    ? (metricParam as DistMetric)
    : 'runs'

  if (loading || error || !distribution) return null

  const dossier = pickDossier(distribution, window)
  const lifetimeEmpty = distribution.lifetime.n_innings === 0
  const windowEmpty = dossier.n_innings === 0

  function windowLabel(w: DistWindow): string {
    return WINDOW_OPTIONS.find(o => o.key === w)?.label ?? 'this window'
  }

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
        marginBottom: '0.5rem',
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

      {!lifetimeEmpty && (
        <div className="wisden-filter-group" style={{ marginBottom: '0.75rem' }}>
          {METRIC_OPTIONS.map(opt => (
            <button
              key={opt.key}
              type="button"
              className={`wisden-seg${metric === opt.key ? ' is-active' : ''}`}
              onClick={() => setMetricParam(opt.param)}
              title={opt.tooltip}
            >{opt.label}</button>
          ))}
        </div>
      )}

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
            No innings in {windowLabel(window)} under this filter.
          </div>
          <FormDeltaLine dossier={distribution} />
        </>
      ) : (
        <>
          {/* Histogram + stat strip rendered for the Runs metric only.
              The SR tab is sparkline-driven (per-innings SR is a
              continuous distribution; the existing histogram is
              integer-runs binned). */}
          {metric === 'runs' && (
            <>
              <div className="wisden-dist-grid">
                <RunsHistogram dossier={dossier} />
                <DistributionStatStrip dossier={dossier} />
              </div>
              <MilestoneChipsRow dossier={dossier} />
            </>
          )}

          <div style={{ marginTop: '0.75rem' }}>
            {(() => {
              const globals = pickBattingBaseline(distribution.scope)
              const cfg = sparklineFor(metric, distribution.lifetime, globals)
              const points = dossier.runs.observations.map(cfg.point)
              const showRolling = window === 'scope' && points.length >= 10
              return (
                <>
                  <DistributionSparkline
                    points={points}
                    playerReferenceValue={cfg.playerReferenceValue}
                    globalReferenceValue={cfg.globalReferenceValue}
                    rollingWindow={showRolling ? 10 : undefined}
                  />
                  <SeasonTickAxis dates={dossier.runs.observations.map(o => o.date)} />
                  <div style={{
                    display: 'flex', flexWrap: 'wrap', alignItems: 'baseline',
                    columnGap: '0.85rem', rowGap: '0.15rem',
                    marginTop: '0.1rem',
                    fontFamily: 'var(--serif)', fontStyle: 'italic',
                    fontSize: '0.7rem', color: 'var(--ink-faint)',
                  }}>
                    <span>{cfg.caption}</span>
                    <SparklineLegend globalLegend={cfg.globalLegend} showRolling={showRolling} />
                  </div>
                </>
              )
            })()}
          </div>
          <FormDeltaLine dossier={distribution} />
        </>
      )}

      <SuggestedSplitsRow playerId={playerId} splits={distribution.suggested_splits} />
    </section>
  )
}
