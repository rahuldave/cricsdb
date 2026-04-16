import { useState } from 'react'
import PlayerSearch from '../PlayerSearch'
import { useSetUrlParams } from '../../hooks/useUrlState'
import { getBatterSummary } from '../../api'
import type { PlayerSearchResult } from '../../types'

interface Props {
  /** Currently-compared IDs (incl. primary). Used to dedupe and to
   *  cap additions at 3. */
  currentIds: string[]
  /** Current `gender` scope from the URL. If set, blocks cross-gender
   *  adds — the page's auto-gender-fill comes off the primary, so any
   *  compared player must share that gender. */
  gender: string | undefined
}

export default function AddComparePicker({ currentIds, gender }: Props) {
  const setUrlParams = useSetUrlParams()
  const [err, setErr] = useState<string | null>(null)

  if (currentIds.length >= 3) return null   // cap at three players total

  const handleSelect = async (p: PlayerSearchResult) => {
    setErr(null)
    if (currentIds.includes(p.id)) {
      setErr('Player already in comparison.')
      return
    }
    // Gender-match gate. A candidate whose nationalities are all the
    // OTHER gender can't be added under the current scope. Use batter
    // summary (no filters) as the cheapest identity probe — every
    // player has a batter row that carries nationalities, even if
    // innings=0 for specialist bowlers.
    if (gender) {
      try {
        const s = await getBatterSummary(p.id)
        const g = s.nationalities?.[0]?.gender
        const allSame = s.nationalities?.every(n => n.gender === g)
        if (g && allSame && g !== gender) {
          setErr(
            `Can't compare across genders. ${p.name} is a ${g === 'female' ? "women's" : "men's"} player; the current scope is ${gender === 'female' ? "women's" : "men's"}.`,
          )
          return
        }
      } catch { /* probe failed — allow rather than block silently */ }
    }
    // Append to compare CSV. Primary stays in `player`; the rest go in
    // `compare`.
    const compareIds = [...currentIds.slice(1), p.id]
    setUrlParams({ compare: compareIds.join(',') })
  }

  const label = currentIds.length === 1
    ? 'Compare with another player…'
    : '+ Add another player to compare…'

  return (
    <div className="wisden-compare-picker">
      <PlayerSearch onSelect={handleSelect} placeholder={label} />
      {err && <div className="wisden-compare-picker-err">{err}</div>}
    </div>
  )
}
