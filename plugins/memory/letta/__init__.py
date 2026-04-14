"""Letta memory plugin — external memory provider using a self-hosted Letta API.

Mode B integration: Hermes remains the primary agent; Letta acts as a structured
memory service. The provider stores durable memory as archival-memory passages on
one lightweight Letta agent per canonical user.

Memory model:
- profile
- preference
- episodic
- summary

Write policy:
- mirror built-in memory writes (user/profile durable facts)
- optional session-end summaries
- ignore transient turn-by-turn chat spam

Read policy:
- prefetch on session start / ambiguous queries / project references
- tool access for explicit inspection/search/write
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, parse, request

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

PROFILE_SCHEMA = {
    "name": "letta_profile",
    "description": "Get compact structured profile/preference memory for the current user from Letta.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SEARCH_SCHEMA = {
    "name": "letta_search",
    "description": "Semantic search over Letta archival memory for the current user. Use for cross-session recall.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "top_k": {"type": "integer", "description": "Maximum results to return (default 5)."},
            "memory_type": {
                "type": "string",
                "description": "Optional filter: profile, preference, episodic, or summary.",
                "enum": ["profile", "preference", "episodic", "summary"],
            },
            "project": {"type": "string", "description": "Optional project namespace filter."},
        },
        "required": ["query"],
    },
}

CONTEXT_SCHEMA = {
    "name": "letta_context",
    "description": "Ask for compact relevant Letta memory context about the current user or project.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language question about remembered user/project context."},
            "project": {"type": "string", "description": "Optional project namespace filter."},
        },
        "required": ["query"],
    },
}

CONCLUDE_SCHEMA = {
    "name": "letta_conclude",
    "description": "Write a durable structured memory entry into Letta for the current user.",
    "parameters": {
        "type": "object",
        "properties": {
            "conclusion": {"type": "string", "description": "Durable fact/preference to store."},
            "memory_type": {
                "type": "string",
                "description": "Memory type bucket.",
                "enum": ["profile", "preference", "episodic", "summary"],
                "default": "preference",
            },
            "project": {"type": "string", "description": "Optional project namespace."},
            "confidence": {"type": "number", "description": "Confidence 0..1 (default 0.9)."},
            "source": {"type": "string", "description": "Source tag (default user_explicit)."},
        },
        "required": ["conclusion"],
    },
}

ALL_TOOL_SCHEMAS = [PROFILE_SCHEMA, SEARCH_SCHEMA, CONTEXT_SCHEMA, CONCLUDE_SCHEMA]


@dataclass
class LettaConfig:
    enabled: bool = True
    base_url: str = ""
    api_key: str = ""
    agent_name_prefix: str = "Hermes Memory"
    user_id_header: str = ""
    project_id: str = ""
    prefetch_top_k: int = 5
    auto_session_summary: bool = True
    session_summary_char_limit: int = 1200

    @classmethod
    def from_global_config(cls) -> "LettaConfig":
        try:
            from hermes_cli.config import load_config
            cfg = load_config()
        except Exception:
            cfg = {}
        mem = cfg.get("memory", {}) if isinstance(cfg, dict) else {}
        letta = mem.get("letta", {}) if isinstance(mem, dict) else {}
        env = os.environ
        return cls(
            enabled=bool(letta.get("enabled", True)),
            base_url=(env.get("LETTA_BASE_URL") or letta.get("base_url") or "").rstrip("/"),
            api_key=env.get("LETTA_API_KEY") or letta.get("api_key") or "",
            agent_name_prefix=letta.get("agent_name_prefix", "Hermes Memory"),
            user_id_header=letta.get("user_id_header", env.get("LETTA_USER_ID_HEADER", "")),
            project_id=env.get("LETTA_PROJECT_ID") or letta.get("project_id") or "",
            prefetch_top_k=int(letta.get("prefetch_top_k", 5) or 5),
            auto_session_summary=str(letta.get("auto_session_summary", True)).lower() in ("true", "1", "yes"),
            session_summary_char_limit=int(letta.get("session_summary_char_limit", 1200) or 1200),
        )


class LettaClient:
    def __init__(self, config: LettaConfig):
        self.config = config

    def _headers(self, *, json_body: bool = True) -> Dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "Hermes-Agent/LettaMemoryProvider"}
        if json_body:
            headers["Content-Type"] = "application/json"
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        if self.config.project_id:
            headers["X-Project-Id"] = self.config.project_id
        if self.config.user_id_header:
            headers["user_id"] = self.config.user_id_header
        return headers

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.config.base_url}{path}"
        if params:
            clean = []
            for k, v in params.items():
                if v is None:
                    continue
                if isinstance(v, list):
                    for item in v:
                        clean.append((k, str(item)))
                else:
                    clean.append((k, str(v)))
            if clean:
                url += "?" + parse.urlencode(clean, doseq=True)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = request.Request(url, data=data, method=method, headers=self._headers(json_body=body is not None))
        try:
            with request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"{method} {path} failed: HTTP {e.code} {detail}") from e
        except error.URLError as e:
            raise RuntimeError(f"{method} {path} failed: {e.reason}") from e

    def list_agents(self, *, name: str) -> List[Dict[str, Any]]:
        data = self._request("GET", "/v1/agents/", params={"name": name, "limit": 10})
        return data if isinstance(data, list) else []

    def create_agent(self, *, name: str, tags: List[str]) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/v1/agents/",
            body={"name": name, "tags": tags, "model": "letta/letta-free"},
        )

    def get_core_memory_blocks(self, agent_id: str) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/v1/agents/{agent_id}/core-memory/blocks")
        return data if isinstance(data, list) else []

    def update_core_memory_block(self, agent_id: str, block_label: str, value: str) -> Dict[str, Any]:
        return self._request("PATCH", f"/v1/agents/{agent_id}/core-memory/blocks/{parse.quote(block_label, safe='')}", body={"value": value})

    def create_passage(self, agent_id: str, text: str) -> Dict[str, Any]:
        return self._request("POST", f"/v1/agents/{agent_id}/archival-memory", body={"text": text})

    def list_archival_memory(self, agent_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/v1/agents/{agent_id}/archival-memory", params={"limit": limit})
        return data if isinstance(data, list) else []

    def search_archival_memory(self, agent_id: str, *, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/v1/agents/{agent_id}/archival-memory/search", params={"query": query, "top_k": top_k})
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            results = data.get("results")
            if isinstance(results, list):
                normalized: List[Dict[str, Any]] = []
                for item in results:
                    if isinstance(item, dict):
                        normalized.append(
                            {
                                "id": item.get("id"),
                                "text": item.get("text") or item.get("content") or "",
                                "content": item.get("content") or item.get("text") or "",
                                "timestamp": item.get("timestamp"),
                                "tags": item.get("tags") or [],
                                "_raw": item,
                            }
                        )
                return normalized
        return []


class LettaMemoryProvider(MemoryProvider):
    def __init__(self):
        self._config: Optional[LettaConfig] = None
        self._client: Optional[LettaClient] = None
        self._session_id = ""
        self._platform = "cli"
        self._canonical_user_id = "local:default"
        self._agent_id = ""
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._initialized = False

    @property
    def name(self) -> str:
        return "letta"

    def is_available(self) -> bool:
        try:
            cfg = LettaConfig.from_global_config()
            return bool(cfg.enabled and cfg.base_url)
        except Exception:
            return False

    def get_config_schema(self):
        return [
            {"key": "base_url", "description": "Letta base URL", "default": "https://letta.example.com", "required": True},
            {"key": "api_key", "description": "Letta API key (optional for open/self-hosted deployments)", "secret": True, "env_var": "LETTA_API_KEY"},
            {"key": "project_id", "description": "Optional Letta project ID", "secret": True, "env_var": "LETTA_PROJECT_ID"},
            {"key": "agent_name_prefix", "description": "Prefix for per-user Letta agents", "default": "Hermes Memory"},
            {"key": "prefetch_top_k", "description": "Default number of recall hits", "default": 5},
            {"key": "auto_session_summary", "description": "Store compact session summaries at session end", "choices": [True, False], "default": True},
            {"key": "session_summary_char_limit", "description": "Max chars for generated session summary text", "default": 1200},
        ]

    def save_config(self, values, hermes_home):
        config_path = Path(hermes_home) / "letta.json"
        existing = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
            except Exception:
                existing = {}
        existing.update(values)
        config_path.write_text(json.dumps(existing, indent=2))

    def initialize(self, session_id: str, **kwargs) -> None:
        self._config = LettaConfig.from_global_config()
        if not self._config.base_url:
            return
        self._session_id = session_id
        self._platform = kwargs.get("platform", "cli")
        self._agent_context = kwargs.get("agent_context", "primary")
        if self._agent_context in ("cron", "flush", "subagent"):
            logger.debug("Letta skipped: non-primary context (%s)", self._agent_context)
            return
        self._client = LettaClient(self._config)
        self._canonical_user_id = self._resolve_canonical_user_id(kwargs)
        self._agent_id = self._ensure_agent()
        self._initialized = bool(self._agent_id)
        if self._initialized:
            self._write_profile_block()
            self._refresh_prefetch("session start")

    def _resolve_canonical_user_id(self, kwargs: Dict[str, Any]) -> str:
        raw_user_id = (kwargs.get("user_id") or "").strip()
        if raw_user_id:
            if ":" in raw_user_id:
                return raw_user_id
            return f"{self._platform}:{raw_user_id}"
        return f"{self._platform}:default"

    def _safe_slug(self, text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-").lower()
        return slug[:60] or "default"

    def _agent_name(self) -> str:
        assert self._config is not None
        return f"{self._config.agent_name_prefix} {self._safe_slug(self._canonical_user_id)}"

    def _ensure_agent(self) -> str:
        assert self._client is not None
        name = self._agent_name()
        agents = self._client.list_agents(name=name)
        for agent in agents:
            if agent.get("name") == name and agent.get("id"):
                return agent["id"]
        created = self._client.create_agent(name=name, tags=["hermes", "memory", f"user:{self._safe_slug(self._canonical_user_id)}"])
        return created.get("id", "")

    def _write_profile_block(self) -> None:
        if not self._agent_id or not self._client:
            return
        profile_lines = [
            f"canonical_user_id={self._canonical_user_id}",
            f"platform={self._platform}",
            "memory_model=profile|preference|episodic|summary",
            "policy=durable_only; no raw chat dump",
        ]
        try:
            blocks = self._client.get_core_memory_blocks(self._agent_id)
            preferred = None
            for block in blocks:
                label = block.get("label") or block.get("name") or ""
                if label in ("human", "persona", "profile", "memory"):
                    preferred = label
                    break
            if preferred:
                self._client.update_core_memory_block(self._agent_id, preferred, "\n".join(profile_lines))
        except Exception as e:
            logger.debug("Letta core memory block update skipped: %s", e)

    def system_prompt_block(self) -> str:
        if not self._initialized:
            return ""
        return (
            "# Letta Memory\n"
            "Active (memory-service mode). Use letta_profile / letta_search / letta_context / letta_conclude for explicit memory access.\n"
            "Structured memory types: profile, preference, episodic, summary.\n"
            "Only durable facts/preferences/project conventions should be written."
        )

    def _format_memory_record(self, content: str, *, memory_type: str, source: str, confidence: float, project: str = "", session_id: str = "") -> str:
        payload = {
            "memory_type": memory_type,
            "canonical_user_id": self._canonical_user_id,
            "project": project or None,
            "content": content.strip(),
            "confidence": round(float(confidence), 3),
            "source": source,
            "session_id": session_id or self._session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(payload, ensure_ascii=False)

    def _store_memory(self, content: str, *, memory_type: str, source: str = "user_explicit", confidence: float = 0.9, project: str = "") -> Dict[str, Any]:
        if not self._initialized or not self._client or not self._agent_id:
            return {"status": "skipped", "reason": "provider not initialized"}
        text = self._format_memory_record(content, memory_type=memory_type, source=source, confidence=confidence, project=project)
        created = self._client.create_passage(self._agent_id, text)
        passage_id = ""
        if isinstance(created, dict):
            passage_id = str(created.get("id") or "")
        elif isinstance(created, list) and created:
            first = created[0]
            if isinstance(first, dict):
                passage_id = str(first.get("id") or "")
        return {"status": "stored", "id": passage_id or None, "memory_type": memory_type}

    def _decode_passage(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        text = item.get("text") or item.get("content") or ""
        if not isinstance(text, str) or not text.strip():
            return None
        try:
            payload = json.loads(text)
            if isinstance(payload, dict) and payload.get("content"):
                payload["_raw"] = item
                return payload
        except Exception:
            return {"memory_type": "unknown", "content": text, "_raw": item}
        return None

    def _search(self, query: str, *, top_k: int = 5, memory_type: str = "", project: str = "") -> List[Dict[str, Any]]:
        if not self._initialized or not self._client or not self._agent_id:
            return []

        def _filter_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            decoded = []
            for row in rows:
                payload = self._decode_passage(row)
                if not payload:
                    continue
                if memory_type and payload.get("memory_type") != memory_type:
                    continue
                if project and payload.get("project") not in (project, None, ""):
                    continue
                decoded.append(payload)
            return decoded

        rows = self._client.search_archival_memory(self._agent_id, query=query, top_k=top_k)
        decoded = _filter_rows(rows)
        if decoded:
            return decoded

        query_terms = [term for term in re.split(r"\W+", query.lower()) if len(term) >= 3]
        archival_rows = self._client.list_archival_memory(self._agent_id, limit=max(top_k * 10, 100))
        fallback_hits = []
        for row in archival_rows:
            payload = self._decode_passage(row)
            if not payload:
                continue
            if memory_type and payload.get("memory_type") != memory_type:
                continue
            if project and payload.get("project") not in (project, None, ""):
                continue
            haystack = json.dumps(payload, ensure_ascii=False).lower()
            score = sum(1 for term in query_terms if term in haystack)
            if score > 0:
                payload["_fallback_score"] = score
                fallback_hits.append(payload)

        fallback_hits.sort(key=lambda item: item.get("_fallback_score", 0), reverse=True)
        return fallback_hits[:top_k]

    def _render_hits(self, hits: List[Dict[str, Any]]) -> str:
        if not hits:
            return "No relevant Letta memory found."
        lines = []
        for hit in hits[:8]:
            mt = hit.get("memory_type", "unknown")
            project = hit.get("project") or "-"
            confidence = hit.get("confidence")
            content = str(hit.get("content", "")).strip()
            lines.append(f"- [{mt}] (project={project}, confidence={confidence}) {content}")
        return "\n".join(lines)

    def _refresh_prefetch(self, query: str) -> None:
        hits = self._search(query, top_k=self._config.prefetch_top_k if self._config else 5)
        text = ""
        if hits:
            text = "# Letta Relevant Memory\n" + self._render_hits(hits)
        with self._prefetch_lock:
            self._prefetch_result = text

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        q = (query or "").strip()
        if q:
            lowered = q.lower()
            if any(tok in lowered for tok in ["remember", "kayak biasa", "seperti biasa", "preference", "prefer", "centracast", "deploy", "vault", "project"]):
                self._refresh_prefetch(q)
        with self._prefetch_lock:
            return self._prefetch_result

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if not query:
            return
        try:
            self._refresh_prefetch(query)
        except Exception:
            logger.debug("Letta queue_prefetch failed", exc_info=True)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        return

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return ALL_TOOL_SCHEMAS

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        try:
            if tool_name == "letta_profile":
                hits = self._search("user profile preferences communication style", top_k=8)
                return json.dumps({"result": self._render_hits([h for h in hits if h.get('memory_type') in ('profile','preference')])})
            if tool_name == "letta_search":
                hits = self._search(
                    args.get("query", ""),
                    top_k=int(args.get("top_k", 5) or 5),
                    memory_type=args.get("memory_type", "") or "",
                    project=args.get("project", "") or "",
                )
                return json.dumps({"result": self._render_hits(hits), "items": hits})
            if tool_name == "letta_context":
                hits = self._search(args.get("query", ""), top_k=6, project=args.get("project", "") or "")
                return json.dumps({"result": self._render_hits(hits)})
            if tool_name == "letta_conclude":
                result = self._store_memory(
                    args.get("conclusion", ""),
                    memory_type=args.get("memory_type", "preference") or "preference",
                    project=args.get("project", "") or "",
                    confidence=float(args.get("confidence", 0.9) or 0.9),
                    source=args.get("source", "user_explicit") or "user_explicit",
                )
                return json.dumps(result)
            return json.dumps({"error": f"Unknown Letta tool: {tool_name}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        if action == "remove" or not content.strip():
            return
        memory_type = "profile" if target == "user" else "preference"
        confidence = 0.95 if target == "user" else 0.9
        try:
            self._store_memory(content, memory_type=memory_type, source="builtin_memory_mirror", confidence=confidence)
        except Exception:
            logger.debug("Letta on_memory_write failed", exc_info=True)

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not self._config or not self._config.auto_session_summary or not messages:
            return
        user_msgs = []
        for msg in messages:
            if msg.get("role") == "user":
                text = msg.get("content")
                if isinstance(text, str) and text.strip():
                    user_msgs.append(text.strip())
        if not user_msgs:
            return
        summary = " | ".join(user_msgs[-5:])
        summary = summary[: self._config.session_summary_char_limit].strip()
        if summary:
            try:
                self._store_memory(summary, memory_type="summary", source="session_end_summary", confidence=0.7)
            except Exception:
                logger.debug("Letta session summary write failed", exc_info=True)

    def shutdown(self) -> None:
        return


def register(ctx) -> None:
    ctx.register_memory_provider(LettaMemoryProvider())
