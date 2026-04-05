from __future__ import annotations

from integrations.boards.base import BoardProvider
from integrations.boards.models import CompanyRef, CompanySnapshot, IssueRef
from integrations.boards.sync import BoardSyncStore
from hermes_state import SessionDB


def test_board_provider_contract_has_issue_methods():
    required = {
        "validate_credentials",
        "fetch_company_snapshot",
        "list_issues",
        "get_issue",
        "create_issue",
        "update_issue",
        "checkout_issue",
        "release_issue",
        "list_issue_comments",
        "add_issue_comment",
    }
    assert required.issubset(set(BoardProvider.__dict__.keys()))


def test_sync_store_caches_snapshot_links_issue_and_records_events(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        db.create_session("sess_1", "cli")
        db.upsert_board_connection(
            connection_id="conn_1",
            provider="paperclip",
            company_id="comp_1",
            company_slug="acme",
            company_name="Acme",
            credential_ref="***",
            raw={"seed": True},
        )

        store = BoardSyncStore(db)
        snapshot = CompanySnapshot(
            company=CompanyRef(id="comp_1", name="Acme", slug="acme", raw={"company": True}),
            issues=[
                IssueRef(
                    id="iss_1",
                    company_id="comp_1",
                    title="Investigate sync drift",
                    status="in_progress",
                    project_id="proj_1",
                    remote_updated_at="2026-04-01T14:10:00Z",
                    raw={"issue": 1},
                )
            ],
            raw={"snapshot": 1},
        )

        store.cache_snapshot("conn_1", snapshot)
        store.link_session_issue("conn_1", "sess_1", "iss_1")
        store.record_pull("conn_1", cursor="cursor_1", detail={"count": 1}, session_id="sess_1")
        store.record_push(
            "conn_1",
            operation="update_issue",
            remote_item_id="iss_1",
            detail={"status": "completed"},
            session_id="sess_1",
        )

        items = store.list_cached_items("conn_1", item_type="issue")
        assert len(items) == 1
        assert items[0]["remote_item_id"] == "iss_1"
        assert items[0]["payload"]["issue"] == 1

        links = db.list_board_links_for_session("sess_1")
        assert len(links) == 1
        assert links[0]["remote_item_id"] == "iss_1"

        events = db.list_board_sync_events("conn_1")
        assert len(events) == 2
        assert {event["event_type"] for event in events} == {"pull", "push"}

    finally:
        db.close()


def test_sync_store_detects_remote_update_timestamp_drift(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        db.upsert_board_connection(
            connection_id="conn_1",
            provider="paperclip",
            company_id="comp_1",
        )
        store = BoardSyncStore(db)
        snapshot = CompanySnapshot(
            company=CompanyRef(id="comp_1", name="Acme"),
            issues=[
                IssueRef(
                    id="iss_1",
                    company_id="comp_1",
                    title="Investigate sync drift",
                    status="in_progress",
                    remote_updated_at="2026-04-01T14:10:00Z",
                    raw={"issue": 1},
                )
            ],
        )
        store.cache_snapshot("conn_1", snapshot)

        assert store.detect_remote_update_drift("conn_1", "iss_1", "2026-04-01T14:10:00Z") is False
        assert store.detect_remote_update_drift("conn_1", "iss_1", "2026-04-01T14:12:00Z") is True
        assert store.detect_remote_update_drift("conn_1", "iss_missing", "2026-04-01T14:12:00Z") is None
    finally:
        db.close()
