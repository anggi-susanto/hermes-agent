from __future__ import annotations

from typing import Any

from hermes_state import SessionDB
from integrations.boards.models import CompanySnapshot, IssueRef


class BoardSyncStore:
    def __init__(self, db: SessionDB):
        self.db = db

    def cache_snapshot(self, connection_id: str, snapshot: CompanySnapshot) -> None:
        company = snapshot.company
        self.db.upsert_board_connection(
            connection_id=connection_id,
            provider=(self.db.get_board_connection(connection_id) or {}).get("provider", "unknown"),
            company_id=company.id,
            company_slug=company.slug,
            company_name=company.name,
            raw=snapshot.raw,
        )
        for issue in snapshot.issues:
            self.db.upsert_board_item(
                item_id=f"{connection_id}:issue:{issue.id}",
                connection_id=connection_id,
                item_type="issue",
                remote_item_id=issue.id,
                parent_remote_item_id=issue.project_id,
                title=issue.title,
                status=issue.status,
                remote_updated_at=str(issue.remote_updated_at) if issue.remote_updated_at is not None else None,
                payload=issue.raw,
            )

    def link_session_issue(self, connection_id: str, session_id: str, issue_id: str) -> str:
        return self.db.link_session_to_board_item(
            link_id=f"{session_id}:{connection_id}:issue:{issue_id}:primary",
            session_id=session_id,
            connection_id=connection_id,
            item_id=f"{connection_id}:issue:{issue_id}",
            remote_item_id=issue_id,
            item_type="issue",
            relationship="primary",
            metadata={"remote_item_id": issue_id},
        )

    def record_pull(
        self,
        connection_id: str,
        cursor: str | None,
        detail: dict[str, Any],
        session_id: str | None = None,
    ) -> str:
        return self.db.record_board_sync_event(
            event_id=f"{connection_id}:pull:{cursor or 'latest'}:{len(detail)}",
            connection_id=connection_id,
            session_id=session_id,
            event_type="pull",
            operation="snapshot",
            status="success",
            cursor=cursor,
            detail=detail,
        )

    def record_push(
        self,
        connection_id: str,
        operation: str,
        remote_item_id: str | None,
        detail: dict[str, Any],
        session_id: str | None = None,
    ) -> str:
        return self.db.record_board_sync_event(
            event_id=f"{connection_id}:push:{operation}:{remote_item_id or 'none'}:{len(detail)}",
            connection_id=connection_id,
            session_id=session_id,
            event_type="push",
            operation=operation,
            item_type="issue" if remote_item_id else None,
            remote_item_id=remote_item_id,
            status="success",
            detail=detail,
        )

    def list_cached_items(self, connection_id: str, item_type: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [connection_id]
        sql = "SELECT * FROM board_items WHERE connection_id = ?"
        if item_type is not None:
            sql += " AND item_type = ?"
            params.append(item_type)
        sql += " ORDER BY updated_at DESC, id DESC"
        with self.db._lock:
            rows = self.db._conn.execute(sql, params).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["payload"] = self.db._json_loads(item.get("payload"))
            items.append(item)
        return items

    def detect_remote_update_drift(
        self,
        connection_id: str,
        remote_item_id: str,
        remote_updated_at: str | None,
    ) -> bool | None:
        with self.db._lock:
            row = self.db._conn.execute(
                """
                SELECT remote_updated_at
                FROM board_items
                WHERE connection_id = ? AND item_type = 'issue' AND remote_item_id = ?
                LIMIT 1
                """,
                (connection_id, remote_item_id),
            ).fetchone()
        if row is None:
            return None
        cached = row[0]
        return cached != remote_updated_at
