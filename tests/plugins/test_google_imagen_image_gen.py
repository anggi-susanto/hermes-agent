"""Tests for the bundled Google Imagen image generation provider."""

from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

import pytest


PLUGIN_PATH = Path(__file__).resolve().parents[2] / "plugins" / "image_gen" / "google-imagen" / "__init__.py"


def _load_plugin_module():
    spec = importlib.util.spec_from_file_location("google_imagen_image_gen_plugin", PLUGIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def google_imagen(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_IMAGEN_MODEL", raising=False)
    return _load_plugin_module()


def test_provider_setup_schema_uses_google_ai_studio_key(google_imagen):
    provider = google_imagen.GoogleImagenImageGenProvider()

    assert provider.name == "google-imagen"
    assert provider.default_model() == "imagen-4.0-generate-001"
    assert provider.is_available() is True

    schema = provider.get_setup_schema()
    assert schema["name"] == "Google Imagen"
    assert schema["env_vars"] == [
        {
            "key": "GOOGLE_API_KEY",
            "prompt": "Google AI Studio API key",
            "url": "https://aistudio.google.com/app/apikey",
        }
    ]


def test_generate_posts_predict_request_and_saves_b64(monkeypatch, google_imagen, tmp_path):
    calls = []
    image_bytes = b"fake-png-bytes"
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "predictions": [
                    {
                        "bytesBase64Encoded": image_b64,
                        "mimeType": "image/png",
                    }
                ]
            }

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(google_imagen.requests, "post", fake_post)

    provider = google_imagen.GoogleImagenImageGenProvider()
    result = provider.generate("a neon turtle", aspect_ratio="portrait")

    assert result["success"] is True
    assert result["provider"] == "google-imagen"
    assert result["model"] == "imagen-4.0-generate-001"
    assert result["aspect_ratio"] == "portrait"
    assert result["google_aspect_ratio"] == "9:16"
    assert result["sample_image_size"] == "1K"
    assert result["mime_type"] == "image/png"

    saved_path = Path(result["image"])
    assert saved_path.is_file()
    assert saved_path.read_bytes() == image_bytes
    assert saved_path.is_relative_to(tmp_path / "cache" / "images")

    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"
    assert kwargs["params"] == {"key": "test-google-key"}
    assert kwargs["json"] == {
        "instances": [{"prompt": "a neon turtle"}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "9:16",
            "sampleImageSize": "1K",
        },
    }
    assert kwargs["timeout"] == 120


def test_generate_accepts_gemini_api_key_alias(monkeypatch, google_imagen):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"predictions": [{"bytesBase64Encoded": base64.b64encode(b"x").decode("ascii")}]} 

    def fake_post(url, **kwargs):
        assert kwargs["params"] == {"key": "test-gemini-key"}
        return FakeResponse()

    monkeypatch.setattr(google_imagen.requests, "post", fake_post)

    result = google_imagen.GoogleImagenImageGenProvider().generate("tiny castle")

    assert result["success"] is True


def test_generate_returns_auth_error_without_google_key(monkeypatch, google_imagen):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = google_imagen.GoogleImagenImageGenProvider().generate("tiny castle")

    assert result["success"] is False
    assert result["error_type"] == "auth_required"
    assert "GOOGLE_API_KEY or GEMINI_API_KEY" in result["error"]


def test_resolve_model_uses_google_imagen_config(monkeypatch, google_imagen, tmp_path):
    import yaml

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "image_gen": {
                    "provider": "google-imagen",
                    "google_imagen": {
                        "model": "imagen-4.0-fast-generate-001",
                        "sample_image_size": "2k",
                    },
                }
            }
        )
    )

    model_id, _meta = google_imagen._resolve_model()

    assert model_id == "imagen-4.0-fast-generate-001"
    assert google_imagen._resolve_sample_image_size() == "2K"
