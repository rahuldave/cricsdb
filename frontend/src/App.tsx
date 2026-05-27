import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import { DormancyProvider } from './components/DormancyContext'
import Home from './pages/Home'
import Teams from './pages/Teams'
import Batting from './pages/Batting'
import Bowling from './pages/Bowling'
import Fielding from './pages/Fielding'
import HeadToHead from './pages/HeadToHead'
import Matches from './pages/Matches'
import MatchScorecard from './pages/MatchScorecard'
import Tournaments from './pages/Tournaments'
import Players from './pages/Players'
import Venues from './pages/Venues'
import Help from './pages/Help'
import HelpUsage from './pages/HelpUsage'
import DevTossFilter from './pages/DevTossFilter'

/** Old /tournaments URLs redirect to /series, preserving query params.
 *  Keeps shared links + bookmarks alive across the rename. */
function LegacyTournamentsRedirect() {
  const { search } = useLocation()
  return <Navigate to={`/series${search}`} replace />
}

/** /league was a brief intermediate route for above-tournament scope
 *  dossiers (2026-05-13 morning). Merged into /series the same day —
 *  /series renders the dossier at every scope. Redirect keeps any
 *  links from the brief /league window working. */
function LeagueRedirect() {
  const { search } = useLocation()
  return <Navigate to={`/series${search}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <DormancyProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/players" element={<Players />} />
          <Route path="/batting" element={<Batting />} />
          <Route path="/bowling" element={<Bowling />} />
          <Route path="/fielding" element={<Fielding />} />
          <Route path="/series" element={<Tournaments />} />
          <Route path="/tournaments" element={<LegacyTournamentsRedirect />} />
          <Route path="/league" element={<LeagueRedirect />} />
          <Route path="/venues" element={<Venues />} />
          <Route path="/head-to-head" element={<HeadToHead />} />
          <Route path="/matches" element={<Matches />} />
          <Route path="/matches/:matchId" element={<MatchScorecard />} />
          <Route path="/help" element={<Help />} />
          <Route path="/help/usage" element={<HelpUsage />} />
          {/* Unlisted dev/test surface for the TossFilter control
              (spec-player-baseline-aux-fallback.md §6.1, decision D2 —
              built now, real mount TBD). Exercised by
              tests/integration/toss_filter.sh. */}
          <Route path="/dev/toss-filter" element={<DevTossFilter />} />
        </Route>
      </Routes>
      </DormancyProvider>
    </BrowserRouter>
  )
}
