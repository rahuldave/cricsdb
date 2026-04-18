import { Link } from 'react-router-dom'
import type { VenueSummary, VenueTGSRow } from '../../types'
import StatCard from '../StatCard'
import DataTable from '../DataTable'

const fmt = (v: number | null | undefined, d = 1, suffix = '') =>
  v == null ? '-' : `${v.toFixed(d)}${suffix}`

const matchLink = (matchId: number, label: string | number) => (
  <Link to={`/matches/${matchId}`} className="comp-link">{label}</Link>
)

const teamLink = (team: string) => (
  <Link to={`/teams?team=${encodeURIComponent(team)}`} className="comp-link">{team}</Link>
)

export default function VenueOverviewPanel({ summary }: { summary: VenueSummary }) {
  const totalToss = Object.values(summary.toss_decision_split).reduce((a, b) => a + b, 0)
  const bat = summary.toss_decision_split.bat ?? 0
  const field = summary.toss_decision_split.field ?? 0
  const tossChoseField_Pct = totalToss ? (field * 100) / totalToss : null

  return (
    <div>
      {/* Headline numbers */}
      <div className="wisden-statrow cols-5 mt-4">
        <StatCard label="Matches" value={summary.matches.toLocaleString()} />
        <StatCard
          label="Avg 1st-inn total"
          value={fmt(summary.avg_first_innings_total, 1)}
          subtitle={`n=${summary.first_innings_sample}`}
        />
        <StatCard
          label="Bat-first win %"
          value={fmt(summary.bat_first_win_pct, 1, '%')}
          subtitle={`${summary.bat_first_wins} W`}
        />
        <StatCard
          label="Chase win %"
          value={fmt(summary.chase_win_pct, 1, '%')}
          subtitle={`${summary.chase_wins} W`}
        />
        <StatCard
          label="Tie / NR"
          value={summary.indecisive}
        />
      </div>

      {/* Toss panel */}
      <div className="mt-6">
        <h3 className="wisden-section-title">Toss</h3>
        <div className="wisden-statrow cols-4 mt-2">
          <StatCard
            label="Chose to bat"
            value={bat}
            subtitle={totalToss ? `${((bat * 100) / totalToss).toFixed(0)}%` : undefined}
          />
          <StatCard
            label="Chose to field"
            value={field}
            subtitle={tossChoseField_Pct != null ? `${tossChoseField_Pct.toFixed(0)}%` : undefined}
          />
          <StatCard
            label="Won toss + chose bat"
            value={fmt(summary.toss_and_win_pct.bat?.win_pct, 1, '%')}
            subtitle={summary.toss_and_win_pct.bat
              ? `${summary.toss_and_win_pct.bat.wins}/${summary.toss_and_win_pct.bat.decided}`
              : undefined}
          />
          <StatCard
            label="Won toss + chose field"
            value={fmt(summary.toss_and_win_pct.field?.win_pct, 1, '%')}
            subtitle={summary.toss_and_win_pct.field
              ? `${summary.toss_and_win_pct.field.wins}/${summary.toss_and_win_pct.field.decided}`
              : undefined}
          />
        </div>
      </div>

      {/* Phase table */}
      <div className="mt-6">
        <h3 className="wisden-section-title">By phase (boundary % / dot %)</h3>
        <DataTable
          columns={[
            { key: 'phase', label: 'Phase' },
            { key: 'overs', label: 'Overs' },
            {
              key: 'boundary_pct', label: 'Boundary %', sortable: true,
              format: (v: number | null) => fmt(v, 1, '%'),
            },
            {
              key: 'dot_pct', label: 'Dot %', sortable: true,
              format: (v: number | null) => fmt(v, 1, '%'),
            },
          ]}
          data={[
            { phase: 'Powerplay', overs: '1-6',
              boundary_pct: summary.boundary_pct_by_phase.powerplay,
              dot_pct: summary.dot_pct_by_phase.powerplay },
            { phase: 'Middle', overs: '7-15',
              boundary_pct: summary.boundary_pct_by_phase.middle,
              dot_pct: summary.dot_pct_by_phase.middle },
            { phase: 'Death', overs: '16-20',
              boundary_pct: summary.boundary_pct_by_phase.death,
              dot_pct: summary.dot_pct_by_phase.death },
          ]}
          rowKey={(r) => r.phase}
        />
      </div>

      {/* Highest / lowest totals */}
      {(summary.highest_total || summary.lowest_all_out) && (
        <div className="mt-6">
          <h3 className="wisden-section-title">Ground-record totals</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {summary.highest_total && (
              <div className="wisden-tile">
                <div className="wisden-tile-title">Highest total</div>
                <div className="wisden-tile-line mt-2">
                  <span className="wisden-tile-em num">{summary.highest_total.runs}</span>
                  {' — '}{teamLink(summary.highest_total.team)}
                  {' v '}{teamLink(summary.highest_total.opponent)}
                  {summary.highest_total.date && (
                    <> {' · '}{matchLink(summary.highest_total.match_id, summary.highest_total.date)}</>
                  )}
                </div>
              </div>
            )}
            {summary.lowest_all_out && (
              <div className="wisden-tile">
                <div className="wisden-tile-title">Lowest all-out</div>
                <div className="wisden-tile-line mt-2">
                  <span className="wisden-tile-em num">{summary.lowest_all_out.runs}</span>
                  {' — '}{teamLink(summary.lowest_all_out.team)}
                  {' v '}{teamLink(summary.lowest_all_out.opponent)}
                  {summary.lowest_all_out.date && (
                    <> {' · '}{matchLink(summary.lowest_all_out.match_id, summary.lowest_all_out.date)}</>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Matches hosted by tournament × gender × season */}
      {summary.by_tournament_gender_season.length > 0 && (
        <div className="mt-8">
          <h3 className="wisden-section-title">
            Matches hosted ({summary.by_tournament_gender_season.length} rows)
          </h3>
          <DataTable
            columns={[
              { key: 'season', label: 'Season', sortable: true },
              { key: 'tournament', label: 'Tournament', sortable: true },
              { key: 'gender', label: 'Gender', format: (v: string | null) => v ?? '-' },
              { key: 'matches', label: 'Matches', sortable: true },
            ]}
            data={summary.by_tournament_gender_season as unknown as VenueTGSRow[]}
            rowKey={(r) => `${r.season}|${r.tournament}|${r.gender ?? ''}`}
          />
        </div>
      )}
    </div>
  )
}
