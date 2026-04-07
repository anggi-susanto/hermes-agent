from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from integrations.boards.models import BoardConnection, CompanySnapshot, IssueRef


class BoardError(RuntimeError):
    """Base exception for board-provider failures."""


class BoardAuthError(BoardError):
    """Raised when credentials are missing or rejected by the remote board."""


class BoardNotFoundError(BoardError):
    """Raised when the requested remote item does not exist."""


class BoardConflictError(BoardError):
    """Raised when a remote write collides with existing board state."""


class BoardValidationError(BoardError):
    """Raised when a request payload is invalid for the provider."""


@dataclass(frozen=True)
class BoardIdentity:
    provider: str
    provider_user_id: str
    provider_user_name: str | None = None
    provider_user_email: str | None = None
    company_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteItemRef:
    provider: str
    item_type: str
    remote_item_id: str
    title: str | None = None
    status: str | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IssueCommentRef:
    id: str
    issue_id: str
    body: str
    author_agent_id: str | None = None
    created_at: float | str | None = None
    updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateIssue:
    title: str
    body: str | None = None
    company_id: str | None = None
    project_id: str | None = None
    goal_id: str | None = None
    assignee_agent_id: str | None = None
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateIssue:
    title: str | None = None
    body: str | None = None
    status: str | None = None
    project_id: str | None = None
    goal_id: str | None = None
    assignee_agent_id: str | None = None
    remote_updated_at: float | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AddComment:
    body: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateApproval:
    issue_id: str
    body: str | None = None
    reviewer_agent_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class BoardProvider(Protocol):
    """Normalized board adapter contract.

    Providers must preserve safe raw payload fragments on returned objects where
    useful for debugging, but must not leak secrets into raw payloads.

    Conflict handling semantics:
    - validation/auth/not-found/conflict should raise typed Board*Error variants
    - update methods should honor provider-native conflict signals, typically by
      comparing remote_updated_at or version-like fields when available
    """

    provider_id: str

    def validate_credentials(self, connection: BoardConnection) -> BoardIdentity:
        """Validate remote credentials and return the authenticated identity."""

    def fetch_company_snapshot(self, connection: BoardConnection) -> CompanySnapshot:
        """Fetch the top-level normalized company snapshot for the connection."""

    def list_issues(self, connection: BoardConnection, company_id: str | None = None) -> list[IssueRef]:
        """List normalized issues visible to the connection scope."""

    def get_issue(self, connection: BoardConnection, issue_id: str) -> IssueRef:
        """Fetch a single normalized issue by remote ID."""

    def create_issue(self, connection: BoardConnection, request: CreateIssue) -> IssueRef:
        """Create a remote issue from normalized request DTO data."""

    def update_issue(self, connection: BoardConnection, issue_id: str, request: UpdateIssue) -> IssueRef:
        """Update a remote issue from normalized request DTO data."""

    def checkout_issue(self, connection: BoardConnection, issue_id: str) -> RemoteItemRef:
        """Acquire provider-native execution ownership/checkout for an issue."""

    def release_issue(self, connection: BoardConnection, issue_id: str) -> RemoteItemRef:
        """Release provider-native execution ownership/checkout for an issue."""

    def list_issue_comments(self, connection: BoardConnection, issue_id: str) -> list[IssueCommentRef]:
        """List issue comments in normalized order."""

    def add_issue_comment(
        self,
        connection: BoardConnection,
        issue_id: str,
        request: AddComment,
    ) -> IssueCommentRef:
        """Append a comment/evidence note to the remote issue."""
