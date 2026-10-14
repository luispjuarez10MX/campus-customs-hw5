import type { AgentName } from '../api'
import { AGENTS, AGENT_ORDER, AgentBadge } from '../agents'

interface Props {
  active: AgentName | null
  involved: Set<AgentName>
}

export function AgentRoster({ active, involved }: Props) {
  return (
    <div className="roster">
      {AGENT_ORDER.map(name => {
        const a = AGENTS[name]
        const isActive = active === name
        return (
          <div
            key={name}
            className={`roster-agent${isActive ? ' is-active' : ''}${involved.has(name) ? ' is-involved' : ''}`}
            style={{ '--agent': a.color, '--agent-tint': a.tint } as React.CSSProperties}
          >
            <AgentBadge agent={name} size={38} active={isActive} />
            <div className="roster-text">
              <span className="roster-name">{a.name}</span>
              <span className="roster-role">{isActive ? 'Working…' : a.role}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
