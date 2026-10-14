import { useEffect, useRef } from 'react'
import type { AgentEvent, AgentName } from '../api'
import { AGENTS, AgentBadge, AgentLabel } from '../agents'
import { clock } from '../lib'

interface Props {
  events: AgentEvent[]
  running: boolean
  ticketId: number | null
}

function argSummary(args: Record<string, unknown>) {
  const parts = Object.entries(args)
    .filter(([k]) => !['reason', 'body', 'note', 'requested_by', 'drafted_by', 'updated_by'].includes(k))
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
  const s = parts.join(', ')
  return s.length > 70 ? s.slice(0, 70) + '…' : s
}

function Chain({ chain }: { chain: AgentName[] }) {
  if (chain.length < 2) return null
  return (
    <span className="chain">
      {chain.map((c, i) => (
        <span key={i} style={{ color: AGENTS[c].color }}>
          {i > 0 && <span className="chain-sep">›</span>}
          {AGENTS[c].name}
        </span>
      ))}
    </span>
  )
}

function Row({ e }: { e: AgentEvent }) {
  const agent = e.agent!
  const a = AGENTS[agent]
  const style = { '--agent': a.color, '--agent-tint': a.tint } as React.CSSProperties

  if (e.type === 'user_prompt') {
    const from = e.asked_by && e.asked_by !== 'dashboard' ? (e.asked_by as AgentName) : null
    return (
      <li className="feed-row handoff" style={style}>
        <div className="handoff-line">
          {from ? <AgentLabel agent={from} /> : <span className="agent-name">Desk</span>}
          <span className="handoff-arrow">→</span>
          <AgentLabel agent={agent} />
          <span className="feed-time">{clock(e.at)}</span>
        </div>
        <p className="handoff-task">{e.text}</p>
      </li>
    )
  }

  const isEnd = e.type === 'end'
  return (
    <li className={`feed-row${isEnd ? ' is-report' : ''}`} style={style}>
      <AgentBadge agent={agent} size={32} />
      <div className="feed-body">
        <div className="feed-head">
          <AgentLabel agent={agent} />
          {isEnd && <span className="feed-kind">reported back</span>}
          {e.chain && <Chain chain={e.chain} />}
          <span className="feed-time">{clock(e.at)}</span>
        </div>
        {e.text && <p className="feed-text">{e.text}</p>}
        {!!e.mcp_tools?.length && (
          <div className="tool-chips">
            {e.mcp_tools.map((t, i) => (
              <span key={i} className="tool-chip" title={JSON.stringify(t.args, null, 1)}>
                <span className="tool-chip-tag">MCP</span>
                <span className="tool-chip-name">{t.tool}</span>
                {argSummary(t.args) && <span className="tool-chip-args">{argSummary(t.args)}</span>}
              </span>
            ))}
          </div>
        )}
        {!!e.delegations?.length && (
          <div className="tool-chips">
            {e.delegations.map((d, i) => (
              <span key={i} className="delegate-chip" style={{ '--agent': AGENTS[d.to]?.color } as React.CSSProperties}>
                Delegates to <b>{AGENTS[d.to]?.name ?? d.to}</b>
              </span>
            ))}
          </div>
        )}
      </div>
    </li>
  )
}

export function ActivityFeed({ events, running, ticketId }: Props) {
  const end = useRef<HTMLDivElement>(null)
  const shown = events.filter(e =>
    (e.type === 'user_prompt' && e.agent) ||
    (e.type === 'model_response' && e.agent && (e.text || e.mcp_tools?.length || e.delegations?.length)) ||
    (e.type === 'end' && e.agent && e.agent !== 'boss') ||
    e.type === 'error',
  )

  useEffect(() => {
    if (running) end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [shown.length, running])

  return (
    <section className="panel feed-panel">
      <div className="panel-head">
        <h2 className="panel-title">Live activity</h2>
        <span className="panel-count">
          {ticketId ? `Ticket ${ticketId}` : 'No ticket selected'}
          {running && <span className="live-tag"><span className="status-dot" />Live</span>}
        </span>
      </div>

      {shown.length === 0 ? (
        <div className="empty">
          <div className="empty-mark">◇</div>
          <p>{ticketId ? 'No run yet for this ticket. Dispatch the team to watch it work.' : 'Select a ticket to see its activity.'}</p>
        </div>
      ) : (
        <ol className="feed">
          {shown.map(e =>
            e.type === 'error' ? (
              <li key={e.id} className="feed-row is-error"><p className="feed-text">⚠ {e.text}</p></li>
            ) : (
              <Row key={e.id} e={e} />
            ),
          )}
          {running && (
            <li className="feed-row thinking">
              <span className="dots"><i /><i /><i /></span>
            </li>
          )}
        </ol>
      )}
      <div ref={end} />
    </section>
  )
}
