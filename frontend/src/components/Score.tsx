/**
 * A match's two scores on one line, as "185/6 │ 180/5".
 */
import { Link } from 'react-router-dom'

/** Props of `Score`. */
type Props = {
  team1Score: string | null | undefined // the first team's score, as "185/6"; "—" when absent
  team2Score: string | null | undefined // the second team's score; "—" when absent
  matchId?: number | null // when set, the score links to that match's scorecard
  title?: string // the tooltip
}

/** Compact innings-score renderer — "185/6 │ 180/5" with a thin
 *  box-drawings vertical between teams (U+2502). When `matchId` is
 *  passed, the whole score becomes a `comp-link` to the scorecard. */
export default function Score({ team1Score, team2Score, matchId, title }: Props) {
  const s1 = team1Score ?? '—'
  const s2 = team2Score ?? '—'
  const body = (
    <span className="num">
      {s1}
      <span className="wisden-score-sep"> │ </span>
      {s2}
    </span>
  )
  if (matchId != null) {
    return (
      <Link to={`/matches/${matchId}`} className="comp-link" title={title}>
        {body}
      </Link>
    )
  }
  return title ? <span title={title}>{body}</span> : body
}
