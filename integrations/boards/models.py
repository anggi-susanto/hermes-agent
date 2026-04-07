from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IssueStatus = Literal["pending", "in_progress", "completed", "cancelled", "unknown"]
RunStatus = Literal["queued", "running", "completed", "failed", "cancelled", "unknown"]


@dataclass(frozen=True)
class CompanyRef:
    id: str
    name: str
    slug: str | None = None
    created_at: float | str | None = None
    updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectRef:
    id: str
    company_id: str | None = None
    name: str = ""
    slug: str | None = None
    description: str | None = None
    created_at: float | str | None = None
    updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoalRef:
    id: str
    company_id: str | None = None
    project_id: str | None = None
    name: str = ""
    status: str | None = None
    created_at: float | str | None = None
    updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRef:
    id: str
    company_id: str | None = None
    name: str = ""
    email: str | None = None
    role: str | None = None
    created_at: float | str | None = None
    updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IssueRef:
    id: str
    company_id: str | None = None
    title: str = ""
    status: IssueStatus = "unknown"
    body: str | None = None
    project_id: str | None = None
    goal_id: str | None = None
    assignee_agent_id: str | None = None
    created_at: float | str | None = None
    updated_at: float | str | None = None
    remote_updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalRef:
    id: str
    issue_id: str | None = None
    status: str | None = None
    requested_by_agent_id: str | None = None
    approved_by_agent_id: str | None = None
    created_at: float | str | None = None
    updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HeartbeatRunRef:
    id: str
    issue_id: str | None = None
    agent_id: str | None = None
    status: RunStatus = "unknown"
    started_at: float | str | None = None
    finished_at: float | str | None = None
    updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActivityEventRef:
    id: str
    issue_id: str | None = None
    agent_id: str | None = None
    type: str = ""
    message: str | None = None
    created_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BoardConnection:
    id: str
    provider: str
    company_id: str | None = None
    company_slug: str | None = None
    company_name: str | None = None
    auth_mode: str = "agent_key"
    credential_ref: str | None = None
    is_active: bool = True
    provider_user_id: str | None = None
    provider_user_name: str | None = None
    created_at: float | str | None = None
    updated_at: float | str | None = None
    last_synced_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompanySnapshot:
    company: CompanyRef
    issues: list[IssueRef] = field(default_factory=list)
    projects: list[ProjectRef] = field(default_factory=list)
    goals: list[GoalRef] = field(default_factory=list)
    agents: list[AgentRef] = field(default_factory=list)
    approvals: list[ApprovalRef] = field(default_factory=list)
    heartbeat_runs: list[HeartbeatRunRef] = field(default_factory=list)
    activity_events: list[ActivityEventRef] = field(default_factory=list)
    fetched_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _normalize_status_token(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


ISSUE_STATUS_MAP: dict[str, IssueStatus] = {
    "todo": "pending",
    "to_do": "pending",
    "backlog": "pending",
    "open": "pending",
    "pending": "pending",
    "in_progress": "in_progress",
    "in_review": "in_progress",
    "review": "in_progress",
    "doing": "in_progress",
    "done": "completed",
    "completed": "completed",
    "resolved": "completed",
    "closed": "completed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "aborted": "cancelled",
}

RUN_STATUS_MAP: dict[str, RunStatus] = {
    "queued": "queued",
    "pending": "queued",
    "running": "running",
    "in_progress": "running",
    "processing": "running",
    "success": "completed",
    "succeeded": "completed",
    "completed": "completed",
    "done": "completed",
    "failed": "failed",
    "error": "failed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


def map_remote_issue_status(value: str | None) -> IssueStatus:
    return ISSUE_STATUS_MAP.get(_normalize_status_token(value), "unknown")



def map_remote_run_status(value: str | None) -> RunStatus:
    return RUN_STATUS_MAP.get(_normalize_status_token(value), "unknown")
