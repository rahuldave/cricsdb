/** `useDiscipline`: which side of the ball the current page shows, read from the URL. */

import { useLocation, useSearchParams } from 'react-router-dom'

/** A stat discipline, or null when the page shows none in particular. */
export type Discipline = 'batting' | 'bowling' | 'fielding' | null

/**
 * Return the active stat discipline, from the path or the `tab` URL param.
 *
 * useDiscipline — derive the active stat discipline from URL state.
 *
 * Single source of truth for "which side of the ball is the user
 * looking at right now?", used to give POV-aware phrasing for the
 * `?inning=` aux ("batted first" vs "bowled first") in
 * abbreviateScope / ScopeStatusStrip / chart + section + kicker
 * subtitles.
 *
 * Resolution order:
 *   1. Path-based — /batting, /bowling, /fielding pages pin discipline.
 *   2. Tab-based — ?tab=Batting / Bowlers / Fielding etc. on the team,
 *      venue, and tournament dossiers.
 *   3. null — no clear discipline (Overview, Compare, By Season, etc.);
 *      callers should default to batting-POV phrasing.
 *
 * Pure read of URL state via react-router-dom hooks; safe to call from
 * any component mounted under <BrowserRouter>. Stable reference between
 * URL changes via the hooks' internal memoization.
 */
export function useDiscipline(): Discipline { // 'batting', 'bowling', 'fielding', or null
  const { pathname } = useLocation()
  const [params] = useSearchParams()

  // Path identifies discipline on the dedicated player pages.
  if (pathname === '/batting') return 'batting'
  if (pathname === '/bowling') return 'bowling'
  if (pathname === '/fielding') return 'fielding'

  // Tab identifies discipline on the dossier pages. Both singular
  // ('Batting' on /teams) and plural ('Batters' on /venues, /series)
  // variants map to the same axis. Partnerships → 'batting' because a
  // partnership is intrinsically a batting concept (both batters belong
  // to the batting team; the wicket that ends it is the batting team's
  // loss); the POV-aware inning label is "batting first/second".
  const tab = params.get('tab')
  if (tab === 'Batting' || tab === 'Batters' || tab === 'Partnerships') return 'batting'
  if (tab === 'Bowling' || tab === 'Bowlers') return 'bowling'
  if (tab === 'Fielding' || tab === 'Fielders') return 'fielding'

  return null
}
