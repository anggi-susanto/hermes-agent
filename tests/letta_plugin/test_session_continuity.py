"""Dedicated Letta continuity tests for LRR-001."""

import pytest


class TestLettaSessionContinuity:
    def _provider(self):
        from plugins.memory.letta import LettaMemoryProvider, LettaConfig

        provider = LettaMemoryProvider()
        provider._initialized = True
        provider._config = LettaConfig(base_url="https://letta.test")
        provider._client = object()
        provider._agent_id = "agent-123"
        return provider

    def test_sync_turn_persists_non_transient_turn_as_role_scoped_records_with_session_id(self):
        provider = self._provider()
        stored = []
        provider._store_memory = lambda content, **kwargs: stored.append({"content": content, **kwargs}) or {"status": "stored"}

        provider.sync_turn(
            "Please inspect the staging branch and confirm the invoice route still responds.",
            "Got it, I will inspect staging and verify the invoice route before saying it is safe.",
            session_id="sess-lrr-001",
        )

        assert len(stored) == 2
        assert [item["memory_type"] for item in stored] == ["episodic", "episodic"]
        assert all(item["source"] == "turn_sync" for item in stored)
        assert all(item["session_id"] == "sess-lrr-001" for item in stored)
        assert all(item["confidence"] == pytest.approx(0.78) for item in stored)
        assert stored[0]["metadata"]["role"] == "user"
        assert stored[1]["metadata"]["role"] == "assistant"
        assert stored[0]["metadata"]["turn_index"] == 1
        assert stored[1]["metadata"]["turn_index"] == 1
        assert "invoice route" in stored[0]["content"].lower()
        assert "invoice route" in stored[1]["content"].lower()

    def test_sync_turn_skips_trivial_exchange_only(self):
        provider = self._provider()
        stored = []
        provider._store_memory = lambda content, **kwargs: stored.append({"content": content, **kwargs}) or {"status": "stored"}

        provider.sync_turn("ok", "sip")
        provider.sync_turn(
            "Track why the POS submit button fires no network request.",
            "I will trace the POS submit event path and prove whether the click reaches the handler.",
        )

        assert len(stored) == 2
        assert all(item["metadata"]["turn_index"] == 1 for item in stored)
        assert stored[0]["metadata"]["role"] == "user"
        assert stored[1]["metadata"]["role"] == "assistant"
        assert "pos submit" in stored[0]["content"].lower()

    def test_sync_turn_chunks_oversized_messages_and_marks_continuations(self):
        provider = self._provider()
        provider._conversation_chunk_chars = 90
        stored = []
        provider._store_memory = lambda content, **kwargs: stored.append({"content": content, **kwargs}) or {"status": "stored"}

        long_user = (
            "Paragraph one explains the staging invoice route behavior in detail. "
            "Paragraph two keeps going so the provider has to split the stored continuity record into chunks. "
            "Paragraph three adds even more detail for the chunking test to verify continuation markers."
        )
        long_assistant = (
            "I will inspect the staging route carefully and preserve every meaningful continuity detail. "
            "Then I will verify the request path, the rendered page, and the runtime response before closing the issue."
        )

        provider.sync_turn(long_user, long_assistant, session_id="sess-chunk")

        assert len(stored) >= 4
        user_chunks = [item for item in stored if item["metadata"]["role"] == "user"]
        assistant_chunks = [item for item in stored if item["metadata"]["role"] == "assistant"]
        assert len(user_chunks) >= 2
        assert len(assistant_chunks) >= 2
        assert user_chunks[0]["metadata"]["chunk_index"] == 1
        assert user_chunks[0]["metadata"]["chunk_total"] == len(user_chunks)
        assert user_chunks[1]["content"].startswith("[continued] ")
        assert assistant_chunks[1]["content"].startswith("[continued] ")
        assert all(item["session_id"] == "sess-chunk" for item in stored)

    def test_sync_turn_increments_turn_index_across_multiple_turns(self):
        provider = self._provider()
        stored = []
        provider._store_memory = lambda content, **kwargs: stored.append({"content": content, **kwargs}) or {"status": "stored"}

        provider.sync_turn(
            "Inspect the first issue in staging.",
            "I will inspect the first issue in staging now.",
            session_id="sess-seq",
        )
        provider.sync_turn(
            "Inspect the second issue in staging.",
            "I will inspect the second issue in staging after the first.",
            session_id="sess-seq",
        )

        turn_indexes = [item["metadata"]["turn_index"] for item in stored]
        assert turn_indexes == [1, 1, 2, 2]
        assert [item["metadata"]["role"] for item in stored] == ["user", "assistant", "user", "assistant"]

    def test_on_session_end_joins_pending_sync_before_summary_logic(self):
        from plugins.memory.letta import LettaConfig

        class DummyThread:
            def __init__(self):
                self.join_calls = []

            def is_alive(self):
                return True

            def join(self, timeout=None):
                self.join_calls.append(timeout)

        provider = self._provider()
        provider._config = LettaConfig(base_url="https://letta.test", auto_session_summary=False)
        provider._sync_thread = DummyThread()

        provider.on_session_end([{"role": "user", "content": "hello"}])

        assert provider._sync_thread.join_calls == [10.0]
