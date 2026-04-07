---
name: hermes-board-provider-architecture
description: Design external board/control-plane integrations for Hermes (Paperclip, Linear, Jira, Trello, Notion) without confusing them with inference/runtime providers.
---

# Hermes Board Provider Architecture

Use this when the user wants Hermes to control an external workboard as a first-class orchestration surface, especially if they mention Paperclip, board mode, control plane, task sync, lane/status mapping, or "full control" over a board.

## Core rule

Do NOT model a board integration as just another runtime/inference provider.

If you shove a board system into:
- `hermes_cli/auth.py` inference `PROVIDER_REGISTRY`
- `hermes_cli/runtime_provider.py`
- inference `active_provider`

then you mix up:
- model auth
- workflow-system auth
- board sync state
- local↔remote task mappings
- human/agent conflict handling

That path is fast-looking but architecturally wrong.

## Correct mental model

Treat the external board as a separate control-plane subsystem.

Hermes remains:
- reasoning/execution engine
- verifier / source of truth for acceptance
- orchestrator of subagents and evidence

The external board becomes:
- visible planning/execution surface
- human review and assignment surface
- remote task/status/comment store

## Recommended subsystem split

Create a separate board-provider layer with three parts:

1. Board provider registry
- separate from inference provider registry
- e.g. `BOARD_PROVIDER_REGISTRY`

2. Board auth/config store
- separate active provider selection from inference auth
- use a separate file like `~/.hermes/board_auth.json`

3. Board sync state
- store mappings/cursors/conflict metadata in `state.db`
- not just YAML/JSON blobs

## Recommended files

New modules usually look like:
- `hermes_cli/board_auth.py`
- `hermes_cli/board_config.py`
- `integrations/boards/base.py`
- `integrations/boards/<provider>.py`
- `integrations/boards/sync.py`
- `integrations/boards/models.py`
- `tools/board_tool.py`

Implementation note from Paperclip milestone 2:
- in this repo, if you introduce `integrations/boards/...`, also create package markers so imports work cleanly under pytest:
  - `integrations/__init__.py`
  - `integrations/boards/__init__.py`
  - `tests/integrations/__init__.py`
  - `tests/integrations/boards/__init__.py`
- otherwise the first failing test may die at package import time before you learn anything useful about the real contract.
- on this environment, prefer `python3` in raw terminal commands; bare `python` may not exist outside uv-managed entrypoints.
- `uv run ...` may dirty `uv.lock`; if lock churn was incidental to testing and not part of the milestone, restore it before commit.
- In this repo, prefer `httpx.MockTransport` for board-provider adapter tests instead of assuming `pytest_httpx`/`respx` exists; current dev deps include `httpx` and `pytest`, but no dedicated HTTP mocking plugin.
- When committing milestone slices here, use explicit `git add <files...>` because the workspace may already contain unrelated dirty files (for example `gateway/run.py` or gateway test edits) that must stay untouched.

Likely edits:
- `hermes_state.py` for schema/migrations
- `hermes_cli/main.py` for CLI flows
- `hermes_cli/commands.py` for slash commands
- docs/README

## Persistence split

Use three durability layers:

### 1. `config.yaml`
For non-secret defaults:
- selected board provider name
- workspace/board defaults
- sync policy
- named board endpoints

### 2. `board_auth.json`
For secrets and provider auth state:
- API keys / OAuth tokens
- active board provider
- selected remote workspace/board IDs

Reuse the locking pattern from inference auth (`_auth_store_lock()` style), but keep board auth physically separate.

### 3. `state.db`
For operational state:
- connection rows
- cached remote items
- local↔remote links
- sync events/cursors
- conflict metadata / audit trail

## Minimum schema shape

Add tables along these lines:
- `board_connections`
- `board_items`
- `board_links`
- `board_sync_events`

You need these so Hermes can answer:
- which remote card is this session linked to?
- what changed since last sync?
- did a human edit this remotely?
- what evidence did Hermes already post?

## Abstract provider contract

Normalize providers behind a shared interface such as:
- validate credentials
- list top-level scopes (workspace/company/project root depending on provider)
- fetch control-plane snapshot
- create item
- update item
- move item or transition status
- add comment
- add attachment
- fetch incremental events

Do provider-specific translation at the adapter boundary, not across the whole codebase.

### Paperclip-specific findings

Paperclip is not a generic kanban-first API. The top-level scope is `company`, and the important first-class entities are:
- `companies`
- `agents`
- `issues`
- `projects`
- `goals`
- `approvals`
- `heartbeat-runs`
- `activity`

That means a Paperclip adapter should normalize around company/issue/approval/run semantics, not just workspace/board/card semantics.

Important Paperclip capabilities worth designing around:
- issue comments are first-class
- issue `checkout` / `release` exists and should be treated as a native coordination primitive
- approvals are first-class governance objects
- heartbeat runs, run logs, task sessions, and activity log make execution/audit observability part of the control plane
- auth is split between board-session auth for humans and bearer API keys for agents

Important Paperclip caveat:
- agent API keys likely provide strong operational control inside agent scope
- board-session auth is broader and may be required for board-member-only governance actions

So when the user says “full control”, explicitly separate:
- agent-scope operational control
- elevated board-member/operator control

## Repo vs runtime gap audit rule

When the user asks whether a provider "is already in Hermes" or whether there is a gap between runtime tools and repo code, do not answer from one surface only.

Audit these layers separately:

1. Board/provider integration code in repo
- check `integrations/boards/<provider>.py`
- check related tests under `tests/integrations/boards/`
- check board-auth wiring under `hermes_cli/board_auth.py` and sync/model modules

2. Native Hermes runtime tools
- check `tools/*.py`
- check whether anything registers a callable tool through `tools.registry`
- if it is not exposed from `tools/` and registry wiring, it is not a first-class Hermes tool

3. MCP runtime surface
- check `~/.hermes/config.yaml` under `mcp_servers:`
- if configured there, Hermes `mcp_tool.py` will usually expose callable tools named like `mcp_<server>_*`
- if no `mcp_servers.<provider>` entry exists, there is no native MCP tool surface for that provider even if repo code mentions it elsewhere

Paperclip-specific conclusion pattern:
- `integrations/boards/paperclip.py` means Paperclip exists as a board provider/control-plane adapter
- this does NOT mean there is an MCP Paperclip server
- this does NOT mean there is a first-class Hermes tool unless there is explicit tool wiring
- absence of `mcp_servers.paperclip` plus no `tools/*paperclip*` exposure means "Paperclip is in repo, but not as MCP/native runtime tool surface"

## Status/lane mapping rule

Never assume the board's native statuses equal Hermes lifecycle states.

Define explicit mapping layers, for example:
- remote `done` -> local `submitted_unverified`
- remote `in_review` -> local `review`
- remote `blocked` -> local `blocked`

Preserve Hermes verification authority. Remote completion is not automatic acceptance.

## Conflict-handling rule

Design field ownership early.

Typical defaults:
- remote/human-owned: assignee, lane ordering, reviewer-driven status
- Hermes-owned: generated evidence comments, execution metadata, agent trace links
- shared/conflict-sensitive: title, description, checklists

Supported policies should include:
- `remote_wins`
- `local_wins`
- `warn`
- `merge_append_only`

Recommended default: `warn` for mutable text, `merge_append_only` for comments/evidence.

## Security checklist

When adding a board provider:
- add board secrets to env blocklists used by subprocess environments
- ensure secret redaction catches provider keys/tokens
- do not store raw secret-bearing responses blindly in payload JSON
- be careful when echoing remote payloads in logs/comments/tools

Implementation note from Paperclip milestone 1:
- `tools/environments/local.py` currently builds `_HERMES_PROVIDER_ENV_BLOCKLIST` from inference `PROVIDER_REGISTRY`, not board providers.
- If you add `BOARD_PROVIDER_REGISTRY` in `hermes_cli/board_auth.py`, also extend `_build_provider_env_blocklist()` to import that registry and include each board provider's `api_key_env_vars`.
- Add an explicit regression test in `tests/tools/test_local_env_blocklist.py` for the new board secret (for Paperclip: `PAPERCLIP_API_KEY`).

## First shippable milestone

Do not promise “full control” first.

Ship this first:
1. login/select board
2. pull snapshot
3. create/update/move one task
4. persist local↔remote mapping
5. post execution evidence comment

Only then add:
- linked session mode
- board-driven subagent spawning
- automatic reconciliation
- richer human/agent co-control

## Review checklist when designing one

Before finishing the design, explicitly answer:
- Why is this not an inference/runtime provider?
- Where do secrets live?
- Where do mappings/cursors live?
- How does Hermes remain the acceptance authority?
- How are remote human edits protected from silent stomping?
- What is the first real milestone that proves the integration works?

## Good final recommendation pattern

State clearly:
- Hermes should use the board as an external orchestration control plane
- not pretend the board is merely another model/runtime endpoint
