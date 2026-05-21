/**
 * Fielder Distribution panel — top-level orchestrator for the §14
 * frontend slice. Spec: internal_docs/spec-distribution-stats.md §14.
 *
 * Mounted on /fielding?player=X between the count tiles row and the
 * Tabs row.
 *
 * URL state (suffixed `_f` to prevent cross-page bleed with the
 * bowler panel's same param names):
 *   ?dist_window_f=scope|last_10|last_60d|last_6mo|last_1yr
 *   ?dist_metric_f=catches|run_outs|stumpings
 *
 * Window toggle redraws histogram + stat strip + chips for the active
 * metric tab. Metric tab swaps the entire view. The Stumpings tab is
 * conditionally rendered only when `lifetime.innings_kept > 0`.
 */

import { useUrlParam } from '../../hooks/useUrlState'
import CountHistogram from './CountHistogram'
import { FielderStatStrip, FielderChipsRow } from './FielderStatStrip'
import DistributionSparkline, { type SparklinePoint } from '../distribution/DistributionSparkline'
import SeasonTickAxis from '../distribution/SeasonTickAxis'
import ScrollableBars from '../distribution/ScrollableBars'
import FielderFormDeltaLine from './FielderFormDeltaLine'
import FielderSuggestedSplitsRow from './FielderSuggestedSplitsRow'
import { WISDEN } from '../charts/palette'
import { KickerHeader } from '../ChartHeader'
import type {
  FielderDistribution, FielderDossier, FielderObservation, FielderCountBlock,
  FieldingSummary,
} from '../../types'

type DistWindow = 'scope' | 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'
type DistMetric = 'catches' | 'run_outs' | 'stumpings'

const WINDOW_OPTIONS: { key: DistWindow; label: string; param: string; tooltip: string }[] = [
  { key: 'scope',    label: 'Scope',    param: '',
    tooltip: 'All matches under the active filter scope.' },
  { key: 'last_10',  label: 'Last 10',  param: 'last_10',
    tooltip: 'Most recent 10 matches.' },
  { key: 'last_60d', label: 'Last 60d', param: 'last_60d',
    tooltip: 'Matches in the last 60 days — current form.' },
  { key: 'last_6mo', label: 'Last 6mo', param: 'last_6mo',
    tooltip: 'Matches in the last 180 days — medium-term arc.' },
  { key: 'last_1yr', label: 'Last 1y',  param: 'last_1yr',
    tooltip: 'Matches in the last 365 days — annual gauge.' },
]

const METRIC_OPTIONS: { key: DistMetric; label: string; param: string; tooltip: string }[] = [
  { key: 'catches',   label: 'Catches',   param: '',
    tooltip: 'Catches per match — non-substitute, in-scope.' },
  { key: 'run_outs',  label: 'Run-outs',  param: 'run_outs',
    tooltip: 'Run-outs participated in per match.' },
  { key: 'stumpings', label: 'Stumpings', param: 'stumpings',
    tooltip: 'Stumpings per match — keeper-only tab.' },
]

const VALID_WINDOWS: ReadonlyArray<DistWindow> = ['last_10', 'last_60d', 'last_6mo', 'last_1yr']
const VALID_METRICS: ReadonlyArray<DistMetric> = ['run_outs', 'stumpings']

function pickDossier(dist: FielderDistribution, window: DistWindow): FielderDossier {
  if (window === 'last_10') return dist.form.last_10
  if (window === 'last_60d') return dist.form.last_60d
  if (window === 'last_6mo') return dist.form.last_6mo
  if (window === 'last_1yr') return dist.form.last_1yr
  return dist.lifetime
}

function pickBlock(dossier: FielderDossier, metric: DistMetric): FielderCountBlock | null {
  if (metric === 'catches')   return dossier.catches
  if (metric === 'run_outs')  return dossier.run_outs
  return dossier.stumpings
}

const METRIC_LABEL: Record<DistMetric, string> = {
  catches: 'Catches', run_outs: 'Run-outs', stumpings: 'Stumpings',
}

interface Props {
  playerId: string
  distribution: FielderDistribution | null
  /** Tier 6 of spec-apples-to-apples-baselines.md — same-scope cohort
   *  baseline source for the green sparkline reference line. */
  summary: FieldingSummary | null
  loading: boolean
  error: string | null
}

export default function FielderDistributionPanel({
  playerId, distribution, summary, loading, error,
}: Props) {
  const [windowParam, setWindowParam] = useUrlParam('dist_window_f')
  const [metricParam, setMetricParam] = useUrlParam('dist_metric_f')

  const window: DistWindow = (VALID_WINDOWS as ReadonlyArray<string>).includes(windowParam)
    ? (windowParam as DistWindow)
    : 'scope'

  if (loading || error || !distribution) return null

  const isKeeper = distribution.lifetime.innings_kept > 0
  // Metric resolution: validated against URL, but stumpings falls back
  // to catches silently for non-keepers (the tab isn't even rendered).
  let metric: DistMetric = (VALID_METRICS as ReadonlyArray<string>).includes(metricParam)
    ? (metricParam as DistMetric)
    : 'catches'
  if (metric === 'stumpings' && !isKeeper) metric = 'catches'

  const dossier = pickDossier(distribution, window)
  const lifetimeEmpty = distribution.lifetime.n_matches === 0
  const windowEmpty = dossier.n_matches === 0
  const block = pickBlock(dossier, metric)

  const metricLabel = METRIC_LABEL[metric]

  function windowLabel(w: DistWindow): string {
    return WINDOW_OPTIONS.find(o => o.key === w)?.label ?? 'this window'
  }

  // Sparkline reference lines:
  // - Global gray line: y=1 for catches/run_outs (the "did at least
  //   one happen this match?" anchor — bars at or above the line are
  //   1+, bars below are zero stubs); null for stumpings (stumping
  //   means are well below 1/match).
  // - Player black line: player's per-match mean for stumpings; null
  //   for catches/run_outs (the y=1 anchor + green cohort line are the
  //   primary references on these tabs).
  // - Tier 6 (spec-apples-to-apples-baselines.md): green league line
  //   at the active-scope cohort baseline (keeper-binary already
  //   correct) — sourced from /fielders/{id}/summary's per-match
  //   envelope scope_avg.
  const lifetimeStumpings = distribution.lifetime.stumpings
  function sparklineRef(): {
    player: number | null;
    global: number | null;
    league: number | null;
    leagueLegend: string | null;
  } {
    if (metric === 'stumpings') {
      const sa = summary?.stumpings_per_match?.scope_avg ?? null
      return {
        player: lifetimeStumpings?.mean_per_match ?? null,
        global: null,
        league: sa,
        leagueLegend: sa != null ? `${sa.toFixed(2)} stumpings/match` : null,
      }
    }
    if (metric === 'run_outs') {
      const sa = summary?.run_outs_per_match?.scope_avg ?? null
      return {
        player: null,
        global: 1,
        league: sa,
        leagueLegend: sa != null ? `${sa.toFixed(2)} run-outs/match` : null,
      }
    }
    // catches
    const sa = summary?.catches_per_match?.scope_avg ?? null
    return {
      player: null,
      global: 1,
      league: sa,
      leagueLegend: sa != null ? `${sa.toFixed(2)} catches/match` : null,
    }
  }

  function sparklinePoint(o: FielderObservation): SparklinePoint {
    const v = o[metric]
    let color: string
    if (v <= 0) color = '#7090A8'           // indigo (zero)
    else if (v === 1) color = '#7A8E6A'     // sage (one)
    else color = WISDEN.ochre               // ochre (multi)
    return {
      date: o.date, matchId: o.match_id, value: v,
      tooltip: `${o.date} · ${v} ${metricLabel.toLowerCase()}`,
      color,
      // Indigo bars (zero) wash out at 0.8; full opacity. Also gives
      // every match a visible 4px stub so wicketless/eventless matches
      // remain clickable per the codified per-item-chart rule.
      opacity: v <= 0 ? 1.0 : undefined,
    }
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
      aria-label="Per-match fielding distribution"
    >
      <header style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: '0.5rem',
        marginBottom: '0.5rem',
      }}>
        <KickerHeader title="Per-match fielding distribution" />
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
        {METRIC_OPTIONS.filter(o => o.key !== 'stumpings' || isKeeper).map(opt => (
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
          No matches under this filter — try widening the scope.
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
            No matches in {windowLabel(window)} under this filter.
          </div>
          <FielderFormDeltaLine dossier={distribution} />
        </>
      ) : block ? (
        <>
          <div className="wisden-dist-grid">
            <CountHistogram
              observations={dossier.observations}
              metricKey={metric}
              metricLabel={metricLabel}
            />
            <FielderStatStrip
              block={block}
              metricLabel={metricLabel}
              nMatches={dossier.n_matches}
              substituteCatches={metric === 'catches' ? dossier.substitute_catches : undefined}
            />
          </div>
          <FielderChipsRow block={block} />

          <div style={{ marginTop: '0.75rem' }}>
            {(() => {
              const refs = sparklineRef()
              const points = dossier.observations.map(sparklinePoint)
              return (
                <>
                  <ScrollableBars count={points.length}>
                    <DistributionSparkline
                      points={points}
                      playerReferenceValue={refs.player}
                      globalReferenceValue={refs.global}
                      leagueReferenceValue={refs.league}
                    />
                    <SeasonTickAxis dates={dossier.observations.map(o => o.date)} />
                  </ScrollableBars>
                  <div style={{
                    display: 'flex', flexWrap: 'wrap', alignItems: 'baseline',
                    columnGap: '0.85rem', rowGap: '0.15rem',
                    marginTop: '0.1rem',
                    fontFamily: 'var(--serif)', fontStyle: 'italic',
                    fontSize: '0.7rem', color: 'var(--ink-faint)',
                  }}>
                    <span>oldest ← bars (one per match, height = {metricLabel.toLowerCase()}) → most recent</span>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center',
                      columnGap: '0.85rem', rowGap: '0.15rem', flexWrap: 'wrap',
                    }}>
                      {metric === 'stumpings' && refs.player !== null && (
                        <span>
                          <span aria-hidden="true" style={{
                            display: 'inline-block', width: 14, height: 2,
                            background: '#1A1714',
                            verticalAlign: 'middle',
                            marginRight: '0.3rem',
                            position: 'relative', top: '-0.1em',
                          }} />
                          player mean {refs.player.toFixed(2)}/match
                        </span>
                      )}
                      {refs.league !== null && (
                        <span>
                          <span aria-hidden="true" style={{
                            display: 'inline-block', width: 14, height: 1.5,
                            background: '#3F7A4D',
                            verticalAlign: 'middle',
                            marginRight: '0.3rem',
                            position: 'relative', top: '-0.1em',
                          }} />
                          cohort at scope ({refs.leagueLegend})
                        </span>
                      )}
                      {refs.global !== null && (
                        <span>
                          <span aria-hidden="true" style={{
                            display: 'inline-block', width: 14, height: 1.5,
                            background: '#8A7D70',
                            verticalAlign: 'middle',
                            marginRight: '0.3rem',
                            position: 'relative', top: '-0.1em',
                          }} />
                          1 {metric === 'run_outs' ? 'run-out' : 'catch'} line
                        </span>
                      )}
                    </span>
                  </div>
                </>
              )
            })()}
          </div>

          <FielderFormDeltaLine dossier={distribution} />
        </>
      ) : null}

      <FielderSuggestedSplitsRow playerId={playerId} splits={distribution.suggested_splits} />
    </section>
  )
}
