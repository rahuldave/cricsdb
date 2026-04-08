import type React from 'react'
import { Link } from 'react-router-dom'
import { getMatches } from '../api'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'

function CompLink({ event, children }: { event: string; children: React.ReactNode }) {
  return (
    <Link to={`/matches?tournament=${encodeURIComponent(event)}`} className="comp-link">
      {children}
    </Link>
  )
}

export default function Home() {
  useDocumentTitle('')
  const { data, loading, error, refetch } = useFetch(
    () => getMatches({ limit: 5, offset: 0 }),
    [],
  )
  const recent = data?.matches ?? []

  return (
    <div className="wisden-page">
      {/* Masthead */}
      <header className="masthead">
        <div className="kicker">Est. 2024 · A T20 Almanack</div>
        <h1 className="title">
          T20 <span className="title-amp">&amp;</span> CricsDB
        </h1>
        <div className="rule-double" />
        <p className="standfirst">
          An almanack of Twenty20 cricket — twelve thousand nine hundred and forty matches,
          two million nine hundred and fifty thousand deliveries, one hundred and sixty
          thousand wickets — drawn from international and club competition the world over.
        </p>
      </header>

      {/* Coverage — surfaces the league links high so users can jump
          straight to IPL / BBL / etc. without scrolling past fixtures. */}
      <section className="wisden-section">
        <div className="section-head">
          <span className="section-label">In the Volume</span>
        </div>
        <div className="rule" />
        <div className="coverage">
          <div className="coverage-col">
            <div className="coverage-head">International</div>
            <div>Men's &amp; Women's T20Is</div>
            <div>
              <CompLink event="ICC Men's T20 World Cup">T20 World Cup</CompLink>,{' '}
              <CompLink event="Men's T20 Asia Cup">Asia Cup</CompLink>
            </div>
            <div>Bilateral series</div>
          </div>
          <div className="coverage-col">
            <div className="coverage-head">Major Leagues</div>
            <div>
              <CompLink event="Indian Premier League">IPL</CompLink>,{' '}
              <CompLink event="Big Bash League">BBL</CompLink>,{' '}
              <CompLink event="Pakistan Super League">PSL</CompLink>,{' '}
              <CompLink event="Caribbean Premier League">CPL</CompLink>
            </div>
            <div>
              <CompLink event="The Hundred Men's Competition">The Hundred</CompLink>,{' '}
              <CompLink event="Vitality Blast">Vitality Blast</CompLink>
            </div>
            <div>
              <CompLink event="Women's Premier League">WPL</CompLink>,{' '}
              <CompLink event="Women's Big Bash League">WBBL</CompLink>, and{' '}
              <Link to="/matches" className="comp-link">others</Link>
            </div>
          </div>
          <div className="coverage-col coverage-stats">
            <div className="coverage-head">The Record</div>
            <div>
              <span className="big-num num">12,940</span>
              <span className="big-num-label">matches</span>
            </div>
            <div>
              <span className="big-num num">2.95M</span>
              <span className="big-num-label">deliveries</span>
            </div>
            <div>
              <span className="big-num num">160K</span>
              <span className="big-num-label">wickets</span>
            </div>
          </div>
        </div>
      </section>

      {/* Recent fixtures */}
      <section className="wisden-section">
        <div className="section-head">
          <span className="section-label">From the Recent Fixtures</span>
          <Link to="/matches" className="section-more">All matches →</Link>
        </div>
        <div className="rule" />

        {loading && <Spinner label="Loading recent matches…" />}
        {error && !loading && (
          <ErrorBanner
            message={`Could not load recent matches: ${error}`}
            onRetry={refetch}
          />
        )}
        {!loading && !error && recent.length > 0 && (
          <ol className="fixtures">
            {recent.map((m) => (
              <li key={m.match_id} className="fixture">
                <Link to={`/matches/${m.match_id}`} className="fixture-link">
                  <div className="fixture-row">
                    <div className="fixture-teams">
                      <span className="team">{m.team1}</span>
                      <span className="versus"> v </span>
                      <span className="team">{m.team2}</span>
                    </div>
                    <div className="fixture-date num">{m.date}</div>
                  </div>
                  <div className="fixture-meta">
                    {m.tournament}
                    {m.city ? ` · ${m.city}` : ''}
                  </div>
                  <div className="fixture-result">
                    {m.result_text}
                    {(m.team1_score || m.team2_score) && (
                      <span className="fixture-scores">
                        {' — '}
                        {m.team1_score && (
                          <>
                            {m.team1} <span className="num">{m.team1_score}</span>
                          </>
                        )}
                        {m.team1_score && m.team2_score && ', '}
                        {m.team2_score && (
                          <>
                            {m.team2} <span className="num">{m.team2_score}</span>
                          </>
                        )}
                      </span>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Departments */}
      <section className="wisden-section">
        <div className="section-head">
          <span className="section-label">The Departments</span>
        </div>
        <div className="rule" />
        <dl className="departments">
          <Link to="/batting" className="dept">
            <dt>Batting</dt>
            <dd>
              Career records, strike rates by over and phase, bowler matchups,
              dismissal analysis, and inter-wicket performance for upwards of ten
              thousand batters.
            </dd>
          </Link>
          <div className="rule-thin" />
          <Link to="/bowling" className="dept">
            <dt>Bowling</dt>
            <dd>
              Economy, wickets, batter matchups, modes of dismissal, and over-by-over
              analysis for seven thousand four hundred bowlers.
            </dd>
          </Link>
          <div className="rule-thin" />
          <Link to="/teams" className="dept">
            <dt>Teams</dt>
            <dd>
              Win and loss records, head-to-head encounters, and season-by-season
              results for three hundred and twenty-two sides across international and
              club cricket.
            </dd>
          </Link>
          <div className="rule-thin" />
          <Link to="/head-to-head" className="dept">
            <dt>Head to Head</dt>
            <dd>
              A close reading of any batter against any bowler: phase breakdowns,
              season trends, and a complete match-by-match record.
            </dd>
          </Link>
        </dl>
      </section>

      <div className="rule-double" />
      <footer className="colophon">
        Compiled from <a href="https://cricsheet.org" target="_blank" rel="noopener">Cricsheet</a>{' '}
        under the ODC-BY 1.0 licence. Built with deebase, FastAPI, React, and Semiotic.
      </footer>
    </div>
  )
}
