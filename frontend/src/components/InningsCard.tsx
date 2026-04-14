import { Link } from 'react-router-dom'
import type { ScorecardInnings } from '../types'

interface Props {
  innings: ScorecardInnings
  linkParams?: string
  highlightBatterId?: string | null
  highlightBowlerId?: string | null
  highlightFielderId?: string | null
}

export default function InningsCard({ innings, linkParams = '', highlightBatterId, highlightBowlerId, highlightFielderId }: Props) {
  // Scroll is handled at the page level in MatchScorecard — see the
  // useEffect there that queries the first `.is-highlighted` after all
  // async data (scorecard + innings grid) has loaded. Scrolling per-card
  // fires before sibling sections (charts, innings-grid) have sized, so
  // the target row ends up displaced once layout settles.

  const batterHref = (id: string | null) =>
    id ? `/batting?player=${encodeURIComponent(id)}${linkParams ? '&' + linkParams : ''}` : null
  const bowlerHref = (id: string | null) =>
    id ? `/bowling?player=${encodeURIComponent(id)}${linkParams ? '&' + linkParams : ''}` : null
  const h2hHref = (batterId: string | null, bowlerId: string | null) =>
    batterId && bowlerId
      ? `/head-to-head?batter=${encodeURIComponent(batterId)}&bowler=${encodeURIComponent(bowlerId)}${linkParams ? '&' + linkParams : ''}`
      : null

  const keeper = innings.keeper
  const keeperHref = (id: string | null) =>
    id ? `/fielding?player=${encodeURIComponent(id)}&tab=Keeping${linkParams ? '&' + linkParams : ''}` : null

  return (
    <div className="wisden-innings">
      <div className="wisden-innings-head">
        <h3>{innings.label}</h3>
        <div className="wisden-innings-score">
          <span className="big num">{innings.total_runs}/{innings.wickets}</span>
          <span className="meta num">({innings.overs} ov, RR {innings.run_rate.toFixed(2)})</span>
        </div>
      </div>

      {/* Keeper label (Tier 2) — above the batting table */}
      {keeper && (
        <div className="wisden-innings-aside" style={{ marginBottom: '0.5rem' }}>
          <span className="lbl">Keeper</span>
          {keeper.person_id ? (
            <>
              <Link to={keeperHref(keeper.person_id)!} className="comp-link">{keeper.name}</Link>
              <span style={{ color: 'var(--ink-faint)', fontSize: '0.75rem', marginLeft: '0.4rem', fontStyle: 'italic' }}>
                ({keeper.confidence})
              </span>
            </>
          ) : (
            <span style={{ fontStyle: 'italic' }}>
              ambiguous —{' '}
              {(keeper.candidate_ids || []).map((id, i) => {
                const name = keeper.candidate_names?.[i] || id
                return (
                  <span key={id}>
                    {i > 0 && ' or '}
                    <Link to={keeperHref(id)!} className="comp-link">{name}</Link>
                  </span>
                )
              })}
            </span>
          )}
        </div>
      )}

      {/* Batting */}
      <table>
        <thead>
          <tr>
            <th>Batter</th>
            <th>Dismissal</th>
            <th className="r">R</th>
            <th className="r">B</th>
            <th className="r">4s</th>
            <th className="r">6s</th>
            <th className="r">SR</th>
          </tr>
        </thead>
        <tbody>
          {innings.batting.map(b => {
            const isHL = !!(highlightBatterId && b.person_id === highlightBatterId)
              || !!(highlightFielderId && b.dismissal_fielder_ids?.includes(highlightFielderId))
            return (
              <tr key={`${b.person_id}-${b.name}`}
                className={isHL ? 'is-highlighted' : undefined}>
                <td className="pname">
                  {batterHref(b.person_id)
                    ? <Link to={batterHref(b.person_id)!}>{b.name}</Link>
                    : b.name}
                </td>
                <td className="dismissal">
                  {h2hHref(b.person_id, b.dismissal_bowler_id)
                    ? <Link to={h2hHref(b.person_id, b.dismissal_bowler_id)!} title="View head-to-head">{b.dismissal}</Link>
                    : b.dismissal}
                </td>
                <td className="r" style={{ color: 'var(--ink)', fontWeight: 600 }}>{b.runs}</td>
                <td className="r">{b.balls}</td>
                <td className="r">{b.fours}</td>
                <td className="r">{b.sixes}</td>
                <td className="r">{b.strike_rate.toFixed(2)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* Extras + Total */}
      <div className="wisden-innings-extras">
        <span>
          <span className="lbl">Extras</span>
          <span className="num">{innings.extras.total}</span>
          <span style={{ color: 'var(--ink-faint)', marginLeft: '0.4rem' }}>
            (b {innings.extras.byes}, lb {innings.extras.legbyes}, w {innings.extras.wides}, nb {innings.extras.noballs}
            {innings.extras.penalty > 0 ? `, p ${innings.extras.penalty}` : ''})
          </span>
        </span>
      </div>
      <div className="wisden-innings-extras total-row">
        <span>Total</span>
        <span className="num">{innings.total_runs}/{innings.wickets} ({innings.overs} ov)</span>
      </div>

      {innings.did_not_bat.length > 0 && (
        <div className="wisden-innings-aside">
          <span className="lbl">Did not bat</span>{innings.did_not_bat.join(', ')}
        </div>
      )}

      {innings.fall_of_wickets.length > 0 && (
        <div className="wisden-innings-aside">
          <span className="lbl">Fall of wickets</span>
          {innings.fall_of_wickets.map((w, i) => (
            <span key={w.wicket} className="num">
              {i > 0 ? ', ' : ''}{w.score}-{w.wicket} ({w.batter}, {w.over_ball} ov)
            </span>
          ))}
        </div>
      )}

      {/* Bowling */}
      <div className="wisden-innings-section-label">Bowling</div>
      <table>
        <thead>
          <tr>
            <th>Bowler</th>
            <th className="r">O</th>
            <th className="r">M</th>
            <th className="r">R</th>
            <th className="r">W</th>
            <th className="r">Econ</th>
            <th className="r">wd</th>
            <th className="r">nb</th>
          </tr>
        </thead>
        <tbody>
          {innings.bowling.map(b => {
            const isHL = !!(highlightBowlerId && b.person_id === highlightBowlerId)
            return (
              <tr key={`${b.person_id}-${b.name}`}
                className={isHL ? 'is-highlighted' : undefined}>
                <td className="pname">
                  {bowlerHref(b.person_id)
                    ? <Link to={bowlerHref(b.person_id)!}>{b.name}</Link>
                    : b.name}
                </td>
                <td className="r">{b.overs}</td>
                <td className="r">{b.maidens}</td>
                <td className="r">{b.runs}</td>
                <td className="r" style={{ color: 'var(--ink)', fontWeight: 600 }}>{b.wickets}</td>
                <td className="r">{b.econ.toFixed(2)}</td>
                <td className="r" style={{ color: 'var(--ink-faint)' }}>{b.wides}</td>
                <td className="r" style={{ color: 'var(--ink-faint)' }}>{b.noballs}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
