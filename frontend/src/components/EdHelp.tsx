/**
 * EdHelp — small table caption explaining the per-row ED subscript.
 *
 * Rendered beneath a DataTable title (or appended to an existing
 * wisden-tab-help caption) wherever TeamLink's `phraseLabel="ed"`
 * token appears in a column. Uses the same italic-serif-muted style
 * (.wisden-tab-help) as other in-tab explanatory text, so readers
 * who don't know the convention can learn it without leaving the
 * page. Convention docs: internal_docs/design-decisions.md
 * "Per-row '(ed)' tag uses row scope".
 */
export default function EdHelp({ className }: { className?: string }) {
  return (
    <div className={`wisden-tab-help${className ? ' ' + className : ''}`}>
      <span className="scope-phrase scope-phrase-ed" style={{ marginLeft: 0, marginRight: '0.25em' }}>ed</span>
      after a team name opens that team's page scoped to the row's
      edition (tournament + season of this match), independent of the
      FilterBar's season window.
    </div>
  )
}
