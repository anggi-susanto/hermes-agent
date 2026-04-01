from __future__ import annotations

import sqlite3

from hermes_state import SCHEMA_VERSION, SessionDB


def test_board_tables_exist_and_session_tables_still_work(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        rows = db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        names = {row[0] for row in rows}
        assert "board_connections" in names
        assert "board_items" in names
        assert "board_links" in names
        assert "board_sync_events" in names

        db.create_session("sess_1", "cli")
        db.append_message("sess_1", role="user", content="masih waras")
        assert db.get_session("sess_1")["message_count"] == 1
    finally:
        db.close()


def test_board_schema_upgrade_from_v6_migrates_cleanly(tmp_path):
    db_path = tmp_path / "migrate.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version (version) VALUES (6);

        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            user_id TEXT,
            model TEXT,
            model_config TEXT,
            system_prompt TEXT,
            parent_session_id TEXT,
            started_at REAL NOT NULL,
            ended_at REAL,
            end_reason TEXT,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            billing_provider TEXT,
            billing_base_url TEXT,
            billing_mode TEXT,
            estimated_cost_usd REAL,
            actual_cost_usd REAL,
            cost_status TEXT,
            cost_source TEXT,
            pricing_version TEXT,
            title TEXT
        );

        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role TEXT NOT NULL,
            content TEXT,
            tool_call_id TEXT,
            tool_calls TEXT,
            tool_name TEXT,
            timestamp REAL NOT NULL,
            token_count INTEGER,
            finish_reason TEXT,
            reasoning TEXT,
            reasoning_details TEXT,
            codex_reasoning_items TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO sessions (id, source, started_at) VALUES (?, ?, ?)",
        ("existing", "cli", 1711970000.0),
    )
    conn.commit()
    conn.close()

    db = SessionDB(db_path)
    try:
        version = db._conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == SCHEMA_VERSION

        names = {
            row[0]
            for row in db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert {"board_connections", "board_items", "board_links", "board_sync_events"}.issubset(names)
        assert db.get_session("existing")["source"] == "cli"
    finally:
        db.close()


def test_board_crud_helpers_roundtrip(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        db.create_session("sess_1", "cli")

        db.upsert_board_connection(
            connection_id="conn_1",
            provider="paperclip",
            company_id="comp_1",
            company_slug="acme",
            company_name="Acme",
            auth_mode="agent_key",
            credential_ref="paperclip:default",
            provider_user_id="agent_1",
            provider_user_name="Hermes",
            is_active=True,
            raw={"hello": "world"},
        )
        connection = db.get_board_connection("conn_1")
        assert connection is not None
        assert connection["provider"] == "paperclip"
        assert connection["raw"]["hello"] == "world"

        db.upsert_board_item(
            item_id="item_1",
            connection_id="conn_1",
            item_type="issue",
            remote_item_id="iss_1",
            parent_remote_item_id="proj_1",
            title="Board sync MVP",
            status="in_progress",
            remote_updated_at="2026-04-01T14:12:00Z",
            payload={"id": "iss_1", "title": "Board sync MVP"},
        )
        db.upsert_board_item(
            item_id="item_1",
            connection_id="conn_1",
            item_type="issue",
            remote_item_id="iss_1",
            title="Board sync MVP updated",
            status="completed",
            remote_updated_at="2026-04-01T14:20:00Z",
            payload={"id": "iss_1", "title": "Board sync MVP updated"},
        )

        db.link_session_to_board_item(
            link_id="link_1",
            session_id="sess_1",
            connection_id="conn_1",
            item_id="item_1",
            remote_item_id="iss_1",
            item_type="issue",
            relationship="primary",
            metadata={"source": "unit-test"},
        )
        links = db.list_board_links_for_session("sess_1")
        assert len(links) == 1
        assert links[0]["remote_item_id"] == "iss_1"
        assert links[0]["metadata"]["source"] == "unit-test"

        db.record_board_sync_event(
            event_id="evt_1",
            connection_id="conn_1",
            session_id="sess_1",
            event_type="pull",
            operation="snapshot",
            item_type="issue",
            remote_item_id="iss_1",
            status="success",
            cursor="cursor_1",
            detail={"count": 1},
        )
        rows = db.list_board_sync_events("conn_1")
        assert len(rows) == 1
        assert rows[0]["detail"]["count"] == 1
        assert rows[0]["cursor"] == "cursor_1"
    finally:
        db.close()
