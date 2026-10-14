# Campus Customs – Multi-Agent Operations Desk

**MGT 409 · AI Foundations for Managers · Homework 5**

A multi-agent operations team for Campus Customs, a Yale apparel shop. Five PydanticAI agents (**Boss, Inventory, Accounting, Facilities, Customer Service**) work the shop's ticket board: customer orders, rent, unpaid vendor bills, discounts, and stock problems. They can delegate to each other, and they reach shop data only through a **FastMCP server** over SQLite. A **FastAPI** backend runs the team, and a **React** dashboard lets a human watch every step and approve payments.

- Every agent call uses `gpt-6-luna` through Portkey.
- Agents can only *prepare* payments and purchase orders. Money moves only when a human clicks **Approve**.
- The shop's "today" is `desk.date_today` (2026-08-31). No revenue comes in. Cash can never go negative. A vendor with an unpaid invoice won't ship. Nobody is ever actually contacted.

The full design and rules are in [`output/harness.md`](output/harness.md).

## Project structure

```
hw5/
├── AI_prompts.md          # every prompt used, per problem
├── README.md
├── requirements.txt       # Python dependencies
├── .env.example           # copy to .env and add your Portkey key
├── .mcp.json              # connects the MCP server to Claude Code
├── data/
│   ├── campus_customs.db      # untouched original (used for resets)
│   └── campus_customs_new.db  # working copy the agents change
├── mcp_server/            # FastMCP server: every shop fact and change goes through it
├── backend/               # agents, prompts, FastAPI app, audit trail
│   ├── main.py            # FastAPI routes
│   ├── agents.py          # the 5-agent team, delegation, guards
│   ├── models.py          # shared data types
│   └── prompts/           # boss.md, inventory.md, accounting.md, facilities.md, customer_service.md
├── frontend/              # React + Vite + TypeScript dashboard
└── output/                # harness, MCP smoke test, desk tickets, design, run results, audit trail
```

## Setup (once)

Requires Python 3.11+ and Node 20+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # then put your PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

The backend looks for the nearest `.env`, starting in this folder and then its parent folders. `.env` is git-ignored: never commit it.

## Running it

All commands run from the `hw5/` folder unless noted.

### 1. Copy the original database to the working database (clean run)

The agents only ever change `data/campus_customs_new.db`. Start from a fresh copy of the original:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

or, equivalently:

```bash
.venv/bin/python -m backend.reset_db
```

`campus_customs.db` is never modified. Resetting also clears the `approval_requests` and `customer_drafts` tables, which exist only in the working copy.

### 2. Start the MCP server

The backend starts its own MCP server process automatically, so for the app you can skip this step. To run the server by itself (it speaks MCP over stdio and waits for a client):

```bash
.venv/bin/python mcp_server/server.py
```

To use the tools from **Claude Code**, open Claude Code in this folder and approve the `campus-customs` server from `.mcp.json`. See [`mcp_server/README.md`](mcp_server/README.md) for the tool list.

### 3. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

It runs at http://localhost:8000; interactive API docs are at http://localhost:8000/docs.

### 4. Start the React dashboard

In a second terminal:

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. On the dashboard:

1. Type your name in **Approving as**.
2. Click **Dispatch team →** on a ticket.
3. Watch the agents in **Live activity**.
4. Approve or reject anything under **Awaiting your signature**.

Optional, in a third terminal: `.venv/bin/python backend/watch_agents.py` prints the same agent activity as text.

### 5. Reset before running all 3 tickets again

Click **Reset desk** in the dashboard's top bar, or call:

```bash
curl -X POST http://localhost:8000/api/reset
```

This restores `campus_customs_new.db` from the original and logs a `reset` marker in `output/audit_trail.json`. The audit trail is append-only, so earlier runs stay in it. The backend refuses to reset while a run is in progress. With the servers stopped, `.venv/bin/python -m backend.reset_db` does the same.

To run the whole team from the command line instead of the dashboard:

```bash
.venv/bin/python -m backend.run --reset
```

## Outputs

| File | What it is |
|---|---|
| `output/harness.md` | Database tables, MCP tools, the 5 agents, API routes, dashboard, approvals, safety rules |
| `output/mcp_smoke.json` | MCP tools called through Claude Code, with real outputs |
| `output/desk_tickets.html` | Expected vs. Actual for tickets 101–103, the Cash ledger, and the Reflection |
| `output/design.md` | Dashboard layout and design choices |
| `output/resolved_tickets.json` | Clean-run results per ticket, with agent contributions and human approvals |
| `output/resolved_board.html` | Screenshots of the real dashboard with all 3 tickets resolved |
| `output/audit_trail.json` | Every agent-loop step of every run |
| `output/github_url.txt` | This repository's URL |

### Clean-run result

Checking went from **$3,400.00** to **$152.00**, through three human-approved payments: invoice 501 $840, 1 tee $8, and rent $2,400. Ticket 103 needed no payment: the 12-hoodie restock ($264) didn't fit in the remaining cash, so the team offered partial fulfillment instead. `data/campus_customs_new.db` holds the database state at the end of that run.
