# Campus Customs MCP Server

This FastMCP server is the only gateway between the Campus Customs agents and the shop's data. Every fact the agents see, and every change they make, goes through one of its tools. The shop rules are enforced in the tool code, not just in prompts.

**Database:** `data/campus_customs_new.db`, the working copy. The original `data/campus_customs.db` is never touched. To point the server at another file, set the `CAMPUS_CUSTOMS_DB` environment variable. Read tools open the database read-only. All dates come from `desk.date_today`.

On its first write, the server adds two workflow tables to the working copy: `approval_requests` and `customer_drafts`. Resetting from the original clears them.

## Tools

### Read

| Tool | Reads | Returns |
|---|---|---|
| `list_open_tickets()` | `tickets`, `desk` | Every unresolved ticket and the shop date |
| `list_tickets()` | `tickets`, `desk` | All tickets with `is_resolved` (dashboard) |
| `list_approval_requests(status)` | `approval_requests` | Payment and PO requests, optionally filtered by status (dashboard) |
| `get_vendor_invoice_status(invoice_id)` | `invoices`, `vendors`, `desk` | Invoice status, days overdue, the vendor and its lead time, whether it will ship, and the arrival date if paid today |
| `get_lease_rent_due(lease_id)` | `leases`, `cash_accounts`, `desk` | Rent, landlord, due date, days left, and the balance after paying |
| `get_stock_and_pricing(sku, size, qty)` | `inventory`, `pricing` | On hand vs. requested, the shortfall, cost, list price, and margin |
| `list_restock_vendors()` | `vendors`, `invoices`, `desk` | Each vendor's specialty, lead days, unpaid invoices, whether it will ship, and the arrival date if ordered today |
| `get_cash_position()` | `cash_accounts`, `invoices`, `vendors`, `leases`, `approval_requests`, `desk` | The balance against unpaid invoices, rent, and pending requests |

### Agent writes (nothing is paid or sent)

| Tool | Writes | Rules enforced |
|---|---|---|
| `request_payment(kind, ref_id, reason, ticket_id)` | `approval_requests` | The amount comes from the DB. Refused if already paid, already pending, or if cash would go negative after the other pending requests. |
| `request_purchase_order(vendor_id, sku, size, qty, reason, ticket_id)` | `approval_requests` | Costed at `unit_cost × qty`. Refused if the vendor has an unpaid invoice with no pending payment, or if cash would go negative. |
| `draft_customer_message(ticket_id, subject, body)` | `customer_drafts` | Addressed to the ticket's requester. Saved as `draft_not_sent`. |
| `update_ticket(ticket_id, status, note)` | `tickets` | The status must be valid. The note is appended with the shop date and the agent's name. |

### Human only (registered only when `CAMPUS_CUSTOMS_HUMAN_APPROVER=1`)

The backend sets this flag only for the MCP client behind its human approval routes. The agents' server process, and the one Claude Code starts from `.mcp.json`, don't have these tools at all.

| Tool | Writes | What it does |
|---|---|---|
| `approve_request(request_id, approved_by)` | `payments`, `cash_accounts`, `invoices` / `leases`, `approval_requests` | Re-checks cash and vendor rules, then in one transaction records the payment, debits checking, and marks the invoice paid, moves the lease's `next_due` forward a month, or sets the PO's arrival date |
| `reject_request(request_id, rejected_by, note)` | `approval_requests` | Marks the request rejected. No money moves. |

## Run

The project's `.mcp.json` starts the server for Claude Code. The backend starts its own copy over stdio.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python mcp_server/server.py
```
