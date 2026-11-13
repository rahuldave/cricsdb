/**
 * One player's profile page: name and flags, role, teams, the opponent filter, a summary row per discipline, and records.
 */
import type { ReactNode } from 'react'
import FlagBadge from '../FlagBadge'
import ScopeIndicator from '../ScopeIndicator'
import ScopedPageHeader from '../ScopedPageHeader'
import PlayerSummaryRow, { disciplineHasData } from './PlayerSummaryRow'
import { classifyRole, matchesInScope } from './roleUtils'
import PlayerRecordsSummary from './PlayerRecordsSummary'
import PlayerTeamsStrip from './PlayerTeamsStrip'
import PlayerOpponentFilter from './PlayerOpponentFilter'
import type { PlayerProfile as PlayerProfileT, FilterParams } from '../../types'

/** Props of `PlayerProfile`. */
interface Props {
  profile: PlayerProfileT // the player's batting, bowling, fielding and keeping summaries in scope
  playerId: string // the player's person ID
  /** Best-effort person name + nationalities. Pulled from whichever
   *  sub-summary loaded first — they all carry the same identity. */
  name: string
  nationalities: { team: string; gender: string }[] // the teams whose flags show beside the name
  filters: FilterParams // the scope
  /** Hide ScopeIndicator when the column is embedded in a compare
   *  grid (the grid shows the scope pill once, above the columns). */
  suppressScopePill?: boolean
  /** Optional node rendered as the trailing cell of the records grid.
   *  Used by single-player view to slot the "Compare with another
   *  player" picker alongside the discipline records panels. */
  recordsTrailingSlot?: ReactNode
}

/**
 * Show one player's profile in scope; a "No matches in scope" message when no discipline has data.
 */
export default function PlayerProfile({
  profile, playerId, name, nationalities, filters, suppressScopePill = false,
  recordsTrailingSlot,
}: Props) {
  const role = classifyRole(profile)
  const matches = matchesInScope(profile)
  const noData = !disciplineHasData('batting',  profile)
             && !disciplineHasData('bowling',  profile)
             && !disciplineHasData('fielding', profile)
             && !disciplineHasData('keeping',  profile)

  return (
    <div>
      <ScopedPageHeader filters={filters}>
        {name}
        {nationalities.length > 0 && (
          <span style={{ display: 'inline-flex', gap: '0.35rem', alignItems: 'center' }}>
            {nationalities.map(n => (
              <FlagBadge key={`${n.team}-${n.gender}`} team={n.team} gender={n.gender} size="lg" linkTo />
            ))}
          </span>
        )}
      </ScopedPageHeader>
      {!suppressScopePill && <ScopeIndicator filters={filters} />}
      <div className="wisden-player-identity">
        <em>{role}</em>
      </div>

      {noData ? (
        <div className="wisden-empty" style={{ marginTop: '2rem' }}>
          No matches in scope. Broaden the filters above or clear the scope to see this player's full career.
        </div>
      ) : (
        <>
          <PlayerTeamsStrip playerId={playerId} filters={filters} />
          <PlayerOpponentFilter playerId={playerId} filters={filters} />
          {matches > 0 && (
            <div className="wisden-overall-matches">
              <span className="wisden-overall-matches-label">Matches in scope</span>
              <span className="wisden-overall-matches-value num">{matches.toLocaleString()}</span>
            </div>
          )}
          {disciplineHasData('batting',  profile) &&
            <PlayerSummaryRow discipline="batting"  profile={profile} playerId={playerId} filters={filters} />}
          {disciplineHasData('bowling',  profile) &&
            <PlayerSummaryRow discipline="bowling"  profile={profile} playerId={playerId} filters={filters} />}
          {disciplineHasData('fielding', profile) &&
            <PlayerSummaryRow discipline="fielding" profile={profile} playerId={playerId} filters={filters} />}
          {disciplineHasData('keeping',  profile) &&
            <PlayerSummaryRow discipline="keeping"  profile={profile} playerId={playerId} filters={filters} />}

          <PlayerRecordsSummary
            playerId={playerId}
            filters={filters}
            hasBatting={disciplineHasData('batting', profile)}
            hasBowling={disciplineHasData('bowling', profile)}
            hasFielding={disciplineHasData('fielding', profile) || disciplineHasData('keeping', profile)}
            trailingSlot={recordsTrailingSlot}
          />
        </>
      )}
    </div>
  )
}
