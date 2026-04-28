# team_class FilterBar — DB-direct anchor numbers

Pinned ground-truth values for `tests/sanity/test_team_class_baseline_numbers.py`.
Derived directly from `cricket.db` via `sqlite3` CLI by a DB-only subagent
(no `api/` source read). Spec: `internal_docs/spec-filterbar-team-class-v3.md` §7.

## Provenance

- **DB:** `/Users/rahul/Projects/cricsdb/cricket.db` (snapshot as of 2026-04-28).
- **FM list (hard-coded, NOT read from `api/full_members.py`):**
  Afghanistan, Australia, Bangladesh, England, India, Ireland,
  New Zealand, Pakistan, South Africa, Sri Lanka, West Indies, Zimbabwe.
- **Scope window for sections A, C, D:** `gender='male'` (or `'female'` for D),
  `team_type='international'`, `season IN ('2024', '2024/25', '2025')`.
- **Super-over exclusion:** `i.super_over = 0` on every batting/bowling aggregation.

### Scope-window discrepancy with task spec

The task instruction listed the season set as `('2024', '2024/25', '2025/26')`
AND simultaneously said "this maps to `season >= '2024' AND season <= '2026'`".
Neither produces the spec's expected counts (Australia 22, India 34).

After binary search, the actual season set that reproduces the spec's expected
anchors is **`('2024', '2024/25', '2025')`** — i.e. omit `2025/26`, include
plain `'2025'`. This is what we pin below. Any test that wants to assert
"men_intl 2024-25" must use this exact IN-list.

For reference, season counts in the wider window:
| season | matches (men_intl) |
|---|---|
| 2024 | 333 |
| 2024/25 | 222 |
| 2025 | 315 |
| 2025/26 | 298 |
| 2026 | 28 |

---

## A — Intl narrowing (where team_class actually fires)

| Anchor | Description | Result |
|---|---|---|
| A1 | Total men_intl 2024-25 matches, no team_class filter | **870** |
| A2 | Same scope, FM-only (team1 AND team2 ∈ FM list) | **140** |
| A3 | Australia men_intl 2024-25, unbounded | **22** |
| A4 | Australia men_intl 2024-25, FM-only | **16** |
| A5 | India men_intl 2024-25, unbounded | **34** |
| A6 | India men_intl 2024-25, FM-only | **31** |
| A7 | Scotland men_intl 2024-25, unbounded | **17** |
| A8 | Scotland men_intl 2024-25, FM-only | **0** |

### Exact SQL

```sql
-- A1
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='international'
  AND season IN ('2024','2024/25','2025');

-- A2
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='international'
  AND season IN ('2024','2024/25','2025')
  AND team1 IN ('Afghanistan','Australia','Bangladesh','England','India','Ireland',
                'New Zealand','Pakistan','South Africa','Sri Lanka','West Indies','Zimbabwe')
  AND team2 IN ('Afghanistan','Australia','Bangladesh','England','India','Ireland',
                'New Zealand','Pakistan','South Africa','Sri Lanka','West Indies','Zimbabwe');

-- A3 (replace 'Australia' for A5/A7)
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='international'
  AND season IN ('2024','2024/25','2025')
  AND (team1='Australia' OR team2='Australia');

-- A4 (replace 'Australia' for A6/A8) — A3 + FM-list AND clause
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='international'
  AND season IN ('2024','2024/25','2025')
  AND (team1='Australia' OR team2='Australia')
  AND team1 IN (<FM list>) AND team2 IN (<FM list>);
```

### A9 — Top-10 batters by total runs, men_intl 2024-25 unbounded

```sql
SELECT d.batter_id, p.name, SUM(d.runs_batter) AS runs
FROM delivery d
JOIN innings i ON i.id=d.innings_id
JOIN match m ON m.id=i.match_id
JOIN person p ON p.id=d.batter_id
WHERE m.gender='male' AND m.team_type='international'
  AND m.season IN ('2024','2024/25','2025')
  AND i.super_over = 0
GROUP BY d.batter_id
ORDER BY runs DESC
LIMIT 10;
```

| rank | person_id | name | runs |
|---|---|---|---|
| 1 | 6a97c7a4 | Karanbir Singh | 1420 |
| 2 | 6f02fe2a | Waseem Muhammad | 1173 |
| 3 | df1f2f29 | Fiaz Ahmed | 1060 |
| 4 | 33b67317 | Bilal Zalmai | 997 |
| 5 | 552b228c | Anshuman Rath | 990 |
| 6 | 06cad4f0 | A Sharafu | 977 |
| 7 | 074acfb4 | Asif Khan | 975 |
| 8 | 8ee36b18 | P Nissanka | 974 |
| 9 | 987187b9 | Zeeshan Ali | 914 |
| 10 | e3eb9e46 | Nizakat Khan | 910 |

(All but P Nissanka are associate-team batters — exactly the kind of leaderboard
distortion the FM filter is designed to remove.)

### A10 — Top-10 batters by total runs, men_intl 2024-25 FM-only

Same SQL as A9 + `AND m.team1 IN (<FM>) AND m.team2 IN (<FM>)`.

| rank | person_id | name | runs |
|---|---|---|---|
| 1 | 8ee36b18 | P Nissanka | 906 |
| 2 | 99b75528 | JC Buttler | 802 |
| 3 | f29185a1 | Abhishek Sharma | 781 |
| 4 | 3d284ca3 | PD Salt | 765 |
| 5 | b0482a1d | Tilak Varma | 597 |
| 6 | b8cc58c9 | RR Hendricks | 594 |
| 7 | 1fc6ef83 | SD Hope | 594 |
| 8 | 33609a8c | Saim Ayub | 574 |
| 9 | 9e52a414 | Towhid Hridoy | 567 |
| 10 | a4cc73aa | SV Samson | 563 |

(Spec text predicted "Suryakumar / Yashasvi rise" — neither appears in the FM
top-10 in this exact scope. Surprises noted at end of doc.)

### A11 — Top-10 bowlers by wickets, men_intl 2024-25 unbounded

```sql
SELECT d.bowler_id, p.name, COUNT(DISTINCT w.id) AS wickets
FROM delivery d
JOIN innings i ON i.id=d.innings_id
JOIN match m ON m.id=i.match_id
JOIN wicket w ON w.delivery_id=d.id
JOIN person p ON p.id=d.bowler_id
WHERE m.gender='male' AND m.team_type='international'
  AND m.season IN ('2024','2024/25','2025')
  AND i.super_over = 0
  AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field')
GROUP BY d.bowler_id
ORDER BY wickets DESC
LIMIT 10;
```

| rank | person_id | name | wickets |
|---|---|---|---|
| 1 | e741ed8f | Rizwan Butt | 68 |
| 2 | 596982e6 | Ali Dawood | 59 |
| 3 | d3851cd8 | Ehsan Khan | 47 |
| 4 | c9d05f1a | Yasim Murtaza | 46 |
| 5 | 5935d694 | Rishad Hossain | 45 |
| 6 | 3c8faed4 | F Banunaek | 44 |
| 7 | ef18b66e | Taskin Ahmed | 43 |
| 8 | 84dc72db | Junaid Siddique | 43 |
| 9 | a9a18e3e | Imran Anwar | 42 |
| 10 | a62f55ba | DJ Hawoe | 42 |

### A12 — Top-10 bowlers by wickets, men_intl 2024-25 FM-only

Same SQL as A11 + `AND m.team1 IN (<FM>) AND m.team2 IN (<FM>)`.

| rank | person_id | name | wickets |
|---|---|---|---|
| 1 | 5b7ab5a9 | CV Varun | 37 |
| 2 | 45a7e761 | Shaheen Shah Afridi | 37 |
| 3 | 24bb1c2f | Haris Rauf | 34 |
| 4 | 5935d694 | Rishad Hossain | 33 |
| 5 | 2cec2a92 | Abbas Afridi | 33 |
| 6 | ef18b66e | Taskin Ahmed | 32 |
| 7 | a97c8ec2 | PWH de Silva | 32 |
| 8 | 244048f6 | Arshdeep Singh | 31 |
| 9 | dadbdb68 | JA Duffy | 28 |
| 10 | 249d60c9 | AU Rashid | 28 |

---

## B — ICC events + rivalries + venue + women's

| Anchor | Description | Result |
|---|---|---|
| A13 | ICC Men's T20 World Cup matches in scope, unbounded | **44** |
| A14 | ICC Men's T20 World Cup matches in scope, FM-only | **16** |
| A15a | India-vs-Australia matches in scope, unbounded | **1** |
| A15b | India-vs-Australia matches in scope, FM-only | **1** |
| A16a | India-vs-Scotland matches in scope, unbounded | **0** |
| A16b | India-vs-Scotland matches in scope, FM-only | **0** |
| A17 | Wankhede Stadium intl 2024-25 matches, unbounded | **1** |
| A18 | Wankhede Stadium intl 2024-25 matches, FM-only | **1** |

### Exact SQL

```sql
-- A13: T20 WC matches, unbounded
SELECT COUNT(*) FROM match
WHERE event_name='ICC Men''s T20 World Cup'
  AND gender='male' AND team_type='international'
  AND season IN ('2024','2024/25','2025');

-- A14: + FM-list AND clause

-- A15a: Ind-Aus rivalry
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='international'
  AND season IN ('2024','2024/25','2025')
  AND ((team1='India' AND team2='Australia') OR (team1='Australia' AND team2='India'));

-- A15b: + FM-list (no-op, both already FM)
-- A16a: replace 'Australia' with 'Scotland' in A15a
-- A16b: A16a + FM-list (Scotland not FM → 0)

-- A17: Wankhede, unbounded
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='international'
  AND season IN ('2024','2024/25','2025')
  AND venue='Wankhede Stadium';

-- A18: A17 + FM-list AND clause
```

### Notes on ICC event names

- Only `'ICC Men''s T20 World Cup'` matches the canonical event_name in scope.
  Legacy strings (`'World T20'`, `'ICC World Twenty20'`) returned 0 in this
  window. Qualifier rounds (`...Region Final`, `...Asia Qualifier`, etc.) have
  separate event_names and are NOT included in A13/A14.
- The 44-match count covers the 2024 group/Super-8/knockout (44 in season
  `'2024'`) plus 0 in `'2024/25'`/`'2025'`. The spec's earlier prediction of
  "55 per existing data" likely included qualifiers; the canonical-event-only
  count is **44**.

### Notes on rivalries

- **India vs Australia in scope = 1 match** (the 2024 T20 WC Super-8 game).
  Both modes return 1 — both teams are FM, so the FM filter is a no-op.
- **India vs Scotland = 0** in both modes (they did not meet in this scope).
  This anchors the "FM excludes associate" semantic differently than the spec
  predicted, but the sanity-test logic ("FM ≤ unbounded; FM=0 when one side
  is non-FM") still holds.

---

## C — Compare-grid chip baselines (numerical run-rate references)

Run rate formula:
`SUM(d.runs_total) * 6.0 / SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END)`

| Anchor | Description | total_runs | legal_balls | RR (4dp) |
|---|---|---|---|---|
| C1 | Australia batting RR, men_intl 2024-25 unbounded | 3614 | 2187 | **9.9150** |
| C2 | Australia batting RR, men_intl 2024-25 FM-only | 2685 | 1640 | **9.8232** |
| C3 | League batting RR, men_intl 2024-25 unbounded | 232077 | 185238 | **7.5172** |
| C4 | League batting RR, men_intl 2024-25 FM-only | 43059 | 30404 | **8.4974** |

### Exact SQL (C1; others swap team filter / add FM clause)

```sql
SELECT SUM(d.runs_total) * 6.0
       / SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END)
       AS run_rate
FROM delivery d
JOIN innings i ON i.id=d.innings_id
JOIN match m ON m.id=i.match_id
WHERE m.gender='male' AND m.team_type='international'
  AND m.season IN ('2024','2024/25','2025')
  AND i.super_over = 0
  AND i.team='Australia';   -- omit for C3/C4 (league RR)
-- C2/C4: + AND m.team1 IN (<FM>) AND m.team2 IN (<FM>)
```

### Sanity check on the chip semantics

- **Australia's RR barely moves** (9.92 → 9.82) under the FM filter — Aus
  played mostly FM teams already, so dropping the 6 non-FM matches shifts
  the rate by ~0.1.
- **The league RR jumps** (7.52 → 8.50) — the unbounded league pool is
  diluted by associate-team matches with low scoring; restricting to
  FM-only lifts the baseline ~1.0.
- This means **Australia's chip flips direction** between modes:
  unbounded scope → Aus 9.92 vs league 7.52 = +32% (good); FM-only scope
  → Aus 9.82 vs league 8.50 = +15.6% (still good but dramatically lower
  delta). This is the core semantic the FilterBar widget exposes.

---

## D — Women's intl symmetry

| Anchor | Description | Result |
|---|---|---|
| D1 | Total women_intl 2024-25 matches, unbounded | **596** |
| D2 | Same scope, FM-only | **97** |

### Exact SQL

```sql
SELECT COUNT(*) FROM match
WHERE gender='female' AND team_type='international'
  AND season IN ('2024','2024/25','2025');
-- D2: + AND team1 IN (<FM>) AND team2 IN (<FM>)
```

The FM list is the same 12 ICC full members for both genders (per task
spec). Net: women_intl narrows ~6.1× under FM (596 → 97), comparable to
men_intl's ~6.2× (870 → 140) — the symmetry holds.

---

## B-prime — Club no-op (defensive gate)

These anchor the rule: when `team_type='club'`, applying `team_class=full_member`
must be a no-op (the FM list contains country names, not franchises — every
club match's `team1`/`team2` would fail the FM check, collapsing the result
set to 0). The backend gate must reject `team_class` whenever team_type≠'international'.

| Anchor | Description | Result |
|---|---|---|
| B1 | RCB IPL 2025 matches, no team_class | **15** |
| B2 | Same query + FM AND clause applied directly to SQL | **0** ⚠️ |
| B3 | SRH IPL 2025 matches, no team_class | **14** |
| B4 | All IPL 2025 matches | **74** |

### Exact SQL

```sql
-- B1 (B3 swaps RCB for SRH)
SELECT COUNT(*) FROM match
WHERE event_name='Indian Premier League' AND season='2025'
  AND (team1='Royal Challengers Bengaluru' OR team2='Royal Challengers Bengaluru');

-- B2: B1 + FM AND clause directly (proves naive application breaks clubs)
SELECT COUNT(*) FROM match
WHERE event_name='Indian Premier League' AND season='2025'
  AND (team1='Royal Challengers Bengaluru' OR team2='Royal Challengers Bengaluru')
  AND team1 IN (<FM list>) AND team2 IN (<FM list>);

-- B4
SELECT COUNT(*) FROM match
WHERE event_name='Indian Premier League' AND season='2025';
```

### Test interpretation

- **B1 = 15, B2 = 0** is the failing case the gate prevents. The sanity
  test should assert: when calling the API with `team_type=club&team_class=full_member`,
  the response equals B1 (15), NOT B2 (0). I.e. the API must drop the
  team_class filter when team_type=club.
- **B3, B4** are control anchors for any /scope/averages/* endpoint that
  fans out without team1 selected.

---

## Summary

**Total anchors derived: 28**
- A1–A8: 8 match-count anchors (intl narrowing)
- A9, A10, A11, A12: 4 top-10 leaderboards (40 individual rows)
- A13–A18: 6 anchors (ICC events, rivalries, venue)
- C1–C4: 4 RR anchors
- D1–D2: 2 women's intl anchors
- B1–B4: 4 club no-op anchors

### Surprises / discrepancies vs spec §7 prose

1. **Scope window:** the task instruction said `season IN ('2024','2024/25','2025/26')`
   AND `season >= '2024' AND season <= '2026'` — neither produces the
   "Aus 22 / India 34" anchors. Correct scope is
   **`('2024','2024/25','2025')`**. Pinned at top of doc.
2. **A1 = 870, not ~1196** as the spec text predicted. The 1196 figure was
   under the broader `season >= '2024' AND season <= '2026'` (which includes
   `'2025/26'` and `'2026'`).
3. **A13 = 44, not 55.** Canonical event_name `'ICC Men''s T20 World Cup'`
   only includes the 2024 main draw (group + Super-8 + knockouts); qualifier
   rounds have separate event_names. A 55 figure would require unioning
   in qualifier strings.
4. **A10 top-10 doesn't include Suryakumar / Yashasvi.** The actual FM-only
   top-10 is led by Nissanka, Buttler, Abhishek Sharma, Salt — likely
   because IPL-style high-volume Indian batters didn't all play enough
   bilateral T20Is in this window. Spec prose was directional, not literal;
   the pinned list is the actual leaderboard.
5. **A15 (Ind-Aus) = 1, not "many".** They only met once in this scope (the
   2024 T20 WC Super-8). The "identical in both modes" assertion still
   holds (1 = 1).
6. **A16 (Ind-Sco) = 0 unbounded too.** They didn't play in this window.
   The spec predicted "any → 0" implying some non-zero unbounded count
   that drops to 0 under FM; in fact it's 0 → 0. The test logic must
   be "FM ≤ unbounded; both 0 still satisfies the invariant."
7. **A17 (Wankhede) = 1**, not the larger figure spec implied. Only one
   men_intl match was at Wankhede in this scope. FM-only = 1 (same match
   was Ind-Eng or similar — both FM).

### File path
`/Users/rahul/Projects/cricsdb/internal_docs/team-class-anchor-numbers.md`
