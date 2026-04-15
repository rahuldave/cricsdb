import { useEffect } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
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
  const navigate = useNavigate()
  const highlightBatterId = searchParams.get('highlight_batter')
  const highlightBowlerId = searchParams.get('highlight_bowler')
  const highlightFielderId = searchParams.get('highlight_fielder')
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

  // Scroll to the first highlighted row in DOM order, AFTER both the
  // scorecard data and the innings-grid data have finished loading.
  // Doing this per-InningsCard (the previous approach) fired the scroll
  // before the async InningsGridChart + MatchupGridChart siblings had
  // sized, so the target row was displaced once layout settled. Here we
  // wait for both fetches, then query the DOM in a rAF callback to pick
  // whatever `.is-highlighted` row appears first (batting, bowling, or
  // fielding — same selector serves all three).
  const hasHighlight = !!(highlightBatterId || highlightBowlerId || highlightFielderId)
  const bothReady = !!(data && grid.data && !grid.loading)
  useEffect(() => {
    if (!hasHighlight || !bothReady) return
    // Two rAFs: first lets the current commit paint, second lets layout
    // settle (charts resize, etc.) before we measure scroll position.
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = document.querySelector('.is-highlighted')
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
    })
    return () => cancelAnimationFrame(id)
  }, [hasHighlight, bothReady, highlightBatterId, highlightBowlerId, highlightFielderId])

  // Back navigation: prefer browser history (which preserves the tab
  // the user came from — tournament Records, team Match List, etc.).
  // Fall back to /matches for direct entries (deep links, new tab).
  // window.history.length > 2 is a heuristic since any nav through the
  // app adds entries; length 1 = first-load direct link.
  const goBack = () => {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate('/matches')
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <button type="button" onClick={goBack} className="wisden-back">← Back</button>

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
          <ScorecardView data={data} highlightBatterId={highlightBatterId} highlightBowlerId={highlightBowlerId} highlightFielderId={highlightFielderId}>
            <div className="mb-6">
              <WormChart innings={data.innings} />
            </div>
            <div className="mb-6">
              <ManhattanChart innings={data.innings} />
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
