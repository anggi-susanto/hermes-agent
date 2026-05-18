"""Hermes plugin adapter for RTK command rewriting.

RTK (Rust Token Killer) is an external CLI proxy that rewrites commands like
``git status`` to ``rtk git status`` so the resulting tool output is filtered
and token-compact. This plugin keeps the actual command-selection logic in
RTK's ``rtk rewrite`` subcommand and only bridges Hermes' ``pre_tool_call``
hook to that binary.

The plugin is deliberately fail-open: if RTK is missing, slow, or rejects a
command, Hermes runs the original terminal command unchanged.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

ACCEPTED_REWRITE_RETURN_CODES = {0, 3}
EXPECTED_PASSTHROUGH_RETURN_CODES = {1, 2}
DEFAULT_TIMEOUT_SECONDS = 2.0

_rtk_available: bool | None = None
_rtk_missing_warned = False


def register(ctx: Any) -> None:
    """Register the Hermes pre-tool callback when the ``rtk`` binary exists."""
    if not _check_rtk():
        return

    ctx.register_hook("pre_tool_call", _pre_tool_call)


def _check_rtk() -> bool:
    """Return whether the rtk binary is in PATH, warning once when missing."""
    global _rtk_available, _rtk_missing_warned

    if _rtk_available is None:
        _rtk_available = shutil.which("rtk") is not None

    if not _rtk_available and not _rtk_missing_warned:
        logger.warning("rtk binary not found in PATH; rtk-rewrite hook not registered")
        _rtk_missing_warned = True

    return _rtk_available


def _rewrite_timeout() -> float:
    """Resolve the RTK rewrite timeout from env, falling back safely."""
    raw = os.getenv("HERMES_RTK_REWRITE_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Invalid HERMES_RTK_REWRITE_TIMEOUT=%r; using %.1fs",
            raw,
            DEFAULT_TIMEOUT_SECONDS,
        )
        return DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        logger.warning(
            "HERMES_RTK_REWRITE_TIMEOUT must be > 0; using %.1fs",
            DEFAULT_TIMEOUT_SECONDS,
        )
        return DEFAULT_TIMEOUT_SECONDS
    return value


def _pre_tool_call(tool_name: str | None = None, args: dict[str, Any] | None = None, **_kwargs: Any) -> None:
    """Rewrite mutable Hermes terminal command args when RTK provides a change."""
    try:
        if tool_name != "terminal" or not isinstance(args, dict):
            return

        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            return

        result = _run_rtk_rewrite(command)
        if result is None:
            return

        rewritten = result.strip()
        if rewritten and rewritten != command:
            args["command"] = rewritten
    except Exception as exc:  # pragma: no cover - final fail-open safety net
        logger.warning("rtk rewrite hook failed: %s", exc)


def _run_rtk_rewrite(command: str) -> str | None:
    """Call ``rtk rewrite`` and return a replacement command, if any."""
    try:
        result = subprocess.run(
            ["rtk", "rewrite", command],
            shell=False,
            timeout=_rewrite_timeout(),
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("rtk rewrite timed out")
        return None
    except OSError as exc:
        logger.warning("rtk rewrite failed to start: %s", exc)
        return None

    if result.returncode not in ACCEPTED_REWRITE_RETURN_CODES:
        if result.returncode not in EXPECTED_PASSTHROUGH_RETURN_CODES:
            stderr = (result.stderr or "").strip()
            details = f"rtk rewrite failed with exit {result.returncode}"
            if stderr:
                details = f"{details}: {stderr}"
            logger.warning(details)
        return None

    return result.stdout or ""
