import type { AgentName } from './api'

// Each agent has a fixed color, monogram, and glyph, used everywhere it appears.
export interface AgentMeta {
  name: string
  role: string
  color: string
  tint: string
  monogram: string
  glyph: React.ReactNode
}

const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' } as const

export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: {
    name: 'Boss',
    role: 'Routes tickets · final calls',
    color: '#00356b',
    tint: 'rgba(0, 53, 107, 0.08)',
    monogram: 'B',
    glyph: <svg viewBox="0 0 24 24" {...stroke}><path d="M4 18h16M5 18l-1-9 5 4 3-7 3 7 5-4-1 9" /></svg>,
  },
  inventory: {
    name: 'Inventory',
    role: 'Stock · shortfalls · vendors',
    color: '#286dc0',
    tint: 'rgba(40, 109, 192, 0.09)',
    monogram: 'I',
    glyph: <svg viewBox="0 0 24 24" {...stroke}><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" /><path d="M4 7.5l8 4.5 8-4.5M12 12v9" /></svg>,
  },
  accounting: {
    name: 'Accounting',
    role: 'Cash · margins · approvals',
    color: '#5f712d',
    tint: 'rgba(95, 113, 45, 0.1)',
    monogram: 'A',
    glyph: <svg viewBox="0 0 24 24" {...stroke}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>,
  },
  facilities: {
    name: 'Facilities',
    role: 'Leases · rent · space',
    color: '#bd5319',
    tint: 'rgba(189, 83, 25, 0.09)',
    monogram: 'F',
    glyph: <svg viewBox="0 0 24 24" {...stroke}><path d="M3 21h18M5 21V9l7-5 7 5v12" /><path d="M10 21v-6h4v6" /></svg>,
  },
  customer_service: {
    name: 'Customer Service',
    role: 'Customer drafts only',
    color: '#7a4b94',
    tint: 'rgba(122, 75, 148, 0.09)',
    monogram: 'C',
    glyph: <svg viewBox="0 0 24 24" {...stroke}><path d="M4 5h16v11H9l-5 4z" /><path d="M8 9.5h8M8 12.5h5" /></svg>,
  },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export function AgentBadge({ agent, size = 34, active = false }: { agent: AgentName; size?: number; active?: boolean }) {
  const a = AGENTS[agent]
  return (
    <span
      className={`agent-badge${active ? ' is-active' : ''}`}
      style={{ '--agent': a.color, width: size, height: size } as React.CSSProperties}
      title={a.name}
    >
      <span className="agent-badge-glyph">{a.glyph}</span>
    </span>
  )
}

export function AgentLabel({ agent }: { agent: AgentName }) {
  return <span className="agent-name" style={{ color: AGENTS[agent].color }}>{AGENTS[agent].name}</span>
}
