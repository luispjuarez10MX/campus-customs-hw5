"""Shared data types for the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.audit import AuditTrail

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

TicketStatus = Literal["open", "in_progress", "waiting_on_approval", "blocked", "resolved"]


class AgentReport(BaseModel):
    """What a specialist hands back to whoever delegated to it."""

    agent: AgentName
    summary: str = Field(description="Two or three sentences: what you found and did.")
    facts: list[str] = Field(default_factory=list, description="Key numbers and dates, each taken from a tool result.")
    actions_taken: list[str] = Field(default_factory=list, description="Requests created, drafts saved, delegations made.")
    approval_request_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list, description="Anything stopping the work, e.g. an unpaid invoice.")
    needs_human: bool = Field(description="True if a human must approve or decide something.")


class TicketOutcome(BaseModel):
    ticket_id: int
    handled_by: list[AgentName]
    decision: str = Field(description="The Boss's final call for this ticket, with the reason.")
    status: TicketStatus
    approval_request_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    next_step: str = Field(description="What has to happen next, and who does it.")


class BossReport(BaseModel):
    """The Boss's final report for a run."""

    summary: str
    tickets: list[TicketOutcome]
    cash_plan: str = Field(description="How the available cash is allocated across the requests, and what is left.")
    pending_human_approvals: list[int] = Field(default_factory=list)


@dataclass
class DelegationRecord:
    """One delegated subtask, kept so no agent asks for the same work twice."""

    id: int
    from_agent: AgentName
    to_agent: AgentName
    ticket_id: int
    task: str
    status: Literal["running", "done", "failed"] = "running"
    result: str | None = None
    summary: str | None = None


@dataclass
class RunState:
    """Shared by every agent in one team run."""

    run_id: str
    audit: AuditTrail
    agents: dict[str, Any]
    work_log: list[DelegationRecord] = field(default_factory=list)

    @property
    def delegations(self) -> int:
        return len(self.work_log)


@dataclass
class TeamDeps:
    """Per-agent dependencies. A delegated agent gets a child copy."""

    agent: AgentName
    state: RunState
    chain: list[AgentName] = field(default_factory=list)

    @property
    def depth(self) -> int:
        return len(self.chain) - 1

    def child(self, agent: AgentName) -> TeamDeps:
        return TeamDeps(agent=agent, state=self.state, chain=[*self.chain, agent])
