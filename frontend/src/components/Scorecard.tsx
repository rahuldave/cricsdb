import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Scorecard } from '../types'
import InningsCard from './InningsCard'

interface Props {
  data: Scorecard
  /** Optional content rendered between the header and the innings cards (e.g. charts). */
  children?: ReactNode
  highlightBatterId?: string | null
  highlightBowlerId?: string | null
  highlightFielderId?: string | null
}

export default function ScorecardView({ data, children, highlightBatterId, highlightBowlerId, highlightFielderId }: Props) {
  const { info, innings } = data
  const tossNode: ReactNode = info.toss_winner && info.toss_decision
    ? (
      <>
        <Link to={`/teams?team=${encodeURIComponent(info.toss_winner)}${info.gender ? `&gender=${info.gender}` : ''}${info.team_type ? `&team_type=${info.team_type}` : ''}`}
          className="comp-link">{info.toss_winner}</Link>
        {` won the toss and chose to ${info.toss_decision}`}
      </>
    )
    : null
  const dateText = info.dates && info.dates.length > 0
    ? info.dates.join(' – ')
    : null
  const venueNode: ReactNode = info.venue
    ? (
      <>
        <Link to={`/matches?filter_venue=${encodeURIComponent(info.venue)}`}
          className="comp-link">{info.venue}</Link>
        {info.city && info.city !== info.venue && <>, {info.city}</>}
      </>
    )
    : info.city || null
  const stageText = info.stage || (info.match_number != null ? `Match ${info.match_number}` : null)

  const linkParams = (() => {
    const params = new URLSearchParams()
    if (info.gender) params.set('gender', info.gender)
    if (info.team_type) params.set('team_type', info.team_type)
    if (info.tournament) params.set('tournament', info.tournament)
    return params.toString()
  })()

  const teamHref = (t: string) => {
    const p = new URLSearchParams({ team: t })
    if (info.gender) p.set('gender', info.gender)
    if (info.team_type) p.set('team_type', info.team_type)
    if (info.tournament) p.set('tournament', info.tournament)
    return `/teams?${p.toString()}`
  }
  const tournamentHref = (() => {
    if (!info.tournament) return null
    const p = new URLSearchParams({ tournament: info.tournament })
    if (info.gender) p.set('gender', info.gender)
    if (info.team_type) p.set('team_type', info.team_type)
    return `/series?${p.toString()}`
  })()

  // Edition-scoped matches link: "2026" under T20 World Cup (Men)
  // → /matches?tournament=T20+World+Cup+(Men)&season_from=2026&season_to=2026.
  // Clicking lands on the match list for that specific edition.
  const seasonMatchesHref = (() => {
    if (!info.season) return null
    const p = new URLSearchParams()
    if (info.tournament) p.set('tournament', info.tournament)
    if (info.gender) p.set('gender', info.gender)
    if (info.team_type) p.set('team_type', info.team_type)
    p.set('season_from', info.season)
    p.set('season_to', info.season)
    return `/matches?${p.toString()}`
  })()

  return (
    <div>
      {/* Breadcrumb — sideways escape hatches for deep-linked arrivals.
          `← Back` lives on the page shell (uses history); this row
          gives explicit up/across links that work without history. */}
      <div className="wisden-match-breadcrumb">
        {tournamentHref && (
          <>
            <Link to={tournamentHref} className="comp-link">{info.tournament}</Link>
            <span className="sep"> › </span>
          </>
        )}
        {seasonMatchesHref && (
          <>
            <Link to={seasonMatchesHref} className="comp-link">{info.season}</Link>
            <span className="sep"> › </span>
          </>
        )}
        <Link to="/matches" className="comp-link">All matches</Link>
      </div>
      <div className="wisden-match-header">
        <h2>
          <Link to={teamHref(info.teams[0])} className="comp-link" style={{ fontSize: 'inherit', fontWeight: 'inherit' }}>
            {info.teams[0]}
          </Link>
          {' '}<span className="vs">v</span>{' '}
          <Link to={teamHref(info.teams[1])} className="comp-link" style={{ fontSize: 'inherit', fontWeight: 'inherit' }}>
            {info.teams[1]}
          </Link>
        </h2>
        <div className="wisden-match-meta">
          {tournamentHref ? (
            <Link to={tournamentHref} className="comp-link">{info.tournament}</Link>
          ) : info.tournament}
          {[stageText, venueNode, dateText].filter(Boolean).map((node, i) => (
            <span key={i}>
              {(info.tournament || i > 0) && ' · '}
              {node}
            </span>
          ))}
        </div>
        <div className="wisden-match-result">{info.result_text}</div>
        {tossNode && (
          <div className="wisden-match-extra">
            <span className="lbl">Toss</span>{tossNode}
          </div>
        )}
        {info.player_of_match && info.player_of_match.length > 0 && (
          <div className="wisden-match-extra">
            <span className="lbl">Player of the Match</span>{info.player_of_match.join(', ')}
          </div>
        )}
      </div>

      {children}

      {innings.map((inn, i) => (
        <InningsCard key={i} innings={inn} linkParams={linkParams}
          highlightBatterId={highlightBatterId}
          highlightBowlerId={highlightBowlerId}
          highlightFielderId={highlightFielderId} />
      ))}

      {info.officials && (
        <div className="wisden-match-extra" style={{ marginTop: '1.5rem' }}>
          {info.officials.umpires && (
            <div><span className="lbl">Umpires</span>{info.officials.umpires.join(', ')}</div>
          )}
          {info.officials.tv_umpires && (
            <div><span className="lbl">TV Umpire</span>{info.officials.tv_umpires.join(', ')}</div>
          )}
          {info.officials.match_referees && (
            <div><span className="lbl">Match Referee</span>{info.officials.match_referees.join(', ')}</div>
          )}
        </div>
      )}
    </div>
  )
}
