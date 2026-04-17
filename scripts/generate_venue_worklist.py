"""
Generate the venue-canonicalization worklist CSV.

Phase 1 step 1 of the Venues spec (internal_docs/spec-venues.md). Queries
every distinct (venue, city) pair from `match`, pre-fills proposed
canonical values for the auto-safe cases, and flags everything else
`needs_review=TRUE` so a human can resolve the hard rows (six "County
Ground"s, ambiguous cities, unknown countries).

Pre-fill heuristics (conservative — flag when unsure):

1. Trim / collapse whitespace on raw values.
2. Apply known city aliases (Chittagong → Chattogram, Bengaluru → Bangalore
   standardized one way, Bombay → Mumbai for post-1995 rename, etc.).
3. Fill NULL city when another row with the same (normalized) venue has
   exactly one non-NULL city — that's unambiguous sibling data.
4. Look up country via a city → country map. When city unknown, country
   stays blank and the row is flagged.
5. Detect same-venue-multiple-cities collisions AFTER city aliasing.
   Residual collisions mean either (a) same-name-different-ground (the
   six "County Ground"s) or (b) a rename we don't know about — propose
   the "{raw_venue} ({city})" disambiguator form and flag needs_review.
6. Flag suffix drift (e.g. "Wankhede" vs "Wankhede Stadium" in the same
   city) for human sanity-check — propose the longer form but
   needs_review=TRUE.

Output: docs/venue-worklist/YYYY-MM-DD-worklist.csv

Usage:
    uv run python scripts/generate_venue_worklist.py
    uv run python scripts/generate_venue_worklist.py --db /tmp/cricket-prod-test.db
"""

import argparse
import asyncio
import csv
import datetime as dt
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(REPO_ROOT, "cricket.db")
OUTPUT_DIR = os.path.join(REPO_ROOT, "docs", "venue-worklist")


# ─── City name aliases (raw → canonical) ────────────────────────────
# Conservative: only well-attested official renames or standard spellings.
# Direction is always raw → canonical (what we want to end up with).
CITY_ALIASES: dict[str, str] = {
    "Chittagong":           "Chattogram",          # BD rename 2018
    "Bangalore":            "Bengaluru",           # IN rename 2014
    "Bombay":               "Mumbai",              # IN rename 1995
    "Calcutta":             "Kolkata",             # IN rename 2001
    "Madras":               "Chennai",             # IN rename 1996
    "Baroda":               "Vadodara",            # IN official
    "Mysore":               "Mysuru",              # IN rename 2014
    "Pondicherry":          "Puducherry",          # IN rename 2006
    "Trivandrum":           "Thiruvananthapuram",  # IN official
    "Cawnpore":             "Kanpur",              # IN archaic
    "Ahmadabad":            "Ahmedabad",           # spelling variant
    "Gurgaon":              "Gurugram",            # IN rename 2016
}


# ─── City → country map ────────────────────────────────────────────
# Populated with every cricket city I can think of. Unknowns stay blank
# and get flagged needs_review=TRUE.
CITY_COUNTRY: dict[str, str] = {
    # India
    **{c: "India" for c in [
        "Mumbai", "Delhi", "Kolkata", "Chennai", "Bengaluru", "Hyderabad",
        "Ahmedabad", "Pune", "Jaipur", "Chandigarh", "Mohali", "Nagpur",
        "Dharamsala", "Indore", "Lucknow", "Kanpur", "Kochi", "Visakhapatnam",
        "Vizag", "Cuttack", "Guwahati", "Ranchi", "Raipur", "Rajkot",
        "Vadodara", "Thiruvananthapuram", "Mysuru", "Puducherry", "Gurugram",
        "Surat", "Dehradun", "Greater Noida", "Noida", "Patna", "Srinagar",
        "Jodhpur", "Amritsar", "Faridabad", "Shillong", "Thumba", "Valsad",
        "Vijayawada", "Jamshedpur", "Bhubaneswar", "Dambulla",
    ]},
    # Pakistan
    **{c: "Pakistan" for c in [
        "Karachi", "Lahore", "Islamabad", "Rawalpindi", "Multan", "Peshawar",
        "Faisalabad", "Sialkot", "Hyderabad (Sindh)", "Quetta", "Gujranwala",
    ]},
    # Sri Lanka (Dambulla is actually SL — fix the India list)
    **{c: "Sri Lanka" for c in [
        "Colombo", "Kandy", "Galle", "Pallekele", "Hambantota", "Moratuwa",
        "Dambulla",  # overrides India entry (last-write-wins in dict merge below)
        "Katunayake", "Kurunegala", "Matara", "Ratnapura",
    ]},
    # Bangladesh
    **{c: "Bangladesh" for c in [
        "Dhaka", "Chattogram", "Sylhet", "Khulna", "Fatullah", "Mirpur",
        "Bogra", "Rajshahi", "Cox's Bazar",
    ]},
    # Afghanistan (home fixtures mostly hosted abroad; still worth listing)
    **{c: "Afghanistan" for c in ["Kabul", "Kandahar"]},
    # England (Wales split separately below)
    **{c: "England" for c in [
        "London", "Manchester", "Birmingham", "Leeds", "Nottingham",
        "Southampton", "Bristol", "Chester-le-Street", "Durham",
        "Canterbury", "Chelmsford", "Derby", "Hove", "Leicester",
        "Northampton", "Scarborough", "Taunton", "Worcester", "Lord's",
        "The Oval", "Liverpool", "Oxford", "Cambridge", "Tunbridge Wells",
        "Arundel", "Horsham", "Guildford", "Colwyn Bay", "Beckenham",
        "Edgbaston",
    ]},
    # Wales
    **{c: "Wales" for c in ["Cardiff", "Swansea"]},
    # Scotland
    **{c: "Scotland" for c in ["Edinburgh", "Glasgow", "Aberdeen", "Dundee"]},
    # Ireland
    **{c: "Ireland" for c in [
        "Dublin", "Belfast", "Bready", "Malahide", "Stormont", "Clontarf",
    ]},
    # Australia
    **{c: "Australia" for c in [
        "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Hobart",
        "Canberra", "Darwin", "Cairns", "Townsville", "Geelong", "Launceston",
        "Gold Coast", "Mackay", "Alice Springs", "Newcastle", "Wollongong",
    ]},
    # New Zealand
    **{c: "New Zealand" for c in [
        "Auckland", "Wellington", "Christchurch", "Hamilton", "Napier",
        "Dunedin", "Tauranga", "Nelson", "Queenstown", "New Plymouth",
        "Mount Maunganui", "Whangarei", "Lincoln", "Rangiora",
    ]},
    # South Africa
    **{c: "South Africa" for c in [
        "Johannesburg", "Cape Town", "Durban", "Pretoria", "Centurion",
        "Port Elizabeth", "Gqeberha", "Bloemfontein", "East London",
        "Paarl", "Potchefstroom", "Kimberley", "Benoni", "Kimberly",
    ]},
    # Zimbabwe
    **{c: "Zimbabwe" for c in [
        "Harare", "Bulawayo", "Kwekwe", "Mutare", "Victoria Falls",
    ]},
    # West Indies (island-level — country = the home nation)
    **{c: "Barbados" for c in ["Bridgetown"]},
    **{c: "Jamaica" for c in ["Kingston", "Montego Bay"]},
    **{c: "Trinidad and Tobago" for c in ["Port of Spain", "Tarouba", "Couva"]},
    **{c: "Guyana" for c in ["Providence", "Georgetown"]},
    **{c: "Saint Lucia" for c in ["Gros Islet", "Castries"]},
    **{c: "Antigua and Barbuda" for c in ["North Sound", "St John's", "St. John's"]},
    **{c: "Saint Kitts and Nevis" for c in ["Basseterre"]},
    **{c: "Saint Vincent and the Grenadines" for c in ["Arnos Vale", "Kingstown"]},
    **{c: "Dominica" for c in ["Roseau"]},
    **{c: "Grenada" for c in ["St George's"]},
    # UAE + neutrals
    **{c: "United Arab Emirates" for c in [
        "Dubai", "Sharjah", "Abu Dhabi", "Fujairah", "Ajman",
    ]},
    **{c: "Oman" for c in ["Al Amerat", "Muscat"]},
    **{c: "Nepal" for c in ["Kathmandu", "Kirtipur", "Pokhara"]},
    **{c: "USA" for c in [
        "Lauderhill", "Morrisville", "Dallas", "Houston", "New York",
        "Prairie View", "Pearland",
    ]},
    **{c: "Canada" for c in ["King City", "Toronto", "Brampton", "Mississauga"]},
    # Africa associates
    **{c: "Kenya" for c in ["Nairobi", "Mombasa"]},
    **{c: "Uganda" for c in ["Kampala", "Entebbe", "Lugogo"]},
    **{c: "Rwanda" for c in ["Kigali", "Gahanga"]},
    **{c: "Namibia" for c in ["Windhoek"]},
    **{c: "Botswana" for c in ["Gaborone"]},
    **{c: "Tanzania" for c in ["Dar es Salaam"]},
    **{c: "Nigeria" for c in ["Lagos", "Abuja"]},
    # Europe associates
    **{c: "Netherlands" for c in ["Amstelveen", "Rotterdam", "The Hague", "Utrecht"]},
    **{c: "Germany" for c in ["Krefeld", "Hamburg", "Berlin"]},
    **{c: "Denmark" for c in ["Copenhagen", "Brondby"]},
    **{c: "Italy" for c in ["Rome", "Milan", "Bologna"]},
    **{c: "Spain" for c in ["Madrid", "Barcelona", "La Manga"]},
    **{c: "Malta" for c in ["Marsa"]},
    **{c: "Gibraltar" for c in ["Gibraltar"]},
    **{c: "Finland" for c in ["Helsinki", "Vantaa"]},
    **{c: "Belgium" for c in ["Waterloo", "Brussels"]},
    # Asia associates
    **{c: "Hong Kong" for c in ["Hong Kong", "Mong Kok"]},
    **{c: "Singapore" for c in ["Singapore"]},
    **{c: "Malaysia" for c in ["Kuala Lumpur", "Johor", "Selangor"]},
    **{c: "Thailand" for c in ["Bangkok", "Chiang Mai"]},
    **{c: "Indonesia" for c in ["Bali"]},
    # Americas associates
    **{c: "Bermuda" for c in ["Hamilton (Bermuda)"]},
}
# Fix dict-merge ordering — Dambulla is SL not India. The Sri Lanka block
# is constructed after India so the later write wins; re-assert for safety.
CITY_COUNTRY["Dambulla"] = "Sri Lanka"


WS_RE = re.compile(r"\s+")


def norm(s: str | None) -> str | None:
    """Trim + collapse internal whitespace. None/empty → None."""
    if s is None:
        return None
    s = WS_RE.sub(" ", s).strip()
    return s or None


def apply_city_alias(city: str | None) -> str | None:
    if city is None:
        return None
    return CITY_ALIASES.get(city, city)


def guess_country(city: str | None) -> str:
    if city is None:
        return ""
    return CITY_COUNTRY.get(city, "")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB,
                    help=f"Path to cricket.db (default: {DEFAULT_DB})")
    ap.add_argument("--out-dir", default=OUTPUT_DIR,
                    help=f"Output directory (default: {OUTPUT_DIR})")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found at {args.db}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(args.out_dir, exist_ok=True)

    db = Database(f"sqlite+aiosqlite:///{args.db}")

    # Pull every distinct (venue, city) pair with a sample match + date.
    # match_date is the denormalized per-match dates table.
    rows = await db.q("""
        SELECT m.venue        AS raw_venue,
               m.city         AS raw_city,
               COUNT(*)       AS match_count,
               MIN(m.id)      AS sample_match_id
        FROM   match m
        WHERE  m.venue IS NOT NULL
        GROUP  BY m.venue, m.city
        ORDER  BY COUNT(*) DESC
    """)

    # Backfill sample_date for each sample_match_id. Chunk the IN clause
    # to avoid SQLite's 32k-expression limit on very large DBs.
    sample_ids = [r["sample_match_id"] for r in rows]
    id_to_date: dict[int, str] = {}
    CHUNK = 1000
    for i in range(0, len(sample_ids), CHUNK):
        chunk = sample_ids[i:i + CHUNK]
        id_list = ",".join(str(x) for x in chunk)
        date_rows = await db.q(f"""
            SELECT match_id, MIN(date) AS d
            FROM   matchdate
            WHERE  match_id IN ({id_list})
            GROUP  BY match_id
        """)
        for r in date_rows:
            id_to_date[r["match_id"]] = r["d"]

    # Normalize raw inputs and bucket by normalized venue for ambiguity
    # analysis. One "bucket" = all rows sharing the same normalized venue;
    # the set of distinct cities in that bucket tells us whether the venue
    # is unambiguous, fillable, or a same-name-different-ground collision.
    records: list[dict] = []
    for r in rows:
        raw_v = r["raw_venue"]
        raw_c = r["raw_city"]
        norm_v = norm(raw_v)
        norm_c = apply_city_alias(norm(raw_c))
        records.append({
            "raw_venue":       raw_v,
            "raw_city":        raw_c,
            "norm_venue":      norm_v,
            "norm_city":       norm_c,
            "match_count":     r["match_count"],
            "sample_match_id": r["sample_match_id"],
            "sample_date":     id_to_date.get(r["sample_match_id"], ""),
        })

    # Build buckets: norm_venue → set of non-NULL norm_cities seen.
    venue_to_cities: dict[str, set[str]] = defaultdict(set)
    for rec in records:
        if rec["norm_venue"] and rec["norm_city"]:
            venue_to_cities[rec["norm_venue"]].add(rec["norm_city"])

    # Prefix-suffix drift detection: if norm_venue A is a strict prefix of
    # norm_venue B (word-boundary) AND they share a city, propose the
    # longer form but flag needs_review.
    norm_venues = sorted({r["norm_venue"] for r in records if r["norm_venue"]})
    prefix_map: dict[str, str] = {}  # shorter → longer canonical candidate
    for i, short in enumerate(norm_venues):
        for long in norm_venues:
            if short == long or not long.startswith(short + " "):
                continue
            # Require they share at least one city so we don't link
            # unrelated grounds.
            if venue_to_cities[short] & venue_to_cities[long]:
                prefix_map[short] = long
                break

    # Now compute proposed values per record.
    out_rows = []
    for rec in records:
        raw_v = rec["raw_venue"]
        raw_c = rec["raw_city"]
        norm_v = rec["norm_venue"]
        norm_c = rec["norm_city"]
        notes: list[str] = []
        needs_review = False

        prop_venue = norm_v or ""
        prop_city = norm_c or ""
        prop_country = ""

        # 1. Whitespace/alias normalization was already applied — note it.
        if raw_v != norm_v:
            notes.append("whitespace-normalized venue")
        if raw_c and norm(raw_c) != norm_c:
            notes.append(f"city alias: {norm(raw_c)}→{norm_c}")

        # 2. NULL-city fill from siblings.
        if norm_v and norm_c is None:
            sibling_cities = venue_to_cities.get(norm_v, set())
            if len(sibling_cities) == 1:
                prop_city = next(iter(sibling_cities))
                notes.append(f"city filled from sibling rows ({prop_city})")
            elif len(sibling_cities) == 0:
                notes.append("city NULL and no siblings with a city — please fill")
                needs_review = True
            else:
                notes.append(
                    f"city NULL, ambiguous siblings: {sorted(sibling_cities)}"
                )
                needs_review = True

        # 3. Same-name-different-ground collision (post city-aliasing).
        if norm_v and len(venue_to_cities.get(norm_v, set())) >= 2:
            # Residual >=2 cities means either a real same-name collision
            # (six "County Ground"s) or an undiscovered rename/variant.
            # Propose the "{venue} ({city})" disambiguator for the CITY
            # this row sits in.
            city_for_disambig = prop_city or "???"
            prop_venue = f"{norm_v} ({city_for_disambig})"
            notes.append(
                f"ambiguous venue name across cities "
                f"{sorted(venue_to_cities[norm_v])} — paren-disambiguate"
            )
            needs_review = True

        # 4. Prefix-suffix drift (e.g. "Wankhede" vs "Wankhede Stadium",
        # or "Happy Valley Ground" vs "Happy Valley Ground 2"). Don't
        # auto-propose a merge — half these cases are sibling pitches
        # that must stay separate. Just flag for human review.
        if norm_v in prefix_map:
            notes.append(
                f"prefix of '{prefix_map[norm_v]}' — verify "
                f"whether to merge or keep separate"
            )
            needs_review = True

        # 5. Country guess (depends on final proposed city).
        if prop_city:
            prop_country = guess_country(prop_city)
            if not prop_country:
                notes.append("country unknown — please fill")
                needs_review = True
        else:
            notes.append("no city — country unknown")
            needs_review = True

        out_rows.append({
            "raw_venue":                 raw_v if raw_v is not None else "",
            "raw_city":                  raw_c if raw_c is not None else "",
            "match_count":               rec["match_count"],
            "sample_match_id":           rec["sample_match_id"],
            "sample_date":               rec["sample_date"],
            "proposed_canonical_venue":  prop_venue,
            "proposed_canonical_city":   prop_city,
            "proposed_country":          prop_country,
            "needs_review":              "TRUE" if needs_review else "FALSE",
            "notes":                     "; ".join(notes),
        })

    today = dt.date.today().isoformat()
    out_path = os.path.join(args.out_dir, f"{today}-worklist.csv")
    fieldnames = [
        "raw_venue", "raw_city", "match_count", "sample_match_id", "sample_date",
        "proposed_canonical_venue", "proposed_canonical_city", "proposed_country",
        "needs_review", "notes",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    total = len(out_rows)
    flagged = sum(1 for r in out_rows if r["needs_review"] == "TRUE")
    distinct_venues = len({r["raw_venue"] for r in out_rows})
    null_city = sum(1 for r in out_rows if not r["raw_city"])

    print(f"Wrote {out_path}")
    print(f"  {total} distinct (venue, city) pairs")
    print(f"  {distinct_venues} distinct raw venue names")
    print(f"  {null_city} rows with NULL raw city")
    print(f"  {flagged} rows flagged needs_review=TRUE ({flagged*100//max(total,1)}%)")


if __name__ == "__main__":
    asyncio.run(main())
