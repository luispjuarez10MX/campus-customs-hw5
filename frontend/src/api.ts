// Typed client for the FastAPI backend (backend/main.py).
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface LastRun {
  run_id: string
  status: 'running' | 'done' | 'failed'
  started_at?: string
  finished_at?: string
}

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  is_resolved: boolean
  team_resolved: boolean
  last_run: LastRun | null
}

export interface ToolUse { tool: string; args: Record<string, unknown> }
export interface Delegation { to: AgentName; ticket_id?: number; task: string }

export interface AgentEvent {
  id: number
  at: string
  run_id: string | null
  agent: AgentName | null
  chain: AgentName[] | null
  type: 'run_start' | 'reset' | 'human_decision' | 'user_prompt' | 'model_response' | 'model_request' | 'end' | 'error' | 'run_end'
  text?: string | null
  asked_by?: string
  ticket_id?: number | null
  status?: 'done' | 'failed'
  mcp_tools?: ToolUse[]
  delegations?: Delegation[]
  final_answer?: boolean
  tool_results?: { tool: string; content: string }[]
  usage?: { requests: number; tool_calls: number; input_tokens: number; output_tokens: number }
}

export interface ApprovalRequest {
  id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number | null
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  ticket_id: number | null
  reason: string
  requested_by: AgentName
  requested_on: string
  status: 'pending' | 'approved' | 'rejected'
  decided_by: string | null
  decided_on: string | null
  payment_id: number | null
  expected_arrival: string | null
}

export interface Cash {
  today: string
  checking_balance: number
  pending_total: number
  projected_after_pending: number
}

export interface TicketOutcome {
  ticket_id: number
  handled_by: AgentName[]
  decision: string
  status: string
  approval_request_ids: number[]
  draft_ids: number[]
  next_step: string
}

export interface RunInfo {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'failed'
  report: { summary: string; tickets: TicketOutcome[]; cash_plan: string; pending_human_approvals: number[] } | null
  error: string | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return body as T
}

export const api = {
  tickets: () => request<{ today: string; tickets: Ticket[] }>('/api/tickets'),
  runTicket: (id: number) => request<{ run_id: string }>(`/api/tickets/${id}/run`, { method: 'POST' }),
  run: (runId: string) => request<RunInfo>(`/api/runs/${runId}`),
  events: (since = -1, limit = 400) =>
    request<{ last_id: number; events: AgentEvent[] }>(`/api/events?since=${since}&limit=${limit}`),
  approvals: () => request<{ requests: ApprovalRequest[] }>('/api/approvals'),
  approve: (id: number, decidedBy: string) =>
    request<{ ok: boolean; checking_balance: number; ticket_resolved: number | null }>(`/api/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ decided_by: decidedBy }),
    }),
  reject: (id: number, decidedBy: string, note = '') =>
    request<{ ok: boolean }>(`/api/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ decided_by: decidedBy, note }),
    }),
  cash: () => request<Cash>('/api/cash'),
  reset: () => request<{ ok: boolean }>('/api/reset', { method: 'POST' }),
  health: () => request<{ ok: boolean; team_running: boolean }>('/api/health'),
}
