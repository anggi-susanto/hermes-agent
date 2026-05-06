"""Regression tests for the Discord /model picker.

Uses the shared discord mock from tests/gateway/conftest.py (installed
at collection time via _ensure_discord_mock()). Previously this file
installed its own mock at module-import time and clobbered sys.modules,
breaking other gateway tests under pytest-xdist.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.platforms.discord import ModelPickerView
import gateway.platforms.discord as discord_platform
from tests.gateway.conftest import _ensure_discord_mock


@pytest.fixture(autouse=True)
def _sync_comprehensive_discord_mock():
    """ModelPickerView needs the full shared discord.ui mock.

    Some legacy Discord test modules still install smaller per-file mocks at
    collection time. Under xdist loadfile ordering those can overwrite the
    module global used by gateway.platforms.discord before this test runs.
    """
    _ensure_discord_mock()
    discord_mod = __import__("discord")
    # Some legacy per-file mocks leave an incomplete discord.ui namespace in
    # sys.modules. If so, explicitly graft the shared conftest mock classes in
    # place by temporarily removing the module and re-running the installer.
    if not hasattr(getattr(discord_mod, "ui", None), "Select"):
        import sys

        for name in ("discord", "discord.ext", "discord.ext.commands"):
            sys.modules.pop(name, None)
        _ensure_discord_mock()
        discord_mod = __import__("discord")
    # The platform module's global may have been rebound to an older per-file
    # mock object during collection. Mutating it in-place is safer than only
    # rebinding: ModelPickerView methods resolve the module global at runtime,
    # while other already-imported helpers may still hold the old object.
    class _TestEmbed:
        def __init__(self, *, title=None, description=None, color=None, **_):
            self.title = title
            self.description = description
            self.color = color

    target = discord_platform.discord
    source_ui = getattr(discord_mod, "ui", None)
    for attr in ("View", "Select", "Button", "button"):
        if source_ui is not None and hasattr(source_ui, attr):
            setattr(target.ui, attr, getattr(source_ui, attr))
    for attr in ("SelectOption", "ButtonStyle", "Color", "Interaction"):
        if hasattr(discord_mod, attr):
            setattr(target, attr, getattr(discord_mod, attr))
    target.Embed = _TestEmbed
    discord_platform.discord = target


@pytest.mark.asyncio
async def test_model_picker_clears_controls_before_running_switch_callback():
    events: list[object] = []

    async def on_model_selected(chat_id: str, model_id: str, provider_slug: str) -> str:
        events.append(("switch", chat_id, model_id, provider_slug))
        return "Model switched"

    async def edit_message(**kwargs):
        events.append(
            (
                "initial-edit",
                kwargs["embed"].title,
                kwargs["embed"].description,
                kwargs["view"],
            )
        )

    async def edit_original_response(**kwargs):
        events.append((
            "final-edit",
            kwargs["embed"].title,
            kwargs["embed"].description,
            kwargs["view"],
        ))

    view = ModelPickerView(
        providers=[
            {
                "slug": "copilot",
                "name": "GitHub Copilot",
                "models": ["gpt-5.4"],
                "total_models": 1,
                "is_current": True,
            }
        ],
        current_model="gpt-5-mini",
        current_provider="copilot",
        session_key="session-1",
        on_model_selected=on_model_selected,
        allowed_user_ids=set(),
    )
    view._selected_provider = "copilot"

    interaction = SimpleNamespace(
        user=SimpleNamespace(id=123),
        channel_id=456,
        data={"values": ["gpt-5.4"]},
        response=SimpleNamespace(
            defer=AsyncMock(),
            send_message=AsyncMock(),
            edit_message=AsyncMock(side_effect=edit_message),
        ),
        edit_original_response=AsyncMock(side_effect=edit_original_response),
    )

    if isinstance(discord_platform.discord.Embed, MagicMock):
        raise AssertionError(f"discord.Embed mock not normalized: {discord_platform.discord!r}")
    # The full suite can leave a mutated Discord module global on this class's
    # defining module. Patch the global for the exact callback invocation so
    # the test is isolated from collection-order contamination.
    with patch.dict(view._on_model_selected.__globals__, {"discord": discord_platform.discord}):
        await view._on_model_selected(interaction)

    assert events == [
        ("initial-edit", "⚙ Switching Model", "Switching to `gpt-5.4`...", None),
        ("switch", "456", "gpt-5.4", "copilot"),
        ("final-edit", "⚙ Model Switched", "Model switched", None),
    ]
    interaction.response.edit_message.assert_awaited_once()
    interaction.response.defer.assert_not_called()
    interaction.edit_original_response.assert_awaited_once()
