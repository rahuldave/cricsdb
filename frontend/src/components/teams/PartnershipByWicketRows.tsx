import type {
  TeamProfile, ScopeAverageProfile,
  PartnershipByWicket, ScopePartnershipByWicket,
} from '../../types'

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

function getRows(
  profile: TeamProfile | ScopeAverageProfile,
): (PartnershipByWicket | ScopePartnershipByWicket)[] | null {
  const obj = profile.partnerships_by_wicket
  if (!obj) return null
  return obj.by_wicket as (PartnershipByWicket | ScopePartnershipByWicket)[]
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

  // Backend returns wickets 1..N in order. Defensive sort just in case.
  const sorted = [...rows].sort((a, b) => a.wicket_number - b.wicket_number)

  return (
    <dl className="wisden-player-compact wisden-partnership-wickets">
      {sorted.map(r => {
        const wn = r.wicket_number
        const label = ORDINAL[wn] ?? `${wn}th`
        // Small-sample suppression on the avg column when fewer than
        // 30 partnerships have formed at this wicket position in
        // scope (typical for 9th/10th wicket).
        const suppress = isAverage && (r.n ?? 0) < SAMPLE_SUPPRESS_THRESHOLD
        if (suppress) {
          return (
            <div key={wn} className="wisden-player-compact-row">
              <dt>{label} wkt</dt>
              <dd
                className="num"
                title={`Only ${r.n} partnerships at the ${label.toLowerCase()} wicket in scope — too few to baseline meaningfully`}
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
              {fmt1(r.avg_runs)}
              <span style={{ opacity: 0.55, marginLeft: '0.4rem', fontSize: '0.85em' }}>
                · n{r.n} / hi{r.best_runs ?? '-'}
              </span>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
