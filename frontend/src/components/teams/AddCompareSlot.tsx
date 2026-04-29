import { useState } from 'react'
import TeamSearch from '../TeamSearch'
import { getTeamSummary, getSeasons } from '../../api'
import { ANY_SENTINEL } from '../../hooks/useUrlState'
import SlotScopeEditor from './SlotScopeEditor'
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
  const [showCustomBuilder, setShowCustomBuilder] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Total compare-side columns. Cap = 2 (primary + 2 = 3 total).
  const filledCount = (slots.slot1 ? 1 : 0) + (slots.slot2 ? 1 : 0)
  if (filledCount >= 2) return null

  const hasSeason = !!primaryFilters.season_from
  // "All-time" / "broaden everything" picks make sense iff primary has
  // ANY overridable narrowing — otherwise the broadened slot is identical
  // to the current-scope one. Includes the post-2026-04-29 axes
  // (series_type, filter_venue, team_class) so e.g. an FM-bilaterals
  // primary still shows "League avg, all-time" as a way to opt out of
  // BOTH narrowings on the avg slot.
  const hasAnyNarrowing = !!primaryFilters.tournament
    || !!primaryFilters.season_from || !!primaryFilters.season_to
    || !!primaryFilters.filter_venue
    || !!primaryFilters.series_type
    || !!primaryFilters.team_class
  const hasAllTimeable = hasAnyNarrowing
  const isInternational = primaryFilters.team_type === 'international'

  // Compare overrides shape-wise so quick-picks gate per-shape, not
  // blanket-hide just because *any* avg / same-team slot exists. User
  // feedback 2026-04-29: with one avg already in scope, the panel
  // collapsed to "Different team — current scope" only — too thin.
  const sameOverridesShape = (a: SlotOverrides, b: SlotOverrides): boolean => {
    const ak = Object.keys(a), bk = Object.keys(b)
    if (ak.length !== bk.length) return false
    return ak.every(k => (a as Record<string, string>)[k] === (b as Record<string, string>)[k])
  }
  const sameTeamAlreadyComparing = (overrides: SlotOverrides): boolean => {
    for (const slot of [slots.slot1, slots.slot2]) {
      if (!slot || slot.kind !== 'team' || slot.entity !== primaryTeam) continue
      if (sameOverridesShape(slot.overrides, overrides)) return true
    }
    return false
  }
  const sameAvgAlreadyComparing = (overrides: SlotOverrides): boolean => {
    for (const slot of [slots.slot1, slots.slot2]) {
      if (!slot || slot.kind !== 'avg') continue
      if (sameOverridesShape(slot.overrides, overrides)) return true
    }
    return false
  }

  const closeAll = () => {
    setOpen(false); setShowTeamPick(false); setShowCustomBuilder(false)
    setErr(null); setBusy(false)
  }

  const onAvgInScope = () => {
    if (sameAvgAlreadyComparing({})) {
      setErr('League avg in current scope is already in comparison.')
      return
    }
    onAddSlot(AVG_SENTINEL, {})
    closeAll()
  }
  const onAvgFullMember = () => {
    const o: SlotOverrides = { team_class: 'full_member' }
    if (sameAvgAlreadyComparing(o)) {
      setErr('Full-member avg in current scope is already in comparison.')
      return
    }
    onAddSlot(AVG_SENTINEL, o)
    closeAll()
  }
  // League avg, all-time — broaden every primary-narrowed axis via
  // the __any__ sentinel so the avg pool is unbounded along seasons /
  // tournament / venue / series_type / team_class. Inherits gender +
  // team_type bound to primary (those aren't slot-overridable).
  // Result: a scope-AVG column whose pool is much broader than the
  // current FilterBar window — useful as a long-horizon baseline.
  const onAvgAllTime = () => {
    const o: SlotOverrides = {}
    if (primaryFilters.season_from) o.season_from = ANY_SENTINEL
    if (primaryFilters.season_to)   o.season_to   = ANY_SENTINEL
    if (primaryFilters.tournament)  o.tournament  = ANY_SENTINEL
    if (primaryFilters.filter_venue) o.filter_venue = ANY_SENTINEL
    if (primaryFilters.series_type) o.series_type = ANY_SENTINEL
    if (primaryFilters.team_class)  o.team_class  = ANY_SENTINEL
    // No primary narrowing → the all-time avg is identical to current-
    // scope avg; skip showing both to avoid duplicate quick-picks.
    if (Object.keys(o).length === 0) {
      setErr('Current scope is already all-time — no narrowing to broaden.')
      return
    }
    if (sameAvgAlreadyComparing(o)) {
      setErr('League avg, all-time is already in comparison.')
      return
    }
    onAddSlot(AVG_SENTINEL, o)
    closeAll()
  }
  const onSameTeamAllTime = () => {
    const overrides: SlotOverrides = {}
    if (primaryFilters.tournament)  overrides.tournament  = ANY_SENTINEL
    if (primaryFilters.season_from) overrides.season_from = ANY_SENTINEL
    if (primaryFilters.season_to)   overrides.season_to   = ANY_SENTINEL
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

      {!showTeamPick && !showCustomBuilder && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          <div style={{ fontSize: '0.78em', opacity: 0.6, marginBottom: '0.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Quick add — same team
          </div>
          {hasSeason && (
            <button type="button" className="comp-link" style={QP_BTN_STYLE} onClick={onSameTeamPrev} disabled={busy}>
              + Same team, previous season
            </button>
          )}
          {hasAllTimeable && (
            <button type="button" className="comp-link" style={QP_BTN_STYLE} onClick={onSameTeamAllTime}>
              + Same team, all-time
            </button>
          )}
          <div style={{ fontSize: '0.78em', opacity: 0.6, marginTop: '0.5rem', marginBottom: '0.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Quick add — league average
          </div>
          <button type="button" className="comp-link" style={QP_BTN_STYLE} onClick={onAvgInScope}>
            + League avg, current scope
          </button>
          {hasAllTimeable && (
            <button
              type="button"
              className="comp-link"
              style={QP_BTN_STYLE}
              onClick={onAvgAllTime}
              title="Avg-column pool broadened past primary's narrowing — uses the __any__ sentinel on tournament / season / venue / series_type so the baseline ignores the FilterBar's narrowing on those axes."
            >
              + League avg, all-time
            </button>
          )}
          {isInternational && (
            <button
              type="button"
              className="comp-link"
              style={QP_BTN_STYLE}
              onClick={onAvgFullMember}
              title="Restrict the avg-column pool to matches between two ICC full-member teams (excludes associates like Namibia, USA, Nepal …)."
            >
              + Full-member avg, current scope
            </button>
          )}
          <div style={{ fontSize: '0.78em', opacity: 0.6, marginTop: '0.5rem', marginBottom: '0.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Quick add — different team
          </div>
          <button type="button" className="comp-link" style={QP_BTN_STYLE} onClick={() => setShowTeamPick(true)}>
            + Different team, current scope
          </button>
          <div style={{ borderTop: '1px solid var(--rule-soft)', margin: '0.6rem 0 0.4rem' }} />
          <button
            type="button"
            className="comp-link"
            style={{ ...QP_BTN_STYLE, fontWeight: 500 }}
            onClick={() => setShowCustomBuilder(true)}
            title="Build a column with explicit team and arbitrary scope overrides — same controls as the ✎ editor on a column header."
          >
            + Build custom column ▾
          </button>
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

      {showCustomBuilder && (
        <CustomBuilder
          primary={primaryFilters}
          primaryTeam={primaryTeam}
          onAdd={(entity, overrides) => {
            // Duplicate-check by entity + overrides shape.
            if (entity === AVG_SENTINEL && sameAvgAlreadyComparing(overrides)) {
              setErr('A league avg column with that exact scope is already in comparison.')
              return
            }
            if (entity !== AVG_SENTINEL && entity === primaryTeam
                && sameTeamAlreadyComparing(overrides)) {
              setErr(`${primaryTeam} with that scope is already in comparison.`)
              return
            }
            if (entity !== AVG_SENTINEL && entity !== primaryTeam) {
              for (const slot of [slots.slot1, slots.slot2]) {
                if (slot?.kind === 'team' && slot.entity === entity
                    && sameOverridesShape(slot.overrides, overrides)) {
                  setErr(`${entity} with that scope is already in comparison.`)
                  return
                }
              }
            }
            onAddSlot(entity, overrides)
            closeAll()
          }}
          onCancel={() => { setShowCustomBuilder(false); setErr(null) }}
          onErr={setErr}
        />
      )}

      {busy && <div style={{ marginTop: '0.4rem', fontSize: '0.85em', opacity: 0.7 }}>Working…</div>}
      {err && <div className="wisden-compare-picker-err" style={{ marginTop: '0.4rem' }}>{err}</div>}
    </div>
  )
}

// ─── Custom builder ───────────────────────────────────────────────────
//
// Three-radio kind selector + (when "different team") a TeamSearch +
// inline SlotScopeEditor. The editor's Apply button trickles up to
// `onAdd(entity, overrides)` with entity computed from kind:
//   self  → primaryTeam
//   other → selected team name
//   avg   → AVG_SENTINEL
//
// Same controls as the ✎ editor on a column header — but here you
// configure both team AND scope before the column is added, instead
// of the two-step "add then click ✎" flow.

interface CustomBuilderProps {
  primary: FilterParams
  primaryTeam: string
  onAdd: (entity: string, overrides: SlotOverrides) => void
  onCancel: () => void
  onErr: (msg: string) => void
}

type BuilderKind = 'self' | 'other' | 'avg'

function CustomBuilder({ primary, primaryTeam, onAdd, onCancel, onErr }: CustomBuilderProps) {
  const [kind, setKind] = useState<BuilderKind>('self')
  const [otherTeam, setOtherTeam] = useState<string>('')

  const teamForEditor: string | undefined =
    kind === 'self' ? primaryTeam :
    kind === 'other' ? (otherTeam || undefined) :
    undefined

  const handleApply = (overrides: SlotOverrides) => {
    if (kind === 'other' && !otherTeam) {
      onErr('Pick a team first.')
      return
    }
    const entity = kind === 'avg' ? AVG_SENTINEL :
                   kind === 'self' ? primaryTeam : otherTeam
    onAdd(entity, overrides)
  }

  const radioStyle: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
    fontSize: '0.85em', cursor: 'pointer', marginRight: '0.8rem',
  }

  return (
    <div>
      <div style={{ fontSize: '0.78em', opacity: 0.6, marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Build custom column
      </div>
      <div style={{ marginBottom: '0.5rem' }}>
        <label style={radioStyle}>
          <input type="radio" checked={kind === 'self'} onChange={() => setKind('self')} />
          {primaryTeam}
        </label>
        <label style={radioStyle}>
          <input type="radio" checked={kind === 'other'} onChange={() => setKind('other')} />
          Different team
        </label>
        <label style={radioStyle}>
          <input type="radio" checked={kind === 'avg'} onChange={() => setKind('avg')} />
          League average
        </label>
      </div>
      {kind === 'other' && (
        <div style={{ marginBottom: '0.5rem' }}>
          <TeamSearch
            onSelect={setOtherTeam}
            placeholder={otherTeam ? `Selected: ${otherTeam}` : 'Search teams…'}
          />
        </div>
      )}
      {/* Remount the editor on kind / team change so its internal
       *  state (tournament/season selects scoped to the team) refreshes
       *  cleanly. */}
      <SlotScopeEditor
        key={`${kind}|${otherTeam}`}
        primary={primary}
        team={teamForEditor}
        initial={{}}
        onApply={handleApply}
        onReset={() => { /* Reset is a no-op — initial is already empty */ }}
        onCancel={onCancel}
      />
    </div>
  )
}
