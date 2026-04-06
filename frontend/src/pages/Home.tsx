import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMatches } from '../api'
import type { MatchListItem } from '../types'

export default function Home() {
  const [recent, setRecent] = useState<MatchListItem[]>([])

  useEffect(() => {
    getMatches({ limit: 5, offset: 0 })
      .then(d => setRecent(d.matches))
      .catch(() => setRecent([]))
  }, [])

  return (
    <div className="max-w-3xl mx-auto py-12">
      <h1 className="text-4xl font-bold text-gray-900 mb-4">T20 CricsDB</h1>
      <p className="text-lg text-gray-600 mb-8">
        A T20 cricket analytics platform covering 12,940 matches across international and club cricket,
        with ball-by-ball data for 2.95 million deliveries.
      </p>

      {/* Last 5 matches */}
      {recent.length > 0 && (
        <div className="mb-10">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-3">
            Most recent matches
          </h2>
          <ul className="bg-white rounded-lg border border-gray-200 shadow-sm divide-y divide-gray-100">
            {recent.map(m => (
              <li key={m.match_id}>
                <Link
                  to={`/matches?match=${m.match_id}`}
                  className="block px-4 py-3 hover:bg-blue-50 transition-colors"
                >
                  <div className="flex items-baseline justify-between">
                    <div className="font-medium text-gray-900">
                      {m.team1} vs {m.team2}
                    </div>
                    <div className="text-xs text-gray-500 whitespace-nowrap ml-3">
                      {m.date}
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {m.tournament}{m.city ? ` · ${m.city}` : ''}
                  </div>
                  <div className="text-sm text-gray-700 mt-1">
                    {m.result_text}
                    {(m.team1_score || m.team2_score) && (
                      <span className="text-gray-500">
                        {' — '}
                        {m.team1_score && `${m.team1} ${m.team1_score}`}
                        {m.team1_score && m.team2_score && ', '}
                        {m.team2_score && `${m.team2} ${m.team2_score}`}
                      </span>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6 mb-12">
        <Link to="/batting" className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Batting</h2>
          <p className="text-sm text-gray-500">
            Career stats, strike rates by over and phase, bowler matchups,
            dismissal analysis, and inter-wicket performance for 10,000+ batters.
          </p>
        </Link>
        <Link to="/bowling" className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Bowling</h2>
          <p className="text-sm text-gray-500">
            Economy, wickets, batter matchups, wicket types, and over-by-over
            analysis for 7,400+ bowlers.
          </p>
        </Link>
        <Link to="/teams" className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Teams</h2>
          <p className="text-sm text-gray-500">
            Win/loss records, head-to-head matchups, and season-by-season results
            for 322 teams across international and club cricket.
          </p>
        </Link>
        <Link to="/head-to-head" className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Head to Head</h2>
          <p className="text-sm text-gray-500">
            Deep dive into any batter vs bowler matchup: phase breakdowns,
            season trends, and match-by-match history.
          </p>
        </Link>
      </div>

      <div className="rounded-lg bg-gray-50 border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-700 mb-3">Coverage</h3>
        <div className="grid grid-cols-3 gap-4 text-sm text-gray-600">
          <div>
            <div className="font-medium text-gray-900">International</div>
            <div>Men's &amp; Women's T20Is</div>
            <div>T20 World Cups, Asia Cups</div>
            <div>Bilateral series</div>
          </div>
          <div>
            <div className="font-medium text-gray-900">Major Leagues</div>
            <div>IPL, BBL, PSL, CPL</div>
            <div>The Hundred, T20 Blast</div>
            <div>WPL, WBBL, and more</div>
          </div>
          <div>
            <div className="font-medium text-gray-900">Data</div>
            <div>12,940 matches</div>
            <div>2.95M deliveries</div>
            <div>160K wickets</div>
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-400 mt-8 text-center">
        Data sourced from <a href="https://cricsheet.org" className="underline" target="_blank" rel="noopener">Cricsheet</a> (ODC-BY 1.0 license).
        Built with deebase, FastAPI, React, and Semiotic.
      </p>
    </div>
  )
}
