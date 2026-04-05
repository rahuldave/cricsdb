import { useState, useEffect, useRef } from 'react'
import { searchPlayers } from '../api'
import type { PlayerSearchResult } from '../types'

interface PlayerSearchProps {
  role: 'batter' | 'bowler'
  onSelect: (player: PlayerSearchResult) => void
  placeholder?: string
}

export default function PlayerSearch({ role, onSelect, placeholder }: PlayerSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlayerSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (query.length < 2) { setResults([]); setOpen(false); return }
    setLoading(true)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      try {
        const data = await searchPlayers(query, role)
        setResults(data.players)
        setOpen(true)
      } catch { setResults([]) }
      setLoading(false)
    }, 300)
    return () => clearTimeout(timerRef.current)
  }, [query, role])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <input
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder={placeholder || `Search ${role}s...`}
        className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none"
      />
      {loading && <div className="absolute right-3 top-2.5 text-xs text-gray-400">...</div>}
      {open && results.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg max-h-60 overflow-y-auto">
          {results.map(p => (
            <li
              key={p.id}
              className="px-4 py-2 hover:bg-blue-50 cursor-pointer flex justify-between"
              onClick={() => { onSelect(p); setQuery(p.name); setOpen(false) }}
            >
              <span className="font-medium text-sm">{p.name}</span>
              <span className="text-xs text-gray-400">{p.innings} inn</span>
            </li>
          ))}
        </ul>
      )}
      {open && results.length === 0 && !loading && query.length >= 2 && (
        <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg px-4 py-3 text-sm text-gray-400">
          No players found
        </div>
      )}
    </div>
  )
}
