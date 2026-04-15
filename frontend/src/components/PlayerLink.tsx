/**
 * PlayerLink — standardises the two-job link pattern for player names.
 *
 *   Name link: always goes to /batting|/bowling|/fielding with just
 *              player + gender set. No inherited narrowing filters.
 *              "Show me this player" intent — consistent everywhere
 *              so users learn one rule.
 *
 *   Context link (optional): goes to the same page with additional
 *              filter params attached. Rendered as an italic faint
 *              suffix (`· at RCB ›`) that self-documents the lens.
 *
 * Scorecards / dense tables skip the context link to avoid clutter.
 * Landing leaderboards skip the context entirely (season range isn't
 * a durable lens — it's a finder filter).
 */
import { Link } from 'react-router-dom'

type PlayerRole = 'batter' | 'bowler' | 'fielder'

const ROLE_PATH: Record<PlayerRole, string> = {
  batter: '/batting',
  bowler: '/bowling',
  fielder: '/fielding',
}

interface PlayerLinkProps {
  personId: string | null | undefined
  name: string
  role: PlayerRole
  /** Pre-set gender on both links so the player's page scopes correctly.
   *  From the context's nationalities list or the current FilterBar. */
  gender?: string | null
  /** Text shown after `·` to advertise the contextual view.
   *  E.g. "at Royal Challengers Bengaluru" / "in Indian Premier League". */
  contextLabel?: string
  /** Extra query params appended to the contextual link (gender already
   *  handled). E.g. { filter_team: 'Royal Challengers Bengaluru' }. */
  contextParams?: Record<string, string>
  /** Hide the context link in dense tables (e.g. scorecard rows). */
  compact?: boolean
}

export default function PlayerLink({
  personId, name, role, gender,
  contextLabel, contextParams, compact,
}: PlayerLinkProps) {
  if (!personId) return <>{name}</>
  const path = ROLE_PATH[role]

  const base = new URLSearchParams({ player: personId })
  if (gender) base.set('gender', gender)
  const nameHref = `${path}?${base.toString()}`

  if (compact || !contextLabel || !contextParams) {
    return <Link to={nameHref} className="comp-link">{name}</Link>
  }

  const ctx = new URLSearchParams(base)
  for (const [k, v] of Object.entries(contextParams)) ctx.set(k, v)
  const ctxHref = `${path}?${ctx.toString()}`

  return (
    <>
      <Link to={nameHref} className="comp-link">{name}</Link>
      {' '}
      <Link
        to={ctxHref}
        className="comp-link"
        style={{ fontStyle: 'italic', fontSize: '0.85em', opacity: 0.75 }}
      >
        · {contextLabel} ›
      </Link>
    </>
  )
}
