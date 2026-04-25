import { useState } from 'react'
import TeamSearch from '../TeamSearch'
import { getTeamSummary } from '../../api'
import type { FilterParams } from '../../types'

interface Props {
  /** Currently-rendered team names incl. primary. Used to dedupe
   *  and cap additions at 3 columns total (primary + 2 compares). */
  currentTeams: string[]
  /** Current FilterBar scope — used to probe the candidate's
   *  in-scope match count before adding. */
  filters: FilterParams
  /** True when the league-average column already occupies a slot;
   *  hides the "+ Add league average" button. */
  avgSlotPresent: boolean
  /** Add a team-kind compare slot; parent decides which slot
   *  (1 or 2) to write to. */
  onAddTeam: (name: string) => void
  /** Add an avg-kind compare slot in the next empty slot. */
  onAddAvg: () => void
}

export default function AddTeamComparePicker({
  currentTeams, filters, avgSlotPresent, onAddTeam, onAddAvg,
}: Props) {
  const [err, setErr] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  // Total columns = primary + filled compare slots. Cap at 3.
  const totalColumns = currentTeams.length + (avgSlotPresent ? 1 : 0)
  const slotsFull = totalColumns >= 3
  if (slotsFull) return null

  const teamSlotsFull = currentTeams.length >= 3 - (avgSlotPresent ? 1 : 0)

  const handleSelect = async (name: string) => {
    setErr(null)
    if (currentTeams.includes(name)) {
      setErr('Team already in comparison.')
      return
    }
    setChecking(true)
    try {
      const s = await getTeamSummary(name, filters)
      if ((s.matches?.value ?? 0) < 1) {
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
    onAddTeam(name)
  }

  const label = currentTeams.length === 1
    ? 'Compare with another team…'
    : '+ Add another team to compare…'

  return (
    <div className="wisden-compare-picker">
      {!teamSlotsFull && (
        <TeamSearch onSelect={handleSelect} placeholder={label} />
      )}
      {checking && <div className="wisden-compare-picker-err">Checking…</div>}
      {err && <div className="wisden-compare-picker-err">{err}</div>}
      {!avgSlotPresent && (
        <button
          type="button"
          className="comp-link wisden-compare-picker-avg-btn"
          onClick={onAddAvg}
          title="Add a league-average column scoped to the current filters"
          style={{
            background: 'none',
            border: 'none',
            padding: '0.4rem 0',
            cursor: 'pointer',
            textAlign: 'left',
            font: 'inherit',
          }}
        >
          + Add league average
        </button>
      )}
    </div>
  )
}
