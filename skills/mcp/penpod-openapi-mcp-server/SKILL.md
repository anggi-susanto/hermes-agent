---
name: penpod-openapi-mcp-server
description: Build a local stdio MCP server in Python that wraps a Swagger/OpenAPI REST API with discovery tools plus a generic operation executor.
version: 1.0.0
author: Hermes Agent
tags: [mcp, openapi, swagger, rest, python]
---

# Penpod/OpenAPI MCP Server Pattern

Use when a user asks for a local MCP server to access a Swagger/OpenAPI REST API and wants something complete but maintainable.

## Recommended architecture

Do NOT generate one MCP tool per endpoint by default when the API is large.
Prefer a hybrid model:

1. `get_api_info`
2. `list_tags`
3. `list_operations`
4. `get_operation`
5. `call_operation`
6. optional `healthcheck`

This keeps the server complete while avoiding tool explosion.

## Why

Large Swagger specs often have 50-100+ operations. Turning every operation into a separate MCP tool creates:
- noisy tool menus
- worse tool selection behavior
- more maintenance when spec changes

A generic executor plus discovery tools is usually the sane default.

But if the user has a repeated operational workflow (for example deploy + check status), add a few thin convenience wrappers for the hot-path endpoints instead of forcing every call through the generic executor.

## Python implementation stack

If `fastmcp` is not installed separately, check whether the installed `mcp` package already exports FastMCP:

```python
from mcp.server import FastMCP
```

This works in current `mcp` package versions used here.

Core runtime pattern:

```python
from mcp.server import FastMCP

mcp = FastMCP("api-name")

@mcp.tool()
def some_tool(...):
    ...

if __name__ == "__main__":
    mcp.run()
```

## Implementation steps

1. Load the OpenAPI/Swagger JSON
   - prefer env override for local file path
   - otherwise fetch from remote URL
   - cache with `lru_cache`

2. Normalize operations
   - iterate `paths`
   - merge path-level and operation-level parameters
   - generate canonical `operation_id`
   - keep alias lookup from upstream `operationId` and method/path slug

3. Resolve schemas
   - support Swagger 2 `#/definitions/...`
   - resolve nested `$ref`
   - normalize `properties`, `items`, `allOf/anyOf/oneOf`

4. Expose discovery tools
   - `get_api_info`
   - `list_tags`
   - `list_operations`
   - `get_operation`

5. Expose generic executor tool
   - inputs:
     - `operation_id`
     - `path_params`
     - `query_params`
     - `body`
     - `headers`
     - `dry_run`
   - validate required params
   - coerce simple scalar types
   - inject bearer auth from env centrally
   - perform HTTP call with `httpx`
   - return structured request/response payload

6. For repeated operational paths, add thin helper tools
   - Example useful wrappers for deployment-heavy APIs:
     - `get_deployment_spec(deployment_id)` for `GET /deployment/{id}/spec`
     - `run_deployment_job(deployment_id, job_id, tag)` for `POST /job/run`
     - `get_service_deployment_status(deployment_name)` for `GET /service/deployment/{deployment_name}`
     - `get_deployment_history(deployment_id, job_id)` for `GET /history`
     - `get_latest_deployment_history(deployment_id, job_id, tag="")` to reduce post-processing in the caller
     - `run_deployment_job_and_wait(...)` to trigger and poll until terminal build status or timeout
     - websocket URL builders for log endpoints when the API exposes logs over WS instead of plain HTTP
     - batch wrappers like `check_last_deployments([...])`
   - Keep wrappers thin, but allow small convenience logic when it meaningfully removes agent friction:
     - selecting the latest history entry
     - filtering by image tag
     - polling with timeout
     - constructing authenticated websocket URLs
   - Prefer helper tools when the user describes the workflow in business terms instead of raw operation IDs

7. Add self-test mode
   - `--self-test` prints spec summary and sample operations
   - useful before wiring into Hermes MCP config

8. Add README next to the script
   - env vars
   - run command
   - Hermes config example
   - usage flow
   - include hot-path examples for the user’s real workflow (deploy, status check, spec check)

## Good defaults

Environment variables:
- `OPENAPI_URL`
- `API_BASE_URL`
- `API_TIMEOUT_SECONDS`
- `API_VERIFY_SSL`
- `OPENAPI_FILE`
- `BEARER_TOKEN`

For API-specific versions, prefix them, e.g. `PENPOD_*`.

For Penpod specifically, support both explicit token mode and credential-based auto mode:
- explicit token:
  - `PENPOD_BEARER_TOKEN`
  - `PENPOD_API_TOKEN`
  - `PENPOD_TOKEN`
- username/password aliases:
  - `PENPOD_USERNAME` / `PENPOD_USER` / `PENPOD_EMAIL`
  - `PENPOD_PASSWORD` / `PENPOD_PASS`
- optional auth endpoint overrides:
  - `PENPOD_AUTH_CLIENT_GRANT_PATH` (default `/ex/v1/auth/grant-client`)
  - `PENPOD_AUTH_USER_GRANT_PATH` (default `/ex/v1/grant/user/password`)
  - keep backward compatibility for older single-endpoint configs only as a legacy fallback, not the primary Penpod path

Recommended auth priority:
1. if explicit bearer token exists, use it
2. otherwise, if username+password exist, run the real Penpod browser login flow and cache the final user bearer token
3. otherwise send no Authorization header

Implementation note for Penpod auto-auth:
- do NOT stop after `grant-client`; that token is a client/bootstrap token and may pass a naive healthcheck while still failing protected Penpod resource endpoints
- the token you want for `GET /ex/v1/deployment` and similar resource calls is the final user token returned by `POST /ex/v1/grant/user/password`
- parse both common response shapes because live responses may differ by service:
  - grant-client commonly returns `data.access_token`
  - grant/user/password may return `data.token` and sometimes also `data.access_token`
- recommended header set for reproducing browser behavior during auth probes:
  - `Origin: https://app.penpod.id`
  - `Referer: https://app.penpod.id/`
  - `User-Agent: penpod-openapi-mcp/1.0` or a browser-ish UA when debugging
  - `Accept: */*` for grant-client
  - `Accept: application/json` and `Content-Type: application/json` for grant/user/password

Important Penpod-specific findings:
- the exposed Swagger does NOT declare a proper username/password login contract
- `POST /ex/v1/auth/grant-client` on the Penpod service has no declared request body in the spec
- in live testing, that endpoint still returns a client access token even with empty or arbitrary body
- the frontend runtime config can expose a split-base setup; inspect `window.__NUXT__.config.public` on `https://app.penpod.id/` before assuming one base URL for all flows
- for the production Penpod app observed here:
  - `apiBase = https://prd-srvc-auth-ext.penpod.id`
  - `penpodBase = https://prd-srvc-penpod-ext.penpod.id`
- the real login flow is therefore two-step:
  1. `POST {penpodBase}/ex/v1/auth/grant-client` to get a client token
  2. `POST {apiBase}/ex/v1/grant/user/password` with `Authorization: Bearer <client_token>` to get the user bearer token
  3. call protected Penpod resource endpoints on `penpodBase` with `Authorization: Bearer <user_token>`
- so username/password support is not just "POST to one auth endpoint"; for Penpod-like deployments, support separate env vars for auth/login base URL vs resource API base URL
- recommended env split when upstream uses multiple bases:
  - `PENPOD_API_BASE_URL` for resource calls/spec host
  - `PENPOD_AUTH_BASE_URL` for user/password login host
  - optional `PENPOD_GRANT_BASE_URL` if client-token grant lives on a third base, otherwise default to `PENPOD_API_BASE_URL`
- if future upstream behavior changes, try common payload shapes when auto-fetching: `{username,password}`, `{email,password}`, `{user,password}`, `{login,password}`
- validate this live with a browser/frontend bundle inspection plus direct HTTP probes, not just Swagger reading, because the spec may omit cross-service auth behavior
- key diagnostic smell from live testing: if `penpod_healthcheck` reports `auto_auth_ok: true` but a protected call like `GET /ex/v1/deployment` still returns `401` with `Invalid token for this service`, then the MCP server is almost certainly sending the wrong token type (often the client token from `grant-client` instead of the final user token) or using the wrong auth base/scope split
- second key diagnostic smell from live testing: if the patched Python module works when executed directly, but the same call still fails through Hermes native MCP, suspect MCP server config drift before re-debugging the code
- practical debugging order for this case:
  1. confirm the protected resource call actually sends `Authorization`
  2. confirm `bearer_token_configured` is false and `token_source` is `username_password_via_grant_client`
  3. if source-level direct HTTP probes succeed but `hermes chat` MCP calls still fail, compare the live shell env against `~/.hermes/config.yaml` under `mcp_servers.penpod.env` — especially `PENPOD_PASSWORD`, `PENPOD_USERNAME`, and `PENPOD_AUTH_BASE_URL`
  4. remember that the MCP subprocess uses the env embedded in Hermes config, not whatever corrected shell env you may currently have
  5. use cheap fingerprints or length checks when comparing secrets; do not print raw passwords into chat/logs
  6. after fixing config drift, rerun both `hermes mcp test penpod` and a real authenticated `hermes chat -Q --source tool -q "Use the penpod_call_operation MCP tool ..."` call, because `mcp test` only proves connection/tool discovery and does not prove protected-resource auth
  7. only if config is aligned and the live MCP call still fails should you go back to auth-flow implementation debugging
- deploy-trigger verification nuance from live use:
  - `run_deployment_job_and_wait(...)` may time out even when the deployment was actually accepted
  - `run_deployment_job(...)` may return HTTP 500 / `failed to trigger job execution` while a new deployment history row is still created for the requested tag
  - `run_deployment_job(...)` can also fail fast with HTTP 400 validation if `tag` is not accepted; one confirmed live failure mode is `invalid tag: must follow semantic versioning (e.g., v1.0.0 or 1.0.0)`
  - for Penpod deploy workflows, treat deployment history and service status as the source of truth, not the trigger endpoint response alone
  - recommended post-trigger verification order:
    1. query latest deployment history filtered by tag
    2. if a new row exists (`queued`, `running`, etc.), consider the trigger accepted
    3. then poll service deployment status by name to confirm generation/revision increments and new ReplicaSet/pods appear
    4. only conclude trigger failure if both the trigger call errors and no matching history entry appears
- remote exec/log streaming nuance from live use:
  - the Swagger can advertise websocket endpoints like `/ex/v1/remote/service/shell` and `/ex/v1/remote/service/pod/logs`, but that does NOT mean they are immediately usable from an agent session
  - one confirmed live failure mode: both endpoints returned HTTP 400 on websocket handshake even after obtaining a valid final user bearer token via the Penpod browser-auth flow
  - this happened even after resolving real deployment metadata first:
    - `get_ex_v1_service_deployment_deployment_name` returned deployment name `stg-centracast-web`, namespace `gunamaya`, and concrete pod names
    - `get_ex_v1_deployment_id` returned the authoritative `namespace_id` (for this case: `13`)
    - handshake still failed for both service shell and pod logs
  - implication: do NOT assume you can rerun an Artisan job through Penpod just because discovery shows shell/log endpoints and auth to normal REST endpoints works
  - recommended diagnostic order before relying on remote exec:
    1. resolve deployment metadata first via `get_service_deployment_status(deployment_name)` and `get_deployment_id(id)` to get deployment name, pod names, namespace, and authoritative `namespace_id`
    2. confirm you are using the final user bearer token, not just the client token from `grant-client`
    3. test websocket access separately from deploy/status REST calls
    4. if websocket handshake still returns HTTP 400, treat remote exec as unavailable/unknown-contract instead of brute-forcing retries
    5. pivot to another execution path: kubectl, SSH, an existing deployment job wrapper, or have the user run the in-pod command once and then resume with API verification
  - practical lesson: Penpod REST auth success + discovered websocket ops is not enough proof that controller-side shell access is actually reachable from Hermes; keep that as a separate capability check

## Operational workflow learned from live use

When using Penpod deploy tools in a multi-repo CentraCast workspace:
- do not assume the repo you just changed is the repo that should be deployed
- explicitly verify the deploy target repo/app first
- in this workspace, Penpod deploys were intended for `centracast` (Laravel backend), not `centracast-runtime`
- so before any Penpod action, confirm whether the deployment request refers to runtime orchestration code or the backend service

Recommended deploy preflight:
1. verify repo/path/branch with `pwd`, `git branch --show-current`, `git remote -v`, `git status --short`
2. confirm the deployment target service/repo with the user if there is any ambiguity
3. use `penpod_get_deployment_spec(deployment_id)` to discover the real `deployment_name`
4. use `penpod_get_service_deployment_status(deployment_name)` to capture pre-deploy health
5. inspect the latest history for that deployment/job pair before triggering anything
6. only then run the deployment job with a valid release tag

Tagging rule learned from live use:
- do not send raw git SHAs as Penpod `tag` values unless you already know that deployment accepts them
- prefer an existing valid release/image tag pattern from deployment history or use a semver-compliant tag
- if a deploy request fails with validation, stop and determine the accepted tag format before retrying
- important verification nuance after patching the server source:
  - a long-lived Hermes/MCP session may keep using the already-started stdio server process or cached tool path, so `penpod_call_operation(...)` can still show the old broken auth behavior even after the file on disk is fixed
  - when that happens, verify the patch by importing/running the Python module directly and making a live read-only request with `_build_headers()` or equivalent
  - then restart/reload the MCP server/session before concluding the patch failed
- concrete live check that proved the fix here:
  - `python -m py_compile scripts/mcp/penpod_openapi_server.py`
  - import the module directly
  - call `_get_auto_bearer_token()`
  - issue `GET {PENPOD_API_BASE_URL}/ex/v1/deployment?limit=3&page=1` with `_build_headers()`
  - success looked like HTTP 200 with deployment names such as `stg-centracast-web`
- important operational limitation learned from live staging use:
  - Penpod read-path helpers can be fully healthy (`hermes mcp test penpod`, `penpod_healthcheck`, deployment listing, deployment spec, service status, deployment history) while still not providing a usable path for arbitrary in-container command execution
  - in this case, the available helper set was enough to confirm deployment identity, pod names, health, and history, but not enough to reliably rerun an application job such as a Laravel queued job from inside the container
  - the remote shell websocket route (`GET /ex/v1/remote/service/shell`) should be treated as experimental until proven in the current environment; a manually constructed websocket handshake may still fail with HTTP 400 even after auth succeeds and the pod/service metadata is correct
  - so do not promise a job rerun just because Penpod MCP auth and read APIs work; first prove an actual exec path works
- recommended escalation order when asked to rerun an app job through Penpod:
  1. verify the target deployment with `penpod_get_deployment_spec(...)`
  2. capture current service health with `penpod_get_service_deployment_status(...)`
  3. inspect deployment details to obtain live pod names
  4. if available, test shell/log websocket capability separately before relying on it for execution
  5. if no proven exec path exists, stop and give the operator the exact fallback command to run inside the container or app environment
- practical fallback for Laravel queued jobs when exec access is missing:
  - queue dispatch via Tinker: `php artisan tinker --execute="dispatch(new App\\Jobs\\FetchYouTubeAnalyticsJob)"`
  - sync execution via Tinker for immediate run: `php artisan tinker --execute="app(App\\Jobs\\FetchYouTubeAnalyticsJob::class)->handle(app(App\\Services\\AnalyticsDashboardService::class))"`
  - note the trade-off explicitly: dispatch requires the correct worker/queue to be alive, while direct `handle(...)` is the more brutal synchronous path
- secrecy rule from this debugging session:
  - websocket builder helpers may return bearer tokens inside generated URLs/query params; never paste those raw values into chat, docs, or skills
  - when documenting or quoting websocket URLs, redact the token and describe only the parameter shape

## Validation scope

Good enough initial validation:
- required path params
- required query params
- required request body presence
- basic scalar coercion (`string`, `integer`, `number`, `boolean`)
- object/array top-level body type checks

Don’t overbuild deep JSON-schema validation unless needed.

## Testing pattern

1. Syntax check
```bash
source venv/bin/activate
python -m py_compile path/to/server.py
```

2. Self-test
```bash
source venv/bin/activate
python path/to/server.py --self-test
```

3. Real MCP stdio smoke test using Python `mcp` client
- spawn the server with `StdioServerParameters`
- `initialize()`
- `list_tools()`
- call `get_api_info`
- call `list_operations`
- dry-run the thin helper tools for the hot path (for example deployment run + deployment status check)
- if token is available, do one live read-only status call too

This proves the server is actually a working MCP server, not just a Python script.

## Hermes config example

```yaml
mcp_servers:
  my_api:
    command: /abs/path/to/venv/bin/python
    args:
      - /abs/path/to/server.py
    env:
      API_BASE_URL: "https://example.com"
      OPENAPI_URL: "https://example.com/swagger.json"
      BEARER_TOKEN: "<token>"
    timeout: 120
    connect_timeout: 60
```

## Pitfalls

- Swagger 2 specs often have missing `operationId`; synthesize stable IDs.
- Don’t create 100+ MCP tools unless the API is small and stable.
- Keep auth centralized; don’t make callers manually pass Authorization unless the spec requires declared header params.
- Some `httpx` logging may print during self-test; acceptable unless stdout cleanliness matters for MCP mode.
- For MCP mode, keep normal output off stdout except protocol traffic.

## Output design

Return structured payloads with:
- request preview
- status code
- response headers subset
- parsed JSON if available
- raw text fallback
- auth status summary

This makes the tool actually usable by agents instead of jadi mesin lempar chaos.
