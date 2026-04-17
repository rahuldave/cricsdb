import { useState } from 'react'
import TeamSearch from '../TeamSearch'
import { useSetUrlParams } from '../../hooks/useUrlState'
import { getTeamSummary } from '../../api'
import type { FilterParams } from '../../types'

interface Props {
  /** Currently-compared team names (incl. primary). Used to dedupe
   *  and cap additions at 3 total. */
  currentTeams: string[]
  /** Current FilterBar scope. The candidate's scope-match count is
   *  probed against this — teams with zero matches in scope are
   *  refused in-place rather than silently added as empty columns. */
  filters: FilterParams
}

export default function AddTeamComparePicker({ currentTeams, filters }: Props) {
  const setUrlParams = useSetUrlParams()
  const [err, setErr] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  if (currentTeams.length >= 3) return null   // cap at three total

  const handleSelect = async (name: string) => {
    setErr(null)
    if (currentTeams.includes(name)) {
      setErr('Team already in comparison.')
      return
    }
    // Defence-in-depth: the TeamSearch dropdown already inherits the
    // FilterBar scope (gender + team_type), so cross-type / cross-gender
    // teams can't be surfaced in the results. But a URL-paste or a
    // race between mount and FilterBar auto-narrow could slip through.
    // Probe scope-match count — zero matches means the team exists but
    // not in the current filter scope.
    setChecking(true)
    try {
      const s = await getTeamSummary(name, filters)
      if ((s.matches ?? 0) < 1) {
        setErr(
          `${name} has no matches in the current filter scope — ` +
          'check gender, team-type, tournament, and season filters.',
        )
        return
      }
    } catch {
      // Probe failed — allow the add rather than block silently.
    } finally {
      setChecking(false)
    }
    // Primary stays in `team`; compares go in `compare` CSV.
    const compares = [...currentTeams.slice(1), name]
    setUrlParams({ compare: compares.join(',') })
  }

  const label = currentTeams.length === 1
    ? 'Compare with another team…'
    : '+ Add another team to compare…'

  return (
    <div className="wisden-compare-picker">
      <TeamSearch onSelect={handleSelect} placeholder={label} />
      {checking && <div className="wisden-compare-picker-err">Checking…</div>}
      {err && <div className="wisden-compare-picker-err">{err}</div>}
    </div>
  )
}
