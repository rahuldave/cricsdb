import { Link, useParams } from 'react-router-dom'
import { getMatchScorecard, getInningsGrid } from '../api'
import ScorecardView from '../components/Scorecard'
import WormChart from '../components/charts/WormChart'
import ManhattanChart from '../components/charts/ManhattanChart'
import InningsGridChart from '../components/charts/InningsGridChart'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { useFetch } from '../hooks/useFetch'

export default function MatchScorecard() {
  const { matchId } = useParams<{ matchId: string }>()
  const { data, loading, error, refetch } = useFetch(
    () => getMatchScorecard(Number(matchId)),
    [matchId],
  )
  const grid = useFetch(
    () => getInningsGrid(Number(matchId)),
    [matchId],
  )

  return (
    <div>
      <div className="mb-4">
        <Link to="/matches" className="text-sm text-blue-600 hover:underline">
          ← Back to matches
        </Link>
      </div>

      {loading && <Spinner label="Loading scorecard…" size="lg" />}

      {error && (
        <ErrorBanner
          message={`Could not load scorecard: ${error}`}
          onRetry={refetch}
        />
      )}

      {data && !loading && (
        <>
          <ScorecardView data={data}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
              <div className="bg-white rounded-lg border shadow-sm p-4">
                <WormChart innings={data.innings} />
              </div>
              <div className="bg-white rounded-lg border shadow-sm p-4">
                <ManhattanChart innings={data.innings} />
              </div>
            </div>
          </ScorecardView>

          {/* Innings grid prototype: per-delivery visualization,
              rendered BELOW the regular scorecard, one card per innings. */}
          {grid.data && !grid.loading && (
            <div className="space-y-4 mt-6">
              {grid.data.innings.map(inn => (
                <InningsGridChart key={inn.innings_number} innings={inn} />
              ))}
            </div>
          )}
          {grid.loading && <div className="mt-6"><Spinner label="Loading innings grid…" /></div>}
          {grid.error && (
            <div className="mt-6">
              <ErrorBanner
                message={`Could not load innings grid: ${grid.error}`}
                onRetry={grid.refetch}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}
