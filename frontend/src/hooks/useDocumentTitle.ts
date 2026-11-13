/** `useDocumentTitle`: set the browser tab's title for a page. */
import { useEffect } from 'react'

const SUFFIX = 'T20 & CricsDB'

/**
 * Set the document title to the page's subject followed by the site name.
 *
 * Set document.title for the current page. Pass the page-specific
 * subject (e.g. a player name); the suffix is appended automatically.
 * Pass null while data is loading to leave the title alone — that
 * avoids a "T20 CricsDB" flash before the real title arrives.
 * @param subject the page's subject, such as a player's name; '' for the site name alone; null or undefined to leave the title
 */
export function useDocumentTitle(subject: string | null | undefined): void {
  useEffect(() => {
    if (subject == null) return
    document.title = subject ? `${subject} — ${SUFFIX}` : SUFFIX
  }, [subject])
}
