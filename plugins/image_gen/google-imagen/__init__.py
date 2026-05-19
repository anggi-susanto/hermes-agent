"""Google Imagen image generation backend.

Uses the Google AI Studio Gemini API key (``GOOGLE_API_KEY`` or
``GEMINI_API_KEY``) to call Imagen's ``predict`` endpoint directly. The
provider intentionally uses ``requests`` instead of the Google SDK so the
image_gen plugin adds no eager dependency.

Selection precedence (first hit wins):
1. ``GOOGLE_IMAGEN_MODEL`` env var
2. ``image_gen.google_imagen.model`` in ``config.yaml``
3. ``image_gen.model`` in ``config.yaml`` (when it matches an Imagen model)
4. :data:`DEFAULT_MODEL`
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)

API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "imagen-4.0-generate-001"

_MODELS: Dict[str, Dict[str, Any]] = {
    "imagen-4.0-generate-001": {
        "display": "Imagen 4",
        "speed": "~10-30s",
        "strengths": "Google Imagen 4 via AI Studio; high quality text-to-image",
        "price": "varies",
    },
    "imagen-4.0-fast-generate-001": {
        "display": "Imagen 4 Fast",
        "speed": "~5-15s",
        "strengths": "Lower-latency Imagen 4 generation",
        "price": "varies",
    },
    "imagen-4.0-ultra-generate-001": {
        "display": "Imagen 4 Ultra",
        "speed": "~30-60s",
        "strengths": "Highest-quality Imagen 4 tier",
        "price": "varies",
    },
    "imagen-3.0-generate-002": {
        "display": "Imagen 3",
        "speed": "~10-30s",
        "strengths": "Stable Imagen 3 generation",
        "price": "varies",
    },
}

# Google Imagen accepts symbolic aspect ratio strings on the predict endpoint.
_ASPECT_RATIOS = {
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "9:16",
}

_SAMPLE_IMAGE_SIZES = {"1K", "2K"}
DEFAULT_SAMPLE_IMAGE_SIZE = "1K"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _get_google_api_key() -> str:
    """Return the Google AI Studio key from env or ``~/.hermes/.env``."""
    try:
        from hermes_cli.config import get_env_value

        value = get_env_value("GOOGLE_API_KEY") or get_env_value("GEMINI_API_KEY")
    except Exception:
        value = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    return (value or "").strip()


def _load_image_gen_config() -> Dict[str, Any]:
    """Read ``image_gen`` from config.yaml (returns {} on any failure)."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen config: %s", exc)
        return {}


def _resolve_model() -> Tuple[str, Dict[str, Any]]:
    """Decide which Imagen model to use and return ``(model_id, meta)``."""
    env_override = os.environ.get("GOOGLE_IMAGEN_MODEL")
    if env_override and env_override in _MODELS:
        return env_override, _MODELS[env_override]

    cfg = _load_image_gen_config()
    google_cfg = cfg.get("google_imagen") if isinstance(cfg.get("google_imagen"), dict) else {}
    candidate: Optional[str] = None
    if isinstance(google_cfg, dict):
        value = google_cfg.get("model")
        if isinstance(value, str) and value in _MODELS:
            candidate = value
    if candidate is None:
        top = cfg.get("model")
        if isinstance(top, str) and top in _MODELS:
            candidate = top

    if candidate is not None:
        return candidate, _MODELS[candidate]

    return DEFAULT_MODEL, _MODELS[DEFAULT_MODEL]


def _resolve_sample_image_size() -> str:
    """Return configured Imagen sample image size, defaulting to 1K."""
    cfg = _load_image_gen_config()
    google_cfg = cfg.get("google_imagen") if isinstance(cfg.get("google_imagen"), dict) else {}
    value = google_cfg.get("sample_image_size") if isinstance(google_cfg, dict) else None
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in _SAMPLE_IMAGE_SIZES:
            return normalized
    return DEFAULT_SAMPLE_IMAGE_SIZE


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _first_prediction_image_b64(result: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
    """Extract the first base64 image from known Imagen predict shapes."""
    predictions = result.get("predictions")
    if not isinstance(predictions, list) or not predictions:
        return None, {}

    first = predictions[0]
    if not isinstance(first, dict):
        return None, {}

    # Imagen currently returns predictions[0].bytesBase64Encoded. Keep a few
    # aliases so minor API casing changes fail gracefully instead of looking
    # like an empty response.
    for key in ("bytesBase64Encoded", "bytes_base64_encoded", "b64_json", "base64"):
        value = first.get(key)
        if isinstance(value, str) and value.strip():
            return value, first

    image_obj = first.get("image")
    if isinstance(image_obj, dict):
        for key in ("bytesBase64Encoded", "bytes_base64_encoded", "b64_json", "base64"):
            value = image_obj.get(key)
            if isinstance(value, str) and value.strip():
                return value, first

    return None, first


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class GoogleImagenImageGenProvider(ImageGenProvider):
    """Google Imagen backend using Google AI Studio API keys."""

    @property
    def name(self) -> str:
        return "google-imagen"

    @property
    def display_name(self) -> str:
        return "Google Imagen"

    def is_available(self) -> bool:
        return bool(_get_google_api_key())

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta["display"],
                "speed": meta["speed"],
                "strengths": meta["strengths"],
                "price": meta.get("price", "varies"),
            }
            for model_id, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Google Imagen",
            "badge": "paid",
            "tag": "Imagen 4/3 via Google AI Studio API key",
            "env_vars": [
                {
                    "key": "GOOGLE_API_KEY",
                    "prompt": "Google AI Studio API key",
                    "url": "https://aistudio.google.com/app/apikey",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="google-imagen",
                aspect_ratio=aspect,
            )

        api_key = _get_google_api_key()
        if not api_key:
            return error_response(
                error=(
                    "GOOGLE_API_KEY or GEMINI_API_KEY not set. Get one at "
                    "https://aistudio.google.com/app/apikey, then run `hermes tools` "
                    "→ Image Generation → Google Imagen to configure."
                ),
                error_type="auth_required",
                provider="google-imagen",
                aspect_ratio=aspect,
                prompt=prompt,
            )

        model_id, _meta = _resolve_model()
        sample_image_size = _resolve_sample_image_size()
        google_aspect = _ASPECT_RATIOS.get(aspect, "16:9")

        payload: Dict[str, Any] = {
            "instances": [
                {
                    "prompt": prompt,
                }
            ],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": google_aspect,
                "sampleImageSize": sample_image_size,
            },
        }

        base_url = (os.getenv("GOOGLE_IMAGEN_BASE_URL") or API_BASE_URL).strip().rstrip("/")
        url = f"{base_url}/models/{model_id}:predict"
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(
                url,
                headers=headers,
                params={"key": api_key},
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else 0
            try:
                body = response.json() if response is not None else {}
                err_msg = body.get("error", {}).get("message") or str(body)[:300]
            except Exception:
                err_msg = response.text[:300] if response is not None else str(exc)
            logger.error("Google Imagen generation failed (%d): %s", status, err_msg)
            return error_response(
                error=f"Google Imagen generation failed ({status}): {err_msg}",
                error_type="api_error",
                provider="google-imagen",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.Timeout:
            return error_response(
                error="Google Imagen generation timed out (120s)",
                error_type="timeout",
                provider="google-imagen",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.ConnectionError as exc:
            return error_response(
                error=f"Google Imagen connection error: {exc}",
                error_type="connection_error",
                provider="google-imagen",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            result = response.json()
        except Exception as exc:
            return error_response(
                error=f"Google Imagen returned invalid JSON: {exc}",
                error_type="invalid_response",
                provider="google-imagen",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        b64, first_prediction = _first_prediction_image_b64(result)
        if not b64:
            return error_response(
                error="Google Imagen returned no base64 image data",
                error_type="empty_response",
                provider="google-imagen",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            saved_path = save_b64_image(b64, prefix=f"google_imagen_{model_id}")
        except Exception as exc:
            return error_response(
                error=f"Could not save image to cache: {exc}",
                error_type="io_error",
                provider="google-imagen",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        extra: Dict[str, Any] = {
            "google_aspect_ratio": google_aspect,
            "sample_image_size": sample_image_size,
        }
        mime_type = first_prediction.get("mimeType") or first_prediction.get("mime_type")
        if isinstance(mime_type, str) and mime_type:
            extra["mime_type"] = mime_type

        return success_response(
            image=str(saved_path),
            model=model_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="google-imagen",
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx: Any) -> None:
    """Register this provider with the image gen registry."""
    ctx.register_image_gen_provider(GoogleImagenImageGenProvider())
