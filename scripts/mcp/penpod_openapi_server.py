from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import httpx
from mcp.server import FastMCP


SERVER_NAME = os.getenv("PENPOD_MCP_SERVER_NAME", "penpod-api")
DEFAULT_SPEC_URL = os.getenv(
    "PENPOD_OPENAPI_URL",
    "https://prd-srvc-penpod-ext.penpod.id/in/swagger/swagger.json",
)
DEFAULT_BASE_URL = os.getenv("PENPOD_API_BASE_URL", "https://prd-srvc-penpod-ext.penpod.id")
REQUEST_TIMEOUT = float(os.getenv("PENPOD_API_TIMEOUT_SECONDS", "60"))
VERIFY_SSL = os.getenv("PENPOD_API_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
DEFAULT_LIMIT = int(os.getenv("PENPOD_MCP_DEFAULT_LIMIT", "25"))
MAX_LIST_LIMIT = int(os.getenv("PENPOD_MCP_MAX_LIST_LIMIT", "200"))
AUTH_GRANT_PATH = os.getenv("PENPOD_AUTH_GRANT_PATH", "/ex/v1/auth/grant-client")
TOKEN_ENV_KEYS = (
    "PENPOD_BEARER_TOKEN",
    "PENPOD_API_TOKEN",
    "PENPOD_TOKEN",
)
USERNAME_ENV_KEYS = (
    "PENPOD_USERNAME",
    "PENPOD_USER",
    "PENPOD_EMAIL",
)
PASSWORD_ENV_KEYS = (
    "PENPOD_PASSWORD",
    "PENPOD_PASS",
)

mcp = FastMCP(SERVER_NAME)


@dataclass(frozen=True)
class Operation:
    operation_id: str
    upstream_operation_id: str | None
    method: str
    path: str
    summary: str
    description: str
    tags: list[str]
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None
    security: list[dict[str, Any]]
    responses: dict[str, Any]
    deprecated: bool


class PenpodAPIError(RuntimeError):
    pass


class OperationNotFoundError(PenpodAPIError):
    pass


class ValidationError(PenpodAPIError):
    pass


_JSON_SCHEMA_PRIMITIVES = {"string", "number", "integer", "boolean", "array", "object"}


def _env_first(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _env_token() -> str | None:
    return _env_first(TOKEN_ENV_KEYS)


def _env_username() -> str | None:
    return _env_first(USERNAME_ENV_KEYS)


def _env_password() -> str | None:
    return _env_first(PASSWORD_ENV_KEYS)


@lru_cache(maxsize=1)
def _get_auto_bearer_token() -> str | None:
    explicit = _env_token()
    if explicit:
        return explicit

    username = _env_username()
    password = _env_password()
    if not username or not password:
        return None

    url = f"{DEFAULT_BASE_URL.rstrip('/')}/{AUTH_GRANT_PATH.lstrip('/')}"
    payload_candidates = [
        {"username": username, "password": password},
        {"email": username, "password": password},
        {"user": username, "password": password},
        {"login": username, "password": password},
    ]

    with httpx.Client(timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL, follow_redirects=True) as client:
        errors: list[str] = []
        for payload in payload_candidates:
            try:
                response = client.post(url, json=payload, headers={"Accept": "application/json", "User-Agent": "penpod-openapi-mcp/1.0"})
                if not response.is_success:
                    errors.append(f"{response.status_code}: {response.text[:200]}")
                    continue
                data = response.json()
            except Exception as exc:
                errors.append(str(exc))
                continue

            token = (
                (data.get("data") or {}).get("access_token")
                or data.get("access_token")
                or (data.get("token") if isinstance(data, dict) else None)
            )
            if token:
                return str(token).strip()

        raise PenpodAPIError(
            "Failed to auto-acquire Penpod bearer token using PENPOD_USERNAME/PENPOD_PASSWORD via "
            f"{AUTH_GRANT_PATH}. Errors: {errors}"
        )


@lru_cache(maxsize=1)
def _load_spec() -> dict[str, Any]:
    source = os.getenv("PENPOD_OPENAPI_FILE", "").strip()
    if source:
        with open(source, "r", encoding="utf-8") as handle:
            return json.load(handle)

    with httpx.Client(timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL, follow_redirects=True) as client:
        response = client.get(DEFAULT_SPEC_URL, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()


@lru_cache(maxsize=1)
def _spec_hash() -> str:
    payload = json.dumps(_load_spec(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _definitions() -> dict[str, Any]:
    spec = _load_spec()
    return spec.get("definitions", {})


@lru_cache(maxsize=1)
def _security_definitions() -> dict[str, Any]:
    spec = _load_spec()
    return spec.get("securityDefinitions", {})


@lru_cache(maxsize=1)
def _operations() -> dict[str, Operation]:
    spec = _load_spec()
    operations: dict[str, Operation] = {}

    for path, path_item in spec.get("paths", {}).items():
        common_parameters = path_item.get("parameters", [])
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue

            raw_operation_id = operation.get("operationId")
            operation_id = _normalize_operation_id(raw_operation_id, method, path)
            merged_parameters = list(common_parameters) + list(operation.get("parameters", []))
            request_body = _extract_request_body(merged_parameters)
            filtered_parameters = [
                _normalize_parameter(param)
                for param in merged_parameters
                if param.get("in") != "body"
            ]
            op = Operation(
                operation_id=operation_id,
                upstream_operation_id=raw_operation_id,
                method=method.upper(),
                path=path,
                summary=operation.get("summary") or raw_operation_id or f"{method.upper()} {path}",
                description=(operation.get("description") or "").strip(),
                tags=list(operation.get("tags") or []),
                parameters=filtered_parameters,
                request_body=request_body,
                security=list(operation.get("security") or spec.get("security") or []),
                responses=operation.get("responses") or {},
                deprecated=bool(operation.get("deprecated", False)),
            )
            operations[op.operation_id] = op

    return operations


def _normalize_operation_id(raw_operation_id: str | None, method: str, path: str) -> str:
    base = raw_operation_id.strip() if raw_operation_id else f"{method}_{path}"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_").lower()
    if not slug:
        slug = f"{method.lower()}_root"
    return slug


@lru_cache(maxsize=1)
def _alias_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for op_id, op in _operations().items():
        result[op_id] = op_id
        if op.upstream_operation_id:
            result[_normalize_operation_id(op.upstream_operation_id, op.method, op.path)] = op_id
        result[_normalize_operation_id(None, op.method, op.path)] = op_id
    return result


def _extract_request_body(parameters: list[dict[str, Any]]) -> dict[str, Any] | None:
    for param in parameters:
        if param.get("in") != "body":
            continue
        schema = _resolve_schema(param.get("schema")) if param.get("schema") else None
        return {
            "name": param.get("name") or "body",
            "required": bool(param.get("required", False)),
            "description": param.get("description") or "",
            "schema": schema,
        }
    return None


@lru_cache(maxsize=None)
def _resolve_ref(ref: str) -> Any:
    if not ref.startswith("#/definitions/"):
        raise ValidationError(f"Unsupported $ref format: {ref}")
    name = ref.split("/")[-1]
    if name not in _definitions():
        raise ValidationError(f"Definition not found for ref: {ref}")
    return _resolve_schema(_definitions()[name])


def _resolve_schema(schema: Any) -> Any:
    if schema is None:
        return None
    if isinstance(schema, list):
        return [_resolve_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    if "$ref" in schema:
        return _resolve_ref(schema["$ref"])

    resolved: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            resolved[key] = {name: _resolve_schema(prop) for name, prop in value.items()}
        elif key == "items":
            resolved[key] = _resolve_schema(value)
        elif key in {"allOf", "anyOf", "oneOf"} and isinstance(value, list):
            resolved[key] = [_resolve_schema(item) for item in value]
        else:
            resolved[key] = value
    return resolved


def _normalize_parameter(param: dict[str, Any]) -> dict[str, Any]:
    schema = param.get("schema")
    normalized = {
        "name": param.get("name"),
        "in": param.get("in"),
        "required": bool(param.get("required", False)),
        "description": (param.get("description") or "").strip(),
        "type": param.get("type"),
    }
    if schema:
        normalized["schema"] = _resolve_schema(schema)
    if "enum" in param:
        normalized["enum"] = param["enum"]
    if "default" in param:
        normalized["default"] = param["default"]
    if "format" in param:
        normalized["format"] = param["format"]
    if "items" in param:
        normalized["items"] = _resolve_schema(param["items"])
    return normalized


def _summarize_parameter(param: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "name": param.get("name"),
        "in": param.get("in"),
        "required": param.get("required", False),
        "type": param.get("type") or param.get("schema", {}).get("type") or "object",
    }
    if param.get("enum"):
        summary["enum"] = param["enum"]
    if param.get("description"):
        summary["description"] = param["description"]
    return summary


def _get_operation(operation_id: str) -> Operation:
    canonical = _alias_map().get(operation_id)
    if not canonical:
        raise OperationNotFoundError(
            f"Unknown operation_id '{operation_id}'. Use penpod_list_operations() first to discover valid operation IDs."
        )
    return _operations()[canonical]


def _coerce_scalar(value: Any, expected_type: str | None) -> Any:
    if expected_type in (None, "string"):
        return value if isinstance(value, str) else str(value)
    if expected_type == "integer":
        return int(value)
    if expected_type == "number":
        return float(value)
    if expected_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValueError(f"Cannot coerce {value!r} to boolean")
    return value


def _validate_and_coerce_named_params(
    supplied: dict[str, Any] | None,
    declared: list[dict[str, Any]],
    *,
    location: str,
) -> dict[str, Any]:
    supplied = supplied or {}
    result: dict[str, Any] = {}
    declared_names = {param["name"] for param in declared}

    for param in declared:
        name = param["name"]
        if param.get("required") and name not in supplied:
            raise ValidationError(f"Missing required {location} parameter: {name}")
        if name not in supplied:
            continue
        value = supplied[name]
        try:
            result[name] = _coerce_scalar(value, param.get("type"))
        except Exception as exc:
            raise ValidationError(
                f"Invalid value for {location} parameter '{name}': expected {param.get('type')}, got {value!r}"
            ) from exc

    unknown = sorted(set(supplied) - declared_names)
    if unknown:
        raise ValidationError(
            f"Unknown {location} parameters: {', '.join(unknown)}. Allowed: {', '.join(sorted(declared_names)) or '(none)'}"
        )

    return result


def _validate_body(operation: Operation, body: Any) -> Any:
    if operation.request_body is None:
        if body is not None:
            raise ValidationError(f"Operation '{operation.operation_id}' does not accept a request body")
        return None

    if body is None:
        if operation.request_body.get("required"):
            raise ValidationError(f"Operation '{operation.operation_id}' requires a request body")
        return None

    schema = operation.request_body.get("schema") or {}
    expected_type = schema.get("type")
    if expected_type == "object" and not isinstance(body, dict):
        raise ValidationError(f"Request body for '{operation.operation_id}' must be an object")
    if expected_type == "array" and not isinstance(body, list):
        raise ValidationError(f"Request body for '{operation.operation_id}' must be an array")
    return body


def _build_headers(extra_headers: dict[str, Any] | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "penpod-openapi-mcp/1.0",
    }
    token = _get_auto_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        for key, value in extra_headers.items():
            if value is None:
                continue
            headers[str(key)] = str(value)
    return headers


def _http_request(
    operation: Operation,
    *,
    path_params: dict[str, Any] | None,
    query_params: dict[str, Any] | None,
    body: Any,
    headers: dict[str, Any] | None,
) -> dict[str, Any]:
    path_declared = [param for param in operation.parameters if param.get("in") == "path"]
    query_declared = [param for param in operation.parameters if param.get("in") == "query"]
    header_declared = [param for param in operation.parameters if param.get("in") == "header"]

    normalized_path = _validate_and_coerce_named_params(path_params, path_declared, location="path")
    normalized_query = _validate_and_coerce_named_params(query_params, query_declared, location="query")
    normalized_header_params = _validate_and_coerce_named_params(headers, header_declared, location="header")
    normalized_body = _validate_body(operation, body)

    url_path = operation.path
    for key, value in normalized_path.items():
        url_path = url_path.replace("{" + key + "}", str(value))

    url = f"{DEFAULT_BASE_URL.rstrip('/')}/{url_path.lstrip('/')}"
    request_headers = _build_headers(normalized_header_params)

    with httpx.Client(timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL, follow_redirects=True) as client:
        response = client.request(
            operation.method,
            url,
            params=normalized_query,
            json=normalized_body,
            headers=request_headers,
        )

    content_type = response.headers.get("content-type", "")
    parsed_body: Any = None
    raw_body: str | None = None
    if response.content:
        if "json" in content_type.lower():
            try:
                parsed_body = response.json()
            except Exception:
                raw_body = response.text
        else:
            raw_body = response.text

    return {
        "ok": response.is_success,
        "status_code": response.status_code,
        "reason_phrase": response.reason_phrase,
        "request": {
            "method": operation.method,
            "url": str(response.request.url),
            "path_params": normalized_path,
            "query_params": normalized_query,
            "headers_sent": sorted(request_headers.keys()),
            "body": normalized_body,
        },
        "response": {
            "headers": {k: v for k, v in response.headers.items() if k.lower() in {"content-type", "date", "etag", "x-request-id"}},
            "json": parsed_body,
            "text": raw_body,
        },
        "auth": {
            "bearer_token_configured": bool(_env_token()),
            "auto_auth_configured": bool(_env_username() and _env_password()),
            "token_source": "explicit_token" if _env_token() else ("username_password_via_grant_client" if (_env_username() and _env_password()) else "none"),
            "security": operation.security,
        },
    }


@mcp.tool()
def penpod_get_api_info() -> dict[str, Any]:
    """Show upstream Penpod API metadata loaded from the Swagger/OpenAPI document."""
    spec = _load_spec()
    return {
        "server_name": SERVER_NAME,
        "spec_url": DEFAULT_SPEC_URL,
        "base_url": DEFAULT_BASE_URL,
        "title": spec.get("info", {}).get("title"),
        "version": spec.get("info", {}).get("version"),
        "path_count": len(spec.get("paths", {})),
        "operation_count": len(_operations()),
        "definition_count": len(spec.get("definitions", {})),
        "security_definitions": _security_definitions(),
        "spec_sha256": _spec_hash(),
        "token_env_keys": TOKEN_ENV_KEYS,
        "bearer_token_configured": bool(_env_token()),
    }


@mcp.tool()
def penpod_list_tags(search: str = "") -> dict[str, Any]:
    """List API tags/groups from the loaded Penpod Swagger spec."""
    tag_map: dict[str, int] = {}
    for operation in _operations().values():
        for tag in operation.tags or ["untagged"]:
            tag_map[tag] = tag_map.get(tag, 0) + 1

    items = [
        {"tag": tag, "operation_count": count}
        for tag, count in sorted(tag_map.items(), key=lambda item: item[0].lower())
    ]
    if search.strip():
        needle = search.strip().lower()
        items = [item for item in items if needle in item["tag"].lower()]
    return {"count": len(items), "items": items}


@mcp.tool()
def penpod_list_operations(
    search: str = "",
    tag: str = "",
    method: str = "",
    limit: int = DEFAULT_LIMIT,
    include_deprecated: bool = False,
) -> dict[str, Any]:
    """List available REST operations from the Penpod Swagger spec, filterable by search/tag/method."""
    query = search.strip().lower()
    tag_filter = tag.strip().lower()
    method_filter = method.strip().upper()
    safe_limit = max(1, min(limit, MAX_LIST_LIMIT))

    items: list[dict[str, Any]] = []
    for operation in sorted(_operations().values(), key=lambda op: (op.tags[:1], op.path, op.method)):
        if operation.deprecated and not include_deprecated:
            continue
        if method_filter and operation.method != method_filter:
            continue
        if tag_filter and not any(tag_filter == t.lower() for t in operation.tags):
            continue
        haystack = " ".join(
            [
                operation.operation_id,
                operation.upstream_operation_id or "",
                operation.summary,
                operation.description,
                operation.path,
                " ".join(operation.tags),
            ]
        ).lower()
        if query and query not in haystack:
            continue
        items.append(
            {
                "operation_id": operation.operation_id,
                "upstream_operation_id": operation.upstream_operation_id,
                "method": operation.method,
                "path": operation.path,
                "summary": operation.summary,
                "tags": operation.tags,
                "deprecated": operation.deprecated,
                "security": operation.security,
                "parameters": [_summarize_parameter(param) for param in operation.parameters],
                "has_request_body": bool(operation.request_body),
            }
        )

    total = len(items)
    return {
        "count": min(total, safe_limit),
        "total": total,
        "items": items[:safe_limit],
        "filters": {
            "search": search,
            "tag": tag,
            "method": method_filter,
            "include_deprecated": include_deprecated,
            "limit": safe_limit,
        },
    }


@mcp.tool()
def penpod_get_operation(operation_id: str) -> dict[str, Any]:
    """Get full metadata, parameter schema, auth requirement, and body schema for one Penpod API operation."""
    operation = _get_operation(operation_id)
    return {
        "operation_id": operation.operation_id,
        "upstream_operation_id": operation.upstream_operation_id,
        "method": operation.method,
        "path": operation.path,
        "summary": operation.summary,
        "description": operation.description,
        "tags": operation.tags,
        "deprecated": operation.deprecated,
        "security": operation.security,
        "parameters": operation.parameters,
        "request_body": operation.request_body,
        "responses": operation.responses,
    }


@mcp.tool()
def penpod_call_operation(
    operation_id: str,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    body: Any = None,
    headers: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute any Penpod REST API operation from the Swagger spec using a canonical operation_id."""
    operation = _get_operation(operation_id)
    path_declared = [param for param in operation.parameters if param.get("in") == "path"]
    query_declared = [param for param in operation.parameters if param.get("in") == "query"]
    header_declared = [param for param in operation.parameters if param.get("in") == "header"]

    normalized_path = _validate_and_coerce_named_params(path_params, path_declared, location="path")
    normalized_query = _validate_and_coerce_named_params(query_params, query_declared, location="query")
    normalized_headers = _validate_and_coerce_named_params(headers, header_declared, location="header")
    normalized_body = _validate_body(operation, body)

    url_path = operation.path
    for key, value in normalized_path.items():
        url_path = url_path.replace("{" + key + "}", str(value))

    preview_url = f"{DEFAULT_BASE_URL.rstrip('/')}/{url_path.lstrip('/')}"
    if normalized_query:
        preview_url = f"{preview_url}?{urlencode(normalized_query, doseq=True)}"

    preview = {
        "operation_id": operation.operation_id,
        "method": operation.method,
        "url": preview_url,
        "path_params": normalized_path,
        "query_params": normalized_query,
        "headers": sorted(_build_headers(normalized_headers).keys()),
        "body": normalized_body,
        "dry_run": dry_run,
    }
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "request": preview,
            "auth": {
                "bearer_token_configured": bool(_env_token()),
                "auto_auth_configured": bool(_env_username() and _env_password()),
            },
        }

    result = _http_request(
        operation,
        path_params=normalized_path,
        query_params=normalized_query,
        body=normalized_body,
        headers=normalized_headers,
    )
    result["request_preview"] = preview
    return result


@mcp.tool()
def penpod_get_deployment_spec(deployment_id: int, dry_run: bool = False) -> dict[str, Any]:
    """Get the latest deployment specification for a single deployment ID using GET /ex/v1/deployment/{id}/spec."""
    return penpod_call_operation(
        operation_id="get_ex_v1_deployment_id_spec",
        path_params={"id": deployment_id},
        dry_run=dry_run,
    )


@mcp.tool()
def penpod_get_latest_deployment_specs(deployment_ids: list[int], stop_on_error: bool = False) -> dict[str, Any]:
    """Batch-fetch the latest deployment specification for multiple deployment IDs."""
    if not deployment_ids:
        raise ValidationError("deployment_ids must contain at least one deployment ID")

    results: list[dict[str, Any]] = []
    for deployment_id in deployment_ids:
        item = {
            "deployment_id": int(deployment_id),
        }
        try:
            response = penpod_get_deployment_spec(deployment_id=int(deployment_id), dry_run=False)
            item["ok"] = bool(response.get("ok"))
            item["status_code"] = response.get("status_code")
            item["response"] = response.get("response")
            item["request_preview"] = response.get("request_preview")
        except Exception as exc:
            item["ok"] = False
            item["error"] = str(exc)
            if stop_on_error:
                raise
        results.append(item)

    success_count = sum(1 for item in results if item.get("ok"))
    return {
        "count": len(results),
        "success_count": success_count,
        "failure_count": len(results) - success_count,
        "items": results,
        "auth": {"bearer_token_configured": bool(_env_token())},
    }


@mcp.tool()
def penpod_run_deployment_job(deployment_id: int, job_id: int, tag: str, dry_run: bool = False) -> dict[str, Any]:
    """Trigger a deployment job via POST /ex/v1/job/run with deployment_id, job id, and image tag."""
    return penpod_call_operation(
        operation_id="post_ex_v1_job_run",
        body={
            "deployment_id": int(deployment_id),
            "id": int(job_id),
            "tag": tag,
        },
        dry_run=dry_run,
    )


@mcp.tool()
def penpod_get_service_deployment_status(deployment_name: str, dry_run: bool = False) -> dict[str, Any]:
    """Check the latest service deployment state by deployment name via GET /ex/v1/service/deployment/{deployment_name}."""
    return penpod_call_operation(
        operation_id="get_ex_v1_service_deployment_deployment_name",
        path_params={"deployment_name": deployment_name},
        dry_run=dry_run,
    )


@mcp.tool()
def penpod_check_last_deployments(deployment_names: list[str], stop_on_error: bool = False) -> dict[str, Any]:
    """Batch-check latest deployment state for multiple deployment names."""
    if not deployment_names:
        raise ValidationError("deployment_names must contain at least one deployment name")

    results: list[dict[str, Any]] = []
    for deployment_name in deployment_names:
        item = {
            "deployment_name": str(deployment_name),
        }
        try:
            response = penpod_get_service_deployment_status(deployment_name=str(deployment_name), dry_run=False)
            item["ok"] = bool(response.get("ok"))
            item["status_code"] = response.get("status_code")
            item["response"] = response.get("response")
            item["request_preview"] = response.get("request_preview")
        except Exception as exc:
            item["ok"] = False
            item["error"] = str(exc)
            if stop_on_error:
                raise
        results.append(item)

    success_count = sum(1 for item in results if item.get("ok"))
    return {
        "count": len(results),
        "success_count": success_count,
        "failure_count": len(results) - success_count,
        "items": results,
        "auth": {"bearer_token_configured": bool(_env_token())},
    }


@mcp.tool()
def penpod_get_deployment_history(
    deployment_id: int,
    job_id: int,
    limit: int = 10,
    page: int = 1,
    dry_run: bool = False,
) -> dict[str, Any]:
    """List job execution history for one deployment/job pair via GET /ex/v1/history."""
    return penpod_call_operation(
        operation_id="get_ex_v1_history",
        query_params={
            "deployment_id": int(deployment_id),
            "job_id": int(job_id),
            "limit": int(limit),
            "page": int(page),
        },
        dry_run=dry_run,
    )


def _extract_history_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response_json = ((payload or {}).get("response") or {}).get("json")
    if not isinstance(response_json, dict):
        return []
    items = response_json.get("data")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    if isinstance(items, dict):
        return [items]
    return []


def _history_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("updated_at") or "",
        item.get("created_at") or "",
        item.get("id") or 0,
    )


def _normalize_status(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_terminal_history_status(value: Any) -> bool:
    normalized = _normalize_status(value)
    return normalized in {
        "success",
        "successful",
        "succeeded",
        "done",
        "completed",
        "complete",
        "failed",
        "failure",
        "error",
        "cancelled",
        "canceled",
        "aborted",
        "timeout",
        "timed_out",
    }


@mcp.tool()
def penpod_get_latest_deployment_history(
    deployment_id: int,
    job_id: int,
    tag: str = "",
    limit: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Fetch deployment/job history and return the latest matching entry, optionally filtered by image tag."""
    response = penpod_get_deployment_history(
        deployment_id=deployment_id,
        job_id=job_id,
        limit=limit,
        page=1,
        dry_run=dry_run,
    )
    if dry_run:
        return response

    items = _extract_history_items(response)
    filtered = items
    if tag.strip():
        filtered = [item for item in items if str(item.get("tag") or "") == tag]
    latest = max(filtered, key=_history_sort_key) if filtered else None

    return {
        "ok": bool(response.get("ok")),
        "status_code": response.get("status_code"),
        "deployment_id": int(deployment_id),
        "job_id": int(job_id),
        "tag_filter": tag,
        "match_count": len(filtered),
        "latest": latest,
        "history_items": filtered,
        "request_preview": response.get("request_preview"),
        "auth": response.get("auth"),
    }


@mcp.tool()
def penpod_run_deployment_job_and_wait(
    deployment_id: int,
    job_id: int,
    tag: str,
    poll_interval_seconds: float = 5.0,
    timeout_seconds: float = 120.0,
    history_limit: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Trigger a deployment job, then poll history until a matching tag reaches a terminal build_status or timeout."""
    run_result = penpod_run_deployment_job(
        deployment_id=deployment_id,
        job_id=job_id,
        tag=tag,
        dry_run=dry_run,
    )
    if dry_run:
        wait_preview = penpod_get_latest_deployment_history(
            deployment_id=deployment_id,
            job_id=job_id,
            tag=tag,
            limit=history_limit,
            dry_run=True,
        )
        return {
            "ok": True,
            "dry_run": True,
            "run_request": run_result.get("request") or run_result.get("request_preview"),
            "wait_request": wait_preview.get("request") or wait_preview.get("request_preview"),
            "poll_interval_seconds": poll_interval_seconds,
            "timeout_seconds": timeout_seconds,
        }

    started_at = time.time()
    attempts: list[dict[str, Any]] = []
    final_history: dict[str, Any] | None = None
    terminal = False
    timed_out = False

    while True:
        history = penpod_get_latest_deployment_history(
            deployment_id=deployment_id,
            job_id=job_id,
            tag=tag,
            limit=history_limit,
            dry_run=False,
        )
        latest = history.get("latest") if isinstance(history, dict) else None
        build_status = (latest or {}).get("build_status") if isinstance(latest, dict) else None
        attempt = {
            "elapsed_seconds": round(time.time() - started_at, 2),
            "history_ok": history.get("ok") if isinstance(history, dict) else False,
            "status_code": history.get("status_code") if isinstance(history, dict) else None,
            "latest_history_id": (latest or {}).get("id") if isinstance(latest, dict) else None,
            "build_status": build_status,
            "tag": (latest or {}).get("tag") if isinstance(latest, dict) else None,
        }
        attempts.append(attempt)
        final_history = history

        if isinstance(latest, dict) and _is_terminal_history_status(build_status):
            terminal = True
            break

        if time.time() - started_at >= timeout_seconds:
            timed_out = True
            break

        time.sleep(max(0.1, float(poll_interval_seconds)))

    latest = (final_history or {}).get("latest") if isinstance(final_history, dict) else None
    build_status = (latest or {}).get("build_status") if isinstance(latest, dict) else None
    success = bool(run_result.get("ok")) and isinstance(latest, dict) and _normalize_status(build_status) in {
        "success",
        "successful",
        "succeeded",
        "done",
        "completed",
        "complete",
    }

    return {
        "ok": success,
        "timed_out": timed_out,
        "terminal_status_reached": terminal,
        "deployment_id": int(deployment_id),
        "job_id": int(job_id),
        "tag": tag,
        "run_result": run_result,
        "latest_history": latest,
        "final_history_lookup": final_history,
        "attempts": attempts,
        "poll_interval_seconds": poll_interval_seconds,
        "timeout_seconds": timeout_seconds,
    }


@mcp.tool()
def penpod_build_service_logs_websocket_url(
    namespace_id: int,
    namespace: str,
    pod: str,
    tail: int = 100,
    follow: bool = True,
    timestamps: bool = True,
) -> dict[str, Any]:
    """Build a ready-to-use WebSocket URL for streaming service pod logs."""
    token = _get_auto_bearer_token()
    if not token:
        raise ValidationError("No bearer token available for service log streaming")
    params = {
        "authorization": f"Bearer {token}",
        "namespace_id": int(namespace_id),
        "namespace": namespace,
        "pod": pod,
        "tail": int(tail),
        "follow": str(bool(follow)).lower(),
        "timestamps": str(bool(timestamps)).lower(),
    }
    base = DEFAULT_BASE_URL.rstrip("/")
    ws_base = re.sub(r"^https://", "wss://", re.sub(r"^http://", "ws://", base))
    path = "/ex/v1/remote/service/pod/logs"
    return {
        "ok": True,
        "websocket_url": f"{ws_base}{path}?{urlencode(params)}",
        "query_params": params,
    }


@mcp.tool()
def penpod_build_package_deployment_logs_websocket_url(package_deployment_id: int) -> dict[str, Any]:
    """Build a ready-to-use WebSocket URL for package deployment pod logs."""
    token = _get_auto_bearer_token()
    if not token:
        raise ValidationError("No bearer token available for package deployment log streaming")
    params = {
        "authorization": f"Bearer {token}",
    }
    base = DEFAULT_BASE_URL.rstrip("/")
    ws_base = re.sub(r"^https://", "wss://", re.sub(r"^http://", "ws://", base))
    path = f"/ex/v1/remote/package-deployment/{int(package_deployment_id)}/logs"
    return {
        "ok": True,
        "websocket_url": f"{ws_base}{path}?{urlencode(params)}",
        "query_params": params,
        "package_deployment_id": int(package_deployment_id),
    }


@mcp.tool()
def penpod_healthcheck() -> dict[str, Any]:
    """Quick smoke check: load the spec, show counts, and confirm the configured API root is reachable."""
    spec_info = penpod_get_api_info()
    with httpx.Client(timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL, follow_redirects=True) as client:
        response = client.get(DEFAULT_SPEC_URL, headers={"Accept": "application/json"})

    auth_info={
        "bearer_token_configured": bool(_env_token()),
        "auto_auth_configured": bool(_env_username() and _env_password()),
        "token_source": "explicit_token" if _env_token() else ("username_password_via_grant_client" if (_env_username() and _env_password()) else "none"),
    }
    if _env_username() and _env_password() and not _env_token():
        try:
            token=_get_auto_bearer_token()
            auth_info["auto_auth_ok"] = bool(token)
        except Exception as exc:
            auth_info["auto_auth_ok"] = False
            auth_info["auto_auth_error"] = str(exc)

    return {
        "spec": spec_info,
        "spec_fetch": {
            "status_code": response.status_code,
            "ok": response.is_success,
            "content_type": response.headers.get("content-type"),
        },
        "auth": auth_info,
    }


def _self_test() -> None:
    info = penpod_get_api_info()
    ops = penpod_list_operations(limit=5)
    payload = {
        "info": info,
        "sample_operations": ops["items"],
    }
    print(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Local MCP server for Penpod REST API via Swagger/OpenAPI")
    parser.add_argument("--self-test", action="store_true", help="Load spec and print a local summary instead of starting the MCP server")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return

    mcp.run()


if __name__ == "__main__":
    main()
