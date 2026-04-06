import { useEffect } from 'react'

const SUFFIX = 'T20 CricsDB'

/**
 * Set document.title for the current page. Pass the page-specific
 * subject (e.g. a player name); the suffix is appended automatically.
 * Pass null while data is loading to leave the title alone — that
 * avoids a "T20 CricsDB" flash before the real title arrives.
 */
export function useDocumentTitle(subject: string | null | undefined): void {
  useEffect(() => {
    if (subject == null) return
    document.title = subject ? `${subject} — ${SUFFIX}` : SUFFIX
  }, [subject])
}
