import type {
  TeamProfile, ScopeAverageProfile,
  MetricEnvelope,
} from '../../types'
import MetricDelta from '../MetricDelta'

interface Props {
  profile: TeamProfile | ScopeAverageProfile
  /** Drives small-sample suppression on the average column. Team
   *  columns never suppress — the user asked about *this* team, so
   *  show what we have. */
  isAverage?: boolean
  placeholder?: boolean
}

const SAMPLE_SUPPRESS_THRESHOLD = 30

const fmt1 = (v: number | null | undefined) => v == null ? '-' : v.toFixed(1)

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

export default function PartnershipByWicketRows({
  profile, isAverage = false, placeholder = false,
}: Props) {
  if (placeholder) return null
  const rows = getRows(profile)
  if (!rows || rows.length === 0) return null

  const sorted = [...rows].sort((a, b) => a.wicket_number - b.wicket_number)

  return (
    <dl className="wisden-player-compact wisden-partnership-wickets">
      {sorted.map(r => {
        const wn = r.wicket_number
        const label = ORDINAL[wn] ?? `${wn}th`
        const nVal = rv(r.n) ?? 0
        const suppress = isAverage && nVal < SAMPLE_SUPPRESS_THRESHOLD
        if (suppress) {
          return (
            <div key={wn} className="wisden-player-compact-row">
              <dt>{label} wkt</dt>
              <dd
                className="num"
                title={`Only ${nVal} partnerships at the ${label.toLowerCase()} wicket in scope — too few to baseline meaningfully`}
                style={{ opacity: 0.4 }}
              >
                —
              </dd>
            </div>
          )
        }
        return (
          <div key={wn} className="wisden-player-compact-row">
            <dt>{label} wkt</dt>
            <dd className="num">
              {fmt1(rv(r.avg_runs))}
              <span style={{ fontSize: '0.75em', marginLeft: '0.4rem' }}>
                <MetricDelta env={env(r.avg_runs)} />
              </span>
              <span style={{ opacity: 0.55, marginLeft: '0.4rem', fontSize: '0.85em' }}>
                · n {nVal} / hi {r.best_runs ?? '-'}
              </span>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
