import type { CSSProperties } from 'react'
import type {
  TeamProfile, ScopeAverageProfile,
  MetricEnvelope,
} from '../../types'
import MetricDelta from '../MetricDelta'

interface Props {
  profile: TeamProfile | ScopeAverageProfile
  /** Avg-column flag (no longer used for suppression — kept for
   *  prop-shape stability with prior callers). After Commit 5 of
   *  spec-avg-column-per-innings.md, the `· n` substat is per-innings
   *  on both columns; tiny rates at late wickets (e.g. n=0.11 at 10th)
   *  convey rarity directly without suppression. */
  isAverage?: boolean
  placeholder?: boolean
}

const fmt1 = (v: number | null | undefined) => v == null ? '-' : v.toFixed(1)
const fmt2 = (v: number | null | undefined) => v == null ? '-' : v.toFixed(2)

/** Either flat number or `.value` off an envelope. */
function rv(x: number | MetricEnvelope | null | undefined): number | null {
  if (x == null) return null
  if (typeof x === 'number') return x
  return x.value
}
function env(x: number | MetricEnvelope | null | undefined): MetricEnvelope | null {
  if (x == null || typeof x === 'number') return null
  return x
}

interface WicketRow {
  wicket_number: number
  n: number | MetricEnvelope
  avg_runs: number | MetricEnvelope | null
  avg_balls: number | null
  best_runs: number | null
}

function getRows(profile: TeamProfile | ScopeAverageProfile): WicketRow[] | null {
  const obj = profile.partnerships_by_wicket
  if (!obj) return null
  return (obj.by_wicket as unknown) as WicketRow[]
}

const ORDINAL: Record<number, string> = {
  1: '1st', 2: '2nd', 3: '3rd', 4: '4th', 5: '5th',
  6: '6th', 7: '7th', 8: '8th', 9: '9th', 10: '10th',
}

// 10 wickets per innings is fixed by the rules of cricket. Used as
// the subgrid row span so the dl reserves 10 tracks of the parent
// grid in EVERY column — including placeholder cols, which return an
// empty dl that still occupies all 10 row tracks so subsequent rows
// (none, since this is the last section) stay row-aligned.
const BY_WICKET_ROWS = 10

const BY_WICKET_SUBGRID_STYLE: CSSProperties = {
  display: 'grid',
  gridTemplateRows: 'subgrid',
  gridRow: `span ${BY_WICKET_ROWS}`,
}

export default function PartnershipByWicketRows({
  profile, isAverage: _isAverage = false, placeholder = false,
}: Props) {
  if (placeholder) {
    return <dl className="wisden-player-compact wisden-partnership-wickets" style={BY_WICKET_SUBGRID_STYLE} />
  }
  const rows = getRows(profile)
  if (!rows || rows.length === 0) {
    return <dl className="wisden-player-compact wisden-partnership-wickets" style={BY_WICKET_SUBGRID_STYLE} />
  }

  // Per-innings divisor for `· n` substat (team side; avg side
  // already comes through per-innings post-Commit 2). Source:
  // batting.innings_batted on TeamProfile (envelope), or null on
  // ScopeAverageProfile (where n is already per-innings).
  const battingSec = profile.batting as
    | { innings_batted?: number | { value: number | null } }
    | null
    | undefined
  const innRaw = battingSec?.innings_batted
  const teamInnsBatted: number | null =
    innRaw == null ? null
    : typeof innRaw === 'number' ? innRaw
    : innRaw.value ?? null
  const teamSide = innRaw != null && typeof innRaw !== 'number'

  const sorted = [...rows].sort((a, b) => a.wicket_number - b.wicket_number)

  return (
    <dl
      className="wisden-player-compact wisden-partnership-wickets"
      style={BY_WICKET_SUBGRID_STYLE}
    >
      {sorted.map(r => {
        const wn = r.wicket_number
        const label = ORDINAL[wn] ?? `${wn}th`
        const nRaw = rv(r.n) ?? 0
        // Convert pool count to per-innings on team side; avg side
        // already arrives per-innings.
        const nPerInn = teamSide && teamInnsBatted && teamInnsBatted > 0
          ? Math.round((nRaw / teamInnsBatted) * 100) / 100
          : nRaw
        return (
          <div key={wn} className="wisden-player-compact-row">
            <dt>{label} wkt</dt>
            <dd className="num">
              {fmt1(rv(r.avg_runs))}
              <span style={{ fontSize: '0.75em', marginLeft: '0.4rem' }}>
                <MetricDelta env={env(r.avg_runs)} />
              </span>
              <span style={{ opacity: 0.55, marginLeft: '0.4rem', fontSize: '0.85em' }}>
                · n {fmt2(nPerInn)}/inn / hi {r.best_runs ?? '-'}
              </span>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
