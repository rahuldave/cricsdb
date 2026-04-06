import { Link } from 'react-router-dom'
import type { ScorecardInnings } from '../types'

interface Props {
  innings: ScorecardInnings
  /**
   * URL query string fragment to append to player page links so the
   * destination opens pre-filtered to this match's context (gender,
   * team_type, tournament). Should NOT start with `?` or `&`.
   */
  linkParams?: string
}

export default function InningsCard({ innings, linkParams = '' }: Props) {
  const batterHref = (id: string | null) =>
    id ? `/batting?player=${encodeURIComponent(id)}${linkParams ? '&' + linkParams : ''}` : null
  const bowlerHref = (id: string | null) =>
    id ? `/bowling?player=${encodeURIComponent(id)}${linkParams ? '&' + linkParams : ''}` : null
  const h2hHref = (batterId: string | null, bowlerId: string | null) =>
    batterId && bowlerId
      ? `/head-to-head?batter=${encodeURIComponent(batterId)}&bowler=${encodeURIComponent(bowlerId)}${linkParams ? '&' + linkParams : ''}`
      : null
  const linkClass = 'text-blue-600 hover:underline'
  return (
    <div className="bg-white rounded-lg border shadow-sm mb-4">
      <div className="flex items-baseline justify-between border-b border-gray-200 px-4 py-2 bg-gray-50 rounded-t-lg">
        <h3 className="font-semibold text-gray-900">{innings.label}</h3>
        <div className="text-sm text-gray-700">
          <span className="font-bold text-gray-900">{innings.total_runs}/{innings.wickets}</span>
          <span className="text-gray-500"> ({innings.overs} ov, RR {innings.run_rate.toFixed(2)})</span>
        </div>
      </div>

      {/* Batting */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-200">
              <th className="px-4 py-2 font-medium">Batter</th>
              <th className="px-4 py-2 font-medium">Dismissal</th>
              <th className="px-2 py-2 font-medium text-right">R</th>
              <th className="px-2 py-2 font-medium text-right">B</th>
              <th className="px-2 py-2 font-medium text-right">4s</th>
              <th className="px-2 py-2 font-medium text-right">6s</th>
              <th className="px-2 py-2 font-medium text-right">SR</th>
            </tr>
          </thead>
          <tbody>
            {innings.batting.map(b => (
              <tr key={`${b.person_id}-${b.name}`} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-1.5 font-medium text-gray-900">
                  {batterHref(b.person_id)
                    ? <Link to={batterHref(b.person_id)!} className={linkClass}>{b.name}</Link>
                    : b.name}
                </td>
                <td className="px-4 py-1.5 text-gray-600 italic">
                  {h2hHref(b.person_id, b.dismissal_bowler_id)
                    ? <Link
                        to={h2hHref(b.person_id, b.dismissal_bowler_id)!}
                        className="text-gray-600 hover:text-blue-600 hover:underline"
                        title="View head-to-head"
                      >{b.dismissal}</Link>
                    : b.dismissal}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums font-semibold">{b.runs}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{b.balls}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{b.fours}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{b.sixes}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-gray-600">{b.strike_rate.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Extras + Total */}
      <div className="px-4 py-2 text-sm border-t border-gray-200 bg-gray-50">
        <div className="flex justify-between text-gray-700">
          <span>
            <span className="font-medium">Extras</span>
            <span className="text-gray-500 ml-2">
              (b {innings.extras.byes}, lb {innings.extras.legbyes}, w {innings.extras.wides}, nb {innings.extras.noballs}
              {innings.extras.penalty > 0 ? `, p ${innings.extras.penalty}` : ''})
            </span>
          </span>
          <span className="font-semibold tabular-nums">{innings.extras.total}</span>
        </div>
        <div className="flex justify-between mt-1 text-gray-900 font-semibold">
          <span>Total</span>
          <span className="tabular-nums">
            {innings.total_runs}/{innings.wickets} ({innings.overs} ov)
          </span>
        </div>
      </div>

      {/* Did not bat */}
      {innings.did_not_bat.length > 0 && (
        <div className="px-4 py-2 text-sm text-gray-600 border-t border-gray-200">
          <span className="font-medium text-gray-700">Did not bat:</span> {innings.did_not_bat.join(', ')}
        </div>
      )}

      {/* Fall of wickets */}
      {innings.fall_of_wickets.length > 0 && (
        <div className="px-4 py-2 text-sm text-gray-600 border-t border-gray-200">
          <span className="font-medium text-gray-700">Fall of wickets:</span>{' '}
          {innings.fall_of_wickets.map((w, i) => (
            <span key={w.wicket}>
              {i > 0 ? ', ' : ''}
              {w.score}-{w.wicket} ({w.batter}, {w.over_ball} ov)
            </span>
          ))}
        </div>
      )}

      {/* Bowling */}
      <div className="overflow-x-auto border-t border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-200">
              <th className="px-4 py-2 font-medium">Bowler</th>
              <th className="px-2 py-2 font-medium text-right">O</th>
              <th className="px-2 py-2 font-medium text-right">M</th>
              <th className="px-2 py-2 font-medium text-right">R</th>
              <th className="px-2 py-2 font-medium text-right">W</th>
              <th className="px-2 py-2 font-medium text-right">Econ</th>
              <th className="px-2 py-2 font-medium text-right">wd</th>
              <th className="px-2 py-2 font-medium text-right">nb</th>
            </tr>
          </thead>
          <tbody>
            {innings.bowling.map(b => (
              <tr key={`${b.person_id}-${b.name}`} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-1.5 font-medium text-gray-900">
                  {bowlerHref(b.person_id)
                    ? <Link to={bowlerHref(b.person_id)!} className={linkClass}>{b.name}</Link>
                    : b.name}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">{b.overs}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{b.maidens}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{b.runs}</td>
                <td className="px-2 py-1.5 text-right tabular-nums font-semibold">{b.wickets}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-gray-600">{b.econ.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-gray-500">{b.wides}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-gray-500">{b.noballs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
