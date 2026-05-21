from deebase import Text, ForeignKey
from typing import Optional
from datetime import date


class Person:
    id: str  # cricsheet identifier (hex string)
    name: str
    unique_name: str
    key_cricinfo: Optional[str] = None
    key_cricbuzz: Optional[str] = None
    key_bcci: Optional[str] = None
    key_bcci_2: Optional[str] = None
    key_bigbash: Optional[str] = None
    key_cricheroes: Optional[str] = None
    key_crichq: Optional[str] = None
    key_cricinfo_2: Optional[str] = None
    key_cricinfo_3: Optional[str] = None
    key_cricingif: Optional[str] = None
    key_cricketarchive: Optional[str] = None
    key_cricketarchive_2: Optional[str] = None
    key_cricketworld: Optional[str] = None
    key_nvplay: Optional[str] = None
    key_nvplay_2: Optional[str] = None
    key_opta: Optional[str] = None
    key_opta_2: Optional[str] = None
    key_pulse: Optional[str] = None
    key_pulse_2: Optional[str] = None


class PersonName:
    """Alternate names for a person."""
    id: int
    person_id: ForeignKey[str, "person"]
    name: str


class Match:
    id: int
    filename: str  # source json filename
    data_version: str
    meta_created: str  # meta.created date string
    meta_revision: int
    gender: str  # male / female
    match_type: str  # Test, ODI, T20, IT20, MDM
    team_type: str  # international / club
    season: str
    team1: str
    team2: str
    venue: Optional[str] = None
    city: Optional[str] = None
    venue_country: Optional[str] = None  # populated via api.venue_aliases
    event_name: Optional[str] = None
    event_match_number: Optional[int] = None
    event_group: Optional[str] = None
    event_stage: Optional[str] = None
    match_type_number: Optional[int] = None
    overs: Optional[int] = None
    balls_per_over: int = 6
    toss_winner: Optional[str] = None
    toss_decision: Optional[str] = None  # bat / field
    toss_uncontested: bool = False
    outcome_winner: Optional[str] = None
    outcome_by_runs: Optional[int] = None
    outcome_by_wickets: Optional[int] = None
    outcome_by_innings: Optional[int] = None
    outcome_result: Optional[str] = None  # draw / tie / no result
    outcome_method: Optional[str] = None  # D/L, VJD, etc.
    outcome_eliminator: Optional[str] = None
    outcome_bowl_out: Optional[str] = None
    player_of_match: Optional[dict] = None  # JSON list of names
    dates: dict  # JSON list of date strings
    officials: Optional[dict] = None  # JSON object of officials


class MatchDate:
    """Individual match dates (for multi-day matches)."""
    id: int
    match_id: ForeignKey[int, "match"]
    date: str  # YYYY-MM-DD


class MatchPlayer:
    """Players in a match, per team."""
    id: int
    match_id: ForeignKey[int, "match"]
    team: str
    player_name: str
    person_id: Optional[ForeignKey[str, "person"]] = None


class Innings:
    id: int
    match_id: ForeignKey[int, "match"]
    innings_number: int  # 0-indexed
    team: str
    declared: bool = False
    forfeited: bool = False
    super_over: bool = False
    target_runs: Optional[int] = None
    target_overs: Optional[float] = None
    powerplays: Optional[dict] = None  # JSON
    penalty_runs_pre: int = 0
    penalty_runs_post: int = 0


class Delivery:
    id: int
    innings_id: ForeignKey[int, "innings"]
    over_number: int
    delivery_index: int  # position within the over's deliveries array
    batter: str
    bowler: str
    non_striker: str
    batter_id: Optional[ForeignKey[str, "person"]] = None
    bowler_id: Optional[ForeignKey[str, "person"]] = None
    non_striker_id: Optional[ForeignKey[str, "person"]] = None
    runs_batter: int = 0
    runs_extras: int = 0
    runs_total: int = 0
    runs_non_boundary: Optional[bool] = None
    extras_wides: int = 0
    extras_noballs: int = 0
    extras_byes: int = 0
    extras_legbyes: int = 0
    extras_penalty: int = 0


class Wicket:
    id: int
    delivery_id: ForeignKey[int, "delivery"]
    player_out: str
    player_out_id: Optional[ForeignKey[str, "person"]] = None
    kind: str  # bowled, caught, lbw, stumped, run out, etc.
    fielders: Optional[dict] = None  # JSON list of fielder objects


class FieldingCredit:
    """One row per fielder per wicket — denormalized from wicket.fielders."""
    id: int
    wicket_id: ForeignKey[int, "wicket"]
    delivery_id: ForeignKey[int, "delivery"]
    fielder_name: str
    fielder_id: Optional[ForeignKey[str, "person"]] = None
    kind: str  # caught, stumped, run_out, caught_and_bowled
    is_substitute: bool = False


class KeeperAssignment:
    """One row per regular innings — who kept, at what confidence.

    See docs/spec-fielding-tier2.md for the 4-layer algorithm that
    populates this table and the ambiguous_reason / confidence enums.
    NULL keeper_id means the innings was ambiguous; details in
    ambiguous_reason + candidate_ids_json.
    """
    id: int
    innings_id: ForeignKey[int, "innings"]
    keeper_id: Optional[ForeignKey[str, "person"]] = None
    method: Optional[str] = None  # stumping|season_single|career_single|team_ever_single|manual
    confidence: Optional[str] = None  # definitive|high|medium|low
    ambiguous_reason: Optional[str] = None
    candidate_ids_json: Optional[dict] = None  # JSON list of competing person_ids when ambiguous


class PlayerScopeStats:
    """One row per (person, scope) — denormalized per-player aggregates.

    `scope_key` is a stable hash of (tournament || season || gender ||
    team_type). The grain is the finest practical scope; queries that
    need a coarser scope (e.g. "all men's club matches across seasons")
    aggregate by SUM-ing rows whose other axes match.

    Built and maintained by `scripts/populate_player_scope_stats.py`,
    auto-called from `import_data.py` (full) and `update_recent.py`
    (incremental). Spec 1 of `internal_docs/spec-team-compare-average.md`
    populates this table but does NOT consume it from any endpoint —
    it exists as the foundation for Spec 2 (cross-app comparisons,
    `internal_docs/outlook-comparisons.md`), particularly position-
    matched player compare.

    Phase boundaries match `api/routers/teams.py`:
        powerplay = over 0-5, middle = 6-14, death = 15-19.
    Bowler `wickets` excludes run out / retired hurt / retired out /
    obstructing the field, matching `api/routers/bowling.py`.

    Position derivation: per innings, position N is the order of
    appearance — striker on the first delivery is position 1,
    non_striker is 2, each subsequent newcomer is position N+1.
    `avg_batting_position` is innings-weighted; `innings_by_position_json`
    is a length-12 array indexed by position (index 0 unused, indices
    1..11 carry counts; index 11 absorbs anything that falls outside
    the 11-batter convention).
    """
    person_id: ForeignKey[str, "person"]
    scope_key: str  # stable hash of tournament || season || gender || team_type
    tournament: Optional[str] = None
    season: str = ""
    gender: str = ""
    team_type: str = ""
    matches: int = 0  # distinct matches in XI (from matchplayer)
    # batting
    innings_batted: int = 0
    runs: int = 0
    legal_balls: int = 0
    dots: int = 0
    fours: int = 0
    sixes: int = 0
    dismissals: int = 0
    avg_batting_position: Optional[float] = None
    innings_by_position_json: Optional[dict] = None  # JSON array, length 12
    # bowling
    balls_bowled: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    bowling_dots: int = 0
    boundaries_conceded: int = 0
    powerplay_overs: float = 0.0
    middle_overs: float = 0.0
    death_overs: float = 0.0
    # innings in which the bowler took ≥ 4 wickets — sibling volume
    # field to `wickets`; backs the per-innings four-wicket-haul rate
    # added in spec-rate-vs-volume-audit.md §2.1 Group A.
    four_wicket_hauls: int = 0
    # Distinct innings the player bowled in (delivered ≥1 legal ball).
    # Per-innings bowling denominator analogous to innings_batted on the
    # batting side. Tier 2 of spec-apples-to-apples-baselines.md surfaces
    # this on the cohort path so the over-mix-weighted per-innings rates
    # (wickets_per_innings etc.) can be scaled from the per-attendance
    # rates the per-over child table yields by the average
    # attendances-per-unique-innings factor.
    bowling_innings: int = 0
    # fielding
    catches: int = 0
    runouts: int = 0
    stumpings: int = 0
    catches_as_keeper: int = 0
    matches_as_keeper: int = 0
    # milestone counts (per-innings batting bucketing) — Q6 of spec-player-
    # baseline-parity.md. Bucketed at populate time from per-innings runs.
    # `ducks` = innings where runs=0 AND the batter was dismissed in that
    # innings (matches the cricketing convention).
    thirties: int = 0   # innings with 30 ≤ runs < 50
    fifties: int = 0    # innings with 50 ≤ runs < 100
    hundreds: int = 0   # innings with runs ≥ 100
    ducks: int = 0      # innings with runs = 0 AND dismissed


class PlayerScopeStatsOver:
    """One row per (person, scope, over_number) — per-over bowling aggregates.

    Child of PlayerScopeStats: same scope_key semantics, further keyed
    by the over the delivery occurred in. over_number is 1..20 in this
    table (the delivery table stores 0..19; we shift to 1-indexed at
    populate time so consumers can refer to "Over 1" through "Over 20"
    without translating).

    Drives the over-mix bowling cohort baseline endpoint
    (`/scope/averages/players/bowling/summary`) and the per-bowler
    over-distribution histogram (next-spec viz work).

    Built and maintained by
    `scripts/populate_playerscopestats_over.py`, auto-called from
    `import_data.py` (full) and `update_recent.py` (incremental).
    Spec: `internal_docs/spec-player-compare-average.md` §4.3.

    Per-over aggregates (legal-balls-only for the rate denominator):
      runs_conceded — SUM(runs_total) over ALL deliveries in the over
                       (matches the bowling router's economy basis).
      legal_balls   — count of deliveries where extras_wides=0 AND
                       extras_noballs=0.
      wickets       — count of wicket-table rows credited to the
                       bowler at this over, excluding run out / retired
                       hurt / retired out / obstructing the field.
      dots          — count of deliveries where runs_batter=0 AND
                       runs_total=0 (effectively legal AND dot).
      boundaries    — count of deliveries where runs_batter=4 OR 6.
    """
    person_id: ForeignKey[str, "person"]
    scope_key: str  # matches PlayerScopeStats.scope_key
    over_number: int  # 1..20 (1-indexed in this table)
    runs_conceded: int = 0
    legal_balls: int = 0
    wickets: int = 0
    dots: int = 0
    boundaries: int = 0
    # Maiden overs bowled by this person at this over-number in this scope.
    # A maiden = the bowler bowled all 6 legal balls of the over with 0
    # runs conceded (off the bat + extras). Added per Q6 of
    # `spec-player-baseline-parity.md` to back maidens_per_innings cohort
    # baselines.
    maidens: int = 0
    # Tier 2 of spec-apples-to-apples-baselines.md.
    # innings_bowled — distinct innings where this person delivered ≥1
    # legal ball at this over_number in this scope. Per-bucket
    # denominator for the over-weighted per-innings cohort rates
    # (wickets/inn, maidens/inn, four_wicket_hauls/inn) — replaces
    # the prior `wickets_per_over × 4` heuristic.
    innings_bowled: int = 0
    # four_wicket_hauls — count of 4-fers attributed to this over_number
    # by the over in which the bowler's 4th wicket fell in that innings.
    # Lets the cohort 4-fers/inn rate be convex-combined over the
    # bowler's over-mix.
    four_wicket_hauls: int = 0
    # PT2 of spec-prob-baselines.md — wicket-ladder milestones for
    # bowling ProbChip cohort baselines.
    #
    #   three_wicket_hauls / five_wicket_hauls — over-attribution
    #     pattern (same as four_wicket_hauls): the haul is credited to
    #     the over_bucket where the bowler's 3rd / 5th wicket fell.
    #
    #   innings_with_wicket / innings_with_two — per-spell-touching
    #     pattern (different from above): for every (innings, bowler)
    #     where the bowler bowled ≥1 legal ball at this over_bucket AND
    #     total wickets in that spell met the threshold, increment
    #     here. So P(≥1) per bucket = innings_with_wicket /
    #     innings_bowled, P(≥2) per bucket = innings_with_two /
    #     innings_bowled. Spec §3.2.
    three_wicket_hauls: int = 0
    five_wicket_hauls: int = 0
    innings_with_wicket: int = 0
    innings_with_two: int = 0
    # PT3 of spec-prob-baselines.md — economy + runs-conceded threshold
    # counters for the bowling ProbChip cohort baselines on /bowlers/.../
    # distribution's economy + runs_conceded blocks.
    #
    # `innings_qualifying` — distinct (innings, bowler) pairs where the
    # bowler bowled ≥1 legal ball at THIS over_bucket AND ≥12 total
    # legal balls in the spell. This is the per-bucket denominator for
    # the threshold cohort baselines: the player chip's master sample
    # filters at min_balls=12, so the cohort denominator must filter
    # the SAME population to be apples-to-apples (otherwise the prob is
    # biased low by ultra-short cameos that can't satisfy the chip's
    # threshold). See spec §3.2 + §8.1 + Decision 1.
    #
    # The eight threshold counters apply min_balls=12 uniformly to both
    # numerator and denominator. Spell-level predicates:
    #   econ leq X = (spell_runs_conceded × 6 / spell_legal_balls) ≤ X,
    #                gated by spell_legal_balls ≥ 12.
    #   econ geq X = same comparison, ≥ X, same gating.
    #   runs leq X = spell_runs_conceded ≤ X, gated by spell_legal_balls
    #                ≥ 12. Matches the chip's master-sample gate.
    #   runs geq X = same, ≥ X, same gating.
    innings_qualifying: int = 0
    innings_econ_leq_6: int = 0
    innings_econ_leq_7: int = 0
    innings_econ_geq_9: int = 0
    innings_econ_geq_10: int = 0
    innings_runs_leq_15: int = 0
    innings_runs_leq_25: int = 0
    innings_runs_geq_40: int = 0
    innings_runs_geq_50: int = 0


class PlayerScopeStatsFieldingCatchDist:
    """One row per (person, scope) — per-match catches distribution.

    PT4 of internal_docs/spec-prob-baselines.md. Backs the fielding
    ProbChip cohort baselines P(=0) / P(=1) / P(≥2) on the
    /fielders/{id}/distribution catches block.

    For every match the person played in (matchplayer-based), counts
    their non-substitute catches in that match (FieldingCredit
    kind IN ('caught', 'caught_and_bowled') AND is_substitute=0 per
    Convention 3 + the spec's master-sample contract). Buckets each
    match into one of three slots:
      matches_with_0    — match where the player took 0 catches (most).
      matches_with_1    — match where the player took exactly 1 catch.
      matches_with_ge2  — match where the player took ≥ 2 catches.

    Per-bucket cohort prob (for the keeper-binary cohort):
      P(=0) = SUM(matches_with_0)   / SUM(matches_total)
      P(=1) = SUM(matches_with_1)   / SUM(matches_total)
      P(≥2) = SUM(matches_with_ge2) / SUM(matches_total)
    where matches_total = matches_with_0 + matches_with_1 + matches_with_ge2.

    Built and maintained by
    `scripts/populate_playerscopestats_fielding_catch_dist.py`,
    auto-called from `import_data.py` (full) and `update_recent.py`
    (incremental). DROP+CREATE on full populate per spec §3 — no
    idempotent ALTER.
    """
    person_id: ForeignKey[str, "person"]
    scope_key: str
    matches_with_0: int = 0
    matches_with_1: int = 0
    matches_with_ge2: int = 0


class PlayerScopeStatsFieldingPosition:
    """One row per (fielder, scope, dismissed-batter-position-bucket).

    Child of PlayerScopeStats: same scope_key semantics; the
    `position_bucket` describes the DISMISSED batter's position in the
    innings (1=opener for positions 1+2 merged, 2=#3, …, 10=#11).
    person_id is the FIELDER (the one credited with the catch /
    stumping / run-out).

    Substitute fielders are EXCLUDED (is_substitute = 0 filter applied
    at populate). Spec §5.2 + CLAUDE.md "Substitute fielders —
    INCLUDED in /leaders, EXCLUDED in /distribution" — the child
    table's downstream consumers are distribution-side endpoints.

    Convention 3 (CLAUDE.md): `catches` is the inclusive count of
    kind IN ('caught', 'caught_and_bowled'); caught_and_bowled is a
    sub-component of the catches headline, not summed separately.

    Drives the fielding cohort baseline endpoint (Phase 3) and the
    per-fielder dismissed-position histogram (next-spec viz). Spec:
    `internal_docs/spec-player-compare-average.md` §4.4.
    """
    person_id: ForeignKey[str, "person"]  # the FIELDER
    scope_key: str  # matches PlayerScopeStats.scope_key
    position_bucket: int  # 1=opener, 2=#3, ..., 10=#11 (DISMISSED batter's bucket)
    catches: int = 0
    stumpings: int = 0
    run_outs: int = 0
    dismissals: int = 0  # catches + stumpings + run_outs


class PlayerScopeStatsBattingPhase:
    """One row per (person, scope, phase_bucket) — per-phase batting aggregates.

    Child of PlayerScopeStats: same scope_key semantics, further keyed
    by the phase the ball was bowled in (1=powerplay overs 0-5, 2=middle
    overs 6-14, 3=death overs 15-19 — matching the parent populate's
    `_phase` boundaries and `api/routers/teams.py`).

    Drives the per-phase batting cohort baseline endpoint
    (`/api/v1/scope/averages/players/batting/by-phase`) and the per-
    batter phase-distribution visualisations (next-spec viz). Both
    consumers read the same indexed table.

    Built and maintained by
    `scripts/populate_playerscopestats_batting_phase.py`, auto-called
    from `import_data.py` (full) and `update_recent.py` (incremental)
    alongside the position child populate. Spec:
    `internal_docs/spec-player-baseline-parity.md` §3.1.1.

    Aggregation excluded-kinds match the parent:
      - Batter dismissals exclude 'retired hurt' / 'retired out'
        (BATTER_DISMISSAL_EXCLUDED).
    """
    person_id: ForeignKey[str, "person"]
    scope_key: str  # matches PlayerScopeStats.scope_key
    phase_bucket: int  # 1=powerplay, 2=middle, 3=death
    innings_in_phase: int = 0    # innings where the batter faced ≥1 ball in this phase
    balls_in_phase: int = 0       # legal balls faced in this phase
    runs_in_phase: int = 0        # runs scored in this phase
    dots_in_phase: int = 0
    fours_in_phase: int = 0
    sixes_in_phase: int = 0
    boundaries_in_phase: int = 0  # fours + sixes
    dismissals_in_phase: int = 0


class PlayerScopeStatsBattingPhasePosition:
    """One row per (person, scope, phase_bucket, position_bucket) —
    position × phase per-batter aggregates.

    Tier 3 of internal_docs/spec-apples-to-apples-baselines.md. Cross
    of PlayerScopeStatsBattingPhase (phase_bucket axis) and
    PlayerScopeStatsPosition (position_bucket axis): 3 phases × 10
    positions = up to 30 rows per (person, scope).

    Drives a position-weighted per-phase batting cohort baseline —
    replaces the position-FLAT baseline currently used by
    compute_players_batting_by_phase so an opener's powerplay SR is
    compared against other openers in the powerplay, not against
    every batter in the powerplay (which is dominated by tail-enders
    who rarely face the new ball).

    Built and maintained by
    `scripts/populate_playerscopestats_batting_phase_position.py`,
    auto-called from `import_data.py` (full) and `update_recent.py`
    (incremental) alongside the other player-scope child populates.

    Per-(person, scope, phase, position) aggregates:
      innings_in_phase — distinct innings where the batter faced ≥1
                         legal ball IN this phase, at this position.
      balls_in_phase   — legal balls faced in this phase × position.
      runs_in_phase    — runs scored.
      dots_in_phase    — dots.
      fours_in_phase / sixes_in_phase / boundaries_in_phase — same.
      dismissals_in_phase — dismissed batter credits.

    Phase boundaries match `_phase` in populate_player_scope_stats.py
    (1=pp overs 0-5, 2=middle 6-14, 3=death 15-19). Position bucket
    semantics match position_to_bucket (1=opener pos 1+2 merged,
    2=#3, …, 10=#11).
    """
    person_id: ForeignKey[str, "person"]
    scope_key: str  # matches PlayerScopeStats.scope_key
    phase_bucket: int     # 1=pp, 2=middle, 3=death
    position_bucket: int  # 1=opener, 2=#3, ..., 10=#11
    innings_in_phase: int = 0
    balls_in_phase: int = 0
    runs_in_phase: int = 0
    dots_in_phase: int = 0
    fours_in_phase: int = 0
    sixes_in_phase: int = 0
    boundaries_in_phase: int = 0
    dismissals_in_phase: int = 0


class PlayerScopeStatsFieldingPhase:
    """One row per (person, scope, phase_bucket) — per-phase fielding aggregates.

    Child of PlayerScopeStats: same scope_key semantics; phase_bucket
    matches PlayerScopeStatsBattingPhase (1=pp overs 0-5, 2=middle 6-14,
    3=death 15-19). The fielder is credited based on the phase the
    delivery (the one carrying the fielding credit) occurred in.

    Substitute fielders EXCLUDED at populate (is_substitute = 0),
    matching the existing fielding-distribution rule (CLAUDE.md
    "Substitute fielders — INCLUDED in /leaders, EXCLUDED in
    /distribution"). Per-match denominators on the consumer side are
    drawn from playerscopestats.matches (matchplayer-based), where
    subs aren't counted either — sample consistency is preserved.

    Convention 3 (CLAUDE.md): `catches_in_phase` is the inclusive count
    of `kind IN ('caught', 'caught_and_bowled')` in this phase.

    Drives the per-phase fielding cohort baseline endpoint
    (`/api/v1/scope/averages/players/fielding/by-phase`). Spec:
    `internal_docs/spec-player-baseline-parity.md` §3.1.2.
    """
    person_id: ForeignKey[str, "person"]  # the FIELDER
    scope_key: str
    phase_bucket: int  # 1=powerplay, 2=middle, 3=death
    catches_in_phase: int = 0       # kind IN ('caught','caught_and_bowled') AND is_substitute=0
    run_outs_in_phase: int = 0      # kind='run_out' AND is_substitute=0
    stumpings_in_phase: int = 0     # kind='stumped' AND is_substitute=0
    dismissals_in_phase: int = 0    # catches + run_outs + stumpings (stored for query convenience)


class PlayerScopeStatsPosition:
    """One row per (person, scope, position_bucket) — per-position batting aggregates.

    Child table to PlayerScopeStats: same scope_key semantics; further
    keyed by the merged-opener position bucket (1=opener for positions
    1+2 merged, 2=#3, 3=#4, …, 10=#11). The merge for openers reflects
    `derive_positions`' arbitrary striker/non-striker assignment on
    ball 1 — splitting them creates noise. Other positions stay
    individual.

    Drives the position-mix baseline endpoints (per-bucket cohort
    metric) and per-player position-distribution histograms (next-spec
    visualisation work). Both consumers read the same indexed table.

    Built and maintained by
    `scripts/populate_playerscopestats_position.py`, auto-called from
    `import_data.py` (full) and `update_recent.py` (incremental)
    alongside the parent PlayerScopeStats populate. Spec:
    `internal_docs/spec-player-compare-average.md` §4.2.
    """
    person_id: ForeignKey[str, "person"]
    scope_key: str  # matches PlayerScopeStats.scope_key
    position_bucket: int  # 1=opener (pos 1+2 merged), 2=#3, ..., 10=#11
    innings: int = 0
    runs: int = 0
    legal_balls: int = 0
    dismissals: int = 0
    fours: int = 0
    sixes: int = 0
    dots: int = 0
    # Tier 1 of spec-apples-to-apples-baselines.md — per-position
    # milestone counts so cohort per-innings rates (hundreds/inn,
    # fifties/inn, thirties/inn, ducks/inn) can be position-weighted
    # via convex combination on by_position[i].milestone_per_innings.
    thirties: int = 0
    fifties: int = 0
    hundreds: int = 0
    ducks: int = 0
    # PT1 of spec-prob-baselines.md — extra per-position milestone
    # buckets for the batting ProbChip cohort baselines:
    #   failures_10 = innings where runs <= 10 (the P(≤10) chip
    #                 threshold; includes ducks).
    #   seventies   = innings where 70 <= runs < 100 (so the cohort
    #                 baseline for P(≥70) is seventies + hundreds).
    failures_10: int = 0
    seventies: int = 0


class PlayerScopeStatsBattingOver:
    """One row per (person, scope, over_number) — per-over batting aggregates.

    Tier 4 of internal_docs/spec-apples-to-apples-baselines.md. Mirrors
    PlayerScopeStatsOver on the bowling side: same scope_key semantics,
    further keyed by the over the BATTER faced a delivery in.

    over_number is 1..20 (the underlying delivery table stores 0..19;
    we shift to 1-indexed at populate time).

    Drives the per-over batting cohort baseline endpoint
    (`/scope/averages/players/batting/by-over`) and the new
    SR-by-Over chart overlay on /batting deep-dive.

    Built and maintained by
    `scripts/populate_playerscopestats_batting_over.py`, auto-called
    from `import_data.py` (full) and `update_recent.py` (incremental).

    Per-over aggregates (legal-balls-only for the rate denominator):
      legal_balls_faced — count of deliveries the batter faced in this
                          over bucket where extras_wides=0 AND
                          extras_noballs=0.
      runs              — SUM(runs_batter) on legal balls only (matches
                          batting router convention).
      dots              — count of deliveries where legal AND runs_batter=0
                          AND runs_total=0.
      fours / sixes     — count of legal balls where runs_batter==4 / 6.
      dismissals        — count of wickets where the player was the
                          dismissed batter, occurring at a delivery
                          in this over bucket (excluding retired hurt /
                          retired out per BATTER_DISMISSAL_EXCLUDED).
      innings_faced     — distinct innings where the batter faced ≥1
                          legal ball in this over bucket. Per-bucket
                          innings denominator (same role as
                          PlayerScopeStatsOver.innings_bowled).
    """
    person_id: ForeignKey[str, "person"]
    scope_key: str  # matches PlayerScopeStats.scope_key
    over_number: int  # 1..20
    legal_balls_faced: int = 0
    runs: int = 0
    dots: int = 0
    fours: int = 0
    sixes: int = 0
    dismissals: int = 0
    innings_faced: int = 0


class Partnership:
    """One row per on-field batting partnership.

    See internal_docs/spec-team-stats.md. `partnership_runs` includes ALL extras
    (matches innings total math); `partnership_balls` is legal balls only.
    Per-batter `batter{1,2}_runs` are off-the-bat only. `batter1` is the
    earlier-arriver (= survivor of previous partnership; = striker on
    first delivery for the opening stand). `wicket_number` follows
    cricsheet's running wicket count (retired hurt increments it too);
    queries needing "before Nth real dismissal" filter on
    `ended_by_kind NOT IN ('retired hurt', 'retired not out')`.
    """
    id: int
    innings_id: ForeignKey[int, "innings"]
    wicket_number: Optional[int] = None  # NULL iff unbroken
    batter1_id: Optional[ForeignKey[str, "person"]] = None
    batter2_id: Optional[ForeignKey[str, "person"]] = None
    batter1_name: str = ""
    batter2_name: str = ""
    batter1_runs: int = 0
    batter1_balls: int = 0  # legal balls faced
    batter2_runs: int = 0
    batter2_balls: int = 0
    partnership_runs: int = 0  # SUM(delivery.runs_total) — includes extras
    partnership_balls: int = 0  # legal balls only
    start_delivery_id: ForeignKey[int, "delivery"] = 0
    end_delivery_id: ForeignKey[int, "delivery"] = 0
    unbroken: bool = False
    ended_by_kind: Optional[str] = None  # wicket.kind of the terminating wicket


# ─── bucket_baseline_* — Phase 2 of Compare-tab perf ────────────────────
#
# Six narrow tables holding per-(gender, team_type, tournament, season,
# team) aggregates. team='__league__' rows are the pool-weighted league
# baselines; every other row is per-team. SUM-then-divide over cells at
# query time gives byte-identical numbers to the live aggregator.
#
# Built and maintained by `scripts/populate_bucket_baseline.py`,
# auto-called from `import_data.py` (full) and `update_recent.py`
# (incremental). Spec: `internal_docs/spec-team-bucket-baseline.md`.
#
# `tournament=''` represents NULL event_name (bilateral matches without
# an explicit tournament). Stored as empty string for SQL convenience.

LEAGUE_TEAM_KEY = "__league__"


class BucketBaselineMatch:
    id: int
    gender: str
    team_type: str
    tournament: str
    season: str
    team: str  # team name, OR LEAGUE_TEAM_KEY for the pool-weighted row
    matches: int = 0
    decided: int = 0
    ties: int = 0
    no_results: int = 0
    toss_decided: int = 0
    bat_first_wins: int = 0
    field_first_wins: int = 0


class BucketBaselineBatting:
    id: int
    gender: str
    team_type: str
    tournament: str
    season: str
    team: str
    innings_batted: int = 0
    total_runs: int = 0
    legal_balls: int = 0
    fours: int = 0
    sixes: int = 0
    dots: int = 0
    # Per-innings stats — stored as sums + counts so SUM-over-cells
    # gives the right combined avg (per-innings weights cancel).
    first_inn_runs_sum: int = 0
    first_inn_count: int = 0
    second_inn_runs_sum: int = 0
    second_inn_count: int = 0
    # MAX over per-innings totals — combine via MAX(MAX) across cells.
    highest_inn_runs: int = 0
    # Identity of the cell's highest single-innings total — combine via
    # picking the cell with MAX(highest_inn_runs) when SUMing over cells.
    highest_inn_match_id: Optional[int] = None
    highest_inn_team: Optional[str] = None
    highest_inn_innings_number: Optional[int] = None
    # Lowest all-out total in cell — MIN over per-innings totals where
    # the team lost ≥10 wickets. NULL if no all-out innings in cell.
    lowest_all_out_runs: Optional[int] = None
    lowest_all_out_match_id: Optional[int] = None
    lowest_all_out_team: Optional[str] = None
    lowest_all_out_innings_number: Optional[int] = None
    # Per-batter-innings 50+/100+ counts. SUM cleanly across cells.
    fifties: int = 0
    hundreds: int = 0
    # Per-inning splits for /teams/{team}/batting/by-inning. SUM across
    # cells gives team-side totals; SUM / SUM(first_inn_count) gives the
    # league per-1st-innings averages. Phase D of
    # spec-series-precompute-followup.md.
    first_inn_legal_balls: int = 0
    first_inn_fours: int = 0
    first_inn_sixes: int = 0
    first_inn_dots: int = 0
    first_inn_wickets_lost: int = 0
    second_inn_legal_balls: int = 0
    second_inn_fours: int = 0
    second_inn_sixes: int = 0
    second_inn_dots: int = 0
    second_inn_wickets_lost: int = 0


class BucketBaselineBowling:
    id: int
    gender: str
    team_type: str
    tournament: str
    season: str
    team: str
    innings_bowled: int = 0
    matches: int = 0  # COUNT(DISTINCT m.id) where this side bowled
    runs_conceded: int = 0
    legal_balls: int = 0
    wides: int = 0   # count of wide deliveries (scope_averages semantic)
    noballs: int = 0 # count of noball deliveries
    wide_runs: int = 0    # SUM(extras_wides) — RUNS from wides (team-side)
    noball_runs: int = 0  # SUM(extras_noballs) — RUNS from noballs
    fours_conceded: int = 0
    sixes_conceded: int = 0
    dots: int = 0
    wickets: int = 0  # bowler-credited (excludes run out / retired / obstructing)
    # MAX of opposition per-innings totals against this side. Combine
    # via MAX(MAX) across cells. Drives /teams/{team}/bowling/by-season
    # `worst_conceded`.
    worst_inn_runs: int = 0
    # Per-inning splits for /teams/{team}/bowling/by-inning. SUM across
    # cells gives team-side totals; SUM / SUM(first_inn_count) gives the
    # league per-1st-innings averages. Phase D of
    # spec-series-precompute-followup.md.
    first_inn_count: int = 0
    first_inn_balls: int = 0
    first_inn_runs_conceded: int = 0
    first_inn_fours_conceded: int = 0
    first_inn_sixes_conceded: int = 0
    first_inn_dots: int = 0
    first_inn_wickets: int = 0
    second_inn_count: int = 0
    second_inn_balls: int = 0
    second_inn_runs_conceded: int = 0
    second_inn_fours_conceded: int = 0
    second_inn_sixes_conceded: int = 0
    second_inn_dots: int = 0
    second_inn_wickets: int = 0


class BucketBaselineFielding:
    id: int
    gender: str
    team_type: str
    tournament: str
    season: str
    team: str
    matches: int = 0  # innings the team was on the field
    catches: int = 0  # cricsheet kind='caught'
    caught_and_bowled: int = 0
    stumpings: int = 0  # cricsheet kind='stumped'
    run_outs: int = 0


class BucketBaselinePhase:
    id: int
    gender: str
    team_type: str
    tournament: str
    season: str
    team: str
    phase: str  # 'powerplay' | 'middle' | 'death'
    side: str   # 'batting' | 'bowling'
    runs: int = 0
    legal_balls: int = 0
    fours: int = 0
    sixes: int = 0
    dots: int = 0
    wickets: int = 0  # only meaningful when side='bowling'; 0 otherwise


class BucketBaselinePartnership:
    id: int
    gender: str
    team_type: str
    tournament: str
    season: str
    team: str
    wicket_number: int  # 0..9 (cricsheet); API exposes 1..10
    n: int = 0
    total_runs: int = 0
    total_balls: int = 0
    best_runs: int = 0  # MAX over partnerships in cell
    # 50+/100+ counts — sum cleanly across cells. Drives partnerships/
    # summary + by-season + by-wicket count_50_plus / count_100_plus.
    count_50_plus: int = 0
    count_100_plus: int = 0
    # Identity of the cell's best partnership — read-side picks the
    # cell with MAX(best_runs) and joins back to partnership for full
    # identity (batters, date, balls). NULL when n=0.
    best_pair_partnership_id: Optional[int] = None


class BucketBaselineMoments:
    """Per-cell top individual moments — drives /series/summary's
    highest_individual / best_bowling / best_fielding tiles without
    running 3 slow GROUP BY (person, match) queries at request time.

    One row per (gender, team_type, tournament, season) cell. No `team`
    column — these records are per-cell global maxima; rivalry-scoped
    requests (filter_team + filter_opponent) fall back to live SQL.

    Read-side roll-up: across a scope spanning N cells, pick the row
    that maximises the relevant metric. SQL becomes a tiny scan over a
    few hundred bucket rows instead of a GROUP BY over millions of
    deliveries.
    """
    id: int
    gender: str
    team_type: str
    tournament: str
    season: str
    # Highest individual batting score in this cell (single innings,
    # legal balls only — matches hi_q in api/routers/tournaments.py).
    hi_person_id: Optional[str] = None
    hi_name: Optional[str] = None
    hi_team: Optional[str] = None
    hi_runs: int = 0
    hi_match_id: Optional[int] = None
    hi_date: Optional[str] = None
    # Best bowling figures in this cell (most wickets, ties broken by
    # fewest runs conceded). Matches bb_q.
    bb_person_id: Optional[str] = None
    bb_name: Optional[str] = None
    bb_team: Optional[str] = None
    bb_wickets: int = 0
    bb_runs: int = 0
    bb_match_id: Optional[int] = None
    bb_date: Optional[str] = None
    # Best fielding tally in this cell (most total dismissals, ties
    # broken by stumpings). Convention 3: catches includes C&B. Matches
    # bf_q.
    bf_person_id: Optional[str] = None
    bf_name: Optional[str] = None
    bf_team: Optional[str] = None
    bf_catches: int = 0
    bf_stumpings: int = 0
    bf_run_outs: int = 0
    bf_caught_bowled: int = 0
    bf_total: int = 0
    bf_match_id: Optional[int] = None
    bf_date: Optional[str] = None


# How many partnership ranks are stored per (cell, wicket_number) in
# bucketbaselinepartnershiptop. Exported here (rather than in
# scripts/populate_bucket_baseline.py where it was first defined) so
# the API router can import it without taking a runtime dependency on
# scripts/ — deploy.sh ships api/ + models/ but NOT scripts/.
PARTNERSHIP_TOP_K = 10


class BucketBaselinePartnershipTop:
    """Per-(cell, wicket_number) top-K partnerships — drives
    /series/partnerships/top-by-wicket without scanning the partnership
    table at request time.

    K = PARTNERSHIP_TOP_K (10) ranks stored — matches the endpoint's
    default per_wicket=10.
    League-only — no team column. The endpoint's dispatch rejects
    filter_team via is_precomputed_scope, so per-team rows are unused.

    Ranking matches the live endpoint exactly:
        ORDER BY p.partnership_runs DESC, p.partnership_balls ASC
    Ties beyond balls are arbitrary (live SQL has no tertiary key);
    populate adds p.id ASC as the deterministic tie-break.

    Includes retired-hurt-terminated partnerships (matches live —
    /series/partnerships/top-by-wicket does NOT exclude them, unlike
    bucketbaselinepartnership which excludes for per-wicket aggregates).

    Read-side merge across N cells: collect K rows per cell, sort by
    runs DESC + balls ASC + partnership_id ASC, take top-K.
    """
    id: int
    gender: str
    team_type: str
    tournament: str
    season: str
    wicket_number: int
    rank: int  # 1..K (K=10)
    partnership_id: int
    runs: int
    balls: int


# ─── Records-page precomputed aggregates ──────────────────────────────
#
# Three tables back the /series/records + /teams/{team}/records
# endpoints. Without them, every records request runs 5 full delivery-
# table scans (3M rows) per request — ~13s unfiltered at all-cricket.
# With them, each record list is a single read on the small aggregate
# table joined to match for scope filtering. See spec-driven request
# 2026-05-16 + commits 854b10a (parallelise) + c7afdf1 (team records).


class InningsTotal:
    """Per-innings aggregate — total runs, wickets that fell, sixes,
    fours, plus denormalized super_over so the records SQL can filter
    without re-joining innings."""
    innings_id: ForeignKey[int, "innings"]
    total_runs: int
    total_wkts: int  # excludes retired hurt / retired not out
    total_sixes: int
    total_fours: int
    super_over: bool


class InningsBatterPerf:
    """Per-(batter, innings) batting performance — feeds best-individual
    -batting and any per-innings batting record list. not_out is denormal-
    ized from the EXISTS(wicket WHERE player_out_id = batter) check the
    live query does inline."""
    batter_id: ForeignKey[str, "person"]
    innings_id: ForeignKey[int, "innings"]
    runs: int
    balls: int  # legal balls (excludes wides + no-balls)
    fours: int
    sixes: int
    not_out: bool


class MatchBowlerPerf:
    """Per-(bowler, match) bowling performance — feeds best-bowling-
    figures. wickets uses Convention-3-style attribution (excludes
    run-outs and retired-hurt-style wickets the bowler doesn't own).
    Matches the live SQL's `kind NOT IN ('run out', 'retired hurt',
    'retired out', 'obstructing the field')` predicate."""
    bowler_id: ForeignKey[str, "person"]
    match_id: ForeignKey[int, "match"]
    wickets: int
    runs: int  # runs conceded (sum runs_total over bowler's deliveries)
    balls: int  # legal balls bowled


class MatchFielderPerf:
    """Per-(fielder, match) fielding performance — feeds the per-player
    fielding records lists. Catches INCLUDE caught_and_bowled per
    Convention 3 (codebase invariant — see CLAUDE.md). Volume framing
    (no is_substitute filter) — substitute appearances count.

    dismissals is the denormalized catches + stumpings + run_outs sum
    so ORDER BY dismissals DESC works without expression columns."""
    fielder_id: ForeignKey[str, "person"]
    match_id: ForeignKey[int, "match"]
    catches: int  # incl caught_and_bowled
    stumpings: int
    run_outs: int
    dismissals: int  # catches + stumpings + run_outs
