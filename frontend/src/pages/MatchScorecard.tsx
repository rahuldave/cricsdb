import { Link, useParams, useSearchParams } from 'react-router-dom'
import { getMatchScorecard, getInningsGrid } from '../api'
import ScorecardView from '../components/Scorecard'
import WormChart from '../components/charts/WormChart'
import ManhattanChart from '../components/charts/ManhattanChart'
import InningsGridChart from '../components/charts/InningsGridChart'
import MatchupGridChart from '../components/charts/MatchupGridChart'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

export default function MatchScorecard() {
  const { matchId } = useParams<{ matchId: string }>()
  const [searchParams] = useSearchParams()
  const highlightBatterId = searchParams.get('highlight_batter')
  const highlightBowlerId = searchParams.get('highlight_bowler')
  const { data, loading, error, refetch } = useFetch(
    () => getMatchScorecard(Number(matchId)),
    [matchId],
  )
  const grid = useFetch(
    () => getInningsGrid(Number(matchId)),
    [matchId],
  )
  useDocumentTitle(
    data ? `${data.info.teams[0]} v ${data.info.teams[1]}` : null
  )

  return (
    <div className="max-w-6xl mx-auto">
      <Link to="/matches" className="wisden-back">← Back to matches</Link>

      {loading && <Spinner label="Loading scorecard…" size="lg" />}

      {error && (
        <ErrorBanner
          message={`Could not load scorecard: ${error}`}
          onRetry={refetch}
        />
      )}

      {data && !loading && (() => {
        // Compute linkParams the same way Scorecard.tsx does, so the
        // matchup-grid head-to-head links carry the same gender,
        // team_type, tournament context as the rest of the page.
        const linkParams = (() => {
          const params = new URLSearchParams()
          if (data.info.gender) params.set('gender', data.info.gender)
          if (data.info.team_type) params.set('team_type', data.info.team_type)
          if (data.info.tournament) params.set('tournament', data.info.tournament)
          return params.toString()
        })()
        return (
        <>
          <ScorecardView data={data} highlightBatterId={highlightBatterId} highlightBowlerId={highlightBowlerId}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <div><WormChart innings={data.innings} /></div>
              <div><ManhattanChart innings={data.innings} /></div>
            </div>

            {/* Matchup grid: per-innings batter × bowler matrix.
                Sits between the charts row and the regular innings
                tables (the user wanted it 'above the scoreboard'). */}
            {grid.data && !grid.loading && (
              <div className="space-y-4 mb-4">
                {grid.data.innings.map(inn => (
                  <MatchupGridChart
                    key={inn.innings_number}
                    innings={inn}
                    linkParams={linkParams}
                    highlightBatterId={highlightBatterId}
                    highlightBowlerId={highlightBowlerId}
                  />
                ))}
              </div>
            )}
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
        )
      })()}
    </div>
  )
}
