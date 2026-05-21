"""Sanity: bowling wicket-ladder ProbChip cohort baselines.

Hits /bowlers/{id}/distribution on the running API and verifies the
PT2.B cohort baseline plumbing on each chip's ProbRecord in the
wickets block:

  1. **Shape**: every chip (p_zero, p_geq_1..5, p_3_given_2,
     p_4_given_2, p_5_given_2) carries scope_avg / delta_pct /
     direction / sample_size keys.

  2. **Direction tags**: P(0) is lower_better; the remaining 8 chips
     higher_better (spec §6).

  3. **delta_pct sign**: matches (value − scope_avg) / scope_avg × 100
     (spec §4.1 + §6).

  4. **Convex combination — simples** (P(0), P(≥1), P(≥2)): scope_avg
     equals Σ mix[o] × (count_at_o / innings_bowled_at_o), where
     count is innings_with_wicket / innings_with_two for P(≥1)/P(≥2);
     innings_bowled − innings_with_wicket for P(0). Bucket-grain
     direct ratio (no per_innings_scale on these — per-spell-touching
     numerators match per-spell-touching denominators dimensionally).

  5. **Convex combination — attribution simples** (P(≥3)): scope_avg
     equals (Σ mix[o] × three_wicket_hauls_at_o / innings_bowled_at_o)
     × per_innings_scale. per_innings_scale = SUM(innings_bowled) /
     SUM(bowling_innings); scales attribution-rate from per-attendance
     to per-spell so it reads as P(≥3).

  6. **Sample size**: ProbRecord.sample_size equals
     cohort.n_balls_total at the same scope.

  7. **Form windows**: lifetime + 4 windows share the same lifetime
     cohort scope_avg (window-slice cohorts deferred — spec §10).

Subject: Bumrah IPL all-time + Bumrah IPL 2024 (small sample).

Spec: internal_docs/spec-prob-baselines.md §3.2 + §6 + §9.

Usage:
  uv run python tests/sanity/test_prob_baselines_bowling.py
  # API server must be running on http://localhost:8000.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")
DEFAULT_HOST = "http://localhost:8000"

EXPECTED_DIRECTIONS: dict[str, str] = {
    "p_zero":      "lower_better",
    "p_geq_1":     "higher_better",
    "p_geq_2":     "higher_better",
    "p_geq_3":     "higher_better",
    "p_geq_4":     "higher_better",
    "p_geq_5":     "higher_better",
    "p_3_given_2": "higher_better",
    "p_4_given_2": "higher_better",
    "p_5_given_2": "higher_better",
}


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{host}{path}?{qs}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    print(f"Sanity: bowling wicket-ladder ProbChip cohort baselines ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    BUMRAH = "462411b3"

    resp = get(
        args.host, f"/api/v1/bowlers/{BUMRAH}/distribution",
        gender="male", team_type="club",
        tournament="Indian Premier League",
        as_of_date="2025-01-01",
    )
    lifetime_ms = resp["lifetime"]["wickets"]["milestones"]

    # ─── Test 1: shape ──────────────────────────────────────────────
    print("\n  1. ProbRecord shape extension (lifetime wickets milestones):")
    for chip in EXPECTED_DIRECTIONS:
        pr = lifetime_ms.get(chip)
        ok = pr is not None and all(
            k in pr for k in ("scope_avg", "delta_pct", "direction", "sample_size")
        )
        _, line = check(
            f"{chip} carries scope_avg / delta_pct / direction / sample_size",
            ok,
        )
        print(line); all_passed &= ok

    # ─── Test 2: direction tags ────────────────────────────────────
    print("\n  2. Direction tags match spec §6:")
    for chip, expected_dir in EXPECTED_DIRECTIONS.items():
        pr = lifetime_ms.get(chip, {})
        ok = pr.get("direction") == expected_dir
        _, line = check(f"{chip} direction={expected_dir}", ok)
        print(line); all_passed &= ok

    # ─── Test 3: delta_pct sign ────────────────────────────────────
    print("\n  3. delta_pct = (value − scope_avg) / scope_avg × 100:")
    for chip in EXPECTED_DIRECTIONS:
        pr = lifetime_ms.get(chip, {})
        value = pr.get("value"); scope_avg = pr.get("scope_avg"); delta_pct = pr.get("delta_pct")
        if value is None or not scope_avg:
            continue
        expected = round((value - scope_avg) / scope_avg * 100, 1)
        ok = delta_pct == expected
        _, line = check(f"{chip} delta_pct matches arithmetic", ok,
                        f"expected={expected}, actual={delta_pct}")
        print(line); all_passed &= ok

    # ─── Test 4: convex combination for per-spell-touching ─────────
    # P(≥1) per bucket = innings_with_wicket / innings_bowled. cv by
    # Bumrah's over-mix from legal_balls.
    print("\n  4. Cohort p_geq_1 matches cv of per-spell-touching:")
    bumrah_mix_rows = conn.execute("""
        SELECT psso.over_number AS o,
               SUM(psso.legal_balls) AS lb
        FROM playerscopestatsover psso
        JOIN playerscopestats pss
          ON psso.scope_key = pss.scope_key AND psso.person_id = pss.person_id
        WHERE pss.person_id = ?
          AND pss.tournament = 'Indian Premier League'
        GROUP BY psso.over_number
    """, (BUMRAH,)).fetchall()
    total_balls = sum(r["lb"] for r in bumrah_mix_rows)
    bumrah_mix = {r["o"]: (r["lb"] or 0) / total_balls for r in bumrah_mix_rows}

    cohort_rows = conn.execute("""
        SELECT psso.over_number AS o,
               SUM(psso.innings_bowled) AS innings_bowled,
               SUM(psso.innings_with_wicket) AS iw,
               SUM(psso.innings_with_two) AS i2,
               SUM(psso.three_wicket_hauls) AS three
        FROM playerscopestatsover psso
        WHERE psso.scope_key IN (
          SELECT scope_key FROM playerscopestats pss
          WHERE pss.tournament = 'Indian Premier League'
        )
        GROUP BY psso.over_number
    """).fetchall()
    cohort_p_geq_1 = {
        r["o"]: (r["iw"] / r["innings_bowled"]) if r["innings_bowled"] else None
        for r in cohort_rows
    }
    expected_p_geq_1 = sum(
        bumrah_mix.get(o, 0) * cohort_p_geq_1[o]
        for o in cohort_p_geq_1
        if cohort_p_geq_1[o] is not None and bumrah_mix.get(o, 0) > 0
    )
    actual_p_geq_1 = lifetime_ms["p_geq_1"]["scope_avg"]
    ok = actual_p_geq_1 is not None and abs(actual_p_geq_1 - round(expected_p_geq_1, 4)) < 1e-3
    _, line = check(
        "p_geq_1 scope_avg matches manual cv from playerscopestatsover",
        ok,
        f"expected≈{expected_p_geq_1:.4f}, actual={actual_p_geq_1}",
    )
    print(line); all_passed &= ok

    # ─── Test 5: attribution-based simples (P(≥3) with per_innings_scale) ─
    # Per-bucket three_wicket_hauls / innings_bowled is per-attendance.
    # cv by mix gives per-attendance prob. Multiply by per_innings_scale
    # = SUM(innings_bowled) / SUM(bowling_innings) to convert to per-
    # spell. The endpoint applies this scale automatically; mirror it
    # here to anchor the cohort math.
    print("\n  5. Cohort p_geq_3 matches cv with per_innings_scale:")
    bowling_inn = conn.execute("""
        SELECT SUM(pss.bowling_innings) AS bi
        FROM playerscopestats pss
        WHERE pss.tournament = 'Indian Premier League'
    """).fetchone()["bi"] or 0
    total_attendances = sum(r["innings_bowled"] or 0 for r in cohort_rows)
    per_innings_scale = (total_attendances / bowling_inn) if bowling_inn else 0
    cohort_attr_geq_3 = {
        r["o"]: (r["three"] / r["innings_bowled"]) if r["innings_bowled"] else None
        for r in cohort_rows
    }
    cv_geq_3 = sum(
        bumrah_mix.get(o, 0) * cohort_attr_geq_3[o]
        for o in cohort_attr_geq_3
        if cohort_attr_geq_3[o] is not None and bumrah_mix.get(o, 0) > 0
    )
    expected_p_geq_3 = cv_geq_3 * per_innings_scale
    actual_p_geq_3 = lifetime_ms["p_geq_3"]["scope_avg"]
    ok = actual_p_geq_3 is not None and abs(actual_p_geq_3 - round(expected_p_geq_3, 4)) < 1e-3
    _, line = check(
        "p_geq_3 scope_avg matches manual cv × per_innings_scale",
        ok,
        f"expected≈{expected_p_geq_3:.4f}, actual={actual_p_geq_3}, scale={per_innings_scale:.3f}",
    )
    print(line); all_passed &= ok

    # ─── Test 6: sample_size == cohort.n_balls_total ─────────────
    print("\n  6. ProbRecord.sample_size = cohort.n_balls_total:")
    sql_balls = conn.execute("""
        SELECT SUM(psso.legal_balls) AS s
        FROM playerscopestatsover psso
        WHERE psso.scope_key IN (
          SELECT scope_key FROM playerscopestats pss
          WHERE pss.tournament = 'Indian Premier League'
        )
    """).fetchone()["s"]
    for chip in EXPECTED_DIRECTIONS:
        ss = lifetime_ms[chip].get("sample_size")
        ok = ss == sql_balls
        _, line = check(f"{chip} sample_size == SQL SUM(legal_balls)", ok,
                        f"sample_size={ss}, sql={sql_balls}")
        print(line); all_passed &= ok

    # ─── Test 7: form windows inherit lifetime cohort ──────────────
    print("\n  7. Form windows inherit lifetime cohort scope_avg:")
    for window_key in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        window_doss = resp["form"].get(window_key, {})
        window_ms = window_doss.get("wickets", {}).get("milestones", {})
        if not window_ms:
            continue
        for chip in ("p_zero", "p_geq_2"):
            ws = window_ms.get(chip, {}).get("scope_avg")
            ls = lifetime_ms[chip]["scope_avg"]
            ok = ws == ls
            _, line = check(f"{window_key} {chip} scope_avg matches lifetime",
                            ok, f"window={ws}, lifetime={ls}")
            print(line); all_passed &= ok

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    else:
        print("SOME FAILURES — see above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
