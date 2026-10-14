import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, type AgentEvent, type AgentName, type ApprovalRequest, type Cash, type RunInfo, type Ticket } from './api'
import { ActivityFeed } from './components/ActivityFeed'
import { AgentRoster } from './components/AgentRoster'
import { ApprovalsPanel } from './components/ApprovalsPanel'
import { CashPanel } from './components/CashPanel'
import { Masthead } from './components/Masthead'
import { RunSummary } from './components/RunSummary'
import { TicketQueue } from './components/TicketQueue'
import { money, usePolling } from './lib'

type Toast = { tone: 'ok' | 'error' | 'info'; text: string }

export default function App() {
  const [today, setToday] = useState<string | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [runs, setRuns] = useState<Record<string, RunInfo>>({})
  // `?ticket=101` opens the dashboard on that ticket (handy for links and screenshots).
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(new URLSearchParams(location.search).get('ticket')) || null)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [connected, setConnected] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [cashFlash, setCashFlash] = useState(false)
  const [toast, setToast] = useState<Toast | null>(null)
  const [approver, setApprover] = useState(() => localStorage.getItem('cc-approver') ?? '')
  const lastEventId = useRef(-1)

  useEffect(() => localStorage.setItem('cc-approver', approver), [approver])
  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 5200)
    return () => clearTimeout(id)
  }, [toast])

  const refreshDesk = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()])
      setToday(t.today)
      setTickets(t.tickets)
      setCash(c)
      setApprovals(a.requests)
      setConnected(true)
      setSelectedId(cur => cur ?? (t.tickets.find(x => !x.team_resolved) ?? t.tickets[0])?.id ?? null)
    } catch {
      setConnected(false)
    }
  }, [])

  const pullEvents = useCallback(async () => {
    try {
      const d = await api.events(lastEventId.current, 1000)
      if (d.events.length) setEvents(prev => [...prev, ...d.events])
      lastEventId.current = Math.max(lastEventId.current, d.last_id)
    } catch {
      setConnected(false)
    }
  }, [])

  const teamRunning = activeRunId !== null || tickets.some(t => t.last_run?.status === 'running')

  usePolling(async () => {
    await Promise.all([pullEvents(), refreshDesk()])
    if (!activeRunId) return
    const info = await api.run(activeRunId).catch(() => null)
    if (!info || info.status === 'running') return
    setRuns(r => ({ ...r, [info.run_id]: info }))
    setActiveRunId(null)
    await Promise.all([pullEvents(), refreshDesk()])
    setToast(
      info.status === 'done'
        ? { tone: 'ok', text: `Ticket ${info.ticket_id} resolved by the team.` }
        : { tone: 'error', text: `Run on ticket ${info.ticket_id} failed: ${info.error}` },
    )
  }, teamRunning ? 1400 : 5000, [teamRunning, activeRunId])

  const selected = tickets.find(t => t.id === selectedId) ?? null
  const viewRunId = selected?.last_run?.run_id ?? null
  const runEvents = useMemo(() => events.filter(e => e.run_id && e.run_id === viewRunId), [events, viewRunId])
  const viewRunning = selected?.last_run?.status === 'running'

  // Load the Boss's report for a finished run if we don't have it yet (lost if the backend restarted).
  useEffect(() => {
    if (!viewRunId || runs[viewRunId] || selected?.last_run?.status !== 'done') return
    api.run(viewRunId).then(info => setRuns(r => ({ ...r, [info.run_id]: info }))).catch(() => {})
  }, [viewRunId, runs, selected?.last_run?.status])

  const activeAgent = useMemo<AgentName | null>(() => {
    if (!viewRunning) return null
    const last = [...runEvents].reverse().find(e => e.agent)
    if (!last) return 'boss'
    if (last.type === 'end' && last.chain && last.chain.length > 1) return last.chain[last.chain.length - 2]
    return last.agent
  }, [runEvents, viewRunning])
  const involved = useMemo(() => new Set(runEvents.flatMap(e => (e.agent ? [e.agent] : []))), [runEvents])

  async function runTicket(id: number) {
    setSelectedId(id)
    try {
      const r = await api.runTicket(id)
      setActiveRunId(r.run_id)
      setToast({ tone: 'info', text: `Team dispatched on ticket ${id}.` })
      setTimeout(() => { refreshDesk(); pullEvents() }, 400)
    } catch (err) {
      setToast({ tone: 'error', text: (err as Error).message })
    }
  }

  async function decide(id: number, approve: boolean) {
    setBusyId(id)
    try {
      if (approve) {
        const r = await api.approve(id, approver.trim())
        setCashFlash(true)
        setTimeout(() => setCashFlash(false), 1600)
        setToast({ tone: 'ok', text: `Request #${id} approved. Checking is now ${money(r.checking_balance)}.` + (r.ticket_resolved ? ` Ticket ${r.ticket_resolved} resolved: all approvals granted.` : '') })
      } else {
        await api.reject(id, approver.trim())
        setToast({ tone: 'info', text: `Request #${id} rejected. No money moved.` })
      }
      await refreshDesk()
    } catch (err) {
      setToast({ tone: 'error', text: (err as Error).message })
    } finally {
      setBusyId(null)
    }
  }

  async function resetDesk() {
    if (!confirm('Reset the working database to the original state? Approvals and drafts are cleared; the audit trail is kept.')) return
    try {
      await api.reset()
      setRuns({})
      await Promise.all([refreshDesk(), pullEvents()])
      setToast({ tone: 'info', text: 'Desk reset to the original database.' })
    } catch (err) {
      setToast({ tone: 'error', text: (err as Error).message })
    }
  }

  const pendingCount = approvals.filter(a => a.status === 'pending').length

  return (
    <div className="app">
      <Masthead today={today} teamRunning={teamRunning} pendingCount={pendingCount} connected={connected} onReset={resetDesk} />

      <main className="desk">
        <aside className="col col-left">
          <TicketQueue tickets={tickets} approvals={approvals} selectedId={selectedId} teamRunning={teamRunning} onSelect={setSelectedId} onRun={runTicket} />
        </aside>

        <div className="col col-center">
          <AgentRoster active={activeAgent} involved={involved} />
          <ActivityFeed events={runEvents} running={viewRunning} ticketId={selectedId} />
          {!viewRunning && <RunSummary events={runEvents} run={viewRunId ? runs[viewRunId] ?? null : null} ticketId={selectedId} />}
        </div>

        <aside className="col col-right">
          <CashPanel cash={cash} flash={cashFlash} />
          <ApprovalsPanel
            approvals={approvals}
            approver={approver}
            setApprover={setApprover}
            busyId={busyId}
            onApprove={id => decide(id, true)}
            onReject={id => decide(id, false)}
          />
        </aside>
      </main>

      <footer className="colophon">
        <span>Campus Customs Operations Desk · MGT 409 · Homework 5</span>
        <span>Agents prepare. Humans approve. Every step is in the audit trail.</span>
      </footer>

      {toast && <div key={toast.text} className={`toast ${toast.tone}`} role="status">{toast.text}</div>}
    </div>
  )
}
