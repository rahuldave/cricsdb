import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Teams from './pages/Teams'
import Batting from './pages/Batting'
import Bowling from './pages/Bowling'
import HeadToHead from './pages/HeadToHead'
import Matches from './pages/Matches'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/batting" element={<Batting />} />
          <Route path="/bowling" element={<Bowling />} />
          <Route path="/head-to-head" element={<HeadToHead />} />
          <Route path="/matches" element={<Matches />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
