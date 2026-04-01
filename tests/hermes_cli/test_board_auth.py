from hermes_cli.board_auth import (
    BOARD_PROVIDER_REGISTRY,
    _board_auth_file_path,
    load_board_auth_store,
    save_board_auth_store,
    save_board_provider_credentials,
    set_active_board_provider,
    deactivate_board_provider,
    get_board_auth_status,
)


def test_paperclip_provider_registered():
    provider = BOARD_PROVIDER_REGISTRY["paperclip"]

    assert provider.id == "paperclip"
    assert provider.name == "Paperclip"
    assert provider.auth_type == "api_key"
    assert provider.api_base_url.endswith("/api")
    assert "PAPERCLIP_API_KEY" in provider.api_key_env_vars
    assert provider.supports_agent_keys is True
    assert provider.supports_user_session is False



def test_board_auth_store_is_separate_from_inference_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert _board_auth_file_path() == tmp_path / "board_auth.json"



def test_load_board_auth_store_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    store = load_board_auth_store()

    assert store == {"version": 1, "providers": {}}



def test_save_and_load_board_auth_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    save_board_auth_store(
        {
            "providers": {
                "paperclip-prod": {
                    "provider": "paperclip",
                    "auth": {"api_key": "pc-secret"},
                }
            },
            "active_provider": "paperclip-prod",
        }
    )

    store = load_board_auth_store()

    assert store["version"] == 1
    assert store["active_provider"] == "paperclip-prod"
    assert store["providers"]["paperclip-prod"]["provider"] == "paperclip"
    assert store["providers"]["paperclip-prod"]["auth"]["api_key"] == "pc-secret"
    assert _board_auth_file_path().exists()



def test_save_board_provider_credentials_sets_active_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    save_board_provider_credentials(
        name="paperclip-prod",
        provider="paperclip",
        auth_payload={"api_key": "pc-secret", "company_id": "comp_123"},
    )

    store = load_board_auth_store()

    assert store["active_provider"] == "paperclip-prod"
    assert store["providers"]["paperclip-prod"] == {
        "provider": "paperclip",
        "auth": {"api_key": "pc-secret", "company_id": "comp_123"},
    }



def test_set_and_deactivate_active_board_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    save_board_auth_store(
        {
            "providers": {
                "paperclip-prod": {"provider": "paperclip", "auth": {"api_key": "pc-secret"}}
            }
        }
    )

    set_active_board_provider("paperclip-prod")
    assert load_board_auth_store()["active_provider"] == "paperclip-prod"

    deactivate_board_provider()
    assert load_board_auth_store().get("active_provider") is None



def test_get_board_auth_status_prefers_named_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    save_board_provider_credentials(
        name="paperclip-prod",
        provider="paperclip",
        auth_payload={"api_key": "pc-secret"},
    )

    status = get_board_auth_status("paperclip-prod")

    assert status["authenticated"] is True
    assert status["provider_name"] == "paperclip-prod"
    assert status["provider_id"] == "paperclip"
    assert status["auth_type"] == "api_key"
    assert status["has_api_key"] is True



def test_get_board_auth_status_returns_unauthenticated_for_unknown_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    status = get_board_auth_status("missing")

    assert status["authenticated"] is False
    assert status["provider_name"] == "missing"
    assert status["provider_id"] is None
    assert status["has_api_key"] is False
