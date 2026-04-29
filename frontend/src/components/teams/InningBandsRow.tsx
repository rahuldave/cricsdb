/**
 * InningBandsRow — compact 3-row table (Overall / 1st innings /
 * 2nd innings) of headline metrics for a team Batting / Bowling /
 * Fielding / Partnerships tab. Sibling of PhaseBandsRow but with
 * a different domain (innings_number instead of over phases).
 *
 * Structure:
 *   - Overall row reads from the team's /summary response (already
 *     fetched by the parent tab — passed in as `summary`).
 *   - 1st / 2nd innings rows read from the /by-inning response
 *     (`bands` prop). Empty bands array hides the whole component.
 *
 * Discipline-specific columns:
 *   batting:      Run rate · Boundary % · Dot % · Wickets lost · Runs
 *   bowling:      Economy  · Wickets    · Dot % · Boundary %    · Conceded
 *   fielding:     Catches  · Stumpings  · Run-outs · Catches/match · Total
 *   partnerships: Partnerships · Avg runs · Best
 *
 * Spec: spec-inning-split.md §6.7.
 */
import type {
  TeamBattingSummary, TeamBattingInning,
  TeamBowlingSummary, TeamBowlingInning,
  TeamFieldingSummary, TeamFieldingInning,
  TeamPartnershipsSummary, TeamPartnershipsInning,
  MetricEnvelope,
} from '../../types'
import MetricDelta from '../MetricDelta'

type Discipline = 'batting' | 'bowling' | 'fielding' | 'partnerships'

interface BattingProps {
  discipline: 'batting'
  summary: TeamBattingSummary
  bands: TeamBattingInning[]
}
interface BowlingProps {
  discipline: 'bowling'
  summary: TeamBowlingSummary
  bands: TeamBowlingInning[]
}
interface FieldingProps {
  discipline: 'fielding'
  summary: TeamFieldingSummary
  bands: TeamFieldingInning[]
}
interface PartnershipsProps {
  discipline: 'partnerships'
  summary: TeamPartnershipsSummary
  bands: TeamPartnershipsInning[]
}
type Props = BattingProps | BowlingProps | FieldingProps | PartnershipsProps

const fmt2 = (v: number | null | undefined) => v == null ? '-' : v.toFixed(2)
const fmt1 = (v: number | null | undefined) => v == null ? '-' : v.toFixed(1)

/** Read either a flat number or a `.value` off an envelope. */
function rv(x: number | MetricEnvelope | null | undefined): number | null {
  if (x == null) return null
  if (typeof x === 'number') return x
  return x.value ?? null
}
/** Envelope or null (no chip when flat). */
function env(x: number | MetricEnvelope | null | undefined): MetricEnvelope | null {
  if (x == null || typeof x === 'number') return null
  return x
}

interface Cell {
  text: string
  env?: MetricEnvelope | null
  fmt?: 1 | 2
}
interface Row {
  label: string
  cells: Cell[]
}

function buildBattingRows(s: TeamBattingSummary, bands: TeamBattingInning[]): { headers: string[]; rows: Row[] } {
  const headers = ['Run rate', 'Boundary %', 'Dot %', 'Wkts', '4s', '6s']
  const overall: Row = {
    label: 'Overall',
    cells: [
      { text: fmt2(rv(s.run_rate)),     env: env(s.run_rate),     fmt: 2 },
      { text: fmt1(rv(s.boundary_pct)), env: env(s.boundary_pct), fmt: 1 },
      { text: fmt1(rv(s.dot_pct)),      env: env(s.dot_pct),      fmt: 1 },
      { text: '-' },  // wickets_lost not on the summary response — left blank
      { text: String(rv(s.fours) ?? '-') },
      { text: String(rv(s.sixes) ?? '-') },
    ],
  }
  const inningRows: Row[] = (bands ?? []).map(b => ({
    label: b.label,
    cells: [
      { text: fmt2(rv(b.run_rate)),     env: env(b.run_rate),     fmt: 2 },
      { text: fmt1(rv(b.boundary_pct)), env: env(b.boundary_pct), fmt: 1 },
      { text: fmt1(rv(b.dot_pct)),      env: env(b.dot_pct),      fmt: 1 },
      { text: String(b.wickets_lost) },
      { text: String(b.fours) },
      { text: String(b.sixes) },
    ],
  }))
  return { headers, rows: [overall, ...inningRows] }
}

function buildBowlingRows(s: TeamBowlingSummary, bands: TeamBowlingInning[]): { headers: string[]; rows: Row[] } {
  const headers = ['Economy', 'Wickets', 'Dot %', 'Boundary %', '4s', '6s']
  const overall: Row = {
    label: 'Overall',
    cells: [
      { text: fmt2(rv(s.economy)),      env: env(s.economy),      fmt: 2 },
      { text: String(rv(s.wickets) ?? '-') },
      { text: fmt1(rv(s.dot_pct)),      env: env(s.dot_pct),      fmt: 1 },
      { text: '-' },  // boundary_pct not on bowling summary
      { text: String(rv(s.fours_conceded) ?? '-') },
      { text: String(rv(s.sixes_conceded) ?? '-') },
    ],
  }
  const inningRows: Row[] = (bands ?? []).map(b => ({
    label: b.label,
    cells: [
      { text: fmt2(rv(b.economy)),      env: env(b.economy),      fmt: 2 },
      { text: String(b.wickets) },
      { text: fmt1(rv(b.dot_pct)),      env: env(b.dot_pct),      fmt: 1 },
      { text: fmt1(rv(b.boundary_pct)), env: env(b.boundary_pct), fmt: 1 },
      { text: String(b.fours_conceded) },
      { text: String(b.sixes_conceded) },
    ],
  }))
  return { headers, rows: [overall, ...inningRows] }
}

function buildFieldingRows(s: TeamFieldingSummary, bands: TeamFieldingInning[]): { headers: string[]; rows: Row[] } {
  const headers = ['Matches', 'Catches', 'Stumpings', 'Run-outs', 'Total dis.', 'C/match']
  const overall: Row = {
    label: 'Overall',
    cells: [
      { text: String(rv(s.matches) ?? '-') },
      { text: String(rv(s.catches) ?? '-') },
      { text: String(rv(s.stumpings) ?? '-') },
      { text: String(rv(s.run_outs) ?? '-') },
      { text: String(rv(s.total_dismissals_contributed) ?? '-') },
      { text: fmt2(rv(s.catches_per_match)), env: env(s.catches_per_match), fmt: 2 },
    ],
  }
  const inningRows: Row[] = (bands ?? []).map(b => ({
    label: b.label,
    cells: [
      { text: String(b.matches) },
      { text: String(b.catches) },
      { text: String(b.stumpings) },
      { text: String(b.run_outs) },
      { text: String(b.total_dismissals_contributed) },
      { text: fmt2(rv(b.catches_per_match)), env: env(b.catches_per_match), fmt: 2 },
    ],
  }))
  return { headers, rows: [overall, ...inningRows] }
}

function buildPartnershipsRows(s: TeamPartnershipsSummary, bands: TeamPartnershipsInning[]): { headers: string[]; rows: Row[] } {
  const headers = ['Total', 'Avg runs', 'Best']
  const overall: Row = {
    label: 'Overall',
    cells: [
      { text: String(rv(s.total) ?? '-') },
      { text: fmt1(rv(s.avg_runs)), env: env(s.avg_runs), fmt: 1 },
      { text: s.highest ? String(s.highest.runs) : '-' },
    ],
  }
  const inningRows: Row[] = (bands ?? []).map(b => ({
    label: b.label,
    cells: [
      { text: String(rv(b.n) ?? '-'),    env: env(b.n) },
      { text: fmt1(rv(b.avg_runs)),       env: env(b.avg_runs), fmt: 1 },
      { text: String(b.best_runs) },
    ],
  }))
  return { headers, rows: [overall, ...inningRows] }
}

function buildRows(props: Props): { headers: string[]; rows: Row[] } {
  switch (props.discipline) {
    case 'batting':      return buildBattingRows(props.summary, props.bands)
    case 'bowling':      return buildBowlingRows(props.summary, props.bands)
    case 'fielding':     return buildFieldingRows(props.summary, props.bands)
    case 'partnerships': return buildPartnershipsRows(props.summary, props.bands)
  }
}

const TITLE_FOR: Record<Discipline, string> = {
  batting:      'By innings — batting',
  bowling:      'By innings — bowling',
  fielding:     'By innings — fielding',
  partnerships: 'By innings — partnerships',
}

export default function InningBandsRow(props: Props) {
  const { headers, rows } = buildRows(props)
  // Hide entirely if the by-inning fetch returned nothing (out-of-
  // scope team, fully abandoned matches, etc.).
  if (props.bands.length === 0) return null
  return (
    <div className="wisden-inning-bands">
      <h3 className="wisden-section-title">{TITLE_FOR[props.discipline]}</h3>
      <table className="wisden-table">
        <thead>
          <tr>
            <th></th>
            {headers.map(h => <th key={h}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.label} className={r.label === 'Overall' ? 'is-overall' : 'is-inning'}>
              <th scope="row">{r.label}</th>
              {r.cells.map((c, i) => (
                <td key={i} className="num">
                  {c.text}
                  {c.env && (
                    <span style={{ fontSize: '0.75em', marginLeft: '0.4rem' }}>
                      <MetricDelta env={c.env} fmt={c.fmt} />
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
