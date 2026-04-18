"""
Canonical venue-name mapping.

Cricsheet records match venues under the raw strings current at match
time. Grounds are renamed (Port Elizabeth → Gqeberha), relabelled with
city suffixes ("Wankhede Stadium" vs "Wankhede Stadium, Mumbai"), and
some share names across grounds (six "County Ground"s in England). This
module is the single source of truth that maps every observed cricsheet
(venue, city) pair to a canonical (venue, city, country) triple.

Used by:
- import_data.py — apply on insert via `resolve()` (clean DB from day 1)
- update_recent.py — same (shares `import_match_file`)
- scripts/fix_venue_names.py — one-time pass over existing DBs that
  pre-date this module

Generated from docs/venue-worklist/2026-04-17-worklist.csv by
/tmp/build_venue_aliases.py. Hand-edit if a one-off tweak is needed;
for bulk additions (next worklist cycle), re-run the CSV round-trip
and regenerate.

Canonical-venue rules summary:
- Ambiguous bare names (County Ground, National Stadium, Gymkhana Club
  Ground, University Oval, Queen's Park) use "X (City)" paren-disambig
  form.
- Sheikh Zayed Stadium Nursery 1/2 → Tolerance Oval / Mohan's Oval.
- Port Elizabeth → Gqeberha, Chittagong → Chattogram,
  Bangalore → Bengaluru (city rename propagation).
- Sibling grounds at multi-oval complexes (Alur I/II/III, Al Amerat
  Turf 1/2, ICC Academy Ground No 2 vs Oval 2, Eden Park vs Outer Oval,
  Sheikh Zayed vs Tolerance vs Mohan's) stay SEPARATE — each has its
  own independent match record.
"""

from typing import Optional


# Key: (raw_venue, raw_city_or_None)
# Value: (canonical_venue, canonical_city, country)
VENUE_ALIASES: dict[tuple[str, Optional[str]], tuple[str, str, str]] = {
    # ─── Shere Bangla National Stadium, Mirpur (Dhaka, Bangladesh) ─
    ('Shere Bangla National Stadium, Mirpur', 'Dhaka'): ('Shere Bangla National Stadium, Mirpur', 'Dhaka', 'Bangladesh'),
    ('Shere Bangla National Stadium', 'Mirpur'): ('Shere Bangla National Stadium, Mirpur', 'Dhaka', 'Bangladesh'),
    ('Shere Bangla National Stadium', 'Dhaka'): ('Shere Bangla National Stadium, Mirpur', 'Dhaka', 'Bangladesh'),

    # ─── Dubai International Cricket Stadium (Dubai, United Arab Emirates) ─
    ('Dubai International Cricket Stadium', 'Dubai'): ('Dubai International Cricket Stadium', 'Dubai', 'United Arab Emirates'),
    ('Dubai International Cricket Stadium', None): ('Dubai International Cricket Stadium', 'Dubai', 'United Arab Emirates'),

    # ─── Al Amerat Cricket Ground Oman Cricket (Ministry Turf 1) (Al Amerat, Oman) ─
    ('Al Amerat Cricket Ground Oman Cricket (Ministry Turf 1)', 'Al Amarat'): ('Al Amerat Cricket Ground Oman Cricket (Ministry Turf 1)', 'Al Amerat', 'Oman'),
    ('Al Amerat Cricket Ground Oman Cricket (Ministry Turf 1)', 'Al Amerat'): ('Al Amerat Cricket Ground Oman Cricket (Ministry Turf 1)', 'Al Amerat', 'Oman'),

    # ─── Tribhuvan University International Cricket Ground, Kirtipur (Kirtipur, Nepal) ─
    ('Tribhuvan University International Cricket Ground, Kirtipur', 'Kirtipur'): ('Tribhuvan University International Cricket Ground', 'Kirtipur', 'Nepal'),
    ('Tribhuvan University International Cricket Ground', 'Kirtipur'): ('Tribhuvan University International Cricket Ground', 'Kirtipur', 'Nepal'),

    # ─── Edgbaston, Birmingham (Birmingham, England) ─
    ('Edgbaston, Birmingham', 'Birmingham'): ('Edgbaston', 'Birmingham', 'England'),
    ('Edgbaston', 'Birmingham'): ('Edgbaston', 'Birmingham', 'England'),

    # ─── Sylhet International Cricket Stadium, Academy Ground (Sylhet, Bangladesh) ─
    ('Sylhet International Cricket Stadium', 'Sylhet'): ('Sylhet International Cricket Stadium, Academy Ground', 'Sylhet', 'Bangladesh'),
    ('Sylhet International Cricket Stadium, Academy Ground', 'Sylhet'): ('Sylhet International Cricket Stadium, Academy Ground', 'Sylhet', 'Bangladesh'),
    ('Sylhet International Cricket Stadium', None): ('Sylhet International Cricket Stadium, Academy Ground', 'Sylhet', 'Bangladesh'),

    # ─── Bayuemas Oval, Kuala Lumpur (Kuala Lumpur, Malaysia) ─
    ('Bayuemas Oval, Kuala Lumpur', 'Kuala Lumpur'): ('Bayuemas Oval', 'Kuala Lumpur', 'Malaysia'),
    ('Bayuemas Oval', 'Kuala Lumpur'): ('Bayuemas Oval', 'Kuala Lumpur', 'Malaysia'),

    # ─── Udayana Cricket Ground (Bali, Indonesia) ─
    ('Udayana Cricket Ground', 'Bali'): ('Udayana Cricket Ground', 'Bali', 'Indonesia'),

    # ─── Terdthai Cricket Ground, Bangkok (Bangkok, Thailand) ─
    ('Terdthai Cricket Ground, Bangkok', 'Bangkok'): ('Terdthai Cricket Ground', 'Bangkok', 'Thailand'),
    ('Terdthai Cricket Ground', 'Bangkok'): ('Terdthai Cricket Ground', 'Bangkok', 'Thailand'),

    # ─── Sharjah Cricket Stadium (Sharjah, United Arab Emirates) ─
    ('Sharjah Cricket Stadium', 'Sharjah'): ('Sharjah Cricket Stadium', 'Sharjah', 'United Arab Emirates'),
    ('Sharjah Cricket Stadium', None): ('Sharjah Cricket Stadium', 'Sharjah', 'United Arab Emirates'),

    # ─── The Rose Bowl, Southampton (Southampton, England) ─
    ('The Rose Bowl, Southampton', 'Southampton'): ('The Rose Bowl', 'Southampton', 'England'),
    ('The Rose Bowl', 'Southampton'): ('The Rose Bowl', 'Southampton', 'England'),

    # ─── Kennington Oval, London (London, England) ─
    ('Kennington Oval, London', 'London'): ('Kennington Oval', 'London', 'England'),
    ('Kennington Oval', 'London'): ('Kennington Oval', 'London', 'England'),

    # ─── Adelaide Oval (Adelaide, Australia) ─
    ('Adelaide Oval', 'Adelaide'): ('Adelaide Oval', 'Adelaide', 'Australia'),
    ('Adelaide Oval', None): ('Adelaide Oval', 'Adelaide', 'Australia'),

    # ─── Gahanga International Cricket Stadium, Rwanda (Kigali, Rwanda) ─
    ('Gahanga International Cricket Stadium, Rwanda', 'Kigali City'): ('Gahanga International Cricket Stadium, Rwanda', 'Kigali', 'Rwanda'),
    ('Gahanga International Cricket Stadium, Rwanda', 'Kigali'): ('Gahanga International Cricket Stadium, Rwanda', 'Kigali', 'Rwanda'),

    # ─── Gaddafi Stadium, Lahore (Lahore, Pakistan) ─
    ('Gaddafi Stadium, Lahore', 'Lahore'): ('Gaddafi Stadium', 'Lahore', 'Pakistan'),
    ('Gaddafi Stadium', 'Lahore'): ('Gaddafi Stadium', 'Lahore', 'Pakistan'),

    # ─── Sheikh Zayed Stadium (Abu Dhabi, United Arab Emirates) ─
    ('Sheikh Zayed Stadium', 'Abu Dhabi'): ('Sheikh Zayed Stadium', 'Abu Dhabi', 'United Arab Emirates'),
    ('Zayed Cricket Stadium, Abu Dhabi', 'Abu Dhabi'): ('Sheikh Zayed Stadium', 'Abu Dhabi', 'United Arab Emirates'),
    ('Sheikh Zayed Stadium, Abu Dhabi', 'Abu Dhabi'): ('Sheikh Zayed Stadium', 'Abu Dhabi', 'United Arab Emirates'),
    ('Zayed Cricket Stadium', 'Abu Dhabi'): ('Sheikh Zayed Stadium', 'Abu Dhabi', 'United Arab Emirates'),

    # ─── Eden Gardens, Kolkata (Kolkata, India) ─
    ('Eden Gardens', 'Kolkata'): ('Eden Gardens', 'Kolkata', 'India'),
    ('Eden Gardens, Kolkata', 'Kolkata'): ('Eden Gardens', 'Kolkata', 'India'),
    ('Eden Gardens', None): ('Eden Gardens', 'Kolkata', 'India'),

    # ─── Headingley, Leeds (Leeds, England) ─
    ('Headingley, Leeds', 'Leeds'): ('Headingley', 'Leeds', 'England'),
    ('Headingley', 'Leeds'): ('Headingley', 'Leeds', 'England'),

    # ─── Trent Bridge, Nottingham (Nottingham, England) ─
    ('Trent Bridge, Nottingham', 'Nottingham'): ('Trent Bridge', 'Nottingham', 'England'),
    ('Trent Bridge', 'Nottingham'): ('Trent Bridge', 'Nottingham', 'England'),

    # ─── Wankhede Stadium, Mumbai (Mumbai, India) ─
    ('Wankhede Stadium', 'Mumbai'): ('Wankhede Stadium', 'Mumbai', 'India'),
    ('Wankhede Stadium, Mumbai', 'Mumbai'): ('Wankhede Stadium', 'Mumbai', 'India'),
    ('Wankhede Stadium', None): ('Wankhede Stadium', 'Mumbai', 'India'),

    # Punctuation collision: "Gahanga International Cricket Stadium. Rwanda"
    # (full stop) is the same ground as the "…, Rwanda" canonical above.
    # Remap to the comma form; don't preserve the period variant as its
    # own canonical. Caught by scripts/sweep_venue_punctuation_collisions.py.
    ('Gahanga International Cricket Stadium. Rwanda', 'Kigali City'): ('Gahanga International Cricket Stadium, Rwanda', 'Kigali', 'Rwanda'),
    ('Gahanga International Cricket Stadium. Rwanda', None): ('Gahanga International Cricket Stadium, Rwanda', 'Kigali', 'Rwanda'),
    ('Gahanga International Cricket Stadium. Rwanda', 'Kigali'): ('Gahanga International Cricket Stadium, Rwanda', 'Kigali', 'Rwanda'),

    # ─── Old Trafford, Manchester (Manchester, England) ─
    ('Old Trafford, Manchester', 'Manchester'): ('Old Trafford', 'Manchester', 'England'),
    ('Old Trafford', 'Manchester'): ('Old Trafford', 'Manchester', 'England'),

    # ─── Sophia Gardens, Cardiff (Cardiff, Wales) ─
    ('Sophia Gardens, Cardiff', 'Cardiff'): ('Sophia Gardens', 'Cardiff', 'Wales'),
    ('Sophia Gardens', 'Cardiff'): ('Sophia Gardens', 'Cardiff', 'Wales'),

    # ─── Zahur Ahmed Chowdhury Stadium, Chattogram (Chattogram, Bangladesh) ─
    ('Zahur Ahmed Chowdhury Stadium, Chattogram', 'Chattogram'): ('Zahur Ahmed Chowdhury Stadium', 'Chattogram', 'Bangladesh'),
    ('Zahur Ahmed Chowdhury Stadium, Chittagong', 'Chattogram'): ('Zahur Ahmed Chowdhury Stadium', 'Chattogram', 'Bangladesh'),
    ('Zahur Ahmed Chowdhury Stadium', 'Chittagong'): ('Zahur Ahmed Chowdhury Stadium', 'Chattogram', 'Bangladesh'),
    ('Zahur Ahmed Chowdhury Stadium', 'Chattogram'): ('Zahur Ahmed Chowdhury Stadium', 'Chattogram', 'Bangladesh'),

    # ─── R Premadasa Stadium, Colombo (Colombo, Sri Lanka) ─
    ('R Premadasa Stadium, Colombo', 'Colombo'): ('R Premadasa Stadium', 'Colombo', 'Sri Lanka'),
    ('R Premadasa Stadium', 'Colombo'): ('R Premadasa Stadium', 'Colombo', 'Sri Lanka'),

    # ─── Kingsmead, Durban (Durban, South Africa) ─
    ('Kingsmead, Durban', 'Durban'): ('Kingsmead', 'Durban', 'South Africa'),
    ('Kingsmead', 'Durban'): ('Kingsmead', 'Durban', 'South Africa'),

    # ─── M Chinnaswamy Stadium, Bengaluru (Bengaluru, India) ─
    ('M Chinnaswamy Stadium', 'Bangalore'): ('M Chinnaswamy Stadium', 'Bengaluru', 'India'),
    ('M Chinnaswamy Stadium, Bengaluru', 'Bengaluru'): ('M Chinnaswamy Stadium', 'Bengaluru', 'India'),
    ('M Chinnaswamy Stadium, Bangalore', 'Bengaluru'): ('M Chinnaswamy Stadium', 'Bengaluru', 'India'),

    # ─── Hagley Oval, Christchurch (Christchurch, New Zealand) ─
    ('Hagley Oval, Christchurch', 'Christchurch'): ('Hagley Oval', 'Christchurch', 'New Zealand'),
    ('Hagley Oval', 'Christchurch'): ('Hagley Oval', 'Christchurch', 'New Zealand'),

    # ─── Bellerive Oval, Hobart (Hobart, Australia) ─
    ('Bellerive Oval, Hobart', 'Hobart'): ('Bellerive Oval', 'Hobart', 'Australia'),
    ('Bellerive Oval', 'Hobart'): ('Bellerive Oval', 'Hobart', 'Australia'),

    # ─── Feroz Shah Kotla (Delhi, India) ─
    ('Feroz Shah Kotla', 'Delhi'): ('Feroz Shah Kotla', 'Delhi', 'India'),

    # ─── Lord's, London (London, England) ─
    ("Lord's, London", 'London'): ("Lord's", 'London', 'England'),
    ("Lord's", 'London'): ("Lord's", 'London', 'England'),

    # ─── Sydney Cricket Ground (Sydney, Australia) ─
    ('Sydney Cricket Ground', 'Sydney'): ('Sydney Cricket Ground', 'Sydney', 'Australia'),
    ('Sydney Cricket Ground', None): ('Sydney Cricket Ground', 'Sydney', 'Australia'),

    # ─── Botswana Cricket Association Oval 1, Gaborone (Gaborone, Botswana) ─
    ('Botswana Cricket Association Oval 1, Gaborone', 'Gaborone'): ('Botswana Cricket Association Oval 1', 'Gaborone', 'Botswana'),
    ('Botswana Cricket Association Oval 1', 'Gaborone'): ('Botswana Cricket Association Oval 1', 'Gaborone', 'Botswana'),

    # ─── Melbourne Cricket Ground (Melbourne, Australia) ─
    ('Melbourne Cricket Ground', 'Melbourne'): ('Melbourne Cricket Ground', 'Melbourne', 'Australia'),
    ('Melbourne Cricket Ground', None): ('Melbourne Cricket Ground', 'Melbourne', 'Australia'),

    # ─── National Stadium (Karachi) (Karachi, Pakistan) ─
    ('National Stadium, Karachi', 'Karachi'): ('National Stadium (Karachi)', 'Karachi', 'Pakistan'),
    ('National Stadium', 'Karachi'): ('National Stadium (Karachi)', 'Karachi', 'Pakistan'),
    ('National Stadium (Karachi)', 'Karachi'): ('National Stadium (Karachi)', 'Karachi', 'Pakistan'),

    # ─── Marsa Sports Club (Marsa, Malta) ─
    ('Marsa Sports Club', 'Marsa'): ('Marsa Sports Club', 'Marsa', 'Malta'),

    # ─── SuperSport Park, Centurion (Centurion, South Africa) ─
    ('SuperSport Park, Centurion', 'Centurion'): ('SuperSport Park', 'Centurion', 'South Africa'),
    ('SuperSport Park', 'Centurion'): ('SuperSport Park', 'Centurion', 'South Africa'),

    # ─── Warner Park, Basseterre (Basseterre, Saint Kitts and Nevis) ─
    ('Warner Park, Basseterre, St Kitts', 'Basseterre'): ('Warner Park', 'Basseterre', 'Saint Kitts and Nevis'),
    ('Warner Park, Basseterre', 'St Kitts'): ('Warner Park', 'Basseterre', 'Saint Kitts and Nevis'),
    ('Warner Park, Basseterre', None): ('Warner Park', 'Basseterre', 'Saint Kitts and Nevis'),
    ('Warner Park, Basseterre', 'Basseterre'): ('Warner Park', 'Basseterre', 'Saint Kitts and Nevis'),

    # ─── West End Park International Cricket Stadium, Doha (Doha, Qatar) ─
    ('West End Park International Cricket Stadium, Doha', 'Doha'): ('West End Park International Cricket Stadium', 'Doha', 'Qatar'),
    ('West End Park International Cricket Stadium', 'Doha'): ('West End Park International Cricket Stadium', 'Doha', 'Qatar'),

    # ─── Newlands, Cape Town (Cape Town, South Africa) ─
    ('Newlands, Cape Town', 'Cape Town'): ('Newlands', 'Cape Town', 'South Africa'),
    ('Newlands', 'Cape Town'): ('Newlands', 'Cape Town', 'South Africa'),

    # ─── Perth Stadium (Perth, Australia) ─
    ('Perth Stadium', 'Perth'): ('Perth Stadium', 'Perth', 'Australia'),
    ('Perth Stadium', None): ('Perth Stadium', 'Perth', 'Australia'),

    # ─── County Ground (Hove) (Hove, England) ─
    ('County Ground, Hove', 'Brighton'): ('County Ground (Hove)', 'Hove', 'England'),
    ('County Ground', 'Hove'): ('County Ground (Hove)', 'Hove', 'England'),
    ('County Ground (Hove)', 'Hove'): ('County Ground (Hove)', 'Hove', 'England'),

    # ─── MA Chidambaram Stadium, Chepauk (Chennai, India) ─
    ('MA Chidambaram Stadium, Chepauk', 'Chennai'): ('MA Chidambaram Stadium, Chepauk', 'Chennai', 'India'),
    ('MA Chidambaram Stadium, Chepauk, Chennai', 'Chennai'): ('MA Chidambaram Stadium, Chepauk', 'Chennai', 'India'),
    ('MA Chidambaram Stadium', 'Chennai'): ('MA Chidambaram Stadium, Chepauk', 'Chennai', 'India'),

    # ─── Providence Stadium (Providence, Guyana) ─
    ('Providence Stadium, Guyana', 'Providence'): ('Providence Stadium', 'Providence', 'Guyana'),
    ('Providence Stadium', 'Guyana'): ('Providence Stadium', 'Providence', 'Guyana'),
    ('Providence Stadium', 'Providence'): ('Providence Stadium', 'Providence', 'Guyana'),

    # ─── Basin Reserve, Wellington (Wellington, New Zealand) ─
    ('Basin Reserve, Wellington', 'Wellington'): ('Basin Reserve', 'Wellington', 'New Zealand'),
    ('Basin Reserve', 'Wellington'): ('Basin Reserve', 'Wellington', 'New Zealand'),

    # ─── Harare Sports Club (Harare, Zimbabwe) ─
    ('Harare Sports Club', 'Harare'): ('Harare Sports Club', 'Harare', 'Zimbabwe'),
    ('Harare Sports Club', None): ('Harare Sports Club', 'Harare', 'Zimbabwe'),

    # ─── Moara Vlasiei Cricket Ground, Ilfov County (Ilfov County, Romania) ─
    ('Moara Vlasiei Cricket Ground, Ilfov County', 'Ilfov County'): ('Moara Vlasiei Cricket Ground', 'Ilfov County', 'Romania'),
    ('Moara Vlasiei Cricket Ground', None): ('Moara Vlasiei Cricket Ground', 'Ilfov County', 'Romania'),

    # ─── Queen's Park Oval, Port of Spain (Port of Spain, Trinidad and Tobago) ─
    ("Queen's Park Oval, Port of Spain", 'Trinidad'): ("Queen's Park Oval", 'Port of Spain', 'Trinidad and Tobago'),
    ("Queen's Park Oval, Port of Spain, Trinidad", 'Port of Spain'): ("Queen's Park Oval", 'Port of Spain', 'Trinidad and Tobago'),
    ("Queen's Park Oval, Port of Spain", 'Port of Spain'): ("Queen's Park Oval", 'Port of Spain', 'Trinidad and Tobago'),

    # ─── Riverside Ground, Chester-le-Street (Chester-le-Street, England) ─
    ('Riverside Ground', 'Chester-le-Street'): ('Riverside Ground', 'Chester-le-Street', 'England'),
    ('Riverside Ground, Chester-le-Street', 'Chester-le-Street'): ('Riverside Ground', 'Chester-le-Street', 'England'),

    # ─── Rajiv Gandhi International Stadium, Uppal (Hyderabad, India) ─
    ('Rajiv Gandhi International Stadium, Uppal', 'Hyderabad'): ('Rajiv Gandhi International Stadium, Uppal', 'Hyderabad', 'India'),
    ('Rajiv Gandhi International Stadium, Uppal, Hyderabad', 'Hyderabad'): ('Rajiv Gandhi International Stadium, Uppal', 'Hyderabad', 'India'),
    ('Rajiv Gandhi International Stadium', 'Hyderabad'): ('Rajiv Gandhi International Stadium, Uppal', 'Hyderabad', 'India'),

    # ─── Rawalpindi Cricket Stadium (Rawalpindi, Pakistan) ─
    ('Rawalpindi Cricket Stadium', 'Rawalpindi'): ('Rawalpindi Cricket Stadium', 'Rawalpindi', 'Pakistan'),
    ('Rawalpindi Cricket Stadium', None): ('Rawalpindi Cricket Stadium', 'Rawalpindi', 'Pakistan'),

    # ─── St George's Park, Gqeberha (Gqeberha, South Africa) ─
    ("St George's Park, Port Elizabeth", 'Port Elizabeth'): ("St George's Park", 'Gqeberha', 'South Africa'),
    ("St George's Park, Gqeberha", 'Gqeberha'): ("St George's Park", 'Gqeberha', 'South Africa'),
    ("St George's Park", 'Port Elizabeth'): ("St George's Park", 'Gqeberha', 'South Africa'),

    # ─── Brisbane Cricket Ground, Woolloongabba (Brisbane, Australia) ─
    ('Brisbane Cricket Ground, Woolloongabba', 'Brisbane'): ('Brisbane Cricket Ground, Woolloongabba', 'Brisbane', 'Australia'),
    ('Brisbane Cricket Ground, Woolloongabba, Brisbane', 'Brisbane'): ('Brisbane Cricket Ground, Woolloongabba', 'Brisbane', 'Australia'),
    ('Brisbane Cricket Ground', 'Brisbane'): ('Brisbane Cricket Ground, Woolloongabba', 'Brisbane', 'Australia'),

    # ─── Al Amerat Cricket Ground Oman Cricket (Ministry Turf 2) (Al Amerat, Oman) ─
    ('Al Amerat Cricket Ground Oman Cricket (Ministry Turf 2)', 'Al Amarat'): ('Al Amerat Cricket Ground Oman Cricket (Ministry Turf 2)', 'Al Amerat', 'Oman'),
    ('Al Amerat Cricket Ground Oman Cricket (Ministry Turf 2)', 'Al Amerat'): ('Al Amerat Cricket Ground Oman Cricket (Ministry Turf 2)', 'Al Amerat', 'Oman'),

    # ─── County Ground (Chelmsford) (Chelmsford, England) ─
    ('County Ground', 'Chelmsford'): ('County Ground (Chelmsford)', 'Chelmsford', 'England'),
    ('County Ground, Chelmsford', 'Chelmsford'): ('County Ground (Chelmsford)', 'Chelmsford', 'England'),
    ('County Ground (Chelmsford)', 'Chelmsford'): ('County Ground (Chelmsford)', 'Chelmsford', 'England'),

    # ─── Docklands Stadium, Melbourne (Melbourne, Australia) ─
    ('Docklands Stadium', 'Melbourne'): ('Docklands Stadium', 'Melbourne', 'Australia'),
    ('Docklands Stadium, Melbourne', 'Melbourne'): ('Docklands Stadium', 'Melbourne', 'Australia'),

    # ─── Entebbe Cricket Oval (Entebbe, Uganda) ─
    ('Entebbe Cricket Oval', 'Entebbe'): ('Entebbe Cricket Oval', 'Entebbe', 'Uganda'),

    # ─── Sawai Mansingh Stadium, Jaipur (Jaipur, India) ─
    ('Sawai Mansingh Stadium', 'Jaipur'): ('Sawai Mansingh Stadium', 'Jaipur', 'India'),
    ('Sawai Mansingh Stadium, Jaipur', 'Jaipur'): ('Sawai Mansingh Stadium', 'Jaipur', 'India'),

    # ─── County Ground (Northampton) (Northampton, England) ─
    ('County Ground', 'Northampton'): ('County Ground (Northampton)', 'Northampton', 'England'),
    ('County Ground, Northampton', 'Northampton'): ('County Ground (Northampton)', 'Northampton', 'England'),
    ('County Ground (Northampton)', 'Northampton'): ('County Ground (Northampton)', 'Northampton', 'England'),

    # ─── County Ground (Taunton) (Taunton, England) ─
    ('The Cooper Associates County Ground, Taunton', 'Taunton'): ('County Ground (Taunton)', 'Taunton', 'England'),
    ('The Cooper Associates County Ground', 'Taunton'): ('County Ground (Taunton)', 'Taunton', 'England'),
    ('County Ground', 'Taunton'): ('County Ground (Taunton)', 'Taunton', 'England'),
    ('County Ground, Taunton', 'Taunton'): ('County Ground (Taunton)', 'Taunton', 'England'),
    ('County Ground (Taunton)', 'Taunton'): ('County Ground (Taunton)', 'Taunton', 'England'),

    # ─── Bayer Uerdingen Cricket Ground (Krefeld, Germany) ─
    ('Bayer Uerdingen Cricket Ground', 'Krefeld'): ('Bayer Uerdingen Cricket Ground', 'Krefeld', 'Germany'),

    # ─── Senwes Park, Potchefstroom (Potchefstroom, South Africa) ─
    ('Senwes Park, Potchefstroom', 'Potchefstroom'): ('Senwes Park', 'Potchefstroom', 'South Africa'),
    ('Senwes Park', 'Potchefstroom'): ('Senwes Park', 'Potchefstroom', 'South Africa'),

    # ─── Boland Park, Paarl (Paarl, South Africa) ─
    ('Boland Park, Paarl', 'Paarl'): ('Boland Park', 'Paarl', 'South Africa'),
    ('Boland Park', 'Paarl'): ('Boland Park', 'Paarl', 'South Africa'),

    # ─── Kensington Oval, Bridgetown (Bridgetown, Barbados) ─
    ('Kensington Oval, Bridgetown', 'Barbados'): ('Kensington Oval', 'Bridgetown', 'Barbados'),
    ('Kensington Oval, Bridgetown, Barbados', 'Bridgetown'): ('Kensington Oval', 'Bridgetown', 'Barbados'),
    ('Kensington Oval, Bridgetown', 'Bridgetown'): ('Kensington Oval', 'Bridgetown', 'Barbados'),

    # ─── Arun Jaitley Stadium, Delhi (Delhi, India) ─
    ('Arun Jaitley Stadium, Delhi', 'Delhi'): ('Arun Jaitley Stadium', 'Delhi', 'India'),
    ('Arun Jaitley Stadium', None): ('Arun Jaitley Stadium', 'Delhi', 'India'),
    ('Arun Jaitley Stadium', 'Delhi'): ('Arun Jaitley Stadium', 'Delhi', 'India'),

    # ─── Botswana Cricket Association Oval 2, Gaborone (Gaborone, Botswana) ─
    ('Botswana Cricket Association Oval 2, Gaborone', 'Gaborone'): ('Botswana Cricket Association Oval 2', 'Gaborone', 'Botswana'),
    ('Botswana Cricket Association Oval 2', 'Gaborone'): ('Botswana Cricket Association Oval 2', 'Gaborone', 'Botswana'),

    # ─── County Ground (Bristol) (Bristol, England) ─
    ('County Ground', 'Bristol'): ('County Ground (Bristol)', 'Bristol', 'England'),
    ('County Ground, Bristol', 'Bristol'): ('County Ground (Bristol)', 'Bristol', 'England'),
    ('County Ground (Bristol)', 'Bristol'): ('County Ground (Bristol)', 'Bristol', 'England'),

    # ─── Narendra Modi Stadium, Ahmedabad (Ahmedabad, India) ─
    ('Narendra Modi Stadium, Ahmedabad', 'Ahmedabad'): ('Narendra Modi Stadium', 'Ahmedabad', 'India'),
    ('Narendra Modi Stadium', 'Ahmedabad'): ('Narendra Modi Stadium', 'Ahmedabad', 'India'),

    # ─── Desert Springs Cricket Ground, Almeria (Palomares, Almeria, Spain) ─
    ('Desert Springs Cricket Ground, Almeria', 'Almeria'): ('Desert Springs Cricket Ground, Almeria', 'Palomares, Almeria', 'Spain'),
    ('Desert Springs Cricket Ground, Almeria', 'Palomares, Almeria'): ('Desert Springs Cricket Ground, Almeria', 'Palomares, Almeria', 'Spain'),

    # ─── Grace Road, Leicester (Leicester, England) ─
    ('Grace Road', 'Leicester'): ('Grace Road', 'Leicester', 'England'),
    ('Grace Road, Leicester', 'Leicester'): ('Grace Road', 'Leicester', 'England'),

    # Collision with "Grand Prairie Stadium" canonical elsewhere. Same
    # ground, different city suffix — Grand Prairie is a Dallas suburb.
    # Remap to the suburb form (canonical elsewhere sets city='Grand
    # Prairie'). Caught by scripts/sweep_venue_punctuation_collisions.py.
    ('Grand Prairie Stadium, Dallas', 'Dallas'): ('Grand Prairie Stadium', 'Grand Prairie', 'USA'),

    # ─── Pallekele International Cricket Stadium (Kandy, Sri Lanka) ─
    ('Pallekele International Cricket Stadium', 'Kandy'): ('Pallekele International Cricket Stadium', 'Kandy', 'Sri Lanka'),
    ('Pallekele International Cricket Stadium', None): ('Pallekele International Cricket Stadium', 'Kandy', 'Sri Lanka'),

    # ─── New Road (Worcester) (Worcester, England) ─
    ('County Ground, New Road', 'Worcester'): ('New Road (Worcester)', 'Worcester', 'England'),
    ('County Ground, New Road, Worcester', 'Worcester'): ('New Road (Worcester)', 'Worcester', 'England'),
    ('New Road (Worcester)', 'Worcester'): ('New Road (Worcester)', 'Worcester', 'England'),

    # ─── Integrated Polytechnic Regional Centre (Kigali, Rwanda) ─
    ('Integrated Polytechnic Regional Centre', 'Kigali City'): ('Integrated Polytechnic Regional Centre', 'Kigali', 'Rwanda'),
    ('Integrated Polytechnic Regional Centre', 'Kigali'): ('Integrated Polytechnic Regional Centre', 'Kigali', 'Rwanda'),

    # ─── Mission Road Ground, Mong Kok (Mong Kok, Hong Kong) ─
    ('Mission Road Ground, Mong Kok, Hong Kong', 'Mong Kok'): ('Mission Road Ground', 'Mong Kok', 'Hong Kong'),
    ('Mission Road Ground, Mong Kok', 'Hong Kong'): ('Mission Road Ground', 'Mong Kok', 'Hong Kong'),
    ('Mission Road Ground, Mong Kok', 'Mong Kok'): ('Mission Road Ground', 'Mong Kok', 'Hong Kong'),

    # ─── St Lawrence Ground, Canterbury (Canterbury, England) ─
    ('St Lawrence Ground', 'Canterbury'): ('St Lawrence Ground', 'Canterbury', 'England'),
    ('St Lawrence Ground, Canterbury', 'Canterbury'): ('St Lawrence Ground', 'Canterbury', 'England'),

    # ─── Sydney Showground Stadium (Sydney, Australia) ─
    ('Sydney Showground Stadium', 'Sydney'): ('Sydney Showground Stadium', 'Sydney', 'Australia'),
    ('Sydney Showground Stadium', None): ('Sydney Showground Stadium', 'Sydney', 'Australia'),

    # ─── UKM-YSD Cricket Oval, Bangi (Bangi, Malaysia) ─
    ('UKM-YSD Cricket Oval, Bangi', 'Bangi'): ('UKM-YSD Cricket Oval', 'Bangi', 'Malaysia'),
    ('UKM-YSD Cricket Oval', 'Bangi'): ('UKM-YSD Cricket Oval', 'Bangi', 'Malaysia'),

    # ─── Singapore National Cricket Ground (Singapore, Singapore) ─
    ('Singapore National Cricket Ground', 'Singapore'): ('Singapore National Cricket Ground', 'Singapore', 'Singapore'),

    # ─── University Oval (Dunedin) (Dunedin, New Zealand) ─
    ('University Oval, Dunedin', 'Dunedin'): ('University Oval (Dunedin)', 'Dunedin', 'New Zealand'),
    ('University Oval', 'Dunedin'): ('University Oval (Dunedin)', 'Dunedin', 'New Zealand'),
    ('University Oval (Dunedin)', 'Dunedin'): ('University Oval (Dunedin)', 'Dunedin', 'New Zealand'),

    # ─── Wanderers Stadium (Johannesburg, South Africa) ─
    ('The Wanderers Stadium, Johannesburg', 'Johannesburg'): ('Wanderers Stadium', 'Johannesburg', 'South Africa'),
    ('New Wanderers Stadium', 'Johannesburg'): ('Wanderers Stadium', 'Johannesburg', 'South Africa'),
    ('New Wanderers Stadium, Johannesburg', 'Johannesburg'): ('Wanderers Stadium', 'Johannesburg', 'South Africa'),
    ('The Wanderers Stadium', 'Johannesburg'): ('Wanderers Stadium', 'Johannesburg', 'South Africa'),
    ('Wanderers Stadium', 'Johannesburg'): ('Wanderers Stadium', 'Johannesburg', 'South Africa'),

    # ─── County Ground (Derby) (Derby, England) ─
    ('County Ground', 'Derby'): ('County Ground (Derby)', 'Derby', 'England'),
    ('County Ground, Derby', 'Derby'): ('County Ground (Derby)', 'Derby', 'England'),
    ('County Ground (Derby)', 'Derby'): ('County Ground (Derby)', 'Derby', 'England'),

    # ─── Eden Park Outer Oval (Auckland, New Zealand) ─
    ('Eden Park Outer Oval, Auckland', 'Auckland'): ('Eden Park Outer Oval', 'Auckland', 'New Zealand'),
    ('Eden Park Outer Oval', 'Auckland'): ('Eden Park Outer Oval', 'Auckland', 'New Zealand'),

    # ─── Daren Sammy National Cricket Stadium, Gros Islet (Gros Islet, Saint Lucia) ─
    ('Daren Sammy National Cricket Stadium, Gros Islet, St Lucia', 'Gros Islet'): ('Daren Sammy National Cricket Stadium', 'Gros Islet', 'Saint Lucia'),
    ('Daren Sammy National Cricket Stadium, Gros Islet', 'St Lucia'): ('Daren Sammy National Cricket Stadium', 'Gros Islet', 'Saint Lucia'),
    ('Daren Sammy National Cricket Stadium, Gros Islet', 'Gros Islet'): ('Daren Sammy National Cricket Stadium', 'Gros Islet', 'Saint Lucia'),

    # ─── Kerava National Cricket Ground (Kerava, Finland) ─
    ('Kerava National Cricket Ground', 'Kerava'): ('Kerava National Cricket Ground', 'Kerava', 'Finland'),

    # ─── North Sydney Oval, Sydney (Sydney, Australia) ─
    ('North Sydney Oval', 'Sydney'): ('North Sydney Oval', 'Sydney', 'Australia'),
    ('North Sydney Oval, Sydney', 'Sydney'): ('North Sydney Oval', 'Sydney', 'Australia'),

    # ─── Punjab Cricket Association Stadium, Mohali (Chandigarh, India) ─
    ('Punjab Cricket Association Stadium, Mohali', 'Chandigarh'): ('Punjab Cricket Association Stadium, Mohali', 'Chandigarh', 'India'),

    # ─── Brabourne Stadium, Mumbai (Mumbai, India) ─
    ('Brabourne Stadium, Mumbai', 'Mumbai'): ('Brabourne Stadium', 'Mumbai', 'India'),
    ('Brabourne Stadium', 'Mumbai'): ('Brabourne Stadium', 'Mumbai', 'India'),

    # ─── Mahinda Rajapaksa International Cricket Stadium, Sooriyawewa (Hambantota, Sri Lanka) ─
    ('Mahinda Rajapaksa International Cricket Stadium, Sooriyawewa, Hambantota', 'Hambantota'): ('Mahinda Rajapaksa International Cricket Stadium, Sooriyawewa', 'Hambantota', 'Sri Lanka'),
    ('Mahinda Rajapaksa International Cricket Stadium, Sooriyawewa', 'Hambantota'): ('Mahinda Rajapaksa International Cricket Stadium, Sooriyawewa', 'Hambantota', 'Sri Lanka'),

    # ─── Manuka Oval, Canberra (Canberra, Australia) ─
    ('Manuka Oval', 'Canberra'): ('Manuka Oval', 'Canberra', 'Australia'),
    ('Manuka Oval, Canberra', 'Canberra'): ('Manuka Oval', 'Canberra', 'Australia'),

    # ─── Rangiri Dambulla International Stadium (Dambulla, Sri Lanka) ─
    ('Rangiri Dambulla International Stadium', 'Dambulla'): ('Rangiri Dambulla International Stadium', 'Dambulla', 'Sri Lanka'),

    # ─── Sano International Cricket Ground (Sano, Japan) ─
    ('Sano International Cricket Ground', 'Sano'): ('Sano International Cricket Ground', 'Sano', 'Japan'),
    ('Sano International Cricket Ground', None): ('Sano International Cricket Ground', 'Sano', 'Japan'),

    # ─── Seddon Park, Hamilton (Hamilton, New Zealand) ─
    ('Seddon Park', 'Hamilton'): ('Seddon Park', 'Hamilton', 'New Zealand'),
    ('Seddon Park, Hamilton', 'Hamilton'): ('Seddon Park', 'Hamilton', 'New Zealand'),

    # ─── Junction Oval, Melbourne (Melbourne, Australia) ─
    ('Junction Oval, Melbourne', 'Melbourne'): ('Junction Oval', 'Melbourne', 'Australia'),
    ('Junction Oval', 'Melbourne'): ('Junction Oval', 'Melbourne', 'Australia'),

    # ─── Sir Vivian Richards Stadium, North Sound (North Sound, Antigua and Barbuda) ─
    ('Sir Vivian Richards Stadium, North Sound, Antigua', 'North Sound'): ('Sir Vivian Richards Stadium', 'North Sound', 'Antigua and Barbuda'),
    ('Sir Vivian Richards Stadium, North Sound', 'Antigua'): ('Sir Vivian Richards Stadium', 'North Sound', 'Antigua and Barbuda'),
    ('Sir Vivian Richards Stadium, North Sound', 'North Sound'): ('Sir Vivian Richards Stadium', 'North Sound', 'Antigua and Barbuda'),

    # ─── Brian Lara Stadium, Tarouba (Tarouba, Trinidad and Tobago) ─
    ('Brian Lara Stadium, Tarouba', 'Trinidad'): ('Brian Lara Stadium', 'Tarouba', 'Trinidad and Tobago'),
    ('Brian Lara Stadium, Tarouba, Trinidad', 'Tarouba'): ('Brian Lara Stadium', 'Tarouba', 'Trinidad and Tobago'),
    ('Brian Lara Stadium, Tarouba', 'Tarouba'): ('Brian Lara Stadium', 'Tarouba', 'Trinidad and Tobago'),

    # ─── Gymkhana Club Ground (Nairobi) (Nairobi, Kenya) ─
    ('Gymkhana Club Ground, Nairobi', 'Nairobi'): ('Gymkhana Club Ground (Nairobi)', 'Nairobi', 'Kenya'),
    ('Gymkhana Club Ground', 'Nairobi'): ('Gymkhana Club Ground (Nairobi)', 'Nairobi', 'Kenya'),
    ('Gymkhana Club Ground (Nairobi)', 'Nairobi'): ('Gymkhana Club Ground (Nairobi)', 'Nairobi', 'Kenya'),

    # ─── Kinrara Academy Oval, Kuala Lumpur (Kuala Lumpur, Malaysia) ─
    ('Kinrara Academy Oval', 'Kuala Lumpur'): ('Kinrara Academy Oval', 'Kuala Lumpur', 'Malaysia'),
    ('Kinrara Academy Oval, Kuala Lumpur', 'Kuala Lumpur'): ('Kinrara Academy Oval', 'Kuala Lumpur', 'Malaysia'),

    # ─── Lalbhai Contractor Stadium (Surat, India) ─
    ('Lalbhai Contractor Stadium', None): ('Lalbhai Contractor Stadium', 'Surat', 'India'),
    ('Lalbhai Contractor Stadium', 'Surat'): ('Lalbhai Contractor Stadium', 'Surat', 'India'),

    # ─── Scott Page Field, Vinor (Prague, Czech Republic) ─
    ('Scott Page Field, Vinor', 'Prague'): ('Scott Page Field, Vinor', 'Prague', 'Czech Republic'),

    # ─── Gahanga B Ground, Rwanda (Kigali, Rwanda) ─
    ('Gahanga B Ground, Rwanda', 'Kigali City'): ('Gahanga B Ground, Rwanda', 'Kigali', 'Rwanda'),
    ('Gahanga B Ground, Rwanda', 'Kigali'): ('Gahanga B Ground, Rwanda', 'Kigali', 'Rwanda'),

    # ─── ICC Academy, Dubai (Dubai, United Arab Emirates) ─
    ('ICC Academy, Dubai', 'Dubai'): ('ICC Academy', 'Dubai', 'United Arab Emirates'),
    ('ICC Academy', 'Dubai'): ('ICC Academy', 'Dubai', 'United Arab Emirates'),

    # ─── Western Australia Cricket Association Ground, Perth (Perth, Australia) ─
    ('Western Australia Cricket Association Ground', 'Perth'): ('Western Australia Cricket Association Ground', 'Perth', 'Australia'),
    ('Western Australia Cricket Association Ground, Perth', 'Perth'): ('Western Australia Cricket Association Ground', 'Perth', 'Australia'),

    # ─── Wanderers Cricket Ground (Windhoek, Namibia) ─
    ('Wanderers Cricket Ground, Windhoek', 'Windhoek'): ('Wanderers Cricket Ground', 'Windhoek', 'Namibia'),
    ('Wanderers Cricket Ground', 'Windhoek'): ('Wanderers Cricket Ground', 'Windhoek', 'Namibia'),
    ('Wanderers', 'Windhoek'): ('Wanderers Cricket Ground', 'Windhoek', 'Namibia'),

    # ─── Bay Oval, Mount Maunganui (Mount Maunganui, New Zealand) ─
    ('Bay Oval, Mount Maunganui', 'Mount Maunganui'): ('Bay Oval', 'Mount Maunganui', 'New Zealand'),
    ('Bay Oval', 'Mount Maunganui'): ('Bay Oval', 'Mount Maunganui', 'New Zealand'),

    # ─── Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow (Lucknow, India) ─
    ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow', 'Lucknow'): ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium', 'Lucknow', 'India'),
    ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium', None): ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium', 'Lucknow', 'India'),
    ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium', 'Lucknow'): ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium', 'Lucknow', 'India'),

    # ─── Gelephu International Cricket Ground (Gelephu, Bhutan) ─
    ('Gelephu International Cricket Ground', 'Gelephu'): ('Gelephu International Cricket Ground', 'Gelephu', 'Bhutan'),

    # ─── Willowmoore Park, Benoni (Benoni, South Africa) ─
    ('Willowmoore Park, Benoni', 'Benoni'): ('Willowmoore Park', 'Benoni', 'South Africa'),
    ('Willowmoore Park', 'Benoni'): ('Willowmoore Park', 'Benoni', 'South Africa'),

    # ─── Holkar Stadium (Indore, India) ─
    ('Holkar Stadium', None): ('Holkar Stadium', 'Indore', 'India'),
    ('Holkar Stadium', 'Indore'): ('Holkar Stadium', 'Indore', 'India'),

    # ─── Sabina Park, Kingston (Kingston, Jamaica) ─
    ('Sabina Park, Kingston', 'Jamaica'): ('Sabina Park', 'Kingston', 'Jamaica'),
    ('Sabina Park, Kingston, Jamaica', 'Kingston'): ('Sabina Park', 'Kingston', 'Jamaica'),
    ('Sabina Park, Kingston', 'Kingston'): ('Sabina Park', 'Kingston', 'Jamaica'),

    # ─── St Albans Club, Buenos Aires (Buenos Aires, Argentina) ─
    ('St Albans Club, Buenos Aires', 'Buenos Aires'): ('St Albans Club', 'Buenos Aires', 'Argentina'),

    # ─── Asian Institute of Technology Ground, Bangkok (Bangkok, Thailand) ─
    ('Asian Institute of Technology Ground', 'Bangkok'): ('Asian Institute of Technology Ground', 'Bangkok', 'Thailand'),
    ('Asian Institute of Technology Ground, Bangkok', 'Bangkok'): ('Asian Institute of Technology Ground', 'Bangkok', 'Thailand'),

    # ─── Eden Park, Auckland (Auckland, New Zealand) ─
    ('Eden Park', 'Auckland'): ('Eden Park', 'Auckland', 'New Zealand'),
    ('Eden Park, Auckland', 'Auckland'): ('Eden Park', 'Auckland', 'New Zealand'),

    # ─── Mulpani Cricket Ground (Kathmandu, Nepal) ─
    ('Mulpani Cricket Ground', 'Kathmandu'): ('Mulpani Cricket Ground', 'Kathmandu', 'Nepal'),

    # ─── Buffalo Park, East London (East London, South Africa) ─
    ('Buffalo Park, East London', 'East London'): ('Buffalo Park', 'East London', 'South Africa'),
    ('Buffalo Park', 'East London'): ('Buffalo Park', 'East London', 'South Africa'),

    # ─── Karen Rolton Oval, Adelaide (Adelaide, Australia) ─
    ('Karen Rolton Oval, Adelaide', 'Adelaide'): ('Karen Rolton Oval', 'Adelaide', 'Australia'),
    ('Karen Rolton Oval', 'Adelaide'): ('Karen Rolton Oval', 'Adelaide', 'Australia'),

    # ─── Sylhet Stadium (Sylhet, Bangladesh) ─
    ('Sylhet Stadium', None): ('Sylhet Stadium', 'Sylhet', 'Bangladesh'),
    ('Sylhet Stadium', 'Sylhet'): ('Sylhet Stadium', 'Sylhet', 'Bangladesh'),

    # ─── Tafawa Balewa Square Cricket Oval, Lagos (Lagos, Nigeria) ─
    ('Tafawa Balewa Square Cricket Oval, Lagos', 'Lagos'): ('Tafawa Balewa Square Cricket Oval', 'Lagos', 'Nigeria'),
    ('Tafawa Balewa Square Cricket Oval', 'Lagos'): ('Tafawa Balewa Square Cricket Oval', 'Lagos', 'Nigeria'),

    # ─── Central Broward Regional Park Stadium Turf Ground (Lauderhill, USA) ─
    ('Central Broward Regional Park Stadium Turf Ground', 'Lauderhill'): ('Central Broward Regional Park Stadium Turf Ground', 'Lauderhill', 'USA'),
    ('Central Broward Regional Park Stadium Turf Ground, Lauderhill', 'Lauderhill'): ('Central Broward Regional Park Stadium Turf Ground', 'Lauderhill', 'USA'),

    # ─── Dr DY Patil Sports Academy, Navi Mumbai (Navi Mumbai, India) ─
    ('Dr DY Patil Sports Academy, Mumbai', 'Navi Mumbai'): ('Dr DY Patil Sports Academy', 'Navi Mumbai', 'India'),
    ('Dr DY Patil Sports Academy', 'Mumbai'): ('Dr DY Patil Sports Academy', 'Navi Mumbai', 'India'),
    ('Dr DY Patil Sports Academy, Navi Mumbai', 'Navi Mumbai'): ('Dr DY Patil Sports Academy', 'Navi Mumbai', 'India'),
    ('Dr DY Patil Sports Academy, Mumbai', 'Mumbai'): ('Dr DY Patil Sports Academy', 'Navi Mumbai', 'India'),

    # ─── Jimmy Powell Oval, Cayman Islands (George Town, Cayman Islands) ─
    ('Jimmy Powell Oval, Cayman Islands', 'George Town'): ('Jimmy Powell Oval, Cayman Islands', 'George Town', 'Cayman Islands'),

    # ─── United Cricket Club Ground, Windhoek (Windhoek, Namibia) ─
    ('United Cricket Club Ground, Windhoek', 'Windhoek'): ('United Cricket Club Ground', 'Windhoek', 'Namibia'),
    ('United Cricket Club Ground', 'Windhoek'): ('United Cricket Club Ground', 'Windhoek', 'Namibia'),

    # ─── W.A.C.A. Ground (Perth, Australia) ─
    ('W.A.C.A. Ground', 'Perth'): ('W.A.C.A. Ground', 'Perth', 'Australia'),

    # ─── Yeonhui Cricket Ground, Incheon (Incheon, South Korea) ─
    ('Yeonhui Cricket Ground', 'Incheon'): ('Yeonhui Cricket Ground', 'Incheon', 'South Korea'),
    ('Yeonhui Cricket Ground, Incheon', 'Incheon'): ('Yeonhui Cricket Ground', 'Incheon', 'South Korea'),

    # ─── Barabati Stadium, Cuttack (Cuttack, India) ─
    ('Barabati Stadium', None): ('Barabati Stadium', 'Cuttack', 'India'),
    ('Barabati Stadium', 'Cuttack'): ('Barabati Stadium', 'Cuttack', 'India'),
    ('Barabati Stadium, Cuttack', 'Cuttack'): ('Barabati Stadium', 'Cuttack', 'India'),

    # ─── C B Patel Ground (Surat, India) ─
    ('C B Patel Ground', None): ('C B Patel Ground', 'Surat', 'India'),
    ('C B Patel Ground', 'Surat'): ('C B Patel Ground', 'Surat', 'India'),

    # ─── Maharashtra Cricket Association Stadium, Pune (Pune, India) ─
    ('Maharashtra Cricket Association Stadium', 'Pune'): ('Maharashtra Cricket Association Stadium', 'Pune', 'India'),
    ('Maharashtra Cricket Association Stadium, Pune', 'Pune'): ('Maharashtra Cricket Association Stadium', 'Pune', 'India'),

    # ─── Nigeria Cricket Federation Oval 1, Abuja (Abuja, Nigeria) ─
    ('Nigeria Cricket Federation Oval 1, Abuja', 'Abuja'): ('Nigeria Cricket Federation Oval 1', 'Abuja', 'Nigeria'),

    # ─── Carrara Oval (Carrara, Australia) ─
    ('Carrara Oval', 'Carrara'): ('Carrara Oval', 'Carrara', 'Australia'),
    ('Carrara Oval', None): ('Carrara Oval', 'Carrara', 'Australia'),

    # Punctuation collision: the space-separated "ACA VDCA" variant is
    # the same ground as "ACA-VDCA" (hyphenated) elsewhere. Remap to
    # the hyphenated long-form canonical. Caught by
    # scripts/sweep_venue_punctuation_collisions.py.
    ('Dr. Y.S. Rajasekhara Reddy ACA VDCA Cricket Stadium', None): ('Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium', 'Visakhapatnam', 'India'),
    ('Dr. Y.S. Rajasekhara Reddy ACA VDCA Cricket Stadium', 'Visakhapatnam'): ('Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium', 'Visakhapatnam', 'India'),

    # ─── Queens Sports Club, Bulawayo (Bulawayo, Zimbabwe) ─
    ('Queens Sports Club, Bulawayo', 'Bulawayo'): ('Queens Sports Club', 'Bulawayo', 'Zimbabwe'),
    ('Queens Sports Club', 'Bulawayo'): ('Queens Sports Club', 'Bulawayo', 'Zimbabwe'),

    # ─── YSD-UKM Cricket Oval, Bangi (Bangi, Malaysia) ─
    ('YSD-UKM Cricket Oval, Bangi', 'Bangi'): ('YSD-UKM Cricket Oval', 'Bangi', 'Malaysia'),

    # ─── Emerald Heights International School Ground (Indore, India) ─
    (' Emerald Heights International School Ground', None): ('Emerald Heights International School Ground', 'Indore', 'India'),
    ('Emerald Heights International School Ground', 'Indore'): ('Emerald Heights International School Ground', 'Indore', 'India'),

    # ─── Achimota Senior Secondary School A Field, Accra (Accra, Ghana) ─
    ('Achimota Senior Secondary School A Field, Accra', 'Accra'): ('Achimota Senior Secondary School A Field', 'Accra', 'Ghana'),

    # ─── Allan Border Field, Brisbane (Brisbane, Australia) ─
    ('Allan Border Field, Brisbane', 'Brisbane'): ('Allan Border Field', 'Brisbane', 'Australia'),
    ('Allan Border Field', 'Brisbane'): ('Allan Border Field', 'Brisbane', 'Australia'),

    # ─── Europa Sports Complex (Gibraltar, Gibraltar) ─
    ('Europa Sports Complex', 'Gibraltar'): ('Europa Sports Complex', 'Gibraltar', 'Gibraltar'),

    # ─── Tikkurila Cricket Ground (Vantaa, Finland) ─
    ('Tikkurila Cricket Ground', 'Vantaa'): ('Tikkurila Cricket Ground', 'Vantaa', 'Finland'),

    # ─── Airforce Complex ground, Palam (Delhi, India) ─
    ('Airforce Complex ground, Palam', None): ('Airforce Complex ground, Palam', 'Delhi', 'India'),
    ('Airforce Complex ground, Palam', 'Delhi'): ('Airforce Complex ground, Palam', 'Delhi', 'India'),

    # ─── Grange Cricket Club Ground, Raeburn Place (Edinburgh, Scotland) ─
    ('Grange Cricket Club Ground, Raeburn Place, Edinburgh', 'Edinburgh'): ('Grange Cricket Club Ground, Raeburn Place', 'Edinburgh', 'Scotland'),
    ('Grange Cricket Club Ground, Raeburn Place', 'Edinburgh'): ('Grange Cricket Club Ground, Raeburn Place', 'Edinburgh', 'Scotland'),

    # ─── Selangor Turf Club, Kuala Lumpur (Kuala Lumpur, Malaysia) ─
    ('Selangor Turf Club, Kuala Lumpur', 'Kuala Lumpur'): ('Selangor Turf Club', 'Kuala Lumpur', 'Malaysia'),

    # ─── Sportpark Maarschalkerweerd, Utrecht (Utrecht, Netherlands) ─
    ('Sportpark Maarschalkerweerd, Utrecht', 'Utrecht'): ('Sportpark Maarschalkerweerd', 'Utrecht', 'Netherlands'),
    ('Sportpark Maarschalkerweerd', 'Utrecht'): ('Sportpark Maarschalkerweerd', 'Utrecht', 'Netherlands'),

    # ─── McLean Park, Napier (Napier, New Zealand) ─
    ('McLean Park, Napier', 'Napier'): ('McLean Park', 'Napier', 'New Zealand'),
    ('McLean Park', 'Napier'): ('McLean Park', 'Napier', 'New Zealand'),

    # ─── Roma Cricket Ground (Spinaceto, Italy) ─
    ('Roma Cricket Ground', 'Spinaceto'): ('Roma Cricket Ground', 'Spinaceto', 'Italy'),

    # ─── Tolerance Oval (Abu Dhabi, United Arab Emirates) ─
    ('Tolerance Oval, Abu Dhabi', 'Abu Dhabi'): ('Tolerance Oval', 'Abu Dhabi', 'United Arab Emirates'),
    ('Tolerance Oval', 'Abu Dhabi'): ('Tolerance Oval', 'Abu Dhabi', 'United Arab Emirates'),
    ('Sheikh Zayed Stadium Nursery 1', 'Abu Dhabi'): ('Tolerance Oval', 'Abu Dhabi', 'United Arab Emirates'),

    # ─── Zhejiang University of Technology Cricket Field (Hangzhou, China) ─
    ('Zhejiang University of Technology Cricket Field', 'Hangzhou'): ('Zhejiang University of Technology Cricket Field', 'Hangzhou', 'China'),

    # ─── Drummoyne Oval, Sydney (Sydney, Australia) ─
    ('Drummoyne Oval', 'Sydney'): ('Drummoyne Oval', 'Sydney', 'Australia'),
    ('Drummoyne Oval, Sydney', 'Sydney'): ('Drummoyne Oval', 'Sydney', 'Australia'),

    # ─── Multan Cricket Stadium (Multan, Pakistan) ─
    ('Multan Cricket Stadium', 'Multan'): ('Multan Cricket Stadium', 'Multan', 'Pakistan'),

    # ─── Simar Cricket Ground, Rome (Rome, Italy) ─
    ('Simar Cricket Ground, Rome', 'Rome'): ('Simar Cricket Ground', 'Rome', 'Italy'),

    # ─── VRA Ground, Amstelveen (Amstelveen, Netherlands) ─
    ('VRA Ground', 'Amstelveen'): ('VRA Ground', 'Amstelveen', 'Netherlands'),
    ('VRA Ground, Amstelveen', 'Amstelveen'): ('VRA Ground', 'Amstelveen', 'Netherlands'),

    # ─── Hurstville Oval (Sydney, Australia) ─
    ('Hurstville Oval', 'Sydney'): ('Hurstville Oval', 'Sydney', 'Australia'),

    # ─── Reliance Cricket Stadium (Vadodara, India) ─
    ('Reliance Cricket Stadium', None): ('Reliance Cricket Stadium', 'Vadodara', 'India'),
    ('Reliance Cricket Stadium', 'Vadodara'): ('Reliance Cricket Stadium', 'Vadodara', 'India'),

    # ─── Santarem Cricket Ground (Albergaria, Portugal) ─
    ('Santarem Cricket Ground', 'Albergaria'): ('Santarem Cricket Ground', 'Albergaria', 'Portugal'),

    # ─── Stadium Australia (Sydney, Australia) ─
    ('Stadium Australia', 'Sydney'): ('Stadium Australia', 'Sydney', 'Australia'),

    # ─── Westpac Stadium (Wellington, New Zealand) ─
    ('Westpac Stadium', 'Wellington'): ('Westpac Stadium', 'Wellington', 'New Zealand'),

    # ─── Amini Park, Port Moresby (Port Moresby, Papua New Guinea) ─
    ('Amini Park, Port Moresby', 'Port Moresby'): ('Amini Park', 'Port Moresby', 'Papua New Guinea'),
    ('Amini Park', 'Port Moresby'): ('Amini Park', 'Port Moresby', 'Papua New Guinea'),

    # ─── DRIEMS Ground (Cuttack, India) ─
    ('DRIEMS Ground', None): ('DRIEMS Ground', 'Cuttack', 'India'),
    ('DRIEMS Ground', 'Cuttack'): ('DRIEMS Ground', 'Cuttack', 'India'),

    # ─── Happy Valley Ground (Episkopi, Cyprus) ─
    ('Happy Valley Ground', 'Episkopi'): ('Happy Valley Ground', 'Episkopi', 'Cyprus'),

    # ─── Himachal Pradesh Cricket Association Stadium (Dharamsala, India) ─
    ('Himachal Pradesh Cricket Association Stadium', 'Dharamsala'): ('Himachal Pradesh Cricket Association Stadium', 'Dharamsala', 'India'),
    ('Himachal Pradesh Cricket Association Stadium, Dharamsala', 'Dharamsala'): ('Himachal Pradesh Cricket Association Stadium', 'Dharamsala', 'India'),
    ('Himachal Pradesh Cricket Association Stadium', 'Dharmasala'): ('Himachal Pradesh Cricket Association Stadium', 'Dharamsala', 'India'),

    # ─── Indian Association Ground, Singapore (Singapore, Singapore) ─
    ('Indian Association Ground', 'Singapore'): ('Indian Association Ground', 'Singapore', 'Singapore'),
    ('Indian Association Ground, Singapore', 'Singapore'): ('Indian Association Ground', 'Singapore', 'Singapore'),

    # ─── Kotambi Stadium, Vadodara (Vadodara, India) ─
    ('Kotambi Stadium, Vadodara', 'Vadodara'): ('Kotambi Stadium', 'Vadodara', 'India'),

    # Punctuation collision: "M.Chinnaswamy Stadium" (dot, no space after
    # M.) is the same ground as "M Chinnaswamy Stadium, Bengaluru" above.
    # Remap to the canonical house-style form (no period on initial).
    # Caught by scripts/sweep_venue_punctuation_collisions.py.
    ('M.Chinnaswamy Stadium', 'Bengaluru'): ('M Chinnaswamy Stadium', 'Bengaluru', 'India'),

    # ─── Maple Leaf North-West Ground, King City (King City, Canada) ─
    ('Maple Leaf North-West Ground, King City', 'King City'): ('Maple Leaf North-West Ground', 'King City', 'Canada'),
    ('Maple Leaf North-West Ground', 'King City'): ('Maple Leaf North-West Ground', 'King City', 'Canada'),

    # ─── Punjab Cricket Association IS Bindra Stadium, Mohali (Mohali, India) ─
    ('Punjab Cricket Association IS Bindra Stadium, Mohali', 'Chandigarh'): ('Punjab Cricket Association IS Bindra Stadium', 'Mohali', 'India'),
    ('Punjab Cricket Association IS Bindra Stadium, Mohali, Chandigarh', 'Chandigarh'): ('Punjab Cricket Association IS Bindra Stadium', 'Mohali', 'India'),
    ('Punjab Cricket Association IS Bindra Stadium', 'Chandigarh'): ('Punjab Cricket Association IS Bindra Stadium', 'Mohali', 'India'),
    ('Punjab Cricket Association IS Bindra Stadium, Mohali', 'Mohali'): ('Punjab Cricket Association IS Bindra Stadium', 'Mohali', 'India'),

    # ─── Subrata Roy Sahara Stadium (Pune, India) ─
    ('Subrata Roy Sahara Stadium', 'Pune'): ('Subrata Roy Sahara Stadium', 'Pune', 'India'),

    # ─── The Village, Malahide (Dublin, Ireland) ─
    ('The Village, Malahide', 'Dublin'): ('The Village, Malahide', 'Dublin', 'Ireland'),
    ('The Village, Malahide, Dublin', 'Dublin'): ('The Village, Malahide', 'Dublin', 'Ireland'),

    # ─── High Performance Oval, Windhoek (Windhoek, Namibia) ─
    ('High Performance Oval, Windhoek', 'Windhoek'): ('High Performance Oval', 'Windhoek', 'Namibia'),

    # ─── King George V Sports Ground, Castel (Castel, Guernsey) ─
    ('King George V Sports Ground, Castel', 'Castel'): ('King George V Sports Ground', 'Castel', 'Guernsey'),
    ('King George V Sports Ground', 'Castel'): ('King George V Sports Ground', 'Castel', 'Guernsey'),

    # ─── La Manga Club Top Ground (Murcia, Spain) ─
    ('La Manga Club Top Ground', 'Murcia'): ('La Manga Club Top Ground', 'Murcia', 'Spain'),

    # ─── Molyneux Park, Alexandra (Alexandra, New Zealand) ─
    ('Molyneux Park, Alexandra', 'Alexandra'): ('Molyneux Park', 'Alexandra', 'New Zealand'),
    ('Molyneux Park', 'Alexandra'): ('Molyneux Park', 'Alexandra', 'New Zealand'),

    # ─── National Sports Academy, Sofia (Sofia, Bulgaria) ─
    ('National Sports Academy, Sofia', 'Sofia'): ('National Sports Academy', 'Sofia', 'Bulgaria'),

    # ─── Sikh Union Club Ground, Nairobi (Nairobi, Kenya) ─
    ('Sikh Union Club Ground, Nairobi', 'Nairobi'): ('Sikh Union Club Ground', 'Nairobi', 'Kenya'),

    # ─── Achimota Senior Secondary School B Field, Accra (Accra, Ghana) ─
    ('Achimota Senior Secondary School B Field, Accra', 'Accra'): ('Achimota Senior Secondary School B Field', 'Accra', 'Ghana'),

    # ─── Beausejour Stadium, Gros Islet (St Lucia, Saint Lucia) ─
    ('Beausejour Stadium, Gros Islet', 'St Lucia'): ('Beausejour Stadium, Gros Islet', 'St Lucia', 'Saint Lucia'),

    # ─── Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium, Visakhapatnam (Visakhapatnam, India) ─
    ('Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium', 'Visakhapatnam'): ('Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium', 'Visakhapatnam', 'India'),
    ('Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium, Visakhapatnam', 'Visakhapatnam'): ('Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium', 'Visakhapatnam', 'India'),

    # ─── GMHBA Stadium, South Geelong, Victoria (Geelong, Australia) ─
    ('GMHBA Stadium, South Geelong, Victoria', 'Geelong'): ('GMHBA Stadium, South Geelong, Victoria', 'Geelong', 'Australia'),

    # ─── Happy Valley Ground 2 (Episkopi, Cyprus) ─
    ('Happy Valley Ground 2', 'Episkopi'): ('Happy Valley Ground 2', 'Episkopi', 'Cyprus'),

    # ─── Hurlingham Club Ground, Buenos Aires (Buenos Aires, Argentina) ─
    ('Hurlingham Club Ground, Buenos Aires', 'Buenos Aires'): ('Hurlingham Club Ground', 'Buenos Aires', 'Argentina'),

    # ─── La Manga Club Bottom Ground (Murcia, Spain) ─
    ('La Manga Club Bottom Ground', 'Murcia'): ('La Manga Club Bottom Ground', 'Murcia', 'Spain'),

    # ─── Pukekura Park, New Plymouth (New Plymouth, New Zealand) ─
    ('Pukekura Park, New Plymouth', 'New Plymouth'): ('Pukekura Park', 'New Plymouth', 'New Zealand'),
    ('Pukekura Park', 'New Plymouth'): ('Pukekura Park', 'New Plymouth', 'New Zealand'),

    # ─── Saurashtra Cricket Association Stadium, Rajkot (Rajkot, India) ─
    ('Saurashtra Cricket Association Stadium, Rajkot', 'Rajkot'): ('Saurashtra Cricket Association Stadium', 'Rajkot', 'India'),
    ('Saurashtra Cricket Association Stadium', 'Rajkot'): ('Saurashtra Cricket Association Stadium', 'Rajkot', 'India'),
    ('Saurashtra Cricket Association Stadium', None): ('Saurashtra Cricket Association Stadium', 'Rajkot', 'India'),

    # ─── Sportpark Het Schootsveld, Deventer (Deventer, Netherlands) ─
    ('Sportpark Het Schootsveld', 'Deventer'): ('Sportpark Het Schootsveld', 'Deventer', 'Netherlands'),
    ('Sportpark Het Schootsveld, Deventer', 'Deventer'): ('Sportpark Het Schootsveld', 'Deventer', 'Netherlands'),

    # ─── Vassil Levski National Sports Academy, Sofia (Sofia, Bulgaria) ─
    ('Vassil Levski National Sports Academy, Sofia', 'Sofia'): ('Vassil Levski National Sports Academy', 'Sofia', 'Bulgaria'),

    # ─── Airforce Complex ground, Palam II (Delhi, India) ─
    ('Airforce Complex ground, Palam II', None): ('Airforce Complex ground, Palam II', 'Delhi', 'India'),
    ('Airforce Complex ground, Palam II', 'Delhi'): ('Airforce Complex ground, Palam II', 'Delhi', 'India'),

    # ─── Church Street Park, Morrisville (Morrisville, USA) ─
    ('Church Street Park, Morrisville', 'Morrisville'): ('Church Street Park', 'Morrisville', 'USA'),
    ('Church Street Park', 'Morrisville'): ('Church Street Park', 'Morrisville', 'USA'),

    # ─── Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -DVR Ground,Mulapadu (Vijayawada, India) ─
    ('Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -DVR Ground,Mulapadu', None): ('Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -DVR Ground,Mulapadu', 'Vijayawada', 'India'),
    ('Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -DVR Ground,Mulapadu', 'Vijayawada'): ('Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -DVR Ground,Mulapadu', 'Vijayawada', 'India'),

    # ─── Namibia Cricket Ground, Windhoek (Windhoek, Namibia) ─
    ('Namibia Cricket Ground, Windhoek', 'Windhoek'): ('Namibia Cricket Ground', 'Windhoek', 'Namibia'),

    # ─── Shaheed Veer Narayan Singh International Stadium, Raipur (Raipur, India) ─
    ('Shaheed Veer Narayan Singh International Stadium', None): ('Shaheed Veer Narayan Singh International Stadium', 'Raipur', 'India'),
    ('Shaheed Veer Narayan Singh International Stadium', 'Raipur'): ('Shaheed Veer Narayan Singh International Stadium', 'Raipur', 'India'),
    ('Shaheed Veer Narayan Singh International Stadium, Raipur', 'Raipur'): ('Shaheed Veer Narayan Singh International Stadium', 'Raipur', 'India'),

    # ─── TCA Oval, Blantyre (Blantyre, Malawi) ─
    ('TCA Oval, Blantyre', 'Blantyre'): ('TCA Oval', 'Blantyre', 'Malawi'),

    # ─── Cricket Stadium, Sector-16 (Chandigarh, India) ─
    ('Cricket Stadium, Sector-16', None): ('Cricket Stadium, Sector-16', 'Chandigarh', 'India'),
    ('Cricket Stadium, Sector-16', 'Chandigarh'): ('Cricket Stadium, Sector-16', 'Chandigarh', 'India'),

    # ─── Diamond Oval, Kimberley (Kimberley, South Africa) ─
    ('Diamond Oval, Kimberley', 'Kimberley'): ('Diamond Oval', 'Kimberley', 'South Africa'),

    # ─── GB Oval, Szodliget (Szodliget, Hungary) ─
    ('GB Oval, Szodliget', 'Szodliget'): ('GB Oval', 'Szodliget', 'Hungary'),

    # ─── Greenfield Stadium (Thiruvananthapuram, India) ─
    ('Greenfield Stadium', None): ('Greenfield Stadium', 'Thiruvananthapuram', 'India'),
    ('Greenfield Stadium', 'Thiruvananthapuram'): ('Greenfield Stadium', 'Thiruvananthapuram', 'India'),

    # ─── Guernsey Rovers Athletic Club Ground, Port Soif (Port Soif, Guernsey) ─
    ('Guernsey Rovers Athletic Club Ground, Port Soif', 'Port  Soif'): ('Guernsey Rovers Athletic Club Ground', 'Port Soif', 'Guernsey'),
    ('Guernsey Rovers Athletic Club Ground, Port Soif', 'Port Soif'): ('Guernsey Rovers Athletic Club Ground', 'Port Soif', 'Guernsey'),

    # ─── Holkar Cricket Stadium, Indore (Indore, India) ─
    ('Holkar Cricket Stadium, Indore', 'Indore'): ('Holkar Cricket Stadium', 'Indore', 'India'),
    ('Holkar Cricket Stadium', 'Indore'): ('Holkar Cricket Stadium', 'Indore', 'India'),

    # ─── JSCA International Stadium Complex, Ranchi (Ranchi, India) ─
    ('JSCA International Stadium Complex, Ranchi', 'Ranchi'): ('JSCA International Stadium Complex', 'Ranchi', 'India'),
    ('JSCA International Stadium Complex', None): ('JSCA International Stadium Complex', 'Ranchi', 'India'),
    ('JSCA International Stadium Complex', 'Ranchi'): ('JSCA International Stadium Complex', 'Ranchi', 'India'),

    # ─── Jawaharlal Nehru Stadium (Kochi, India) ─
    ('Jawaharlal Nehru Stadium', None): ('Jawaharlal Nehru Stadium', 'Kochi', 'India'),
    ('Jawaharlal Nehru Stadium', 'Kochi'): ('Jawaharlal Nehru Stadium', 'Kochi', 'India'),

    # ─── Motibaug Cricket Ground (Vadodara, India) ─
    ('Motibaug Cricket Ground', None): ('Motibaug Cricket Ground', 'Vadodara', 'India'),
    ('Motibaug Cricket Ground', 'Vadodara'): ('Motibaug Cricket Ground', 'Vadodara', 'India'),

    # ─── Sardar Patel Stadium, Motera (Ahmedabad, India) ─
    ('Sardar Patel Stadium, Motera', 'Ahmedabad'): ('Sardar Patel Stadium, Motera', 'Ahmedabad', 'India'),

    # ─── Saxton Oval, Nelson (Nelson, New Zealand) ─
    ('Saxton Oval, Nelson', 'Nelson'): ('Saxton Oval', 'Nelson', 'New Zealand'),
    ('Saxton Oval', 'Nelson'): ('Saxton Oval', 'Nelson', 'New Zealand'),

    # ─── Takashinga Sports Club (Harare, Zimbabwe) ─
    ('Takashinga Sports Club, Highfield, Harare', 'Harare'): ('Takashinga Sports Club', 'Harare', 'Zimbabwe'),
    ('Takashinga Sports Club', 'Harare'): ('Takashinga Sports Club', 'Harare', 'Zimbabwe'),

    # ─── University of Doha for Science and Technology (Doha, Qatar) ─
    ('University of Doha for Science and Technology', 'Doha'): ('University of Doha for Science and Technology', 'Doha', 'Qatar'),

    # ─── Vidarbha Cricket Association Stadium, Jamtha (Nagpur, India) ─
    ('Vidarbha Cricket Association Stadium, Jamtha', 'Nagpur'): ('Vidarbha Cricket Association Stadium, Jamtha', 'Nagpur', 'India'),
    ('Vidarbha Cricket Association Stadium, Jamtha', None): ('Vidarbha Cricket Association Stadium, Jamtha', 'Nagpur', 'India'),
    ('Vidarbha Cricket Association Stadium, Jamtha, Nagpur', 'Nagpur'): ('Vidarbha Cricket Association Stadium, Jamtha', 'Nagpur', 'India'),

    # ─── Albert Park 1, Suva (Suva, Fiji) ─
    ('Albert Park 1, Suva', 'Suva'): ('Albert Park 1', 'Suva', 'Fiji'),
    ('Albert Park 1', 'Suva'): ('Albert Park 1', 'Suva', 'Fiji'),

    # ─── BKC Ground (Mumbai, India) ─
    ('BKC Ground', None): ('BKC Ground', 'Mumbai', 'India'),
    ('BKC Ground', 'Mumbai'): ('BKC Ground', 'Mumbai', 'India'),

    # ─── College Ground, Cheltenham (Cheltenham, England) ─
    ('College Ground', 'Cheltenham'): ('College Ground', 'Cheltenham', 'England'),
    ('College Ground, Cheltenham', 'Cheltenham'): ('College Ground', 'Cheltenham', 'England'),

    # ─── Coolidge Cricket Ground, Antigua (Coolidge, Antigua and Barbuda) ─
    ('Coolidge Cricket Ground, Antigua', 'Coolidge'): ('Coolidge Cricket Ground, Antigua', 'Coolidge', 'Antigua and Barbuda'),

    # ─── Dr P.V.G. Raju ACA Sports Complex (Vizianagaram, India) ─
    ('Dr P.V.G. Raju ACA Sports Complex', None): ('Dr P.V.G. Raju ACA Sports Complex', 'Vizianagaram', 'India'),
    ('Dr P.V.G. Raju ACA Sports Complex', 'Vizianagaram'): ('Dr P.V.G. Raju ACA Sports Complex', 'Vizianagaram', 'India'),

    # ─── Faleata Oval No 2, Apia (Apia, Samoa) ─
    ('Faleata Oval No 2, Apia', 'Apia'): ('Faleata Oval No 2', 'Apia', 'Samoa'),

    # ─── GSSS, Sector 26 (Chandigarh, India) ─
    ('GSSS, Sector 26', None): ('GSSS, Sector 26', 'Chandigarh', 'India'),
    ('GSSS, Sector 26', 'Chandigarh'): ('GSSS, Sector 26', 'Chandigarh', 'India'),

    # ─── Galle International Stadium (Galle, Sri Lanka) ─
    ('Galle International Stadium', None): ('Galle International Stadium', 'Galle', 'Sri Lanka'),
    ('Galle International Stadium', 'Galle'): ('Galle International Stadium', 'Galle', 'Sri Lanka'),

    # ─── Haslegrave Ground, Loughborough (Loughborough, England) ─
    ('Haslegrave Ground, Loughborough', 'Loughborough'): ('Haslegrave Ground', 'Loughborough', 'England'),
    ('Haslegrave Ground', 'Loughborough'): ('Haslegrave Ground', 'Loughborough', 'England'),

    # ─── Hazelaarweg, Rotterdam (Rotterdam, Netherlands) ─
    ('Hazelaarweg, Rotterdam', 'Rotterdam'): ('Hazelaarweg', 'Rotterdam', 'Netherlands'),
    ('Hazelaarweg', 'Rotterdam'): ('Hazelaarweg', 'Rotterdam', 'Netherlands'),

    # ─── John Davies Oval, Queenstown (Queenstown, New Zealand) ─
    ('John Davies Oval, Queenstown', 'Queenstown'): ('John Davies Oval', 'Queenstown', 'New Zealand'),

    # ─── White Hill Field, Sandys Parish (Hamilton, New Zealand) ─
    ('White Hill Field, Sandys Parish', 'Hamilton'): ('White Hill Field, Sandys Parish', 'Hamilton', 'New Zealand'),

    # ─── Woodley Cricket Field, Los Angeles (Los Angeles, USA) ─
    ('Woodley Cricket Field, Los Angeles', 'Los Angeles'): ('Woodley Cricket Field', 'Los Angeles', 'USA'),

    # ─── YMCA Cricket Club (Dublin, Ireland) ─
    ('YMCA Cricket Club', 'Dublin'): ('YMCA Cricket Club', 'Dublin', 'Ireland'),

    # ─── Aurora Stadium, Launceston (Launceston, Australia) ─
    ('Aurora Stadium', 'Launceston'): ('Aurora Stadium', 'Launceston', 'Australia'),
    ('Aurora Stadium, Launceston', 'Launceston'): ('Aurora Stadium', 'Launceston', 'Australia'),

    # ─── Barsapara Cricket Stadium, Guwahati (Guwahati, India) ─
    ('Barsapara Cricket Stadium, Guwahati', 'Guwahati'): ('Barsapara Cricket Stadium', 'Guwahati', 'India'),
    ('ACA Stadium, Barsapara', None): ('Barsapara Cricket Stadium', 'Guwahati', 'India'),
    ('Barsapara Cricket Stadium', 'Guwahati'): ('Barsapara Cricket Stadium', 'Guwahati', 'India'),

    # ─── Blacktown International Sportspark, Sydney (Sydney, Australia) ─
    ('Blacktown International Sportspark', 'Sydney'): ('Blacktown International Sportspark', 'Sydney', 'Australia'),
    ('Blacktown International Sportspark, Sydney', 'Sydney'): ('Blacktown International Sportspark', 'Sydney', 'Australia'),

    # ─── Civil Service Cricket Club, Stormont (Belfast, Ireland) ─
    ('Civil Service Cricket Club, Stormont', 'Belfast'): ('Civil Service Cricket Club, Stormont', 'Belfast', 'Ireland'),
    ('Civil Service Cricket Club, Stormont, Belfast', 'Belfast'): ('Civil Service Cricket Club, Stormont', 'Belfast', 'Ireland'),

    # ─── Friendship Oval (Dasmarinas, Philippines) ─
    ('Friendship Oval', 'Dasmarinas'): ('Friendship Oval', 'Dasmarinas', 'Philippines'),

    # ─── Grand Prairie Stadium (Grand Prairie, USA) ─
    ('Grand Prairie Stadium', 'Dallas'): ('Grand Prairie Stadium', 'Grand Prairie', 'USA'),
    ('Grand Prairie Stadium', 'Grand Prairie'): ('Grand Prairie Stadium', 'Grand Prairie', 'USA'),

    # ─── ICC Academy Ground No 2, Dubai (Dubai, United Arab Emirates) ─
    ('ICC Academy Ground No 2', 'Dubai'): ('ICC Academy Ground No 2', 'Dubai', 'United Arab Emirates'),
    ('ICC Academy Ground No 2, Dubai', 'Dubai'): ('ICC Academy Ground No 2', 'Dubai', 'United Arab Emirates'),

    # ─── Mangaung Oval, Bloemfontein (Bloemfontein, South Africa) ─
    ('Mangaung Oval, Bloemfontein', 'Bloemfontein'): ('Mangaung Oval', 'Bloemfontein', 'South Africa'),
    ('Mangaung Oval', 'Bloemfontein'): ('Mangaung Oval', 'Bloemfontein', 'South Africa'),

    # ─── Ray Mitchell Oval, Harrup Park, Mackay (Mackay, Australia) ─
    ('Ray Mitchell Oval, Harrup Park, Mackay', 'Mackay'): ('Ray Mitchell Oval, Harrup Park', 'Mackay', 'Australia'),

    # ─── Reforma Athletic Club, Naucalpan (Naucalpan, Mexico) ─
    ('Reforma Athletic Club, Naucalpan', 'Naucalpan'): ('Reforma Athletic Club', 'Naucalpan', 'Mexico'),

    # ─── Sportpark Westvliet, Voorburg (The Hague, Netherlands) ─
    ('Sportpark Westvliet, Voorburg', 'The Hague'): ('Sportpark Westvliet, Voorburg', 'The Hague', 'Netherlands'),
    ('Sportpark Westvliet, The Hague', 'The Hague'): ('Sportpark Westvliet, Voorburg', 'The Hague', 'Netherlands'),
    ('Sportpark Westvliet', 'The Hague'): ('Sportpark Westvliet, Voorburg', 'The Hague', 'Netherlands'),

    # ─── Stars Arena Hofstade, Zemst (Zemst, Belgium) ─
    ('Stars Arena Hofstade, Zemst', 'Zemst'): ('Stars Arena Hofstade', 'Zemst', 'Belgium'),

    # ─── Svanholm Park, Brondby (Brondby, Denmark) ─
    ('Svanholm Park, Brondby', 'Brondby'): ('Svanholm Park', 'Brondby', 'Denmark'),

    # ─── Abhimanyu Cricket Academy, Dehradun (Dehra Dun, India) ─
    ('Abhimanyu Cricket Academy, Dehradun', 'Dehra Dun'): ('Abhimanyu Cricket Academy, Dehradun', 'Dehra Dun', 'India'),

    # ─── Belgrano Athletic Club Ground, Buenos Aires (Buenos Aires, Argentina) ─
    ('Belgrano Athletic Club Ground, Buenos Aires', 'Buenos Aires'): ('Belgrano Athletic Club Ground', 'Buenos Aires', 'Argentina'),

    # ─── Centre for Cricket Development Ground, Windhoek (Windhoek, Namibia) ─
    ('Centre for Cricket Development Ground, Windhoek', 'Windhoek'): ('Centre for Cricket Development Ground', 'Windhoek', 'Namibia'),

    # ─── Chevrolet Park, Bloemfontein (Bloemfontein, South Africa) ─
    ('Chevrolet Park, Bloemfontein', 'Bloemfontein'): ('Chevrolet Park', 'Bloemfontein', 'South Africa'),

    # ─── Estonian National Cricket and Rugby Field (Tallinn, Estonia) ─
    ('Estonian National Cricket and Rugby Field', 'Tallinn'): ('Estonian National Cricket and Rugby Field', 'Tallinn', 'Estonia'),

    # ─── Fitzherbert Park, Palmerston North (Palmerston North, New Zealand) ─
    ('Fitzherbert Park, Palmerston North', 'Palmerston North'): ('Fitzherbert Park', 'Palmerston North', 'New Zealand'),

    # ─── Forthill (Dundee, Scotland) ─
    ('Forthill', 'Dundee'): ('Forthill', 'Dundee', 'Scotland'),

    # ─── Gokaraju Liala Gangaaraju ACA Cricket Ground (Vijayawada, India) ─
    ('Gokaraju Liala Gangaaraju ACA Cricket Ground', None): ('Gokaraju Liala Gangaaraju ACA Cricket Ground', 'Vijayawada', 'India'),
    ('Gokaraju Liala Gangaaraju ACA Cricket Ground', 'Vijayawada'): ('Gokaraju Liala Gangaaraju ACA Cricket Ground', 'Vijayawada', 'India'),

    # ─── Independence Park, Port Vila (Port Vila, Vanuatu) ─
    ('Independence Park, Port Vila', 'Port Vila'): ('Independence Park', 'Port Vila', 'Vanuatu'),

    # ─── Ishoj Cricket Club, Vejledalen (Ishoj, Denmark) ─
    ('Ishoj Cricket Club, Vejledalen', 'Ishoj'): ('Ishoj Cricket Club, Vejledalen', 'Ishoj', 'Denmark'),

    # ─── Lilac Hill Park, Perth (Perth, Australia) ─
    ('Lilac Hill Park', 'Perth'): ('Lilac Hill Park', 'Perth', 'Australia'),
    ('Lilac Hill Park, Perth', 'Perth'): ('Lilac Hill Park', 'Perth', 'Australia'),

    # ─── Lisicji Jarak Cricket Ground (Belgrade, Serbia) ─
    ('Lisicji Jarak Cricket Ground', 'Belgrade'): ('Lisicji Jarak Cricket Ground', 'Belgrade', 'Serbia'),

    # ─── National Cricket Stadium, St George's (St George's, Grenada) ─
    ("National Cricket Stadium, St George's, Grenada", "St George's"): ("National Cricket Stadium", "St George's", 'Grenada'),
    ("National Cricket Stadium, St George's", 'Grenada'): ("National Cricket Stadium", "St George's", 'Grenada'),
    ("National Cricket Stadium, St George's", "St George's"): ("National Cricket Stadium", "St George's", 'Grenada'),

    # ─── Pierre Werner Cricket Ground (Walferdange, Luxembourg) ─
    ('Pierre Werner Cricket Ground', 'Walferdange'): ('Pierre Werner Cricket Ground', 'Walferdange', 'Luxembourg'),

    # ─── R.Premadasa Stadium, Khettarama (Colombo, Sri Lanka) ─
    ('R.Premadasa Stadium, Khettarama', 'Colombo'): ('R.Premadasa Stadium, Khettarama', 'Colombo', 'Sri Lanka'),

    # ─── Royal Brussels Cricket Club Ground, Waterloo (Waterloo, Belgium) ─
    ('Royal Brussels Cricket Club Ground, Waterloo', 'Waterloo'): ('Royal Brussels Cricket Club Ground', 'Waterloo', 'Belgium'),

    # ─── Sharad Pawar Cricket Academy BKC (Mumbai, India) ─
    ('Sharad Pawar Cricket Academy BKC', None): ('Sharad Pawar Cricket Academy BKC', 'Mumbai', 'India'),
    ('Sharad Pawar Cricket Academy BKC', 'Mumbai'): ('Sharad Pawar Cricket Academy BKC', 'Mumbai', 'India'),

    # ─── Vanuatu Cricket Ground (Port Vila, Vanuatu) ─
    ('Vanuatu Cricket Ground', 'Port Vila'): ('Vanuatu Cricket Ground', 'Port Vila', 'Vanuatu'),

    # ─── Albert Park 2, Suva (Suva, Fiji) ─
    ('Albert Park 2, Suva', 'Suva'): ('Albert Park 2', 'Suva', 'Fiji'),
    ('Albert Park 2', 'Suva'): ('Albert Park 2', 'Suva', 'Fiji'),

    # ─── Arnos Vale Ground, Kingstown (Kingstown, Saint Vincent and the Grenadines) ─
    ('Arnos Vale Ground, Kingstown, St Vincent', 'Kingstown'): ('Arnos Vale Ground', 'Kingstown', 'Saint Vincent and the Grenadines'),
    ('Arnos Vale Ground, Kingstown', 'St Vincent'): ('Arnos Vale Ground', 'Kingstown', 'Saint Vincent and the Grenadines'),
    ('Arnos Vale Ground, Kingstown', 'Kingstown'): ('Arnos Vale Ground', 'Kingstown', 'Saint Vincent and the Grenadines'),

    # ─── Bready Cricket Club, Magheramason (Bready, Ireland) ─
    ('Bready Cricket Club, Magheramason, Bready', 'Bready'): ('Bready Cricket Club, Magheramason', 'Bready', 'Ireland'),
    ('Bready Cricket Club, Magheramason', 'Londonderry'): ('Bready Cricket Club, Magheramason', 'Bready', 'Ireland'),
    ('Bready', 'Derry'): ('Bready Cricket Club, Magheramason', 'Bready', 'Ireland'),
    ('Bready Cricket Club, Magheramason', 'Bready'): ('Bready Cricket Club, Magheramason', 'Bready', 'Ireland'),

    # ─── Bulawayo Athletic Club (Bulawayo, Zimbabwe) ─
    ('Bulawayo Athletic Club', 'Bulawayo'): ('Bulawayo Athletic Club', 'Bulawayo', 'Zimbabwe'),

    # ─── Gymkhana Club Ground (Dar-es-Salaam) (Dar-es-Salaam, Tanzania) ─
    ('Gymkhana Club Ground, Dar-es-Salaam', 'Dar-es-Salaam'): ('Gymkhana Club Ground (Dar-es-Salaam)', 'Dar-es-Salaam', 'Tanzania'),
    ('Gymkhana Club Ground (Dar-es-Salaam)', 'Dar-es-Salaam'): ('Gymkhana Club Ground (Dar-es-Salaam)', 'Dar-es-Salaam', 'Tanzania'),

    # ─── JU Second Campus, Salt Lake (Kolkata, India) ─
    ('JU Second Campus, Salt Lake', None): ('JU Second Campus, Salt Lake', 'Kolkata', 'India'),
    ('JU Second Campus, Salt Lake', 'Kolkata'): ('JU Second Campus, Salt Lake', 'Kolkata', 'India'),

    # ─── Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur (New Chandigarh, India) ─
    ('Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur', 'Mohali'): ('Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur', 'New Chandigarh', 'India'),
    ('Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur', 'New Chandigarh'): ('Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur', 'New Chandigarh', 'India'),

    # ─── Marina Ground, Corfu (Corfu, Greece) ─
    ('Marina Ground, Corfu', 'Corfu'): ('Marina Ground', 'Corfu', 'Greece'),

    # ─── Mladost Cricket Ground, Zagreb (Zagreb, Croatia) ─
    ('Mladost Cricket Ground, Zagreb', 'Zagreb'): ('Mladost Cricket Ground', 'Zagreb', 'Croatia'),

    # ─── Oakland Coliseum,Oakland (Oakland, USA) ─
    ('Oakland Coliseum,Oakland', 'Oakland'): ('Oakland Coliseum,Oakland', 'Oakland', 'USA'),

    # ─── St George's College Ground, Buenos Aires (Buenos Aires, Argentina) ─
    ("St George's College Ground, Buenos Aires", 'Buenos Aires'): ("St George's College Ground", 'Buenos Aires', 'Argentina'),

    # ─── Tack-Tec Ground (Kuwait City, Kuwait) ─
    ('Tack-Tec Ground', 'Kuwait City'): ('Tack-Tec Ground', 'Kuwait City', 'Kuwait'),

    # ─── Velden Cricket Ground, Latschach (Latschach, Austria) ─
    ('Velden Cricket Ground, Latschach', 'Latschach'): ('Velden Cricket Ground', 'Latschach', 'Austria'),

    # ─── Goldenacre, Edinburgh (Edinburgh, Scotland) ─
    ('Goldenacre, Edinburgh', 'Edinburgh'): ('Goldenacre', 'Edinburgh', 'Scotland'),
    ('Goldenacre', 'Edinburgh'): ('Goldenacre', 'Edinburgh', 'Scotland'),

    # ─── Grainville, St Saviour (St Saviour, Jersey) ─
    ('Grainville, St Saviour, Jersey', 'St Saviour'): ('Grainville', 'St Saviour', 'Jersey'),
    ('Grainville, St Saviour', 'St Saviour'): ('Grainville', 'St Saviour', 'Jersey'),

    # ─── Gurugram Cricket Ground (SRNCC) (Gurugram, India) ─
    ('Gurugram Cricket Ground (SRNCC)', None): ('Gurugram Cricket Ground (SRNCC)', 'Gurugram', 'India'),
    ('Gurugram Cricket Ground (SRNCC)', 'Gurugram'): ('Gurugram Cricket Ground (SRNCC)', 'Gurugram', 'India'),

    # ─── Hong Kong Cricket Club (Wong Nai Chung Gap, Hong Kong) ─
    ('Hong Kong Cricket Club', 'Wong Nai Chung Gap'): ('Hong Kong Cricket Club', 'Wong Nai Chung Gap', 'Hong Kong'),
    ('Hong Kong Cricket Club', None): ('Hong Kong Cricket Club', 'Wong Nai Chung Gap', 'Hong Kong'),

    # ─── Nassau County International Cricket Stadium, New York (New York, USA) ─
    ('Nassau County International Cricket Stadium, New York', 'New York'): ('Nassau County International Cricket Stadium', 'New York', 'USA'),

    # ─── Old Hararians (Harare, Zimbabwe) ─
    ('Old Hararians', 'Harare'): ('Old Hararians', 'Harare', 'Zimbabwe'),

    # ─── Pembroke Cricket Club, Sandymount (Dublin, Ireland) ─
    ('Pembroke Cricket Club, Sandymount, Dublin', 'Dublin'): ('Pembroke Cricket Club, Sandymount', 'Dublin', 'Ireland'),
    ('Pembroke Cricket Club, Sandymount', 'Dublin'): ('Pembroke Cricket Club, Sandymount', 'Dublin', 'Ireland'),

    # ─── Sinhalese Sports Club Ground, Colombo (Colombo, Sri Lanka) ─
    ('Sinhalese Sports Club Ground, Colombo', 'Colombo'): ('Sinhalese Sports Club Ground', 'Colombo', 'Sri Lanka'),
    ('Sinhalese Sports Club Ground', 'Colombo'): ('Sinhalese Sports Club Ground', 'Colombo', 'Sri Lanka'),

    # ─── Sulabiya Ground (Kuwait City, Kuwait) ─
    ('Sulabiya Ground', 'Kuwait City'): ('Sulabiya Ground', 'Kuwait City', 'Kuwait'),

    # ─── University of Dar-es-Salaam Ground (Dar-es-Salaam, Tanzania) ─
    ('University of Dar-es-Salaam Ground', 'Dar-es-Salaam'): ('University of Dar-es-Salaam Ground', 'Dar-es-Salaam', 'Tanzania'),

    # ─── University of Lagos Cricket Oval (Lagos, Nigeria) ─
    ('University of Lagos Cricket Oval', 'Lagos'): ('University of Lagos Cricket Oval', 'Lagos', 'Nigeria'),

    # ─── Vanuatu Cricket Ground (Oval 2) (Port Vila, Vanuatu) ─
    ('Vanuatu Cricket Ground (Oval 2)', 'Port Vila'): ('Vanuatu Cricket Ground (Oval 2)', 'Port Vila', 'Vanuatu'),

    # ─── ACA Stadium,Mangalagiri (Mangalagiri, India) ─
    ('ACA Stadium,Mangalagiri', None): ('ACA Stadium,Mangalagiri', 'Mangalagiri', 'India'),
    ('ACA Stadium,Mangalagiri', 'Mangalagiri'): ('ACA Stadium,Mangalagiri', 'Mangalagiri', 'India'),

    # ─── Castle Avenue, Dublin (Dublin, Ireland) ─
    ('Castle Avenue, Dublin', 'Dublin'): ('Castle Avenue', 'Dublin', 'Ireland'),

    # ─── Clayton Panama, Panama City (Panama City, Panama) ─
    ('Clayton Panama, Panama City', 'Panama City'): ('Clayton Panama', 'Panama City', 'Panama'),

    # ─── Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -CP Ground,Mulapadu (Vijayawada, India) ─
    ('Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -CP Ground,Mulapadu', None): ('Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -CP Ground,Mulapadu', 'Vijayawada', 'India'),
    ('Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -CP Ground,Mulapadu', 'Vijayawada'): ('Dr. Gokaraju Laila Ganga Raju ACA Cricket Complex -CP Ground,Mulapadu', 'Vijayawada', 'India'),

    # ─── Dreux Sport Cricket Club (Dreux, France) ─
    ('Dreux Sport Cricket Club', 'Dreux'): ('Dreux Sport Cricket Club', 'Dreux', 'France'),

    # ─── Great Barrier Reef Arena, Mackay (Mackay, Australia) ─
    ('Great Barrier Reef Arena, Mackay', 'Mackay'): ('Great Barrier Reef Arena', 'Mackay', 'Australia'),

    # ─── Lochlands (Arbroath, Scotland) ─
    ('Lochlands', 'Arbroath'): ('Lochlands', 'Arbroath', 'Scotland'),

    # ─── MA Aziz Stadium, Chittagong (Chattogram, Bangladesh) ─
    ('MA Aziz Stadium, Chittagong', 'Chattogram'): ('MA Aziz Stadium, Chittagong', 'Chattogram', 'Bangladesh'),

    # ─── Old Deer Park (Richmond, England) ─
    ('Old Deer Park', 'Richmond'): ('Old Deer Park', 'Richmond', 'England'),

    # ─── Prairie View Cricket Complex (Houston, USA) ─
    ('Prairie View Cricket Complex', 'Houston'): ('Prairie View Cricket Complex', 'Houston', 'USA'),

    # ─── Queen's Park (Chesterfield) (Chesterfield, England) ─
    ("Queen's Park", 'Chesterfield'): ("Queen's Park (Chesterfield)", 'Chesterfield', 'England'),
    ("Queen's Park, Chesterfield", 'Chesterfield'): ("Queen's Park (Chesterfield)", 'Chesterfield', 'England'),
    ("Queen's Park (Chesterfield)", 'Chesterfield'): ("Queen's Park (Chesterfield)", 'Chesterfield', 'England'),

    # ─── Radlett Cricket Club, Radlett (Radlett, England) ─
    ('Radlett Cricket Club, Radlett', 'Radlett'): ('Radlett Cricket Club', 'Radlett', 'England'),
    ('Radlett Cricket Club', 'Radlett'): ('Radlett Cricket Club', 'Radlett', 'England'),

    # ─── Sheikh Abu Naser Stadium, Khulna (Khulna, Bangladesh) ─
    ('Sheikh Abu Naser Stadium, Khulna', 'Khulna'): ('Sheikh Abu Naser Stadium', 'Khulna', 'Bangladesh'),
    ('Sheikh Abu Naser Stadium', 'Khulna'): ('Sheikh Abu Naser Stadium', 'Khulna', 'Bangladesh'),

    # ─── St Pauls college ground Kalamassery (Kochi, India) ─
    ('St  Pauls college ground  Kalamassery', None): ('St Pauls college ground Kalamassery', 'Kochi', 'India'),
    ('St Pauls college ground Kalamassery', 'Kochi'): ('St Pauls college ground Kalamassery', 'Kochi', 'India'),

    # ─── St'Xavier's KCA Cricket Ground (Thiruvananthapuram, India) ─
    ("St'Xavier's KCA Cricket Ground", None): ("St'Xavier's KCA Cricket Ground", 'Thiruvananthapuram', 'India'),
    ("St'Xavier's KCA Cricket Ground", 'Thiruvananthapuram'): ("St'Xavier's KCA Cricket Ground", 'Thiruvananthapuram', 'India'),

    # ─── Stanley Park, Blackpool (Blackpool, England) ─
    ('Stanley Park, Blackpool', 'Blackpool'): ('Stanley Park', 'Blackpool', 'England'),

    # ─── VCA Ground (Nagpur, India) ─
    ('VCA Ground', None): ('VCA Ground', 'Nagpur', 'India'),
    ('VCA Ground', 'Nagpur'): ('VCA Ground', 'Nagpur', 'India'),

    # ─── Woodbridge Road, Guildford (Guildford, England) ─
    ('Woodbridge Road, Guildford', 'Guildford'): ('Woodbridge Road', 'Guildford', 'England'),

    # ─── Alembic 2 Cricket Ground (Vadodara, India) ─
    ('Alembic 2  Cricket Ground', None): ('Alembic 2 Cricket Ground', 'Vadodara', 'India'),
    ('Alembic 2 Cricket Ground', 'Vadodara'): ('Alembic 2 Cricket Ground', 'Vadodara', 'India'),

    # ─── Bir Sreshtho Flight Lieutenant Matiur Rahman Stadium, Chattogram (Chattogram, Bangladesh) ─
    ('Bir Sreshtho Flight Lieutenant Matiur Rahman Stadium, Chattogram', 'Chattogram'): ('Bir Sreshtho Flight Lieutenant Matiur Rahman Stadium', 'Chattogram', 'Bangladesh'),

    # ─── Botkyrka Cricket Center, Stockholm (Stockholm, Sweden) ─
    ('Botkyrka Cricket Center, Stockholm', 'Stockholm'): ('Botkyrka Cricket Center', 'Stockholm', 'Sweden'),

    # Punctuation collision: "Casey Fields No. 4" (with period) vs
    # "Casey Fields No 4, Melbourne" (no period + city suffix) — same
    # ground. Remap to the canonical house-style form (no period on
    # "No", city suffix). Caught by
    # scripts/sweep_venue_punctuation_collisions.py.
    ('Casey Fields No. 4', 'Melbourne'): ('Casey Fields No 4', 'Melbourne', 'Australia'),

    # ─── Greenfield International Stadium, Thiruvananthapuram (Thiruvananthapuram, India) ─
    ('Greenfield International Stadium, Thiruvananthapuram', 'Thiruvananthapuram'): ('Greenfield International Stadium', 'Thiruvananthapuram', 'India'),
    ('Greenfield International Stadium', 'Thiruvananthapuram'): ('Greenfield International Stadium', 'Thiruvananthapuram', 'India'),

    # ─── Ground 1, Independence Park (Port Vila, Vanuatu) ─
    ('Ground 1, Independence Park', 'Port Vila'): ('Ground 1, Independence Park', 'Port Vila', 'Vanuatu'),

    # ─── Harrup Park (Mackay, Australia) ─
    ('Harrup Park', 'Mackay'): ('Harrup Park', 'Mackay', 'Australia'),

    # ─── Kyambogo Cricket Oval (Kampala, Uganda) ─
    ('Kyambogo Cricket Oval', 'Kampala'): ('Kyambogo Cricket Oval', 'Kampala', 'Uganda'),

    # ─── N'Du Stadium, Noumea, New Caledonia (Noumea, New Caledonia) ─
    ("N'Du Stadium, Noumea, New Caledonia", 'Noumea'): ("N'Du Stadium, Noumea, New Caledonia", 'Noumea', 'New Caledonia'),

    # ─── Narendra Modi Stadium Ground 'A', Motera (Ahmedabad, India) ─
    ("Narendra Modi Stadium Ground 'A', Motera", None): ("Narendra Modi Stadium Ground 'A', Motera", 'Ahmedabad', 'India'),
    ("Narendra Modi Stadium Ground 'A', Motera", 'Ahmedabad'): ("Narendra Modi Stadium Ground 'A', Motera", 'Ahmedabad', 'India'),

    # ─── National Stadium (Hamilton) (Hamilton, Bermuda) ─
    ('National Stadium', 'Hamilton'): ('National Stadium (Hamilton)', 'Hamilton', 'Bermuda'),
    ('National Stadium, Hamilton', 'Hamilton'): ('National Stadium (Hamilton)', 'Hamilton', 'Bermuda'),
    ('Bermuda National Stadium', 'Hamilton'): ('National Stadium (Hamilton)', 'Hamilton', 'Bermuda'),
    ('National Stadium (Hamilton)', 'Hamilton'): ('National Stadium (Hamilton)', 'Hamilton', 'Bermuda'),

    # ─── Royal Selangor Club, Kuala Lumpur (Kuala Lumpur, Malaysia) ─
    ('Royal Selangor Club', 'Kuala Lumpur'): ('Royal Selangor Club', 'Kuala Lumpur', 'Malaysia'),
    ('Royal Selangor Club, Kuala Lumpur', 'Kuala Lumpur'): ('Royal Selangor Club', 'Kuala Lumpur', 'Malaysia'),

    # ─── Ruaraka Sports Club Ground, Nairobi (Nairobi, Kenya) ─
    ('Ruaraka Sports Club Ground, Nairobi', 'Nairobi'): ('Ruaraka Sports Club Ground', 'Nairobi', 'Kenya'),

    # ─── Simonds Stadium, South Geelong (South Geelong, Australia) ─
    ('Simonds Stadium, South Geelong, Victoria', 'Geelong'): ('Simonds Stadium', 'South Geelong', 'Australia'),
    ('Simonds Stadium, South Geelong', 'Victoria'): ('Simonds Stadium', 'South Geelong', 'Australia'),
    ('Simonds Stadium, South Geelong', 'South Geelong'): ('Simonds Stadium', 'South Geelong', 'Australia'),

    # ─── Sportpark Thurlede (Schiedam, Netherlands) ─
    ('Sportpark Thurlede', 'Schiedam'): ('Sportpark Thurlede', 'Schiedam', 'Netherlands'),

    # ─── The Kent County Cricket Ground (Beckenham, England) ─
    ('The Kent County Cricket Ground', 'Beckenham'): ('The Kent County Cricket Ground', 'Beckenham', 'England'),

    # ─── Titwood, Glasgow (Glasgow, Scotland) ─
    ('Titwood, Glasgow', 'Glasgow'): ('Titwood', 'Glasgow', 'Scotland'),

    # ─── Traeger Park (Alice Springs, Australia) ─
    ('Traeger Park', 'Alice Springs'): ('Traeger Park', 'Alice Springs', 'Australia'),

    # ─── Albertslund Cricket Club (Copenhagen, Denmark) ─
    ('Albertslund Cricket Club', 'Copenhagen'): ('Albertslund Cricket Club', 'Copenhagen', 'Denmark'),

    # ─── Alur Cricket Stadium III (Bengaluru, India) ─
    ('Alur Cricket Stadium III', None): ('Alur Cricket Stadium III', 'Bengaluru', 'India'),
    ('Alur Cricket Stadium III', 'Bengaluru'): ('Alur Cricket Stadium III', 'Bengaluru', 'India'),

    # ─── Arundel Castle Cricket Club Ground (Arundel, England) ─
    ('Arundel Castle Cricket Club Ground', None): ('Arundel Castle Cricket Club Ground', 'Arundel', 'England'),
    ('Arundel Castle Cricket Club Ground', 'Arundel'): ('Arundel Castle Cricket Club Ground', 'Arundel', 'England'),

    # ─── Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium B (Lucknow, India) ─
    ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium B', None): ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium B', 'Lucknow', 'India'),
    ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium B', 'Lucknow'): ('Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium B', 'Lucknow', 'India'),

    # ─── Camberwell Sports Ground (Melbourne, Australia) ─
    ('Camberwell Sports Ground', 'Melbourne'): ('Camberwell Sports Ground', 'Melbourne', 'Australia'),

    # ─── College Field, St Peter Port (St Peter Port, Guernsey) ─
    ('College Field', 'St Peter Port'): ('College Field', 'St Peter Port', 'Guernsey'),
    ('College Field, St Peter Port', 'St Peter Port'): ('College Field', 'St Peter Port', 'Guernsey'),

    # ─── De Beers Diamond Oval, Kimberley (Kimberley, South Africa) ─
    ('De Beers Diamond Oval, Kimberley', 'Kimberley'): ('De Beers Diamond Oval', 'Kimberley', 'South Africa'),
    ('De Beers Diamond Oval', 'Kimberley'): ('De Beers Diamond Oval', 'Kimberley', 'South Africa'),

    # ─── F B Colony Ground (Vadodara, India) ─
    ('F B Colony Ground', None): ('F B Colony Ground', 'Vadodara', 'India'),
    ('F B Colony Ground', 'Vadodara'): ('F B Colony Ground', 'Vadodara', 'India'),

    # ─── FB Fields, St Clement (St Clement, Jersey) ─
    ('FB Fields, St Clement', 'St Clement'): ('FB Fields', 'St Clement', 'Jersey'),

    # ─── Green Park (Kanpur, India) ─
    ('Green Park', 'Kanpur'): ('Green Park', 'Kanpur', 'India'),

    # ─── Koge Cricket Club (Koge, Denmark) ─
    ('Koge Cricket Club', 'Koge'): ('Koge Cricket Club', 'Koge', 'Denmark'),

    # ─── Lugogo Cricket Oval, Kampala (Kampala, Uganda) ─
    ('Lugogo Cricket Oval, Kampala', 'Kampala'): ('Lugogo Cricket Oval', 'Kampala', 'Uganda'),
    ('Lugogo Cricket Oval', 'Kampala'): ('Lugogo Cricket Oval', 'Kampala', 'Uganda'),

    # ─── Malkerns Country Club oval (Malkerns, Eswatini) ─
    ('Malkerns Country Club oval', 'Malkerns'): ('Malkerns Country Club oval', 'Malkerns', 'Eswatini'),

    # ─── Meersen, Gent (Ghent, Belgium) ─
    ('Meersen, Gent', 'Ghent'): ('Meersen, Gent', 'Ghent', 'Belgium'),

    # ─── Merchant Taylors' School Ground, Northwood (Northwood, England) ─
    ("Merchant Taylors' School Ground, Northwood", 'Northwood'): ("Merchant Taylors' School Ground", 'Northwood', 'England'),
    ("Merchant Taylors' School Ground", 'Northwood'): ("Merchant Taylors' School Ground", 'Northwood', 'England'),

    # ─── Nehru Stadium (Kochi, India) ─
    ('Nehru Stadium', 'Kochi'): ('Nehru Stadium', 'Kochi', 'India'),
    ('Nehru Stadium', None): ('Nehru Stadium', 'Kochi', 'India'),

    # ─── Nigeria Cricket Federation Oval 2, Abuja (Abuja, Nigeria) ─
    ('Nigeria Cricket Federation Oval 2, Abuja', 'Abuja'): ('Nigeria Cricket Federation Oval 2', 'Abuja', 'Nigeria'),

    # ─── SSN College Ground (Chennai, India) ─
    ('SSN College Ground', None): ('SSN College Ground', 'Chennai', 'India'),
    ('SSN College Ground', 'Chennai'): ('SSN College Ground', 'Chennai', 'India'),

    # ─── Mohan's Oval (Abu Dhabi, United Arab Emirates) ─
    ('Sheikh Zayed Stadium Nursery 2', 'Abu Dhabi'): ("Mohan's Oval", 'Abu Dhabi', 'United Arab Emirates'),
    ("Mohan's Oval", 'Abu Dhabi'): ("Mohan's Oval", 'Abu Dhabi', 'United Arab Emirates'),

    # ─── Sky Stadium, Wellington (Wellington, New Zealand) ─
    ('Sky Stadium, Wellington', 'Wellington'): ('Sky Stadium', 'Wellington', 'New Zealand'),
    ('Sky Stadium', 'Wellington'): ('Sky Stadium', 'Wellington', 'New Zealand'),

    # ─── Southend Club Cricket Stadium, Karachi (Karachi, Pakistan) ─
    ('Southend Club Cricket Stadium', 'Karachi'): ('Southend Club Cricket Stadium', 'Karachi', 'Pakistan'),
    ('Southend Club Cricket Stadium, Karachi', 'Karachi'): ('Southend Club Cricket Stadium', 'Karachi', 'Pakistan'),

    # ─── Sri Ramachandra Medical College (Chennai, India) ─
    ('Sri Ramachandra Medical College', None): ('Sri Ramachandra Medical College', 'Chennai', 'India'),
    ('Sri Ramachandra Medical College', 'Chennai'): ('Sri Ramachandra Medical College', 'Chennai', 'India'),

    # ─── T I Murugappa Ground (Chennai, India) ─
    ('T I Murugappa Ground', None): ('T I Murugappa Ground', 'Chennai', 'India'),
    ('T I Murugappa Ground', 'Chennai'): ('T I Murugappa Ground', 'Chennai', 'India'),

    # ─── University of Tasmania Stadium, Launceston (Launceston, Australia) ─
    ('University of Tasmania Stadium, Launceston', 'Launceston'): ('University of Tasmania Stadium', 'Launceston', 'Australia'),

    # ─── Uxbridge Cricket Club Ground (Uxbridge, England) ─
    ('Uxbridge Cricket Club Ground', None): ('Uxbridge Cricket Club Ground', 'Uxbridge', 'England'),
    ('Uxbridge Cricket Club Ground', 'Uxbridge'): ('Uxbridge Cricket Club Ground', 'Uxbridge', 'England'),

    # ─── 7he Sevens Stadium, Dubai (Dubai, United Arab Emirates) ─
    ('7he Sevens Stadium, Dubai', 'Dubai'): ('7he Sevens Stadium', 'Dubai', 'United Arab Emirates'),

    # ─── Abu Dhabi Oval 1 (Abu Dhabi, United Arab Emirates) ─
    ('Abu Dhabi Oval 1', 'Abu Dhabi'): ('Abu Dhabi Oval 1', 'Abu Dhabi', 'United Arab Emirates'),

    # ─── Aigburth, Liverpool (Liverpool, England) ─
    ('Aigburth, Liverpool', 'Liverpool'): ('Aigburth', 'Liverpool', 'England'),
    ('Aigburth', 'Liverpool'): ('Aigburth', 'Liverpool', 'England'),

    # ─── Alur Cricket Stadium (Bengaluru, India) ─
    ('Alur Cricket Stadium', None): ('Alur Cricket Stadium', 'Bengaluru', 'India'),
    ('Alur Cricket Stadium', 'Bengaluru'): ('Alur Cricket Stadium', 'Bengaluru', 'India'),

    # ─── Alur Cricket Stadium II (Bengaluru, India) ─
    ('Alur Cricket Stadium II', None): ('Alur Cricket Stadium II', 'Bengaluru', 'India'),
    ('Alur Cricket Stadium II', 'Bengaluru'): ('Alur Cricket Stadium II', 'Bengaluru', 'India'),

    # ─── Chaudhry Bansi Lal Cricket Stadium (Lahli, India) ─
    ('Chaudhry Bansi Lal Cricket Stadium', None): ('Chaudhry Bansi Lal Cricket Stadium', 'Lahli', 'India'),
    ('Chaudhry Bansi Lal Cricket Stadium', 'Lahli'): ('Chaudhry Bansi Lal Cricket Stadium', 'Lahli', 'India'),

    # ─── Eastern Oval, Ballarat (Ballarat, Australia) ─
    ('Eastern Oval, Ballarat', 'Ballarat'): ('Eastern Oval', 'Ballarat', 'Australia'),
    ('Eastern Oval', 'Ballarat'): ('Eastern Oval', 'Ballarat', 'Australia'),

    # ─── Ground 2, Independence Park (Port Vila, Vanuatu) ─
    ('Ground 2, Independence Park', 'Port Vila'): ('Ground 2, Independence Park', 'Port Vila', 'Vanuatu'),

    # ─── Guanggong International Cricket Stadium (Guangzhou, China) ─
    ('Guanggong International Cricket Stadium', None): ('Guanggong International Cricket Stadium', 'Guangzhou', 'China'),
    ('Guanggong International Cricket Stadium', 'Guangzhou'): ('Guanggong International Cricket Stadium', 'Guangzhou', 'China'),

    # ─── International Sports Stadium, Coffs Harbour (Coffs Harbour, Australia) ─
    ('International Sports Stadium, Coffs Harbour', 'Coffs Harbour'): ('International Sports Stadium', 'Coffs Harbour', 'Australia'),
    ('International Sports Stadium', 'Coffs Harbour'): ('International Sports Stadium', 'Coffs Harbour', 'Australia'),

    # ─── Jadavpur University Campus (Kolkata, India) ─
    ('Jadavpur University Campus', None): ('Jadavpur University Campus', 'Kolkata', 'India'),
    ('Jadavpur University Campus', 'Kolkata'): ('Jadavpur University Campus', 'Kolkata', 'India'),

    # ─── Kaizuka Cricket Ground (Osaka, Japan) ─
    ('Kaizuka Cricket Ground', 'Osaka'): ('Kaizuka Cricket Ground', 'Osaka', 'Japan'),

    # ─── Kerrydale Oval (Gold Coast, Australia) ─
    ('Kerrydale Oval', 'Gold Coast'): ('Kerrydale Oval', 'Gold Coast', 'Australia'),

    # ─── Lalabhai Contractor Stadium (Surat, India) ─
    ('Lalabhai Contractor Stadium', 'Surat'): ('Lalabhai Contractor Stadium', 'Surat', 'India'),

    # ─── Los Reyes Polo Club (Guacima, Costa Rica) ─
    ('Los Reyes Polo Club', 'Guacima'): ('Los Reyes Polo Club', 'Guacima', 'Costa Rica'),

    # ─── Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh (New Chandigarh, India) ─
    ('Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh', 'New Chandigarh'): ('Maharaja Yadavindra Singh International Cricket Stadium', 'New Chandigarh', 'India'),

    # ─── Malek Cricket Ground, Ajman (Ajman, United Arab Emirates) ─
    ('Malek Cricket Ground, Ajman', 'Ajman'): ('Malek Cricket Ground', 'Ajman', 'United Arab Emirates'),

    # ─── Maple Leaf North-East Ground, King City (King City, Canada) ─
    ('Maple Leaf North-East Ground, King City', 'King City'): ('Maple Leaf North-East Ground', 'King City', 'Canada'),

    # ─── Morodok Techo National Stadium (Phnom Penh, Cambodia) ─
    ('Morodok Techo National Stadium', 'Phnom Penh'): ('Morodok Techo National Stadium', 'Phnom Penh', 'Cambodia'),

    # ─── Myreside (Edinburgh, Scotland) ─
    ('Myreside', 'Edinburgh'): ('Myreside', 'Edinburgh', 'Scotland'),

    # ─── New Williamfield No1 Oval (Stirling, Scotland) ─
    ('New Williamfield No1 Oval', 'Stirling'): ('New Williamfield No1 Oval', 'Stirling', 'Scotland'),

    # ─── P Sara Oval, Colombo (Colombo, Sri Lanka) ─
    ('P Sara Oval', 'Colombo'): ('P Sara Oval', 'Colombo', 'Sri Lanka'),
    ('P Sara Oval, Colombo', 'Colombo'): ('P Sara Oval', 'Colombo', 'Sri Lanka'),

    # ─── Pokhara Rangasala (Pokhara, Nepal) ─
    ('Pokhara Rangasala', 'Pokhara'): ('Pokhara Rangasala', 'Pokhara', 'Nepal'),

    # ─── Royal Chiangmai Golf Club (Chiang Mai, Thailand) ─
    ('Royal Chiangmai Golf Club', 'Chiang Mai'): ('Royal Chiangmai Golf Club', 'Chiang Mai', 'Thailand'),

    # ─── Seebarn Cricket Centre, Lower Austria (Lower Austria, Austria) ─
    ('Seebarn Cricket Centre', 'Lower Austria'): ('Seebarn Cricket Centre', 'Lower Austria', 'Austria'),
    ('Seebarn Cricket Centre, Lower Austria', 'Lower Austria'): ('Seebarn Cricket Centre', 'Lower Austria', 'Austria'),

    # ─── Warner Park, St Kitts (Basseterre, Saint Kitts and Nevis) ─
    ('Warner Park, St Kitts', 'Basseterre'): ('Warner Park, St Kitts', 'Basseterre', 'Saint Kitts and Nevis'),

    # ─── AMI Stadium (Christchurch, New Zealand) ─
    ('AMI Stadium', 'Christchurch'): ('AMI Stadium', 'Christchurch', 'New Zealand'),

    # ─── Al Dhaid Cricket Village (Al Dhaid, United Arab Emirates) ─
    ('Al Dhaid Cricket Village', None): ('Al Dhaid Cricket Village', 'Al Dhaid', 'United Arab Emirates'),
    ('Al Dhaid Cricket Village', 'Al Dhaid'): ('Al Dhaid Cricket Village', 'Al Dhaid', 'United Arab Emirates'),

    # ─── Alembic 1 Cricket Ground (Vadodara, India) ─
    ('Alembic 1 Cricket Ground', None): ('Alembic 1 Cricket Ground', 'Vadodara', 'India'),
    ('Alembic 1 Cricket Ground', 'Vadodara'): ('Alembic 1 Cricket Ground', 'Vadodara', 'India'),

    # ─── Clifton Park Ground, York (York, England) ─
    ('Clifton Park Ground, York', 'York'): ('Clifton Park Ground', 'York', 'England'),

    # ─── Clontarf Cricket Club Ground, Dublin (Dublin, Ireland) ─
    ('Clontarf Cricket Club Ground', 'Dublin'): ('Clontarf Cricket Club Ground', 'Dublin', 'Ireland'),
    ('Clontarf Cricket Club Ground, Dublin', 'Dublin'): ('Clontarf Cricket Club Ground', 'Dublin', 'Ireland'),

    # ─── Colts Cricket Club Ground (Colombo, Sri Lanka) ─
    ('Colts Cricket Club Ground', 'Colombo'): ('Colts Cricket Club Ground', 'Colombo', 'Sri Lanka'),

    # ─── Cricket Central, Sydney (Sydney, Australia) ─
    ('Cricket Central, Sydney', 'Sydney'): ('Cricket Central', 'Sydney', 'Australia'),

    # ─── Darren Sammy National Cricket Stadium, St Lucia (Gros Islet, Saint Lucia) ─
    ('Darren Sammy National Cricket Stadium, St Lucia', 'Gros Islet'): ('Darren Sammy National Cricket Stadium, St Lucia', 'Gros Islet', 'Saint Lucia'),

    # ─── Ekeberg Cricket Ground 1, Oslo (Oslo, Norway) ─
    ('Ekeberg Cricket Ground 1, Oslo', 'Oslo'): ('Ekeberg Cricket Ground 1', 'Oslo', 'Norway'),

    # ─── Gliderol Stadium (Adelaide, Australia) ─
    ('Gliderol Stadium', 'Adelaide'): ('Gliderol Stadium', 'Adelaide', 'Australia'),

    # ─── Gucherre Cricket Ground (Albergaria, Portugal) ─
    ('Gucherre Cricket Ground', 'Albergaria'): ('Gucherre Cricket Ground', 'Albergaria', 'Portugal'),

    # ─── IC-Gurunanak College Ground (Chennai, India) ─
    ('IC-Gurunanak College Ground', None): ('IC-Gurunanak College Ground', 'Chennai', 'India'),
    ('IC-Gurunanak College Ground', 'Chennai'): ('IC-Gurunanak College Ground', 'Chennai', 'India'),

    # ─── Johor Cricket Academy Oval (Johor, Malaysia) ─
    ('Johor Cricket Academy Oval', None): ('Johor Cricket Academy Oval', 'Johor', 'Malaysia'),
    ('Johor Cricket Academy Oval', 'Johor'): ('Johor Cricket Academy Oval', 'Johor', 'Malaysia'),

    # ─── Kensington Oval, Barbados (Bridgetown, Barbados) ─
    ('Kensington Oval, Barbados', 'Bridgetown'): ('Kensington Oval, Barbados', 'Bridgetown', 'Barbados'),

    # ─── Merrion Cricket Club Ground (Dublin, Ireland) ─
    ('Merrion Cricket Club Ground', 'Dublin'): ('Merrion Cricket Club Ground', 'Dublin', 'Ireland'),

    # ─── Mombasa Sports Club Ground (Mombasa, Kenya) ─
    ('Mombasa Sports Club Ground', None): ('Mombasa Sports Club Ground', 'Mombasa', 'Kenya'),
    ('Mombasa Sports Club Ground', 'Mombasa'): ('Mombasa Sports Club Ground', 'Mombasa', 'Kenya'),

    # ─── New Farnley CC, Leeds (Leeds, England) ─
    ('New Farnley CC, Leeds', 'Leeds'): ('New Farnley CC', 'Leeds', 'England'),

    # ─── OUTsurance Oval (Bloemfontein, South Africa) ─
    ('OUTsurance Oval', 'Bloemfontein'): ('OUTsurance Oval', 'Bloemfontein', 'South Africa'),

    # ─── Sportpark Harga, Schiedam (Schiedam, Netherlands) ─
    ('Sportpark Harga, Schiedam', 'Schiedam'): ('Sportpark Harga', 'Schiedam', 'Netherlands'),

    # ─── St Georges Quilmes (Buenos Aires, Argentina) ─
    ('St Georges Quilmes', None): ('St Georges Quilmes', 'Buenos Aires', 'Argentina'),
    ('St Georges Quilmes', 'Buenos Aires'): ('St Georges Quilmes', 'Buenos Aires', 'Argentina'),

    # ─── Stubberudmyra Cricket Ground, Oslo (Oslo, Norway) ─
    ('Stubberudmyra Cricket Ground, Oslo', 'Oslo'): ('Stubberudmyra Cricket Ground', 'Oslo', 'Norway'),

    # ─── Ted Summerton Reserve, Moe (Moe, Australia) ─
    ('Ted Summerton Reserve, Moe', 'Moe'): ('Ted Summerton Reserve', 'Moe', 'Australia'),
    ('Ted Summerton Reserve', 'Moe'): ('Ted Summerton Reserve', 'Moe', 'Australia'),

    # ─── Three Ws Oval, Cave Hill, Barbados (Cave Hill, Barbados) ─
    ('Three Ws Oval, Cave Hill, Barbados', 'Cave Hill'): ('Three Ws Oval, Cave Hill, Barbados', 'Cave Hill', 'Barbados'),

    # ─── West Park Oval (Burnie, Australia) ─
    ('West Park Oval', 'Burnie'): ('West Park Oval', 'Burnie', 'Australia'),

    # ─── York Cricket Club (York, England) ─
    ('York Cricket Club', 'York'): ('York Cricket Club', 'York', 'England'),

    # ─── Abu Dhabi Oval 2 (Abu Dhabi, United Arab Emirates) ─
    ('Abu Dhabi Oval 2', 'Abu Dhabi'): ('Abu Dhabi Oval 2', 'Abu Dhabi', 'United Arab Emirates'),

    # ─── Ballpark Ground, Graz (Graz, Austria) ─
    ('Ballpark Ground, Graz', 'Graz'): ('Ballpark Ground', 'Graz', 'Austria'),

    # ─── Bankstown Oval (Sydney, Australia) ─
    ('Bankstown Oval', 'Sydney'): ('Bankstown Oval', 'Sydney', 'Australia'),

    # ─── Cazaly's Stadium, Cairns (Cairns, Australia) ─
    ("Cazaly's Stadium, Cairns", 'Cairns'): ("Cazaly's Stadium", 'Cairns', 'Australia'),
    ("Cazaly's Stadium", 'Cairns'): ("Cazaly's Stadium", 'Cairns', 'Australia'),

    # ─── City Oval, Pietermaritzburg (Pietermaritzburg, South Africa) ─
    ('City Oval', 'Pietermaritzburg'): ('City Oval', 'Pietermaritzburg', 'South Africa'),
    ('City Oval, Pietermaritzburg', 'Pietermaritzburg'): ('City Oval', 'Pietermaritzburg', 'South Africa'),

    # ─── Cobham Oval (New), Whangarei (Whangarei, New Zealand) ─
    ('Cobham Oval (New), Whangarei', 'Whangarei'): ('Cobham Oval (New)', 'Whangarei', 'New Zealand'),

    # ─── Colombo Cricket Club Ground (Colombo, Sri Lanka) ─
    ('Colombo Cricket Club Ground', None): ('Colombo Cricket Club Ground', 'Colombo', 'Sri Lanka'),
    ('Colombo Cricket Club Ground', 'Colombo'): ('Colombo Cricket Club Ground', 'Colombo', 'Sri Lanka'),

    # ─── Desert Springs Cricket Ground (Almeria, Spain) ─
    ('Desert Springs Cricket Ground', 'Almeria'): ('Desert Springs Cricket Ground', 'Almeria', 'Spain'),

    # ─── Geelong Cricket Ground (Geelong, Australia) ─
    ('Geelong Cricket Ground', 'Geelong'): ('Geelong Cricket Ground', 'Geelong', 'Australia'),

    # ─── Grange Cricket Club, Raeburn Place (Edinburgh, Scotland) ─
    ('Grange Cricket Club, Raeburn Place', 'Edinburgh'): ('Grange Cricket Club, Raeburn Place', 'Edinburgh', 'Scotland'),

    # ─── ICC Academy Oval 2 (Dubai, United Arab Emirates) ─
    ('ICC Academy Oval 2', 'Dubai'): ('ICC Academy Oval 2', 'Dubai', 'United Arab Emirates'),

    # ─── ICC Global Cricket Academy (Dubai, United Arab Emirates) ─
    ('ICC Global Cricket Academy', 'Dubai'): ('ICC Global Cricket Academy', 'Dubai', 'United Arab Emirates'),

    # ─── Invermay Park, Launceston (Launceston, Australia) ─
    ('Invermay Park, Launceston', 'Launceston'): ('Invermay Park', 'Launceston', 'Australia'),
    ('Invermay Park', 'Launceston'): ('Invermay Park', 'Launceston', 'Australia'),

    # ─── Jadavpur University Campus 2nd Ground, Kolkata (Kolkata, India) ─
    ('Jadavpur University Campus 2nd Ground, Kolkata', 'Kolkata'): ('Jadavpur University Campus 2nd Ground', 'Kolkata', 'India'),

    # ─── Jaffery Sports Club Ground (Nairobi, Kenya) ─
    ('Jaffery Sports Club Ground', 'Nairobi'): ('Jaffery Sports Club Ground', 'Nairobi', 'Kenya'),

    # ─── Jinja Cricket Ground (Jinja, Uganda) ─
    ('Jinja Cricket Ground', 'Jinja'): ('Jinja Cricket Ground', 'Jinja', 'Uganda'),

    # ─── KSCA Cricket Ground, Alur (Bengaluru, India) ─
    ('KSCA Cricket Ground, Alur', 'Bengaluru'): ('KSCA Cricket Ground, Alur', 'Bengaluru', 'India'),

    # ─── Khan Shaheb Osman Ali Stadium (Fatullah, Bangladesh) ─
    ('Khan Shaheb Osman Ali Stadium', 'Fatullah'): ('Khan Shaheb Osman Ali Stadium', 'Fatullah', 'Bangladesh'),

    # ─── Koge Cricket Club 2 (Koge, Denmark) ─
    ('Koge Cricket Club 2', 'Koge'): ('Koge Cricket Club 2', 'Koge', 'Denmark'),

    # ─── Latrobe Recreation Ground, Latrobe (Latrobe, Australia) ─
    ('Latrobe Recreation Ground, Latrobe', 'Latrobe'): ('Latrobe Recreation Ground', 'Latrobe', 'Australia'),

    # ─── Lavington Sports Oval, Albury (Albury, Australia) ─
    ('Lavington Sports Oval', 'Albury'): ('Lavington Sports Oval', 'Albury', 'Australia'),
    ('Lavington Sports Oval, Albury', 'Albury'): ('Lavington Sports Oval', 'Albury', 'Australia'),

    # ─── Malahide, Dublin (Dublin, Ireland) ─
    ('Malahide, Dublin', 'Dublin'): ('Malahide', 'Dublin', 'Ireland'),

    # ─── Marrara Stadium, Darwin (Darwin, Australia) ─
    ('Marrara Stadium, Darwin', 'Darwin'): ('Marrara Stadium', 'Darwin', 'Australia'),

    # ─── Nevill Ground (Tunbridge Wells, England) ─
    ('Nevill Ground', 'Tunbridge Wells'): ('Nevill Ground', 'Tunbridge Wells', 'England'),

    # ─── Nondescripts Cricket Club Ground (Colombo, Sri Lanka) ─
    ('Nondescripts Cricket Club Ground', 'Colombo'): ('Nondescripts Cricket Club Ground', 'Colombo', 'Sri Lanka'),

    # ─── North Marine Road Ground, Scarborough (Scarborough, England) ─
    ('North Marine Road Ground, Scarborough', 'Scarborough'): ('North Marine Road Ground', 'Scarborough', 'England'),

    # ─── Nuriootpa Centennial Park (Nuriootpa, Australia) ─
    ('Nuriootpa Centennial Park', 'Nuriootpa'): ('Nuriootpa Centennial Park', 'Nuriootpa', 'Australia'),

    # ─── Queen Elizabeth II Oval (Bendigo, Australia) ─
    ('Queen Elizabeth II Oval', 'Bendigo'): ('Queen Elizabeth II Oval', 'Bendigo', 'Australia'),

    # ─── San Albano (Buenos Aires, Argentina) ─
    ('San Albano', None): ('San Albano', 'Buenos Aires', 'Argentina'),
    ('San Albano', 'Buenos Aires'): ('San Albano', 'Buenos Aires', 'Argentina'),

    # ─── Sao Fernando Polo and Cricket Club, Campo Sede (Seropedica, Brazil) ─
    ('Sao Fernando Polo and Cricket Club', 'Seropedica'): ('Sao Fernando Polo and Cricket Club, Campo Sede', 'Seropedica', 'Brazil'),
    ('Sao Fernando Polo and Cricket Club, Campo Sede', 'Seropedica'): ('Sao Fernando Polo and Cricket Club, Campo Sede', 'Seropedica', 'Brazil'),

    # ─── Sheikh Kamal International Cricket Stadium (Cox's Bazar, Bangladesh) ─
    ('Sheikh Kamal International Cricket Stadium', "Cox's Bazar"): ('Sheikh Kamal International Cricket Stadium', "Cox's Bazar", 'Bangladesh'),

    # ─── Skarpnack 1 (Stockholm, Sweden) ─
    ('Skarpnack 1', 'Stockholm'): ('Skarpnack 1', 'Stockholm', 'Sweden'),

    # ─── Skarpnack 2 (Stockholm, Sweden) ─
    ('Skarpnack 2', 'Stockholm'): ('Skarpnack 2', 'Stockholm', 'Sweden'),

    # ─── Solvangs Park, Glostrup (Copenhagen, Denmark) ─
    ('Solvangs Park, Glostrup', 'Copenhagen'): ('Solvangs Park, Glostrup', 'Copenhagen', 'Denmark'),

    # ─── Sydney Parade (Dublin, Ireland) ─
    ('Sydney Parade', 'Dublin'): ('Sydney Parade', 'Dublin', 'Ireland'),

    # ─── The Vineyard (Dublin, Ireland) ─
    ('The Vineyard', 'Dublin'): ('The Vineyard', 'Dublin', 'Ireland'),

    # ─── Tony Ireland Stadium (Townsville, Australia) ─
    ('Tony Ireland Stadium', 'Townsville'): ('Tony Ireland Stadium', 'Townsville', 'Australia'),

    # ─── University Oval (Hobart) (Hobart, Australia) ─
    ('University Oval, Hobart', 'Hobart'): ('University Oval (Hobart)', 'Hobart', 'Australia'),
    ('University Oval (Hobart)', 'Hobart'): ('University Oval (Hobart)', 'Hobart', 'Australia'),

    # ─── Windsor Park, Roseau (Roseau, Dominica) ─
    ('Windsor Park, Roseau', 'Dominica'): ('Windsor Park', 'Roseau', 'Dominica'),
    ('Windsor Park, Roseau, Dominica', 'Roseau'): ('Windsor Park', 'Roseau', 'Dominica'),
    ('Windsor Park, Roseau', 'Roseau'): ('Windsor Park', 'Roseau', 'Dominica'),

    # ─── Adelaide Oval No. 2 (Adelaide, Australia) ─
    ('Adelaide Oval No. 2', None): ('Adelaide Oval No. 2', 'Adelaide', 'Australia'),
    ('Adelaide Oval No. 2', 'Adelaide'): ('Adelaide Oval No. 2', 'Adelaide', 'Australia'),

    # ─── Affies Park (Windhoek, Namibia) ─
    ('Affies Park', 'Windhoek'): ('Affies Park', 'Windhoek', 'Namibia'),

    # ─── Boland Bank Park (Paarl, South Africa) ─
    ('Boland Bank Park', 'Paarl'): ('Boland Bank Park', 'Paarl', 'South Africa'),

    # ─── Boughton Hall Cricket Club Ground, Chester (Chester, England) ─
    ('Boughton Hall Cricket Club Ground, Chester', 'Chester'): ('Boughton Hall Cricket Club Ground', 'Chester', 'England'),

    # ─── Casey Fields No 4, Melbourne (Melbourne, Australia) ─
    ('Casey Fields No 4, Melbourne', 'Melbourne'): ('Casey Fields No 4', 'Melbourne', 'Australia'),

    # ─── Castle Park Cricket Ground (Colchester, England) ─
    ('Castle Park Cricket Ground', 'Colchester'): ('Castle Park Cricket Ground', 'Colchester', 'England'),

    # ─── Chilaw Marians Cricket Club Ground (Katunayake, Sri Lanka) ─
    ('Chilaw Marians Cricket Club Ground', 'FTZ Sports Complex'): ('Chilaw Marians Cricket Club Ground', 'Katunayake', 'Sri Lanka'),
    ('Chilaw Marians Cricket Club Ground', 'Katunayake'): ('Chilaw Marians Cricket Club Ground', 'Katunayake', 'Sri Lanka'),

    # ─── Coolidge Cricket Ground (Antigua, Antigua and Barbuda) ─
    ('Coolidge Cricket Ground', 'Antigua'): ('Coolidge Cricket Ground', 'Antigua', 'Antigua and Barbuda'),

    # ─── Ekeberg Cricket Ground 2, Oslo (Oslo, Norway) ─
    ('Ekeberg Cricket Ground 2, Oslo', 'Oslo'): ('Ekeberg Cricket Ground 2', 'Oslo', 'Norway'),

    # ─── Guttsta Wicked Cricket Club (Kolsva, Sweden) ─
    ('Guttsta Wicked Cricket Club', 'Kolsva'): ('Guttsta Wicked Cricket Club', 'Kolsva', 'Sweden'),

    # ─── Howell Oval (Sydney, Australia) ─
    ('Howell Oval', 'Sydney'): ('Howell Oval', 'Sydney', 'Australia'),

    # ─── ICC Academy Oval 1 (Dubai, United Arab Emirates) ─
    ('ICC Academy Oval 1', 'Dubai'): ('ICC Academy Oval 1', 'Dubai', 'United Arab Emirates'),

    # ─── Jade Stadium (Christchurch, New Zealand) ─
    ('Jade Stadium', 'Christchurch'): ('Jade Stadium', 'Christchurch', 'New Zealand'),

    # ─── Jubilee Park, Ringwood, Melbourne (Melbourne, Australia) ─
    ('Jubilee Park, Ringwood, Melbourne', 'Melbourne'): ('Jubilee Park, Ringwood', 'Melbourne', 'Australia'),

    # ─── Kent County Cricket Ground (Beckenham, England) ─
    ('Kent County Cricket Ground', 'Beckenham'): ('Kent County Cricket Ground', 'Beckenham', 'England'),

    # ─── LC de Villiers Oval (Pretoria, South Africa) ─
    ('LC de Villiers Oval', 'Pretoria'): ('LC de Villiers Oval', 'Pretoria', 'South Africa'),

    # ─── Las Caballerizas (Mexico City, Mexico) ─
    ('Las Caballerizas', 'Mexico City'): ('Las Caballerizas', 'Mexico City', 'Mexico'),

    # ─── Mainpower Oval (Rangiora, New Zealand) ─
    ('Mainpower Oval', 'Rangiora'): ('Mainpower Oval', 'Rangiora', 'New Zealand'),

    # ─── Mercantile Cricket Association Ground (Colombo, Sri Lanka) ─
    ('Mercantile Cricket Association Ground', 'Colombo'): ('Mercantile Cricket Association Ground', 'Colombo', 'Sri Lanka'),

    # ─── Moses Mabhida Stadium (Durban, South Africa) ─
    ('Moses Mabhida Stadium', 'Durban'): ('Moses Mabhida Stadium', 'Durban', 'South Africa'),

    # ─── National Cricket Stadium, Grenada (St George's, Grenada) ─
    ('National Cricket Stadium, Grenada', "St George's"): ('National Cricket Stadium, Grenada', "St George's", 'Grenada'),

    # ─── North Dalton Park (Wollongong, Australia) ─
    ('North Dalton Park', 'Wollongong'): ('North Dalton Park', 'Wollongong', 'Australia'),

    # ─── North Sydney Oval No.2 (Sydney, Australia) ─
    ('North Sydney Oval No.2', 'Sydney'): ('North Sydney Oval No.2', 'Sydney', 'Australia'),

    # ─── Queen's Park (Invercargill) (Invercargill, New Zealand) ─
    ("Queen's Park", 'Invercargill'): ("Queen's Park (Invercargill)", 'Invercargill', 'New Zealand'),
    ("Queen's Park (Invercargill)", 'Invercargill'): ("Queen's Park (Invercargill)", 'Invercargill', 'New Zealand'),

    # ─── Sano International Cricket Ground 2 (Sano, Japan) ─
    ('Sano International Cricket Ground 2', 'Sano'): ('Sano International Cricket Ground 2', 'Sano', 'Japan'),

    # ─── Sea Breeze Oval (Hamilton, New Zealand) ─
    ('Sea Breeze Oval', 'Hamilton'): ('Sea Breeze Oval', 'Hamilton', 'New Zealand'),

    # ─── Shrimant Madhavrao Scindia Cricket Stadium, Gwalior (Gwalior, India) ─
    ('Shrimant Madhavrao Scindia Cricket Stadium, Gwalior', 'Gwalior'): ('Shrimant Madhavrao Scindia Cricket Stadium', 'Gwalior', 'India'),

    # ─── Sportpark Het Schootsveld 2 (Deventer, Netherlands) ─
    ('Sportpark Het Schootsveld 2', 'Deventer'): ('Sportpark Het Schootsveld 2', 'Deventer', 'Netherlands'),

    # ─── Tafawa Balewa Square (TBS) Cricket Oval (Lagos, Nigeria) ─
    ('Tafawa Balewa Square (TBS) Cricket Oval', None): ('Tafawa Balewa Square (TBS) Cricket Oval', 'Lagos', 'Nigeria'),
    ('Tafawa Balewa Square (TBS) Cricket Oval', 'Lagos'): ('Tafawa Balewa Square (TBS) Cricket Oval', 'Lagos', 'Nigeria'),

    # ─── Thailand Cricket Ground (Bangkok, Thailand) ─
    ('Thailand Cricket Ground', 'Bangkok'): ('Thailand Cricket Ground', 'Bangkok', 'Thailand'),

    # ─── Trafalgar Road Ground, Southport (Southport, England) ─
    ('Trafalgar Road Ground, Southport', 'Southport'): ('Trafalgar Road Ground', 'Southport', 'England'),

    # ─── Turf City B Cricket Ground (Singapore, Singapore) ─
    ('Turf City B Cricket Ground', 'Singapore'): ('Turf City B Cricket Ground', 'Singapore', 'Singapore'),

    # ─── Waverley Oval (Sydney, Australia) ─
    ('Waverley Oval', 'Sydney'): ('Waverley Oval', 'Sydney', 'Australia'),

}


def resolve(
    raw_venue: Optional[str],
    raw_city: Optional[str],
) -> Optional[tuple[str, str, str]]:
    """Return (canonical_venue, canonical_city, country) or None if unknown.

    Lookup prefers exact (raw_venue, raw_city) match; falls back to
    (raw_venue, None) in case the city is NULL in incoming data but the
    same venue appears elsewhere with a city.
    """
    if raw_venue is None:
        return None
    hit = VENUE_ALIASES.get((raw_venue, raw_city))
    if hit is not None:
        return hit
    return VENUE_ALIASES.get((raw_venue, None))


def _strip_city_suffix(
    raw_venue: Optional[str],
    raw_city: Optional[str],
) -> Optional[str]:
    """Return raw_venue with a trailing ", <raw_city>" lopped off iff
    present and non-empty result. Otherwise None.

    Applied as a display-tidy rule on unknown-venue fallthrough so new
    cricsheet venues that follow the common ", <City>" convention
    don't render as "X, Mumbai · Mumbai" in the UI. The full alias
    table already has this suffix stripped on every manually-
    catalogued entry (scripts/strip_venue_suffix.py, run 2026-04-18);
    this runtime rule keeps new/unseen venues consistent without
    requiring a worklist round-trip per ground. Fires for both full
    rebuild (via import_data.import_match_file) and incremental
    (update_recent → import_match_file). Country stays None; the
    unknowns log still captures the row so country can be backfilled.
    """
    if not raw_venue or not raw_city:
        return None
    suffix = f", {raw_city}"
    if raw_venue.endswith(suffix) and len(raw_venue) > len(suffix):
        return raw_venue[: -len(suffix)]
    return None


def resolve_or_raw(
    raw_venue: Optional[str],
    raw_city: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Soft-fail variant: returns (canonical_venue, canonical_city,
    country) on hit, otherwise (raw_venue, raw_city, None) — lossless
    passthrough, never raises. Used at import time so unknown new
    venues are still persisted (just not canonicalized); the caller
    is expected to log the miss for worklist review.

    On a dict miss, applies `_strip_city_suffix` as a display-tidy
    fallback — a cricsheet name like "New Test Stadium, Mumbai" with
    city="Mumbai" auto-resolves to ("New Test Stadium", "Mumbai", None).
    City + country still need human review (country stays None, the
    unknowns log still records the row), but the UI gets a clean
    venue name from the first ball without waiting for an alias PR.
    """
    hit = resolve(raw_venue, raw_city)
    if hit is not None:
        return hit
    stripped = _strip_city_suffix(raw_venue, raw_city)
    if stripped is not None:
        return (stripped, raw_city, None)
    return (raw_venue, raw_city, None)
