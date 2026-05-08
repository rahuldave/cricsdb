/**
 * Team-fielding Distribution panel — top-level orchestrator for the
 * §17.5 frontend slice. Spec:
 * internal_docs/spec-distribution-stats.md §17.5.
 *
 * Mounted at the top of the Teams page Fielding tab content area
 * (see Teams.tsx).
 *
 * URL state — both keys default to absent param (canonical default
 * encoded by absence; share-link reproducibility):
 *   ?dist_window_t=scope|last_10|last_60d|last_6mo|last_1yr   (shared with batting/bowling)
 *   ?dist_metric_t_field=catches|run_outs|stumpings
 *
 * Three metric tabs swap histogram + stat strip + chips as a unit.
 * Sparkline + form-delta + splits row stay across tabs; sparkline
 * value & color flip per tab. Stumpings tab is ALWAYS rendered at
 * team grain (every senior team has had a keeper) — when zero,
 * chips show 0% and the panel still mounts.
 */

import { useUrlParam } from '../../hooks/useUrlState'
import BarChart from '../charts/BarChart'
import { WISDEN } from '../charts/palette'
import DistributionSparkline, { type SparklinePoint } from '../distribution/DistributionSparkline'
import SeasonTickAxis from '../distribution/SeasonTickAxis'
import { pickTeamFieldingBaseline, type GlobalTeamFieldingBaselines } from '../distribution/globalBaselines'
import {
  buildTeamCatchesHistogramRows,
  buildTeamCount3HistogramRows,
  teamCatchesTier,
  teamCount3Tier,
} from './distributionBins'
import {
  CatchesStatStrip, CatchesChipsRow,
  CountStatStrip, CountChipsRow,
} from './TeamFieldingStatStrips'
import TeamFieldingFormDeltaLine from './TeamFieldingFormDeltaLine'
import TeamFieldingSuggestedSplitsRow from './TeamFieldingSuggestedSplitsRow'
import type {
  TeamFieldingDistribution,
  TeamFieldingDossier,
  TeamFieldingObservation,
} from '../../types'

type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'
type DistMetric = 'catches' | 'run_outs' | 'stumpings'

const WINDOW_OPTIONS: { key: DistWindow; label: string; param: string; tooltip: string }[] = [
  { key: 'scope',    label: 'Scope',    param: '',
    tooltip: 'All team innings under the active filter scope.' },
  { key: 'last_10',  label: 'Last 10',  param: 'last_10',
    tooltip: 'Most recent 10 team innings.' },
  { key: 'last_60d', label: 'Last 60d', param: 'last_60d',
    tooltip: 'Innings in the last 60 days — current form.' },
  { key: 'last_6mo', label: 'Last 6mo', param: 'last_6mo',
    tooltip: 'Innings in the last 180 days — medium-term arc.' },
  { key: 'last_1yr', label: 'Last 1y',  param: 'last_1yr',
    tooltip: 'Innings in the last 365 days — annual gauge.' },
]

const METRIC_OPTIONS: { key: DistMetric; label: string; param: string; tooltip: string }[] = [
  { key: 'catches',   label: 'Catches',   param: '',
    tooltip: 'Per-innings catches distribution + 0/≥3/≥5/≥7 milestones. Substitutes excluded.' },
  { key: 'run_outs',  label: 'Run-outs',  param: 'run_outs',
    tooltip: 'Per-innings run-outs distribution + 0/1/≥2 partition.' },
  { key: 'stumpings', label: 'Stumpings', param: 'stumpings',
    tooltip: 'Per-innings stumpings distribution. Always shown at team grain.' },
]

const VALID_WINDOWS: ReadonlyArray<DistWindow> = ['last_10', 'last_60d', 'last_6mo', 'last_1yr']
const VALID_METRICS: ReadonlyArray<DistMetric> = ['run_outs', 'stumpings']

// 3-tier polarity-aware palette per CLAUDE.md "Distribution-panel
// color discipline (3-tier palette)". All three fielding tabs use
// the OUTCOME-ASCENDING tinting — fielding events are good for the
// fielding side.
const C_INDIGO = '#7090A8'
const C_SAGE   = '#7A8E6A'
const C_OCHRE  = WISDEN.ochre
const COLOR_SCHEME = [C_INDIGO, C_SAGE, C_OCHRE]

function tierColor(tier: 'low' | 'mid' | 'high'): string {
  return tier === 'low' ? C_INDIGO : tier === 'mid' ? C_SAGE : C_OCHRE
}

function pickDossier(dist: TeamFieldingDistribution, window: DistWindow): TeamFieldingDossier {
  if (window === 'last_10') return dist.form.last_10
  if (window === 'last_60d') return dist.form.last_60d
  if (window === 'last_6mo') return dist.form.last_6mo
  if (window === 'last_1yr') return dist.form.last_1yr
  return dist.lifetime
}

interface SparklineConfig {
  point: (o: TeamFieldingObservation) => SparklinePoint
  /** Player line — scope-baseline mean (this team's lifetime in scope). */
  playerReferenceValue: number | null
  /** Global line — gender-tiered all-team centre. */
  globalReferenceValue: number
  caption: string
  globalLegend: string
}

function sparklineFor(
  metric: DistMetric,
  scopeLifetime: TeamFieldingDossier,
  globals: GlobalTeamFieldingBaselines,
): SparklineConfig {
  if (metric === 'run_outs') {
    return {
      point: (o) => {
        const tier = teamCount3Tier(o.run_outs === 0 ? 0 : o.run_outs === 1 ? 1 : 2)
        return {
          date: o.date, matchId: o.match_id, value: o.run_outs,
          tooltip: `${o.date} · ${o.run_outs} run-out${o.run_outs === 1 ? '' : 's'}`,
          color: tierColor(tier),
          opacity: tier === 'low' ? 1.0 : undefined,
        }
      },
      playerReferenceValue: scopeLifetime.run_outs.mean_per_innings,
      globalReferenceValue: globals.run_outs,
      caption: 'oldest ← bars (one per innings, height = run-outs) → most recent',
      globalLegend: `${globals.run_outs} run-out/inn`,
    }
  }
  if (metric === 'stumpings') {
    return {
      point: (o) => {
        const tier = teamCount3Tier(o.stumpings === 0 ? 0 : o.stumpings === 1 ? 1 : 2)
        return {
          date: o.date, matchId: o.match_id, value: o.stumpings,
          tooltip: `${o.date} · ${o.stumpings} stumping${o.stumpings === 1 ? '' : 's'}`,
          color: tierColor(tier),
          opacity: tier === 'low' ? 1.0 : undefined,
        }
      },
      playerReferenceValue: scopeLifetime.stumpings.mean_per_innings,
      // Stumpings global rounds to 0 (~0.2/innings empirically); fall
      // back to the scope baseline when the global doesn't anchor a
      // visible line.
      globalReferenceValue: globals.stumpings,
      caption: 'oldest ← bars (one per innings, height = stumpings) → most recent',
      globalLegend: `${globals.stumpings} stumping/inn (≈0.2 actual)`,
    }
  }
  return {
    point: o => {
      const tier = teamCatchesTier(o.catches)
      // Tooltip enrichment per spec §17.5 — "X catches of Y wickets".
      const ofWkts = o.wickets_total > 0 ? ` of ${o.wickets_total} wickets` : ''
      return {
        date: o.date, matchId: o.match_id, value: o.catches,
        tooltip: `${o.date} · ${o.catches} catch${o.catches === 1 ? '' : 'es'}${ofWkts}`,
        color: tierColor(tier),
        opacity: tier === 'low' ? 1.0 : undefined,
      }
    },
    playerReferenceValue: scopeLifetime.catches.mean_per_innings,
    globalReferenceValue: globals.catches,
    caption: 'oldest ← bars (one per innings, height = catches) → most recent',
    globalLegend: `${globals.catches} catches/inn`,
  }
}

/** Tiny inline legend explaining the reference lines + rolling mean.
 *  Mirrors TeamBattingDistributionPanel's SparklineLegend. */
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
  team: string
  distribution: TeamFieldingDistribution | null
  loading: boolean
  error: string | null
}

export default function TeamFieldingDistributionPanel({
  team, distribution, loading, error,
}: Props) {
  const [windowParam, setWindowParam] = useUrlParam('dist_window_t')
  const [metricParam, setMetricParam] = useUrlParam('dist_metric_t_field')

  const window: DistWindow = (VALID_WINDOWS as ReadonlyArray<string>).includes(windowParam)
    ? (windowParam as DistWindow)
    : 'scope'
  const metric: DistMetric = (VALID_METRICS as ReadonlyArray<string>).includes(metricParam)
    ? (metricParam as DistMetric)
    : 'catches'

  if (loading || error || !distribution) return null

  const dossier = pickDossier(distribution, window)
  const lifetimeEmpty = distribution.lifetime.n_innings_fielded === 0
  const windowEmpty = dossier.n_innings_fielded === 0

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
      aria-label="Per-innings team fielding distribution"
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
          fontFamily: 'var(--serif)',
          fontStyle: 'italic',
          fontSize: '0.78rem',
          color: 'var(--ink-faint)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}>
          Per-innings team fielding distribution
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
          No team innings under this filter — try widening the scope.
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
            No team innings in {windowLabel(window)} under this filter.
          </div>
          <TeamFieldingFormDeltaLine dossier={distribution} />
        </>
      ) : (
        <>
          <div className="wisden-dist-grid">
            {metric === 'catches' && (
              <>
                <BarChart
                  data={buildTeamCatchesHistogramRows(dossier.observations)}
                  categoryAccessor="label"
                  valueAccessor="count"
                  colorBy="tier"
                  colorScheme={COLOR_SCHEME}
                  categoryLabel="Catches in innings"
                  valueLabel="Innings"
                  height={220}
                />
                <CatchesStatStrip
                  block={dossier.catches}
                  n_innings_fielded={dossier.n_innings_fielded}
                  substitute_catches={dossier.substitute_catches}
                />
              </>
            )}
            {metric === 'run_outs' && (
              <>
                <BarChart
                  data={buildTeamCount3HistogramRows(dossier.observations.map(o => ({ value: o.run_outs })))}
                  categoryAccessor="label"
                  valueAccessor="count"
                  colorBy="tier"
                  colorScheme={COLOR_SCHEME}
                  categoryLabel="Run-outs in innings"
                  valueLabel="Innings"
                  height={220}
                />
                <CountStatStrip
                  block={dossier.run_outs}
                  n_innings_fielded={dossier.n_innings_fielded}
                  noun="Run-out"
                />
              </>
            )}
            {metric === 'stumpings' && (
              <>
                <BarChart
                  data={buildTeamCount3HistogramRows(dossier.observations.map(o => ({ value: o.stumpings })))}
                  categoryAccessor="label"
                  valueAccessor="count"
                  colorBy="tier"
                  colorScheme={COLOR_SCHEME}
                  categoryLabel="Stumpings in innings"
                  valueLabel="Innings"
                  height={220}
                />
                <CountStatStrip
                  block={dossier.stumpings}
                  n_innings_fielded={dossier.n_innings_fielded}
                  noun="Stumping"
                />
              </>
            )}
          </div>
          {metric === 'catches'   && <CatchesChipsRow block={dossier.catches} />}
          {metric === 'run_outs'  && <CountChipsRow block={dossier.run_outs} />}
          {metric === 'stumpings' && <CountChipsRow block={dossier.stumpings} />}

          <div style={{ marginTop: '0.75rem' }}>
            {(() => {
              const globals = pickTeamFieldingBaseline(distribution.scope)
              const cfg = sparklineFor(metric, distribution.lifetime, globals)
              const points = dossier.observations.map(o => cfg.point(o))
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
                  <SeasonTickAxis dates={dossier.observations.map(o => o.date)} />
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

          <TeamFieldingFormDeltaLine dossier={distribution} />
        </>
      )}

      <TeamFieldingSuggestedSplitsRow team={team} splits={distribution.suggested_splits} />
    </section>
  )
}
