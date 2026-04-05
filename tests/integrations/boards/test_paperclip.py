from __future__ import annotations

import httpx
import pytest

from integrations.boards.base import AddComment, BoardConflictError, BoardIdentity, CreateIssue, UpdateIssue
from integrations.boards.models import BoardConnection
from integrations.boards.paperclip import PaperclipBoardProvider


@pytest.fixture
def board_connection() -> BoardConnection:
    return BoardConnection(
        id="conn_1",
        provider="paperclip",
        company_id="comp_1",
        company_slug="acme",
        company_name="Acme",
        auth_mode="agent_key",
        credential_ref="paperclip:default",
        raw={"api_key": "pc_test_key"},
    )


@pytest.fixture
def provider_transport():
    requests: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization")
        assert auth == "Bearer pc_test_key"
        body = None
        if request.content:
            body = request.read().decode("utf-8")
        requests.append((request.method, str(request.url), dict(request.headers), body))

        if request.method == "GET" and str(request.url) == "https://paperclip.ing/api/agents/me":
            return httpx.Response(200, json={"id": "agent_123", "name": "Hermes", "email": "hermes@paperclip.ing"})
        if request.method == "GET" and str(request.url) == "https://paperclip.ing/api/companies/comp_1":
            return httpx.Response(200, json={"id": "comp_1", "name": "Acme", "slug": "acme"})
        if request.method == "GET" and str(request.url) == "https://paperclip.ing/api/companies/comp_1/agents":
            return httpx.Response(200, json={"items": [{"id": "agent_123", "name": "Hermes", "role": "operator"}]})
        if request.method == "GET" and str(request.url) == "https://paperclip.ing/api/companies/comp_1/issues":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "iss_1",
                            "companyId": "comp_1",
                            "title": "Fix checkout flow",
                            "description": "Make it less cursed",
                            "status": "in_progress",
                            "projectId": "proj_1",
                            "goalId": "goal_1",
                            "assigneeAgentId": "agent_123",
                            "updatedAt": "2026-04-01T14:00:00Z",
                        }
                    ]
                },
            )
        if request.method == "GET" and str(request.url) == "https://paperclip.ing/api/companies/comp_1/projects":
            return httpx.Response(200, json={"items": [{"id": "proj_1", "companyId": "comp_1", "name": "Core"}]})
        if request.method == "GET" and str(request.url) == "https://paperclip.ing/api/companies/comp_1/goals":
            return httpx.Response(200, json={"items": [{"id": "goal_1", "companyId": "comp_1", "projectId": "proj_1", "name": "Stability"}]})
        if request.method == "GET" and str(request.url) == "https://paperclip.ing/api/issues/iss_1":
            return httpx.Response(
                200,
                json={
                    "id": "iss_1",
                    "companyId": "comp_1",
                    "title": "Fix checkout flow",
                    "description": "Make it less cursed",
                    "status": "done",
                    "updatedAt": "2026-04-01T14:10:00Z",
                },
            )
        if request.method == "POST" and str(request.url) == "https://paperclip.ing/api/issues":
            return httpx.Response(
                201,
                json={
                    "id": "iss_created",
                    "companyId": "comp_1",
                    "title": "New issue",
                    "description": "Ship it",
                    "status": "todo",
                    "projectId": "proj_1",
                    "goalId": "goal_1",
                },
            )
        if request.method == "PATCH" and str(request.url) == "https://paperclip.ing/api/issues/iss_1":
            return httpx.Response(
                200,
                json={
                    "id": "iss_1",
                    "companyId": "comp_1",
                    "title": "Fix checkout flow now",
                    "description": "Patched",
                    "status": "done",
                    "updatedAt": "2026-04-01T14:20:00Z",
                },
            )
        if request.method == "POST" and str(request.url) == "https://paperclip.ing/api/issues/iss_1/checkout":
            return httpx.Response(200, json={"id": "iss_1", "status": "checked_out"})
        if request.method == "POST" and str(request.url) == "https://paperclip.ing/api/issues/iss_1/release":
            return httpx.Response(200, json={"id": "iss_1", "status": "released"})
        if request.method == "GET" and str(request.url) == "https://paperclip.ing/api/issues/iss_1/comments":
            return httpx.Response(200, json={"items": [{"id": "c_1", "issueId": "iss_1", "body": "LGTM", "authorAgentId": "agent_123"}]})
        if request.method == "POST" and str(request.url) == "https://paperclip.ing/api/issues/iss_1/comments":
            return httpx.Response(201, json={"id": "c_2", "issueId": "iss_1", "body": "evidence posted", "authorAgentId": "agent_123"})
        if request.method == "POST" and str(request.url) == "https://paperclip.ing/api/issues/iss_conflict/checkout":
            return httpx.Response(409, json={"error": "already checked out"})
        raise AssertionError(f"Unhandled request: {request.method} {request.url}")

    return requests, httpx.MockTransport(handler)


def test_validate_credentials_uses_agents_me(board_connection, provider_transport):
    requests, transport = provider_transport
    provider = PaperclipBoardProvider(transport=transport)

    identity = provider.validate_credentials(board_connection)

    assert isinstance(identity, BoardIdentity)
    assert identity.provider_user_id == "agent_123"
    assert identity.provider_user_name == "Hermes"
    assert requests[0][0:2] == ("GET", "https://paperclip.ing/api/agents/me")


def test_fetch_company_snapshot_normalizes_entities(board_connection, provider_transport):
    _, transport = provider_transport
    provider = PaperclipBoardProvider(transport=transport)

    snapshot = provider.fetch_company_snapshot(board_connection)

    assert snapshot.company.id == "comp_1"
    assert len(snapshot.issues) == 1
    assert snapshot.issues[0].status == "in_progress"
    assert len(snapshot.projects) == 1
    assert len(snapshot.goals) == 1
    assert len(snapshot.agents) == 1
    assert snapshot.raw["company"]["id"] == "comp_1"


def test_issue_workflow_methods_create_update_comment_checkout_and_release(board_connection, provider_transport):
    _, transport = provider_transport
    provider = PaperclipBoardProvider(transport=transport)

    issues = provider.list_issues(board_connection)
    issue = provider.get_issue(board_connection, "iss_1")
    created = provider.create_issue(
        board_connection,
        CreateIssue(
            title="New issue",
            body="Ship it",
            company_id="comp_1",
            project_id="proj_1",
            goal_id="goal_1",
            status="pending",
        ),
    )
    updated = provider.update_issue(
        board_connection,
        "iss_1",
        UpdateIssue(title="Fix checkout flow now", body="Patched", status="completed"),
    )
    checkout = provider.checkout_issue(board_connection, "iss_1")
    release = provider.release_issue(board_connection, "iss_1")
    comments = provider.list_issue_comments(board_connection, "iss_1")
    comment = provider.add_issue_comment(board_connection, "iss_1", AddComment(body="evidence posted"))

    assert issues[0].id == "iss_1"
    assert issue.status == "completed"
    assert created.status == "pending"
    assert updated.status == "completed"
    assert checkout.status == "checked_out"
    assert release.status == "released"
    assert comments[0].body == "LGTM"
    assert comment.body == "evidence posted"


def test_checkout_issue_maps_409_to_conflict(board_connection):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "already checked out"})

    provider = PaperclipBoardProvider(transport=httpx.MockTransport(handler))

    with pytest.raises(BoardConflictError):
        provider.checkout_issue(board_connection, "iss_conflict")
