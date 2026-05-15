/**
 * Team-batting Distribution panel — top-level orchestrator for the
 * §17 frontend slice. Spec: internal_docs/spec-distribution-stats.md
 * §17.3.
 *
 * Mounted at the top of the Teams page Batting tab content area
 * (see Teams.tsx).
 *
 * URL state — both keys default to absent param (canonical default
 * encoded by absence; share-link reproducibility):
 *   ?dist_window_t=scope|last_10|last_60d|last_6mo|last_1yr
 *   ?dist_metric_t_bat=runs|run_rate
 *
 * The `_t` suffix prevents collision with the player-page panel's
 * `dist_window` / `dist_metric` keys when navigating between
 * /batting?player= and /teams?team=.
 *
 * Two metric tabs (Runs / Run Rate) — narrower than the bowler
 * panel's three tabs. Window toggle redraws histogram + stat strip
 * + chips for the active metric tab. Sparkline + form-delta +
 * splits row are window-dependent / window-independent per spec
 * §17.3.
 */

import { useUrlParam } from '../../hooks/useUrlState'
import BarChart from '../charts/BarChart'
import { WISDEN } from '../charts/palette'
import DistributionSparkline, { type SparklinePoint } from '../distribution/DistributionSparkline'
import SeasonTickAxis from '../distribution/SeasonTickAxis'
import ScrollableBars from '../distribution/ScrollableBars'
import { pickTeamBattingBaseline, type GlobalTeamBattingBaselines } from '../distribution/globalBaselines'
import {
  buildTeamRunsHistogramRows,
  buildTeamRunRateHistogramRows,
  teamRunsTier,
  teamRRTier,
  type TeamRunsBinTier,
  type TeamRRBinTier,
} from './distributionBins'
import { RunsStatStrip, RunsChipsRow, RRStatStrip, RRChipsRow } from './TeamBattingStatStrips'
import TeamBattingFormDeltaLine from './TeamBattingFormDeltaLine'
import TeamBattingSuggestedSplitsRow from './TeamBattingSuggestedSplitsRow'
import { KickerHeader } from '../ChartHeader'
import type {
  TeamBattingDistribution,
  TeamBattingDossier,
  TeamBattingInningsObservation,
} from '../../types'

type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'
type DistMetric = 'runs' | 'run_rate'

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
  { key: 'runs',     label: 'Runs',     param: '',
    tooltip: 'Per-innings runs distribution + 100/150/200/230 milestone ladder + doubling-at-10 escalation.' },
  { key: 'run_rate', label: 'Run Rate', param: 'run_rate',
    tooltip: 'Per-innings RR distribution + RR-threshold milestones.' },
]

const VALID_WINDOWS: ReadonlyArray<DistWindow> = ['last_10', 'last_60d', 'last_6mo', 'last_1yr']

// Rolling-mean overlay window for the Scope tab. Team-grain
// batting = 7: spans more than two 3-game bilaterals, sits under
// the World Cup ceiling so the overlay still draws in tournament
// scopes. Lower per-innings variance than player-grain (team
// total is a sum) so 7 smooths reliably without staleness.
// See internal_docs/colors.md "Rolling-mean windows by grain".
const ROLLING_WINDOW = 7
const VALID_METRICS: ReadonlyArray<DistMetric> = ['run_rate']

// 3-tier polarity-aware palette per CLAUDE.md "Distribution-panel
// color discipline (3-tier palette)". Both Runs and RR use the
// same colorScheme array because the polarity is encoded in the
// bin-tier helper (low/mid/high → INDIGO/SAGE/OCHRE in both cases).
const TIER_TO_COLOR: Record<TeamRunsBinTier | TeamRRBinTier, string> = {
  low:  '#7090A8',   // indigo — under-baseline outcome
  mid:  '#7A8E6A',   // sage   — typical
  high: WISDEN.ochre, // ochre  — strong outcome
}
const TIER_ORDER: (TeamRunsBinTier | TeamRRBinTier)[] = ['low', 'mid', 'high']
const COLOR_SCHEME = TIER_ORDER.map(t => TIER_TO_COLOR[t])

function pickDossier(dist: TeamBattingDistribution, window: DistWindow): TeamBattingDossier {
  if (window === 'last_10') return dist.form.last_10
  if (window === 'last_60d') return dist.form.last_60d
  if (window === 'last_6mo') return dist.form.last_6mo
  if (window === 'last_1yr') return dist.form.last_1yr
  return dist.lifetime
}

interface SparklineConfig {
  point: (o: TeamBattingInningsObservation, rr?: number) => SparklinePoint
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
  scopeLifetime: TeamBattingDossier,
  globals: GlobalTeamBattingBaselines,
): SparklineConfig {
  if (metric === 'run_rate') {
    return {
      point: (o, rr) => {
        const v = rr ?? (o.balls > 0 ? +(o.runs * 6 / o.balls).toFixed(2) : 0)
        const tier = teamRRTier(v)
        return {
          date: o.date, matchId: o.match_id, value: v,
          tooltip: `${o.date} · RR ${fmt2(v)} (${o.runs}/${o.wickets} in ${o.balls}b)`,
          color: TIER_TO_COLOR[tier],
          // Indigo bars (slow RR) wash out worst at 0.8; full opacity.
          opacity: tier === 'low' ? 1.0 : undefined,
        }
      },
      playerReferenceValue: scopeLifetime.run_rate.pool,
      globalReferenceValue: globals.rr,
      caption: 'oldest ← bars (one per innings, height = team RR) → most recent',
      globalLegend: `${globals.rr} RPO`,
    }
  }
  return {
    point: o => {
      const tier = teamRunsTier(o.runs)
      return {
        date: o.date, matchId: o.match_id, value: o.runs,
        tooltip: `${o.date} · ${o.runs}/${o.wickets} (${o.balls}b)`,
        color: TIER_TO_COLOR[tier],
        // Indigo bars (under-100) wash out worst at 0.8; full opacity
        // so the "didn't get going" tier stays as visible as the
        // "explosive" tier.
        opacity: tier === 'low' ? 1.0 : undefined,
      }
    },
    playerReferenceValue: scopeLifetime.runs.mean_per_innings,
    globalReferenceValue: globals.runs,
    caption: 'oldest ← bars (one per innings, height = runs) → most recent',
    globalLegend: `${globals.runs} runs/inn`,
  }
}

/** Tiny inline legend explaining the reference lines + rolling mean.
 *  Mirrors BowlerDistributionPanel's SparklineLegend. */
function SparklineLegend({ globalLegend, leagueLegend, rollingWindow }: {
  globalLegend: string
  /** Forest-green league average label, e.g. "league avg 135.9 runs/inn"
   *  for the same scope. Hidden when null. */
  leagueLegend: string | null
  rollingWindow: number | null
}) {
  // Swatch alignment pattern per commit b770918: NO inline-flex
  // wrapper; verticalAlign: middle + position: relative top -0.1em
  // sits the swatch at the optical centre of the text x-height
  // when the surrounding row uses align-items: baseline. Earlier
  // wrapper-based pattern pushed the labels visibly lower than
  // the leading "oldest ←" caption on the same row.
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
      {rollingWindow !== null && (
        <span><Swatch color="#7A1F1F" h={1.5} />rolling-{rollingWindow} mean</span>
      )}
    </span>
  )
}

interface Props {
  team: string
  distribution: TeamBattingDistribution | null
  loading: boolean
  error: string | null
  /** Same-scope league averages for the green reference line on the
   *  sparkline. Sourced from the existing /summary endpoint's
   *  scope_avg envelope (already fetched by the parent BattingTab).
   *  - `runs` → `summary.total_runs.scope_avg` (per-innings).
   *  - `runRate` → `summary.run_rate.scope_avg`. */
  leagueAvg?: { runs: number | null; runRate: number | null }
}

export default function TeamBattingDistributionPanel({
  team, distribution, loading, error, leagueAvg,
}: Props) {
  const [windowParam, setWindowParam] = useUrlParam('dist_window_t')
  const [metricParam, setMetricParam] = useUrlParam('dist_metric_t_bat')

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

  // RR per-innings list aligned with runs.observations — built once
  // for the histogram + sparkline so they share the same per-innings
  // values.
  const rrPerInnings = dossier.run_rate.per_innings

  return (
    <section
      className="wisden-statrow"
      style={{
        display: 'block',
        padding: '1.25rem 0.5rem 0.75rem',
        borderTop: '1px solid var(--rule)',
        borderBottom: '1px solid var(--rule)',
      }}
      aria-label="Per-innings team batting distribution"
    >
      <header style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: '0.5rem',
        marginBottom: '0.5rem',
      }}>
        <KickerHeader title="Per-innings team batting distribution" />
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
          <TeamBattingFormDeltaLine dossier={distribution} />
        </>
      ) : (
        <>
          <div className="wisden-dist-grid">
            {metric === 'runs' && (
              <>
                <BarChart
                  data={buildTeamRunsHistogramRows(dossier.runs.observations)}
                  categoryAccessor="label"
                  valueAccessor="count"
                  colorBy="tier"
                  colorScheme={COLOR_SCHEME}
                  categoryLabel="Runs in innings"
                  valueLabel="Innings"
                  height={220}
                />
                <RunsStatStrip block={dossier.runs} n_innings={dossier.n_innings} />
              </>
            )}
            {metric === 'run_rate' && (
              <>
                <BarChart
                  data={buildTeamRunRateHistogramRows(rrPerInnings)}
                  categoryAccessor="label"
                  valueAccessor="count"
                  colorBy="tier"
                  colorScheme={COLOR_SCHEME}
                  categoryLabel="RPO in innings"
                  valueLabel="Innings"
                  height={220}
                />
                <RRStatStrip block={dossier.run_rate} n_innings={dossier.n_innings} />
              </>
            )}
          </div>
          {metric === 'runs' && <RunsChipsRow block={dossier.runs} />}
          {metric === 'run_rate' && <RRChipsRow block={dossier.run_rate} />}

          <div style={{ marginTop: '0.75rem' }}>
            {(() => {
              const globals = pickTeamBattingBaseline(distribution.scope)
              const cfg = sparklineFor(metric, distribution.lifetime, globals)
              const points = dossier.runs.observations.map((o, i) =>
                cfg.point(o, metric === 'run_rate' ? rrPerInnings[i] : undefined),
              )
              // Rolling-mean overlay only on the widest window (Scope)
              // where smoothing reads as form-arc rather than noise;
              // skipped on Last 10 / 60d / 6mo / 1y (samples too short).
              const showRolling = window === 'scope' && points.length >= ROLLING_WINDOW
              const league = metric === 'run_rate'
                ? leagueAvg?.runRate ?? null
                : leagueAvg?.runs ?? null
              const leagueLegend = league !== null
                ? (metric === 'run_rate'
                    ? `league avg ${league.toFixed(2)} RPO`
                    : `league avg ${league.toFixed(1)} runs/inn`)
                : null
              return (
                <>
                  <ScrollableBars count={points.length}>
                    <DistributionSparkline
                      points={points}
                      playerReferenceValue={cfg.playerReferenceValue}
                      globalReferenceValue={cfg.globalReferenceValue}
                      leagueReferenceValue={league}
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
                      leagueLegend={leagueLegend}
                      rollingWindow={showRolling ? ROLLING_WINDOW : null}
                    />
                  </div>
                </>
              )
            })()}
          </div>

          <TeamBattingFormDeltaLine dossier={distribution} />
        </>
      )}

      <TeamBattingSuggestedSplitsRow team={team} splits={distribution.suggested_splits} />
    </section>
  )
}
