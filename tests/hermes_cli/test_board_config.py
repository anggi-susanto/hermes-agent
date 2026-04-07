from hermes_cli.board_config import (
    get_board_section,
    get_default_board_provider_name,
    get_board_provider_config,
    list_board_provider_configs,
)


def test_get_board_section_defaults_to_empty_dict():
    assert get_board_section({}) == {}



def test_get_default_board_provider_name_from_config():
    config = {
        "board": {
            "default_provider": "paperclip-prod",
        }
    }

    assert get_default_board_provider_name(config) == "paperclip-prod"



def test_get_board_provider_config_merges_registry_defaults_with_overrides():
    config = {
        "board": {
            "providers": {
                "paperclip-prod": {
                    "provider": "paperclip",
                    "api_base_url": "https://paperclip.ing/api",
                    "company_id": "comp_123",
                    "sync": {"mode": "manual"},
                }
            }
        }
    }

    provider = get_board_provider_config("paperclip-prod", config)

    assert provider["name"] == "paperclip-prod"
    assert provider["provider"] == "paperclip"
    assert provider["provider_id"] == "paperclip"
    assert provider["api_base_url"] == "https://paperclip.ing/api"
    assert provider["web_base_url"] == "https://paperclip.ing"
    assert provider["company_id"] == "comp_123"
    assert provider["sync"] == {"mode": "manual"}
    assert provider["api_key_env_vars"] == ["PAPERCLIP_API_KEY"]
    assert provider["supports_agent_keys"] is True



def test_list_board_provider_configs_returns_named_entries():
    config = {
        "board": {
            "providers": {
                "paperclip-prod": {"provider": "paperclip", "company_id": "comp_prod"},
                "paperclip-staging": {"provider": "paperclip", "company_id": "comp_stg"},
            }
        }
    }

    providers = list_board_provider_configs(config)

    assert [provider["name"] for provider in providers] == ["paperclip-prod", "paperclip-staging"]
    assert providers[0]["company_id"] == "comp_prod"
    assert providers[1]["company_id"] == "comp_stg"



def test_get_board_provider_config_returns_none_for_unknown_name():
    config = {"board": {"providers": {}}}

    assert get_board_provider_config("missing", config) is None
