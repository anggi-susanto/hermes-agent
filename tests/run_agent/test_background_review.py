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
    parent.status_callback = None
    parent._safe_print = lambda *args, **kwargs: None
    parent._cached_system_prompt = "test-cached-system-prompt"
    import datetime as _dt
    parent.session_start = _dt.datetime(2026, 1, 1, 12, 0, 0)
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
    assert "persist_session" not in child_kwargs

    assert any(call[0] == "shutdown" for call in child_calls)
    assert child_calls[-1][0] == "close"
"""Regression tests for background review agent cleanup."""

import run_agent as run_agent_module
from run_agent import AIAgent


def _bare_agent() -> AIAgent:
    agent = object.__new__(AIAgent)
    agent.model = "fake-model"
    agent.platform = "telegram"
    agent.provider = "openai"
    agent.base_url = ""
    agent.api_key = ""
    agent.api_mode = ""
    agent.session_id = "test-session"
    agent._parent_session_id = ""
    agent._credential_pool = None
    agent._memory_store = object()
    agent._memory_enabled = True
    agent._user_profile_enabled = False
    agent._cached_system_prompt = "test-cached-system-prompt"
    import datetime as _dt
    agent.session_start = _dt.datetime(2026, 1, 1, 12, 0, 0)
    agent._MEMORY_REVIEW_PROMPT = "review memory"
    agent._SKILL_REVIEW_PROMPT = "review skills"
    agent._COMBINED_REVIEW_PROMPT = "review both"
    agent.background_review_callback = None
    agent.status_callback = None
    agent._safe_print = lambda *_args, **_kwargs: None
    return agent


class ImmediateThread:
    def __init__(self, *, target, daemon=None, name=None):
        self._target = target

    def start(self):
        self._target()


def test_background_review_shuts_down_memory_provider_before_close(monkeypatch):
    events = []

    class FakeReviewAgent:
        def __init__(self, **kwargs):
            events.append(("init", kwargs))
            self._session_messages = []

        def run_conversation(self, **kwargs):
            events.append(("run_conversation", kwargs))

        def shutdown_memory_provider(self):
            events.append(("shutdown_memory_provider", None))

        def close(self):
            events.append(("close", None))

    monkeypatch.setattr(run_agent_module, "AIAgent", FakeReviewAgent)
    monkeypatch.setattr(run_agent_module.threading, "Thread", ImmediateThread)

    agent = _bare_agent()

    AIAgent._spawn_background_review(
        agent,
        messages_snapshot=[{"role": "user", "content": "hello"}],
        review_memory=True,
    )

    assert [name for name, _payload in events] == [
        "init",
        "run_conversation",
        "shutdown_memory_provider",
        "close",
    ]


def test_background_review_installs_auto_deny_approval_callback(monkeypatch):
    """Regression guard for #15216.

    The background review thread must install a non-interactive approval
    callback. If it doesn't, any dangerous-command guard the review agent
    trips falls back to input() on a daemon thread, which deadlocks against
    the parent's prompt_toolkit TUI.
    """
    import tools.terminal_tool as tt

    observed: dict = {"during_run": "<unread>", "after_finally": "<unread>"}

    class FakeReviewAgent:
        def __init__(self, **kwargs):
            self._session_messages = []

        def run_conversation(self, **kwargs):
            # Capture what the callback looks like mid-run. It must be
            # a callable (the auto-deny) -- not None.
            observed["during_run"] = tt._get_approval_callback()

        def shutdown_memory_provider(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(run_agent_module, "AIAgent", FakeReviewAgent)
    monkeypatch.setattr(run_agent_module.threading, "Thread", ImmediateThread)

    # Start from a clean slot.
    tt.set_approval_callback(None)
    agent = _bare_agent()

    AIAgent._spawn_background_review(
        agent,
        messages_snapshot=[{"role": "user", "content": "hello"}],
        review_memory=True,
    )

    observed["after_finally"] = tt._get_approval_callback()

    assert callable(observed["during_run"]), (
        "Background review did not install an approval callback on its "
        "worker thread; dangerous-command prompts will deadlock against "
        "the parent TUI (#15216)."
    )
    # The installed callback must deny (it's a safety gate, not a prompt).
    assert observed["during_run"]("rm -rf /", "test") == "deny"

    assert observed["after_finally"] is None, (
        "Background review leaked its approval callback into the worker "
        "thread's TLS slot; a recycled thread-id could reuse it."
    )


def test_background_review_summary_is_attributed_to_self_improvement_loop(monkeypatch):
    """The CLI/gateway emission must identify the self-improvement loop.

    Users who miss the line in their terminal have no way to tell that the
    background review was what modified their skill/memory stores. The
    summary prefix ``💾 Self-improvement review: …`` makes the origin
    explicit so both the CLI and gateway deliveries are unambiguous.
    """
    import json

    captured_prints: list = []
    captured_bg_callback: list = []

    class FakeReviewAgent:
        def __init__(self, **kwargs):
            # Simulate a review that successfully updated memory so
            # _summarize_background_review_actions returns a real action.
            self._session_messages = [
                {
                    "role": "tool",
                    "tool_call_id": "call_bg",
                    "content": json.dumps(
                        {"success": True, "message": "Entry added", "target": "memory"}
                    ),
                }
            ]

        def run_conversation(self, **kwargs):
            pass

        def shutdown_memory_provider(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(run_agent_module, "AIAgent", FakeReviewAgent)
    monkeypatch.setattr(run_agent_module.threading, "Thread", ImmediateThread)

    agent = _bare_agent()
    agent._safe_print = lambda *a, **kw: captured_prints.append(" ".join(str(x) for x in a))
    agent.background_review_callback = lambda msg: captured_bg_callback.append(msg)

    AIAgent._spawn_background_review(
        agent,
        messages_snapshot=[{"role": "user", "content": "hi"}],
        review_memory=True,
    )

    # Exactly one summary should have been emitted, and it must identify
    # the self-improvement review explicitly.
    assert len(captured_prints) == 1, captured_prints
    printed = captured_prints[0]
    assert "Self-improvement review" in printed, printed
    assert "Memory updated" in printed, printed

    # Gateway path gets the same prefix.
    assert len(captured_bg_callback) == 1
    assert captured_bg_callback[0].startswith("💾 Self-improvement review:"), (
        captured_bg_callback[0]
    )
