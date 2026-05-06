/**
 * Bowler Distribution panel — top-level orchestrator for the §12
 * frontend slice. Spec: internal_docs/spec-distribution-stats.md §12.
 *
 * Mounted on /bowling?player=X between stat row 1 (Wickets / Average
 * / Economy) and stat row 2 (Strike Rate / Best Figures / Dot% /
 * B/Boundary).
 *
 * URL state — both keys default to absent param (canonical default
 * encoded by absence; share-link reproducibility):
 *   ?dist_window=scope|last_10|last_60d|last_6mo|last_1yr
 *   ?dist_metric=wickets|economy|runs
 *
 * Window toggle redraws the histogram + stat strip + chips for the
 * active metric tab. Metric tab swaps the entire metric view
 * (histogram + stat strip + chips). Sparkline + form-delta line +
 * splits row are window-dependent / window-independent per spec
 * §12.2 — see those components.
 */

import { useUrlParam } from '../../hooks/useUrlState'
import WicketsHistogram from './WicketsHistogram'
import EconomyHistogram from './EconomyHistogram'
import RunsConcededHistogram from './RunsConcededHistogram'
import {
  WicketsStatStrip, WicketsChipsRow,
  EconomyStatStrip, EconomyChipsRow,
  RunsConcededStatStrip, RunsConcededChipsRow,
} from './BowlerStatStrips'
import DistributionSparkline, { type SparklinePoint } from '../distribution/DistributionSparkline'
import SeasonTickAxis from '../distribution/SeasonTickAxis'
import { pickBowlingBaseline, type GlobalBowlingBaselines } from '../distribution/globalBaselines'
import BowlerFormDeltaLine from './BowlerFormDeltaLine'
import BowlerSuggestedSplitsRow from './BowlerSuggestedSplitsRow'
import { WISDEN_WICKET_TIERS, WISDEN_LOWER_IS_BETTER_TIERS } from '../charts/palette'
import { wicketBin, wicketTier, economyTier, runsConcededTier } from './distributionBins'
import type { BowlerDistribution, BowlerDossier, BowlerInningsObservation } from '../../types'

type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'
type DistMetric = 'wickets' | 'economy' | 'runs'

const WINDOW_OPTIONS: { key: DistWindow; label: string; param: string; tooltip: string }[] = [
  { key: 'scope',    label: 'Scope',    param: '',
    tooltip: 'All qualifying spells under the active filter scope.' },
  { key: 'last_10',  label: 'Last 10',  param: 'last_10',
    tooltip: 'Most recent 10 qualifying spells.' },
  { key: 'last_60d', label: 'Last 60d', param: 'last_60d',
    tooltip: 'Spells in the last 60 days — current form.' },
  { key: 'last_6mo', label: 'Last 6mo', param: 'last_6mo',
    tooltip: 'Spells in the last 180 days — medium-term arc.' },
  { key: 'last_1yr', label: 'Last 1y',  param: 'last_1yr',
    tooltip: 'Spells in the last 365 days — annual gauge.' },
]

const METRIC_OPTIONS: { key: DistMetric; label: string; param: string; tooltip: string }[] = [
  { key: 'wickets', label: 'Wickets',       param: '',
    tooltip: 'Per-innings wicket distribution + ≥2-anchored conditional ladder.' },
  { key: 'economy', label: 'Economy',       param: 'economy',
    tooltip: 'Per-innings RPO distribution + economy-threshold milestones.' },
  { key: 'runs',    label: 'Runs conceded', param: 'runs',
    tooltip: 'Per-innings absolute runs conceded distribution.' },
]

const VALID_WINDOWS: ReadonlyArray<DistWindow> = ['last_10', 'last_60d', 'last_6mo', 'last_1yr']
const VALID_METRICS: ReadonlyArray<DistMetric> = ['economy', 'runs']

function pickDossier(dist: BowlerDistribution, window: DistWindow): BowlerDossier {
  if (window === 'last_10') return dist.form.last_10
  if (window === 'last_60d') return dist.form.last_60d
  if (window === 'last_6mo') return dist.form.last_6mo
  if (window === 'last_1yr') return dist.form.last_1yr
  return dist.lifetime
}

interface SparklineConfig {
  /** Per-bar mapping from observation → renderable point. */
  point: (o: BowlerInningsObservation) => SparklinePoint
  /** Player line — scope-baseline mean (the lifetime block of the
   *  active filter scope). Constant across window toggles. */
  playerReferenceValue: number | null
  /** Global line — gender-tiered all-bowler centre. */
  globalReferenceValue: number
  caption: string
  /** "8 RPO" / "1 wkts/spell" / "26 runs/spell" — for the legend. */
  globalLegend: string
}

function sparklineFor(
  metric: DistMetric,
  scopeLifetime: BowlerDossier,
  globals: GlobalBowlingBaselines,
): SparklineConfig {
  if (metric === 'wickets') {
    return {
      point: o => ({
        date: o.date, matchId: o.match_id, value: o.wickets,
        tooltip: `${o.date} · ${o.wickets} wkt${o.wickets === 1 ? '' : 's'} (${o.balls}b, ${o.runs_conceded}r)`,
        color: WISDEN_WICKET_TIERS[wicketTier(wicketBin(o.wickets))],
      }),
      playerReferenceValue: scopeLifetime.wickets.mean_per_innings,
      globalReferenceValue: globals.wickets,
      caption: 'oldest ← bars (one per spell, height = wickets) → most recent',
      globalLegend: `${globals.wickets} wkts/spell`,
    }
  }
  if (metric === 'economy') {
    return {
      point: o => {
        const v = o.balls > 0 ? +(o.runs_conceded * 6 / o.balls).toFixed(2) : 0
        return {
          date: o.date, matchId: o.match_id, value: v,
          tooltip: `${o.date} · econ ${v.toFixed(2)} (${o.runs_conceded}r in ${o.balls}b, ${o.wickets} wkt${o.wickets === 1 ? '' : 's'})`,
          color: WISDEN_LOWER_IS_BETTER_TIERS[economyTier(v)],
        }
      },
      playerReferenceValue: scopeLifetime.economy.pool,
      globalReferenceValue: globals.rpo,
      caption: 'oldest ← bars (one per spell, height = econ RPO) → most recent',
      globalLegend: `${globals.rpo} RPO`,
    }
  }
  return {
    point: o => ({
      date: o.date, matchId: o.match_id, value: o.runs_conceded,
      tooltip: `${o.date} · ${o.runs_conceded}r conceded (${o.balls}b, ${o.wickets} wkt${o.wickets === 1 ? '' : 's'})`,
      color: WISDEN_LOWER_IS_BETTER_TIERS[runsConcededTier(o.runs_conceded)],
    }),
    playerReferenceValue: scopeLifetime.runs_conceded.mean_per_innings,
    globalReferenceValue: globals.runs,
    caption: 'oldest ← bars (one per spell, height = runs conceded) → most recent',
    globalLegend: `${globals.runs} runs/spell`,
  }
}

/** Tiny inline legend explaining the reference lines + rolling mean. */
function SparklineLegend({ globalLegend, showRolling }: {
  globalLegend: string
  showRolling: boolean
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
        <Swatch color="#1A1714" h={2} />
        scope baseline
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <Swatch color="#8A7D70" h={1.5} />
        gender-global ({globalLegend})
      </span>
      {showRolling && (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <Swatch color="#7A1F1F" h={1.5} />
          rolling-10 mean
        </span>
      )}
    </span>
  )
}


interface Props {
  playerId: string
  distribution: BowlerDistribution | null
  loading: boolean
  error: string | null
}

export default function BowlerDistributionPanel({
  playerId, distribution, loading, error,
}: Props) {
  const [windowParam, setWindowParam] = useUrlParam('dist_window')
  const [metricParam, setMetricParam] = useUrlParam('dist_metric')

  const window: DistWindow = (VALID_WINDOWS as ReadonlyArray<string>).includes(windowParam)
    ? (windowParam as DistWindow)
    : 'scope'
  const metric: DistMetric = (VALID_METRICS as ReadonlyArray<string>).includes(metricParam)
    ? (metricParam as DistMetric)
    : 'wickets'

  if (loading || error || !distribution) return null

  const dossier = pickDossier(distribution, window)
  const lifetimeEmpty = distribution.lifetime.n_innings === 0
  const windowEmpty = dossier.n_innings === 0
  const minBalls = distribution.thresholds.min_balls

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
      aria-label="Per-innings bowling distribution"
    >
      <header style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: '0.5rem',
        marginBottom: '0.5rem',
      }}>
        <div style={{
          display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.6rem',
        }}>
          <div style={{
            fontFamily: 'var(--serif)',
            fontStyle: 'italic',
            fontSize: '0.78rem',
            color: 'var(--ink-faint)',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}>
            Per-innings bowling distribution
          </div>
          <div style={{
            fontFamily: 'var(--serif)',
            fontStyle: 'italic',
            fontSize: '0.72rem',
            color: 'var(--ink-faint)',
          }}>
            min {minBalls} balls
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

      {lifetimeEmpty ? (
        <div style={{
          padding: '1.5rem 0',
          textAlign: 'center',
          fontFamily: 'var(--serif)',
          fontStyle: 'italic',
          color: 'var(--ink-faint)',
        }}>
          No qualifying spells (≥ {minBalls} balls) under this filter — try
          widening the scope, or add <code>?min_balls=0</code> to include
          short cameos.
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
            No qualifying spells in {windowLabel(window)} under this filter.
          </div>
          <BowlerFormDeltaLine dossier={distribution} />
        </>
      ) : (
        <>
          <div className="wisden-dist-grid">
            {metric === 'wickets' && (
              <>
                <WicketsHistogram block={dossier.wickets} />
                <WicketsStatStrip
                  block={dossier.wickets}
                  dossier={dossier}
                  n_innings={dossier.n_innings}
                />
              </>
            )}
            {metric === 'economy' && (
              <>
                <EconomyHistogram block={dossier.economy} />
                <EconomyStatStrip block={dossier.economy} />
              </>
            )}
            {metric === 'runs' && (
              <>
                <RunsConcededHistogram observations={dossier.wickets.observations} />
                <RunsConcededStatStrip block={dossier.runs_conceded} />
              </>
            )}
          </div>
          {metric === 'wickets' && <WicketsChipsRow block={dossier.wickets} />}
          {metric === 'economy' && <EconomyChipsRow block={dossier.economy} />}
          {metric === 'runs' && <RunsConcededChipsRow block={dossier.runs_conceded} />}

          <div style={{ marginTop: '0.75rem' }}>
            {(() => {
              const globals = pickBowlingBaseline(distribution.scope)
              const cfg = sparklineFor(metric, distribution.lifetime, globals)
              const points = dossier.wickets.observations.map(cfg.point)
              // Rolling-mean overlay only on the widest window (Scope)
              // where smoothing reads as form-arc rather than noise;
              // skipped on Last 10 / 60d / 6mo / 1y (samples too short).
              const showRolling = window === 'scope' && points.length >= 10
              return (
                <>
                  <DistributionSparkline
                    points={points}
                    playerReferenceValue={cfg.playerReferenceValue}
                    globalReferenceValue={cfg.globalReferenceValue}
                    rollingWindow={showRolling ? 10 : undefined}
                  />
                  <SeasonTickAxis dates={dossier.wickets.observations.map(o => o.date)} />
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

          <BowlerFormDeltaLine dossier={distribution} />
        </>
      )}

      <BowlerSuggestedSplitsRow playerId={playerId} splits={distribution.suggested_splits} />
    </section>
  )
}
