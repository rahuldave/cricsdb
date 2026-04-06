import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getMatchScorecard } from '../api'
import ScorecardView from '../components/Scorecard'
import WormChart from '../components/charts/WormChart'
import ManhattanChart from '../components/charts/ManhattanChart'
import type { Scorecard } from '../types'

export default function MatchScorecard() {
  const { matchId } = useParams<{ matchId: string }>()
  const [data, setData] = useState<Scorecard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!matchId) return
    setData(null); setError(null)
    getMatchScorecard(Number(matchId))
      .then(setData)
      .catch(() => setError('Could not load scorecard'))
  }, [matchId])

  return (
    <div>
      <div className="mb-4">
        <Link to="/matches" className="text-sm text-blue-600 hover:underline">
          ← Back to matches
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {!data && !error && (
        <div className="text-center text-gray-400 py-16">Loading scorecard…</div>
      )}

      {data && (
        <ScorecardView data={data}>
          {/* Charts rendered between header and innings cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <div className="bg-white rounded-lg border shadow-sm p-4">
              <WormChart innings={data.innings} />
            </div>
            <div className="bg-white rounded-lg border shadow-sm p-4">
              <ManhattanChart innings={data.innings} />
            </div>
          </div>
        </ScorecardView>
      )}
    </div>
  )
}
