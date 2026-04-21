import json

import pytest


class TestLettaHistoryMigration:
    def _build_db(self, tmp_path):
        from hermes_state import SessionDB

        db_path = tmp_path / "state.db"
        db = SessionDB(db_path=db_path)
        return db, db_path

    def _provider(self):
        from plugins.memory.letta import LettaConfig, LettaMemoryProvider

        provider = LettaMemoryProvider()
        provider._initialized = True
        provider._config = LettaConfig(base_url="https://letta.test")
        provider._client = object()
        provider._agent_id = "agent-123"
        provider._canonical_user_id = "telegram:73784266"
        return provider

    def test_migrate_state_db_history_imports_cli_and_telegram_turns_into_unified_agent(self, tmp_path, monkeypatch):
        db, db_path = self._build_db(tmp_path)
        db.create_session("tg-1", "telegram", user_id="73784266")
        db.append_message("tg-1", "user", "Tolong cek lane invoice staging sekarang.")
        db.append_message("tg-1", "assistant", "Siap, gue cek lane invoice staging sekarang.")

        db.create_session("cli-1", "cli")
        db.append_message("cli-1", "user", "Trace kenapa POS submit tidak bikin request.")
        db.append_message("cli-1", "assistant", "Oke, gue trace event submit POS sampai ketemu penyebabnya.")

        db.create_session("cron-1", "cron")
        db.append_message("cron-1", "user", "noise")
        db.append_message("cron-1", "assistant", "skip me")

        provider = self._provider()
        stored = []
        provider._store_memory = lambda content, **kwargs: stored.append({"content": content, **kwargs}) or {"status": "stored"}
        ensured = []
        monkeypatch.setattr(provider, "_ensure_agent", lambda: ensured.append(provider._canonical_user_id) or "agent-unified")

        result = provider.migrate_state_db_history(
            str(db_path),
            target_canonical_user_id="owner:73784266",
        )

        assert result["dry_run"] is False
        assert result["sessions_scanned"] == 3
        assert result["sessions_selected"] == 2
        assert result["skipped_sessions"] == 1
        assert result["imported_sessions"] == 2
        assert result["imported_turns"] == 2
        assert result["stored_passages"] == 4
        assert result["target_canonical_user_id"] == "owner:73784266"
        assert ensured == ["owner:73784266"]
        assert provider._canonical_user_id == "owner:73784266"
        assert provider._agent_id == "agent-unified"
        assert {item["session_id"] for item in stored} == {"tg-1", "cli-1"}
        assert {item["metadata"]["session_source"] for item in stored} == {"telegram", "cli"}
        assert all(item["memory_type"] == "episodic" for item in stored)
        assert all(item["source"] == "migrated_session_history" for item in stored)
        assert all(item["metadata"]["turn_index"] == 1 for item in stored)

    def test_migrate_state_db_history_skips_existing_migrated_passages(self, tmp_path, monkeypatch):
        db, db_path = self._build_db(tmp_path)
        db.create_session("tg-1", "telegram", user_id="73784266")
        db.append_message("tg-1", "user", "Trace billing lane sekarang.")
        db.append_message("tg-1", "assistant", "Siap, gue trace billing lane sekarang.")

        provider = self._provider()

        class DummyClient:
            def list_archival_memory(self, agent_id, limit=100):
                return [
                    {
                        "text": '{"memory_type":"episodic","content":"Trace billing lane sekarang.","source":"migrated_session_history","session_id":"tg-1","metadata":{"role":"user"}}'
                    },
                    {
                        "text": '{"memory_type":"episodic","content":"Siap, gue trace billing lane sekarang.","source":"migrated_session_history","session_id":"tg-1","metadata":{"role":"assistant"}}'
                    },
                ]

        provider._client = DummyClient()
        provider._store_memory = lambda *args, **kwargs: pytest.fail("existing migrated passages must not be written again")
        monkeypatch.setattr(provider, "_ensure_agent", lambda: "agent-unified")

        result = provider.migrate_state_db_history(
            str(db_path),
            target_canonical_user_id="owner:73784266",
        )

        assert result["imported_sessions"] == 0
        assert result["imported_turns"] == 0
        assert result["stored_passages"] == 0

    def test_migrate_state_db_history_skips_existing_chunked_migrated_passages(self, tmp_path, monkeypatch):
        db, db_path = self._build_db(tmp_path)
        long_text = (
            "Paragraph one explains the staging invoice route behavior in detail. "
            "Paragraph two keeps going so the provider has to split the stored continuity record into chunks. "
            "Paragraph three adds even more detail for the chunking dedup test."
        )
        db.create_session("tg-1", "telegram", user_id="73784266")
        db.append_message("tg-1", "user", long_text)
        db.append_message("tg-1", "assistant", long_text)

        provider = self._provider()
        provider._conversation_chunk_chars = 90
        user_chunks = provider._chunk_message(long_text, provider._conversation_chunk_chars)
        assistant_chunks = provider._chunk_message(long_text, provider._conversation_chunk_chars)

        class DummyClient:
            def list_archival_memory(self, agent_id, limit=100):
                rows = []
                for role, chunks in (("user", user_chunks), ("assistant", assistant_chunks)):
                    for chunk in chunks:
                        rows.append(
                            {
                                "text": json.dumps(
                                    {
                                        "memory_type": "episodic",
                                        "content": chunk,
                                        "source": "migrated_session_history",
                                        "session_id": "tg-1",
                                        "metadata": {"role": role},
                                    }
                                )
                            }
                        )
                return rows

        provider._client = DummyClient()
        provider._store_memory = lambda *args, **kwargs: pytest.fail("existing chunked migrated passages must not be written again")
        monkeypatch.setattr(provider, "_ensure_agent", lambda: "agent-unified")

        result = provider.migrate_state_db_history(
            str(db_path),
            target_canonical_user_id="owner:73784266",
        )

        assert result["imported_sessions"] == 0
        assert result["imported_turns"] == 0
        assert result["stored_passages"] == 0

    def test_migrate_state_db_history_dry_run_reports_counts_without_writing(self, tmp_path, monkeypatch):
        db, db_path = self._build_db(tmp_path)
        db.create_session("tg-1", "telegram", user_id="73784266")
        db.append_message("tg-1", "user", "Please inspect the deploy lane.")
        db.append_message("tg-1", "assistant", "I will inspect the deploy lane now.")

        provider = self._provider()
        provider._store_memory = lambda *args, **kwargs: pytest.fail("dry run must not write to Letta")
        monkeypatch.setattr(provider, "_ensure_agent", lambda: pytest.fail("dry run must not create or switch Letta agent"))

        result = provider.migrate_state_db_history(
            str(db_path),
            target_canonical_user_id="owner:73784266",
            dry_run=True,
        )

        assert result == {
            "dry_run": True,
            "sessions_scanned": 1,
            "sessions_selected": 1,
            "skipped_sessions": 0,
            "estimated_sessions": 1,
            "estimated_turns": 1,
            "estimated_passages": 2,
            "target_canonical_user_id": "owner:73784266",
        }
