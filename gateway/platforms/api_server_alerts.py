"""
Alert dispatch endpoint for API server.

Provides POST /api/alerts endpoint for external services (like CentraCast runtime)
to dispatch maintenance alerts through the Hermes gateway to configured channels.

Authentication: HMAC-SHA256 signature in X-Alert-Signature header.
"""

import hashlib
import hmac
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def verify_alert_signature(body: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC-SHA256 signature for alert payload.
    
    Args:
        body: Raw request body bytes
        signature: Signature from X-Alert-Signature header
        secret: Shared secret from HERMES_ALERT_SECRET env var
    
    Returns:
        True if signature is valid
    """
    if not secret:
        # No secret configured - allow all (local-only use)
        return True
    
    expected = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Timing-safe comparison
    return hmac.compare_digest(expected, signature)


async def handle_alert_dispatch(request, adapter) -> Any:
    """
    POST /api/alerts - Dispatch maintenance alerts to configured channels.
    
    Request body (JSON):
    {
        "alert_type": "maintenance_failure",
        "severity": "error",
        "title": "Build failed for release xyz",
        "message": "Full error details...",
        "metadata": {
            "release_id": "123",
            "asset_id": "456",
            ...
        }
    }
    
    Response:
    {
        "success": true,
        "dispatched_to": ["telegram:123456", "discord:789"],
        "message_ids": {...}
    }
    """
    from aiohttp import web
    
    # Read raw body for signature verification
    try:
        body_bytes = await request.read()
        body = json.loads(body_bytes.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return web.json_response(
            {"error": {"message": f"Invalid JSON: {e}", "type": "invalid_request"}},
            status=400
        )
    
    # Verify HMAC signature
    signature = request.headers.get('X-Alert-Signature', '').strip()
    secret = os.getenv('HERMES_ALERT_SECRET', '')

    if not verify_alert_signature(body_bytes, signature, secret):
        logger.warning("Alert dispatch rejected: invalid signature")
        return web.json_response(
            {"error": {"message": "Invalid signature", "type": "authentication_error"}},
            status=401
        )
    
    # Extract alert fields
    alert_type = body.get('alert_type', 'unknown')
    severity = body.get('severity', 'info')
    title = body.get('title', 'Alert')
    message = body.get('message', '')
    metadata = body.get('metadata', {})
    
    # Build formatted alert message
    severity_emoji = {
        'critical': '🔴',
        'error': '⚠️',
        'warning': '⚠️',
        'info': 'ℹ️',
    }.get(severity, '📢')
    
    alert_text = f"{severity_emoji} **{title}**\n\n{message}"
    
    if metadata:
        alert_text += "\n\n**Metadata:**\n"
        for key, value in metadata.items():
            alert_text += f"- {key}: {value}\n"
    
    # Resolve delivery targets from config
    # Default: send to all configured home channels
    from gateway.delivery import DeliveryRouter, DeliveryTarget
    from gateway.config import Platform
    
    # Get gateway config and adapters from the app
    gateway_runner = request.app.get('gateway_runner')
    if not gateway_runner:
        logger.error("Alert dispatch failed: gateway_runner not available")
        return web.json_response(
            {"error": {"message": "Gateway not available", "type": "server_error"}},
            status=500
        )
    
    # Build delivery targets from configured home channels
    targets = []
    for platform in gateway_runner.config.get_connected_platforms():
        home = gateway_runner.config.get_home_channel(platform)
        if home:
            targets.append(DeliveryTarget(
                platform=platform,
                chat_id=home.chat_id
            ))
    
    if not targets:
        logger.warning("Alert dispatch: no home channels configured")
        return web.json_response(
            {"error": {"message": "No delivery targets configured", "type": "configuration_error"}},
            status=500
        )
    
    # Dispatch to all targets
    router = gateway_runner.delivery_router
    router.adapters = gateway_runner.adapters  # Ensure adapters are available
    
    try:
        results = await router.deliver(
            content=alert_text,
            targets=targets,
            metadata={
                'alert_type': alert_type,
                'severity': severity,
                'source': 'api_alerts'
            }
        )
    except Exception as e:
        logger.error("Alert dispatch failed: %s", e, exc_info=True)
        return web.json_response(
            {"error": {"message": f"Dispatch failed: {e}", "type": "server_error"}},
            status=500
        )
    
    # Build response
    dispatched_to = []
    message_ids = {}
    failed = []
    
    for target_str, result in results.items():
        if result.get('success'):
            dispatched_to.append(target_str)
            if 'result' in result and isinstance(result['result'], dict):
                msg_id = result['result'].get('message_id')
                if msg_id:
                    message_ids[target_str] = msg_id
        else:
            failed.append({
                'target': target_str,
                'error': result.get('error', 'Unknown error')
            })
    
    response_data = {
        'success': len(dispatched_to) > 0,
        'dispatched_to': dispatched_to,
        'message_ids': message_ids
    }
    
    if failed:
        response_data['failed'] = failed
    
    logger.info("Alert dispatched to %d targets: %s", len(dispatched_to), dispatched_to)
    
    return web.json_response(response_data)
