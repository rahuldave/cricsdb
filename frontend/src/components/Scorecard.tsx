import type { ReactNode } from 'react'
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
  const tossText = info.toss_winner && info.toss_decision
    ? `${info.toss_winner} won the toss and chose to ${info.toss_decision}`
    : null
  const dateText = info.dates && info.dates.length > 0
    ? info.dates.join(' – ')
    : null
  const venueText = [info.venue, info.city].filter(Boolean).join(', ')
  const stageText = info.stage || (info.match_number != null ? `Match ${info.match_number}` : null)

  const linkParams = (() => {
    const params = new URLSearchParams()
    if (info.gender) params.set('gender', info.gender)
    if (info.team_type) params.set('team_type', info.team_type)
    if (info.tournament) params.set('tournament', info.tournament)
    return params.toString()
  })()

  return (
    <div>
      <div className="wisden-match-header">
        <h2>
          {info.teams[0]} <span className="vs">v</span> {info.teams[1]}
        </h2>
        <div className="wisden-match-meta">
          {[info.tournament, stageText, venueText, dateText].filter(Boolean).join(' · ')}
        </div>
        <div className="wisden-match-result">{info.result_text}</div>
        {tossText && (
          <div className="wisden-match-extra">
            <span className="lbl">Toss</span>{tossText}
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
