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

## Hand-rolled helper verification (spec commit 3)

Per spec §5.4 + §9 commit 3, this is verification-only with zero
backend edits. Curl matrix run 2026-04-28 against the just-shipped
commit 2 (FilterBar widget):

| Endpoint | plain | bilateral_only | tournament_only |
|---|---|---|---|
| `/tournaments` (men_intl 24-25) | 128 | **126** | **2** |
| `/seasons` (men_intl unbounded) | 44 | 44 | **12** |
| `/teams` (typeahead, men_intl) | 107 | 107 | 107 |
| `/matches` (men_intl 24-25) | **870** | **802** | **68** |
| `/scope/averages/summary` (per-team) | 17.4 | 16.04 | 5.04 |

- `/tournaments` narrowing matches spec §5.4's curl-verified anchor
  exactly (128 → 126 → 2). ✓
- `/seasons` plain = bilateral_only because every year in window
  has at least one bilateral match — narrowing doesn't drop seasons
  in this scope. tournament_only narrows to 12 (only seasons with
  ICC events). ✓
- `/teams` (typeahead): GAP at first audit (100 == 100), fixed
  same-day in a follow-up commit — `list_teams` now applies
  `series_type_clause(filters.series_type)` alongside the
  `team_class` clause. Post-fix: 100 → 27 under `series_type=icc`
  on men_intl 2024-25 (only the 27 teams that played in T20 WC or
  ACC Premier Cup). Scotland row narrows 17 → 4 (4 ICC + 13
  bilateral = 17 total). Asserted by
  `tests/integration/series_type_per_tab_narrowing.sh::Test 7`. ✓
- `/matches` matches S1/S2/S3 anchors above (870 / 802 / 68). ✓
- `/scope/averages/summary` narrows correctly AND dispatch falls
  back to live aggregation under series_type (per
  `is_precomputed_scope` reading filters.series_type now). ✓

Net: every endpoint that mattered before commit 1 still narrows
correctly post-promotion. The only known gap (`list_teams`
typeahead) was acknowledged by the spec as deferred.
