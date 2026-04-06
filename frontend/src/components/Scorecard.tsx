import type { Scorecard } from '../types'
import InningsCard from './InningsCard'

interface Props {
  data: Scorecard
}

export default function ScorecardView({ data }: Props) {
  const { info, innings } = data
  const tossText = info.toss_winner && info.toss_decision
    ? `${info.toss_winner} won the toss and chose to ${info.toss_decision}`
    : null
  const dateText = info.dates && info.dates.length > 0
    ? info.dates.join(' – ')
    : null
  const venueText = [info.venue, info.city].filter(Boolean).join(', ')
  const stageText = info.stage || (info.match_number != null ? `Match ${info.match_number}` : null)

  return (
    <div className="mt-6">
      {/* Header */}
      <div className="bg-white rounded-lg border shadow-sm mb-4 p-4">
        <h2 className="text-xl font-bold text-gray-900">
          {info.teams[0]} vs {info.teams[1]}
        </h2>
        <div className="text-sm text-gray-600 mt-1">
          {[info.tournament, stageText, venueText, dateText].filter(Boolean).join(' · ')}
        </div>
        {tossText && (
          <div className="text-sm text-gray-700 mt-2">
            <span className="font-medium">Toss:</span> {tossText}
          </div>
        )}
        <div className="text-sm text-gray-900 mt-1 font-semibold">
          {info.result_text}
        </div>
        {info.player_of_match && info.player_of_match.length > 0 && (
          <div className="text-sm text-gray-700 mt-1">
            <span className="font-medium">Player of the Match:</span> {info.player_of_match.join(', ')}
          </div>
        )}
      </div>

      {/* Innings cards */}
      {innings.map((inn, i) => (
        <InningsCard key={i} innings={inn} />
      ))}

      {/* Officials (small footer) */}
      {info.officials && (
        <div className="text-xs text-gray-500 mt-2 px-4 py-2">
          {info.officials.umpires && (
            <div><span className="font-medium">Umpires:</span> {info.officials.umpires.join(', ')}</div>
          )}
          {info.officials.tv_umpires && (
            <div><span className="font-medium">TV Umpire:</span> {info.officials.tv_umpires.join(', ')}</div>
          )}
          {info.officials.match_referees && (
            <div><span className="font-medium">Match Referee:</span> {info.officials.match_referees.join(', ')}</div>
          )}
        </div>
      )}
    </div>
  )
}
