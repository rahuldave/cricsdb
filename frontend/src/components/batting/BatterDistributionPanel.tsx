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
 *   - Dual reference lines: black scope average + gray gender-
 *     global anchor (BATTING_GLOBAL_* in distribution/globalBaselines).
 *   - Rolling-N mean overlay (oxblood/red) on the Scope window
 *     when n ≥ N. Player-grain N = 5 (smaller window keeps recent
 *     swings visible; one bad innings is the floor).
 */

import { useUrlParam } from '../../hooks/useUrlState'
import RunsHistogram from './RunsHistogram'
import SRHistogram from './SRHistogram'
import DistributionStatStrip, { MilestoneChipsRow } from './DistributionStatStrip'
import DistributionSparkline, { type SparklinePoint } from '../distribution/DistributionSparkline'
import SeasonTickAxis from '../distribution/SeasonTickAxis'
import ScrollableBars from '../distribution/ScrollableBars'
import { pickBattingBaseline, type GlobalBattingBaselines } from '../distribution/globalBaselines'
import { binIndex, binTier, srBinIndex, srBinTier } from './distributionBins'
import { WISDEN_RUN_TIERS, WISDEN_SR_TIERS } from '../charts/palette'
import FormDeltaLine from './FormDeltaLine'
import SuggestedSplitsRow from './SuggestedSplitsRow'
import type { BatterDistribution, BattingSummary, DistributionDossier, InningsObservation } from '../../types'

import { KickerHeader } from '../ChartHeader'
type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'
type DistMetric = 'runs' | 'sr'

// Rolling-mean overlay window for the Scope tab. Player-grain
// batting = 5: one duck swings the mean by ~runs/5, which the eye
// can still attribute to one innings rather than smoothing it
// away. Window = 10 oversmoothed visible IPL-scope swings (user
// feedback 2026-05-14). See internal_docs/colors.md "Rolling-mean
// windows by grain" for the per-panel table.
const ROLLING_WINDOW = 5

const WINDOW_OPTIONS: { key: DistWindow; label: string; param: string; tooltip: string }[] = [
  { key: 'scope',    label: 'At scope', param: '',
    tooltip: 'All innings under the active filter scope.' },
  { key: 'last_10',  label: 'Last 10',  param: 'last_10',
    tooltip: 'Most recent 10 innings within the active filter scope.' },
  { key: 'last_60d', label: 'Last 60d', param: 'last_60d',
    tooltip: 'Innings in the last 60 days within scope — current form.' },
  { key: 'last_6mo', label: 'Last 6mo', param: 'last_6mo',
    tooltip: 'Innings in the last 180 days within scope — medium-term arc.' },
  { key: 'last_1yr', label: 'Last 1y',  param: 'last_1yr',
    tooltip: 'Innings in the last 365 days within scope — annual / loss-of-form gauge.' },
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
  /** Same-scope cohort baseline (Tier 6 of spec-apples-to-apples-
   *  baselines.md). Forest green line. Sourced from /batters/{id}/
   *  summary's per-innings envelope scope_avg — position-weighted
   *  via Tier 1. Null when chip is below-cliff. */
  leagueReferenceValue: number | null
  caption: string
  globalLegend: string
  /** Short label for the green line in the sparkline legend
   *  ("xx.x runs/inn"). Matches the chip's scope_avg display. */
  leagueLegend: string | null
}

function sparklineFor(
  metric: DistMetric,
  scopeLifetime: DistributionDossier,
  globals: GlobalBattingBaselines,
  summary: BattingSummary | null,
): SparklineConfig {
  if (metric === 'sr') {
    // Career SR: server-computed (audit §4.1) on lifetime.runs.
    const playerSR = scopeLifetime.runs.strike_rate
    const leagueSR = summary?.strike_rate?.scope_avg ?? null
    return {
      point: o => {
        // Per-innings SR: server-computed (audit §4.5) on each observation;
        // null only when balls=0 (no balls faced — fall back to 0 for binning).
        const sr = o.strike_rate ?? 0
        const tier = srBinTier(srBinIndex(sr))
        return {
          date: o.date, matchId: o.match_id, value: sr,
          tooltip: `${o.date} · SR ${sr.toFixed(1)} (${o.runs}r in ${o.balls}b${o.dismissed ? '' : '*'})`,
          color: WISDEN_SR_TIERS[tier],
          // Indigo bars (slow) wash out at 0.8; full opacity.
          opacity: tier === 'slow' ? 1.0 : undefined,
        }
      },
      playerReferenceValue: playerSR,
      globalReferenceValue: globals.sr,
      leagueReferenceValue: leagueSR,
      caption: 'oldest ← bars (one per innings, height = SR) → most recent',
      globalLegend: `${globals.sr} SR`,
      leagueLegend: leagueSR != null ? `${leagueSR.toFixed(1)} SR` : null,
    }
  }
  const leagueRuns = summary?.runs_per_innings?.scope_avg ?? null
  return {
    point: o => {
      const tier = binTier(binIndex(o.runs))
      return {
        date: o.date, matchId: o.match_id, value: o.runs,
        tooltip: `${o.date} · ${o.runs}r (${o.balls}b${o.dismissed ? '' : '*'})`,
        color: WISDEN_RUN_TIERS[tier],
        // Indigo bars (failure) wash out at 0.8; full opacity.
        opacity: tier === 'failure' ? 1.0 : undefined,
      }
    },
    playerReferenceValue: scopeLifetime.runs.mean_per_innings,
    globalReferenceValue: globals.runs,
    leagueReferenceValue: leagueRuns,
    caption: 'oldest ← bars (one per innings, height = runs) → most recent',
    globalLegend: `${globals.runs} runs/inn`,
    leagueLegend: leagueRuns != null ? `${leagueRuns.toFixed(1)} runs/inn` : null,
  }
}

/** Pure stat strip for the SR tab — computed client-side from
 *  the runs observations (no SR-specific dossier in the API yet). */
function SRStatStrip({ dossier }: { dossier: DistributionDossier }) {
  // Per-innings SR + Career SR both server-computed (audit §4.1 + §4.5).
  // Mean / median / std of per-innings SR are derived from observations
  // here — pure aggregates, no DB-dependent predicates, so client-side
  // is fine.
  const obs = dossier.runs.observations
  const srs = obs
    .filter((o): o is typeof o & { strike_rate: number } => o.strike_rate !== null)
    .map(o => o.strike_rate)
  if (srs.length === 0) return null
  const sorted = [...srs].sort((a, b) => a - b)
  const median = sorted.length % 2
    ? sorted[(sorted.length - 1) / 2]
    : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
  const mean = srs.reduce((s, x) => s + x, 0) / srs.length
  const poolSR = dossier.runs.strike_rate
  const variance = srs.length >= 2
    ? srs.reduce((s, x) => s + (x - mean) ** 2, 0) / (srs.length - 1)
    : 0
  const std = Math.sqrt(variance)

  function StatRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'baseline', padding: '0.25rem 0',
      }}>
        <span style={{
          fontFamily: 'var(--serif)', fontStyle: 'italic',
          fontSize: '0.78rem', color: 'var(--ink-faint)',
        }}>{label}</span>
        <span className="num" style={{
          fontFamily: 'var(--serif)',
          fontSize: accent ? '1.15rem' : '1rem',
          fontWeight: accent ? 600 : 500,
          color: 'var(--ink)',
        }}>{value}</span>
      </div>
    )
  }
  const fmt = (v: number | null, d = 1) => v === null ? '—' : v.toFixed(d)
  return (
    <div>
      <StatRow label="Career SR" value={fmt(poolSR, 2)} accent />
      <StatRow label="Mean / inn" value={fmt(mean, 1)} />
      <StatRow label="Median / inn" value={fmt(median, 1)} accent />
      <StatRow label="Std" value={fmt(std, 1)} />
      <div style={{
        fontFamily: 'var(--serif)', fontStyle: 'italic',
        fontSize: '0.7rem', color: 'var(--ink-faint)',
        textAlign: 'right', marginTop: '0.25rem',
      }}>
        {srs.length} inns with balls faced
      </div>
    </div>
  )
}

function SparklineLegend({ globalLegend, leagueLegend, rollingWindow }: {
  globalLegend: string;
  leagueLegend: string | null;
  rollingWindow: number | null
}) {
  // Swatch alignment pattern per commit b770918: NO inline-flex
  // wrapper; verticalAlign: middle + position: relative top -0.1em
  // sits the swatch at the optical centre of the text x-height
  // when the surrounding row uses align-items: baseline.
  const Swatch = ({ color, h = 1.5 }: { color: string; h?: number }) => (
    <span aria-hidden="true" style={{
      display: 'inline-block', width: 14, height: h,
      background: color,
      verticalAlign: 'middle',
      marginRight: '0.3rem',
      position: 'relative', top: '-0.1em',
    }} />
  )
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'baseline', flexWrap: 'wrap',
      columnGap: '0.85rem', rowGap: '0.15rem',
      fontFamily: 'var(--serif)', fontStyle: 'italic',
      fontSize: '0.7rem', color: 'var(--ink-faint)',
    }}>
      <span><Swatch color="#1A1714" h={2} />player scope mean</span>
      {leagueLegend !== null && (
        <span><Swatch color="#3F7A4D" />cohort at scope ({leagueLegend})</span>
      )}
      <span><Swatch color="#8A7D70" />all-T20 ({globalLegend})</span>
      {rollingWindow !== null && (
        <span><Swatch color="#7A1F1F" />rolling-{rollingWindow} mean</span>
      )}
    </span>
  )
}

interface Props {
  playerId: string
  distribution: BatterDistribution | null
  /** Tier 6 of spec-apples-to-apples-baselines.md — when present, the
   *  sparkline draws a forest-green reference line at the active-scope
   *  cohort baseline (position-weighted via Tier 1). Sourced from the
   *  /batters/{id}/summary `runs_per_innings.scope_avg` for the runs
   *  tab and `strike_rate.scope_avg` for the SR tab. */
  summary: BattingSummary | null
  loading: boolean
  error: string | null
}

export default function BatterDistributionPanel({
  playerId, distribution, summary, loading, error,
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
        <KickerHeader title="Per-innings runs distribution" />
        <div className="wisden-filter-group">
          {WINDOW_OPTIONS.map((opt, i) => (
            <span key={opt.key} style={{ display: 'inline-flex', alignItems: 'baseline' }}>
              {/* Insert an italic "within scope:" separator between the
                 first ("At scope") button and the windowed slices. */}
              {i === 1 && (
                <span style={{
                  fontFamily: 'var(--serif)', fontStyle: 'italic',
                  fontSize: '0.78rem', color: 'var(--ink-faint)',
                  marginRight: '0.5rem',
                }}>within scope:</span>
              )}
              <button
                type="button"
                className={`wisden-seg${window === opt.key ? ' is-active' : ''}`}
                onClick={() => setWindowParam(opt.param)}
                title={opt.tooltip}
              >{opt.label}</button>
            </span>
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
          {metric === 'runs' && (
            <>
              <div className="wisden-dist-grid">
                <RunsHistogram dossier={dossier} />
                <DistributionStatStrip dossier={dossier} />
              </div>
              <MilestoneChipsRow dossier={dossier} window={window} playerId={playerId} />
            </>
          )}
          {metric === 'sr' && (
            <div className="wisden-dist-grid">
              <SRHistogram observations={dossier.runs.observations} />
              <SRStatStrip dossier={dossier} />
            </div>
          )}

          <div style={{ marginTop: '0.75rem' }}>
            {(() => {
              const globals = pickBattingBaseline(distribution.scope)
              const cfg = sparklineFor(metric, distribution.lifetime, globals, summary)
              const points = dossier.runs.observations.map(cfg.point)
              const showRolling = window === 'scope' && points.length >= ROLLING_WINDOW
              return (
                <>
                  <ScrollableBars count={points.length}>
                    <DistributionSparkline
                      points={points}
                      playerReferenceValue={cfg.playerReferenceValue}
                      globalReferenceValue={cfg.globalReferenceValue}
                      leagueReferenceValue={cfg.leagueReferenceValue}
                      rollingWindow={showRolling ? ROLLING_WINDOW : undefined}
                    />
                    <SeasonTickAxis dates={dossier.runs.observations.map(o => o.date)} />
                  </ScrollableBars>
                  <div style={{
                    display: 'flex', flexWrap: 'wrap', alignItems: 'baseline',
                    columnGap: '0.85rem', rowGap: '0.15rem',
                    marginTop: '0.1rem',
                    fontFamily: 'var(--serif)', fontStyle: 'italic',
                    fontSize: '0.7rem', color: 'var(--ink-faint)',
                  }}>
                    <span>{cfg.caption}</span>
                    <SparklineLegend
                      globalLegend={cfg.globalLegend}
                      leagueLegend={cfg.leagueLegend}
                      rollingWindow={showRolling ? ROLLING_WINDOW : null}
                    />
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
