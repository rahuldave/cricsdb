import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

function siteStatsMeta(): Plugin {
  return {
    name: 'site-stats-meta',
    transformIndexHtml(html) {
      const path = resolve(import.meta.dirname, 'src/generated/site-stats.json')
      const stats = JSON.parse(readFileSync(path, 'utf-8')) as {
        totals: { matches: number; deliveries: number; wickets: number }
      }
      const matches = new Intl.NumberFormat('en-US').format(stats.totals.matches)
      const deliveries = `${(stats.totals.deliveries / 1_000_000).toFixed(2)}M`
      return html
        .replaceAll('__SITE_MATCHES__', matches)
        .replaceAll('__SITE_DELIVERIES__', deliveries)
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), siteStatsMeta()],
  server: {
    // `host: true` binds to BOTH IPv4 and IPv6 instead of vite's
    // default IPv6-only `localhost`. Safari prefers IPv4 and gets
    // ECONNREFUSED on the default binding; curl/agent-browser pick
    // IPv6 and work. User-flagged 2026-05-08 ("safari can't make a
    // connection to localhost").
    host: true,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
