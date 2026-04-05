---
name: hermes-gateway-image-vision-debugging
description: Investigate Telegram/gateway image OCR or vision complaints in Hermes, trace the real photo enrichment path, and diagnose provider/model routing mismatches for auxiliary vision.
tags: [hermes-agent, gateway, telegram, vision, ocr, images, multimodal, debugging]
---

# Hermes Gateway Image / Vision Debugging

Use when:
- user says Telegram image OCR is broken
- photos arrive in Hermes but the assistant says it cannot see them
- you need to determine whether the failure is in Telegram ingestion, gateway enrichment, or auxiliary vision provider routing

## Why this exists

A real failure mode happened where Telegram photos were downloaded and batched correctly, but image analysis still failed at runtime because auxiliary vision was routed to a custom endpoint with an unsupported model slug.

Observed evidence:
- gateway cached the user photo
- gateway flushed the photo batch to the agent
- `vision_analyze_tool` raised `502 unknown provider for model anthropic/claude-opus-4.6`
- logs later showed: `Auxiliary vision: using custom (anthropic/claude-opus-4.6) at https://clip.gunamaya.id/v1/`

So the bug was not "Telegram cannot receive images" and not necessarily "OCR is missing".
It was provider/model mismatch on the auxiliary vision backend.

## Investigation flow

1. Verify the image-enrichment path in `gateway/run.py`.
   Look for:
   - image attachments with MIME `image/*`
   - `MessageType.PHOTO`
   - calls into `_enrich_message_with_vision(...)`

2. Confirm runtime evidence in logs before changing code.
   Search `~/.hermes/logs/gateway.log` for:
   - `Cached user photo`
   - `Flushing photo batch`
   - `Error analyzing image:`
   - `Auxiliary vision: using`
   - `unknown provider for model`

   If you see cached photo + batch flush, transport is working.
   If analysis then fails, the problem is downstream in vision routing/execution.

3. Distinguish the failure layer.

   Case A: no cached photo log
   - Telegram/media ingestion issue

   Case B: cached photo exists, no flush
   - batching or message assembly issue

   Case C: flush happens, `vision_analyze_tool` errors
   - auxiliary vision backend/provider/model issue

   Case D: analysis succeeds but assistant still acts blind
   - context injection / prompt assembly issue

4. Inspect the active model and auxiliary config.
   Important files/values:
   - `~/.hermes/config.yaml`
   - `model.provider`
   - `model.base_url`
   - `model.default`
   - `auxiliary.vision.provider`
   - `auxiliary.vision.model`
   - `auxiliary.vision.base_url`
   - `auxiliary.vision.api_key`

## Critical routing insight

In `agent/auxiliary_client.py`, vision routing is conservative in `auto` mode.
A model override alone does NOT guarantee the intended backend.

Important behavior:
- if `auxiliary.vision.base_url` or `AUXILIARY_VISION_BASE_URL` is set, vision is forced to `custom`
- if only `AUXILIARY_VISION_MODEL` is set while provider stays `auto`, the chosen backend may still come from the auto resolver, not necessarily the custom runtime you expected
- the selected main provider may influence auto ordering, but only when recognized as a known-good vision backend

Therefore, if you want vision to use the active custom proxy, do not set only the model. Set the full auxiliary vision route explicitly.

## Implementation pattern that worked

When the main runtime uses a custom OpenAI-compatible proxy (for example `https://clip.gunamaya.id/v1`), the safest configuration is:

```yaml
auxiliary:
  vision:
    provider: custom
    model: gpt-5.4
    base_url: https://clip.gunamaya.id/v1
    api_key: <same key as the custom provider>
    timeout: 30
```

Equivalent env overrides:
- `AUXILIARY_VISION_PROVIDER=custom`
- `AUXILIARY_VISION_MODEL=gpt-5.4`
- `AUXILIARY_VISION_BASE_URL=https://clip.gunamaya.id/v1`
- `AUXILIARY_VISION_API_KEY=...`

Do NOT rely on this weaker setup:
- provider = `auto`
- model = some custom slug
- hope the resolver chooses the right backend

That can produce mismatches such as routing a request to a custom proxy with a model slug the proxy does not understand.

## What to verify after changing config

1. Send one Telegram photo.
2. Check `gateway.log` for a line like:
   - `Auxiliary vision: using custom (gpt-5.4) at https://clip.gunamaya.id/v1/`
3. Confirm there is no:
   - `unknown provider for model`
   - `502`
4. Confirm the enriched user message now contains image analysis rather than only a generic fallback note.

## Reporting guidance

Use a Red/Yellow/Green style if helpful:
- Green: image transport path works (photo cached, batch flushed)
- Yellow: fallback text exists but is too generic for operators
- Red: auxiliary vision backend rejects the configured model/provider combination

## Pitfalls

### Pitfall 1: successful photo download != successful OCR/vision
`Cached user photo` only proves Telegram transport worked.
It does not prove analysis succeeded.

### Pitfall 2: model-only override is not enough
Setting only `AUXILIARY_VISION_MODEL` can leave backend selection ambiguous.
If you need a specific custom proxy, set provider + base_url + model together.

### Pitfall 3: custom proxy compatibility must be real, not assumed
A custom OpenAI-compatible endpoint may support chat but not multimodal payloads, or may reject certain model slugs.
Even if the main CLI works, verify that image requests pass through.

### Pitfall 4: generic fallbacks hide operator-actionable root cause
If vision fails due to provider mismatch, report that explicitly instead of only saying "I couldn't quite see it".
This user prefers transparent weak-state signaling.

## Recommended next improvement

If you patch code after diagnosis, improve gateway/operator diagnostics so provider mismatch errors become more actionable in logs or fallback context, instead of only a vague image-analysis failure note.
