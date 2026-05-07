/**
 * Quick-start chip row rendered below the PlayerSearch on
 * /batting, /bowling, /fielding. Curated marquee names per
 * discipline so first-time visitors have a one-click path to
 * a populated dossier rather than staring at an empty search.
 *
 * Each chip is a pure URL link — preserves any FilterBar +
 * inning-aux state already set by the user via `?...&player=ID`
 * append rather than reset (mirrors PlayerSearch.handleSelect).
 *
 * Names + IDs picked for: T20-prominent across multiple eras
 * (no all-IPL or all-international monoculture); mix of
 * nationalities; for fielding tab, mix of keepers + outfielders.
 */

import { Link, useSearchParams } from 'react-router-dom'

export type QuickStartDiscipline = 'batting' | 'bowling' | 'fielding'

interface Suggestion {
  id: string
  name: string
}

const SUGGESTIONS: Record<QuickStartDiscipline, Suggestion[]> = {
  batting: [
    { id: 'ba607b88', name: 'V Kohli' },
    { id: '740742ef', name: 'RG Sharma' },
    { id: '99b75528', name: 'JC Buttler' },
    { id: 'c4487b84', name: 'AB de Villiers' },
    { id: 'dcce6f09', name: 'DA Warner' },
    { id: '30a45b23', name: 'SPD Smith' },
  ],
  bowling: [
    { id: '462411b3', name: 'JJ Bumrah' },
    { id: '5f547c8b', name: 'Rashid Khan' },
    { id: 'a818c1be', name: 'TA Boult' },
    { id: '3fb19989', name: 'MA Starc' },
    { id: '495d42a5', name: 'R Ashwin' },
    { id: '9d430b40', name: 'SP Narine' },
  ],
  fielding: [
    { id: '4a8a2e3b', name: 'MS Dhoni' },
    { id: '372455c4', name: 'Q de Kock' },
    { id: '99b75528', name: 'JC Buttler' },
    { id: '919a3be2', name: 'RR Pant' },
    { id: 'ba607b88', name: 'V Kohli' },
    { id: 'c4487b84', name: 'AB de Villiers' },
  ],
}

interface Props {
  discipline: QuickStartDiscipline
  basePath: string  // e.g. '/batting'
}

export default function PlayerQuickStart({ discipline, basePath }: Props) {
  const [searchParams] = useSearchParams()
  const suggestions = SUGGESTIONS[discipline]

  function buildHref(id: string): string {
    const sp = new URLSearchParams(searchParams)
    sp.set('player', id)
    return `${basePath}?${sp.toString()}`
  }

  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'baseline',
      gap: '0.4rem',
      fontFamily: 'var(--serif)',
      fontStyle: 'italic',
      fontSize: '0.82rem',
      color: 'var(--ink-faint)',
    }}>
      <span>Try:</span>
      {suggestions.map((s, i) => (
        <span key={s.id} style={{ display: 'inline-flex', alignItems: 'baseline', gap: '0.4rem' }}>
          <Link
            to={buildHref(s.id)}
            className="comp-link"
            style={{ color: 'var(--ink)', fontStyle: 'normal' }}
          >
            {s.name}
          </Link>
          {i < suggestions.length - 1 && <span style={{ color: 'var(--ink-faint)' }}>·</span>}
        </span>
      ))}
    </div>
  )
}
