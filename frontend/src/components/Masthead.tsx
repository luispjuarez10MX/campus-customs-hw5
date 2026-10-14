import { longDate } from '../lib'

interface Props {
  today: string | null
  teamRunning: boolean
  pendingCount: number
  connected: boolean
  onReset: () => void
}

export function Masthead({ today, teamRunning, pendingCount, connected, onReset }: Props) {
  return (
    <header className="masthead">
      <div className="masthead-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden>CC</span>
          <div>
            <div className="brand-eyebrow">Campus Customs · New Haven</div>
            <h1 className="brand-title">Operations Desk</h1>
          </div>
        </div>

        <div className="masthead-meta">
          <div className="meta-block">
            <span className="meta-label">Shop date</span>
            <span className="meta-value">{today ? longDate(today) : '—'}</span>
          </div>
          <div className="meta-block">
            <span className="meta-label">Team</span>
            <span className={`status-pill ${!connected ? 'is-offline' : teamRunning ? 'is-live' : ''}`}>
              <span className="status-dot" />
              {!connected ? 'Backend offline' : teamRunning ? 'Working' : 'Standing by'}
            </span>
          </div>
          <div className="meta-block">
            <span className="meta-label">Signatures</span>
            <span className={`status-pill ${pendingCount ? 'is-attention' : ''}`}>
              {pendingCount ? `${pendingCount} awaiting you` : 'None pending'}
            </span>
          </div>
          <button className="btn btn-ghost-light" onClick={onReset} disabled={teamRunning}>
            Reset desk
          </button>
        </div>
      </div>
      <div className="masthead-rule" />
    </header>
  )
}
