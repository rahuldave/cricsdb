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
import ScrollableBars from '../distribution/ScrollableBars'
import { pickBowlingBaseline, type GlobalBowlingBaselines } from '../distribution/globalBaselines'
import BowlerFormDeltaLine from './BowlerFormDeltaLine'
import BowlerSuggestedSplitsRow from './BowlerSuggestedSplitsRow'
import { WISDEN_WICKET_TIERS, WISDEN_LOWER_TIERS } from '../charts/palette'
import { wicketBin, wicketTier, economyTier, runsConcededTier } from './distributionBins'
import type { BowlerDistribution, BowlerDossier, BowlerInningsObservation, BowlingSummary } from '../../types'

import { KickerHeader } from '../ChartHeader'
type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'
type DistMetric = 'wickets' | 'economy' | 'runs'

const WINDOW_OPTIONS: { key: DistWindow; label: string; param: string; tooltip: string }[] = [
  { key: 'scope',    label: 'At scope', param: '',
    tooltip: 'All qualifying innings under the active filter scope.' },
  { key: 'last_10',  label: 'Last 10',  param: 'last_10',
    tooltip: 'Most recent 10 qualifying innings within scope.' },
  { key: 'last_60d', label: 'Last 60d', param: 'last_60d',
    tooltip: 'Spells in the last 60 days within scope — current form.' },
  { key: 'last_6mo', label: 'Last 6mo', param: 'last_6mo',
    tooltip: 'Spells in the last 180 days within scope — medium-term arc.' },
  { key: 'last_1yr', label: 'Last 1y',  param: 'last_1yr',
    tooltip: 'Spells in the last 365 days within scope — annual gauge.' },
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

// Rolling-mean overlay window for the Scope tab. Player-grain
// bowling = 5: per-spell wickets are very bursty (0/1 modal, 3+
// rare) so smaller window preserves the visual signature of a
// hot streak. Window = 10 oversmoothed visible IPL-scope swings
// (user feedback 2026-05-14). See internal_docs/colors.md
// "Rolling-mean windows by grain".
const ROLLING_WINDOW = 5

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
  /** Tier 6 of spec-apples-to-apples-baselines.md — same-scope cohort
   *  baseline. Forest green. Sourced from /bowlers/{id}/summary's
   *  over-weighted per-innings envelope scope_avg. Null when chip is
   *  below-cliff. */
  leagueReferenceValue: number | null
  caption: string
  /** "8 RPO" / "1 wkts/inn" / "26 runs/inn" — for the legend. */
  globalLegend: string
  /** Short label for the green line in the sparkline legend
   *  ("0.30 wkts/inn"). Matches the chip's scope_avg display. */
  leagueLegend: string | null
}

function sparklineFor(
  metric: DistMetric,
  scopeLifetime: BowlerDossier,
  globals: GlobalBowlingBaselines,
  summary: BowlingSummary | null,
): SparklineConfig {
  if (metric === 'wickets') {
    const leagueWpi = summary?.wickets_per_innings?.scope_avg ?? null
    return {
      point: o => {
        const tier = wicketTier(wicketBin(o.wickets))
        return {
          date: o.date, matchId: o.match_id, value: o.wickets,
          tooltip: `${o.date} · ${o.wickets} wkt${o.wickets === 1 ? '' : 's'} (${o.balls}b, ${o.runs_conceded}r)`,
          color: WISDEN_WICKET_TIERS[tier],
          // Indigo bars (wicketless) wash out at 0.8; full opacity.
          opacity: tier === 'wicketless' ? 1.0 : undefined,
        }
      },
      playerReferenceValue: scopeLifetime.wickets.mean_per_innings,
      globalReferenceValue: globals.wickets,
      leagueReferenceValue: leagueWpi,
      caption: 'oldest ← bars (one per innings, height = wickets) → most recent',
      globalLegend: `${globals.wickets} wkts/inn`,
      leagueLegend: leagueWpi != null ? `${leagueWpi.toFixed(2)} wkts/inn` : null,
    }
  }
  if (metric === 'economy') {
    const leagueEcon = summary?.economy?.scope_avg ?? null
    return {
      point: o => {
        const v = o.balls > 0 ? +(o.runs_conceded * 6 / o.balls).toFixed(2) : 0
        return {
          date: o.date, matchId: o.match_id, value: v,
          tooltip: `${o.date} · econ ${v.toFixed(2)} (${o.runs_conceded}r in ${o.balls}b, ${o.wickets} wkt${o.wickets === 1 ? '' : 's'})`,
          color: WISDEN_LOWER_TIERS[economyTier(v)],
        }
      },
      playerReferenceValue: scopeLifetime.economy.pool,
      globalReferenceValue: globals.rpo,
      leagueReferenceValue: leagueEcon,
      caption: 'oldest ← bars (one per innings, height = econ RPO) → most recent',
      globalLegend: `${globals.rpo} RPO`,
      leagueLegend: leagueEcon != null ? `${leagueEcon.toFixed(2)} RPO` : null,
    }
  }
  // Runs-conceded tab: no first-class /summary scope_avg field for
  // runs_per_spell exists. Approximate from economy.scope_avg × player
  // balls-per-innings (player's own spell-length × cohort run-rate ≈
  // cohort-typical runs conceded under player's deployment). Skipped
  // when player has no innings. The wickets block carries the
  // per-innings observations array (balls populated); use it as the
  // canonical per-spell sample.
  const econSA = summary?.economy?.scope_avg
  const wktsObs = scopeLifetime.wickets.observations
  const playerBallsPerInn = wktsObs.length > 0
    ? wktsObs.reduce((s, o) => s + o.balls, 0) / wktsObs.length
    : null
  const leagueRunsPerSpell = (econSA != null && playerBallsPerInn != null)
    ? +(econSA * playerBallsPerInn / 6).toFixed(1)
    : null
  return {
    point: o => ({
      date: o.date, matchId: o.match_id, value: o.runs_conceded,
      tooltip: `${o.date} · ${o.runs_conceded}r conceded (${o.balls}b, ${o.wickets} wkt${o.wickets === 1 ? '' : 's'})`,
      color: WISDEN_LOWER_TIERS[runsConcededTier(o.runs_conceded)],
    }),
    playerReferenceValue: scopeLifetime.runs_conceded.mean_per_innings,
    globalReferenceValue: globals.runs,
    leagueReferenceValue: leagueRunsPerSpell,
    caption: 'oldest ← bars (one per innings, height = runs conceded) → most recent',
    globalLegend: `${globals.runs} runs/inn`,
    leagueLegend: leagueRunsPerSpell != null
      ? `${leagueRunsPerSpell} r/inn @ player spell length` : null,
  }
}

/** Tiny inline legend explaining the reference lines + rolling mean. */
function SparklineLegend({ globalLegend, leagueLegend, rollingWindow }: {
  globalLegend: string
  leagueLegend: string | null
  rollingWindow: number | null
}) {
  // Swatch alignment pattern per commit b770918 — see
  // BatterDistributionPanel comment for rationale.
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
        <span><Swatch color="#3F7A4D" h={1.5} />cohort at scope ({leagueLegend})</span>
      )}
      <span><Swatch color="#8A7D70" h={1.5} />all-T20 ({globalLegend})</span>
      {rollingWindow !== null && (
        <span><Swatch color="#7A1F1F" h={1.5} />rolling-{rollingWindow} mean</span>
      )}
    </span>
  )
}


interface Props {
  playerId: string
  distribution: BowlerDistribution | null
  /** Tier 6 of spec-apples-to-apples-baselines.md — same-scope cohort
   *  baseline source for the green sparkline reference line. */
  summary: BowlingSummary | null
  loading: boolean
  error: string | null
}

export default function BowlerDistributionPanel({
  playerId, distribution, summary, loading, error,
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
          <KickerHeader title="Per-innings bowling distribution" />
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
          {WINDOW_OPTIONS.map((opt, i) => (
            <span key={opt.key} style={{ display: 'inline-flex', alignItems: 'baseline' }}>
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
          No qualifying innings (≥ {minBalls} balls) under this filter — try
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
            No qualifying innings in {windowLabel(window)} under this filter.
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
          {metric === 'wickets' && <WicketsChipsRow block={dossier.wickets} window={window} playerId={playerId} />}
          {metric === 'economy' && <EconomyChipsRow block={dossier.economy} window={window} playerId={playerId} />}
          {metric === 'runs' && <RunsConcededChipsRow block={dossier.runs_conceded} window={window} playerId={playerId} />}

          <div style={{ marginTop: '0.75rem' }}>
            {(() => {
              const globals = pickBowlingBaseline(distribution.scope)
              const cfg = sparklineFor(metric, distribution.lifetime, globals, summary)
              const points = dossier.wickets.observations.map(cfg.point)
              // Rolling-mean overlay only on the widest window (Scope)
              // where smoothing reads as form-arc rather than noise;
              // skipped on Last 10 / 60d / 6mo / 1y (samples too short).
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
                    <SeasonTickAxis dates={dossier.wickets.observations.map(o => o.date)} />
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

          <BowlerFormDeltaLine dossier={distribution} />
        </>
      )}

      <BowlerSuggestedSplitsRow playerId={playerId} splits={distribution.suggested_splits} />
    </section>
  )
}
