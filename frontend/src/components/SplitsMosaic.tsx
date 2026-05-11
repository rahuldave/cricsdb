/**
 * SplitsMosaic — joint distribution of (toss_outcome × inning × result)
 * for the active filter scope. Doubles as a filter widget: marginals,
 * outer cells, and outcome sub-rects all write URL params on click.
 *
 * Dimensionality is URL-derived (the chart's shape IS the URL state):
 *
 *   filters set | free axes | layout
 *   ---|---|---
 *   0           | 3         | 2×2 (toss × inning) cells, each sub-divided into traffic-light W/T/L sub-rects
 *   1           | 2         | 2×2 of the two free axes; cells single-color when outcome is the filtered axis
 *   2           | 1         | 1D horizontal stacked bar over the one free axis
 *   3           | 0         | status strip only (no chart — the strip IS the widget)
 *
 * Fixed axis ordering (when free): toss_outcome → inning → result.
 * `result` always owns the innermost color slot when free; toss and
 * inning are always spatial. New conditioning axes added later must
 * be spatial, never color — color is outcome's permanent slot.
 *
 * Mount: top of frontend/src/pages/Teams.tsx, both landing
 * (no `?team=`) and team-detail (`?team=X`). Team-detail variant
 * carries per-cell deltas vs the league baseline at the same filter
 * scope (envelope pattern from `/summary`).
 *
 * Spec: internal_docs/spec-splits-mosaic.md §3.
 */
import { useMemo } from 'react'
import { useSetUrlParams } from '../hooks/useUrlState'
import { WISDEN, WISDEN_WL, WISDEN_WL_TINTS } from './charts/palette'
import MetricDelta from './MetricDelta'
import type { TeamSplits, SplitsCell, FilterParams, MetricEnvelope } from '../types'

interface Props {
  data: TeamSplits | null
  loading: boolean
  filters: FilterParams
  /** Active discipline tab on the page — determines how `?inning=` is
   *  interpreted. Match-level filters (`_inning_match_filter`,
   *  `/summary`) treat `inning=0` as "team batted first" (batting POV).
   *  Innings-joined widgets on Bowling / Fielding tabs treat
   *  `inning=0` as "team bowled in match-innings 0" = "team bowled
   *  first" (= team batted SECOND).
   *
   *  The mosaic IS a match-level widget but lives on the page above
   *  every tab — when the user has flipped to a bowling-side tab,
   *  the mosaic must read the URL with bowling-side semantics so the
   *  same `?inning=` produces a coherent reading across all widgets
   *  on the page. Spec: spec-splits-mosaic.md §3.2, see also
   *  spec-inning-split.md §3.4 dual-meaning. */
  activeTab?: string
  /** Team's `matches` envelope from `/teams/{team}/summary` — kept
   *  for API symmetry but currently unused: matches direction is null
   *  in `wrap_metric` (count, not a rate) so its delta_pct is null.
   *  The All-toss / Both-innings deltas are computed client-side from
   *  data.scope_total_n vs data.league_total_n / unique_teams_in_scope. */
  matchesEnvelope?: MetricEnvelope | null
  /** Unique teams in scope, from /teams/{team}/summary. Needed to
   *  compute the per-team league-avg matches as the comparison anchor
   *  for All-toss / Both-innings deltas. */
  uniqueTeamsInScope?: number | null
}

type Outcome = 'won' | 'lost' | 'tied'

// ─── Vocabulary (spec §3.10) ────────────────────────────────────────
const TOSS_LABEL = { won: 'Won toss', lost: 'Lost toss' } as const
const INNING_LABEL_BAT = { '0': 'Batted first', '1': 'Batted second' } as const
const INNING_LABEL_BOWL = { '0': 'Bowled first', '1': 'Bowled second' } as const
const RESULT_LABEL = {
  won:  'Won the game',
  lost: 'Lost the game',
  tied: 'Tied',
} as const
const RESULT_LEGEND = { won: 'Won', lost: 'Lost', tied: 'Tied' } as const

const BOWLING_TABS = new Set(['Bowling', 'Fielding'])

/** When on Bowling/Fielding tabs, ?inning= refers to the match's
 *  innings_number the team BOWLED in. Mosaic cell `team_inning` is
 *  always batting-POV (team batted in inning 0 vs 1). So when the
 *  user picks "Bowled first" (URL ?inning=0) on a bowling tab, we
 *  filter mosaic cells to team_inning=1 (team batted second).
 *
 *  Conversion: in bowling context, inning_user XOR 1 = team_inning_in_mosaic.
 */
function userInningToTeamInning(userInning: 0 | 1, bowlingCtx: boolean): 0 | 1 {
  return bowlingCtx ? ((1 - userInning) as 0 | 1) : userInning
}

function teamInningToUserInning(teamInning: 0 | 1, bowlingCtx: boolean): 0 | 1 {
  return bowlingCtx ? ((1 - teamInning) as 0 | 1) : teamInning
}

const OUTCOME_COLOR: Record<Outcome, string> = {
  won:  WISDEN_WL.won,
  tied: WISDEN_WL.tied,
  lost: WISDEN_WL.lost,
}

// NEUTRAL_FILL removed — when result is filtered, cells stay colored
// with the filtered outcome's WL color (per spec §3.5 "WISDEN_WL
// reserved for outcome encoding"; the cells should reinforce the
// outcome the user picked, not go gray).

// ─── Status strip text (spec §3.10) ─────────────────────────────────
function strip(
  filters: FilterParams,
  total: number,
  subjectTeam: string | null,
  bowlingCtx: boolean,
): string {
  const r = filters.result
  const t = filters.toss_outcome
  const i = filters.inning
  const N = total
  const teamPrefix = subjectTeam ? `${subjectTeam}: ` : ''
  const inningLabels = bowlingCtx ? INNING_LABEL_BOWL : INNING_LABEL_BAT
  // Strip-fragment verbs for inning narrowing (lower-case, embedded).
  const inningVerb = (v: string) => bowlingCtx
    ? (v === '0' ? 'bowling first' : 'bowling second')
    : (v === '0' ? 'batting first' : 'batting second')
  const inningNounPhrase = (v: string) => bowlingCtx
    ? (v === '0' ? 'matches bowling first' : 'matches bowling second')
    : (v === '0' ? 'matches batting first' : 'matches batting second')

  // 3 filters set → verbose middot summary
  if (r && t && i !== undefined) {
    const tossStr = TOSS_LABEL[t as 'won' | 'lost']
    const innStr = inningLabels[i as '0' | '1']
    const resStr = RESULT_LABEL[r as Outcome]
    return `${teamPrefix}${tossStr} · ${innStr} · ${resStr} — ${N} matches`
  }

  // 2 filters set
  if (r && i !== undefined) {
    const resStr = r === 'won' ? 'wins' : r === 'lost' ? 'losses' : 'tied games'
    return `${teamPrefix}Of ${N} ${resStr} after ${inningVerb(i)}:`
  }
  if (r && t) {
    const tossStr = t === 'won' ? 'winning the toss' : 'losing the toss'
    const resStr = r === 'won' ? 'wins' : r === 'lost' ? 'losses' : 'tied games'
    return `${teamPrefix}Of ${N} ${resStr} after ${tossStr}:`
  }
  if (t && i !== undefined) {
    const tossStr = t === 'won' ? 'winning the toss' : 'losing the toss'
    return `${teamPrefix}Of ${N} matches ${inningVerb(i)} after ${tossStr}:`
  }

  // 1 filter set
  if (r) {
    const resStr = r === 'won' ? 'wins' : r === 'lost' ? 'losses' : 'tied games'
    return `${teamPrefix}Of ${N} ${resStr}:`
  }
  if (t) {
    const tossStr = t === 'won' ? 'toss wins' : 'toss losses'
    return `${teamPrefix}Of ${N} ${tossStr}:`
  }
  if (i !== undefined) {
    return `${teamPrefix}Of ${N} ${inningNounPhrase(i)}:`
  }

  // 0 filters
  return `${teamPrefix}All ${N} matches`
}

// ─── Opacity for low-n cells (spec §3.8) ────────────────────────────
function opacityForN(n: number): number {
  if (n >= 20) return 1.0
  if (n >= 10) return 0.70
  if (n >= 5) return 0.45
  if (n >= 1) return 0.25
  return 0.15  // n=0 — hatched would be nice; opacity 0.15 reads as 'empty'
}

// ─── Delta percentage renderer ──────────────────────────────────────
//
// Wraps the existing MetricDelta component — same green/red direction-
// aware coloring used everywhere else in the codebase for "vs league
// avg" deltas. The Splits widget builds a synthetic MetricEnvelope
// shape with a `direction` chosen per axis:
//   - Won outcomes / won-dominant cells: 'higher_better' (more wins = good)
//   - Lost outcomes / lost-dominant cells: 'lower_better' (more losses = bad)
//   - Tied / non-directional axes (toss / inning): direction=null →
//     MetricDelta intentionally returns null (no delta shown), because
//     "60% won toss vs league 50%" doesn't have a good/bad direction.
function mkEnv(
  share: number | null | undefined,
  leagueShare: number | null | undefined,
  deltaPct: number | null | undefined,
  direction: 'higher_better' | 'lower_better' | null,
): MetricEnvelope {
  return {
    value: share ?? null,
    scope_avg: leagueShare ?? null,
    delta_pct: deltaPct ?? null,
    direction,
    sample_size: null,
  }
}

function dirForOutcome(rv: Outcome): 'higher_better' | 'lower_better' | null {
  if (rv === 'won') return 'higher_better'
  if (rv === 'lost') return 'lower_better'
  return null  // tied — no direction
}

// ─── Wilson CI tooltip text ─────────────────────────────────────────
function cellTooltip(cell: SplitsCell, total: number, hasSubject: boolean, bowlingCtx: boolean): string {
  const sharePct = cell.share != null ? (cell.share * 100).toFixed(1) : '–'
  const inningLabels = bowlingCtx ? INNING_LABEL_BOWL : INNING_LABEL_BAT
  // Cell.inning is team_inning (batting POV). In bowling context, the
  // user-facing label is flipped: team_inning=0 (batted first) →
  // "Bowled second" from the user's POV.
  const userInning = teamInningToUserInning(cell.inning as 0 | 1, bowlingCtx)
  const lines = [
    `${TOSS_LABEL[cell.toss_outcome]} · ${inningLabels[String(userInning) as '0' | '1']} · ${RESULT_LABEL[cell.result]}`,
    `${cell.n} of ${total} matches (${sharePct}%)`,
  ]
  if (cell.wilson_lo != null && cell.wilson_hi != null) {
    lines.push(
      `Wilson 95% CI: ${(cell.wilson_lo * 100).toFixed(0)}% – ${(cell.wilson_hi * 100).toFixed(0)}%`,
    )
  }
  if (hasSubject && cell.delta_pct != null && cell.league_share != null) {
    const arrow = cell.delta_pct > 0 ? '↑' : '↓'
    const sign = cell.delta_pct > 0 ? '+' : ''
    lines.push(
      `vs league baseline: ${arrow} ${sign}${cell.delta_pct.toFixed(1)}% (${(cell.league_share * 100).toFixed(0)}% → ${sharePct}%)`,
    )
  }
  return lines.join('\n')
}

// ─── Component ──────────────────────────────────────────────────────
export default function SplitsMosaic({ data, loading, filters, activeTab, matchesEnvelope: _me, uniqueTeamsInScope }: Props) {
  const setUrlParams = useSetUrlParams()

  // Bowling-side tabs flip the inning semantic — see Props.activeTab
  // doc + spec-inning-split.md §3.4.
  const bowlingCtx = !!activeTab && BOWLING_TABS.has(activeTab)
  const inningLabels = bowlingCtx ? INNING_LABEL_BOWL : INNING_LABEL_BAT

  // Active filter narrowings — these define dimensionality.
  const r = filters.result || null
  const t = filters.toss_outcome || null
  const i = filters.inning || null
  const subjectTeam = data?.subject?.team ?? null
  const hasSubject = !!subjectTeam
  const total = data?.scope_total_n ?? 0

  // Aux cleanup helper — clears toss/result/inning, optionally overrides one or more.
  const setAux = (overrides: Partial<Record<'result' | 'toss_outcome' | 'inning', string>>) => {
    const next: Record<string, string> = {
      result: overrides.result ?? '',
      toss_outcome: overrides.toss_outcome ?? '',
      inning: overrides.inning ?? '',
    }
    setUrlParams(next)
  }

  const setOne = (key: 'result' | 'toss_outcome' | 'inning', value: string) => {
    setUrlParams({ [key]: value })
  }

  // Build cell index for fast lookup.
  const cellMap = useMemo(() => {
    const m = new Map<string, SplitsCell>()
    if (data?.cells) {
      for (const c of data.cells) {
        m.set(`${c.toss_outcome}|${c.inning}|${c.result}`, c)
      }
    }
    return m
  }, [data])

  if (loading) {
    return (
      <div className="wisden-splits-mosaic" style={{ padding: '0.75rem 1rem', minHeight: 60 }}>
        <span style={{ fontStyle: 'italic', color: WISDEN.faint }}>Loading splits…</span>
      </div>
    )
  }
  if (!data || total === 0) {
    return (
      <div className="wisden-splits-mosaic" style={{ padding: '0.75rem 1rem' }}>
        <span style={{ fontStyle: 'italic', color: WISDEN.faint }}>
          No matches in scope for splits.
        </span>
      </div>
    )
  }

  const thinSample = total < 30

  // ─── 0-free case — status strip only ─────────────────────────────
  if (r && t && i !== null) {
    return (
      <div className="wisden-splits-mosaic">
        <Strip filters={filters} total={total} subjectTeam={subjectTeam} thinSample={thinSample} setAux={setAux} bowlingCtx={bowlingCtx} />
      </div>
    )
  }

  // ─── 1-free case — 1D bar ────────────────────────────────────────
  if ([r, t, i].filter(x => x !== null).length === 2) {
    return (
      <div className="wisden-splits-mosaic">
        <Strip filters={filters} total={total} subjectTeam={subjectTeam} thinSample={thinSample} setAux={setAux} bowlingCtx={bowlingCtx} />
        <OneDimBar
          marginals={data.marginals}
          freeAxis={r === null ? 'result' : t === null ? 'toss_outcome' : 'inning'}
          hasSubject={hasSubject}
          setOne={setOne}
          bowlingCtx={bowlingCtx}
        />
      </div>
    )
  }

  // ─── 2-free or 3-free case — 2×2 mosaic ──────────────────────────
  // Toss → columns, inning → rows, result → within-cell sub-rects.
  // When one of {toss, inning} is filtered, only one column/row
  // appears. When result is filtered, sub-rects collapse to a single
  // neutral fill.

  const tossValues: ('won' | 'lost')[] = t === null ? ['won', 'lost'] : [t as 'won' | 'lost']
  // `inningValues` is in team-batting POV (mosaic SQL's team_inning).
  // When user has set ?inning= AND we're in bowling context, the URL's
  // user-POV value flips to derive which team_inning to filter to.
  const inningValues: (0 | 1)[] = i === null
    ? [0, 1]
    : [userInningToTeamInning(parseInt(i) as 0 | 1, bowlingCtx)]
  const resultValues: Outcome[] = r === null ? ['won', 'tied', 'lost'] : [r as Outcome]

  // Column widths proportional to toss-outcome marginal.
  const tossN = (tv: 'won' | 'lost') => data.marginals.toss_outcome[tv]?.n ?? 0
  const tossTotal = tossValues.reduce((s, v) => s + tossN(v), 0) || 1
  const colWidths = tossValues.map(tv => tossN(tv) / tossTotal)

  // Build CSS-grid template columns: row-header width + proportional toss columns.
  const gridCols = `9rem ${colWidths.map(w => `${w}fr`).join(' ')}`

  // All-toss / Both-innings totals reflect the current filtered slice
  // (= scope_total_n). When the toss / inning filter IS set, this is
  // the narrowed count; clicking clears the narrowing and the
  // displayed total expands.
  const allTossN = total
  const allInningsN = total

  // Per-team league avg matches for the comparison anchor on the
  // All-toss / Both-innings deltas. league_total_n is the unpivot
  // total (= 2 × match_count), so league_total_n / 2 = match_count.
  // Divide by N_teams to get per-team avg. unique_teams_in_scope
  // comes from /teams/{team}/summary.
  const leaguePerTeamMatches = (
    data.league_total_n && uniqueTeamsInScope && uniqueTeamsInScope > 0
  )
    ? (data.league_total_n / 2) / uniqueTeamsInScope
    : null
  const matchesDeltaPct = leaguePerTeamMatches
    ? Math.round((total - leaguePerTeamMatches) / leaguePerTeamMatches * 100 * 10) / 10
    : null
  const matchesDeltaEnv: MetricEnvelope | null = (hasSubject && leaguePerTeamMatches != null && matchesDeltaPct != null)
    ? {
        value: total,
        scope_avg: Math.round(leaguePerTeamMatches * 10) / 10,
        delta_pct: matchesDeltaPct,
        direction: null,  // count — informational, neutral coloring
        sample_size: total,
      }
    : null

  return (
    <div className="wisden-splits-mosaic">
      <Strip filters={filters} total={total} subjectTeam={subjectTeam} thinSample={thinSample} setAux={setAux} bowlingCtx={bowlingCtx} />

      {/* Marginal links above the matrix.
          Line 1: outcome marginals (Won/Tied/Lost) with color-coded
                  text + direction-aware MetricDelta.
          Line 2: All-toss / Both-innings filter-clear links with
                  numbers + delta (vs per-team league avg, sourced
                  from the StatCard's matchesEnvelope). */}
      <div className="wisden-splits-marginal-row">
        {(['won', 'tied', 'lost'] as Outcome[]).map(rv => {
          const m = data.marginals.result[rv]
          const tint = WISDEN_WL_TINTS[rv]
          const isActive = r === rv
          return (
            <button
              key={rv}
              type="button"
              onClick={() => setOne('result', isActive ? '' : rv)}
              className={`wisden-splits-outcome-link${isActive ? ' is-active' : ''}`}
              style={{ color: tint.fg }}
              title={isActive ? `Clear ${RESULT_LABEL[rv]}` : `Filter to ${RESULT_LABEL[rv]}`}
            >
              <span className="wisden-splits-outcome-swatch" style={{ background: OUTCOME_COLOR[rv] }} aria-hidden="true" />
              <strong>{RESULT_LEGEND[rv]}</strong>{' '}
              {m?.n ?? 0}
              {m?.share != null && ` (${(m.share * 100).toFixed(0)}%)`}
              {hasSubject && (
                <MetricDelta env={mkEnv(m?.share, m?.league_share, m?.delta_pct, dirForOutcome(rv))} />
              )}
            </button>
          )
        })}
      </div>
      <div className="wisden-splits-marginal-row wisden-splits-marginal-row-secondary">
        <button
          type="button"
          onClick={() => setOne('toss_outcome', '')}
          className="wisden-splits-clear-link"
          title={filters.toss_outcome ? 'Clear toss filter — show both Won toss and Lost toss' : 'Currently showing both Won toss and Lost toss'}
        >
          All toss · {allTossN}
          {matchesDeltaEnv && <MetricDelta env={matchesDeltaEnv} />}
        </button>
        <button
          type="button"
          onClick={() => setOne('inning', '')}
          className="wisden-splits-clear-link"
          title={i !== null ? 'Clear inning filter — show both innings' : 'Currently showing both innings'}
        >
          Both innings · {allInningsN}
          {matchesDeltaEnv && <MetricDelta env={matchesDeltaEnv} />}
        </button>
      </div>

      {/* Confusion-matrix style table. */}
      <div className="wisden-splits-table" style={{ gridTemplateColumns: gridCols }}>
        {/* Empty corner — All-toss / Both-innings moved to the marginal row above. */}
        <div className="wisden-splits-corner-empty" />

        {/* COLUMN HEADERS — Won toss / Lost toss */}
        {tossValues.map(tv => {
          const m = data.marginals.toss_outcome[tv]
          return (
            <button
              key={tv}
              type="button"
              onClick={() => setOne('toss_outcome', tv)}
              className="wisden-splits-marginal wisden-splits-col-header"
              title={`Filter to ${TOSS_LABEL[tv]}`}
            >
              <strong>{TOSS_LABEL[tv]}</strong>
              <span style={{ color: WISDEN.faint, marginLeft: '0.4em', fontWeight: 400 }}>
                · {m?.n ?? 0}{m?.share != null && ` (${(m.share * 100).toFixed(0)}%)`}
              </span>
              {hasSubject && (
                <MetricDelta env={mkEnv(m?.share, m?.league_share, m?.delta_pct, null)} />
              )}
            </button>
          )
        })}

        {/* ROWS — each row contributes [row-header, cell, cell, ...] grid items. */}
        {inningValues.flatMap(iv => {
          const userIv = teamInningToUserInning(iv, bowlingCtx)
          const userIvStr = String(userIv) as '0' | '1'
          const m = data.marginals.inning[String(iv) as '0' | '1']
          const primaryLabel = inningLabels[userIvStr]
          const otherLabels = bowlingCtx ? INNING_LABEL_BAT : INNING_LABEL_BOWL
          const secondaryLabel = otherLabels[String(1 - userIv) as '0' | '1']
          return [
            <button
              key={`row-${iv}`}
              type="button"
              onClick={() => setOne('inning', userIvStr)}
              className="wisden-splits-marginal wisden-splits-row-header"
              title={`Filter to ${primaryLabel} (${secondaryLabel})`}
            >
              <div className="wisden-splits-row-primary">{primaryLabel}</div>
              <div className="wisden-splits-row-secondary">({secondaryLabel})</div>
              <div className="wisden-splits-row-stats">
                {m?.n ?? 0}
                {m?.share != null && ` (${(m.share * 100).toFixed(0)}%)`}
                {hasSubject && (
                  <MetricDelta env={mkEnv(m?.share, m?.league_share, m?.delta_pct, null)} />
                )}
              </div>
            </button>,
            ...tossValues.map(tv => {
              const summedN = resultValues.reduce(
                (s, rv) => s + (cellMap.get(`${tv}|${iv}|${rv}`)?.n ?? 0), 0,
              )
              const colTotal = tossN(tv)
              const cellShare = colTotal ? summedN / colTotal : null
              const cellOpacity = opacityForN(summedN)
              // Dominant outcome of the cell — for tinting the cell label.
              const dominantOutcome: Outcome | null = (() => {
                if (r !== null) return r as Outcome  // result is filtered → that's the only outcome
                let max = -1
                let dom: Outcome | null = null
                for (const rv of resultValues) {
                  const cn = cellMap.get(`${tv}|${iv}|${rv}`)?.n ?? 0
                  if (cn > max) { max = cn; dom = rv }
                }
                return dom
              })()
              // dominantOutcome is now only used to pick MetricDelta's
              // direction (won-dominant cell ⇒ higher_better, etc.) —
              // the cell-label color chip was removed when labels moved
              // INSIDE the bars in white-on-color.
              const cellDelta = (() => {
                if (!hasSubject || resultValues.length !== 1) return null
                const cell = cellMap.get(`${tv}|${iv}|${resultValues[0]}`)
                return cell?.delta_pct ?? null
              })()
              return (
                <div
                  key={`cell-${iv}-${tv}`}
                  className="wisden-splits-cell"
                  style={{ opacity: cellOpacity }}
                >
                  <div
                    className="wisden-splits-cell-fills"
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      setUrlParams({
                        toss_outcome: tv,
                        inning: String(teamInningToUserInning(iv, bowlingCtx)),
                        result: filters.result || '',
                      })
                    }}
                    title={`Filter to ${TOSS_LABEL[tv]} · ${inningLabels[String(teamInningToUserInning(iv, bowlingCtx)) as '0' | '1']}`}
                  >
                    {resultValues.map(rv => {
                      const cell = cellMap.get(`${tv}|${iv}|${rv}`)
                      const cellN = cell?.n ?? 0
                      const sliceShare = summedN ? cellN / summedN : 0
                      // Always use the outcome's WL color — when result is
                      // filtered, the cell becomes a single-color bar in that
                      // outcome's color (not neutral gray). User feedback
                      // 2026-05-11: "When I click on Won the colors go away.
                      // It should be one bar with color."
                      const fill = OUTCOME_COLOR[rv]
                      const pct = (sliceShare * 100).toFixed(0)
                      // Per-sub-rect label INSIDE the bar in white text.
                      // Wins/losses: number + percentage. Ties: number
                      // only (the yellow segment is usually narrow; OK
                      // to bleed out for readability). User 2026-05-11.
                      const labelText = cellN === 0
                        ? ''
                        : rv === 'tied'
                          ? `${cellN}`
                          : `${cellN} (${pct}%)`
                      return (
                        <div
                          key={rv}
                          className={`wisden-splits-subrect wisden-splits-subrect-${rv}`}
                          style={{ flexBasis: `${sliceShare * 100}%`, background: fill }}
                          onClick={(e) => {
                            e.stopPropagation()
                            setUrlParams({
                              toss_outcome: tv,
                              inning: String(teamInningToUserInning(iv, bowlingCtx)),
                              result: rv,
                            })
                          }}
                          title={cell ? cellTooltip(cell, total, hasSubject, bowlingCtx) : `${RESULT_LEGEND[rv]} — 0 matches`}
                        >
                          {labelText && (
                            <span className="wisden-splits-subrect-label">
                              {labelText}
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                  {hasSubject && cellDelta != null && (
                    <div className="wisden-splits-cell-delta">
                      <MetricDelta
                        env={mkEnv(cellShare, null, cellDelta,
                          dominantOutcome ? dirForOutcome(dominantOutcome) : null)}
                      />
                    </div>
                  )}
                </div>
              )
            }),
          ]
        })}
      </div>

      {thinSample && (
        <div className="wisden-splits-thin-sample">
          Thin sample (n &lt; 30) — interpret with caution.
        </div>
      )}
    </div>
  )
}

// ─── Sub-components ─────────────────────────────────────────────────

function Strip({
  filters, total, subjectTeam, thinSample, setAux, bowlingCtx,
}: {
  filters: FilterParams; total: number; subjectTeam: string | null;
  thinSample: boolean; setAux: (o: Partial<Record<'result' | 'toss_outcome' | 'inning', string>>) => void;
  bowlingCtx: boolean;
}) {
  const hasAnyFilter = !!(filters.result || filters.toss_outcome || filters.inning)
  return (
    <div className="wisden-splits-strip">
      <span>{strip(filters, total, subjectTeam, bowlingCtx)}</span>
      {hasAnyFilter && (
        <button
          type="button"
          onClick={() => setAux({})}
          className="wisden-splits-reset"
          title="Clear toss / inning / result narrowings"
        >
          reset
        </button>
      )}
      {thinSample && (
        <span style={{ color: WISDEN.faint, fontStyle: 'italic', marginLeft: '0.6em' }}>
          (thin sample)
        </span>
      )}
    </div>
  )
}

function OneDimBar({
  marginals, freeAxis, hasSubject, setOne, bowlingCtx,
}: {
  marginals: TeamSplits['marginals']
  freeAxis: 'result' | 'toss_outcome' | 'inning'
  hasSubject: boolean
  setOne: (key: 'result' | 'toss_outcome' | 'inning', value: string) => void
  bowlingCtx: boolean
}) {
  type Entry = {
    key: string
    label: string
    color: string
    m: { n: number; share: number | null; league_share?: number | null; delta_pct?: number | null } | undefined
    direction: 'higher_better' | 'lower_better' | null
  }
  const entries: Entry[] = (() => {
    if (freeAxis === 'result') {
      return (['won', 'tied', 'lost'] as Outcome[]).map(k => ({
        key: k, label: RESULT_LEGEND[k], color: OUTCOME_COLOR[k],
        m: marginals.result[k],
        direction: dirForOutcome(k),
      }))
    }
    if (freeAxis === 'toss_outcome') {
      return (['won', 'lost'] as const).map(k => ({
        key: k, label: TOSS_LABEL[k], color: WISDEN.indigo,
        m: marginals.toss_outcome[k],
        direction: null,
      }))
    }
    const inningLabels = bowlingCtx ? INNING_LABEL_BOWL : INNING_LABEL_BAT
    return (['0', '1'] as const).map(userK => {
      const teamInning = userInningToTeamInning(parseInt(userK) as 0 | 1, bowlingCtx)
      return {
        key: userK as '0' | '1',
        label: inningLabels[userK],
        color: WISDEN.indigo,
        m: marginals.inning[String(teamInning) as '0' | '1'],
        direction: null,
      }
    })
  })()
  const total = entries.reduce((s, e) => s + (e.m?.n ?? 0), 0) || 1
  return (
    <div className="wisden-splits-1d">
      {entries.map(e => {
        const n = e.m?.n ?? 0
        const w = n / total
        return (
          <button
            key={e.key}
            type="button"
            onClick={() => setOne(freeAxis, e.key)}
            className="wisden-splits-1d-segment"
            style={{ flexBasis: `${w * 100}%`, background: e.color }}
            title={`Filter to ${e.label}`}
          >
            <span className="wisden-splits-1d-label">
              {e.label} {n} ({(w * 100).toFixed(0)}%)
              {hasSubject && (
                <MetricDelta env={mkEnv(e.m?.share, e.m?.league_share, e.m?.delta_pct, e.direction)} />
              )}
            </span>
          </button>
        )
      })}
    </div>
  )
}
