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

import { Link } from 'react-router-dom'

type FlagSize = 'xs' | 'sm' | 'md' | 'lg'

const SIZE_PX: Record<FlagSize, number> = {
  xs: 12,   // tile badges, dense lists
  sm: 18,   // H2H title, inline with player names
  md: 22,   // default
  lg: 32,   // player-page header
}

/** Nudge flags down a touch so they sit on the serif cap-height line
 *  rather than the baseline — serif titles have tall ascenders and
 *  vertical-align: middle reads as "too low". Eyeballed per size. */
const Y_NUDGE_EM: Record<FlagSize, string> = {
  xs: '-0.05em',
  sm: '-0.12em',
  md: '-0.12em',
  lg: '-0.15em',
}

interface FlagBadgeProps {
  team: string | null | undefined
  gender?: string | null
  size?: FlagSize
  className?: string
  /** When true, wrap the flag in a Link to the team page. Requires `team`
   *  to resolve to a known code (club sides fall through as before). */
  linkTo?: boolean
}

export default function FlagBadge({
  team, gender, size = 'sm', className = '', linkTo = false,
}: FlagBadgeProps) {
  if (!team) return null
  const code = TEAM_TO_FLAG[team]
  if (!code) return null

  const h = SIZE_PX[size]
  const w = Math.round(h * 4 / 3)
  const nudge = Y_NUDGE_EM[size]

  const inner = code === 'wi' ? (
    // West Indies: no ISO code. Render a small "WI" pill.
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
        transform: `translateY(${nudge})`,
        background: 'var(--accent)',
        color: 'white',
        borderRadius: 2,
        letterSpacing: '-0.02em',
      }}
    >
      WI
    </span>
  ) : (
    <span
      className={`fi fi-${code} ${className}`}
      title={team}
      style={{
        display: 'inline-block',
        width: w,
        height: h,
        verticalAlign: 'middle',
        transform: `translateY(${nudge})`,
        borderRadius: 1,
      }}
    />
  )

  if (!linkTo) return inner

  const p = new URLSearchParams({ team })
  if (gender) p.set('gender', gender)
  p.set('team_type', 'international')
  return (
    <Link
      to={`/teams?${p.toString()}`}
      aria-label={`Go to ${team}${gender ? ` (${gender === 'female' ? "women's" : "men's"})` : ''} team page`}
      style={{ textDecoration: 'none', display: 'inline-block' }}
    >
      {inner}
    </Link>
  )
}
