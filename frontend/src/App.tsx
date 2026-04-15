import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Teams from './pages/Teams'
import Batting from './pages/Batting'
import Bowling from './pages/Bowling'
import Fielding from './pages/Fielding'
import HeadToHead from './pages/HeadToHead'
import Matches from './pages/Matches'
import MatchScorecard from './pages/MatchScorecard'
import Help from './pages/Help'
import HelpUsage from './pages/HelpUsage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/batting" element={<Batting />} />
          <Route path="/bowling" element={<Bowling />} />
          <Route path="/fielding" element={<Fielding />} />
          <Route path="/head-to-head" element={<HeadToHead />} />
          <Route path="/matches" element={<Matches />} />
          <Route path="/matches/:matchId" element={<MatchScorecard />} />
          <Route path="/help" element={<Help />} />
          <Route path="/help/usage" element={<HelpUsage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
