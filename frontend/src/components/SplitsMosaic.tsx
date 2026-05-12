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
import { useMemo, useRef } from 'react'
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
  /** Aux-stripped /splits response (same FilterBar scope, but
   *  inning / toss_outcome / result filters NOT applied). Drives
   *  the marginal-row chips (outcome marginals, column-header
   *  toss values, row-header inning values, All-toss / Both-
   *  innings counts) so they keep showing 4-rect baseline values
   *  even when the user has clicked into a filter. The cells
   *  themselves still use the aux-filtered `data`. */
  unauxData?: TeamSplits | null
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

// ─── Sub-rect ordering inside a cell ─────────────────────────────────
//
// Default order is [won, tied, lost] (cricket convention: good → bad,
// reading left → right). `reverse=true` flips to [lost, tied, won],
// applied to the LEFT column of the 2×2 (tv === 'won') so the green
// won-sub-rects sit ADJACENT to the right column's green sub-rects —
// greens cluster at the center cross, making area-wise win comparisons
// across the four cells easier. The rule depends only on column
// position (`tv`), not on filter state, so it sustains through
// filtering: filtering hides cells but never changes orientation.
function orderedResultsForCell(resultValues: Outcome[], reverse: boolean = false): Outcome[] {
  return reverse ? [...resultValues].reverse() : resultValues
}

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

function dirForOutcome(rv: Outcome): 'higher_better' | 'lower_better' {
  if (rv === 'won') return 'higher_better'
  if (rv === 'lost') return 'lower_better'
  // tied — no inherent value direction, but user wants the chip
  // colored by sign anyway ("the chip just says above/below avg,
  // not a value judgement"). 'higher_better' makes positive
  // delta→green, negative→red without implying tied-more-is-good.
  return 'higher_better'
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
export default function SplitsMosaic({ data, loading, filters, activeTab, matchesEnvelope, uniqueTeamsInScope: _uniqueTeamsInScope, unauxData }: Props) {
  const setUrlParams = useSetUrlParams()

  // Scroll preservation: handled at the document level by the
  // global `body { padding-bottom: 50vh }` rule (see index.css).
  // That gives every page enough scroll headroom that when an aux
  // filter shrinks the mosaic, the document doesn't shrink past
  // the user's current scrollY — so the browser doesn't auto-
  // scroll up, and the mosaic stays put. The mosaic panel itself
  // sizes naturally to its content, the tabs below reflow up
  // immediately, and there's no empty space inside the bordered
  // panel.
  const mosaicRootRef = useRef<HTMLDivElement | null>(null)

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
      <div ref={mosaicRootRef} className="wisden-splits-mosaic" style={{ padding: '0.75rem 1rem', minHeight: 60 }}>
        <span style={{ fontStyle: 'italic', color: WISDEN.faint }}>Loading splits…</span>
      </div>
    )
  }
  if (!data || total === 0) {
    return (
      <div ref={mosaicRootRef} className="wisden-splits-mosaic" style={{ padding: '0.75rem 1rem' }}>
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
      <div ref={mosaicRootRef} className="wisden-splits-mosaic">
        <Strip filters={filters} total={total} subjectTeam={subjectTeam} thinSample={thinSample} setAux={setAux} bowlingCtx={bowlingCtx} />
      </div>
    )
  }

  // ─── 1-free case — 1D bar ────────────────────────────────────────
  if ([r, t, i].filter(x => x !== null).length === 2) {
    return (
      <div ref={mosaicRootRef} className="wisden-splits-mosaic">
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

  // ─── Mosaic — 4 cells in a 2×2 outer grid + a scalable cell area
  //
  // The outer container is a CSS grid with clean alignment:
  //   ┌─────────────┬──────────────────────┐
  //   │  (corner)   │  column headers row  │
  //   ├─────────────┼──────────────────────┤
  //   │ row headers │     CELL AREA        │
  //   │  column     │   (the 4 squares)    │
  //   └─────────────┴──────────────────────┘
  // Headers sit in fixed strips that span the full grid track;
  // they don't chase the cells' extents. Inside the cell area
  // (bottom-right grid cell) the 4 mosaic cells are absolutely
  // positioned, anchored at the GEOMETRIC CENTER (50%, 50%) of
  // the cell area. Each mosaic cell's width is `(count/unit) ×
  // SCALE_FRAC` percent of the cell-area width, and its height the
  // same percent of the cell-area HEIGHT — so a cell distorts
  // along with the cell-area's aspect ratio (wide on desktop, tall
  // on mobile, both set by media query). Relative sizes between
  // cells stay correct in both because they all use the same x/y
  // percentage axes.
  //
  // Filter-bar scope total — STABLE under aux filters. Comes from
  // /summary's matches envelope (FilterBar respects gender/tier/
  // tournament/season/team but not toss_outcome/inning/result).
  // Falls back to scope_total_n if envelope absent.
  const baseTotal = (matchesEnvelope?.value ?? total) || 1
  const unitHalf = baseTotal / 2  // = average marginal in filter scope

  // Joint count for cell (tv, iv).
  const cellJointN = (tv: 'won' | 'lost', iv: 0 | 1) =>
    resultValues.reduce(
      (s, rv) => s + (cellMap.get(`${tv}|${iv}|${rv}`)?.n ?? 0),
      0,
    )
  const showCell = (tv: 'won' | 'lost', iv: 0 | 1) =>
    tossValues.includes(tv) && inningValues.includes(iv)

  // Side fraction of the QUADRANT — area-proportional sizing via
  // sqrt so cell area encodes count linearly. With SCALE_FRAC = 1
  // a cell with count = unitHalf (= total/2) would fill its
  // quadrant exactly; smaller cells take less. Joint counts can
  // theoretically reach 2×unitHalf (= total) so we clamp at 1.0
  // to keep cells inside their quadrant.
  const SCALE_FRAC = 1.0
  const sideFrac = (tv: 'won' | 'lost', iv: 0 | 1) => {
    if (!showCell(tv, iv)) return 0
    const ratio = cellJointN(tv, iv) / unitHalf
    if (ratio <= 0) return 0
    return Math.min(1.0, Math.sqrt(ratio) * SCALE_FRAC)
  }

  // Cream "+" gutter at the center cross is drawn by the
  // grid-gap between quadrants (set in CSS) — no inline gutter
  // calculation needed here.

  // All-toss / Both-innings totals show the FilterBar-scope total
  // (= matchesEnvelope.value, FROZEN under aux filters), not the
  // aux-narrowed `scope_total_n`. The label "All toss · 276" is
  // meant to clear the toss filter and show all matches, so it
  // should display the unfiltered total at all times.
  const baseTotalForRow = matchesEnvelope?.value ?? total
  const allTossN = baseTotalForRow
  const allInningsN = baseTotalForRow

  // Per-team league avg matches — comes straight from the
  // matchesEnvelope's scope_avg, which the /summary endpoint
  // already computes correctly (= league_total_n / unique_teams).
  // Earlier code derived it as `league_total_n / 2 / unique_teams`
  // which double-divided and produced wrong deltas (e.g. +240% for
  // teams that actually only sat ~70% above league avg).
  const leaguePerTeamMatches = matchesEnvelope?.scope_avg ?? null
  const matchesDeltaPct = (leaguePerTeamMatches != null && leaguePerTeamMatches > 0)
    ? Math.round((baseTotalForRow - leaguePerTeamMatches) / leaguePerTeamMatches * 100 * 10) / 10
    : null
  const matchesDeltaEnv: MetricEnvelope | null = (hasSubject && leaguePerTeamMatches != null && matchesDeltaPct != null)
    ? {
        value: baseTotalForRow,
        scope_avg: Math.round(leaguePerTeamMatches * 10) / 10,
        delta_pct: matchesDeltaPct,
        direction: 'higher_better',
        sample_size: baseTotalForRow,
      }
    : null

  // Marginals come from unauxData when available — that's the
  // /splits response with aux filters stripped, so the chips
  // (outcome row + col-header toss + row-header inning) keep
  // showing 4-rect baseline values regardless of aux filtering.
  // Falls back to the aux-filtered data.marginals if unauxData
  // isn't loaded yet (initial render before sibling fetch settles).
  const marginalsForDisplay = unauxData?.marginals ?? data.marginals

  return (
    <div ref={mosaicRootRef} className="wisden-splits-mosaic">
      <Strip filters={filters} total={total} subjectTeam={subjectTeam} thinSample={thinSample} setAux={setAux} bowlingCtx={bowlingCtx} />

      {/* Marginal links above the matrix.
          Line 1: outcome marginals (Won/Tied/Lost) with color-coded
                  text + direction-aware MetricDelta.
          Line 2: All-toss / Both-innings filter-clear links with
                  numbers + delta (vs per-team league avg, sourced
                  from the StatCard's matchesEnvelope). */}
      <div className="wisden-splits-marginal-row">
        {(['won', 'tied', 'lost'] as Outcome[]).map(rv => {
          const m = marginalsForDisplay.result[rv]
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
              <strong className="comp-link">{RESULT_LEGEND[rv]}</strong>{' '}
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
          <span className="comp-link">All toss</span> · {allTossN}
          {matchesDeltaEnv && <MetricDelta env={matchesDeltaEnv} />}
        </button>
        <button
          type="button"
          onClick={() => setOne('inning', '')}
          className="wisden-splits-clear-link"
          title={i !== null ? 'Clear inning filter — show both innings' : 'Currently showing both innings'}
        >
          <span className="comp-link">Both innings</span> · {allInningsN}
          {matchesDeltaEnv && <MetricDelta env={matchesDeltaEnv} />}
        </button>
      </div>

      {/* Mosaic — outer 2×2 grid (corner + col-headers row + row-
          headers col + cell area). Headers sit in fixed strips,
          aligned along the outer grid. Inside the cell area, 4
          cells are absolutely positioned, anchored at geometric
          center (50%, 50%), and sized by their joint count via
          percentage. Cell area aspect-ratio is media-queried (wide
          on desktop, tall on mobile) so cells get more horizontal
          space on landscape viewports. */}
      <div className="wisden-splits-table">
        {/* Empty corner */}
        <div className="wisden-splits-corner-empty" />

        {/* Column-headers row — Won toss / Lost toss, even split */}
        <div className="wisden-splits-col-headers">
          {tossValues.map(tv => {
            const m = marginalsForDisplay.toss_outcome[tv]
            return (
              <button
                key={tv}
                type="button"
                onClick={() => setOne('toss_outcome', tv)}
                className="wisden-splits-marginal wisden-splits-col-header"
                title={`Filter to ${TOSS_LABEL[tv]}`}
              >
                <strong className="comp-link">{TOSS_LABEL[tv]}</strong>
                <span style={{ color: WISDEN.faint, marginLeft: '0.4em', fontWeight: 400 }}>
                  · {m?.n ?? 0}{m?.share != null && ` (${(m.share * 100).toFixed(0)}%)`}
                </span>
                {hasSubject && (
                  <MetricDelta env={mkEnv(m?.share, m?.league_share, m?.delta_pct, 'higher_better')} />
                )}
              </button>
            )
          })}
        </div>

        {/* Row-headers column — Batted first / Batted second */}
        <div className="wisden-splits-row-headers">
          {inningValues.map(iv => {
            const userIv = teamInningToUserInning(iv, bowlingCtx)
            const userIvStr = String(userIv) as '0' | '1'
            const m = marginalsForDisplay.inning[String(iv) as '0' | '1']
            const primaryLabel = inningLabels[userIvStr]
            const otherLabels = bowlingCtx ? INNING_LABEL_BAT : INNING_LABEL_BOWL
            const secondaryLabel = otherLabels[String(1 - userIv) as '0' | '1']
            return (
              <button
                key={`row-${iv}`}
                type="button"
                onClick={() => setOne('inning', userIvStr)}
                className="wisden-splits-marginal wisden-splits-row-header"
                title={`Filter to ${primaryLabel} (${secondaryLabel})`}
              >
                <div className="wisden-splits-row-primary"><span className="comp-link">{primaryLabel}</span></div>
                <div className="wisden-splits-row-secondary">({secondaryLabel})</div>
                <div className="wisden-splits-row-stats">
                  {m?.n ?? 0}
                  {m?.share != null && ` (${(m.share * 100).toFixed(0)}%)`}
                  {hasSubject && (
                    <MetricDelta env={mkEnv(m?.share, m?.league_share, m?.delta_pct, 'higher_better')} />
                  )}
                </div>
              </button>
            )
          })}
        </div>

        {/* Cell area — CSS Grid of 4 quadrants. Each quadrant has
            a fixed aspect-ratio (media-queried). The cell inside
            each quadrant is anchored to the corner adjacent to the
            center cross and sized by sqrt(count/unitHalf). When a
            row or column is filtered out, those quadrants aren't
            rendered and CSS Grid naturally collapses those tracks
            — remaining cells stay the same physical size. */}
        <div className="wisden-splits-cell-area">
        {([
          ['won',  0],
          ['lost', 0],
          ['won',  1],
          ['lost', 1],
        ] as Array<['won' | 'lost', 0 | 1]>).map(([tv, iv]) => {
          if (!showCell(tv, iv)) return null
          const s = sideFrac(tv, iv)
          if (s <= 0) return null
          const sPct = s * 100
          const isLeft = tv === 'won'
          const isTop = iv === 0
          // Cell position within its quadrant: anchored to the
          // quadrant corner that touches the center cross.
          const cellLeft = isLeft ? `${(1 - s) * 100}%` : '0%'
          const cellTop  = isTop  ? `${(1 - s) * 100}%` : '0%'
          const summedN = cellJointN(tv, iv)
          const cellOpacity = opacityForN(summedN)
          const dominantOutcome: Outcome | null = (() => {
            if (r !== null) return r as Outcome
            let max = -1
            let dom: Outcome | null = null
            for (const rv of resultValues) {
              const cn = cellMap.get(`${tv}|${iv}|${rv}`)?.n ?? 0
              if (cn > max) { max = cn; dom = rv }
            }
            return dom
          })()
          const cellDelta = (() => {
            if (!hasSubject || resultValues.length !== 1) return null
            const cell = cellMap.get(`${tv}|${iv}|${resultValues[0]}`)
            return cell?.delta_pct ?? null
          })()
          const cellShare = baseTotal ? summedN / baseTotal : null

          // Quadrant-summed counts for the per-cell summary label.
          const leagueSummedShare = resultValues.reduce(
            (sum, rv) => sum + (cellMap.get(`${tv}|${iv}|${rv}`)?.league_share ?? 0),
            0,
          )
          const teamJointShare = cellShare
          const quadrantDelta = (hasSubject && teamJointShare != null && leagueSummedShare > 0)
            ? ((teamJointShare - leagueSummedShare) / leagueSummedShare) * 100
            : null
          const quadrantEnv: MetricEnvelope | null = (hasSubject && quadrantDelta != null)
            ? {
                value: summedN,
                scope_avg: Math.round(leagueSummedShare * baseTotal),
                delta_pct: quadrantDelta,
                direction: 'higher_better',
                sample_size: summedN,
              }
            : null

          // Summary label position within the quadrant. Top
          // quadrants: just ABOVE the cell. Bottom quadrants: just
          // BELOW the cell. Spans the cell's horizontal extent.
          const summaryStyle: React.CSSProperties = {
            position: 'absolute',
            left: cellLeft,
            width: `${sPct}%`,
            height: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.3rem',
            fontSize: '0.78rem',
            color: WISDEN.faint,
            fontFamily: 'var(--sans)',
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
          }
          if (isTop) {
            summaryStyle.bottom = `${sPct}%`  // just above cell
          } else {
            summaryStyle.top = `${sPct}%`      // just below cell
          }

          return (
            <div
              key={`quadrant-${iv}-${tv}`}
              className="wisden-splits-quadrant"
              style={{
                gridColumn: isLeft ? 1 : 2,
                gridRow: isTop ? 1 : 2,
              }}
            >
              <div style={summaryStyle}>
                <span className="num" style={{ color: WISDEN.ink, fontWeight: 600 }}>
                  {summedN}
                </span>
                {quadrantEnv && <MetricDelta env={quadrantEnv} />}
              </div>
              <div
                className="wisden-splits-cell"
                style={{
                  position: 'absolute',
                  left: cellLeft,
                  top: cellTop,
                  width: `${sPct}%`,
                  height: `${sPct}%`,
                  opacity: cellOpacity,
                }}
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
                {orderedResultsForCell(resultValues, /* reverse */ tv === 'won').map(rv => {
                  const cell = cellMap.get(`${tv}|${iv}|${rv}`)
                  const cellN = cell?.n ?? 0
                  const sliceShare = summedN ? cellN / summedN : 0
                  const fill = OUTCOME_COLOR[rv]
                  const pct = (sliceShare * 100).toFixed(0)
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
                      {cellN > 0 && (
                        <span className="wisden-splits-subrect-label">
                          <span className="comp-link">{cellN}</span>
                          {rv !== 'tied' && ` (${pct}%)`}
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
            </div>
          )
        })}
        </div>
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
      {/* Labels row above the bar — mirrors the 4-rect outcome
          marginal row (color swatch + label + count + delta).
          Labels DON'T have to align with the bar segments; small
          segments (like a 5% Tied) used to get their label clipped
          inside the bar, which read as broken. Putting labels in a
          flex row above the bar fixes the readability. */}
      <div className="wisden-splits-1d-labels">
        {entries.map(e => {
          const n = e.m?.n ?? 0
          const w = n / total
          return (
            <button
              key={`label-${e.key}`}
              type="button"
              onClick={() => setOne(freeAxis, e.key)}
              className="wisden-splits-outcome-link"
              title={`Filter to ${e.label}`}
            >
              <span className="wisden-splits-outcome-swatch" style={{ background: e.color }} aria-hidden="true" />
              <strong className="comp-link">{e.label}</strong>{' '}
              {n}
              {` (${(w * 100).toFixed(0)}%)`}
              {hasSubject && (
                <MetricDelta env={mkEnv(e.m?.share, e.m?.league_share, e.m?.delta_pct, e.direction)} />
              )}
            </button>
          )
        })}
      </div>
      <div className="wisden-splits-1d-bar">
        {entries.map(e => {
          const n = e.m?.n ?? 0
          const w = n / total
          return (
            <button
              key={`seg-${e.key}`}
              type="button"
              onClick={() => setOne(freeAxis, e.key)}
              className="wisden-splits-1d-segment"
              style={{ flexBasis: `${w * 100}%`, background: e.color }}
              title={`Filter to ${e.label} — ${n} (${(w * 100).toFixed(0)}%)`}
              aria-label={`${e.label} — ${n} matches`}
            />
          )
        })}
      </div>
    </div>
  )
}
