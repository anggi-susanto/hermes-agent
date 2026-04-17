"""Compatibility shim for the built-in memory provider.

The built-in memory system is now embodied by the always-present local memory
files/tools rather than a standalone provider class, but older tests/imports
still reference agent.builtin_memory_provider.BuiltinMemoryProvider.

Provide a tiny no-op provider that identifies itself as the builtin provider so
MemoryManager registration semantics and user_id threading tests keep working.
"""

from __future__ import annotations

from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider


class BuiltinMemoryProvider(MemoryProvider):
    @property
    def name(self) -> str:
        return "builtin"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        # Built-in memory is managed elsewhere; this shim only preserves the
        # provider contract for tests and compatibility imports.
        return None

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        raise NotImplementedError(f"Builtin memory shim does not handle tool {tool_name}")

    def shutdown(self) -> None:
        return None
