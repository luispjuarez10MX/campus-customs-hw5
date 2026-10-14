# Campus Customs – Agent Harness

A multi-agent operations team for Campus Customs, a Yale apparel shop. Five PydanticAI agents (`gpt-6-luna` through Portkey) work the ticket board. All shop data goes through a FastMCP server over the SQLite database. A FastAPI backend runs the team and exposes human approvals, and a React dashboard lets a person watch the agents and sign payments.

```
React dashboard (frontend/, :5173)
        │  HTTP (polls tickets, events, cash, approvals)
FastAPI backend (backend/main.py, :8000) ── runs ──► Agent team (backend/agents.py)
        │                                               │ MCP over stdio (agent tool allowlists)
        │ approver MCP process (human routes only)      ▼
        └──────────────────────────────────────► MCP server (mcp_server/server.py)
                                                        │
                                              data/campus_customs_new.db
```

**Run it** (from the project root `hw5/`, after `python -m venv .venv && .venv/bin/pip install -r requirements.txt` and `cd frontend && npm install`):

| What | Command |
|---|---|
| Backend | `cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000` |
| Dashboard | `cd frontend && npm run dev`, then open http://localhost:5173 |
| Agent activity in a terminal (optional) | `.venv/bin/python backend/watch_agents.py` |
| Reset the working DB | Dashboard **Reset desk**, `POST /api/reset`, or `.venv/bin/python -m backend.reset_db` |
| Whole team from the CLI | `.venv/bin/python -m backend.run --reset` |

The API key (`PORTKEY_API_KEY`) is read from the nearest `.env`: this folder's (copied from `.env.example`) or the shared course-root one. `.env` is git-ignored and never stored in this repo.

## Databases

- `data/campus_customs.db`: untouched original, kept read-only. Used only to reset.
- `data/campus_customs_new.db`: working copy. All agent tools read and write this file.

## Tables

### `desk`
Fields: `date_today` (TEXT, required), `notes` (TEXT)
Why it matters: `date_today` is the shop's "today" (2026-08-31). Agents use it for every due-date, overdue, and lead-time calculation, never the real clock.

### `tickets`
Fields: `id` (INTEGER, PK), `type` (TEXT, required), `requester` (TEXT, required), `subject` (TEXT, required), `sku` (TEXT), `size` (TEXT), `qty` (INTEGER), `lease_id` (INTEGER, FK → `leases.id`), `invoice_id` (INTEGER, FK → `invoices.id`), `status` (TEXT, required), `notes` (TEXT), `created_at` (TEXT, required)
Why it matters: This is the work board. The Boss reads open tickets, routes each one by `type`, and follows the optional link fields to the data a specialist agent needs.

### `inventory`
Fields: `sku` (TEXT, PK part), `name` (TEXT, required), `size` (TEXT, PK part), `qty` (INTEGER, required), `location` (TEXT, required)
Why it matters: Inventory checks stock per SKU + size here to find shortfalls. One-size items use size `OS`.

### `pricing`
Fields: `sku` (TEXT, PK), `unit_cost` (REAL, required), `list_price` (REAL, required)
Why it matters: Accounting uses cost against price to check margins on discounts and to estimate restock cost.

### `vendors`
Fields: `id` (INTEGER, PK), `name` (TEXT, required), `specialty` (TEXT, required), `lead_days` (INTEGER, required)
Why it matters: Inventory chooses a restock vendor by `specialty` and uses `lead_days` from here to compute arrival dates.

### `leases`
Fields: `id` (INTEGER, PK), `space_name` (TEXT, required), `landlord` (TEXT, required), `monthly_rent` (REAL, required), `next_due` (TEXT, required), `notes` (TEXT)
Why it matters: Facilities uses it to see what rent is owed, to whom, and when.

### `cash_accounts`
Fields: `name` (TEXT, PK), `balance` (REAL, required), `date` (TEXT, required)
Why it matters: This is the shop's only money ($3,400 in `checking`). Every payment must leave the balance at or above zero, and no revenue comes in.

### `payments`
Fields: `id` (INTEGER, PK), `kind` (TEXT, required), `ref_id` (INTEGER), `amount` (REAL, required), `account` (TEXT, required), `paid_at` (TEXT, required), `approved_by` (TEXT, required)
Why it matters: This is the payments ledger, empty at the start. Rows are written only after a human approves. `approved_by` records who approved it, and `kind` + `ref_id` point to what was paid (for example, an invoice or a lease).

### `invoices`
Fields: `id` (INTEGER, PK), `vendor_id` (INTEGER, required, FK → `vendors.id`), `amount` (REAL, required), `due_date` (TEXT, required), `status` (TEXT, required), `description` (TEXT)
Why it matters: Shows what the shop owes vendors. A vendor with an unpaid invoice won't ship, so Accounting must clear it before Inventory can restock from that vendor.

## How the tables connect

- Declared foreign keys: `tickets.invoice_id → invoices.id`, `tickets.lease_id → leases.id`, `invoices.vendor_id → vendors.id`.
- Implied links (no FK in the schema):
  - `tickets.sku`/`size` → `inventory`, and `sku` → `pricing`.
  - `payments.ref_id` → an invoice or lease, depending on `kind`.
  - SKU → vendor is matched only through `vendors.specialty`.

## Open tickets at the start (shop date 2026-08-31)

| Ticket | Type | Linked data | What it involves |
|---|---|---|---|
| 101 | `customer_order` | Tauhid Zaman wants `CC-TEE-WHITE` size S, qty 1. `invoice_id` 501. | Inventory has 0 in size S. Invoice 501 ($840, Bulldog Print Co, "Rush reprint CC-TEE-WHITE S") was due 2026-08-28 and is still `open`, so Bulldog won't ship. Bulldog's lead time is 5 days. |
| 102 | `rent_notice` | Elm City Properties. `lease_id` 1. | Lease 1: Chapel Street shop, $2,400, `next_due` 2026-09-02. |
| 103 | `price_override` | Yale AI Club wants `CC-HOOD-NAVY` size M, qty 20, at a bulk discount. | Inventory has 8 in size M, a shortfall of 12. Pricing: cost $22, list $58. The restock would come from an apparel vendor, which is Bulldog, the same vendor blocked by invoice 501. |

Cash check: invoice 501 ($840) + rent ($2,400) = $3,240, against $3,400 in checking. Paying both leaves $160. That isn't enough to also buy the 12 hoodies at cost (12 × $22 = $264).

## Workflow tables (added by the MCP server)

The MCP server creates these two tables in the working copy only. Resetting from the original clears them.

### `approval_requests`
Fields: `id`, `kind` (invoice | rent | purchase_order), `ref_id`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `ticket_id`, `reason`, `requested_by`, `requested_on`, `status` (pending | approved | rejected), `decided_by`, `decided_on`, `decision_note`, `payment_id`, `expected_arrival`
Why it matters: Agents put every payment or purchase order here as `pending`. Only a human approval turns one into a row in `payments`.

### `customer_drafts`
Fields: `id`, `ticket_id`, `recipient`, `subject`, `body`, `drafted_by`, `drafted_on`, `status` (always `draft_not_sent`)
Why it matters: Customer Service's output lands here for a human to review. Nothing is ever sent.

## Agents (`backend/`)

All 5 agents use `gpt-6-luna` through Portkey, via the OpenAI Responses API (the model rejects tools on `/chat/completions`). Each agent has its own prompt in `backend/prompts/<agent>.md`. The shared types are in `backend/models.py`.

| Agent | Job | MCP tools it may call | Returns |
|---|---|---|---|
| Boss | Reads the board, routes tickets, makes final calls, updates tickets | `list_open_tickets`, `get_cash_position`, `update_ticket` | `BossReport` |
| Inventory | Stock by SKU/size, shortfalls, which vendor can restock and when | `get_stock_and_pricing`, `list_restock_vendors`, `get_vendor_invoice_status` | `AgentReport` |
| Accounting | Cash, invoices, margins; prepares payment and PO requests | `get_cash_position`, `get_vendor_invoice_status`, `get_lease_rent_due`, `get_stock_and_pricing`, `request_payment`, `request_purchase_order` | `AgentReport` |
| Facilities | Leases, rent, shop-space issues | `get_lease_rent_due`, `get_cash_position` | `AgentReport` |
| Customer Service | Drafts customer messages only | `list_open_tickets`, `draft_customer_message` | `AgentReport` |

**Delegation (fully connected):** every agent has a `delegate(to, task, ticket_id, new_subtask_reason)` tool. Its `to` choices are the agent's 4 teammates, never itself, so all 20 directed paths exist. The delegated agent shares the caller's token budget and returns its report as JSON.

| From \ To | Boss | Inventory | Accounting | Facilities | Customer Service |
|---|---|---|---|---|---|
| Boss | — | ✓ | ✓ | ✓ | ✓ |
| Inventory | ✓ | — | ✓ | ✓ | ✓ |
| Accounting | ✓ | ✓ | — | ✓ | ✓ |
| Facilities | ✓ | ✓ | ✓ | — | ✓ |
| Customer Service | ✓ | ✓ | ✓ | ✓ | — |

**Guards against duplicate work and loops** (enforced in `delegate`; checked during development with stand-in agents on all 20 paths):

| Guard | What happens |
|---|---|
| Self | An agent can't pick itself: the target list excludes it, and the code refuses it anyway. |
| Back up the chain | If the target is already waiting on the caller (e.g. Boss → Accounting, then Accounting → Boss), the call is refused. The caller puts its question in its report. Prevents A → B → A loops. |
| Duplicate | The same teammate and the same ticket returns the earlier report, with no new run. If that teammate is still working, the caller is told to wait. A new run happens only with an explicit `new_subtask_reason`, which is logged. |
| Depth | Max 3 levels below the Boss (Boss → Inventory → Accounting → Customer Service is the deepest). |
| Budget | Max 12 delegations per run, across the whole team. |
| Shared work log | Every delegation (who, whom, ticket, task, result summary) is injected into every agent's instructions, so agents reuse earlier results instead of asking again. |

**Shortages:** a shortage is not automatically `blocked`. The Boss considers partial fulfillment (ship what's in stock now, the rest after restock). It offers that only when Inventory has confirmed the quantities and Accounting has confirmed the margin, and only as an option for human and customer approval, never as shop policy. If the restock for the remainder can't be afforded, the team also offers **customer prepayment** for those units (added after the clean run):
- Accounting works out the amount (units × the offered price) and whether it covers the restock cost.
- Inventory gives the ship estimate: prepayment date + vendor lead days.
- Customer Service presents it in the draft.

The prepayment is never counted as cash, which keeps the no-revenue rule. The PO is requested only after the money actually arrives, and still needs human approval.

**Audit trail:** `output/audit_trail.json` is a JSON list that is only ever appended to. Each run adds:
- a `run_start` entry with the task, the model, the database, and whether it was reset;
- one entry per agent-loop step: `user_prompt`, `model_request` (tool results sent to the model), `model_response` (text and tool calls with arguments, plus token usage), `end` (the final output), and `error` if one occurs;
- a `run_end` entry with total requests, tool calls, tokens, and delegations.

Outside agent runs, the trail also gets:
- a `reset` marker whenever the working DB is reset (dashboard, API, or `backend.reset_db`);
- a `human_decision` entry for every Approve/Reject click, including refused ones.

Both were added after the clean run, so that run's human approvals are recorded in `approval_requests` and `payments` instead.

**What's in the trail:** `output/audit_trail.json` contains only the real clean run of Problem 9. During development, every test run was pointed at scratch copies (`CAMPUS_CUSTOMS_DB` and `AUDIT_TRAIL_PATH`), so test traffic never mixed with the real trail. Nothing was erased from it.

**Model name:** steps record `model: "gpt-6-luna-global"`. That is the deployment name Portkey/Azure reports back for `gpt-6-luna`; the code only ever requests `gpt-6-luna`.

Every step carries `run_id`, `agent`, `depth`, the delegation `chain` (e.g. `boss → facilities → accounting`), and a timestamp.

**Running:**
- `.venv/bin/python -m backend.run --reset` resets the working DB from the original, then runs the team.
- `.venv/bin/python -m backend.reset_db` only resets.

## MCP tools (`mcp_server/server.py`)

All shop facts and every change go through these tools. The backend has no database code of its own.

| Tool | Type | Tables | Used for |
|---|---|---|---|
| `list_open_tickets` | read | `tickets`, `desk` | Boss reads the board (tickets 101–103) and the shop date. |
| `list_tickets` | read | `tickets`, `desk` | Dashboard: all tickets with `is_resolved`. Not given to agents. |
| `list_approval_requests(status)` | read | `approval_requests` | Dashboard: requests waiting for a human. Not given to agents. |
| `get_vendor_invoice_status(invoice_id)` | read | `invoices`, `vendors`, `desk` | Ticket 101: invoice 501 is unpaid and 3 days overdue, so Bulldog won't ship. If paid today, arrival is 2026-09-05. |
| `get_lease_rent_due(lease_id)` | read | `leases`, `cash_accounts`, `desk` | Ticket 102: confirms $2,400 is due 2026-09-02 and that checking can cover it. |
| `get_stock_and_pricing(sku, size, qty)` | read | `inventory`, `pricing` | Ticket 103 (and 101): 8 of 20 hoodies on hand, short 12. Cost $22 vs. list $58 sets the discount floor. |
| `list_restock_vendors` | read | `vendors`, `invoices`, `desk` | Tickets 101 and 103: picks the restock vendor by specialty, with lead days and whether it will ship. |
| `get_cash_position` | read | `cash_accounts`, `invoices`, `vendors`, `leases`, `approval_requests`, `desk` | All tickets: the balance against invoices, rent, and pending requests, for deciding what to pay first. |
| `request_payment(kind, ref_id, …)` | write | reads `invoices`/`leases`, `cash_accounts`; writes `approval_requests` | Tickets 101 and 102: a pending request to pay invoice 501 or the rent. |
| `request_purchase_order(vendor_id, sku, size, qty, …)` | write | reads `vendors`, `pricing`, `inventory`, `invoices`, `cash_accounts`; writes `approval_requests` | Tickets 101 and 103: a pending restock order at unit cost. |
| `draft_customer_message(ticket_id, …)` | write | reads `tickets`; writes `customer_drafts` | Tickets 101 and 103: a reply draft to the requester. |
| `update_ticket(ticket_id, status, note)` | write | `tickets` | All tickets: the Boss records the status and the reason. |
| `approve_request(request_id, approved_by)` | **human only**, registered only with `CAMPUS_CUSTOMS_HUMAN_APPROVER=1` | writes `payments`, `cash_accounts`, `invoices`/`leases`, `approval_requests` | Moves money after a human approves. Never given to an agent. |
| `reject_request(request_id, rejected_by, note)` | **human only**, registered only with `CAMPUS_CUSTOMS_HUMAN_APPROVER=1` | `approval_requests` | Rejects a pending request. Never given to an agent. |

## Backend routes (`backend/main.py`)

Run from `backend/`: `uvicorn main:app --reload --port 8000`, then open http://localhost:8000 (API docs at `/docs`). Shop data goes through MCP clients; there is no SQL in the backend.

- `GET /api/tickets`: all tickets with the Boss's `status`, `is_resolved`, the latest team run since the last reset (`last_run`), and `team_resolved` (the team finished a run on the ticket), via MCP `list_tickets` plus the audit trail.
- `POST /api/tickets/{ticket_id}/run`: starts the agent team on that one ticket in the background and returns a `run_id`. Returns 409 if a run is already going or the ticket is resolved, 404 if the ticket doesn't exist.
- `GET /api/runs/{run_id}`: the run's status (`running` / `done` / `failed`) and the Boss's report.
- `GET /api/events?since=&limit=&run_id=`: recent agent activity from `output/audit_trail.json`: what each agent said, the MCP tools it called with arguments, tool results, and delegations. Poll with `since=<last_id>`.
- `GET /api/approvals?status=pending`: payment and PO requests the agents prepared, via MCP `list_approval_requests`.
- `POST /api/approvals/{request_id}/approve` (body `{"decided_by": "<name>"}`): **human only**, the single route that changes cash. It calls `approve_request` on the approver MCP process, which re-checks the cash and vendor rules first.
- `POST /api/approvals/{request_id}/reject` (body `{"decided_by", "note"}`): human only. Rejects the request; no money moves.
- `GET /api/cash`: the actual checking balance from `cash_accounts`, with pending requests shown separately as `projected_after_pending`.
- `POST /api/reset`: copies the original DB over `campus_customs_new.db`, which also clears approvals and drafts, and logs a `reset` step in the audit trail. Returns 409 while a run is going.
- `GET /api/health`: server status, the database in use, and whether the team is running.

## Dashboard (`frontend/`)

React + Vite + TypeScript. Start it with `npm run dev` in `frontend/` (http://localhost:5173). It talks to the backend at `http://localhost:8000`; override with `VITE_API_BASE`. Design notes are in `output/design.md`.

| Area | What it shows | Data from |
|---|---|---|
| Ticket board | 3 ticket cards with **Dispatch team →**. **✓ Resolved** seal once the team finishes a run, plus the Boss's status, which becomes "Approved by you" once every request is signed. | `GET /api/tickets` |
| Agent roster | The 5 agents in their colors; the active one pulses | `GET /api/events` |
| Live activity | Handoffs, what each agent said, MCP tool chips with arguments, delegations. Polled every 1.4 s while a run is live. | `GET /api/events?since=` |
| Run summary | The Boss's decision and next step, plus one card per agent with its report and tools | `GET /api/runs/{id}` + events |
| Checking | The **actual** balance from `cash_accounts`. Pending amounts and the projected balance are shown separately. | `GET /api/cash` |
| Awaiting your signature | Each pending request: amount, what it pays, reason, which agent prepared it, **Approve / Reject**, and the approver's name | `GET /api/approvals`, `POST …/approve`, `POST …/reject` |

`?ticket=101` opens the dashboard on a given ticket; the Problem 9 screenshots use it. Agents are told apart by color, glyph, and name. Resolved tickets turn green with a seal. Approvals are the only orange element on the page.

## Human approvals

1. **An agent prepares.** Accounting calls `request_payment` (invoice or rent) or `request_purchase_order`. The MCP server takes the amount from the DB, refuses duplicates, refuses anything that would make cash negative once other pending requests are counted, and refuses a PO to a vendor whose unpaid invoice has no payment pending. It saves a `pending` row in `approval_requests`. No money moves.
2. **The dashboard shows it** under *Awaiting your signature*, and the masthead counts it.
3. **A human decides.** **Approve** requires a name and calls `POST /api/approvals/{id}/approve`. The backend sends it to `approve_request` on the separate approver MCP process (`CAMPUS_CUSTOMS_HUMAN_APPROVER=1`), which re-checks cash ≥ 0 and the vendor rule against the live DB.
4. **One transaction executes it:**
   - inserts into `payments` with `approved_by`, debits `cash_accounts`, and marks the request `approved`;
   - for an invoice, marks it `paid`;
   - for rent, moves the lease's `next_due` forward one month;
   - for a PO, records `expected_arrival` (shop date + `lead_days`).
5. **Reject** marks the request `rejected`; no money moves.

6. **Closing the ticket** (added after the clean run): if the approved request was the ticket's **last pending** one and the Boss left the ticket `waiting_on_approval`, the same transaction sets the ticket to `resolved` and appends "[shop date human] All approvals granted by [approver]". The API returns it as `ticket_resolved`, and the dashboard says so in the confirmation. A ticket the Boss left `in_progress`, e.g. 103 waiting on the customer, keeps its status.

In the clean run (before this fix), 101 and 102 kept `waiting_on_approval` after approval. That run's data was deliberately not changed; the dashboard showed "Approved by you" instead.

## Clean run (Problem 9)

Reset at 2026-10-14 02:41 UTC; the three tickets were then run one at a time from the dashboard while the human watched and approved.

| Ticket | Run | Agents (handoffs) | Human approvals | Cash | Outcome |
|---|---|---|---|---|---|
| 101 Bulldog tee | `7ef5e1d089b0` | Boss → Inventory → Accounting; Boss → Accounting (new subtask); Boss → Customer Service | #1 invoice 501 $840.00, #2 PO 1 tee $8.00 | $3,400.00 → $2,552.00 | Vendor unblocked; tee expected about 2026-09-05; draft #1 |
| 102 Rent due | `1b478145ae7d` | Boss → Facilities → Accounting | #3 rent $2,400.00 | $2,552.00 → $152.00 | Rent paid; next due 2026-10-02 |
| 103 Hoodie discount | `f6745292c571` | Boss → Inventory; Boss → Accounting; Boss → Customer Service | none | $152.00 | $55 each offered, 8 now + 12 later as an option; draft #2; `in_progress` |

Ending checking: **$152.00** = $3,400.00 − $3,248.00, matching `cash_accounts` in `data/campus_customs_new.db`.

## Output files

| File | What it is |
|---|---|
| `output/harness.md` | This document |
| `output/mcp_smoke.json` | Problem 4: the 3 original MCP tools called through Claude Code |
| `output/audit_trail.json` | Every agent-loop step of every run, append-only (reset markers included) |
| `output/desk_tickets.html` | Expected vs. Actual per ticket, plus the Cash ledger and its verification |
| `output/resolved_tickets.json` | Per ticket: final status, outcome, each agent's contribution, human approvals |
| `output/resolved_board.html` | Screenshots of the real dashboard with all 3 tickets resolved. The images are embedded, so the file opens anywhere by double-clicking. |
| `output/design.md` | Dashboard layout and design choices |

## Safety

**Money**
- Agents can only create `pending` requests. Money moves only in `approve_request`, and the only way to reach it is the human route `POST /api/approvals/{id}/approve`. Five layers, each checked during development:
  1. The tool is registered only in an MCP server process started with `CAMPUS_CUSTOMS_HUMAN_APPROVER=1`. The backend starts that process only for its approval client.
  2. The agents' MCP process runs with the flag set to `0`. A direct call there fails with "Unknown tool".
  3. No agent's tool allowlist includes it.
  4. The backend's `process_tool_call` hook refuses it by name.
  5. Claude Code's `.mcp.json` server doesn't have it either. Agents have no HTTP tool, so they can't call the route.
- Amounts come from the database (invoice amount, lease rent, `unit_cost × qty`). Agents never type an amount.
- Cash can't go negative. This is checked twice: when the request is made (counting all other pending requests) and again at approval (against the real balance).
- No revenue: nothing ever adds to `cash_accounts`.
- A vendor with an unpaid invoice won't ship. A purchase order is refused unless that invoice's payment is already pending, and it can't be approved until the invoice is paid.
- No duplicate pending requests for the same invoice or lease.
- Every write records who acted. The backend stamps the real agent name onto `requested_by` / `drafted_by` / `updated_by`, so an agent can't sign as another.

**Customers, vendors, and landlords**
- No tool sends anything. Customer messages are stored as `draft_not_sent`, addressed to the ticket's requester.
- Customer Service has no tools for money, stock, or ticket status. Its prompt forbids promising prices, discounts, or dates the Boss hasn't approved.
- Accounting reports the break-even price (unit cost) and the margin at any proposed price, and the Boss decides the price. There is no hard floor in code; in the clean run the chosen price ($55) stayed well above the $22 cost.

**Data**
- Read tools open the database read-only.
- The original `campus_customs.db` is read-only, and the backend only ever copies it (reset).
- Dates always come from `desk.date_today`.

**Observed in the clean run**
- Every cash change came from a human click; pending requests never changed `cash_accounts`.
- The only order that would have broken the cash rule (12 hoodies, $264 vs. $152) was never requested.
- The duplicate-delegation guard caught one repeat request to Accounting on ticket 101.
- No message was sent. Two customer drafts are stored as `draft_not_sent`.

**Token limits**
- One shared budget per run, across all agents and delegations: 60 model requests, 80 tool calls, 250k total tokens.
- Max 2,000 output tokens per response, with reasoning effort set to `low`.
- Delegation: no self-delegation, no delegating back up the current chain (prevents loops), max depth 3, and max 12 delegations per run.
- Each agent sees only its own tools, which keeps tool schemas out of every prompt.
- Long tool results and outputs are clipped to 4,000 characters in the audit trail.
- Observed in the clean run: 101 used 19 model calls (~49k tokens), 102 used 11 (~21k), and 103 used 12 (~28k), all well under the per-run limits.
