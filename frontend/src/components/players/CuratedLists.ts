// Curated seeds for the /players landing.
//
// `role` picks which summary fetch drives the tile's one-line stat
// strip (batters/keepers/all-rounders show batting numbers; specialist
// bowlers show bowling numbers).
//
// IDs are resolved from the DB (`person` table) — if a seed player
// isn't in our cricsheet corpus we sub the closest canonical name.
// Cricsheet stores abbreviated forms ("S Mandhana", "D Sharma",
// "MM Lanning") — we display the canonical abbreviation here rather
// than re-spelling, since that's what the rest of the site uses.

export interface ProfileTile {
  id: string
  name: string
  gender: 'male' | 'female'
  /** Drives which summary the tile fetches for its stat strip. */
  role: 'batter' | 'bowler'
}

export interface ComparePair {
  a: ProfileTile
  b: ProfileTile
}

export const PROFILE_MEN: ProfileTile[] = [
  { id: 'ba607b88', name: 'V Kohli',       gender: 'male', role: 'batter' },
  { id: '462411b3', name: 'JJ Bumrah',     gender: 'male', role: 'bowler' },
  { id: '30a45b23', name: 'SPD Smith',     gender: 'male', role: 'batter' },
  { id: '740742ef', name: 'RG Sharma',     gender: 'male', role: 'batter' },
  { id: '99b75528', name: 'JC Buttler',    gender: 'male', role: 'batter' },
  { id: 'e798611a', name: 'HM Amla',       gender: 'male', role: 'batter' },
  { id: '8a75e999', name: 'Babar Azam',    gender: 'male', role: 'batter' },
  { id: 'd027ba9f', name: 'KS Williamson', gender: 'male', role: 'batter' },
  { id: '0f721006', name: 'JO Holder',     gender: 'male', role: 'bowler' },
]

export const PROFILE_WOMEN: ProfileTile[] = [
  { id: '5d2eda89', name: 'S Mandhana',    gender: 'female', role: 'batter' },
  { id: 'be150fc8', name: 'EA Perry',      gender: 'female', role: 'batter' },
  { id: '4ba0289e', name: 'HC Knight',     gender: 'female', role: 'batter' },
  { id: '52d1dbc8', name: 'BL Mooney',     gender: 'female', role: 'batter' },
  { id: '27e003ce', name: 'MM Lanning',    gender: 'female', role: 'batter' },
  { id: '201fef33', name: 'D Sharma',      gender: 'female', role: 'bowler' },
  { id: '321644de', name: 'AJ Healy',      gender: 'female', role: 'batter' },
  { id: 'de69af96', name: 'SFM Devine',    gender: 'female', role: 'batter' },
  { id: 'd32cf49a', name: 'HK Matthews',   gender: 'female', role: 'batter' },
]

export const COMPARE_MEN: ComparePair[] = [
  { a: PROFILE_MEN[0], b: { id: '6a26221c', name: 'AK Markram',   gender: 'male', role: 'batter' } },
  { a: PROFILE_MEN[2], b: { id: 'a343262c', name: 'JE Root',      gender: 'male', role: 'batter' } },
  { a: PROFILE_MEN[1], b: { id: 'e62dd25d', name: 'K Rabada',     gender: 'male', role: 'bowler' } },
  { a: { id: 'e087956b', name: 'BA Stokes', gender: 'male', role: 'batter' },
    b: { id: 'fe93fd9d', name: 'RA Jadeja', gender: 'male', role: 'batter' } },
  { a: PROFILE_MEN[4], b: { id: '2b6e6dec', name: 'AC Gilchrist', gender: 'male', role: 'batter' } },
]

export const COMPARE_WOMEN: ComparePair[] = [
  { a: PROFILE_WOMEN[0], b: PROFILE_WOMEN[3] },   // Mandhana × Mooney
  { a: PROFILE_WOMEN[1], b: PROFILE_WOMEN[2] },   // Perry × Knight
  { a: PROFILE_WOMEN[6], b: PROFILE_WOMEN[0] },   // Healy × Mandhana
]
