import FlagBadge from '../FlagBadge'
import ScopeIndicator from '../ScopeIndicator'
import PlayerSummaryRow, { disciplineHasData } from './PlayerSummaryRow'
import { classifyRole, matchesInScope } from './roleUtils'
import type { PlayerProfile as PlayerProfileT, FilterParams } from '../../types'

interface Props {
  profile: PlayerProfileT
  playerId: string
  /** Best-effort person name + nationalities. Pulled from whichever
   *  sub-summary loaded first — they all carry the same identity. */
  name: string
  nationalities: { team: string; gender: string }[]
  filters: FilterParams
  /** Hide ScopeIndicator when the column is embedded in a compare
   *  grid (the grid shows the scope pill once, above the columns). */
  suppressScopePill?: boolean
}

export default function PlayerProfile({
  profile, playerId, name, nationalities, filters, suppressScopePill = false,
}: Props) {
  const role = classifyRole(profile)
  const matches = matchesInScope(profile)
  const noData = !disciplineHasData('batting',  profile)
             && !disciplineHasData('bowling',  profile)
             && !disciplineHasData('fielding', profile)
             && !disciplineHasData('keeping',  profile)

  return (
    <div>
      <h2 className="wisden-page-title">
        {name}
        {nationalities.length > 0 && (
          <span style={{ marginLeft: '0.6rem', display: 'inline-flex', gap: '0.35rem', alignItems: 'center' }}>
            {nationalities.map(n => (
              <FlagBadge key={`${n.team}-${n.gender}`} team={n.team} gender={n.gender} size="lg" linkTo />
            ))}
          </span>
        )}
      </h2>
      {!suppressScopePill && <ScopeIndicator filters={filters} />}
      <div className="wisden-player-identity">
        <em>{role}</em>
        {matches > 0 && <> · <span className="num">{matches}</span> matches</>}
      </div>

      {noData ? (
        <div className="wisden-empty" style={{ marginTop: '2rem' }}>
          No matches in scope. Broaden the filters above or clear the scope to see this player's full career.
        </div>
      ) : (
        <>
          {disciplineHasData('batting',  profile) &&
            <PlayerSummaryRow discipline="batting"  profile={profile} playerId={playerId} filters={filters} />}
          {disciplineHasData('bowling',  profile) &&
            <PlayerSummaryRow discipline="bowling"  profile={profile} playerId={playerId} filters={filters} />}
          {disciplineHasData('fielding', profile) &&
            <PlayerSummaryRow discipline="fielding" profile={profile} playerId={playerId} filters={filters} />}
          {disciplineHasData('keeping',  profile) &&
            <PlayerSummaryRow discipline="keeping"  profile={profile} playerId={playerId} filters={filters} />}
        </>
      )}
    </div>
  )
}
