from __future__ import annotations

from hermes_cli.board_auth import BOARD_PROVIDER_REGISTRY
from hermes_cli.plugins import PluginContext, PluginManager, PluginManifest


def test_plugin_context_register_board_provider_adds_metadata():
    manager = PluginManager()
    manifest = PluginManifest(name="acme-board", key="boards/acme-board", kind="board-provider")
    ctx = PluginContext(manifest, manager)

    ctx.register_board_provider(
        id="acme-board",
        name="Acme Board",
        auth_type="api_key",
        api_base_url="https://acme.invalid/api",
        web_base_url="https://acme.invalid",
        api_key_env_vars=("ACME_BOARD_API_KEY",),
    )

    provider = BOARD_PROVIDER_REGISTRY["acme-board"]

    assert provider.id == "acme-board"
    assert provider.name == "Acme Board"
    assert provider.api_base_url == "https://acme.invalid/api"
    assert provider.web_base_url == "https://acme.invalid"
    assert provider.api_key_env_vars == ("ACME_BOARD_API_KEY",)
