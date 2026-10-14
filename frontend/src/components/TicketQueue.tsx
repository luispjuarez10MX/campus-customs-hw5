import type { ApprovalRequest, Ticket } from '../api'
import { BOSS_STATUS, TICKET_TYPES } from '../lib'

interface Props {
  tickets: Ticket[]
  approvals: ApprovalRequest[]
  selectedId: number | null
  teamRunning: boolean
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

function detail(t: Ticket) {
  if (t.sku) return `${t.qty} × ${t.sku} · ${t.size}`
  if (t.lease_id) return `Lease ${t.lease_id}`
  return null
}

export function TicketQueue({ tickets, approvals, selectedId, teamRunning, onSelect, onRun }: Props) {
  return (
    <section className="panel ticket-queue">
      <div className="panel-head">
        <h2 className="panel-title">Ticket board</h2>
        <span className="panel-count">{tickets.filter(t => !t.team_resolved).length} open</span>
      </div>

      <ol className="ticket-list">
        {tickets.map((t, i) => {
          const running = t.last_run?.status === 'running'
          // Once you've signed every request for this ticket, say so next to the Boss's last status.
          const mine = approvals.filter(a => a.ticket_id === t.id)
          const signed = t.status === 'waiting_on_approval' && mine.length > 0 && mine.every(a => a.status !== 'pending')
          const selected = t.id === selectedId
          return (
            <li
              key={t.id}
              className={`ticket${selected ? ' is-selected' : ''}${t.team_resolved ? ' is-resolved' : ''}${running ? ' is-running' : ''}`}
              style={{ animationDelay: `${120 + i * 90}ms` }}
              onClick={() => onSelect(t.id)}
            >
              <div className="ticket-top">
                <span className="ticket-id">No. {t.id}</span>
                <span className="ticket-type">{TICKET_TYPES[t.type] ?? t.type}</span>
              </div>
              <h3 className="ticket-subject">{t.subject}</h3>
              <div className="ticket-requester">{t.requester}</div>
              {detail(t) && <div className="ticket-detail">{detail(t)}</div>}

              <div className="ticket-foot">
                {t.team_resolved ? (
                  <span className="resolved-seal">
                    <svg viewBox="0 0 24 24" aria-hidden><path d="M5 12.5l4.2 4.2L19 7" /></svg>
                    Resolved
                  </span>
                ) : running ? (
                  <span className="running-tag"><span className="status-dot" />Team working</span>
                ) : (
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={teamRunning}
                    onClick={e => { e.stopPropagation(); onRun(t.id) }}
                  >
                    Dispatch team <span aria-hidden>→</span>
                  </button>
                )}
                {signed ? (
                  <span className="boss-status s-approved" title="You decided every approval request for this ticket">
                    {mine.every(a => a.status === 'approved') ? 'Approved by you' : 'Decided by you'}
                  </span>
                ) : (
                  <span className={`boss-status s-${t.status}`} title="The Boss's status for this ticket">
                    {BOSS_STATUS[t.status] ?? t.status}
                  </span>
                )}
              </div>
              {t.team_resolved && <div className="ticket-ribbon" aria-hidden />}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
