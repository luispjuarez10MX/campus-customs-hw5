import type { ApprovalRequest } from '../api'
import { AGENTS, AgentBadge } from '../agents'
import { KIND_LABEL, money } from '../lib'

interface Props {
  approvals: ApprovalRequest[]
  approver: string
  setApprover: (v: string) => void
  busyId: number | null
  onApprove: (id: number) => void
  onReject: (id: number) => void
}

function what(r: ApprovalRequest) {
  if (r.kind === 'invoice') return `Invoice ${r.ref_id}`
  if (r.kind === 'rent') return `Lease ${r.ref_id}`
  return `${r.qty} × ${r.sku} · ${r.size}`
}

export function ApprovalsPanel({ approvals, approver, setApprover, busyId, onApprove, onReject }: Props) {
  const pending = approvals.filter(r => r.status === 'pending')
  const decided = approvals.filter(r => r.status !== 'pending').slice().reverse()
  const named = approver.trim().length > 0

  return (
    <section className={`panel approvals-panel${pending.length ? ' has-pending' : ''}`}>
      <div className="panel-head">
        <h2 className="panel-title">Awaiting your signature</h2>
        <span className={`count-badge${pending.length ? ' is-hot' : ''}`}>{pending.length}</span>
      </div>

      <label className="approver">
        <span>Approving as</span>
        <input value={approver} onChange={e => setApprover(e.target.value)} placeholder="Your name" />
      </label>

      {pending.length === 0 ? (
        <p className="quiet">Nothing to sign. Agents can only prepare requests; money moves only when you approve one here.</p>
      ) : (
        <ul className="approval-list">
          {pending.map(r => (
            <li key={r.id} className="approval-card" style={{ '--agent': AGENTS[r.requested_by]?.color } as React.CSSProperties}>
              <div className="approval-top">
                <span className="approval-kind">{KIND_LABEL[r.kind]} · #{r.id}</span>
                {r.ticket_id && <span className="approval-ticket">Ticket {r.ticket_id}</span>}
              </div>
              <div className="approval-amount">{money(r.amount, true)}</div>
              <div className="approval-what">{what(r)}</div>
              <p className="approval-reason">{r.reason}</p>
              <div className="approval-by">
                <AgentBadge agent={r.requested_by} size={22} />
                Prepared by {AGENTS[r.requested_by]?.name ?? r.requested_by}
              </div>
              <div className="approval-actions">
                <button className="btn btn-primary" disabled={!named || busyId === r.id} onClick={() => onApprove(r.id)}>
                  {busyId === r.id ? 'Signing…' : 'Approve'}
                </button>
                <button className="btn btn-ghost" disabled={!named || busyId === r.id} onClick={() => onReject(r.id)}>
                  Reject
                </button>
              </div>
              {!named && <div className="approval-hint">Enter your name to sign.</div>}
            </li>
          ))}
        </ul>
      )}

      {decided.length > 0 && (
        <details className="decided">
          <summary>History · {decided.length}</summary>
          <ul>
            {decided.map(r => (
              <li key={r.id}>
                <span className={`decided-tag ${r.status}`}>{r.status}</span>
                {KIND_LABEL[r.kind]} #{r.id} · {money(r.amount, true)}
                <span className="decided-by">by {r.decided_by}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
