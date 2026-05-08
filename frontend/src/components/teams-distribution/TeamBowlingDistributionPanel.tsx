/**
 * Team-bowling Distribution panel — top-level orchestrator for the
 * §17.4 frontend slice. Spec:
 * internal_docs/spec-distribution-stats.md §17.4.
 *
 * Mounted at the top of the Teams page Bowling tab content area
 * (see Teams.tsx).
 *
 * URL state — both keys default to absent param (canonical default
 * encoded by absence; share-link reproducibility):
 *   ?dist_window_t=scope|last_10|last_60d|last_6mo|last_1yr   (shared with batting tab)
 *   ?dist_metric_t_bowl=wickets|runs_conceded|economy
 *
 * Three metric tabs swap histogram + stat strip + chips as a unit.
 * Sparkline + form-delta + splits row are window-dependent /
 * metric-aware (sparkline value & color flip per tab) per spec §17.4.
 */

import { useUrlParam } from '../../hooks/useUrlState'
import BarChart from '../charts/BarChart'
import { WISDEN } from '../charts/palette'
import DistributionSparkline, { type SparklinePoint } from '../distribution/DistributionSparkline'
import SeasonTickAxis from '../distribution/SeasonTickAxis'
import { pickTeamBowlingBaseline, type GlobalTeamBowlingBaselines } from '../distribution/globalBaselines'
import {
  buildTeamWicketsHistogramRows,
  buildTeamRunsConcededHistogramRows,
  buildTeamConcedeRPOHistogramRows,
  teamWicketsTier,
  teamRunsConcededTier,
  teamConcedeRPOTier,
} from './distributionBins'
import {
  WicketsStatStrip, WicketsChipsRow,
  RunsConcededStatStrip, RunsConcededChipsRow,
  EconomyStatStrip, EconomyChipsRow,
} from './TeamBowlingStatStrips'
import TeamBowlingFormDeltaLine from './TeamBowlingFormDeltaLine'
import TeamBowlingSuggestedSplitsRow from './TeamBowlingSuggestedSplitsRow'
import type {
  TeamBowlingDistribution,
  TeamBowlingDossier,
  TeamBowlingInningsObservation,
} from '../../types'

type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'
type DistMetric = 'wickets' | 'runs_conceded' | 'economy'

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
  { key: 'wickets',       label: 'Wickets',       param: '',
    tooltip: 'Per-innings wickets distribution + ≤3/≥5/≥7/=10 milestones + early-breakthrough at over 10.' },
  { key: 'runs_conceded', label: 'Runs Conceded', param: 'runs_conceded',
    tooltip: 'Per-innings runs conceded + 100/150/200/230 ladder + opposition doubling-at-10 leakage.' },
  { key: 'economy',       label: 'Economy',       param: 'economy',
    tooltip: 'Per-innings RPO distribution + ≤6/≤7/≥9/≥10 thresholds.' },
]

const VALID_WINDOWS: ReadonlyArray<DistWindow> = ['last_10', 'last_60d', 'last_6mo', 'last_1yr']
const VALID_METRICS: ReadonlyArray<DistMetric> = ['runs_conceded', 'economy']

// 3-tier polarity-aware palette per CLAUDE.md "Distribution-panel
// color discipline (3-tier palette)". Bin-index ordering is always
// low→mid→high (left-to-right on the histogram); the tier-to-color
// mapping flips per metric to track the OUTCOME polarity:
//   Wickets       — high wkts is good for the bowler → high=ochre
//   Runs Conceded — low conceded is good for the bowler → low=ochre (FLIPPED)
//   Economy       — low RPO is good for the bowler → low=ochre (FLIPPED)
const C_INDIGO = '#7090A8'
const C_SAGE   = '#7A8E6A'
const C_OCHRE  = WISDEN.ochre
const COLOR_SCHEME_WICKETS  = [C_INDIGO, C_SAGE, C_OCHRE]  // low/mid/high → poor/typical/strong
const COLOR_SCHEME_FLIPPED  = [C_OCHRE,  C_SAGE, C_INDIGO] // low/mid/high → strong/typical/poor (runs_conceded + economy)

function tierColor(metric: DistMetric, tier: 'low' | 'mid' | 'high'): string {
  const idx = tier === 'low' ? 0 : tier === 'mid' ? 1 : 2
  return metric === 'wickets' ? COLOR_SCHEME_WICKETS[idx] : COLOR_SCHEME_FLIPPED[idx]
}

function pickDossier(dist: TeamBowlingDistribution, window: DistWindow): TeamBowlingDossier {
  if (window === 'last_10') return dist.form.last_10
  if (window === 'last_60d') return dist.form.last_60d
  if (window === 'last_6mo') return dist.form.last_6mo
  if (window === 'last_1yr') return dist.form.last_1yr
  return dist.lifetime
}

interface SparklineConfig {
  point: (o: TeamBowlingInningsObservation, rpo?: number) => SparklinePoint
  /** Player line — scope-baseline mean (this team's lifetime in scope). */
  playerReferenceValue: number | null
  /** Global line — gender-tiered all-team centre. */
  globalReferenceValue: number
  caption: string
  globalLegend: string
}

function fmt2(v: number): string { return v.toFixed(2) }

function sparklineFor(
  metric: DistMetric,
  scopeLifetime: TeamBowlingDossier,
  globals: GlobalTeamBowlingBaselines,
): SparklineConfig {
  if (metric === 'runs_conceded') {
    return {
      point: (o) => {
        const tier = teamRunsConcededTier(o.runs_conceded)
        return {
          date: o.date, matchId: o.match_id, value: o.runs_conceded,
          tooltip: `${o.date} · conceded ${o.runs_conceded}/${o.wickets} (${o.balls}b)`,
          color: tierColor('runs_conceded', tier),
          // High-tier (heavy leakage) is INDIGO at this metric → fully
          // opaque. INDIGO bars wash out worst at 0.8 across the
          // distribution palette.
          opacity: tier === 'high' ? 1.0 : undefined,
        }
      },
      playerReferenceValue: scopeLifetime.runs_conceded.mean_per_innings,
      globalReferenceValue: globals.runs,
      caption: 'oldest ← bars (one per innings, height = runs conceded) → most recent',
      globalLegend: `${globals.runs} runs/inn`,
    }
  }
  if (metric === 'economy') {
    return {
      point: (o, rpo) => {
        const v = rpo ?? (o.balls > 0 ? +(o.runs_conceded * 6 / o.balls).toFixed(2) : 0)
        const tier = teamConcedeRPOTier(v)
        return {
          date: o.date, matchId: o.match_id, value: v,
          tooltip: `${o.date} · econ ${fmt2(v)} (${o.runs_conceded}/${o.wickets} in ${o.balls}b)`,
          color: tierColor('economy', tier),
          // High RPO → INDIGO → fully opaque.
          opacity: tier === 'high' ? 1.0 : undefined,
        }
      },
      playerReferenceValue: scopeLifetime.economy.pool,
      globalReferenceValue: globals.rpo,
      caption: 'oldest ← bars (one per innings, height = RPO) → most recent',
      globalLegend: `${globals.rpo} RPO`,
    }
  }
  return {
    point: o => {
      const tier = teamWicketsTier(o.wickets)
      return {
        date: o.date, matchId: o.match_id, value: o.wickets,
        tooltip: `${o.date} · ${o.wickets}/${o.runs_conceded} (${o.balls}b)`,
        color: tierColor('wickets', tier),
        // Low-tier (few wickets) is INDIGO → fully opaque.
        opacity: tier === 'low' ? 1.0 : undefined,
      }
    },
    playerReferenceValue: scopeLifetime.wickets.mean_per_innings,
    globalReferenceValue: globals.wickets,
    caption: 'oldest ← bars (one per innings, height = wickets) → most recent',
    globalLegend: `${globals.wickets} wkts/inn`,
  }
}

/** Tiny inline legend explaining the reference lines + rolling mean.
 *  Mirrors TeamBattingDistributionPanel's SparklineLegend. */
function SparklineLegend({ globalLegend, leagueLegend, showRolling }: {
  globalLegend: string
  leagueLegend: string | null
  showRolling: boolean
}) {
  // Swatch alignment pattern per commit b770918 — see
  // TeamBattingDistributionPanel comment for rationale.
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
      <span><Swatch color="#1A1714" h={2} />scope average</span>
      {leagueLegend && (
        <span><Swatch color="#3F7A4D" h={1.5} />{leagueLegend}</span>
      )}
      <span><Swatch color="#8A7D70" h={1.5} />gender-global ({globalLegend})</span>
      {showRolling && (
        <span><Swatch color="#7A1F1F" h={1.5} />rolling-10 mean</span>
      )}
    </span>
  )
}

interface Props {
  team: string
  distribution: TeamBowlingDistribution | null
  loading: boolean
  error: string | null
  /** Same-scope league averages from the existing /summary envelope.
   *  - `wickets` ← `summary.wickets.scope_avg` (per-innings).
   *  - `runsConceded` ← `summary.runs_conceded.scope_avg`.
   *  - `economy` ← `summary.economy.scope_avg`. */
  leagueAvg?: { wickets: number | null; runsConceded: number | null; economy: number | null }
}

export default function TeamBowlingDistributionPanel({
  team, distribution, loading, error, leagueAvg,
}: Props) {
  const [windowParam, setWindowParam] = useUrlParam('dist_window_t')
  const [metricParam, setMetricParam] = useUrlParam('dist_metric_t_bowl')

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

  function windowLabel(w: DistWindow): string {
    return WINDOW_OPTIONS.find(o => o.key === w)?.label ?? 'this window'
  }

  // Per-innings RPO list aligned with wickets.observations — built
  // once for the histogram + sparkline so they share the same values.
  const rpoPerInnings = dossier.economy.per_innings

  return (
    <section
      className="wisden-statrow"
      style={{
        display: 'block',
        padding: '1.25rem 0.5rem 0.75rem',
        borderTop: '1px solid var(--rule)',
        borderBottom: '1px solid var(--rule)',
      }}
      aria-label="Per-innings team bowling distribution"
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
          Per-innings team bowling distribution
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
          <TeamBowlingFormDeltaLine dossier={distribution} />
        </>
      ) : (
        <>
          <div className="wisden-dist-grid">
            {metric === 'wickets' && (
              <>
                <BarChart
                  data={buildTeamWicketsHistogramRows(dossier.wickets.observations)}
                  categoryAccessor="label"
                  valueAccessor="count"
                  colorBy="tier"
                  colorScheme={COLOR_SCHEME_WICKETS}
                  categoryLabel="Wickets in innings"
                  valueLabel="Innings"
                  height={220}
                />
                <WicketsStatStrip
                  block={dossier.wickets}
                  runs_conceded_total={dossier.runs_conceded.total}
                  economy_pool={dossier.economy.pool}
                  n_innings={dossier.n_innings}
                />
              </>
            )}
            {metric === 'runs_conceded' && (
              <>
                <BarChart
                  data={buildTeamRunsConcededHistogramRows(dossier.wickets.observations)}
                  categoryAccessor="label"
                  valueAccessor="count"
                  colorBy="tier"
                  colorScheme={COLOR_SCHEME_FLIPPED}
                  categoryLabel="Runs conceded"
                  valueLabel="Innings"
                  height={220}
                />
                <RunsConcededStatStrip block={dossier.runs_conceded} n_innings={dossier.n_innings} />
              </>
            )}
            {metric === 'economy' && (
              <>
                <BarChart
                  data={buildTeamConcedeRPOHistogramRows(rpoPerInnings)}
                  categoryAccessor="label"
                  valueAccessor="count"
                  colorBy="tier"
                  colorScheme={COLOR_SCHEME_FLIPPED}
                  categoryLabel="RPO in innings"
                  valueLabel="Innings"
                  height={220}
                />
                <EconomyStatStrip block={dossier.economy} n_innings={dossier.n_innings} />
              </>
            )}
          </div>
          {metric === 'wickets'       && <WicketsChipsRow       block={dossier.wickets} />}
          {metric === 'runs_conceded' && <RunsConcededChipsRow  block={dossier.runs_conceded} />}
          {metric === 'economy'       && <EconomyChipsRow       block={dossier.economy} />}

          <div style={{ marginTop: '0.75rem' }}>
            {(() => {
              const globals = pickTeamBowlingBaseline(distribution.scope)
              const cfg = sparklineFor(metric, distribution.lifetime, globals)
              const points = dossier.wickets.observations.map((o, i) =>
                cfg.point(o, metric === 'economy' ? rpoPerInnings[i] : undefined),
              )
              // Rolling-mean overlay only on the widest window (Scope)
              // where smoothing reads as form-arc rather than noise;
              // skipped on Last 10 / 60d / 6mo / 1y (samples too short).
              const showRolling = window === 'scope' && points.length >= 10
              const league = metric === 'runs_conceded'
                ? leagueAvg?.runsConceded ?? null
                : metric === 'economy'
                  ? leagueAvg?.economy ?? null
                  : leagueAvg?.wickets ?? null
              const leagueLegend = league !== null
                ? (metric === 'runs_conceded'
                    ? `league avg ${league.toFixed(1)} runs/inn`
                    : metric === 'economy'
                      ? `league avg ${league.toFixed(2)} RPO`
                      : `league avg ${league.toFixed(2)} wkts/inn`)
                : null
              return (
                <>
                  <DistributionSparkline
                    points={points}
                    playerReferenceValue={cfg.playerReferenceValue}
                    globalReferenceValue={cfg.globalReferenceValue}
                    leagueReferenceValue={league}
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
                    <SparklineLegend
                      globalLegend={cfg.globalLegend}
                      leagueLegend={leagueLegend}
                      showRolling={showRolling}
                    />
                  </div>
                </>
              )
            })()}
          </div>

          <TeamBowlingFormDeltaLine dossier={distribution} />
        </>
      )}

      <TeamBowlingSuggestedSplitsRow team={team} splits={distribution.suggested_splits} />
    </section>
  )
}
