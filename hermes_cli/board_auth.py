from __future__ import annotations

import json
import os
import stat
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_cli.config import ensure_hermes_home
from hermes_constants import get_hermes_home
from utils import atomic_json_write

try:
    import fcntl
except Exception:
    fcntl = None

try:
    import msvcrt
except Exception:
    msvcrt = None


BOARD_AUTH_STORE_VERSION = 1
BOARD_AUTH_LOCK_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class BoardProviderConfig:
    id: str
    name: str
    auth_type: str
    api_base_url: str = ""
    web_base_url: str = ""
    api_key_env_vars: tuple[str, ...] = ()
    supports_user_session: bool = False
    supports_agent_keys: bool = True


BOARD_PROVIDER_REGISTRY: Dict[str, BoardProviderConfig] = {
    "paperclip": BoardProviderConfig(
        id="paperclip",
        name="Paperclip",
        auth_type="api_key",
        api_base_url="https://paperclip.ing/api",
        web_base_url="https://paperclip.ing",
        api_key_env_vars=("PAPERCLIP_API_KEY",),
        supports_user_session=False,
        supports_agent_keys=True,
    )
}


_board_lock_holder = threading.local()


def _board_auth_file_path() -> Path:
    return get_hermes_home() / "board_auth.json"


def _board_auth_lock_path() -> Path:
    return _board_auth_file_path().with_suffix(".lock")


@contextmanager
def _board_store_lock(timeout_seconds: float = BOARD_AUTH_LOCK_TIMEOUT_SECONDS):
    if getattr(_board_lock_holder, "depth", 0) > 0:
        _board_lock_holder.depth += 1
        try:
            yield
        finally:
            _board_lock_holder.depth -= 1
        return

    lock_path = _board_auth_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if fcntl is None and msvcrt is None:
        _board_lock_holder.depth = 1
        try:
            yield
        finally:
            _board_lock_holder.depth = 0
        return

    if msvcrt and (not lock_path.exists() or lock_path.stat().st_size == 0):
        lock_path.write_text(" ", encoding="utf-8")

    with lock_path.open("r+" if msvcrt else "a+") as lock_file:
        deadline = time.time() + max(1.0, timeout_seconds)
        while True:
            try:
                if fcntl:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except (BlockingIOError, OSError, PermissionError):
                if time.time() >= deadline:
                    raise TimeoutError("Timed out waiting for board auth store lock")
                time.sleep(0.05)

        _board_lock_holder.depth = 1
        try:
            yield
        finally:
            _board_lock_holder.depth = 0
            if fcntl:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            elif msvcrt:
                try:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                except (OSError, IOError):
                    pass


def _default_board_auth_store() -> Dict[str, Any]:
    return {"version": BOARD_AUTH_STORE_VERSION, "providers": {}}


def load_board_auth_store(auth_file: Optional[Path] = None) -> Dict[str, Any]:
    auth_file = auth_file or _board_auth_file_path()
    if not auth_file.exists():
        return _default_board_auth_store()

    try:
        raw = json.loads(auth_file.read_text(encoding="utf-8"))
    except Exception:
        return _default_board_auth_store()

    if not isinstance(raw, dict) or not isinstance(raw.get("providers"), dict):
        return _default_board_auth_store()

    raw.setdefault("version", BOARD_AUTH_STORE_VERSION)
    return raw


def _secure_file(path: Path) -> None:
    try:
        if path.exists():
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def save_board_auth_store(auth_store: Dict[str, Any]) -> Path:
    ensure_hermes_home()
    auth_file = _board_auth_file_path()
    payload = dict(auth_store)
    payload["version"] = BOARD_AUTH_STORE_VERSION
    with _board_store_lock():
        atomic_json_write(auth_file, payload)
        _secure_file(auth_file)
    return auth_file


def set_active_board_provider(name: str) -> None:
    with _board_store_lock():
        store = load_board_auth_store()
        store["active_provider"] = name
        save_board_auth_store(store)


def deactivate_board_provider() -> None:
    with _board_store_lock():
        store = load_board_auth_store()
        store.pop("active_provider", None)
        save_board_auth_store(store)


def save_board_provider_credentials(name: str, provider: str, auth_payload: Dict[str, Any]) -> None:
    with _board_store_lock():
        store = load_board_auth_store()
        providers = dict(store.get("providers") or {})
        providers[name] = {
            "provider": provider,
            "auth": dict(auth_payload),
        }
        store["providers"] = providers
        store["active_provider"] = name
        save_board_auth_store(store)


def get_active_board_provider() -> Optional[str]:
    return load_board_auth_store().get("active_provider")


def get_board_auth_status(name_or_provider: Optional[str] = None) -> Dict[str, Any]:
    store = load_board_auth_store()
    target_name = name_or_provider or store.get("active_provider")
    provider_state = None

    if target_name:
        provider_state = (store.get("providers") or {}).get(target_name)

    provider_id = None
    auth_type = None
    has_api_key = False
    authenticated = False

    if isinstance(provider_state, dict):
        provider_id = provider_state.get("provider")
        provider_config = BOARD_PROVIDER_REGISTRY.get(provider_id)
        auth_type = provider_config.auth_type if provider_config else None
        auth_payload = provider_state.get("auth") or {}
        has_api_key = bool(auth_payload.get("api_key"))
        authenticated = has_api_key

    return {
        "provider_name": target_name,
        "provider_id": provider_id,
        "auth_type": auth_type,
        "authenticated": authenticated,
        "has_api_key": has_api_key,
    }


def list_board_provider_metadata() -> list[dict[str, Any]]:
    return [asdict(provider) for provider in BOARD_PROVIDER_REGISTRY.values()]
