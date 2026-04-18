import { Link } from 'react-router-dom'
import FlagBadge from '../FlagBadge'
import { useFetch } from '../../hooks/useFetch'
import { getBatterSummary, getBowlerSummary } from '../../api'
import {
  PROFILE_MEN, PROFILE_WOMEN, COMPARE_MEN, COMPARE_WOMEN,
  type ProfileTile, type ComparePair,
} from './CuratedLists'
import { carryFilters } from './roleUtils'
import type { FilterParams } from '../../types'

interface Props {
  filters: FilterParams
}

// Flag-mapping uses cricsheet team strings. For the landing tiles we
// hand-map seeded players to their primary nationality flag — saves
// a summary round-trip and avoids tiles flickering in as identities
// arrive.
const FLAG_BY_ID: Record<string, string> = {
  // Men
  ba607b88: 'India',
  '462411b3': 'India',
  '30a45b23': 'Australia',
  '740742ef': 'India',
  '99b75528': 'England',
  e798611a: 'South Africa',
  '8a75e999': 'Pakistan',
  d027ba9f: 'New Zealand',
  '0f721006': 'West Indies',
  '6a26221c': 'South Africa',
  a343262c: 'England',
  e62dd25d: 'South Africa',
  e087956b: 'England',
  fe93fd9d: 'India',
  '2b6e6dec': 'Australia',
  // Women
  '5d2eda89': 'India',
  be150fc8: 'Australia',
  '4ba0289e': 'England',
  '52d1dbc8': 'Australia',
  '27e003ce': 'Australia',
  '201fef33': 'India',
  '321644de': 'Australia',
  de69af96: 'New Zealand',
  d32cf49a: 'West Indies',
}

export default function PlayersLanding({ filters }: Props) {
  const showMen   = filters.gender !== 'female'
  const showWomen = filters.gender !== 'male'

  return (
    <div>
      <div className="wisden-tab-help" style={{ marginBottom: '1.5rem' }}>
        Pick a player to see their full batting, bowling and fielding
        record in one place. The <em>Compare</em> tiles below open two
        players side-by-side. All filters above narrow every view.
      </div>

      <h3 className="wisden-section-title" style={{ marginTop: '2rem' }}>Popular profiles</h3>
      {showMen && (
        <>
          <div className="wisden-players-subhead">Men</div>
          <div className="wisden-players-grid">
            {PROFILE_MEN.map(t => <ProfileTileCard key={t.id} tile={t} filters={filters} />)}
          </div>
        </>
      )}
      {showWomen && (
        <>
          <div className="wisden-players-subhead" style={{ marginTop: '1.5rem' }}>Women</div>
          <div className="wisden-players-grid">
            {PROFILE_WOMEN.map(t => <ProfileTileCard key={t.id} tile={t} filters={filters} />)}
          </div>
        </>
      )}

      <h3 className="wisden-section-title" style={{ marginTop: '2.5rem' }}>Popular comparisons</h3>
      {showMen && (
        <>
          <div className="wisden-players-subhead">Men</div>
          <div className="wisden-compare-grid">
            {COMPARE_MEN.map((p, i) => <ComparePairCard key={i} pair={p} filters={filters} />)}
          </div>
        </>
      )}
      {showWomen && (
        <>
          <div className="wisden-players-subhead" style={{ marginTop: '1.5rem' }}>Women</div>
          <div className="wisden-compare-grid">
            {COMPARE_WOMEN.map((p, i) => <ComparePairCard key={i} pair={p} filters={filters} />)}
          </div>
        </>
      )}
    </div>
  )
}

function ProfileTileCard({ tile, filters }: { tile: ProfileTile; filters: FilterParams }) {
  const qs = new URLSearchParams({
    player: tile.id, gender: tile.gender, ...carryFilters({ ...filters, gender: undefined }),
  })
  const href = `/players?${qs}`
  const flagTeam = FLAG_BY_ID[tile.id]

  // Stat strip — fetch the summary for the tile's primary role.
  // Filters propagate so a women-only or IPL-only landing shows
  // scope-consistent numbers. `.catch(() => null)` — a 404 (e.g.
  // a women's player in a men's scope) just suppresses the strip,
  // the tile is still clickable.
  const filterDeps = [
    tile.id, tile.role,
    filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_venue,
  ]
  const strip = useFetch<StatStrip | null>(
    () => fetchStrip(tile, filters),
    filterDeps,
  )

  return (
    <Link to={href} className="wisden-player-tile">
      <div className="wisden-player-tile-head">
        <FlagBadge team={flagTeam} gender={tile.gender} size="sm" />
        <span className="wisden-player-tile-name">{tile.name}</span>
      </div>
      <div className="wisden-player-tile-strip num">
        {strip.data ? strip.data.text : strip.loading ? '…' : '—'}
      </div>
    </Link>
  )
}

function ComparePairCard({ pair, filters }: { pair: ComparePair; filters: FilterParams }) {
  // Both players share the pair's gender (enforced by the no-mixed-
  // gender rule). Take gender from the first.
  const g = pair.a.gender
  const qs = new URLSearchParams({
    player: pair.a.id,
    compare: pair.b.id,
    gender: g,
    ...carryFilters({ ...filters, gender: undefined }),
  })
  const href = `/players?${qs}`
  return (
    <Link to={href} className="wisden-player-tile wisden-compare-tile">
      <div className="wisden-player-tile-head">
        <FlagBadge team={FLAG_BY_ID[pair.a.id]} gender={g} size="sm" />
        <span className="wisden-player-tile-name">{pair.a.name}</span>
      </div>
      <div className="wisden-compare-vs">×</div>
      <div className="wisden-player-tile-head">
        <FlagBadge team={FLAG_BY_ID[pair.b.id]} gender={g} size="sm" />
        <span className="wisden-player-tile-name">{pair.b.name}</span>
      </div>
      <div className="wisden-player-tile-strip" style={{ fontStyle: 'italic' }}>compare →</div>
    </Link>
  )
}

// ─── stat-strip helper ──────────────────────────────────────────────

interface StatStrip { text: string }

async function fetchStrip(tile: ProfileTile, filters: FilterParams): Promise<StatStrip | null> {
  if (tile.role === 'bowler') {
    const s = await getBowlerSummary(tile.id, filters).catch(() => null)
    if (!s || s.balls === 0) return null
    return {
      text: `${fmt0(s.matches)} m · ${fmt0(s.wickets)} wkts · ${fmt2(s.economy)} econ`,
    }
  }
  const s = await getBatterSummary(tile.id, filters).catch(() => null)
  if (!s || s.innings === 0) return null
  return {
    text: `${fmt0(s.matches)} m · ${fmt0(s.runs)} runs · ${fmt2(s.average)} avg`,
  }
}

const fmt0 = (n: number) => n.toLocaleString()
const fmt2 = (v: number | null) => v == null ? '-' : v.toFixed(2)
