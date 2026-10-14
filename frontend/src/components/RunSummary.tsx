import type { AgentEvent, AgentName, RunInfo } from '../api'
import { AGENTS, AGENT_ORDER, AgentBadge } from '../agents'
import { BOSS_STATUS } from '../lib'

interface Props {
  events: AgentEvent[]
  run: RunInfo | null
  ticketId: number | null
}

export function RunSummary({ events, run, ticketId }: Props) {
  const end = events.find(e => e.type === 'run_end')
  if (!end) return null

  // What each agent reported back (an agent may be called more than once).
  const reports = new Map<AgentName, string[]>()
  const tools = new Map<AgentName, Set<string>>()
  for (const e of events) {
    if (!e.agent) continue
    if (e.type === 'end' && e.text) reports.set(e.agent, [...(reports.get(e.agent) ?? []), e.text])
    for (const t of e.mcp_tools ?? []) tools.set(e.agent, (tools.get(e.agent) ?? new Set()).add(t.tool))
  }
  const outcome = run?.report?.tickets.find(t => t.ticket_id === ticketId)

  return (
    <section className="panel summary-panel">
      <div className="panel-head">
        <h2 className="panel-title">Run summary</h2>
        <span className="panel-count">
          {end.status === 'failed' ? 'Failed' : 'Complete'}
          {end.usage && ` · ${end.usage.requests} model calls · ${end.delegations} handoffs`}
        </span>
      </div>

      {outcome && (
        <div className="decision">
          <div className="decision-label">The Boss's call · <span className={`boss-status s-${outcome.status}`}>{BOSS_STATUS[outcome.status] ?? outcome.status}</span></div>
          <p className="decision-text">{outcome.decision}</p>
          <p className="decision-next"><b>Next:</b> {outcome.next_step}</p>
        </div>
      )}

      <div className="summary-grid">
        {AGENT_ORDER.filter(a => reports.has(a)).map((a, i) => (
          <article key={a} className="summary-card" style={{ '--agent': AGENTS[a].color, '--agent-tint': AGENTS[a].tint, animationDelay: `${i * 80}ms` } as React.CSSProperties}>
            <header>
              <AgentBadge agent={a} size={30} />
              <span className="summary-name">{AGENTS[a].name}</span>
            </header>
            <p>{reports.get(a)!.at(-1)}</p>
            {tools.has(a) && (
              <div className="summary-tools">
                {[...tools.get(a)!].map(t => <code key={t}>{t}</code>)}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
