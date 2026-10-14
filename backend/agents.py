"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

Every agent can delegate to every other agent (a fully connected team). All
shop data comes from the MCP server; each agent only sees the MCP tools its
role needs, and the two human-only approval tools are never given to anyone.
"""

import copy
import sys
import uuid
from dataclasses import replace

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import RunUsage

from backend.audit import AuditTrail, describe_node
from backend.config import (
    AUDIT_TRAIL_PATH,
    DB_PATH,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_RUN,
    MCP_SERVER_SCRIPT,
    MODEL_NAME,
    MODEL_SETTINGS,
    PROJECT_ROOT,
    PROMPTS_DIR,
    USAGE_LIMITS,
    build_model,
)
from backend.models import AGENT_NAMES, AgentName, AgentReport, BossReport, DelegationRecord, RunState, TeamDeps
from backend.reset_db import reset_db

# Least privilege: the MCP tools each role may call.
AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": {"list_open_tickets", "get_cash_position", "update_ticket"},
    "inventory": {"get_stock_and_pricing", "list_restock_vendors", "get_vendor_invoice_status"},
    "accounting": {
        "get_cash_position", "get_vendor_invoice_status", "get_lease_rent_due",
        "get_stock_and_pricing", "request_payment", "request_purchase_order",
    },
    "facilities": {"get_lease_rent_due", "get_cash_position"},
    "customer_service": {"list_open_tickets", "draft_customer_message"},
}
# Defense in depth: these aren't even registered in the agents' MCP process.
HUMAN_ONLY_TOOLS = {"approve_request", "reject_request"}
assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_TOOLS.values())

# Write tools record who acted. The backend fills this in, so an agent cannot
# sign a request with another agent's name.
ACTOR_FIELDS = {
    "request_payment": "requested_by",
    "request_purchase_order": "requested_by",
    "draft_customer_message": "drafted_by",
    "update_ticket": "updated_by",
}

DEFAULT_TASK = (
    "Work through every open ticket on the board. For each one, decide who handles it, "
    "get the facts from your team, make the final call, and update the ticket. "
    "Keep total cash at or above zero, and leave every payment for human approval."
)


async def _stamp_actor(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict):
    if name in HUMAN_ONLY_TOOLS:
        raise PermissionError(f"{name} is reserved for the human approver.")
    if name in ACTOR_FIELDS:
        args = {**args, ACTOR_FIELDS[name]: ctx.deps.agent}
    return await call_tool(name, args)


def build_mcp_toolset() -> MCPToolset:
    transport = PythonStdioTransport(
        MCP_SERVER_SCRIPT,
        python_cmd=sys.executable,
        cwd=str(PROJECT_ROOT),
        # Explicitly not the human approver: approve/reject don't exist in this process.
        env={"CAMPUS_CUSTOMS_DB": str(DB_PATH), "CAMPUS_CUSTOMS_HUMAN_APPROVER": "0"},
    )
    return MCPToolset(Client(transport), process_tool_call=_stamp_actor)


async def delegate(
    ctx: RunContext[TeamDeps],
    to: AgentName,
    task: str,
    ticket_id: int,
    new_subtask_reason: str | None = None,
) -> str:
    """Hand a focused subtask to a teammate and get their report back.

    Teammates: boss (routing and final calls), inventory (stock, shortfalls,
    restock vendor, lead times), accounting (cash, invoices, margins,
    discounts, payment and PO requests), facilities (leases, rent, store
    space), customer_service (customer drafts only). Pass the ticket id and the
    facts you already have. `ticket_id` is the ticket this subtask serves.

    If that teammate already handled this ticket during this run, you get their
    earlier report back instead of a new run. Only if you need something
    genuinely different from them, call again with `new_subtask_reason`
    saying what is new.
    """
    deps = ctx.deps
    state = deps.state
    if to == deps.agent:
        return "You cannot delegate to yourself."
    if to in deps.chain:
        return (
            f"{to} is already waiting on you in this chain ({' -> '.join(deps.chain)}). "
            "Put your question or finding in your report instead."
        )

    earlier = [r for r in state.work_log if r.to_agent == to and r.ticket_id == ticket_id]
    if earlier and not new_subtask_reason:
        running = [r for r in earlier if r.status == "running"]
        if running:
            return f"{to} is already working on ticket {ticket_id} (delegation #{running[0].id}). Wait for that result instead of asking again."
        reports = "\n".join(f"#{r.id} ({r.from_agent} asked: {r.task})\n{r.result}" for r in earlier)
        return (
            f"Reusing {to}'s earlier work on ticket {ticket_id}; no new run was started.\n{reports}\n"
            "If you need something genuinely different, call again with new_subtask_reason."
        )

    if deps.depth >= MAX_DELEGATION_DEPTH:
        return "Delegation depth limit reached. Finish with the facts you have."
    if state.delegations >= MAX_DELEGATIONS_PER_RUN:
        return "The team's delegation budget for this run is used up. Finish with the facts you have."

    record = DelegationRecord(
        id=state.delegations + 1, from_agent=deps.agent, to_agent=to, ticket_id=ticket_id,
        task=task if not new_subtask_reason else f"{task} [new subtask: {new_subtask_reason}]",
    )
    state.work_log.append(record)
    try:
        output = await run_agent(to, task, deps.child(to), usage=ctx.usage)
    except Exception:
        record.status = "failed"
        raise
    record.status, record.result, record.summary = "done", output.model_dump_json(), output.summary
    return record.result


async def _teammates_only(ctx: RunContext[TeamDeps], tool_def: ToolDefinition) -> ToolDefinition:
    """Show each agent only its 4 teammates as delegation targets (never itself)."""
    schema = copy.deepcopy(tool_def.parameters_json_schema)
    schema["properties"]["to"]["enum"] = [n for n in AGENT_NAMES if n != ctx.deps.agent]
    return replace(tool_def, parameters_json_schema=schema)


def work_log_note(ctx: RunContext[TeamDeps]) -> str:
    """Dynamic instructions: the delegation chain and all work done so far this run."""
    lines = [f"Delegation chain for this task: {' -> '.join(ctx.deps.chain)}."]
    log = ctx.deps.state.work_log
    if log:
        lines.append("Work already done this run (reuse it; don't delegate the same subtask again):")
        for r in log:
            ticket = f"ticket {r.ticket_id}"
            outcome = r.summary if r.status == "done" else r.status
            lines.append(f"- #{r.id} {r.from_agent} -> {r.to_agent} ({ticket}): {r.task[:160]} => {outcome}")
    return "\n".join(lines)


def build_team(mcp: MCPToolset) -> dict[AgentName, Agent]:
    model = build_model()
    team = {}
    for name in AGENT_NAMES:
        allowed = AGENT_TOOLS[name]
        agent = Agent(
            model,
            name=name,
            deps_type=TeamDeps,
            output_type=BossReport if name == "boss" else AgentReport,
            instructions=(PROMPTS_DIR / f"{name}.md").read_text(),
            model_settings=MODEL_SETTINGS,
            toolsets=[mcp.filtered(lambda ctx, tool, allowed=allowed: tool.name in allowed)],
            tools=[Tool(delegate, prepare=_teammates_only)],
        )
        agent.instructions(work_log_note)
        team[name] = agent
    return team


async def run_agent(name: AgentName, task: str, deps: TeamDeps, usage: RunUsage | None = None):
    """Run one agent step by step, appending every loop step to the audit trail."""
    state = deps.state
    base = {"run_id": state.run_id, "agent": name, "chain": deps.chain, "depth": deps.depth}
    step = 0
    try:
        async with state.agents[name].iter(
            task, deps=deps, usage=usage, usage_limits=USAGE_LIMITS
        ) as run:
            async for node in run:
                step += 1
                state.audit.append({**base, "step": step, **describe_node(node)})
    except Exception as exc:
        state.audit.append({**base, "step": step + 1, "step_type": "error", "error": f"{type(exc).__name__}: {exc}"})
        raise
    return run.result.output


async def run_team(
    task: str = DEFAULT_TASK, *, reset: bool = False, run_id: str | None = None, ticket_id: int | None = None
) -> BossReport:
    """Start at the Boss and let the team work. Returns the Boss's final report."""
    if reset:
        reset_db()
    mcp = build_mcp_toolset()
    state = RunState(run_id=run_id or uuid.uuid4().hex[:12], audit=AuditTrail(AUDIT_TRAIL_PATH), agents=build_team(mcp))
    usage = RunUsage()
    state.audit.append({
        "run_id": state.run_id, "step_type": "run_start", "task": task,
        "model": MODEL_NAME, "database": DB_PATH.name, "reset_before_run": reset, "ticket_id": ticket_id,
    })
    status, report = "failed", None
    try:
        async with mcp:
            report = await run_agent("boss", task, TeamDeps("boss", state, ["boss"]), usage=usage)
        status = "done"
    finally:
        _log_run_end(state, usage, status, ticket_id)
    return report


def _log_run_end(state: RunState, usage: RunUsage, status: str, ticket_id: int | None) -> None:
    state.audit.append({
        "run_id": state.run_id, "step_type": "run_end", "status": status, "ticket_id": ticket_id,
        "delegations": state.delegations,
        "work_log": [
            {"id": r.id, "from": r.from_agent, "to": r.to_agent, "ticket_id": r.ticket_id, "status": r.status, "task": r.task}
            for r in state.work_log
        ],
        "usage": {
            "requests": usage.requests, "tool_calls": usage.tool_calls,
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
        },
    })
