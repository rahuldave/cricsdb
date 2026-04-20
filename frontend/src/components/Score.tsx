import { Link } from 'react-router-dom'

type Props = {
  team1Score: string | null | undefined
  team2Score: string | null | undefined
  matchId?: number | null
  title?: string
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
