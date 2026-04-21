import threading

import run_agent


class _ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, **_):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


def test_spawn_background_review_uses_ephemeral_child_and_shuts_down_memory(monkeypatch):
    original_agent_cls = run_agent.AIAgent
    child_inits = []
    child_calls = []

    class FakeReviewAgent:
        def __init__(self, *args, **kwargs):
            child_inits.append(kwargs.copy())
            self._session_messages = []

        def run_conversation(self, user_message: str, conversation_history=None):
            child_calls.append(("run", user_message, conversation_history))
            self._session_messages = []
            return {"final_response": "ok"}

        def shutdown_memory_provider(self, messages=None):
            child_calls.append(("shutdown", messages))

        def close(self):
            child_calls.append(("close", None))

    monkeypatch.setattr(run_agent, "AIAgent", FakeReviewAgent)
    monkeypatch.setattr(threading, "Thread", _ImmediateThread)

    parent = object.__new__(original_agent_cls)
    parent.model = "test/model"
    parent.platform = "cli"
    parent.provider = "test-provider"
    parent.skip_memory = True
    parent.skip_context_files = True
    parent._memory_store = object()
    parent._memory_enabled = True
    parent._user_profile_enabled = True
    parent.background_review_callback = None
    parent._safe_print = lambda *args, **kwargs: None
    parent._COMBINED_REVIEW_PROMPT = original_agent_cls._COMBINED_REVIEW_PROMPT
    parent._MEMORY_REVIEW_PROMPT = original_agent_cls._MEMORY_REVIEW_PROMPT
    parent._SKILL_REVIEW_PROMPT = original_agent_cls._SKILL_REVIEW_PROMPT

    original_agent_cls._spawn_background_review(
        parent,
        messages_snapshot=[{"role": "assistant", "content": "done"}],
        review_memory=True,
        review_skills=False,
    )

    assert len(child_inits) == 1
    child_kwargs = child_inits[0]
    assert child_kwargs["skip_memory"] is True
    assert child_kwargs["skip_context_files"] is True
    assert child_kwargs["persist_session"] is False

    assert any(call[0] == "shutdown" for call in child_calls)
    assert child_calls[-1][0] == "close"
