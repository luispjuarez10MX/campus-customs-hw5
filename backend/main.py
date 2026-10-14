"""FastAPI backend for the Campus Customs dashboard.

Run from this folder:  uvicorn main:app --reload --port 8000

Shop data is read and changed only through the MCP server. This file opens
two MCP clients:

- `shop`: the same tools the agents have. Used for tickets, cash, and approvals lists.
- `approver`: a separate server process started with CAMPUS_CUSTOMS_HUMAN_APPROVER=1,
  the only process where approve_request / reject_request exist. Only the two
  human approval routes use it.
"""

import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# `uvicorn main:app` runs from backend/, so put the project root on the path
# for the `backend.*` imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastmcp import Client  # noqa: E402
from fastmcp.client.transports import PythonStdioTransport  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.agents import AGENT_TOOLS, run_team  # noqa: E402
from backend.audit import AuditTrail  # noqa: E402
from backend.config import AUDIT_TRAIL_PATH, DB_PATH, MCP_SERVER_SCRIPT, PROJECT_ROOT  # noqa: E402
from backend.reset_db import reset_db  # noqa: E402

MCP_TOOL_NAMES = set().union(*AGENT_TOOLS.values())
EVENT_TEXT_LIMIT = 600


def _mcp_client(human_approver: bool) -> Client:
    return Client(PythonStdioTransport(
        MCP_SERVER_SCRIPT,
        python_cmd=sys.executable,
        cwd=str(PROJECT_ROOT),
        env={
            "CAMPUS_CUSTOMS_DB": str(DB_PATH),
            "CAMPUS_CUSTOMS_HUMAN_APPROVER": "1" if human_approver else "0",
        },
    ))


clients: dict[str, Client] = {}
runs: dict[str, dict[str, Any]] = {}
run_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    clients["shop"] = _mcp_client(human_approver=False)
    clients["approver"] = _mcp_client(human_approver=True)
    async with clients["shop"], clients["approver"]:
        yield


app = FastAPI(title="Campus Customs Ops API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp(name: str, args: dict | None = None, *, client: str = "shop") -> dict:
    try:
        result = await clients[client].call_tool(name, args or {})
    except ToolError as exc:
        raise HTTPException(400, str(exc)) from exc
    return result.structured_content or {}


def _refused(result: dict) -> None:
    if result.get("ok") is False:
        raise HTTPException(409, result.get("refused", "Refused by the MCP server."))


# ------------------------------------------------------------------ tickets


def _audit_steps() -> list[dict]:
    return json.loads(AUDIT_TRAIL_PATH.read_text()) if AUDIT_TRAIL_PATH.exists() else []


def _runs_since_reset() -> dict[int, dict]:
    """Latest team run per ticket since the last reset, from the audit trail."""
    latest: dict[int, dict] = {}
    for e in _audit_steps():
        kind, tid = e.get("step_type"), e.get("ticket_id")
        if kind == "reset":
            latest = {}
        elif kind == "run_start" and tid is not None:
            latest[tid] = {"run_id": e["run_id"], "status": "running", "started_at": e.get("logged_at")}
        elif kind == "run_end" and tid is not None and latest.get(tid, {}).get("run_id") == e["run_id"]:
            latest[tid].update(status=e.get("status", "done"), finished_at=e.get("logged_at"))
    return latest


@app.get("/api/tickets")
async def get_tickets():
    """All tickets with the Boss's status, whether they're resolved, and the latest team run.

    `team_resolved` is true once the team has finished a run on the ticket (the Boss made its
    final call) or the ticket's status is `resolved`. Pending approvals stay visible separately.
    """
    data = await mcp("list_tickets")
    last = _runs_since_reset()
    for t in data["tickets"]:
        t["last_run"] = last.get(t["id"])
        t["team_resolved"] = t["is_resolved"] or (t["last_run"] or {}).get("status") == "done"
    return data


class RunStarted(BaseModel):
    run_id: str
    ticket_id: int
    status: str


@app.post("/api/tickets/{ticket_id}/run", status_code=202, response_model=RunStarted)
async def run_ticket(ticket_id: int):
    """Start the agent team on one ticket in the background. Poll /api/events or /api/runs/{run_id}."""
    if run_lock.locked():
        raise HTTPException(409, "The team is already working on a run. Wait for it to finish.")
    tickets = {t["id"]: t for t in (await mcp("list_tickets"))["tickets"]}
    if ticket_id not in tickets:
        raise HTTPException(404, f"Ticket {ticket_id} not found.")
    if tickets[ticket_id]["is_resolved"]:
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved.")

    run_id = uuid.uuid4().hex[:12]
    runs[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running", "report": None, "error": None}
    task = (
        f"Work only on ticket {ticket_id}. Get the facts from your team, make the final call, "
        "and update that ticket. Leave every other ticket alone. Keep cash at or above zero, "
        "and leave every payment for human approval."
    )

    await run_lock.acquire()  # held until the background run finishes

    async def _run():
        try:
            report = await run_team(task, run_id=run_id, ticket_id=ticket_id)
            runs[run_id].update(status="done", report=report.model_dump())
        except Exception as exc:  # surfaced to the dashboard, also in the audit trail
            runs[run_id].update(status="failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            run_lock.release()

    runs[run_id]["task"] = asyncio.create_task(_run())
    return RunStarted(run_id=run_id, ticket_id=ticket_id, status="running")


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Status of a run started from the dashboard, with the Boss's report when done."""
    if run_id not in runs:
        raise HTTPException(404, f"Run {run_id} not found.")
    return {k: v for k, v in runs[run_id].items() if k != "task"}


# ------------------------------------------------------------------- events


def _clip(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= EVENT_TEXT_LIMIT else text[:EVENT_TEXT_LIMIT] + "…"


def _to_event(i: int, e: dict) -> dict | None:
    """Turn one audit-trail step into a compact dashboard event."""
    base = {"id": i, "at": e.get("logged_at"), "run_id": e.get("run_id"), "agent": e.get("agent"),
            "chain": e.get("chain"), "type": e["step_type"]}
    kind = e["step_type"]
    if kind == "run_start":
        return {**base, "ticket_id": e.get("ticket_id"), "text": _clip(e.get("task"))}
    if kind == "reset":
        return {**base, "text": "Working database reset from the original."}
    if kind == "human_decision":
        return {**base, "text": f"Request #{e['request_id']} {e['decision']} by {e['decided_by']}" + ("" if e.get("ok") else f" (refused: {e.get('refused')})")}
    if kind == "user_prompt":
        asked_by = e["chain"][-2] if len(e.get("chain") or []) > 1 else "dashboard"
        return {**base, "asked_by": asked_by, "text": _clip(e.get("prompt"))}
    if kind == "model_response":
        said = " ".join(p["text"] for p in e["model_output"] if "text" in p)
        calls = [p for p in e["model_output"] if "tool_call" in p]
        return {
            **base,
            "text": _clip(said) if said else None,
            "mcp_tools": [{"tool": c["tool_call"], "args": c["args"]} for c in calls if c["tool_call"] in MCP_TOOL_NAMES],
            "delegations": [{"to": c["args"].get("to"), "ticket_id": c["args"].get("ticket_id"), "task": _clip(c["args"].get("task", ""))}
                            for c in calls if c["tool_call"] == "delegate"],
            "final_answer": any(c["tool_call"] == "final_result" for c in calls),
        }
    if kind == "model_request":
        results = [p for p in e["sent_to_model"] if "tool_result" in p]
        if not results:
            return None
        return {**base, "tool_results": [{"tool": r["tool_result"], "content": _clip(r["content"])} for r in results]}
    if kind == "end":
        out = e.get("output")
        return {**base, "text": _clip(out.get("summary") if isinstance(out, dict) else out)}
    if kind == "error":
        return {**base, "text": e.get("error")}
    if kind == "run_end":
        return {**base, "status": e.get("status", "done"), "ticket_id": e.get("ticket_id"),
                "usage": e.get("usage"), "delegations": e.get("delegations")}
    return None


@app.get("/api/events")
async def get_events(
    since: int = Query(-1, description="Return events with id greater than this (for polling)."),
    limit: int = Query(200, le=1000),
    run_id: str | None = None,
):
    """Recent agent activity from output/audit_trail.json: what each agent said and which MCP tools it called."""
    steps = _audit_steps()
    events = [
        ev for i, e in enumerate(steps)
        if i > since and (run_id is None or e.get("run_id") == run_id) and (ev := _to_event(i, e))
    ]
    return {"last_id": len(steps) - 1, "events": events[-limit:]}


# ---------------------------------------------------------------- approvals


@app.get("/api/approvals")
async def get_approvals(status: str | None = Query(None, pattern="^(pending|approved|rejected)$")):
    """Payment and purchase-order requests prepared by the agents."""
    return await mcp("list_approval_requests", {"status": status} if status else {})


class Decision(BaseModel):
    decided_by: str = Field(min_length=1, description="Name of the human who clicked the button.")
    note: str = ""


def _log_decision(decision: str, request_id: int, by: str, result: dict) -> None:
    """Record every human click (including refused ones) in the audit trail."""
    AuditTrail(AUDIT_TRAIL_PATH).append({
        "step_type": "human_decision", "decision": decision, "request_id": request_id, "decided_by": by,
        "ok": result.get("ok", False), "refused": result.get("refused"),
        "amount": result.get("amount"), "checking_balance": result.get("checking_balance"),
        "ticket_resolved": result.get("ticket_resolved"),
    })


@app.post("/api/approvals/{request_id}/approve")
async def approve(request_id: int, decision: Decision):
    """HUMAN ONLY. The single route that can move money. Calls approve_request on the approver MCP process,
    which re-checks cash and vendor rules before writing the payment. If this was the ticket's last pending
    request and the ticket was waiting_on_approval, `ticket_resolved` holds the ticket id that was closed."""
    result = await mcp("approve_request", {"request_id": request_id, "approved_by": decision.decided_by}, client="approver")
    _log_decision("approved", request_id, decision.decided_by, result)
    _refused(result)
    return result


@app.post("/api/approvals/{request_id}/reject")
async def reject(request_id: int, decision: Decision):
    """HUMAN ONLY. Reject a pending request. No money moves."""
    result = await mcp("reject_request", {"request_id": request_id, "rejected_by": decision.decided_by, "note": decision.note}, client="approver")
    _log_decision("rejected", request_id, decision.decided_by, result)
    _refused(result)
    return result


# --------------------------------------------------------------- cash/reset


@app.get("/api/cash")
async def get_cash():
    """Actual checking balance from cash_accounts, plus pending requests shown separately as a projection."""
    pos = await mcp("get_cash_position")
    return {
        "today": pos["today"],
        "checking_balance": pos["checking_balance"],
        "pending_total": pos["pending_total"],
        "projected_after_pending": pos["available_after_pending"],
    }


@app.post("/api/reset")
async def reset():
    """Copy the untouched original database over campus_customs_new.db (also clears approvals and drafts)."""
    if run_lock.locked():
        raise HTTPException(409, "Can't reset while the team is running.")
    reset_db()  # also logs a reset marker in the audit trail
    return {"ok": True, "database": DB_PATH.name, "tickets": (await mcp("list_tickets"))["tickets"]}


@app.get("/api/health")
async def health():
    return {"ok": True, "database": DB_PATH.name, "team_running": run_lock.locked()}
