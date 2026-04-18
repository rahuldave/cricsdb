# Venue-worklist research sources

Web sources used to resolve ambiguous venue rows during the 2026-04-17
canonicalization pass (commit `6e9efe8`). Saved so we can re-check
decisions later without re-searching.

## Indian domestic grounds (SMAT / Ranji venues)

- [Reliance Stadium, Vadodara](https://en.wikipedia.org/wiki/Reliance_Stadium) — Baroda team's home
- [Nehru Stadium, Kochi — SMAT 2016 venues](https://www.cricbuzz.com/cricket-series/2365/syed-mushtaq-ali-trophy-2016/matches) — resolved "Jawaharlal Nehru Stadium" for Punjab vs Rajasthan
- [Dr PVG Raju ACA Sports Complex](https://en.wikipedia.org/wiki/Dr_PVG_Raju_ACA_Sports_Complex) — Vizianagaram, AP
- [St Xavier's College Ground, Thumba](https://en.wikipedia.org/wiki/St_Xavier's_College_Ground) — Thiruvananthapuram (KCA ground)
- [Dr Gokaraju Laila Ganga Raju ACA, Mulapadu](https://www.espncricinfo.com/india/content/ground/1063510.html) — Vijayawada
- [Bharat Ratna Ekana Cricket Stadium, Lucknow](https://en.wikipedia.org/wiki/Ekana_Cricket_Stadium)
- [Emerald Heights International School, Indore](https://emeraldheights.edu.in/sports-infrastructure/)
- [Alur Cricket Stadium (Three Ovals KSCA)](https://en.wikipedia.org/wiki/Three_Ovals_KSCA_Stadium) — Bengaluru outskirts
- [F.B. Colony Ground, Vadodara](https://en.wikipedia.org/wiki/F._B._Colony_Ground)
- [Guru Nanak College Ground, Chennai](https://en.wikipedia.org/wiki/Guru_Nanak_College_Ground) — IC-Gurunanak College Ground
- [DRIEMS Ground, Tangi/Cuttack](https://en.wikipedia.org/wiki/DRIEMS_Ground)

## International / associate venues

- [Guanggong International Cricket Stadium](https://en.wikipedia.org/wiki/Guanggong_International_Cricket_Stadium) — Guangzhou, China
- [FTZ Sports Complex / Chilaw Marians](https://en.wikipedia.org/wiki/FTZ_Sports_Complex) — Katunayake, Sri Lanka
- [Club San Albano, Buenos Aires](https://en.wikipedia.org/wiki/Club_San_Albano) — Argentina
- [Malkerns Country Club Oval](https://www.espncricinfo.com/cricket-grounds/malkerns-country-club-oval-malkerns-1326810) — Eswatini
- [Los Reyes Polo Club, Guacima](https://www.espncricinfo.com/cricket-grounds/los-reyes-polo-club-guacima-1207464) — Costa Rica
- [Bermuda National Stadium, Hamilton](https://en.wikipedia.org/wiki/Bermuda_National_Stadium) — disambiguates "National Stadium Hamilton" from Pakistan's Karachi stadium

## Pattern notes for future resolution

- **Cricsheet `city` is the political/administrative label at match time.**
  Sometimes it's the state (`Victoria` for Australian grounds), sometimes
  the neighborhood (`Mirpur` for Shere Bangla in Dhaka), sometimes the
  island (`St Kitts` instead of `Basseterre`). Always double-check when
  the city string is short or generic.
- **English county cricket grounds named "County Ground"** appear in six
  cities (Taunton, Bristol, Chelmsford, Northampton, Derby, Hove). Must
  use paren-disambiguation; the raw venue name alone is not a key.
- **Twin-city mislabels:** Mohali/Chandigarh, Mullanpur/New Chandigarh,
  Grand Prairie/Dallas, Kalamassery/Kochi, Mirpur/Dhaka. Canonical =
  the actual local government city, not the better-known metro.
- **"N" suffix conventions:** `Ground 2`, `Oval 2`, `No. 2`, `Nursery 1`
  almost always mean a sibling pitch at the same complex — keep separate
  unless external evidence says they're synonyms (Sheikh Zayed Nursery 1
  was the lone merge in this pass).
- **Punctuation-only collisions** (dots, commas, apostrophes, hyphens,
  whitespace) need a dedicated second-pass sweep. Initial
  canonicalization matched on token-level prefix/suffix and missed
  e.g. `M.Chinnaswamy Stadium` vs `M Chinnaswamy Stadium, Bengaluru`.
  Run `scripts/sweep_venue_punctuation_collisions.py` after every
  big incremental import; it lists candidate groups punctuation-
  insensitively grouped, human edits `api/venue_aliases.py` to
  remap losers → winners, then `fix_venue_names.py` retrofits.
  Five collisions found + fixed 2026-04-17: M.Chinnaswamy,
  Casey Fields No. 4, ACA-VDCA hyphen variant, Gahanga period/comma,
  Grand Prairie Stadium/Dallas.
- **Neutral venues:** Pakistan's "home" games 2009-2019 were mostly in
  UAE (Sharjah, Abu Dhabi, Dubai). A Pakistan-Australia match at Sharjah
  doesn't imply Sharjah is in Pakistan. When cross-checking via teams,
  look for the most frequent home team or series context, not any one
  match.
