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

/** Tiered badge text per the design-decisions.md threshold table.
 *  Returns null below the 60d threshold (badge hidden — entity is
 *  active in scope). */
export function dormancyBadgeText(gapDays: number): string | null {
  if (gapDays > 365) return '(0 in 1y+)'
  if (gapDays > 180) return '(0 in 6mo)'
  if (gapDays > 60)  return '(0 in 60d)'
  return null
}
