import { useEffect } from 'react'
import { useFilters } from '../hooks/useFilters'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import PlayerSearch from '../components/PlayerSearch'
import PlayerProfile from '../components/players/PlayerProfile'
import PlayersLanding from '../components/players/PlayersLanding'
import PlayerCompareGrid from '../components/players/PlayerCompareGrid'
import AddComparePicker from '../components/players/AddComparePicker'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { getPlayerProfile } from '../api'
import type { PlayerSearchResult, PlayerProfile as PlayerProfileT } from '../types'

export default function Players() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const [compareCsv] = useUrlParam('compare')
  const setUrlParams = useSetUrlParams()

  const compareIds = compareCsv
    ? compareCsv.split(',').map(s => s.trim()).filter(Boolean).slice(0, 2)
    : []
  const isCompare = playerId && compareIds.length > 0

  const handleSelect = (p: PlayerSearchResult) => {
    setUrlParams({ player: p.id })
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <PlayerSearch onSelect={handleSelect} placeholder="Search for a player…" />
      </div>

      {!playerId && <PlayersLanding filters={filters} />}

      {playerId && !isCompare && (
        <>
          <SinglePlayerView playerId={playerId} />
          <AddComparePicker currentIds={[playerId]} gender={filters.gender} />
        </>
      )}

      {playerId && isCompare && (
        <>
          <PlayerCompareGrid ids={[playerId, ...compareIds]} filters={filters} />
          <AddComparePicker
            currentIds={[playerId, ...compareIds]}
            gender={filters.gender}
          />
        </>
      )}
    </div>
  )
}

// ─── Single-player mode ─────────────────────────────────────────────

function SinglePlayerView({ playerId }: { playerId: string }) {
  const filters = useFilters()
  const setUrlParams = useSetUrlParams()

  const filterDeps = [
    playerId, filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_team, filters.filter_opponent,
    filters.filter_venue,
  ]

  const profileFetch = useFetch<PlayerProfileT | null>(
    () => getPlayerProfile(playerId, filters),
    filterDeps,
  )
  const profile = profileFetch.data

  // Pick the best identity source (name + flags) — the discipline
  // sub-summaries all carry the same person metadata; whichever
  // loaded first wins. Specialist batters have null bowling, etc.
  const identity = profile
    ? (profile.batting ?? profile.bowling ?? profile.fielding)
    : null
  const name = identity?.name ?? ''
  const nationalities = identity?.nationalities ?? []

  useDocumentTitle(name || 'Players')

  // Self-correcting deep link — same pattern as pages/Batting.tsx:73.
  // If the URL has ?player=X without a gender, and the player's
  // international appearances are unambiguous, fill gender via
  // `replace` so the auto-correction doesn't pollute history.
  useEffect(() => {
    if (!identity || filters.gender) return
    const g = nationalities[0]?.gender
    const allSame = nationalities.every(n => n.gender === g)
    if (g && allSame) setUrlParams({ gender: g }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity, filters.gender])

  if (profileFetch.loading && !profile) return <Spinner label="Loading player…" size="lg" />
  if (profileFetch.error) {
    return <ErrorBanner
      message={`Could not load player: ${profileFetch.error}`}
      onRetry={profileFetch.refetch}
    />
  }
  if (!profile || !identity) {
    return <div className="wisden-empty">Player not found.</div>
  }

  return (
    <PlayerProfile
      profile={profile}
      playerId={playerId}
      name={name}
      nationalities={nationalities}
      filters={filters}
    />
  )
}

// ─── Placeholders (landed / compare) — filled in next phases ────────

