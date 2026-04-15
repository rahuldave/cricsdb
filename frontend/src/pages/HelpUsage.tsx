import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import userHelpMd from '../content/user-help.md?raw'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

// /help/usage — renders frontend/src/content/user-help.md.
// Editable by the site maintainer; rebuilt on next `npm run build`.
export default function HelpUsage() {
  useDocumentTitle('How to use CricsDB')

  return (
    <div className="wisden-page" style={{ maxWidth: '48rem', margin: '0 auto' }}>
      <div className="kicker">
        <Link to="/help" className="comp-link">← Back to About &amp; Help</Link>
      </div>
      <div className="markdown-body">
        <ReactMarkdown>{userHelpMd}</ReactMarkdown>
      </div>
    </div>
  )
}
