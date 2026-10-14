import type { Cash } from '../api'
import { money, useAnimatedNumber } from '../lib'

export function CashPanel({ cash, flash }: { cash: Cash | null; flash: boolean }) {
  const balance = useAnimatedNumber(cash?.checking_balance ?? 0)
  const pending = cash?.pending_total ?? 0
  const projected = cash?.projected_after_pending ?? 0
  const total = Math.max(cash?.checking_balance ?? 0, 1)
  const pendingPct = Math.min(100, (pending / total) * 100)

  return (
    <section className={`panel cash-panel${flash ? ' is-flash' : ''}`}>
      <div className="panel-head">
        <h2 className="panel-title light">Checking</h2>
        <span className="panel-count light">Actual balance</span>
      </div>
      <div className="cash-figure">{money(balance)}</div>
      <div className="cash-note">From <code>cash_accounts</code>. It changes only when you approve a payment.</div>

      <div className="cash-bar" aria-hidden>
        <span className="cash-bar-free" style={{ width: `${100 - pendingPct}%` }} />
        <span className="cash-bar-pending" style={{ width: `${pendingPct}%` }} />
      </div>

      <dl className="cash-rows">
        <div>
          <dt><span className="swatch pending" />Awaiting approval</dt>
          <dd>{money(pending)}</dd>
        </div>
        <div>
          <dt><span className="swatch free" />Projected if all approved</dt>
          <dd className={projected < 0 ? 'neg' : ''}>{money(projected)}</dd>
        </div>
      </dl>
      <div className="cash-foot">No revenue comes in. Payments can never take cash below zero.</div>
    </section>
  )
}
