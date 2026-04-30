---
spec: filterbar-team-class-club
extends: spec-filterbar-team-class-v3.md
status: build-ready, anchors derived, not yet implemented
authored: 2026-04-30
anchors-derived: 2026-04-30 (DB snapshot)
---

# Spec — `team_class` for clubs (primary / secondary tiers)

> **Extends** `spec-filterbar-team-class-v3.md` (v3 intl pill, shipped).
> v3 introduced the `team_class` URL key and FilterBar pill but
> defensive-gated all values to `team_type='international'` because
> `full_member` is meaningless for clubs. **This spec lifts the
> `team_type='club'` gate** by teaching `team_class` two new values —
> `primary_club` and `secondary_club` — modelled on the same key, the
> same pill widget, the same chip strip, the same per-slot inheritance.

The classification is the IPL-tier (10 men's + 4 women's leagues) /
domestic-tier (5 men's + 2 women's leagues) split discussed in chat
2026-04-30 — see `internal_docs/club-tier-classification.md` (NEW)
for the full rationale and edge cases.

---

## 1. Mental model

`team_class` becomes a polymorphic FilterBar key, dispatched by
`team_type`:

| `team_type` | Allowed `team_class` values | UI |
|---|---|---|
| `international` | `''` (default), `full_member` | Toggle button: ▢/▣ "Full members only" |
| `club` | `''` (default), `primary_club`, `secondary_club` | Three-state segmented control: All / Primary / Secondary |
| `''` (All) | `''` (forced) | Pill hidden; widget auto-clears any stray value |

This **reuses the existing URL param**, the existing Compare-tab slot
inheritance (`team_class` is already in `OVERRIDABLE_SLOT_KEYS`), the
existing scope-link plumbing (already in `FILTER_KEYS`), and the
existing chip strip — extending behaviour, not adding a sibling key.

Why one key, not two:

- Adding a parallel `club_tier` key would duplicate the entire v3
  scaffolding (slot inheritance, chip strip, deep-link guards, scope-
  link plumbing, deserialization) for the same conceptual purpose
  ("narrow by class of team in the active type"). CLAUDE.md "extend
  existing abstractions — do NOT fork parallel helpers" applies
  directly.
- The two concepts are mutually exclusive at the data level: a match
  has exactly one `team_type`, so at most one `team_class` value is
  applicable. The polymorphism is natural, not forced.

---

## 2. Classification — the source of truth

A new module `api/club_tiers.py`, parallel to `api/full_members.py`.
Two frozensets keyed by cricsheet `event_name`:

```python
PRIMARY_CLUB_LEAGUES: frozenset[str] = frozenset({
    # Men's marquee international franchise leagues — auction-driven
    # full-member overseas rosters, recognized as top-tier T20
    # destinations.
    "Indian Premier League",
    "Big Bash League",
    "Pakistan Super League",
    "Bangladesh Premier League",
    "Caribbean Premier League",
    "SA20",
    "International League T20",
    "Lanka Premier League",
    "Major League Cricket",
    "The Hundred Men's Competition",

    # Women's franchise leagues — same structural class.
    "Women's Big Bash League",
    "Women's Premier League",
    "The Hundred Women's Competition",
    "Women's Cricket Super League",  # defunct 2016-2019; predecessor
                                     # to The Hundred Women's
})

SECONDARY_CLUB_LEAGUES: frozenset[str] = frozenset({
    # Men's domestic state/county/provincial competitions + small-
    # market franchises.
    "Vitality Blast",                # county (England)
    "Syed Mushtaq Ali Trophy",       # state (India)
    "CSA T20 Challenge",             # provincial (South Africa)
    "Super Smash",                   # provincial (NZ)
    "Nepal Premier League",          # small-market franchise
                                     # (mostly Associate roster, not a
                                     #  marquee international destination)

    # Women's provincial.
    "Women's Super Smash",
    "New Zealand Cricket Women's Twenty20",  # older event_name for
                                             # the same NZ provincial set
})
```

**Disjointness invariant** (asserted at module-import time): the two
sets have empty intersection. Any cricsheet club `event_name` not in
either set is `team_class`-untagged — the filter silently no-ops on
those matches, which is the only safe behaviour for an unknown event.

Rationale per league: `internal_docs/club-tier-classification.md`
(new doc, see §10).

### Helpers

```python
def primary_club_clause(table_alias: str = "m") -> str:
    """Match's event_name is in a primary-tier club league."""
    a = table_alias
    quoted = ", ".join(f"'{e.replace(chr(39), chr(39)*2)}'"
                       for e in sorted(PRIMARY_CLUB_LEAGUES))
    return (f"({a}.team_type = 'club' "
            f"AND {a}.event_name IN ({quoted}))")

def secondary_club_clause(table_alias: str = "m") -> str:
    """Match's event_name is in a secondary-tier club league."""
    # Symmetric to primary_club_clause.
    ...
```

Match-level (`m.event_name`), not team-string. This is structurally
cleaner than `full_member_clause`'s per-team-string-IN approach
because club teams are uniquely tied to their league — no cross-league
team strings exist (verified DB-wide 2026-04-30).

### Why a new module, not extension of `tournament_canonical.py`

`tournament_canonical.py` already has `TOURNAMENT_SERIES_TYPE`
(franchise_league / domestic_league / women_franchise / other) used
by the Teams + Tournaments landing pages. Two reasons to keep
`club_tiers.py` separate:

1. **Different audiences.** Landing-page bucketing is a UX section
   header. Tier classification is a filter narrowing. They overlap
   substantially today but won't always.
2. **Existing landing-page bucketing has known imperfections** —
   notably Super Smash and Women's Super Smash are tagged
   `franchise_league` / `women_franchise` in the existing map, but
   they're provincial NZ competitions and belong with secondary in
   the tier map. Reconciling the landing-page buckets to the tier map
   is a separate UX discussion (phase 2). Until then, the dual map is
   a deliberate accommodation: filter semantics ship now, landing-page
   relabelling waits for product call.

This is documented in `internal_docs/design-decisions.md` (new bullet,
see §10) so the inconsistency doesn't get "cleaned up" by a future
contributor without consulting the tier-rationale doc.

---

## 3. Defensive gating

Triple-layer, mirroring v3 §3 but per-direction:

1. **FilterBar widget** — pill renders the appropriate sub-widget per
   `team_type`:
   - `international` → existing FM toggle.
   - `club` → new three-state segmented control.
   - `''` (All) → no pill.
   On `team_type` transition, a `replace`-mode `useEffect` clears
   `team_class` when the current value is incompatible with the new
   type:
   - intl→club clears `full_member`.
   - club→intl clears `primary_club` / `secondary_club`.
   - any→All clears any value.
2. **Frontend deep-link guard** — on mount, if URL carries a
   `team_class` value mismatched with `team_type`, strip it (replace
   mode). Prevents a stale link surfacing a chip-strip value the UI
   can't display.
3. **Backend defensive gate** — `FilterBarParams.build()` only emits
   the corresponding clause when `team_class` and `team_type`
   match. Cross-type values are silent no-ops (response identical to
   no `team_class`). Critical for URL robustness — a curl request
   `?team_type=club&team_class=full_member` must NOT zero out the
   response (it would, naively, because no club team matches the FM
   country list).

Pseudo-code in `filters.py::build()`:

```python
if _is_set(self.team_class):
    if self.team_class == "full_member" and self.team_type == "international":
        clauses.append(full_member_clause(table_alias=table_alias))
    elif self.team_class == "primary_club" and self.team_type == "club":
        clauses.append(primary_club_clause(table_alias=table_alias))
    elif self.team_class == "secondary_club" and self.team_type == "club":
        clauses.append(secondary_club_clause(table_alias=table_alias))
    # else: silent no-op (cross-type or unknown value)
```

Same dispatch added to `tournaments.py::_build_filter_clauses` and
`reference.py::_reference_clauses` + `reference.py::list_teams`. The
pattern in v3 §5.4/5.5 already exists for the FM branch — extend the
existing if/elif chain to add the two club branches.

---

## 4. Surface changes

### 4.1 FilterBar widget (`frontend/src/components/FilterBar.tsx`)

Replace the existing intl-only block (lines 278-289) with a polymorphic
block that branches on `teamType`:

```tsx
{teamType === 'international' && (
  <div className="wisden-filter-group">
    <button
      type="button"
      onClick={() => set('team_class', teamClass ? '' : 'full_member')}
      className={segBtn(teamClass === 'full_member')}
      title="Restrict to matches between two ICC full-member nations …"
    >
      {teamClass === 'full_member' ? '▣' : '▢'} Full members only
    </button>
  </div>
)}

{teamType === 'club' && (
  <div className="wisden-filter-group">
    <span className="wisden-filter-label">Tier</span>
    <button onClick={() => set('team_class', '')}
            className={segBtn(!teamClass)}>All</button>
    <button onClick={() => set('team_class', 'primary_club')}
            className={segBtn(teamClass === 'primary_club')}
            title="Marquee international franchise leagues — IPL, BBL, PSL, BPL, CPL, SA20, ILT20, MLC, LPL, The Hundred (M+W), WBBL, WPL, …">
      Primary
    </button>
    <button onClick={() => set('team_class', 'secondary_club')}
            className={segBtn(teamClass === 'secondary_club')}
            title="Domestic state / county / provincial leagues — Vitality Blast, Syed Mushtaq Ali, CSA T20 Challenge, Super Smash, Nepal Premier League, Women's Super Smash">
      Secondary
    </button>
  </div>
)}
```

Auto-clear effect (replaces the v3 single-direction effect):

```tsx
useEffect(() => {
  if (!teamType && teamClass) {
    setUrlParams({ team_class: '' }, { replace: true })
  } else if (teamType === 'international' &&
             teamClass && teamClass !== 'full_member') {
    setUrlParams({ team_class: '' }, { replace: true })
  } else if (teamType === 'club' &&
             teamClass === 'full_member') {
    setUrlParams({ team_class: '' }, { replace: true })
  }
}, [teamType, teamClass])
```

`anyFilterSet` and `clearAll` already include `team_class` (v3) — no
change.

### 4.2 ScopeStatusStrip (`frontend/src/components/ScopeStatusStrip.tsx`)

Extend the v3 chip line (line 79):

```tsx
if (filters.team_class === 'full_member') {
  segs.push({ label: 'Team class', value: 'full members' })
} else if (filters.team_class === 'primary_club') {
  segs.push({ label: 'Team class', value: 'primary clubs' })
} else if (filters.team_class === 'secondary_club') {
  segs.push({ label: 'Team class', value: 'secondary clubs' })
}
```

### 4.3 Scope-link URLs

No edit. `team_class` already in `FILTER_KEYS` (v3 §6.1). The new
values automatically flow through `buildParams` /
`scopeLinks.ts::resolveScopePhrases` etc.

### 4.4 Compare-tab UI (`frontend/src/components/teams/SlotScopeEditor.tsx`)

Class dropdown widens. Today the editor renders a binary FM toggle.
For club slots, the dropdown should offer:
- "(inherit)"  — no override
- "All"        — explicit empty (write `compareN_team_class=`)
- "Primary"    — `primary_club`
- "Secondary"  — `secondary_club`

For intl slots, unchanged: "(inherit)" / "All" / "Full members only".

The `cmp(...) → o.team_class = teamClass` persistence rule from v3
§6.4 is unchanged — write only when the slot value differs from
primary.

### 4.5 AddCompareSlot quick-pick

Today (v3): "+ Full-member avg in current scope" appears for intl.
Add three peers:

- For club slots: "+ Primary-club avg in current scope" and
  "+ Secondary-club avg in current scope" — set `compareN_team_class`
  to the appropriate value, leaves all other axes inherited.
  Visible regardless of FilterBar state (matches v3's
  hide-when-ambient-on rule rejection).

### 4.6 Backend dispatch

Files touched:

- `api/filters.py` — extend the team_class branch in `build()` (§3
  pseudo-code).
- `api/routers/tournaments.py::_build_filter_clauses` — extend the FM
  branch with two club branches.
- `api/routers/reference.py::_reference_clauses` and `list_teams` —
  extend.
- `api/routers/bucket_baseline_dispatch.py::is_precomputed_scope` —
  bucket tables don't carry tier-of-event, so reject precompute when
  any tier value is set (same logic as FM rejection).
- `api/social_meta.py` — extend the description scope tag (line 154):
  add `primary_club` → "primary clubs only", `secondary_club` →
  "secondary clubs only".

### 4.7 Backwards-compatibility surface

- v3's existing intl behaviour (FM toggle + URL `team_class=full_member`)
  is byte-identical post-this-spec.
- v3's defensive gate for club URLs (`team_type=club&team_class=full_member`)
  remains a silent no-op.
- All new behaviour activates only on `team_class=primary_club` or
  `team_class=secondary_club`, both of which are new URL surface.

---

## 5. Pre-flight DB anchors

Closed historical window: **`gender='male'`, `team_type='club'`,
`season IN ('2024', '2024/25', '2025')`** (the same window v3 used
for intl, applied here to club). All numbers below derived directly
from `cricket.db` snapshot 2026-04-30; full SQL pinned in
`internal_docs/club-tier-anchor-numbers.md` (NEW, see §10).

The full anchor count is **47** (P1-P12, G1-G4, V1-V6, H1-H4, X1-X6,
C1-C7, BWL1-BWL2, B-list rows ×30, BWL-list rows ×30, W1-W4, plus
disjointness invariants). One anchor → one sanity-test row.

### P-series — Match counts in window (men's)

| Anchor | Description | Result |
|---|---|---|
| P1  | Total club male, 2024-25, no `team_class` | **901** |
| P2  | Same scope, `team_class=primary_club` | **548** |
| P3  | Same scope, `team_class=secondary_club` | **353** |
| P4  | Disjointness invariant — `P2 + P3 == P1` | **548 + 353 = 901 ✓** |
| P5  | Mumbai Indians, no `team_class` | **30** |
| P6  | Mumbai Indians, `team_class=primary_club` | **30** ✓ (no narrowing — MI ∈ primary) |
| P7  | Mumbai Indians, `team_class=secondary_club` | **0** ✓ (cross-tier) |
| P8  | Surrey, no `team_class` | **30** |
| P9  | Surrey, `team_class=primary_club` | **0** ✓ (cross-tier) |
| P10 | Surrey, `team_class=secondary_club` | **30** ✓ (no narrowing — Surrey ∈ secondary) |
| P11 | Baroda (small SMA-only team), no `team_class` | **2** |
| P12 | Baroda, `team_class=secondary_club` | **2** ✓ |

P7, P9 prove tier-mismatch returns zero rows on a per-team narrowing —
the load-bearing contract.

### Per-event breakdown (correctness witnesses for the `IN (...)` clauses)

In the window (proves clause coverage is exhaustive):

```
PRIMARY (P2 = 548):
  IPL=145, Hundred(M)=68, CPL=66, MLC=56, BPL=46, BBL=42, PSL=34,
  ILT20=34, SA20=33, LPL=24
  → 145+68+66+56+46+42+34+34+33+24 = 548 ✓

SECONDARY (P3 = 353):
  Vitality Blast=258, NPL=32, Super Smash=29, CSA T20=26, SMA=8
  → 258+32+29+26+8 = 353 ✓
```

### Whole-DB partition invariant

| Anchor | Description | Result |
|---|---|---|
| INV1 | All `team_type=club`, `match_type=T20` | **7573** |
| INV2 | Same + event_name in `PRIMARY_CLUB_LEAGUES` | **4578** |
| INV3 | Same + event_name in `SECONDARY_CLUB_LEAGUES` | **2995** |
| INV4 | Untagged (event_name in neither set) | **0** ✓ |
| INV5 | INV2 + INV3 == INV1 | **4578 + 2995 = 7573 ✓** |

INV4 = 0 is the **completeness invariant**. Every cricsheet club T20
event in the DB is currently mapped. A future `update_recent` run that
introduces a new event (e.g. a brand-new league) will fail this
invariant → sanity test fails CI → human reviews and slots the event
into one of the two frozensets. Per CLAUDE.md "the doc grows with the
codebase; never let a [classification] go undocumented".

### G-series — Defensive-gate proof (cross-type silent no-op)

| Anchor | Description | Result |
|---|---|---|
| G1 | India intl 2024-25, no `team_class` | **34** (= v3 A5) |
| G2 | India intl 2024-25, `team_class=primary_club` (cross-type) | **34** ✓ |
| G3 | India intl 2024-25, `team_class=secondary_club` (cross-type) | **34** ✓ |
| G4 | RCB IPL 2025, `team_class=full_member` (cross-type) | **15** (= v3 B1) |
| G5 | Mumbai Indians club 2024-25, `team_class=full_member` (cross-type) | **30** ✓ |
| G6 | RCB IPL 2025, `team_class=primary_club` (same-type, narrows but RCB ∈ primary so no-op) | **15** ✓ |

G2/G3/G4/G5 are the four cross-type pairs. Each is a sanity-test row
that the API call returns the unbounded count, **NOT zero**. This is
the load-bearing assertion proving the defensive backend gate fires.
G6 shows same-type but tautological (no narrowing).

### V-series — Venue interaction (single-tier and multi-tier venues)

| Anchor | Description | Result |
|---|---|---|
| V1 | Wankhede club male 2024-25, unbounded | **14** |
| V2 | Wankhede + `team_class=primary_club` | **14** ✓ (Wankhede only hosts IPL → primary) |
| V3 | Wankhede + `team_class=secondary_club` | **0** ✓ |
| V4 | Kennington Oval club male 2024-25, unbounded | **25** (multi-tier — Surrey VBlast + Oval Invincibles Hundred) |
| V5 | Kennington Oval + `team_class=primary_club` | **10** ✓ (Hundred only) |
| V6 | Kennington Oval + `team_class=secondary_club` | **15** ✓ (Vitality Blast only) |

V4 = V5 + V6 (10 + 15 = 25) — multi-tier venue partitions cleanly.
This catches a bug where venue + tier composition failed (e.g. one
of the clauses was OR'd instead of AND'd).

### H-series — Head-to-head rivalry under tier filter

| Anchor | Description | Result |
|---|---|---|
| H1 | MI vs CSK 2024-25 club male, unbounded | **3** |
| H2 | Same + `team_class=primary_club` | **3** ✓ |
| H3 | Surrey vs Somerset 2024-25 club male, unbounded | **5** |
| H4 | Same + `team_class=secondary_club` | **5** ✓ |

Tautological narrowing (both teams in same tier) → preserves count.

### X-series — Cross-tier player narrowing (player dossier)

| Anchor | Description | Result |
|---|---|---|
| X1 | SM Curran club male 2024-25 matches, unbounded | **69** |
| X2 | SM Curran + `team_class=primary_club` (IPL/MLC/Hundred) | **49** |
| X3 | SM Curran + `team_class=secondary_club` (Vitality Blast for Surrey) | **20** |
| X4 | X2 + X3 == X1 | **49 + 20 = 69 ✓** |
| X5 | SM Curran total batting runs, unbounded | **1812** |
| X6 | X5 split — primary 1210 + secondary 602 = 1812 ✓ | **1210 / 602 / 1812** |

X-series tests the **player dossier** under tier filters — crucial
because cross-tier players exist (overseas pros who play county +
franchise). The two narrowed counts must sum to unbounded: this catches
double-counting bugs in `i.team` (batter side) vs match-level filter
composition.

### C-series — Compare-grid chip baselines (run rates)

Run rate formula:
`SUM(d.runs_total) * 6.0 / SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END)`

| Anchor | Description | runs | legal_balls | RR (4dp) |
|---|---|---|---|---|
| C1 | Mumbai Indians batting RR, club male 2024-25 unbounded | 5480 | 3420 | **9.6140** |
| C2 | Mumbai Indians batting RR, + `primary_club` (no-op — MI ∈ primary) | 5480 | 3420 | **9.6140** ✓ |
| C3 | League batting RR, club male 2024-25 unbounded | 289977 | 198211 | **8.7778** |
| C4 | League batting RR, + `primary_club` | 177551 | 119815 | **8.8913** |
| C5 | League batting RR, + `secondary_club` | 112426 | 78396 | **8.6045** |
| C6 | Surrey batting RR, club male 2024-25 unbounded | 5158 | 3334 | **9.2825** |
| C7 | Surrey batting RR, + `secondary_club` (no-op — Surrey ∈ secondary) | 5158 | 3334 | **9.2825** ✓ |

**C3 ≠ C4 ≠ C5** — the load-bearing "league average actually shifts"
assertion. Primary-tier RR is **0.11 runs/over above** unbounded;
secondary-tier RR is **0.17 runs/over below** unbounded. Mumbai
Indians' "above-avg" delta vs the league flips from +0.84 (vs
unbounded) to +0.72 (vs primary) — small but non-zero, so the chip
direction stays "above" but magnitude moves. The Surrey vs
secondary-only chip flips magnitude similarly.

C3 = C4_runs + C5_runs (when adjusted for the third-pool overlap):
177551 + 112426 = 289977 ✓ (legal balls similarly: 119815 + 78396 =
198211 ✓). Confirms the partition is disjoint at the delivery level
too.

### BWL — Bowling-side baselines

| Anchor | Description | runs | legal_balls | ER (4dp) |
|---|---|---|---|---|
| BWL1 | MI bowling ER (vs MI batting), club male 2024-25 unbounded | 5376 | 3444 | **9.3659** |
| BWL2 | MI bowling ER, + `primary_club` (no-op — MI ∈ primary) | 5376 | 3444 | **9.3659** ✓ |

Bowling-side aggregation uses `i.team = m.opponent_of(MI)` — exercises
the side-neutral build path in `filters.py::build_side_neutral`. Pin
to ensure the filter clause is applied through that codepath too
(side-neutral build re-enters the team_class branch).

### B-list — Top-10 batters (literal lists)

Pin top-10 batters by `SUM(runs_batter)` in the 2024-25 club male
window under each of three modes:

**B-unb (unbounded, top 10)** — mixed primary/secondary:

| rank | person_id | name | runs |
|---|---|---|---|
| 1  | 3241e3fd | N Pooran           | 3021 |
| 2  | 3355b542 | F du Plessis       | 2219 |
| 3  | a15618fe | JM Vince           | 2204 |
| 4  | 92aeac25 | AD Hales           | 1881 |
| 5  | e94915e6 | SM Curran          | 1812 |
| 6  | f836b33d | T Kohler-Cadmore   | 1790 |
| 7  | 9caf69a1 | WG Jacks           | 1770 |
| 8  | 372455c4 | Q de Kock          | 1765 |
| 9  | 1fc6ef83 | SD Hope            | 1756 |
| 10 | 4663bd23 | TL Seifert         | 1710 |

**B-pri (primary_club, top 10)** — IPL/CPL/MLC/Hundred-dominated:

| rank | person_id | name | runs |
|---|---|---|---|
| 1  | 3241e3fd | N Pooran           | 3021 |
| 2  | 3355b542 | F du Plessis       | 2219 |
| 3  | 372455c4 | Q de Kock          | 1765 |
| 4  | 1fc6ef83 | SD Hope            | 1756 |
| 5  | 92aeac25 | AD Hales           | 1743 |
| 6  | 4663bd23 | TL Seifert         | 1710 |
| 7  | 48a1d7b7 | SO Hetmyer         | 1674 |
| 8  | 235c2bb6 | H Klaasen          | 1554 |
| 9  | ba607b88 | V Kohli            | 1398 |
| 10 | a15618fe | JM Vince           | 1394 |

**B-sec (secondary_club, top 10)** — Vitality Blast / SMA dominated:

| rank | person_id | name | runs |
|---|---|---|---|
| 1  | 7ca5e05d | RS Bopara          | 1088 |
| 2  | 67b9536c | SR Hain            | 1029 |
| 3  | f836b33d | T Kohler-Cadmore   | 943 |
| 4  | f3982af9 | DP Hughes          | 940 |
| 5  | 35f173a0 | MP Breetzke        | 933 |
| 6  | 270e4c23 | MS Pepper          | 899 |
| 7  | 4e18e961 | WCF Smeed          | 880 |
| 8  | a6c17509 | TE Albert          | 859 |
| 9  | ab01e323 | SA Zaib            | 852 |
| 10 | 10b79140 | TS Muyeye          | 814 |

Notable cross-tier signals:
- **N Pooran's 3021 = 3021** under primary (no secondary appearance —
  Pooran is purely franchise-tier).
- **JM Vince** (Hampshire / pri-MLC) is #3 unbounded but #10 under
  primary (county runs drop) — visible split.
- **T Kohler-Cadmore** appears in both lists (#6 unbounded, #3
  secondary, dropped from primary top-10) — exemplary cross-tier
  player; verifies the API surfaces the right subset under each
  filter.

### BWL-list — Top-10 bowlers (literal lists)

Same SQL pattern as v3 A11/A12: `COUNT(DISTINCT w.id)` excluding
`run out / retired hurt / retired out / obstructing the field`.

**BWL-unb (top 10)**:

| rank | person_id | name | wkts |
|---|---|---|---|
| 1  | efc04be7 | Noor Ahmad         | 95 |
| 2  | a818c1be | TA Boult           | 79 |
| 3  | 19b9f399 | CJ Green           | 79 |
| 4  | 245c97cb | TS Mills           | 77 |
| 5  | e94915e6 | SM Curran          | 76 |
| 6  | 6c79c098 | DA Payne           | 76 |
| 7  | 64775749 | RP Meredith        | 74 |
| 8  | e174dadd | Mohammad Amir      | 72 |
| 9  | 7f048519 | DJ Willey          | 67 |
| 10 | 9d430b40 | SP Narine          | 64 |

**BWL-pri (top 10)**:

| rank | person_id | name | wkts |
|---|---|---|---|
| 1  | efc04be7 | Noor Ahmad         | 95 |
| 2  | a818c1be | TA Boult           | 79 |
| 3  | 9d430b40 | SP Narine          | 64 |
| 4  | 0f721006 | JO Holder          | 64 |
| 5  | 5f547c8b | Rashid Khan        | 62 |
| 6  | 4d7f517e | AJ Hosein          | 57 |
| 7  | bbd41817 | AD Russell         | 55 |
| 8  | e94915e6 | SM Curran          | 53 |
| 9  | 2f9d0389 | LH Ferguson        | 53 |
| 10 | e174dadd | Mohammad Amir      | 49 |

**BWL-sec (top 10)** — Vitality Blast quicks/spinners:

| rank | person_id | name | wkts |
|---|---|---|---|
| 1  | 6c79c098 | DA Payne           | 50 |
| 2  | f3abd0c9 | DR Briggs          | 49 |
| 3  | c5f40e35 | SW Currie          | 47 |
| 4  | 64775749 | RP Meredith        | 42 |
| 5  | 245c97cb | TS Mills           | 42 |
| 6  | e871a7a1 | BW Sanderson       | 41 |
| 7  | 34b37279 | BGF Green          | 41 |
| 8  | 01a95383 | MD Taylor          | 40 |
| 9  | bdc0670a | LBK Hollman        | 39 |
| 10 | 4c0f3806 | BA Raine           | 38 |

Cross-tier signals:
- **SM Curran** (#5 unbounded with 76 wkts) drops to #8 in primary
  with 53; the missing 23 are his Vitality Blast haul (verifying
  cross-tier delivery splits).
- **TS Mills** (#4 unbounded with 77 wkts) drops out of primary entirely;
  in secondary at #5 with 42. Implies he's a pure secondary bowler
  in this window — his 35 missing wkts are county-only.

### W-series — Women's anchors

Closed window: `gender='female'`, `team_type='club'`,
`season IN ('2024', '2024/25', '2025')`.

| Anchor | Description | Result |
|---|---|---|
| W1 | Total club female 2024-25, unbounded | **162** |
| W2 | Same + `team_class=primary_club` | **131** |
| W3 | Same + `team_class=secondary_club` | **31** |
| W4 | Disjointness — `W2 + W3 == W1` | **131 + 31 = 162 ✓** |

Per-event breakdown (window):
- Primary: WBBL 2024/25 = 42, WPL 2024/25 = 22, The Hundred Women 2024 = 33, The Hundred Women 2025 = 34 → 131 ✓
- Secondary: Women's Super Smash 2024/25 = 31 → 31 ✓

(NZC Women's T20 has no matches in this exact season set; its older
seasons would surface in a wider window.)

### Distinct-team-string counts (whole DB)

| Anchor | Description | Result |
|---|---|---|
| T1 | Distinct men's primary team strings | **105** |
| T2 | Distinct men's secondary team strings | **83** |
| T3 | Distinct women's primary team strings | **27** |
| T4 | Distinct women's secondary team strings | **6** |
| T5 | Cross-tier team-string intersection (primary ∩ secondary) | **0** ✓ |

T5 = 0 is the **disjoint-team-string invariant**: a team string
appears in exactly one tier. Asserted in
`test_team_class_club_baseline_numbers.py::test_team_strings_disjoint`
on every test run; failure means a future event introduced a team
name collision (which the human must rename before merging).

---

## 6. Test plan

Four layers, parallel to v3 §8.

### 6.1 Sanity (Python, DB-direct)

**New file:** `tests/sanity/test_team_class_club_baseline_numbers.py`.
Each anchor in §5 → one row. **47 anchors total** (P×12 + INV×5 +
G×6 + V×6 + H×4 + X×6 + C×7 + BWL×2 + W×4 + T×5 — counts the
disjointness invariants as anchors since they're independent
assertions, plus 60 list-row anchors from B-list and BWL-list = 107
sanity-test rows). Pattern (from v3):

```python
async def assert_anchor(label, sql_query, sql_params, api_call, expected_count):
    db_count = (await db.q(sql_query, sql_params))[0]['count']
    api_count = await api_call()
    assert db_count == expected_count, f"DB drift on {label}"
    assert api_count == db_count, f"API≠DB on {label}: api={api_count} db={db_count}"
```

Plus three in-Python invariant tests:

```python
def test_tier_disjointness():
    """No cricsheet event_name appears in both tier sets."""
    from api.club_tiers import PRIMARY_CLUB_LEAGUES, SECONDARY_CLUB_LEAGUES
    assert PRIMARY_CLUB_LEAGUES & SECONDARY_CLUB_LEAGUES == set()

async def test_completeness_invariant():
    """Every cricsheet club T20 event in the DB is mapped to some tier.
    Catches the case where a new event arrives via update_recent and
    is silently untagged (would become a no-op for the filter, masking
    the missing classification)."""
    db = get_db()
    rows = await db.q("""
        SELECT DISTINCT event_name FROM match
        WHERE team_type='club' AND match_type='T20'
    """)
    untagged = [
        r['event_name'] for r in rows
        if r['event_name'] not in PRIMARY_CLUB_LEAGUES
        and r['event_name'] not in SECONDARY_CLUB_LEAGUES
    ]
    assert untagged == [], (
        f"New club events found in DB that aren't in club_tiers.py: "
        f"{untagged}. Slot each into PRIMARY_CLUB_LEAGUES or "
        f"SECONDARY_CLUB_LEAGUES."
    )

async def test_team_strings_disjoint():
    """No team string appears in matches under both tiers (T5 = 0).
    A team string is pinned to its tier by the leagues it plays in."""
    ...  # T5 SQL from §5
```

The completeness test fires on every CI run. If `update_recent`
introduces a new event (e.g. "Hong Kong Super Sixes T20" enters via
cricsheet), the test fails with the event name → human reviews and
adds it to one of the frozensets before merging. This is a
hard-edge invariant; the alternative (silent no-op) is exactly what
the spec is trying to avoid.

**Update v3 sanity tests** — three `test_avg_baseline_*` files in
`tests/sanity/` need additional rows for club-tier modes:
- `test_avg_baseline_pools.py`: extend column set from
  `[unbounded, full_member]` to `[unbounded, full_member,
  primary_club, secondary_club]`. Each row asserts the pool size for
  the matching scope.
- `test_avg_baseline_numbers.py`: add `mi_ipl_2025_primary_club`
  (no-op, == unbounded) and `surrey_vblast_2025_secondary_club` rows.
- `test_chip_direction_invariant.py`: add `mi_csk_2025_primary_club`
  symmetric-narrowing row + `mi_csk_2025_secondary_club` row that
  must ZERO OUT (rivalry vanishes under wrong tier — the chip
  direction defaults / no-data path must render correctly).

### 6.2 Regression (shell, hash diff)

Two no-drift contracts:

1. **All existing v3 URLs** (intl with/without `full_member`, club
   without `team_class`) match HEAD hashes byte-identical post-spec.
   Field already exists; new branches don't change the no-tier code
   path.
2. **Cross-type silent-no-op URLs** (`team_type=international&team_class=primary_club`,
   `team_type=club&team_class=full_member`) match the corresponding
   no-`team_class` URL byte-identical. **Pinned as `NEW` rows that
   intentionally `MATCH` an existing REG row's hash** — surfaces gate
   regressions immediately.

**No `REG → NEW` flips**. All work additive.

**New URL additions** (~180 across 10 suites, all `NEW`). Subjects
mirror the anchor set: **Mumbai Indians** (primary, P5/P6),
**Surrey** (secondary, P8/P10), **SM Curran** (cross-tier player,
X-series), **Kennington Oval** (multi-tier venue, V4-V6), **MI vs
CSK** + **Surrey vs Somerset** (H-series rivalries), plus tier-totals
URLs (P1/P2/P3/W1/W2/W3) and tier-mismatch zero-rows (P7, P9).

Per-suite breakdown:

- `tests/regression/teams/urls.txt` — **42 URLs**:
  - 18 Mumbai Indians × `team_class=primary_club` (landing,
    summary, results, by-season, players-by-season, opponents,
    opponents-matrix, vs-opponent CSK, batting summary/by-season/
    by-phase/top-batters/heatmap, bowling summary/by-season/by-phase/
    top-bowlers/heatmap, fielding summary/by-season/top-fielders,
    partnerships summary/by-wicket/best-pairs/heatmap/top — same
    18-endpoint set v3 used for India FM)
  - 18 Surrey × `team_class=secondary_club` (parallel)
  - 6 cross-type silent-no-op rows: Mumbai Indians ×
    `team_class=full_member`, Surrey × `team_class=full_member`,
    Mumbai Indians × `team_class=secondary_club` (zero-row P7),
    Surrey × `team_class=primary_club` (zero-row P9), and two
    landing rows. All pinned `NEW` with hash recorded after first
    run; subsequent runs MUST match exactly. The full-member
    no-op rows must hash-equal the corresponding no-team_class row.
- `tests/regression/scope-averages/urls.txt` — **18 URLs**:
  - 4 men's pool rows: unbounded, primary_club, secondary_club, FM
    cross-type no-op (matches unbounded). Each at the
    `/api/v1/teams/<team>/avg/...` endpoint.
  - 4 women's pool rows: same pattern with WBBL teams.
  - 8 Mumbai Indians × Surrey chip-baseline avg URLs (one per
    bat/bowl side × tier × subject).
  - 2 the-Hundred-specific URLs (multi-team primary participation).
- `tests/regression/batting/urls.txt` — **14 URLs**:
  - leaderboards under each tier (top-batters strike rate / runs /
    by-phase / by-season).
  - Cross-tier player check: SM Curran's batter dossier under each
    tier; expect runs counts X5/X6 reflected in the response.
- `tests/regression/bowling/urls.txt` — **12 URLs**:
  - top-bowlers under each tier (BWL-list anchors).
  - SM Curran cross-tier dossier (76 → 53 + 23 wkts split).
- `tests/regression/fielding/urls.txt` — **10 URLs**:
  - top-fielders under each tier; one cross-type no-op row.
- `tests/regression/players/urls.txt` — **16 URLs**:
  - SM Curran player dossier (X-series) under tier × side × tab
    × tournament-pin permutations.
  - JM Vince (mixed-tier batter) — confirm tier=primary moves him
    out of the unbounded #3 slot.
- `tests/regression/series/urls.txt` — **12 URLs**:
  - IPL × `team_class=primary_club` (no-op equality with IPL alone —
    counts must match v3's `IPL` REG row).
  - IPL × `team_class=secondary_club` (zero-row).
  - Vitality Blast × each tier (mirror).
  - WBBL × each tier (women).
- `tests/regression/matches/urls.txt` — **12 URLs**:
  - match list under each tier × gender; pinning rivalries from
    H-series. Cross-tier zero-rows pinned (e.g. team1=Mumbai
    Indians&team_class=secondary_club).
- `tests/regression/head_to_head/urls.txt` — **10 URLs**:
  - MI vs CSK + tier (H1, H2 anchors); Surrey vs Somerset + tier
    (H3, H4); plus multi-tournament rivalries (e.g. CSK vs RCB).
  - One cross-type no-op (intl rivalry + primary_club).
- `tests/regression/venues/urls.txt` — **12 URLs**:
  - Wankhede × each tier (V1-V3).
  - Kennington Oval × each tier (V4-V6) — multi-tier partition.
  - Lord's × each tier (multi-tier mirror).
- `tests/regression/filterbar_refs/urls.txt` — **8 URLs**:
  - `/api/v1/teams?team_class=primary_club&team_type=club` (typeahead
    narrows to 105 entries; T1 anchor).
  - `/api/v1/teams?team_class=secondary_club&team_type=club` (83;
    T2 anchor).
  - Women's variants (T3, T4).
  - `/api/v1/tournaments?team_class=primary_club&team_type=club`
    (auto-narrowed Tournament dropdown payload — 11 entries
    expected: 10 men's primary + the Hundred Men's).
  - `/api/v1/tournaments?team_class=secondary_club&team_type=club`
    (5 entries).
  - Cross-type silent no-op:
    `/api/v1/teams?team_class=full_member&team_type=club` MUST hash-
    equal the same URL without `team_class`.
- `tests/regression/team_class_url_gen.sh` (existing) — extend to
  exercise the four URL transitions:
  1. start with `team_type=club&team_class=primary_club`, switch to
     `team_type=international` → assert `team_class` cleared and
     URL serialization matches the expected post-clear shape.
  2. start with `team_type=international&team_class=full_member`,
     switch to `team_type=club` → assert `team_class` cleared.
  3. start with `team_type=club&team_class=primary_club`, click
     "Secondary" pill button → assert `team_class=secondary_club`,
     pill state flipped.
  4. deep-link with `?team_type=club&team_class=full_member`
     (cross-type) → assert URL self-corrects on mount, `team_class`
     stripped.
  Each transition is a curl + URL parse + assertion. ~16 lines.

**Cross-type silent-no-op asssertion shape:** for each NEW row
labelled "no-op", the runner records the hash and a paired REG-row
hash; these two MUST match. Implemented via a special tag in
`urls.txt` (e.g. `NEW@matches=teams_landing_men_intl`) — extension to
`run.sh` to validate the equality at run-time. If the hashes diverge,
the gate broke. This is the load-bearing test for §3.

`tests/regression/<feature>/series_type.txt`, where present, also
gets paired entries (Series Type × Tier interactions are a small
matrix — 2 × 3 — that this file pins).

### 6.3 Integration (shell + agent-browser)

Six new scripts under `tests/integration/`. Each assertion cites the
SQL-anchored truth from §5 verbatim where applicable — the rendered
text MUST contain the literal anchor count, not a vague "≥ some
number" sanity check. Per CLAUDE.md "Audit prompt discipline":
assert literal cell text, not summary verdicts.

1. **`team_class_club_filterbar.sh`** — pill rendering + URL state
   plumbing.
   - Pill three-button segmented control visible on
     `team_type=club`. Buttons read literally "All" / "Primary" /
     "Secondary" — assert exact text via DOM query.
   - Pill is the existing FM toggle (button text "Full members
     only") on `team_type=international`.
   - Pill hidden on `team_type=''`.
   - Click "Primary" → URL contains `team_class=primary_club`;
     query DOM, assert button has `is-active` class; "Secondary" and
     "All" do NOT.
   - Click "Secondary" → URL changes to
     `team_class=secondary_club`; "Primary" loses active,
     "Secondary" gains active. Tooltip text verified literal:
     "Domestic state / county / provincial leagues …" (substring).
   - Click "All" → URL drops `team_class`; "All" active.
   - Browser back navigation: pill state re-applies (URL state
     wins, no stale active class).

2. **`team_class_club_gating.sh`** — defensive gates (six layered
   tests):
   - Type→Club auto-clears stale `full_member`. Start with
     `?team_type=international&team_class=full_member`, click Type
     → "Club" → URL after settle has `team_class` stripped, has
     `team_type=club`. Pill widget DOM swaps from toggle to
     segmented control.
   - Type→International auto-clears stale `primary_club` /
     `secondary_club` (both tested as separate tests).
   - Type→All clears any value (tested with each of the three
     non-empty values as start state).
   - Deep-link `?team_type=club&team_class=full_member` self-corrects
     on mount → URL after settle has `team_class` empty.
   - Backend silent no-op proof:
     `curl -s '/api/v1/teams/landing?team_type=international&team_class=primary_club' | jq '.international.men.regular | length'`
     equals the same URL without `team_class` (proves G2 anchor).
   - Pill DOM swap is **immediate** (within 500ms of Type change).

3. **`team_class_club_persistence.sh`** — URL plumbing through tabs.
   For each navigation, assert `team_class` parameter and value are
   preserved letter-for-letter.
   - Set `team_class=primary_club` on Teams landing.
   - Click into Mumbai Indians (anchor P5) → URL preserves
     `team_class=primary_club`. ScopeStatusStrip shows literal text
     "Team class: primary clubs" (substring assertion).
   - Click "Compare" tab on the team page → URL preserves
     `team_class`. Compare's avg slot inherits `primary_club` (no
     `compare1_team_class` written).
   - Click into a player named in B-pri list (e.g. Pooran) → URL
     preserves `team_class`.
   - Click back to Teams → URL preserves it.
   - Switch FilterBar's `tournament` to IPL — `team_class` survives;
     URL contains both keys.
   - Switch tournament to Vitality Blast (cross-tier, decided per
     §8 #1: persists, results empty) — `team_class` persists; results
     panel shows the literal empty-state hint
     "Vitality Blast is in the secondary tier" (substring).
   - Switch tournament dropdown to "All" — `team_class` survives.

4. **`team_class_club_per_tab_narrowing.sh`** — apply tier on each
   subtab and assert literal anchor counts. Each row asserts:
   "Mumbai Indians page under `?team_type=club&team_class=primary_club&season_from=2024&season_to=2025`
   shows literal text '30 matches' in the team header" (anchor P6).
   - Teams › Mumbai Indians + primary_club → "30 matches" (P6).
   - Teams › Mumbai Indians + secondary_club → empty state (P7).
   - Teams › Surrey + secondary_club → "30 matches" (P10).
   - Teams › Surrey + primary_club → empty state (P9).
   - Series tab + primary_club → "548" total (P2; substring of
     header). Tournament dropdown contents are literal — assert all
     11 primary-tier event names appear (10 men's + The Hundred
     Men's — wait, that's 10 men's including The Hundred — confirm
     count is **10 men's primary + 4 women's primary = 14 events
     when gender unset**).
   - Players tab › SM Curran + primary_club → batter dossier shows
     "1210 runs" (X-component of X5).
   - Players tab › SM Curran + secondary_club → "602 runs"
     (X-component of X6).
   - H2H tab › MI vs CSK + primary_club → "3 matches" (H2).
   - Matches tab + primary_club, gender=male, season=2024-2025 → row
     count == 548 (P2). Run via DOM count.
   - Venues tab › Kennington Oval + primary_club → "10 matches"
     (V5); + secondary_club → "15 matches" (V6).

5. **`team_class_club_compare.sh`** — Compare-tab inheritance,
   override, and chip direction.
   - Open Teams › Mumbai Indians › Compare with
     `?team_class=primary_club&season_from=2024&season_to=2025` →
     primary column shows MI batting RR literal "9.61" (C1/C2,
     rounded; 9.6140 truncated to 2dp).
   - Default avg slot (compare1=__avg__) inherits
     `team_class=primary_club` → avg slot's RR shows literal "8.89"
     (C4 rounded; LEAGUE-AVG with primary tier).
   - Click "+ Secondary-club avg in current scope" on slot 2 →
     URL gains `compare2_team_class=secondary_club`; slot 2 RR
     shows literal "8.60" (C5 rounded).
   - SlotHeaderChip on slot 2 must show "below avg" with magnitude
     ≈ +0.0 vs primary's avg. Note that secondary chip on a primary-
     scope team is somewhat meta — assert ONLY that chip renders,
     not magnitude direction (chip-direction is one of the v3 §10
     parked edge cases).
   - Open SlotScopeEditor for slot 2 → Class dropdown shows
     "Secondary" pre-selected (literal text).
   - Switch slot 2 back to "(inherit)" → `compare2_team_class`
     dropped from URL; slot 2 RR returns to primary inheritance
     value 8.89.
   - Force a club→intl Type switch from Compare tab — assert
     `compare1_team_class` AND `compare2_team_class` URL keys are
     stripped if they hold club-tier values (sanitize fan-out).

6. **`team_class_club_landing_buckets.sh`** — Teams landing-page
   bucketing under tier filter (without phase-2 rename).
   - Open `/teams?team_type=club&team_class=primary_club` → assert
     the four existing landing-page sections (franchise_leagues,
     domestic_leagues, women_franchise, other) render with **only**
     primary-tier tournaments populated. Specifically:
     - Vitality Blast section (in domestic_leagues bucket today):
       must show ZERO teams (its event_name is in
       `SECONDARY_CLUB_LEAGUES`, the API filter zeroes it out).
     - SMA Trophy: zero.
     - IPL section: 10 teams listed (BBL teams); 8 teams listed for
       BBL etc. (assert literal team names — Mumbai Indians, Sunrisers
       Hyderabad, … from the unbounded landing).
     - This section's "buckets stay; tournaments inside are
       tier-filtered" semantic is the deliberate UX phase-1
       behaviour. Phase-2 is the rename.
   - Open `/teams?team_type=club&team_class=secondary_club` →
     assert: IPL section empty, Vitality Blast section full, SMA
     full. Each event-name section's literal team set asserted.

Each script begins with the standard ab/agent-browser preamble used
by `team_class_filterbar.sh`. PASS/FAIL summary per CLAUDE.md.

**Test count:** 6 integration scripts, ~70 assertions total. Each
assertion is a literal-text DOM check (no "renders correctly"
verdicts).

### 6.4 Browser-agent verification (one-shot, post-merge)

After commits 1-N land, a single agent-browser session walks the
golden path:

- Teams › `?team_type=club&team_class=primary_club` →
  - landing list shows only IPL, BBL, PSL, …, WBBL teams (one
    representative team name per league cited literally in the audit
    output).
  - Mumbai Indians dossier under this scope → results count 15;
    counts on every tab (batting/bowling/fielding/partnerships) sane
    (positive, < unbounded counts).
  - Surrey dossier under this scope → "no matches in scope" empty
    state (zero everywhere).
- Same path with `team_class=secondary_club` swap → Surrey shows
  matches, Mumbai Indians is empty.
- Compare tab: `?team_class=primary_club` then explicit slot override
  to secondary → screenshot compared cell-by-cell against the spec's
  expected differential.

Audit prompt is **literal-text-content**, not summary verdicts (per
CLAUDE.md "Audit prompt discipline"). Each assertion gets a paired
shell test entry above so the audit becomes durable.

---

## 7. Documentation

Mandatory updates per CLAUDE.md "Keeping docs in sync":

| Doc | What to add |
|---|---|
| `docs/api.md` | `team_class` query-param description on every endpoint that accepts FilterBarParams — extend to mention `primary_club` / `secondary_club` (intl-gate vs club-gate). Add 4 new example curl invocations: men-primary, men-secondary, women-primary, women-secondary. Re-curl one existing example to verify the param description renders in `/api/docs` Swagger. |
| `internal_docs/landing-pages.md` | Note that the FilterBar `team_class` pill becomes context-sensitive on Type. Note that the Teams landing-page bucketing (franchise / domestic / women_franchise / other) is unchanged in this phase — phase-2 reconciliation tracked. |
| `internal_docs/design-decisions.md` | New bullet: "`team_class` is polymorphic over `team_type`" — describe the dispatch and the silent-no-op gate. New bullet: "club-tier classification lives in `api/club_tiers.py`; landing-page bucketing lives in `api/tournament_canonical.py`. Two maps deliberately, not one." |
| `internal_docs/codebase-tour.md` | Add `api/club_tiers.py` to the api/ section. Add `internal_docs/club-tier-classification.md` and `internal_docs/club-tier-anchor-numbers.md` to the docs section. |
| `internal_docs/club-tier-classification.md` (NEW) | The full rationale doc — leagues, the marquee-international principle, the NPL bump-down call, the Vitality-Blast call, women's coverage, Super-Smash misclassification note. Captures the chat 2026-04-30 reasoning so future contributors don't re-litigate. |
| `internal_docs/club-tier-anchor-numbers.md` (NEW) | All 30 anchors from §5, with full SQL + expected counts. Pinned at spec-implementation time, not at spec time. |
| `internal_docs/how-stats-calculated.md` | Add a "tier-narrowed averages" subsection: when `team_class=primary_club` is set, every avg-pool slot aggregates only over matches in primary leagues. Note the gotcha that the league average jumps when you switch tiers (visible in C-row anchors). |
| `frontend/public/user-help.md` (or wherever user-help is hosted — verify) | New section under "FilterBar": "Class / tier toggle". Describe the binary FM toggle on intl, the three-way segmented control on club, and the per-tab impact. Add a Compare-tab subsection: tier inheritance + per-slot override. Quoting the FilterBar pill button text verbatim. |
| `CLAUDE.md` | Add `internal_docs/spec-filterbar-team-class-club.md` and `internal_docs/club-tier-classification.md` to the Pointers > Domain + UX section. |
| `internal_docs/enhancements-roadmap.md` | New entry. Cross-link this spec. |
| `internal_docs/next-session-ideas.md` | Update the next-session anchor (currently inning-split) once this work begins. |

Phase-2 reconciliation work to track separately (NOT in this spec):

- Fix Super Smash / Women's Super Smash classification in
  `tournament_canonical.py::TOURNAMENT_SERIES_TYPE` — they're
  provincial, not franchise. Move to a `domestic_league` /
  `women_domestic` bucket. This is a landing-page rename (visible UX
  change), so wants its own product call before shipping.
- Optionally rename landing-page sections to "Primary leagues" /
  "Secondary leagues" / "Women's primary" / "Women's secondary" —
  ties the section labels to the same vocabulary as the FilterBar
  pill. Phase-2 because it's a UX rename, not a filter capability.

---

## 8. Decisions (resolved 2026-04-30)

1. **Tournament + Tier interaction. RESOLVED → (a) honour both,
   show empty state with hint.** When user sets
   `tournament=Vitality Blast&team_class=primary_club`, render
   empty state with literal hint
   *"No matches — Vitality Blast is in the secondary tier; clear
   Tier or pick a primary-tier league."* Implemented in the empty-
   state component for the affected tabs. Tested as a literal text
   match in `team_class_club_persistence.sh`. Internally consistent
   with how every other FilterBar combination already behaves
   (e.g. `filter_team=India&team_type=club` → empty).

2. **Tournament dropdown narrowing. RESOLVED → (b) auto-narrow.**
   `/api/v1/tournaments` already accepts `team_class`; adding the
   param to the FilterBar's tournament-fetch removes the empty-state
   combination from the user's reach in the first place. Tested as
   a literal-events list assertion in
   `team_class_club_per_tab_narrowing.sh`: under primary, only the
   primary-tier event names appear in the dropdown.

3. **Sort order in segmented pill. RESOLVED → All / Primary /
   Secondary.** Hierarchical reading; matches the FM toggle
   precedent (off → on, never alphabetical).

4. **`team_class` in identity vs phrase URLs. RESOLVED → matches v3
   precedent.** `team_class` rides on phrase URLs (narrowing) but not
   on team-name identity URLs. A team's `/teams/<name>` route drops
   `team_class` so the team's intrinsic dossier scope is the team's
   own scope. Implemented in `scopeLinks.ts` already; no edit needed.

5. **Bucket-baseline rejection breadth. RESOLVED → reject all tier
   values.** Bucket tables don't carry tier-of-event, so live
   aggregation is the fallback whenever `team_class` is set. Tier-
   specific buckets are an explicit phase-2 follow-up if a perf
   regression surfaces.

---

## 9. Commit cadence

Per CLAUDE.md "Commit as soon as a feature looks complete — don't
batch":

- **C1.** `api/club_tiers.py` + module-level disjointness assert +
  `tests/sanity/test_team_class_club_baseline_numbers.py` skeleton.
  Lands the source of truth alone.
- **C2.** `api/filters.py` dispatch extension + cross-cutting backend
  routers (`tournaments.py`, `reference.py`, `bucket_baseline_dispatch.py`,
  `social_meta.py`). Every endpoint accepts the new values; defensive
  gate fires correctly. Sanity numbers anchored.
- **C3.** Regression URL inventory expansion (§6.2) + run
  `./tests/regression/run.sh <each>` until clean.
- **C4.** Frontend FilterBar pill polymorphism + auto-clear logic +
  `team_class_club_filterbar.sh` + `team_class_club_gating.sh`.
- **C5.** ScopeStatusStrip + scope-link integration (no edit needed,
  but verified by `team_class_club_persistence.sh`).
- **C6.** Compare-tab `SlotScopeEditor` widening + AddCompareSlot
  quick-picks + `team_class_club_compare.sh`.
- **C7.** Docs pass — every doc in §7 updated. Ends with a re-curl
  smoke check that `/api/docs` reflects the new param values.

Commits are independently reverteable; if the integration tests under
C4 reveal an auto-clear bug, the backend (C2) doesn't have to revert.

---

## 10. Out-of-scope explicit list

These are **not** in this spec; flagged here so they don't get
silently scope-crept in:

- **Renaming landing-page buckets** to primary/secondary. Phase 2.
- **Reclassifying Super Smash / Women's Super Smash** in
  `TOURNAMENT_SERIES_TYPE`. Phase 2 (sibling).
- **Multi-tier filtering** (`team_class=primary_club,secondary_club`
  list-style). Not needed; "All" already does this.
- **Bucket precompute under tier**. Live aggregation is fast enough.
- **Per-team-string tier classification**. The match-level `event_name`
  IN clause is sufficient; never list 200+ team strings when 22
  `event_name`s do the job.
- **A `tier` URL param distinct from `team_class`**. The CLAUDE.md
  "extend, don't fork" rule is the explicit reason. If the future
  brings a third dimension that doesn't fit `team_class` (e.g.
  player-class), open a new key then — not preemptively.
