"""Sanity: per-bucket cohort fields on /fielders/{id}/summary
dismissal_position_distribution.

Spec: internal_docs/spec-mix-and-performance-charts.md §3.3 — the
mix-histogram + performance-vs-cohort charts on the By Dismissed
Position tab read two cohort fields attached to each entry:

  - `cohort_dismissals_share`   — bucket's share of cohort-total
    dismissals (across the keeper-binary partition matching the
    player's is_keeper flag); sums to 1.0 across the 10 buckets.
  - `cohort_catches_per_match`  — cohort catches at this bucket /
    cohort matches across the partition. Sum across buckets ≈
    overall cohort catches-per-match.

Invariants:
  1. Length-10 array, one entry per bucket (1=Opener merged, 2..10 = #3..#11).
  2. `cohort_dismissals_share` sums to 1.0 ± 1e-6.
  3. Keeper-partition cohort catches/match > outfielder-partition
     cohort catches/match at every bucket (keepers catch more per
     match than outfielders by design — same partition Dhoni vs
     Kohli on the same scope locks the partition logic).
  4. Sum of cohort_catches_per_match across the 10 buckets ≈
     the overall /summary.catches_per_match.scope_avg envelope
     value (algebraic identity — the sum IS the rate).

Usage:
  uv run python tests/sanity/test_fielder_summary_dismissal_position.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


DEFAULT_HOST = "http://localhost:8000"


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{host}{path}?{qs}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    args = parser.parse_args()

    print(f"Sanity: /fielders/{{id}}/summary dismissal_position cohort fields ({args.host})")
    all_passed = True

    # Two subjects on the same scope so the partition flips:
    # Kohli (outfielder, is_keeper=0) vs Dhoni (keeper, is_keeper=1).
    SCOPE = dict(gender="male", team_type="club", tournament="Indian Premier League")
    kohli = get(args.host, "/api/v1/fielders/ba607b88/summary", **SCOPE)
    dhoni = get(args.host, "/api/v1/fielders/4a8a2e3b/summary", **SCOPE)

    print("\n  1. Shape:")
    ok = (kohli["is_keeper"] == 0 and dhoni["is_keeper"] == 1)
    _, line = check("Kohli is_keeper=0; Dhoni is_keeper=1", ok,
                    f"Kohli={kohli['is_keeper']}, Dhoni={dhoni['is_keeper']}")
    print(line); all_passed &= ok

    kpd = kohli["dismissal_position_distribution"]
    dpd = dhoni["dismissal_position_distribution"]
    ok = len(kpd) == 10 and len(dpd) == 10
    _, line = check("both pds length 10", ok, f"Kohli={len(kpd)}, Dhoni={len(dpd)}")
    print(line); all_passed &= ok

    print("\n  2. cohort_dismissals_share sums to 1.0 on both partitions:")
    for label, pd in (("outfielder (Kohli)", kpd), ("keeper (Dhoni)", dpd)):
        total = sum((e.get("cohort_dismissals_share") or 0) for e in pd)
        ok = abs(total - 1.0) < 1e-6
        _, line = check(f"{label} sum ≈ 1.0", ok, f"sum = {total:.9f}")
        print(line); all_passed &= ok

    print("\n  3. Keeper cohort catches/match > outfielder cohort at EVERY bucket:")
    every_bucket_higher = True
    detail_first_bad = ""
    for b in range(10):
        k_val = kpd[b].get("cohort_catches_per_match")
        d_val = dpd[b].get("cohort_catches_per_match")
        if k_val is not None and d_val is not None and not (d_val > k_val):
            every_bucket_higher = False
            detail_first_bad = f"bucket {b+1}: outfielder={k_val}, keeper={d_val}"
            break
    _, line = check(
        "keeper cohort_catches_per_match > outfielder at every bucket",
        every_bucket_higher, detail_first_bad,
    )
    print(line); all_passed &= ok and every_bucket_higher

    print("\n  4. Sum of cohort_catches_per_match ≈ /summary scope_avg:")
    for label, summary, pd in (("Kohli", kohli, kpd), ("Dhoni", dhoni, dpd)):
        bucket_sum = sum((e.get("cohort_catches_per_match") or 0) for e in pd)
        envelope_avg = summary["catches_per_match"]["scope_avg"]
        ok = abs(bucket_sum - envelope_avg) < 0.01
        _, line = check(
            f"{label}: sum(per-bucket c/m) ≈ envelope scope_avg",
            ok, f"sum={bucket_sum:.4f}, envelope={envelope_avg}",
        )
        print(line); all_passed &= ok

    print()
    print("=" * 60)
    print("ALL PASSED" if all_passed else "FAILURES")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
