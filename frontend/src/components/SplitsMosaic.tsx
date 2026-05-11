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
import { WISDEN, WISDEN_WL } from './charts/palette'
import type { TeamSplits, SplitsCell, FilterParams } from '../types'

interface Props {
  data: TeamSplits | null
  loading: boolean
  filters: FilterParams
}

type Outcome = 'won' | 'lost' | 'tied'

// ─── Vocabulary (spec §3.10) ────────────────────────────────────────
const TOSS_LABEL = { won: 'Won toss', lost: 'Lost toss' } as const
const INNING_LABEL = { '0': 'Batted first', '1': 'Batted second' } as const
const RESULT_LABEL = {
  won:  'Won the game',
  lost: 'Lost the game',
  tied: 'Tied',
} as const
const RESULT_LEGEND = { won: 'Won', lost: 'Lost', tied: 'Tied' } as const

const OUTCOME_COLOR: Record<Outcome, string> = {
  won:  WISDEN_WL.won,
  tied: WISDEN_WL.tied,
  lost: WISDEN_WL.lost,
}

const NEUTRAL_FILL = '#E8E2D4'  // muted cream tone for outcome-filtered cells

// ─── Status strip text (spec §3.10) ─────────────────────────────────
function strip(
  filters: FilterParams,
  total: number,
  subjectTeam: string | null,
): string {
  const r = filters.result
  const t = filters.toss_outcome
  const i = filters.inning
  const N = total
  const teamPrefix = subjectTeam ? `${subjectTeam}: ` : ''

  // 3 filters set → verbose middot summary
  if (r && t && i !== undefined) {
    const tossStr = TOSS_LABEL[t as 'won' | 'lost']
    const innStr = INNING_LABEL[i as '0' | '1']
    const resStr = RESULT_LABEL[r as Outcome]
    return `${teamPrefix}${tossStr} · ${innStr} · ${resStr} — ${N} matches`
  }

  // 2 filters set
  if (r && i !== undefined) {
    const innStr = i === '0' ? 'batting first' : 'batting second'
    const resStr = r === 'won' ? 'wins' : r === 'lost' ? 'losses' : 'tied games'
    return `${teamPrefix}Of ${N} ${resStr} after ${innStr}:`
  }
  if (r && t) {
    const tossStr = t === 'won' ? 'winning the toss' : 'losing the toss'
    const resStr = r === 'won' ? 'wins' : r === 'lost' ? 'losses' : 'tied games'
    return `${teamPrefix}Of ${N} ${resStr} after ${tossStr}:`
  }
  if (t && i !== undefined) {
    const tossStr = t === 'won' ? 'winning the toss' : 'losing the toss'
    const innStr = i === '0' ? 'batting first' : 'batting second'
    return `${teamPrefix}Of ${N} matches ${innStr} after ${tossStr}:`
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
    const innStr = i === '0' ? 'matches batting first' : 'matches batting second'
    return `${teamPrefix}Of ${N} ${innStr}:`
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

// ─── Delta arrow renderer ───────────────────────────────────────────
//
// Single neutral color (faint ink). Splits proportions are
// informational — most cells / marginals have no inherent "good/bad"
// direction (a team batting first 70% of the time isn't good or bad;
// it just is). Sign + arrow carry the entire signal. Green/red
// polarity here would suggest a value judgment the data doesn't
// support and would also blur the WISDEN_WL outcome vocabulary.
function DeltaBadge({ pct }: { pct: number | null | undefined }) {
  if (pct == null) return null
  const arrow = pct > 0 ? '↑' : pct < 0 ? '↓' : ''
  const sign = pct > 0 ? '+' : ''
  return (
    <span style={{ color: WISDEN.faint, fontSize: '0.75em', marginLeft: '0.3em' }}>
      {arrow} {sign}{pct.toFixed(1)}%
    </span>
  )
}

// ─── Wilson CI tooltip text ─────────────────────────────────────────
function cellTooltip(cell: SplitsCell, total: number, hasSubject: boolean): string {
  const sharePct = cell.share != null ? (cell.share * 100).toFixed(1) : '–'
  const lines = [
    `${TOSS_LABEL[cell.toss_outcome]} · ${INNING_LABEL[String(cell.inning) as '0' | '1']} · ${RESULT_LABEL[cell.result]}`,
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
export default function SplitsMosaic({ data, loading, filters }: Props) {
  const setUrlParams = useSetUrlParams()

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
        <Strip filters={filters} total={total} subjectTeam={subjectTeam} thinSample={thinSample} setAux={setAux} />
      </div>
    )
  }

  // ─── 1-free case — 1D bar ────────────────────────────────────────
  if ([r, t, i].filter(x => x !== null).length === 2) {
    return (
      <div className="wisden-splits-mosaic">
        <Strip filters={filters} total={total} subjectTeam={subjectTeam} thinSample={thinSample} setAux={setAux} />
        <OneDimBar
          marginals={data.marginals}
          freeAxis={r === null ? 'result' : t === null ? 'toss_outcome' : 'inning'}
          hasSubject={hasSubject}
          setOne={setOne}
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
  const inningValues: (0 | 1)[] = i === null ? [0, 1] : [parseInt(i) as 0 | 1]
  const resultValues: Outcome[] = r === null ? ['won', 'tied', 'lost'] : [r as Outcome]

  // Column widths proportional to toss-outcome marginal.
  const tossN = (tv: 'won' | 'lost') => data.marginals.toss_outcome[tv]?.n ?? 0
  const tossTotal = tossValues.reduce((s, v) => s + tossN(v), 0) || 1
  const colWidths = tossValues.map(tv => tossN(tv) / tossTotal)

  return (
    <div className="wisden-splits-mosaic">
      <Strip filters={filters} total={total} subjectTeam={subjectTeam} thinSample={thinSample} setAux={setAux} />

      {/* Mobile-friendly layout: desktop 2×2 via flex, mobile stacks via media query. */}
      <div className="wisden-splits-grid">
        {/* Column headers — marginal Toss labels with click-to-filter */}
        <div className="wisden-splits-col-headers">
          {tossValues.map((tv, idx) => {
            const m = data.marginals.toss_outcome[tv]
            return (
              <button
                key={tv}
                type="button"
                onClick={() => setOne('toss_outcome', tv)}
                className="wisden-splits-marginal"
                title={`Filter to ${TOSS_LABEL[tv]}`}
                style={{ flex: `${colWidths[idx]} 1 0` }}
              >
                {TOSS_LABEL[tv]}
                <span style={{ color: WISDEN.faint, marginLeft: '0.4em', fontWeight: 400 }}>
                  · {m?.n ?? 0}{m?.share != null && ` (${(m.share * 100).toFixed(0)}%)`}
                </span>
                {hasSubject && <DeltaBadge pct={m?.delta_pct} />}
              </button>
            )
          })}
        </div>

        {/* Body: rows = inning values, each row has [label | cells container] */}
        {inningValues.map(iv => {
          return (
            <div key={iv} className="wisden-splits-row">
              {/* Row label */}
              <button
                type="button"
                onClick={() => setOne('inning', String(iv))}
                className="wisden-splits-marginal wisden-splits-row-label"
                title={`Filter to ${INNING_LABEL[String(iv) as '0' | '1']}`}
              >
                {INNING_LABEL[String(iv) as '0' | '1']}
                {hasSubject && (
                  <DeltaBadge pct={data.marginals.inning[String(iv) as '0' | '1']?.delta_pct} />
                )}
              </button>
              <div className="wisden-splits-cells-row">
              {tossValues.map((tv, idx) => {
                // For each (toss, inning) outer cell, sum across outcomes (when result free).
                const summedN = resultValues.reduce(
                  (s, rv) => s + (cellMap.get(`${tv}|${iv}|${rv}`)?.n ?? 0), 0,
                )
                // Column denominator for cell share = column total.
                const colTotal = tossN(tv)
                const cellShare = colTotal ? summedN / colTotal : null
                const cellOpacity = opacityForN(summedN)
                const cellDelta = (() => {
                  if (!hasSubject || resultValues.length !== 1) return null
                  const cell = cellMap.get(`${tv}|${iv}|${resultValues[0]}`)
                  return cell?.delta_pct ?? null
                })()
                return (
                  <div
                    key={tv}
                    className="wisden-splits-cell"
                    style={{ opacity: cellOpacity, flex: `${colWidths[idx]} 1 0` }}
                  >
                    {/* Inner sub-rects by outcome (when result is free) */}
                    <div
                      className="wisden-splits-cell-fills"
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        // Outer-cell click — set both toss + inning, leave result free.
                        setUrlParams({
                          toss_outcome: tv,
                          inning: String(iv),
                          result: filters.result || '',
                        })
                      }}
                      title={`Filter to ${TOSS_LABEL[tv]} · ${INNING_LABEL[String(iv) as '0' | '1']}`}
                    >
                      {resultValues.map(rv => {
                        const cell = cellMap.get(`${tv}|${iv}|${rv}`)
                        const cellN = cell?.n ?? 0
                        const sliceShare = summedN ? cellN / summedN : 0
                        const fill = r === null ? OUTCOME_COLOR[rv] : NEUTRAL_FILL
                        return (
                          <div
                            key={rv}
                            className="wisden-splits-subrect"
                            style={{ flexBasis: `${sliceShare * 100}%`, background: fill }}
                            onClick={(e) => {
                              // Sub-rect click — set ALL three filters.
                              e.stopPropagation()
                              setUrlParams({
                                toss_outcome: tv,
                                inning: String(iv),
                                result: rv,
                              })
                            }}
                            title={cell ? cellTooltip(cell, total, hasSubject) : `${RESULT_LEGEND[rv]} — 0 matches`}
                          />
                        )
                      })}
                    </div>
                    <div className="wisden-splits-cell-label">
                      <strong>{summedN}</strong>
                      <span style={{ color: WISDEN.faint, marginLeft: '0.4em', fontSize: '0.85em' }}>
                        {cellShare != null && `${(cellShare * 100).toFixed(0)}%`}
                      </span>
                      {hasSubject && cellDelta != null && <DeltaBadge pct={cellDelta} />}
                    </div>
                  </div>
                )
              })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Outcome legend (only when result is free) */}
      {r === null && (
        <div className="wisden-splits-legend">
          {(['won', 'tied', 'lost'] as Outcome[]).map(rv => {
            const m = data.marginals.result[rv]
            return (
              <button
                key={rv}
                type="button"
                onClick={() => setOne('result', rv)}
                className="wisden-splits-legend-item"
                title={`Filter to ${RESULT_LABEL[rv]}`}
              >
                <span
                  className="wisden-splits-legend-swatch"
                  style={{ background: OUTCOME_COLOR[rv] }}
                  aria-hidden="true"
                />
                {RESULT_LEGEND[rv]}
                <span style={{ color: WISDEN.faint, marginLeft: '0.3em', fontWeight: 400 }}>
                  · {m?.n ?? 0}{m?.share != null && ` (${(m.share * 100).toFixed(0)}%)`}
                </span>
                {hasSubject && <DeltaBadge pct={m?.delta_pct} />}
              </button>
            )
          })}
        </div>
      )}

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
  filters, total, subjectTeam, thinSample, setAux,
}: {
  filters: FilterParams; total: number; subjectTeam: string | null;
  thinSample: boolean; setAux: (o: Partial<Record<'result' | 'toss_outcome' | 'inning', string>>) => void;
}) {
  const hasAnyFilter = !!(filters.result || filters.toss_outcome || filters.inning)
  return (
    <div className="wisden-splits-strip">
      <span>{strip(filters, total, subjectTeam)}</span>
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
  marginals, freeAxis, hasSubject, setOne,
}: {
  marginals: TeamSplits['marginals']
  freeAxis: 'result' | 'toss_outcome' | 'inning'
  hasSubject: boolean
  setOne: (key: 'result' | 'toss_outcome' | 'inning', value: string) => void
}) {
  const entries = (() => {
    if (freeAxis === 'result') {
      return (['won', 'tied', 'lost'] as Outcome[]).map(k => ({
        key: k, label: RESULT_LEGEND[k], color: OUTCOME_COLOR[k],
        m: marginals.result[k],
      }))
    }
    if (freeAxis === 'toss_outcome') {
      return (['won', 'lost'] as const).map(k => ({
        key: k, label: TOSS_LABEL[k], color: WISDEN.indigo,
        m: marginals.toss_outcome[k],
      }))
    }
    return (['0', '1'] as const).map(k => ({
      key: k, label: INNING_LABEL[k], color: WISDEN.indigo,
      m: marginals.inning[k],
    }))
  })()
  const total = entries.reduce((s, e) => s + (e.m?.n ?? 0), 0) || 1
  return (
    <div className="wisden-splits-1d">
      {entries.map(e => {
        const n = e.m?.n ?? 0
        const w = n / total
        // No opacity-by-n here — at 1D dimensionality the bar IS the
        // viz; dimming would make small segments invisible AND
        // unclickable. The proportional width already encodes
        // sample size visually.
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
              {hasSubject && <DeltaBadge pct={e.m?.delta_pct} />}
            </span>
          </button>
        )
      })}
    </div>
  )
}
