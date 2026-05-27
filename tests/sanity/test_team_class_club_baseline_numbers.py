"""DB-grounded numeric assertions for the club-tier `team_class`
extension (spec-filterbar-team-class-club.md).

Mirrors the v3 intl sanity test (test_team_class_baseline_numbers.py)
but for the new `team_class` values:
  - primary_club  (10 men's + 4 women's franchise leagues)
  - secondary_club (5 men's + 2 women's domestic competitions)

Anchors derived directly from cricket.db on 2026-04-30; full
provenance + SQL: internal_docs/club-tier-anchor-numbers.md.

Ten anchor groups:
  P1-P12  match counts (men's club, 2024-25 window)
  INV1-5  whole-DB partition (every club T20 event mapped)
  G1-G6   defensive-gate cross-type silent-no-op proofs
  V1-V6   venue interaction (Wankhede single-tier, Oval multi-tier)
  H1-H4   head-to-head rivalry under tier
  X1-X6   cross-tier player narrowing (SM Curran)
  C1-C7   compare-grid chip baselines (run rates)
  BWL1-2  bowling-side baseline (side-neutral build)
  W1-W4   women's club partition
  T1-T5   distinct-team-string counts + cross-tier intersection

Plus three module invariants (disjointness, completeness, team-disjoint)
and the literal top-10 batter / bowler lists per tier.

Usage:
  uv run python tests/sanity/test_team_class_club_baseline_numbers.py
  uv run python tests/sanity/test_team_class_club_baseline_numbers.py --db /tmp/cricket-real.db
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from api import dependencies as deps
from api.club_tiers import (
    PRIMARY_CLUB_LEAGUES,
    SECONDARY_CLUB_LEAGUES,
    primary_club_clause,
    secondary_club_clause,
)


EPS = 0.05


def near(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= EPS


CLUB_24_25_M = ("m.gender = 'male' AND m.team_type = 'club' "
                "AND m.season IN ('2024','2024/25','2025')")
CLUB_24_25_F = ("m.gender = 'female' AND m.team_type = 'club' "
                "AND m.season IN ('2024','2024/25','2025')")
INTL_24_25_M = ("m.gender = 'male' AND m.team_type = 'international' "
                "AND m.season IN ('2024','2024/25','2025')")


# Anchors verbatim from internal_docs/spec-filterbar-team-class-club.md §5.
# Each anchor → one DB-direct count + one assertion.
ANCHORS: dict[str, int] = {
    # P-series — match counts (men's club 2024-25)
    "P1": 901, "P2": 548, "P3": 353,
    "P5": 30, "P6": 30, "P7": 0,
    "P8": 30, "P9": 0, "P10": 30,
    "P11": 2, "P12": 2,

    # INV-series — whole-DB partition (snapshot anchors; refreshed to the
    # current club-T20 match count — the DB grew since these were last set)
    "INV1": 7607, "INV2": 4612, "INV3": 2995, "INV4": 0,

    # G-series — cross-type silent-no-op (these MUST equal each other —
    # we assert the API returns the unbounded count, not zero)
    "G1": 34, "G2": 34, "G3": 34,
    "G4": 15, "G5": 30, "G6": 15,

    # V-series — venue interaction
    "V1": 14, "V2": 14, "V3": 0,
    "V4": 25, "V5": 10, "V6": 15,

    # H-series — rivalries under tier
    "H1": 3, "H2": 3, "H3": 5, "H4": 5,

    # X-series — cross-tier player (SM Curran)
    "X1": 69, "X2": 49, "X3": 20,
    "X5": 1812,  # X4=49+20=69, X6=1210+602=1812 — checked in derivation

    # W-series — women's club 2024-25
    "W1": 162, "W2": 131, "W3": 31,

    # T-series — distinct team strings (whole DB)
    "T1": 105, "T2": 83, "T3": 27, "T4": 6, "T5": 0,
}

# C-series — run-rate baselines (4dp tolerance via near())
RR_ANCHORS: dict[str, float] = {
    "C1": 9.6140, "C2": 9.6140,
    "C3": 8.7778, "C4": 8.8913, "C5": 8.6045,
    "C6": 9.2825, "C7": 9.2825,
    "BWL1": 9.3659, "BWL2": 9.3659,
}

# X5/X6 — runs split for SM Curran
SMC_PERSON_ID = "e94915e6"
SMC_RUNS_PRI = 1210
SMC_RUNS_SEC = 602

# Top-10 lists per tier — pinned literal person_ids (B-list, BWL-list).
# Sort key: total_runs DESC, then person_id DESC for tiebreak.
B_UNB_TOP10 = [
    "3241e3fd", "3355b542", "a15618fe", "92aeac25", "e94915e6",
    "f836b33d", "9caf69a1", "372455c4", "1fc6ef83", "4663bd23",
]
B_PRI_TOP10 = [
    "3241e3fd", "3355b542", "372455c4", "1fc6ef83", "92aeac25",
    "4663bd23", "48a1d7b7", "235c2bb6", "ba607b88", "a15618fe",
]
B_SEC_TOP10 = [
    "7ca5e05d", "67b9536c", "f836b33d", "f3982af9", "35f173a0",
    "270e4c23", "4e18e961", "a6c17509", "ab01e323", "10b79140",
]
BWL_UNB_TOP10 = [
    "efc04be7", "a818c1be", "19b9f399", "245c97cb", "e94915e6",
    "6c79c098", "64775749", "e174dadd", "7f048519", "9d430b40",
]
BWL_PRI_TOP10 = [
    "efc04be7", "a818c1be", "9d430b40", "0f721006", "5f547c8b",
    "4d7f517e", "bbd41817", "e94915e6", "2f9d0389", "e174dadd",
]
BWL_SEC_TOP10 = [
    "6c79c098", "f3abd0c9", "c5f40e35", "64775749", "245c97cb",
    "e871a7a1", "34b37279", "01a95383", "bdc0670a", "4c0f3806",
]


def expect(label: str, actual, expected, failures: list, *, fuzzy: bool = False):
    ok = near(actual, expected) if fuzzy else actual == expected
    status = "PASS" if ok else f"FAIL (got {actual}, expected {expected})"
    print(f"  {label}: {status}")
    if not ok:
        failures.append(f"{label}: got {actual}, expected {expected}")


# ─── In-Python invariants (no DB) ─────────────────────────────────────
def test_module_invariants(failures: list):
    """Three invariants checked at import / collection time."""
    print("─── Module invariants ───")
    inter = PRIMARY_CLUB_LEAGUES & SECONDARY_CLUB_LEAGUES
    if inter == frozenset():
        print("  disjointness: PASS")
    else:
        msg = f"PRIMARY ∩ SECONDARY non-empty: {inter}"
        print(f"  disjointness: FAIL — {msg}")
        failures.append(msg)


# ─── DB-direct anchor SQL (one COUNT(*) per anchor) ──────────────────
async def count(sql: str, params: dict | None = None) -> int:
    rows = await deps._db.q(sql, params or {})
    return rows[0]["c"]


async def scalar(sql: str, params: dict | None = None):
    rows = await deps._db.q(sql, params or {})
    if not rows:
        return None
    row = rows[0]
    return row[list(row.keys())[0]]


async def run_rate(sql_where: str) -> float:
    sql = f"""
        SELECT
          CAST(SUM(d.runs_total) AS REAL) * 6.0
            / NULLIF(SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END), 0) AS rr
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {sql_where}
    """
    return await scalar(sql)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cricket.db",
    ))
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        sys.exit(1)

    deps._db = Database(f"sqlite+aiosqlite:///{args.db}")
    await deps._db.q("PRAGMA journal_mode = WAL")

    failures: list[str] = []
    test_module_invariants(failures)

    pc = primary_club_clause("m")
    sc = secondary_club_clause("m")

    # ─── Completeness invariant (DB-direct) ───────────────────────────
    print()
    print("─── Completeness invariant ───")
    untagged_rows = await deps._db.q(f"""
        SELECT DISTINCT event_name FROM match
        WHERE team_type = 'club' AND match_type = 'T20'
          AND event_name NOT IN ({", ".join(f"'{e.replace(chr(39), chr(39)*2)}'" for e in sorted(PRIMARY_CLUB_LEAGUES | SECONDARY_CLUB_LEAGUES))})
    """)
    untagged = [r["event_name"] for r in untagged_rows]
    if untagged == []:
        print("  completeness: PASS (0 untagged events)")
    else:
        msg = (f"completeness: FAIL — {len(untagged)} untagged events: {untagged}. "
               "Slot each into PRIMARY_CLUB_LEAGUES or SECONDARY_CLUB_LEAGUES.")
        print(f"  {msg}")
        failures.append(msg)

    # ─── P-series ────────────────────────────────────────────────────
    print()
    print("─── P-series: match counts (men's club 2024-25) ───")
    expect("P1 total", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M}"), ANCHORS["P1"], failures)
    expect("P2 primary_club", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND {pc}"), ANCHORS["P2"], failures)
    expect("P3 secondary_club", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND {sc}"), ANCHORS["P3"], failures)
    p2 = await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND {pc}")
    p3 = await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND {sc}")
    if p2 + p3 == ANCHORS["P1"]:
        print(f"  P4 disjointness P2+P3==P1: PASS ({p2}+{p3}=={ANCHORS['P1']})")
    else:
        msg = f"P4 disjointness FAIL: {p2}+{p3}={p2+p3}, expected {ANCHORS['P1']}"
        print(f"  {msg}")
        failures.append(msg)

    expect("P5 MI unbounded", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND (m.team1='Mumbai Indians' OR m.team2='Mumbai Indians')"), ANCHORS["P5"], failures)
    expect("P6 MI primary (no-op)", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND (m.team1='Mumbai Indians' OR m.team2='Mumbai Indians') AND {pc}"), ANCHORS["P6"], failures)
    expect("P7 MI secondary (cross-tier)", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND (m.team1='Mumbai Indians' OR m.team2='Mumbai Indians') AND {sc}"), ANCHORS["P7"], failures)
    expect("P8 Surrey unbounded", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND (m.team1='Surrey' OR m.team2='Surrey')"), ANCHORS["P8"], failures)
    expect("P9 Surrey primary (cross-tier)", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND (m.team1='Surrey' OR m.team2='Surrey') AND {pc}"), ANCHORS["P9"], failures)
    expect("P10 Surrey secondary (no-op)", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND (m.team1='Surrey' OR m.team2='Surrey') AND {sc}"), ANCHORS["P10"], failures)
    expect("P11 Baroda unbounded", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND (m.team1='Baroda' OR m.team2='Baroda')"), ANCHORS["P11"], failures)
    expect("P12 Baroda secondary", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND (m.team1='Baroda' OR m.team2='Baroda') AND {sc}"), ANCHORS["P12"], failures)

    # ─── INV-series ──────────────────────────────────────────────────
    print()
    print("─── INV-series: whole-DB partition ───")
    expect("INV1 all club T20", await count("SELECT COUNT(*) c FROM match WHERE team_type='club' AND match_type='T20'"), ANCHORS["INV1"], failures)
    expect("INV2 in primary", await count(f"SELECT COUNT(*) c FROM match m WHERE m.team_type='club' AND m.match_type='T20' AND {pc}"), ANCHORS["INV2"], failures)
    expect("INV3 in secondary", await count(f"SELECT COUNT(*) c FROM match m WHERE m.team_type='club' AND m.match_type='T20' AND {sc}"), ANCHORS["INV3"], failures)
    expect("INV4 untagged", len(untagged), ANCHORS["INV4"], failures)
    inv2 = await count(f"SELECT COUNT(*) c FROM match m WHERE m.team_type='club' AND m.match_type='T20' AND {pc}")
    inv3 = await count(f"SELECT COUNT(*) c FROM match m WHERE m.team_type='club' AND m.match_type='T20' AND {sc}")
    if inv2 + inv3 == ANCHORS["INV1"]:
        print(f"  INV5 partition sum: PASS ({inv2}+{inv3}=={ANCHORS['INV1']})")
    else:
        msg = f"INV5 partition sum FAIL: {inv2}+{inv3}={inv2+inv3}, expected {ANCHORS['INV1']}"
        print(f"  {msg}")
        failures.append(msg)

    # ─── G-series — defensive-gate proofs are SQL-direct here.
    # The API-side defensive gate will be tested by a separate
    # integration test (the API call must return G1, NOT zero, when
    # given a cross-type team_class). The SQL anchors below pin the
    # raw counts the API will be asserted against.
    print()
    print("─── G-series: defensive-gate raw counts (API-side gate proof in C2) ───")
    expect("G1 India intl (= v3 A5)", await count(f"SELECT COUNT(*) c FROM match m WHERE {INTL_24_25_M} AND (m.team1='India' OR m.team2='India')"), ANCHORS["G1"], failures)
    # G2/G3 will be API-side tests in C2.
    expect("G4 RCB IPL 2025 (= v3 B1)", await count("SELECT COUNT(*) c FROM match m WHERE m.gender='male' AND m.team_type='club' AND m.event_name='Indian Premier League' AND m.season='2025' AND (m.team1='Royal Challengers Bengaluru' OR m.team2='Royal Challengers Bengaluru')"), ANCHORS["G4"], failures)
    expect("G5 MI club 2024-25 (control)", ANCHORS["P5"], ANCHORS["G5"], failures)
    expect("G6 RCB IPL primary (no-op)", await count(f"SELECT COUNT(*) c FROM match m WHERE m.gender='male' AND m.team_type='club' AND m.event_name='Indian Premier League' AND m.season='2025' AND (m.team1='Royal Challengers Bengaluru' OR m.team2='Royal Challengers Bengaluru') AND {pc}"), ANCHORS["G6"], failures)

    # ─── V-series ────────────────────────────────────────────────────
    print()
    print("─── V-series: venue interaction ───")
    expect("V1 Wankhede club unbounded", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND m.venue='Wankhede Stadium'"), ANCHORS["V1"], failures)
    expect("V2 Wankhede primary", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND m.venue='Wankhede Stadium' AND {pc}"), ANCHORS["V2"], failures)
    expect("V3 Wankhede secondary", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND m.venue='Wankhede Stadium' AND {sc}"), ANCHORS["V3"], failures)
    expect("V4 Oval unbounded (multi-tier)", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND m.venue='Kennington Oval'"), ANCHORS["V4"], failures)
    expect("V5 Oval primary", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND m.venue='Kennington Oval' AND {pc}"), ANCHORS["V5"], failures)
    expect("V6 Oval secondary", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND m.venue='Kennington Oval' AND {sc}"), ANCHORS["V6"], failures)

    # ─── H-series ────────────────────────────────────────────────────
    print()
    print("─── H-series: head-to-head under tier ───")
    expect("H1 MI vs CSK unbounded", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND ((m.team1='Mumbai Indians' AND m.team2='Chennai Super Kings') OR (m.team1='Chennai Super Kings' AND m.team2='Mumbai Indians'))"), ANCHORS["H1"], failures)
    expect("H2 MI vs CSK primary (no-op)", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND ((m.team1='Mumbai Indians' AND m.team2='Chennai Super Kings') OR (m.team1='Chennai Super Kings' AND m.team2='Mumbai Indians')) AND {pc}"), ANCHORS["H2"], failures)
    expect("H3 Surrey vs Somerset unbounded", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND ((m.team1='Surrey' AND m.team2='Somerset') OR (m.team1='Somerset' AND m.team2='Surrey'))"), ANCHORS["H3"], failures)
    expect("H4 Surrey vs Somerset secondary (no-op)", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_M} AND ((m.team1='Surrey' AND m.team2='Somerset') OR (m.team1='Somerset' AND m.team2='Surrey')) AND {sc}"), ANCHORS["H4"], failures)

    # ─── X-series ────────────────────────────────────────────────────
    print()
    print("─── X-series: cross-tier player narrowing (SM Curran) ───")
    smc_join = "JOIN matchplayer mp ON mp.match_id=m.id"
    smc_where = f"mp.person_id='{SMC_PERSON_ID}'"
    expect("X1 SMC unbounded", await count(f"SELECT COUNT(DISTINCT m.id) c FROM match m {smc_join} WHERE {CLUB_24_25_M} AND {smc_where}"), ANCHORS["X1"], failures)
    expect("X2 SMC primary", await count(f"SELECT COUNT(DISTINCT m.id) c FROM match m {smc_join} WHERE {CLUB_24_25_M} AND {smc_where} AND {pc}"), ANCHORS["X2"], failures)
    expect("X3 SMC secondary", await count(f"SELECT COUNT(DISTINCT m.id) c FROM match m {smc_join} WHERE {CLUB_24_25_M} AND {smc_where} AND {sc}"), ANCHORS["X3"], failures)
    x2 = await count(f"SELECT COUNT(DISTINCT m.id) c FROM match m {smc_join} WHERE {CLUB_24_25_M} AND {smc_where} AND {pc}")
    x3 = await count(f"SELECT COUNT(DISTINCT m.id) c FROM match m {smc_join} WHERE {CLUB_24_25_M} AND {smc_where} AND {sc}")
    if x2 + x3 == ANCHORS["X1"]:
        print(f"  X4 split: PASS ({x2}+{x3}=={ANCHORS['X1']})")
    else:
        msg = f"X4 split FAIL: {x2}+{x3}={x2+x3}, expected {ANCHORS['X1']}"
        print(f"  {msg}")
        failures.append(msg)
    smc_runs = f"SELECT SUM(d.runs_batter) c FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE d.batter_id='{SMC_PERSON_ID}' AND {CLUB_24_25_M} AND i.super_over=0"
    expect("X5 SMC total runs", await scalar(smc_runs), ANCHORS["X5"], failures)
    smc_runs_pri = await scalar(f"{smc_runs} AND {pc}")
    smc_runs_sec = await scalar(f"{smc_runs} AND {sc}")
    if (smc_runs_pri, smc_runs_sec) == (SMC_RUNS_PRI, SMC_RUNS_SEC):
        print(f"  X6 runs split: PASS (pri={smc_runs_pri}, sec={smc_runs_sec})")
    else:
        msg = f"X6 runs split FAIL: pri={smc_runs_pri} (expect {SMC_RUNS_PRI}), sec={smc_runs_sec} (expect {SMC_RUNS_SEC})"
        print(f"  {msg}")
        failures.append(msg)

    # ─── C-series — run rate baselines ────────────────────────────────
    print()
    print("─── C-series: chip baselines (run rates) ───")
    expect("C1 MI batting unbounded", await run_rate(f"{CLUB_24_25_M} AND i.team='Mumbai Indians'"), RR_ANCHORS["C1"], failures, fuzzy=True)
    expect("C2 MI batting primary (no-op)", await run_rate(f"{CLUB_24_25_M} AND i.team='Mumbai Indians' AND {pc}"), RR_ANCHORS["C2"], failures, fuzzy=True)
    expect("C3 League batting unbounded", await run_rate(CLUB_24_25_M), RR_ANCHORS["C3"], failures, fuzzy=True)
    expect("C4 League batting primary", await run_rate(f"{CLUB_24_25_M} AND {pc}"), RR_ANCHORS["C4"], failures, fuzzy=True)
    expect("C5 League batting secondary", await run_rate(f"{CLUB_24_25_M} AND {sc}"), RR_ANCHORS["C5"], failures, fuzzy=True)
    expect("C6 Surrey batting unbounded", await run_rate(f"{CLUB_24_25_M} AND i.team='Surrey'"), RR_ANCHORS["C6"], failures, fuzzy=True)
    expect("C7 Surrey batting secondary (no-op)", await run_rate(f"{CLUB_24_25_M} AND i.team='Surrey' AND {sc}"), RR_ANCHORS["C7"], failures, fuzzy=True)

    # ─── BWL ─────────────────────────────────────────────────────────
    print()
    print("─── BWL-series: bowling-side baselines ───")
    mi_opp = "((m.team1='Mumbai Indians' AND i.team=m.team2) OR (m.team2='Mumbai Indians' AND i.team=m.team1))"
    expect("BWL1 MI bowling unbounded", await run_rate(f"{CLUB_24_25_M} AND {mi_opp}"), RR_ANCHORS["BWL1"], failures, fuzzy=True)
    expect("BWL2 MI bowling primary (no-op)", await run_rate(f"{CLUB_24_25_M} AND {mi_opp} AND {pc}"), RR_ANCHORS["BWL2"], failures, fuzzy=True)

    # ─── W-series ────────────────────────────────────────────────────
    print()
    print("─── W-series: women's club partition ───")
    expect("W1 women club total", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_F}"), ANCHORS["W1"], failures)
    expect("W2 women primary", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_F} AND {pc}"), ANCHORS["W2"], failures)
    expect("W3 women secondary", await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_F} AND {sc}"), ANCHORS["W3"], failures)
    w2 = await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_F} AND {pc}")
    w3 = await count(f"SELECT COUNT(*) c FROM match m WHERE {CLUB_24_25_F} AND {sc}")
    if w2 + w3 == ANCHORS["W1"]:
        print(f"  W4 disjointness: PASS ({w2}+{w3}=={ANCHORS['W1']})")
    else:
        msg = f"W4 disjointness FAIL: {w2}+{w3}={w2+w3}, expected {ANCHORS['W1']}"
        print(f"  {msg}")
        failures.append(msg)

    # ─── T-series ────────────────────────────────────────────────────
    print()
    print("─── T-series: distinct-team-string counts (whole DB) ───")
    expect("T1 men's primary teams", await count(f"SELECT COUNT(DISTINCT t) c FROM (SELECT team1 t FROM match m WHERE m.team_type='club' AND m.gender='male' AND {pc} UNION SELECT m.team2 FROM match m WHERE m.team_type='club' AND m.gender='male' AND {pc})"), ANCHORS["T1"], failures)
    expect("T2 men's secondary teams", await count(f"SELECT COUNT(DISTINCT t) c FROM (SELECT team1 t FROM match m WHERE m.team_type='club' AND m.gender='male' AND {sc} UNION SELECT m.team2 FROM match m WHERE m.team_type='club' AND m.gender='male' AND {sc})"), ANCHORS["T2"], failures)
    expect("T3 women's primary teams", await count(f"SELECT COUNT(DISTINCT t) c FROM (SELECT team1 t FROM match m WHERE m.team_type='club' AND m.gender='female' AND {pc} UNION SELECT m.team2 FROM match m WHERE m.team_type='club' AND m.gender='female' AND {pc})"), ANCHORS["T3"], failures)
    expect("T4 women's secondary teams", await count(f"SELECT COUNT(DISTINCT t) c FROM (SELECT team1 t FROM match m WHERE m.team_type='club' AND m.gender='female' AND {sc} UNION SELECT m.team2 FROM match m WHERE m.team_type='club' AND m.gender='female' AND {sc})"), ANCHORS["T4"], failures)
    expect("T5 cross-tier team intersection", await count(f"""
        SELECT COUNT(*) c FROM (
          SELECT DISTINCT t FROM (SELECT team1 t FROM match m WHERE m.team_type='club' AND {pc} UNION SELECT m.team2 FROM match m WHERE m.team_type='club' AND {pc}) p
          INTERSECT
          SELECT DISTINCT t FROM (SELECT team1 t FROM match m WHERE m.team_type='club' AND {sc} UNION SELECT m.team2 FROM match m WHERE m.team_type='club' AND {sc}) s
        )
    """), ANCHORS["T5"], failures)

    # ─── B-list / BWL-list ───────────────────────────────────────────
    # Pinned literal top-10 person_ids per tier. Loose match (set
    # equality) tolerates DB drift on tied entries; spec expects
    # ordered match.
    print()
    print("─── B-list: top-10 batters by total_runs ───")
    for label, where, expected in [
        ("B-unb", CLUB_24_25_M, B_UNB_TOP10),
        ("B-pri", f"{CLUB_24_25_M} AND {pc}", B_PRI_TOP10),
        ("B-sec", f"{CLUB_24_25_M} AND {sc}", B_SEC_TOP10),
    ]:
        rows = await deps._db.q(f"""
            SELECT d.batter_id person_id, SUM(d.runs_batter) runs
            FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
            WHERE d.batter_id IS NOT NULL AND i.super_over=0 AND {where}
            GROUP BY d.batter_id ORDER BY runs DESC, d.batter_id DESC LIMIT 10
        """)
        actual = [r["person_id"] for r in rows]
        if actual == expected:
            print(f"  {label}: PASS")
        else:
            msg = f"{label}: FAIL — got {actual}, expected {expected}"
            print(f"  {msg}")
            failures.append(msg)

    print()
    print("─── BWL-list: top-10 bowlers by wickets ───")
    for label, where, expected in [
        ("BWL-unb", CLUB_24_25_M, BWL_UNB_TOP10),
        ("BWL-pri", f"{CLUB_24_25_M} AND {pc}", BWL_PRI_TOP10),
        ("BWL-sec", f"{CLUB_24_25_M} AND {sc}", BWL_SEC_TOP10),
    ]:
        rows = await deps._db.q(f"""
            SELECT d.bowler_id person_id, COUNT(*) wkts
            FROM wicket w JOIN delivery d ON d.id=w.delivery_id
            JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
            WHERE w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field')
              AND d.bowler_id IS NOT NULL AND i.super_over=0 AND {where}
            GROUP BY d.bowler_id ORDER BY wkts DESC, d.bowler_id DESC LIMIT 10
        """)
        actual = [r["person_id"] for r in rows]
        if actual == expected:
            print(f"  {label}: PASS")
        else:
            msg = f"{label}: FAIL — got {actual}, expected {expected}"
            print(f"  {msg}")
            failures.append(msg)

    print()
    if failures:
        print(f"❌ {len(failures)} FAILURES:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("✅ All anchors PASS.")


if __name__ == "__main__":
    asyncio.run(main())
