import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import aboutMeMd from '../content/about-me.md?raw'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

// The /help route. Three sections:
// 1. About CricsDB — fixed intro (data source + known gap).
// 2. About me — pulled from about-me.md so the site maintainer can
//    edit that file directly.
// 3. See also — links to user guide (/help/usage) and API refs.
//
// Kept intentionally simple: no fetches, one external dependency
// (react-markdown). Styles lean on the existing .wisden-* classes.

export default function Help() {
  useDocumentTitle('About & Help')

  return (
    <div className="wisden-page" style={{ maxWidth: '48rem', margin: '0 auto' }}>
      <header style={{ marginBottom: '2rem' }}>
        <div className="kicker">About this site</div>
        <h1 className="wisden-page-title" style={{ marginTop: '0.25rem' }}>
          CricsDB — About &amp; Help
        </h1>
        <div className="rule-double" />
      </header>

      <section style={{ marginBottom: '2.5rem' }}>
        <h2 className="wisden-section-title" style={{ textAlign: 'left' }}>
          What this is
        </h2>
        <p>
          CricsDB is a T20-cricket analytics site built from the
          ball-by-ball data that{' '}
          <a href="https://cricsheet.org" target="_blank" rel="noopener">
            cricsheet.org
          </a>{' '}
          publishes openly under an ODC-BY 1.0 licence. Every number on
          the site — every average, every strike rate, every
          partnership — is derived from the roughly 2.95 million
          deliveries cricsheet has released for men's and women's
          T20s since 2005.
        </p>
        <p>
          Coverage spans international T20Is (men's and women's) plus
          18+ franchise competitions (IPL, BBL, CPL, PSL, The Hundred,
          Vitality Blast, WBBL, WPL, and more). See the Teams page
          directory for the full list in whatever scope you pick.
        </p>
        <p>
          <strong>Known gap: Afghanistan cricket is not in the
          dataset.</strong> Cricsheet has historically not published
          Afghanistan men's or women's T20 matches. Every other
          ICC full-member nation is present. If cricsheet starts
          carrying Afghanistan, a rebuild will pick it up
          automatically. See{' '}
          <a href="https://cricsheet.org" target="_blank" rel="noopener">
            cricsheet.org
          </a>{' '}
          for details.
        </p>
        <p>
          The site is a spare-time project by one person
          (see <a href="#about-me" className="comp-link">About me</a> below).
          It's not affiliated with cricsheet, Cricinfo, the ICC, or
          any cricket board.
        </p>
      </section>

      <section id="about-me" style={{ marginBottom: '2.5rem' }}>
        <div className="markdown-body">
          <ReactMarkdown>{aboutMeMd}</ReactMarkdown>
        </div>
      </section>

      <section style={{ marginBottom: '2rem' }}>
        <h2 className="wisden-section-title" style={{ textAlign: 'left' }}>
          See also
        </h2>
        <ul className="wisden-link-list">
          <li>
            <Link to="/help/usage" className="comp-link">
              How to use the site
            </Link>{' '}
            — filter bar, landing defaults, what each tab means.
          </li>
          <li>
            <a href="/docs" target="_blank" rel="noopener" className="comp-link">
              Interactive API docs
            </a>{' '}
            — Swagger UI auto-generated from the FastAPI routes. Click
            any endpoint to try it out in the browser.
          </li>
          <li>
            <a
              href="https://github.com/rahuldave/cricsdb/blob/main/docs/api.md"
              target="_blank"
              rel="noopener"
              className="comp-link"
            >
              API reference (narrative)
            </a>{' '}
            — a plain-English walk-through of every endpoint with
            example curls and responses. Companion to the Swagger
            docs.
          </li>
          <li>
            <a
              href="https://github.com/rahuldave/cricsdb"
              target="_blank"
              rel="noopener"
              className="comp-link"
            >
              Source code on GitHub
            </a>{' '}
            — issues, questions, contributions welcome.
          </li>
        </ul>
      </section>
    </div>
  )
}
