# Series-type FilterBar promotion — anchor numbers

Pre-flight per `spec-filterbar-series-type.md` §7 + §11. Closed
historical window so the post-promotion sanity test
(`tests/sanity/test_series_type_baseline_numbers.py`) doesn't drift
over time.

Derived 2026-04-28 by direct SQL against `cricket.db`. The
`series_type_clause` helper from `api/tournament_canonical.py` is
the only api/ import — that's the SQL builder, not the FilterBar /
AuxParams / endpoint code path under test, so it's safe to import
without tautology risk.

## Window

- gender=male, team_type=international, season ∈ [2024, 2025]
  unless noted otherwise.
- ICC event count in window: 12 canonical names, 12 cricsheet
  variants (T20 WC variants: `ICC Men's T20 World Cup`, …).

## Numbers

| Anchor | Description | Matches |
|---|---|---|
| S1  | Total men_intl 24-25 (no series_type) | **870** |
| S2  | + `series_type=bilateral_only` | **802** |
| S3  | + `series_type=tournament_only` / `icc` | **68** |
| S4  | + tournament=T20 World Cup + `bilateral_only` | **0** (T20 WC is ICC) |
| S5  | + tournament=T20 World Cup + `icc` | **44** |
| S6  | + filter_team=India + `bilateral_only` | **27** |
| S7  | + filter_team=India + filter_opponent=Australia + `bilateral_only` | **0** (Ind vs Aus only met in T20 WC group stage 2024) |
| S8  | women_intl 24-25 + `bilateral_only` | **535** |
| S9  | club 24-25 + `bilateral_only` | **0** (bilateral clause requires team_type=international) |
| S10 | + scope_to_team=Australia + `bilateral_only` (= Aus's bilateral matches) | **16** |

## Reproducer

```bash
uv run python -c "
import sqlite3
from api.tournament_canonical import series_type_clause

con = sqlite3.connect('cricket.db')
def count(extra=''):
    return con.execute(f'''
        SELECT COUNT(*) FROM match m
        WHERE m.gender='male' AND m.team_type='international'
          AND m.season>='2024' AND m.season<='2025' {extra}
    ''').fetchone()[0]

bilat = ' AND ' + series_type_clause('bilateral_only')
icc   = ' AND ' + series_type_clause('tournament_only')
print('S1 unbounded:', count())
print('S2 bilat:', count(bilat))
print('S3 icc:', count(icc))
"
```

## Sanity invariants

- S1 = S2 + S3 (bilateral + ICC partition the men_intl pool exactly,
  870 = 802 + 68).
- S4 = 0 strictly (any matches in an ICC event by definition aren't
  bilateral).
- S9 = 0 strictly (bilateral clause has `team_type='international'`
  hard-coded).

## Followups

The sanity test (`test_series_type_baseline_numbers.py`, written
in commit 5) hits each anchor via two paths:

1. Raw SQL (the reproducer above) — independent ground truth.
2. The relevant API endpoint with `?series_type=...` set — proves
   the FilterBar widget's URL plumbing reaches the backend clause
   via `FilterBarParams.series_type`.

If the two paths agree on every anchor, the promotion is inert
where it should be (S1, S5 are the unbounded controls) AND active
where it should be (S2, S3, S6, S7, S8, S10).
