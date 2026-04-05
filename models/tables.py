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
