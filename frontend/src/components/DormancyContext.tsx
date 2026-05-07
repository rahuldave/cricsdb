/**
 * DormancyContext — page → chrome bridge for the dormancy badge.
 *
 * Each page that fetches a Distribution dossier sets the
 * `last_match_date` from `lifetime.last_match_date` here. The
 * ScopedPageHeader and ScopeStatusStrip read from the same context
 * and render the tiered badge ('(0 in 60d)' / '(0 in 6mo)' /
 * '(0 in 1y+)') when the gap from today exceeds the threshold.
 *
 * Pages without a Distribution panel never call setLastMatchDate,
 * so the context stays null and the badge stays absent. Page
 * navigation resets the context via the consumer hook (each page's
 * useEffect clears + re-sets).
 *
 * Spec: internal_docs/design-decisions.md "Dormancy badge".
 */

import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react'

interface DormancyState {
  /** ISO YYYY-MM-DD; null when the scope has no observations or page hasn't fetched. */
  lastMatchDate: string | null
  setLastMatchDate: (d: string | null) => void
}

const Ctx = createContext<DormancyState>({
  lastMatchDate: null,
  setLastMatchDate: () => {},
})

export function DormancyProvider({ children }: { children: ReactNode }) {
  const [lastMatchDate, setRaw] = useState<string | null>(null)
  // Stable setter so consumer-side useEffect deps don't churn.
  const setLastMatchDate = useCallback((d: string | null) => setRaw(d), [])
  const value = useMemo(
    () => ({ lastMatchDate, setLastMatchDate }),
    [lastMatchDate, setLastMatchDate],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useDormancy() {
  return useContext(Ctx)
}

/** Computes the dormancy gap in days. Returns 0 when last_match_date
 *  is null or in the future (clamped). Pure function — exported for
 *  unit-testing. */
export function dormancyGapDays(
  lastMatchDate: string | null,
  today: Date = new Date(),
): number {
  if (!lastMatchDate) return 0
  const last = new Date(lastMatchDate)
  if (Number.isNaN(last.getTime())) return 0
  const ms = today.getTime() - last.getTime()
  return Math.max(0, Math.floor(ms / 86400000))
}

/** Hybrid badge text — duration under 12 months, calendar over.
 *  Returns null when gap ≤ 60 days (badge hidden; entity is
 *  active in scope) or when lastMatchDate is invalid.
 *
 *  Spec: design-decisions.md "Dormancy badge" — language revised
 *  2026-05-08. Earlier `(0 in 60d/6mo/1y+)` form was data-speak;
 *  this form reads naturally:
 *    61-364 days  → "5 months since last match"
 *    ≥ 365 days   → "last match: Oct 2021"
 *  Anchoring on a date avoids the artificial ceiling that
 *  understated ABdV's 4.5-year gap as "1y+".
 */
export function dormancyBadgeText(
  gapDays: number,
  lastMatchDate: string | null,
): string | null {
  if (gapDays <= 60) return null
  if (gapDays < 365) {
    // Round to nearest month — 30.5 days/month gives 2-12 months
    // for gaps in [61, 364].
    const months = Math.max(2, Math.round(gapDays / 30.5))
    return `${months} months since last match`
  }
  // ≥ 1 year — calendar form. Reader does the math on familiar
  // year units (Oct 2021 → "that's a long time ago") instead of
  // a numeric duration that needs unpacking.
  if (!lastMatchDate) return null
  const d = new Date(lastMatchDate)
  if (Number.isNaN(d.getTime())) return null
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  // Use UTC accessors — the ISO date is date-only (no time
  // component) so the local timezone could shift it by a day
  // and flip the month at month-boundaries. UTC keeps the
  // string display stable.
  return `last match: ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
}
