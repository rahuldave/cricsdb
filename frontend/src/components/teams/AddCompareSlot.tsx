import { useState } from 'react'
import TeamSearch from '../TeamSearch'
import { getTeamSummary, getSeasons } from '../../api'
import type { FilterParams } from '../../types'
import { AVG_SENTINEL, type CompareSlots, type SlotOverrides } from '../../hooks/useCompareSlots'

interface Props {
  primaryTeam: string
  primaryFilters: FilterParams
  slots: CompareSlots
  /** Add a new compare slot to the next empty position. */
  onAddSlot: (entity: string, overrides: SlotOverrides) => void
}

const QP_BTN_STYLE: React.CSSProperties = {
  background: 'none',
  border: 'none',
  padding: '0.3rem 0',
  cursor: 'pointer',
  textAlign: 'left',
  font: 'inherit',
}

export default function AddCompareSlot({
  primaryTeam, primaryFilters, slots, onAddSlot,
}: Props) {
  const [open, setOpen] = useState(false)
  const [showTeamPick, setShowTeamPick] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Total compare-side columns. Cap = 2 (primary + 2 = 3 total).
  const filledCount = (slots.slot1 ? 1 : 0) + (slots.slot2 ? 1 : 0)
  if (filledCount >= 2) return null

  const hasAvg = slots.slot1?.kind === 'avg' || slots.slot2?.kind === 'avg'
  const hasSeason = !!primaryFilters.season_from
  const hasAllTimeable = !!primaryFilters.tournament || !!primaryFilters.season_from || !!primaryFilters.season_to

  const sameTeamAlreadyComparing = (overrides: SlotOverrides) => {
    // Refuse if a slot already has the SAME entity AND the SAME effective
    // overrides — keeps quick-picks idempotent.
    for (const slot of [slots.slot1, slots.slot2]) {
      if (!slot || slot.kind !== 'team' || slot.entity !== primaryTeam) continue
      const cur = slot.overrides
      const sameKeys = Object.keys(overrides).length === Object.keys(cur).length
        && Object.keys(overrides).every(k => (cur as Record<string, string>)[k] === (overrides as Record<string, string>)[k])
      if (sameKeys) return true
    }
    return false
  }

  const closeAll = () => { setOpen(false); setShowTeamPick(false); setErr(null); setBusy(false) }

  const onAvgInScope = () => {
    onAddSlot(AVG_SENTINEL, {})
    closeAll()
  }
  const onSameTeamAllTime = () => {
    const overrides: SlotOverrides = {}
    if (primaryFilters.tournament)  overrides.tournament  = ''
    if (primaryFilters.season_from) overrides.season_from = ''
    if (primaryFilters.season_to)   overrides.season_to   = ''
    if (sameTeamAlreadyComparing(overrides)) {
      setErr(`${primaryTeam} all-time is already in comparison.`)
      return
    }
    onAddSlot(primaryTeam, overrides)
    closeAll()
  }
  const onSameTeamPrev = async () => {
    setErr(null); setBusy(true)
    try {
      const r = await getSeasons({
        team: primaryTeam,
        gender: primaryFilters.gender,
        team_type: primaryFilters.team_type,
        tournament: primaryFilters.tournament || undefined,
      })
      const seasonsList = r.seasons ?? []
      const idx = seasonsList.indexOf(primaryFilters.season_from!)
      const prev = idx > 0 ? seasonsList[idx - 1] : null
      if (prev == null) {
        setErr('No previous season in scope.')
        return
      }
      const overrides: SlotOverrides = { season_from: prev, season_to: prev }
      if (sameTeamAlreadyComparing(overrides)) {
        setErr(`${primaryTeam} ${prev} is already in comparison.`)
        return
      }
      onAddSlot(primaryTeam, overrides)
      closeAll()
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Lookup failed.')
    } finally {
      setBusy(false)
    }
  }
  const onTeamSelected = async (name: string) => {
    setErr(null)
    if (name === primaryTeam) {
      setErr('Same as primary — use a "Same team, …" quick-pick instead.')
      return
    }
    if (slots.slot1?.entity === name || slots.slot2?.entity === name) {
      setErr('Team already in comparison.')
      return
    }
    setBusy(true)
    try {
      const s = await getTeamSummary(name, primaryFilters)
      if ((s.matches?.value ?? 0) < 1) {
        setErr(
          `${name} has no matches in the current filter scope — ` +
          'check gender, team-type, tournament, and season filters.',
        )
        return
      }
    } catch { /* ignore — proceed */ }
    finally { setBusy(false) }
    onAddSlot(name, {})
    closeAll()
  }

  if (!open) {
    return (
      <button
        type="button"
        className="comp-link wisden-compare-add-btn"
        onClick={() => setOpen(true)}
        style={{
          background: 'none',
          border: '1px dashed var(--ink-3, rgba(0,0,0,0.25))',
          padding: '0.5rem 0.8rem',
          marginTop: '0.6rem',
          cursor: 'pointer',
          textAlign: 'left',
          font: 'inherit',
          width: '100%',
        }}
      >
        + Add a column ▾
      </button>
    )
  }

  return (
    <div className="wisden-compare-add-panel" style={{
      border: '1px solid var(--ink-3, rgba(0,0,0,0.25))',
      padding: '0.75rem',
      marginTop: '0.6rem',
      background: 'var(--bg-soft, rgba(0,0,0,0.03))',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.5rem' }}>
        <strong style={{ fontSize: '0.9em' }}>Add a column</strong>
        <button type="button" className="comp-link" onClick={closeAll}>close</button>
      </div>

      {!showTeamPick && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <div style={{ fontSize: '0.78em', opacity: 0.6, marginBottom: '0.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Quick add
          </div>
          {!hasAvg && (
            <button type="button" className="comp-link" style={QP_BTN_STYLE} onClick={onAvgInScope}>
              + League avg in current scope
            </button>
          )}
          {hasSeason && (
            <button type="button" className="comp-link" style={QP_BTN_STYLE} onClick={onSameTeamPrev} disabled={busy}>
              + Same team, previous season
            </button>
          )}
          <button type="button" className="comp-link" style={QP_BTN_STYLE} onClick={() => setShowTeamPick(true)}>
            + Different team — current scope
          </button>
          {hasAllTimeable && (
            <button type="button" className="comp-link" style={QP_BTN_STYLE} onClick={onSameTeamAllTime}>
              + Same team, all-time
            </button>
          )}
          <div style={{ fontSize: '0.78em', opacity: 0.55, marginTop: '0.5rem' }}>
            Tip: add a column then click <span style={{ fontWeight: 600 }}>✎</span> on its header to override
            tournament, season, venue, or series type for that column only.
          </div>
        </div>
      )}

      {showTeamPick && (
        <div>
          <div style={{ fontSize: '0.78em', opacity: 0.6, marginBottom: '0.3rem' }}>
            Pick a team — current FilterBar scope applies (gender, team_type).
          </div>
          <TeamSearch onSelect={onTeamSelected} placeholder="Search teams…" />
          <button
            type="button"
            className="comp-link"
            onClick={() => { setShowTeamPick(false); setErr(null) }}
            style={{ marginTop: '0.4rem', fontSize: '0.85em' }}
          >
            ← back to quick-picks
          </button>
        </div>
      )}

      {busy && <div style={{ marginTop: '0.4rem', fontSize: '0.85em', opacity: 0.7 }}>Working…</div>}
      {err && <div className="wisden-compare-picker-err" style={{ marginTop: '0.4rem' }}>{err}</div>}
    </div>
  )
}
