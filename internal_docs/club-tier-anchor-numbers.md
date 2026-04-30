# club-tier `team_class` — DB-direct anchor numbers

Pinned ground-truth values for
`tests/sanity/test_team_class_club_baseline_numbers.py`. Derived
from the live DB on 2026-04-30.

Spec: `internal_docs/spec-filterbar-team-class-club.md` §5.

## Provenance

- **DB**: `/Users/rahul/Projects/cricsdb/cricket.db` (snapshot
  2026-04-30).
- **Tier sets** (hard-coded in `api/club_tiers.py`):
  - **PRIMARY_CLUB_LEAGUES** (14):
    Indian Premier League, Big Bash League, Pakistan Super League,
    Bangladesh Premier League, Caribbean Premier League, SA20,
    International League T20, Lanka Premier League, Major League
    Cricket, The Hundred Men's Competition, Women's Big Bash League,
    Women's Premier League, The Hundred Women's Competition,
    Women's Cricket Super League.
  - **SECONDARY_CLUB_LEAGUES** (7):
    Vitality Blast, Syed Mushtaq Ali Trophy, CSA T20 Challenge,
    Super Smash, Nepal Premier League, Women's Super Smash, New
    Zealand Cricket Women's Twenty20.
- **Closed window** (men's): `gender='male'`, `team_type='club'`,
  `season IN ('2024', '2024/25', '2025')`. Same as v3's intl window.
- **Super-over exclusion**: `i.super_over=0` on every batting / bowling
  delivery aggregation.

---

## P-series — match counts (men's club, 2024-25 window)

| Anchor | Description | Result |
|---|---|---|
| P1  | Total club male, no `team_class` | **901** |
| P2  | Same scope, `team_class=primary_club` | **548** |
| P3  | Same scope, `team_class=secondary_club` | **353** |
| P4  | Disjointness: `P2 + P3 == P1` | **548 + 353 = 901 ✓** |
| P5  | Mumbai Indians, no `team_class` | **30** |
| P6  | Mumbai Indians, `primary_club` (no-op — MI ∈ primary) | **30** |
| P7  | Mumbai Indians, `secondary_club` (cross-tier) | **0** |
| P8  | Surrey, no `team_class` | **30** |
| P9  | Surrey, `primary_club` (cross-tier) | **0** |
| P10 | Surrey, `secondary_club` (no-op — Surrey ∈ secondary) | **30** |
| P11 | Baroda (small SMA team), no `team_class` | **2** |
| P12 | Baroda, `secondary_club` | **2** |

### Per-event breakdown in window

```
PRIMARY (P2 = 548):
  IPL=145, Hundred(M)=68, CPL=66, MLC=56, BPL=46, BBL=42, PSL=34,
  ILT20=34, SA20=33, LPL=24
SECONDARY (P3 = 353):
  Vitality Blast=258, NPL=32, Super Smash=29, CSA T20=26, SMA=8
```

### SQL

```sql
-- P1
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='club' AND season IN ('2024','2024/25','2025');

-- P2 (replace event list for primary set)
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='club' AND season IN ('2024','2024/25','2025')
  AND event_name IN ('Indian Premier League','Big Bash League','Pakistan Super League',
                     'Bangladesh Premier League','Caribbean Premier League','SA20',
                     'International League T20','Lanka Premier League',
                     'Major League Cricket','The Hundred Men''s Competition');

-- P3 (replace event list for secondary set)
-- Same as P2 with: ('Vitality Blast','Syed Mushtaq Ali Trophy','CSA T20 Challenge',
--                   'Super Smash','Nepal Premier League')

-- P5 / P6 / P7 — replace 'Mumbai Indians' for Surrey / Baroda
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='club' AND season IN ('2024','2024/25','2025')
  AND (team1='Mumbai Indians' OR team2='Mumbai Indians')
  -- + AND <event_name IN primary> for P6
  -- + AND <event_name IN secondary> for P7
  ;
```

---

## INV-series — whole-DB partition

Asserted across the FULL DB (not the 2024-25 window). The
completeness invariant is the load-bearing CI guard against
classification drift.

| Anchor | Description | Result |
|---|---|---|
| INV1 | All `team_type=club` AND `match_type=T20` | **7,573** |
| INV2 | Same + event_name in PRIMARY_CLUB_LEAGUES | **4,578** |
| INV3 | Same + event_name in SECONDARY_CLUB_LEAGUES | **2,995** |
| INV4 | Untagged (event_name in neither set) | **0** ✓ |
| INV5 | INV2 + INV3 == INV1 | **4,578 + 2,995 = 7,573 ✓** |

If `update_recent` introduces a new club T20 event, INV4 fails CI
with the event name. Slot it into the appropriate frozenset before
merging.

---

## G-series — defensive-gate proofs (cross-type silent no-op)

Each G-row asserts the API returns the unbounded count, NOT zero,
when given a cross-type `team_class` value.

| Anchor | Description | Result |
|---|---|---|
| G1 | India intl 2024-25, no `team_class` | **34** (= v3 A5) |
| G2 | Same + `team_class=primary_club` (cross-type) | **34** ✓ |
| G3 | Same + `team_class=secondary_club` (cross-type) | **34** ✓ |
| G4 | RCB IPL 2025, no `team_class` | **15** (= v3 B1) |
| G5 | MI club 2024-25, `team_class=full_member` (cross-type) | **30** |
| G6 | RCB IPL primary (same-type, tautological) | **15** ✓ |

---

## V-series — venue interaction (single-tier + multi-tier)

| Anchor | Description | Result |
|---|---|---|
| V1 | Wankhede club male 2024-25, unbounded | **14** |
| V2 | Wankhede + `primary_club` (only IPL hosted) | **14** |
| V3 | Wankhede + `secondary_club` | **0** |
| V4 | Kennington Oval, unbounded (multi-tier — Surrey VBlast + Oval Invincibles Hundred) | **25** |
| V5 | Kennington Oval + `primary_club` (Hundred only) | **10** |
| V6 | Kennington Oval + `secondary_club` (Vitality Blast only) | **15** |

V4 = V5 + V6 = 25 — multi-tier venue partitions cleanly. Catches
clause-composition bugs (e.g. an OR'd clause when AND was expected).

---

## H-series — head-to-head rivalry under tier

| Anchor | Description | Result |
|---|---|---|
| H1 | MI vs CSK 2024-25 club male, unbounded | **3** |
| H2 | Same + `primary_club` (no-op) | **3** |
| H3 | Surrey vs Somerset 2024-25, unbounded | **5** |
| H4 | Same + `secondary_club` (no-op) | **5** |

---

## X-series — cross-tier player narrowing (SM Curran)

SM Curran (`person_id='e94915e6'`) plays in both Vitality Blast
(Surrey, secondary) and IPL/MLC/Hundred (primary).

| Anchor | Description | Result |
|---|---|---|
| X1 | SMC unbounded matches | **69** |
| X2 | SMC `primary_club` | **49** |
| X3 | SMC `secondary_club` | **20** |
| X4 | X2 + X3 == X1 | **49 + 20 = 69 ✓** |
| X5 | SMC total batting runs, unbounded | **1,812** |
| X6 | Runs split: primary 1,210 + secondary 602 = 1,812 ✓ | **1,210 / 602 / 1,812** |

X-series exercises the **player dossier under tier filters**. The
two narrowed counts must sum to unbounded — catches double-counting
bugs in `i.team` (batter side) vs match-level filter composition.

---

## C-series — chip baselines (run rates)

Run rate formula:
`SUM(d.runs_total) * 6.0 / SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END)`

| Anchor | Description | runs | legal_balls | RR (4dp) |
|---|---|---|---|---|
| C1 | MI batting RR, club male 2024-25 unbounded | 5,480 | 3,420 | **9.6140** |
| C2 | MI batting RR, + `primary_club` (no-op — MI ∈ primary) | 5,480 | 3,420 | **9.6140** |
| C3 | League batting RR, club male 2024-25 unbounded | 289,977 | 198,211 | **8.7778** |
| C4 | League batting RR, + `primary_club` | 177,551 | 119,815 | **8.8913** |
| C5 | League batting RR, + `secondary_club` | 112,426 | 78,396 | **8.6045** |
| C6 | Surrey batting RR, club male 2024-25 unbounded | 5,158 | 3,334 | **9.2825** |
| C7 | Surrey batting RR, + `secondary_club` (no-op — Surrey ∈ secondary) | 5,158 | 3,334 | **9.2825** |

**C3 ≠ C4 ≠ C5** is the load-bearing "league average actually
shifts" assertion. Primary-tier RR is **0.11 runs/over above**
unbounded; secondary-tier is **0.17 below**. Confirms the
delivery-level partition is disjoint:
- C4_runs + C5_runs = 177,551 + 112,426 = 289,977 ✓ (= C3_runs)
- C4_legal + C5_legal = 119,815 + 78,396 = 198,211 ✓ (= C3_legal)

---

## BWL — bowling-side baselines

Bowling-side aggregation uses `i.team = m.opponent_of(MI)` —
exercises `filters.py::build_side_neutral`'s code path.

| Anchor | Description | runs | legal_balls | ER (4dp) |
|---|---|---|---|---|
| BWL1 | MI bowling ER, club male 2024-25 unbounded | 5,376 | 3,444 | **9.3659** |
| BWL2 | MI bowling ER, + `primary_club` (no-op) | 5,376 | 3,444 | **9.3659** |

---

## W-series — women's club partition

| Anchor | Description | Result |
|---|---|---|
| W1 | Total women club 2024-25 | **162** |
| W2 | + `primary_club` | **131** |
| W3 | + `secondary_club` | **31** |
| W4 | W2 + W3 == W1 | **131 + 31 = 162 ✓** |

Per-event breakdown in window:
- Primary: WBBL 2024/25 = 42, WPL 2024/25 = 22, The Hundred Women
  2024 = 33 + 2025 = 34. Total = 131 ✓
- Secondary: Women's Super Smash 2024/25 = 31. Total = 31 ✓
- (NZC Women's T20 has no matches in this season set; older seasons
  surface in a wider window.)

---

## T-series — distinct team strings (whole DB)

| Anchor | Description | Result |
|---|---|---|
| T1 | Distinct men's primary team strings | **105** |
| T2 | Distinct men's secondary team strings | **83** |
| T3 | Distinct women's primary team strings | **27** |
| T4 | Distinct women's secondary team strings | **6** |
| T5 | Cross-tier team-string intersection | **0** ✓ |

T5 = 0 is the **disjoint-team-string invariant** — a team string
appears in exactly one tier across the whole DB.

---

## B-list — top-10 batters by total runs (2024-25 club male window)

Sort: `SUM(runs_batter) DESC, batter_id DESC`. Tiebreak makes
SQLite output deterministic for the test.

### B-unb (unbounded — top 10)

| rank | person_id | name | runs |
|---|---|---|---|
| 1  | 3241e3fd | N Pooran           | 3,021 |
| 2  | 3355b542 | F du Plessis       | 2,219 |
| 3  | a15618fe | JM Vince           | 2,204 |
| 4  | 92aeac25 | AD Hales           | 1,881 |
| 5  | e94915e6 | SM Curran          | 1,812 |
| 6  | f836b33d | T Kohler-Cadmore   | 1,790 |
| 7  | 9caf69a1 | WG Jacks           | 1,770 |
| 8  | 372455c4 | Q de Kock          | 1,765 |
| 9  | 1fc6ef83 | SD Hope            | 1,756 |
| 10 | 4663bd23 | TL Seifert         | 1,710 |

### B-pri (`primary_club` — top 10)

| rank | person_id | name | runs |
|---|---|---|---|
| 1  | 3241e3fd | N Pooran           | 3,021 |
| 2  | 3355b542 | F du Plessis       | 2,219 |
| 3  | 372455c4 | Q de Kock          | 1,765 |
| 4  | 1fc6ef83 | SD Hope            | 1,756 |
| 5  | 92aeac25 | AD Hales           | 1,743 |
| 6  | 4663bd23 | TL Seifert         | 1,710 |
| 7  | 48a1d7b7 | SO Hetmyer         | 1,674 |
| 8  | 235c2bb6 | H Klaasen          | 1,554 |
| 9  | ba607b88 | V Kohli            | 1,398 |
| 10 | a15618fe | JM Vince           | 1,394 |

### B-sec (`secondary_club` — top 10, Vitality Blast / SMA dominated)

| rank | person_id | name | runs |
|---|---|---|---|
| 1  | 7ca5e05d | RS Bopara          | 1,088 |
| 2  | 67b9536c | SR Hain            | 1,029 |
| 3  | f836b33d | T Kohler-Cadmore   | 943 |
| 4  | f3982af9 | DP Hughes          | 940 |
| 5  | 35f173a0 | MP Breetzke        | 933 |
| 6  | 270e4c23 | MS Pepper          | 899 |
| 7  | 4e18e961 | WCF Smeed          | 880 |
| 8  | a6c17509 | TE Albert          | 859 |
| 9  | ab01e323 | SA Zaib            | 852 |
| 10 | 10b79140 | TS Muyeye          | 814 |

Cross-tier signals:
- **N Pooran's 3,021** under primary equals unbounded — purely
  franchise-tier player.
- **JM Vince** (Hampshire / pri-MLC) drops from #3 unbounded to #10
  primary — the county runs visible split.
- **T Kohler-Cadmore** appears in both lists — exemplary
  cross-tier player; verifies the API surfaces the right subset
  under each tier filter.

---

## BWL-list — top-10 bowlers by wickets (2024-25 club male window)

Sort: `COUNT(*) DESC, bowler_id DESC`. Excludes
`run out / retired hurt / retired out / obstructing the field`.

### BWL-unb (unbounded — top 10)

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

### BWL-pri (`primary_club` — top 10)

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

### BWL-sec (`secondary_club` — top 10, Vitality Blast attack)

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
- **SM Curran** (#5 unbounded with 76 wkts) drops to #8 primary
  with 53; the missing 23 are his Vitality Blast haul.
- **TS Mills** (#4 unbounded with 77) drops out of primary entirely;
  surfaces in secondary at #5 with 42. Implies he's a pure-secondary
  bowler in this window.
