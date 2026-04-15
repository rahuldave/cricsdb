/**
 * FlagBadge — renders a country flag for a cricket team string.
 *
 * Uses the flag-icons CSS library for ISO country flags. Special cases
 * for cricket-specific "countries" (West Indies — a multi-nation entity
 * with no ISO code) and for UK subdivisions that cricket treats as
 * separate teams (England / Scotland / Wales each have their own flag).
 *
 * Returns null for unmappable team strings (club teams, unrecognised
 * associate nations) so the caller doesn't need to guard before use.
 */

// Cricsheet team string → flag-icons code OR special tag ("wi" / "eng" / …).
// Codes are ISO 3166-1 alpha-2 (lowercase) per flag-icons convention.
// UK subdivisions use the alpha-3 uppercase form from the GB- namespace.
const TEAM_TO_FLAG: Record<string, string> = {
  // Full members
  "Afghanistan": "af",
  "Australia": "au",
  "Bangladesh": "bd",
  "England": "gb-eng",
  "India": "in",
  "Ireland": "ie",
  "New Zealand": "nz",
  "Pakistan": "pk",
  "South Africa": "za",
  "Sri Lanka": "lk",
  "West Indies": "wi",          // special — rendered as WI pill
  "Zimbabwe": "zw",
  // Associates (top contributors)
  "United Arab Emirates": "ae",
  "Netherlands": "nl",
  "Hong Kong": "hk",
  "Uganda": "ug",
  "Namibia": "na",
  "Nepal": "np",
  "Malaysia": "my",
  "Thailand": "th",
  "Scotland": "gb-sct",
  "Rwanda": "rw",
  "Kenya": "ke",
  "Bahrain": "bh",
  "Oman": "om",
  "Indonesia": "id",
  "Nigeria": "ng",
  "Tanzania": "tz",
  "Papua New Guinea": "pg",
  "Singapore": "sg",
  "Kuwait": "kw",
  "United States of America": "us",
  "Botswana": "bw",
  "Canada": "ca",
  "Germany": "de",
  "Qatar": "qa",
  "Japan": "jp",
  "Sierra Leone": "sl",
  "Bhutan": "bt",
  "Malawi": "mw",
  "Austria": "at",
  "Argentina": "ar",
  "Belgium": "be",
  "Belize": "bz",
  "Bermuda": "bm",
  "Brazil": "br",
  "Bulgaria": "bg",
  "Cambodia": "kh",
  "Cameroon": "cm",
  "Cayman Islands": "ky",
  "Chile": "cl",
  "China": "cn",
  "Costa Rica": "cr",
  "Croatia": "hr",
  "Cyprus": "cy",
  "Czech Republic": "cz",
  "Denmark": "dk",
  "Estonia": "ee",
  "Eswatini": "sz",
  "Fiji": "fj",
  "Finland": "fi",
  "France": "fr",
  "Gambia": "gm",
  "Ghana": "gh",
  "Gibraltar": "gi",
  "Greece": "gr",
  "Guernsey": "gg",
  "Hungary": "hu",
  "Iran": "ir",
  "Isle of Man": "im",
  "Israel": "il",
  "Italy": "it",
  "Jamaica": "jm",
  "Jersey": "je",
  "Lesotho": "ls",
  "Luxembourg": "lu",
  "Maldives": "mv",
  "Malta": "mt",
  "Mexico": "mx",
  "Mongolia": "mn",
  "Mozambique": "mz",
  "Myanmar": "mm",
  "Norway": "no",
  "Panama": "pa",
  "Peru": "pe",
  "Philippines": "ph",
  "Poland": "pl",
  "Portugal": "pt",
  "Romania": "ro",
  "Russia": "ru",
  "Samoa": "ws",
  "Saudi Arabia": "sa",
  "Serbia": "rs",
  "Seychelles": "sc",
  "Slovenia": "si",
  "South Korea": "kr",
  "Spain": "es",
  "St Helena": "sh",
  "Sweden": "se",
  "Switzerland": "ch",
  "Turkey": "tr",
  "Uzbekistan": "uz",
  "Vanuatu": "vu",
  "Wales": "gb-wls",
  "Zambia": "zm",
}

type FlagSize = 'xs' | 'sm' | 'md' | 'lg'

const SIZE_PX: Record<FlagSize, number> = {
  xs: 12,   // tile badges, dense lists
  sm: 16,   // H2H title, inline with player names
  md: 20,   // default
  lg: 28,   // player-page header
}

export default function FlagBadge({
  team, size = 'sm', className = '',
}: { team: string | null | undefined; size?: FlagSize; className?: string }) {
  if (!team) return null
  const code = TEAM_TO_FLAG[team]
  if (!code) return null

  const h = SIZE_PX[size]
  // flag-icons renders as 4:3 aspect (width = height * 4/3). Keep the
  // span size explicit so the flag doesn't distort inside narrow cells.
  const w = Math.round(h * 4 / 3)

  // West Indies: no ISO code. Render a small "WI" text pill in the
  // same footprint as a flag so alignment with other entries is clean.
  if (code === 'wi') {
    return (
      <span
        className={`wisden-flag-wi ${className}`}
        title={team}
        style={{
          display: 'inline-block',
          width: w,
          height: h,
          lineHeight: `${h}px`,
          textAlign: 'center',
          fontSize: `${Math.round(h * 0.55)}px`,
          fontWeight: 700,
          verticalAlign: 'middle',
          background: 'var(--accent)',
          color: 'white',
          borderRadius: 2,
          letterSpacing: '-0.02em',
        }}
      >
        WI
      </span>
    )
  }

  return (
    <span
      className={`fi fi-${code} ${className}`}
      title={team}
      style={{
        display: 'inline-block',
        width: w,
        height: h,
        verticalAlign: 'middle',
        borderRadius: 1,
        // flag-icons sets background-image; we just enforce size.
      }}
    />
  )
}
