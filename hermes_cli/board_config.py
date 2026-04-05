from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from hermes_cli.board_auth import BOARD_PROVIDER_REGISTRY
from hermes_cli.config import load_config



def get_board_section(config: Optional[dict] = None) -> dict:
    source = config if config is not None else load_config()
    board = source.get("board") or {}
    return board if isinstance(board, dict) else {}



def get_default_board_provider_name(config: Optional[dict] = None) -> Optional[str]:
    board = get_board_section(config)
    default_name = board.get("default_provider")
    return default_name if isinstance(default_name, str) and default_name else None



def _registry_defaults(provider_id: str) -> Dict[str, Any]:
    provider = BOARD_PROVIDER_REGISTRY[provider_id]
    return {
        "provider": provider.id,
        "provider_id": provider.id,
        "label": provider.name,
        "auth_type": provider.auth_type,
        "api_base_url": provider.api_base_url,
        "web_base_url": provider.web_base_url,
        "api_key_env_vars": list(provider.api_key_env_vars),
        "supports_user_session": provider.supports_user_session,
        "supports_agent_keys": provider.supports_agent_keys,
    }



def get_board_provider_config(name: str, config: Optional[dict] = None) -> Optional[dict]:
    board = get_board_section(config)
    providers = board.get("providers") or {}
    if not isinstance(providers, dict):
        return None

    raw = providers.get(name)
    if not isinstance(raw, dict):
        return None

    provider_id = raw.get("provider")
    if provider_id not in BOARD_PROVIDER_REGISTRY:
        return None

    merged = _registry_defaults(provider_id)
    merged.update(deepcopy(raw))
    merged["name"] = name
    merged["provider"] = provider_id
    merged["provider_id"] = provider_id
    return merged



def list_board_provider_configs(config: Optional[dict] = None) -> list[dict]:
    board = get_board_section(config)
    providers = board.get("providers") or {}
    if not isinstance(providers, dict):
        return []

    resolved = []
    for name in providers:
        provider_config = get_board_provider_config(name, config)
        if provider_config is not None:
            resolved.append(provider_config)
    return resolved
