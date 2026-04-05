from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

import httpx

from hermes_cli.board_auth import BOARD_PROVIDER_REGISTRY
from integrations.boards.base import (
    AddComment,
    BoardAuthError,
    BoardConflictError,
    BoardIdentity,
    BoardNotFoundError,
    BoardValidationError,
    CreateIssue,
    IssueCommentRef,
    RemoteItemRef,
    UpdateIssue,
)
from integrations.boards.models import (
    AgentRef,
    BoardConnection,
    CompanyRef,
    CompanySnapshot,
    GoalRef,
    IssueRef,
    ProjectRef,
    map_remote_issue_status,
)


class PaperclipBoardProvider:
    provider_id = "paperclip"

    def __init__(
        self,
        api_base_url: str | None = None,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ):
        registry = BOARD_PROVIDER_REGISTRY[self.provider_id]
        self.api_base_url = (api_base_url or registry.api_base_url).rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def validate_credentials(self, connection: BoardConnection) -> BoardIdentity:
        payload = self._request(connection, "GET", "/agents/me")
        return BoardIdentity(
            provider=self.provider_id,
            provider_user_id=str(payload.get("id") or ""),
            provider_user_name=payload.get("name"),
            provider_user_email=payload.get("email"),
            company_id=connection.company_id,
            raw=self._safe_raw(payload),
        )

    def fetch_company_snapshot(self, connection: BoardConnection) -> CompanySnapshot:
        company_id = self._require_company_id(connection)
        company = self._request(connection, "GET", f"/companies/{company_id}")
        agents = self._extract_items(self._request(connection, "GET", f"/companies/{company_id}/agents"))
        issues = self._extract_items(self._request(connection, "GET", f"/companies/{company_id}/issues"))
        projects = self._extract_items(self._request(connection, "GET", f"/companies/{company_id}/projects"))
        goals = self._extract_items(self._request(connection, "GET", f"/companies/{company_id}/goals"))
        return CompanySnapshot(
            company=self._to_company(company),
            agents=[self._to_agent(item) for item in agents],
            issues=[self._to_issue(item) for item in issues],
            projects=[self._to_project(item) for item in projects],
            goals=[self._to_goal(item) for item in goals],
            raw={
                "company": self._safe_raw(company),
                "agents": [self._safe_raw(item) for item in agents],
                "issues": [self._safe_raw(item) for item in issues],
                "projects": [self._safe_raw(item) for item in projects],
                "goals": [self._safe_raw(item) for item in goals],
            },
        )

    def list_issues(self, connection: BoardConnection, company_id: str | None = None) -> list[IssueRef]:
        target_company_id = company_id or self._require_company_id(connection)
        payload = self._request(connection, "GET", f"/companies/{target_company_id}/issues")
        return [self._to_issue(item) for item in self._extract_items(payload)]

    def get_issue(self, connection: BoardConnection, issue_id: str) -> IssueRef:
        payload = self._request(connection, "GET", f"/issues/{issue_id}")
        return self._to_issue(payload)

    def create_issue(self, connection: BoardConnection, request: CreateIssue) -> IssueRef:
        payload = self._request(connection, "POST", "/issues", json=self._create_issue_payload(connection, request))
        return self._to_issue(payload)

    def update_issue(self, connection: BoardConnection, issue_id: str, request: UpdateIssue) -> IssueRef:
        payload = self._request(connection, "PATCH", f"/issues/{issue_id}", json=self._update_issue_payload(request))
        return self._to_issue(payload)

    def checkout_issue(self, connection: BoardConnection, issue_id: str) -> RemoteItemRef:
        payload = self._request(connection, "POST", f"/issues/{issue_id}/checkout")
        return self._to_remote_item(issue_id, payload)

    def release_issue(self, connection: BoardConnection, issue_id: str) -> RemoteItemRef:
        payload = self._request(connection, "POST", f"/issues/{issue_id}/release")
        return self._to_remote_item(issue_id, payload)

    def list_issue_comments(self, connection: BoardConnection, issue_id: str) -> list[IssueCommentRef]:
        payload = self._request(connection, "GET", f"/issues/{issue_id}/comments")
        return [self._to_comment(item) for item in self._extract_items(payload)]

    def add_issue_comment(self, connection: BoardConnection, issue_id: str, request: AddComment) -> IssueCommentRef:
        payload = self._request(connection, "POST", f"/issues/{issue_id}/comments", json={"body": request.body, **request.raw})
        return self._to_comment(payload)

    def _request(
        self,
        connection: BoardConnection,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._resolve_api_key(connection)}",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"

        with httpx.Client(base_url=self.api_base_url, timeout=self.timeout, transport=self.transport) as client:
            response = client.request(method, path, json=json, headers=headers)

        if response.status_code in (401, 403):
            raise BoardAuthError(f"Paperclip auth failed for {method} {path}")
        if response.status_code == 404:
            raise BoardNotFoundError(f"Paperclip item not found for {method} {path}")
        if response.status_code == 409:
            raise BoardConflictError(f"Paperclip conflict for {method} {path}")
        if response.status_code == 400:
            raise BoardValidationError(f"Paperclip validation failed for {method} {path}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise BoardValidationError(f"Paperclip returned non-object payload for {method} {path}")
        return payload

    def _resolve_api_key(self, connection: BoardConnection) -> str:
        raw_key = connection.raw.get("api_key") if isinstance(connection.raw, dict) else None
        if raw_key:
            return str(raw_key)
        for env_var in BOARD_PROVIDER_REGISTRY[self.provider_id].api_key_env_vars:
            value = os.getenv(env_var)
            if value:
                return value
        raise BoardAuthError("Missing Paperclip API key")

    def _require_company_id(self, connection: BoardConnection) -> str:
        company_id = connection.company_id or (connection.raw or {}).get("company_id")
        if not company_id:
            raise BoardValidationError("Paperclip board connection requires company_id")
        return str(company_id)

    @staticmethod
    def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        items = payload.get("items", payload.get("data", []))
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []

    @staticmethod
    def _safe_raw(payload: dict[str, Any]) -> dict[str, Any]:
        redacted = dict(payload)
        for key in list(redacted.keys()):
            if "token" in key.lower() or "key" in key.lower() or "secret" in key.lower():
                redacted.pop(key, None)
        return redacted

    def _to_company(self, payload: dict[str, Any]) -> CompanyRef:
        return CompanyRef(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            slug=payload.get("slug"),
            created_at=payload.get("createdAt") or payload.get("created_at"),
            updated_at=payload.get("updatedAt") or payload.get("updated_at"),
            raw=self._safe_raw(payload),
        )

    def _to_agent(self, payload: dict[str, Any]) -> AgentRef:
        return AgentRef(
            id=str(payload.get("id") or ""),
            company_id=payload.get("companyId") or payload.get("company_id"),
            name=str(payload.get("name") or ""),
            email=payload.get("email"),
            role=payload.get("role"),
            created_at=payload.get("createdAt") or payload.get("created_at"),
            updated_at=payload.get("updatedAt") or payload.get("updated_at"),
            raw=self._safe_raw(payload),
        )

    def _to_issue(self, payload: dict[str, Any]) -> IssueRef:
        return IssueRef(
            id=str(payload.get("id") or ""),
            company_id=payload.get("companyId") or payload.get("company_id"),
            title=str(payload.get("title") or ""),
            status=map_remote_issue_status(payload.get("status")),
            body=payload.get("description") or payload.get("body"),
            project_id=payload.get("projectId") or payload.get("project_id"),
            goal_id=payload.get("goalId") or payload.get("goal_id"),
            assignee_agent_id=payload.get("assigneeAgentId") or payload.get("assignee_agent_id"),
            created_at=payload.get("createdAt") or payload.get("created_at"),
            updated_at=payload.get("updatedAt") or payload.get("updated_at"),
            remote_updated_at=payload.get("updatedAt") or payload.get("updated_at"),
            raw=self._safe_raw(payload),
        )

    def _to_project(self, payload: dict[str, Any]) -> ProjectRef:
        return ProjectRef(
            id=str(payload.get("id") or ""),
            company_id=payload.get("companyId") or payload.get("company_id"),
            name=str(payload.get("name") or ""),
            slug=payload.get("slug"),
            description=payload.get("description"),
            created_at=payload.get("createdAt") or payload.get("created_at"),
            updated_at=payload.get("updatedAt") or payload.get("updated_at"),
            raw=self._safe_raw(payload),
        )

    def _to_goal(self, payload: dict[str, Any]) -> GoalRef:
        return GoalRef(
            id=str(payload.get("id") or ""),
            company_id=payload.get("companyId") or payload.get("company_id"),
            project_id=payload.get("projectId") or payload.get("project_id"),
            name=str(payload.get("name") or ""),
            status=payload.get("status"),
            created_at=payload.get("createdAt") or payload.get("created_at"),
            updated_at=payload.get("updatedAt") or payload.get("updated_at"),
            raw=self._safe_raw(payload),
        )

    def _to_remote_item(self, issue_id: str, payload: dict[str, Any]) -> RemoteItemRef:
        return RemoteItemRef(
            provider=self.provider_id,
            item_type="issue",
            remote_item_id=str(payload.get("id") or issue_id),
            title=payload.get("title"),
            status=payload.get("status"),
            raw=self._safe_raw(payload),
        )

    def _to_comment(self, payload: dict[str, Any]) -> IssueCommentRef:
        return IssueCommentRef(
            id=str(payload.get("id") or ""),
            issue_id=str(payload.get("issueId") or payload.get("issue_id") or ""),
            body=str(payload.get("body") or ""),
            author_agent_id=payload.get("authorAgentId") or payload.get("author_agent_id"),
            created_at=payload.get("createdAt") or payload.get("created_at"),
            updated_at=payload.get("updatedAt") or payload.get("updated_at"),
            raw=self._safe_raw(payload),
        )

    def _create_issue_payload(self, connection: BoardConnection, request: CreateIssue) -> dict[str, Any]:
        payload = {
            "title": request.title,
            "description": request.body,
            "companyId": request.company_id or self._require_company_id(connection),
            "projectId": request.project_id,
            "goalId": request.goal_id,
            "assigneeAgentId": request.assignee_agent_id,
            "status": self._to_remote_status(request.status),
        }
        payload.update(request.raw)
        return {key: value for key, value in payload.items() if value is not None}

    def _update_issue_payload(self, request: UpdateIssue) -> dict[str, Any]:
        payload = {
            "title": request.title,
            "description": request.body,
            "status": self._to_remote_status(request.status),
            "projectId": request.project_id,
            "goalId": request.goal_id,
            "assigneeAgentId": request.assignee_agent_id,
            "remoteUpdatedAt": request.remote_updated_at,
        }
        payload.update(request.raw)
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _to_remote_status(value: str | None) -> str | None:
        if value is None:
            return None
        mapping = {
            "pending": "todo",
            "in_progress": "in_progress",
            "completed": "done",
            "cancelled": "cancelled",
        }
        return mapping.get(value, value)
