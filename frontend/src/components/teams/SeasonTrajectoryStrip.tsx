import LineChart from '../charts/LineChart'
import type {
  TeamProfile, ScopeAverageProfile, TeamBattingSeason, TeamBowlingSeason,
} from '../../types'

interface ColumnInput {
  /** Display name in the legend. Either a team name or the scope-avg label. */
  label: string
  profile: TeamProfile | ScopeAverageProfile
  /** True for the league-average column — rendered in a neutral colour. */
  isAverage?: boolean
}

interface Props {
  columns: ColumnInput[]
  /** Hide the strip when single-season filters collapse the trajectory
   *  to a single point per line (no story to tell). */
  hidden?: boolean
}

/** Read by-season array from either profile shape. Team endpoints
 *  return `{ seasons: [...] }`; scope-avg returns `{ by_season: [...] }`. */
function getBattingSeasons(p: TeamProfile | ScopeAverageProfile): TeamBattingSeason[] {
  const o = p.batting_by_season as { seasons?: TeamBattingSeason[]; by_season?: TeamBattingSeason[] } | null
  if (!o) return []
  return (o.seasons ?? o.by_season ?? []) as TeamBattingSeason[]
}

function getBowlingSeasons(p: TeamProfile | ScopeAverageProfile): TeamBowlingSeason[] {
  const o = p.bowling_by_season as { seasons?: TeamBowlingSeason[]; by_season?: TeamBowlingSeason[] } | null
  if (!o) return []
  return (o.seasons ?? o.by_season ?? []) as TeamBowlingSeason[]
}

/** Coerce a season string (e.g. "2024" or "2023/24") to a numeric x.
 *  For Y/Y formats we use the first year — IPL "2023/24" sorts as 2023.5
 *  isn't worth — first year keeps it linear. */
function seasonNum(season: string): number {
  const m = /^(\d{4})/.exec(season)
  return m ? Number(m[1]) : 0
}

interface Row {
  series: string
  season_num: number
  season_label: string
  value: number | null
  isAverage: boolean
}

function flattenBatting(columns: ColumnInput[]): Row[] {
  const out: Row[] = []
  for (const c of columns) {
    for (const s of getBattingSeasons(c.profile)) {
      out.push({
        series: c.label,
        season_num: seasonNum(s.season),
        season_label: s.season,
        value: s.run_rate,
        isAverage: c.isAverage ?? false,
      })
    }
  }
  return out.filter(r => r.value != null)
}

function flattenBowling(columns: ColumnInput[]): Row[] {
  const out: Row[] = []
  for (const c of columns) {
    for (const s of getBowlingSeasons(c.profile)) {
      out.push({
        series: c.label,
        season_num: seasonNum(s.season),
        season_label: s.season,
        value: s.economy,
        isAverage: c.isAverage ?? false,
      })
    }
  }
  return out.filter(r => r.value != null)
}

export default function SeasonTrajectoryStrip({ columns, hidden = false }: Props) {
  if (hidden) return null

  const battingRows = flattenBatting(columns)
  const bowlingRows = flattenBowling(columns)

  // Skip trajectory if every column has at most one season — nothing
  // to draw a line through.
  const distinctSeasons = new Set(battingRows.map(r => r.season_num))
  if (distinctSeasons.size < 2) return null

  return (
    <section className="wisden-player-section" style={{ marginTop: '2rem' }}>
      <div className="wisden-player-section-head">
        <h3 className="wisden-player-section-label">SEASON TRAJECTORY</h3>
      </div>
      <p
        className="wisden-help-note"
        style={{ marginTop: '-0.4rem', marginBottom: '1rem', fontSize: '0.9em' }}
      >
        Run rate (batting) and economy (bowling) per season. Each line is a
        compare column; the league-average line is rendered in grey.
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '2rem',
        }}
      >
        <div>
          <h4 style={{ fontSize: '0.85em', marginBottom: '0.4rem', opacity: 0.75 }}>
            Batting RR
          </h4>
          {battingRows.length > 0
            ? <LineChart
                data={battingRows}
                xAccessor="season_num"
                yAccessor="value"
                lineBy="series"
                colorBy="series"
                height={220}
                xLabel="Season"
                yLabel="RR"
                showPoints
              />
            : <em style={{ opacity: 0.6 }}>No season data.</em>
          }
        </div>
        <div>
          <h4 style={{ fontSize: '0.85em', marginBottom: '0.4rem', opacity: 0.75 }}>
            Bowling Econ
          </h4>
          {bowlingRows.length > 0
            ? <LineChart
                data={bowlingRows}
                xAccessor="season_num"
                yAccessor="value"
                lineBy="series"
                colorBy="series"
                height={220}
                xLabel="Season"
                yLabel="Econ"
                showPoints
              />
            : <em style={{ opacity: 0.6 }}>No season data.</em>
          }
        </div>
      </div>
    </section>
  )
}
