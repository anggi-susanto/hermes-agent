# Paperclip Board Provider Implementation Plan

> For Hermes: use subagent-driven-development to implement this plan task-by-task. Do not touch unrelated dirty files (`gateway/run.py`, `tests/gateway/test_telegram_documents.py`) while executing this plan.

Goal: ship the first real Hermes control-plane integration for Paperclip so Hermes can authenticate to a Paperclip company, sync issue-centric work state, link Hermes sessions to remote issues, and write execution evidence back to Paperclip without abusing the runtime-provider abstraction.

Architecture: add a new board-provider subsystem parallel to inference/runtime providers. Split concerns into four layers: board auth/config, normalized board domain models, provider adapters + sync engine, and user/agent entrypoints (CLI, slash commands, tools). Start with agent-key mode and issue-centric workflows only; keep operator-session auth and advanced governance as follow-up milestones.

Tech stack: Python, existing Hermes CLI/auth/config patterns, SQLite `state.db`, `httpx`, dataclasses/typing, existing tool registration patterns, and pytest.

Source design package: `docs/plans/2026-04-01-paperclip-board-provider-architecture.md`

Current state assessment:
- Hermes already has mature inference auth in `hermes_cli/auth.py` and runtime endpoint resolution in `hermes_cli/runtime_provider.py`.
- Hermes already persists session/message history in `hermes_state.py` with explicit schema versioning and WAL-safe writes.
- Slash commands are centrally declared in `hermes_cli/commands.py`.
- Secret redaction already exists in `agent/redact.py`.
- Tool env blocklist coverage is enforced in `tests/tools/test_local_env_blocklist.py`.
- There is no dedicated board/control-plane abstraction yet.
- Repo has unrelated dirty files right now: `gateway/run.py`, `tests/gateway/test_telegram_documents.py`. This plan must not modify or commit those.

Non-goals for first shippable milestone:
- No board-session/browser-cookie auth yet.
- No generic multi-provider board marketplace yet beyond a clean interface.
- No webhook consumer yet.
- No automatic issue selection/planning intelligence yet.
- No elevated approval decision writes unless the Paperclip agent key is explicitly authorized and validated.

---

## Mission

Turn Paperclip into a first-class Hermes control plane, not a fake runtime endpoint. The result should let Hermes:
1. authenticate separately from model providers,
2. pull Paperclip company/issue state into normalized local models,
3. link a Hermes session to a Paperclip issue,
4. update/comment/check out/release that issue safely,
5. persist sync state across restarts,
6. avoid silent overwrites when humans change remote data.

Success means a real agent-key-backed issue workflow works end-to-end with durable local mappings and tests.

---

## Staffing model

Recommended execution lanes:

1. Lane A — board foundation
   Owner: implementation agent
   Reviewer: spec-compliance reviewer
   Scope: auth/config/models/base interfaces
   Must not own: Paperclip transport details, CLI polish

2. Lane B — persistence + sync
   Owner: implementation agent
   Reviewer: code-quality reviewer
   Scope: `hermes_state.py` schema, repositories, sync event persistence
   Must not own: user-facing commands

3. Lane C — Paperclip adapter
   Owner: implementation agent
   Reviewer: API-contract reviewer
   Scope: `httpx` client, request/response normalization, issue ops
   Must not own: slash-command UX

4. Lane D — surfaces + tests
   Owner: implementation agent
   Reviewer: integration reviewer
   Scope: CLI commands, slash commands, tool entrypoints, test suite, docs
   Must not own: redesigning prior data model

Parallelization rule:
- Lane A must freeze the contracts first.
- Lane B may start once models + connection/auth contracts are stable.
- Lane C may start after Lane A defines the provider interface.
- Lane D should start after Lane A names the commands and after Lane C exposes adapter methods.

---

## Milestone coding map

### Milestone 0 — contract freeze and safety rails
Outcome:
- codebase touchpoints identified
- exact file/module names frozen
- execution constrained to avoid unrelated dirty files
Proof:
- plan doc committed
- implementation branch/task sequence agreed

### Milestone 1 — board auth/config foundation
Outcome:
- separate board auth store exists
- named board providers resolvable from config
- `paperclip` provider metadata registered
Proof:
- unit tests for auth store CRUD + resolution pass

### Milestone 2 — normalized models + persistence
Outcome:
- board dataclasses and state tables exist
- local↔remote links and sync events persist durably
Proof:
- migration tests and CRUD tests pass on fresh and upgraded DBs

### Milestone 3 — Paperclip issue workflow adapter
Outcome:
- validate credentials via Paperclip API
- list/fetch company snapshot
- issue create/update/comment/checkout/release works through adapter
Proof:
- adapter tests using mocked `httpx` responses pass

### Milestone 4 — Hermes surfaces
Outcome:
- CLI + slash commands exist for board login/status/pull/link/update
- agent-facing board tool can read/update linked issues
Proof:
- command parsing tests + tool tests pass

### Milestone 5 — first shippable end-to-end slice
Outcome:
- Hermes session can link to remote issue, persist mapping, write execution comment, and recover after restart
Proof:
- integration test or scripted smoke flow passes with mocked API
- optional live smoke against real Paperclip company if credentials available

### Milestone 6 — post-MVP hardening
Outcome:
- conflict policies enforced
- redaction/blocklist updated
- retries, pagination, and observability improved
Proof:
- negative-path tests added

---

## File-by-file implementation map

Create:
- `hermes_cli/board_auth.py`
- `hermes_cli/board_config.py`
- `integrations/boards/__init__.py`
- `integrations/boards/models.py`
- `integrations/boards/base.py`
- `integrations/boards/sync.py`
- `integrations/boards/paperclip.py`
- `tools/board_tool.py`
- `tests/hermes_cli/test_board_auth.py`
- `tests/hermes_cli/test_board_config.py`
- `tests/integrations/boards/test_models.py`
- `tests/integrations/boards/test_sync.py`
- `tests/integrations/boards/test_paperclip.py`
- `tests/tools/test_board_tool.py`
- `tests/cli/test_board_commands.py`
- `tests/state/test_board_state.py`

Modify:
- `hermes_state.py`
- `hermes_cli/main.py`
- `hermes_cli/commands.py`
- `agent/redact.py`
- `tests/tools/test_local_env_blocklist.py`
- potentially `tools/__init__` or the central tool registration module if required by current project layout
- docs/README files only after code lands

Do not modify as part of this project unless separately requested:
- `hermes_cli/runtime_provider.py` except maybe docs/comments referencing separation of concerns
- `gateway/run.py`
- `tests/gateway/test_telegram_documents.py`

---

## Task 1: Create the board auth/config contract docstrings and provider metadata

Objective: establish the new subsystem boundaries before any persistence or API code lands.

Files:
- Create: `hermes_cli/board_auth.py`
- Create: `hermes_cli/board_config.py`
- Test: `tests/hermes_cli/test_board_auth.py`
- Test: `tests/hermes_cli/test_board_config.py`

Step 1: Write failing tests for provider registry + auth/config separation

Example expectations:
```python
from hermes_cli.board_auth import BOARD_PROVIDER_REGISTRY, _board_auth_file_path
from hermes_cli.board_config import get_board_provider_config


def test_paperclip_provider_registered():
    provider = BOARD_PROVIDER_REGISTRY["paperclip"]
    assert provider.id == "paperclip"
    assert provider.api_base_url.endswith("/api")
    assert "PAPERCLIP_API_KEY" in provider.api_key_env_vars


def test_board_auth_store_is_separate_from_inference_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert _board_auth_file_path().name == "board_auth.json"
```

Step 2: Run tests to verify failure

Run:
`pytest tests/hermes_cli/test_board_auth.py tests/hermes_cli/test_board_config.py -v`

Expected:
- FAIL because modules/functions do not exist yet.

Step 3: Implement minimal `board_auth.py`

Required contents:
- `BoardProviderConfig` dataclass
- `BOARD_PROVIDER_REGISTRY`
- `_board_auth_file_path()`
- `_board_store_lock()` mirroring `auth.py` locking style
- `load_board_auth_store()` / `save_board_auth_store()`
- `get_board_auth_status(name_or_provider)`
- `set_active_board_provider(name)` / `deactivate_board_provider()`
- `save_board_provider_credentials(name, provider, auth_payload)`

Minimum shape:
```python
@dataclass(frozen=True)
class BoardProviderConfig:
    id: str
    name: str
    auth_type: str
    api_base_url: str = ""
    web_base_url: str = ""
    api_key_env_vars: tuple[str, ...] = ()
    supports_user_session: bool = False
    supports_agent_keys: bool = True
```

Step 4: Implement minimal `board_config.py`

Required contents:
- helpers to read `board:` config from `config.yaml`
- resolve named provider entries under `board.providers`
- merge provider defaults from registry + config overrides
- helper for default company ID and sync policy

Suggested API:
```python
def get_board_section(config: dict | None = None) -> dict: ...
def list_board_provider_configs(config: dict | None = None) -> list[dict]: ...
def get_board_provider_config(name: str, config: dict | None = None) -> dict | None: ...
def get_default_board_provider_name(config: dict | None = None) -> str | None: ...
```

Step 5: Re-run tests

Run:
`pytest tests/hermes_cli/test_board_auth.py tests/hermes_cli/test_board_config.py -v`

Expected:
- PASS

Step 6: Commit

```bash
git add hermes_cli/board_auth.py hermes_cli/board_config.py tests/hermes_cli/test_board_auth.py tests/hermes_cli/test_board_config.py
git commit -m "feat: add board auth and config foundation"
```

---

## Task 2: Add normalized board models

Objective: define canonical Hermes control-plane entities so Paperclip-specific payloads do not leak across the codebase.

Files:
- Create: `integrations/boards/models.py`
- Test: `tests/integrations/boards/test_models.py`

Step 1: Write failing model tests

Cover:
- `CompanyRef`
- `IssueRef`
- `ProjectRef`
- `GoalRef`
- `AgentRef`
- `ApprovalRef`
- `HeartbeatRunRef`
- `ActivityEventRef`
- `BoardConnection`
- `CompanySnapshot`
- `IssueStatus` mapping helpers

Example:
```python
from integrations.boards.models import IssueRef, map_remote_issue_status


def test_remote_issue_status_mapping():
    assert map_remote_issue_status("todo") == "pending"
    assert map_remote_issue_status("in_progress") == "in_progress"
    assert map_remote_issue_status("done") == "completed"
```

Step 2: Run tests to verify failure

Run:
`pytest tests/integrations/boards/test_models.py -v`

Expected:
- FAIL because file/module does not exist.

Step 3: Implement dataclasses and status mappers

Requirements:
- use explicit dataclasses or frozen dataclasses where appropriate
- keep raw payload field for debugging
- separate task status mapping and run status mapping
- include timestamp fields as optional normalized floats/strings, not provider-specific chaos

Suggested helper names:
```python
def map_remote_issue_status(value: str | None) -> str: ...
def map_remote_run_status(value: str | None) -> str: ...
```

Step 4: Re-run tests

Run:
`pytest tests/integrations/boards/test_models.py -v`

Expected:
- PASS

Step 5: Commit

```bash
git add integrations/boards/models.py tests/integrations/boards/test_models.py
git commit -m "feat: add normalized board domain models"
```

---

## Task 3: Define the provider interface

Objective: freeze the adapter contract so Paperclip implementation and higher-level sync code can proceed independently.

Files:
- Create: `integrations/boards/base.py`
- Test: `tests/integrations/boards/test_sync.py`

Step 1: Write a failing test that imports the protocol/base types

Example:
```python
from integrations.boards.base import BoardProvider


def test_board_provider_contract_has_issue_methods():
    required = {
        "validate_credentials",
        "fetch_company_snapshot",
        "list_issues",
        "get_issue",
        "create_issue",
        "update_issue",
        "checkout_issue",
        "release_issue",
        "add_issue_comment",
    }
    assert required.issubset(set(BoardProvider.__dict__.keys()))
```

Step 2: Run test to verify failure

Run:
`pytest tests/integrations/boards/test_sync.py -v`

Expected:
- FAIL

Step 3: Implement `BoardProvider` protocol and supporting request DTOs

Include:
- request dataclasses such as `CreateIssue`, `UpdateIssue`, `AddComment`, `CreateApproval`
- `BoardIdentity` / `RemoteItemRef` result types where needed
- docstrings defining expected semantics for conflict handling and raw payload preservation

Step 4: Re-run tests

Run:
`pytest tests/integrations/boards/test_sync.py -v`

Expected:
- PASS on import/contract coverage

Step 5: Commit

```bash
git add integrations/boards/base.py tests/integrations/boards/test_sync.py
git commit -m "feat: define board provider interface"
```

---

## Task 4: Add board tables to `hermes_state.py`

Objective: persist board connections, cached remote items, links, and sync events safely in the main SQLite state DB.

Files:
- Modify: `hermes_state.py`
- Test: `tests/state/test_board_state.py`

Step 1: Write failing migration tests

Cover these cases:
- fresh DB initializes with new tables
- schema upgrade from current schema version migrates cleanly
- insert/select helpers work
- unrelated session tables still function

Example:
```python
from hermes_state import SessionDB


def test_board_tables_exist(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    rows = db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {row[0] for row in rows}
    assert "board_connections" in names
    assert "board_links" in names
    assert "board_sync_events" in names
```

Step 2: Run tests to verify failure

Run:
`pytest tests/state/test_board_state.py -v`

Expected:
- FAIL because tables/helpers do not exist.

Step 3: Implement schema changes

Required edits in `hermes_state.py`:
- bump `SCHEMA_VERSION`
- extend schema creation/migration logic
- add tables:
  - `board_connections`
  - `board_items`
  - `board_links`
  - `board_sync_events`
- add indexes for `connection_id`, `remote_item_id`, `session_id`, `item_type`
- add CRUD helpers on `SessionDB`

Suggested helper APIs:
```python
def upsert_board_connection(...): ...
def upsert_board_item(...): ...
def link_session_to_board_item(...): ...
def list_board_links_for_session(session_id: str): ...
def record_board_sync_event(...): ...
def get_board_connection(connection_id: str): ...
```

Implementation rule:
- use the existing `_execute_write()` pattern for all writes.
- keep raw payloads JSON-serializable.

Step 4: Re-run tests

Run:
`pytest tests/state/test_board_state.py -v`

Expected:
- PASS

Step 5: Commit

```bash
git add hermes_state.py tests/state/test_board_state.py
git commit -m "feat: persist board sync state in sqlite"
```

---

## Task 5: Implement sync repository logic

Objective: centralize board cache/link reconciliation so CLI/tool surfaces do not write ad hoc SQL.

Files:
- Create: `integrations/boards/sync.py`
- Test: `tests/integrations/boards/test_sync.py`

Step 1: Expand tests to cover sync repository behavior

Test scenarios:
- store a company snapshot into cache
- upsert issue item without duplicating rows
- create session↔issue link
- record sync pull/push events
- detect remote update timestamp drift

Step 2: Run tests to verify failure

Run:
`pytest tests/integrations/boards/test_sync.py -v`

Expected:
- FAIL because repository functions do not exist.

Step 3: Implement sync helpers

Suggested API:
```python
class BoardSyncStore:
    def __init__(self, db: SessionDB): ...
    def cache_snapshot(self, connection_id: str, snapshot: CompanySnapshot) -> None: ...
    def link_session_issue(self, connection_id: str, session_id: str, issue_id: str) -> None: ...
    def record_pull(self, connection_id: str, cursor: str | None, detail: dict) -> None: ...
    def record_push(self, connection_id: str, operation: str, remote_item_id: str | None, detail: dict) -> None: ...
```

Keep logic narrow:
- no API calls here
- no CLI output here
- just normalized persistence + conflict metadata helpers

Step 4: Re-run tests

Run:
`pytest tests/integrations/boards/test_sync.py -v`

Expected:
- PASS

Step 5: Commit

```bash
git add integrations/boards/sync.py tests/integrations/boards/test_sync.py
git commit -m "feat: add board sync repository"
```

---

## Task 6: Implement Paperclip adapter authentication and company snapshot reads

Objective: get a real Paperclip provider implementation online for agent-key mode.

Files:
- Create: `integrations/boards/paperclip.py`
- Test: `tests/integrations/boards/test_paperclip.py`

Step 1: Write failing adapter tests for auth + snapshot reads

Mock `httpx` responses for:
- `GET /api/agents/me`
- company lookup/listing endpoint(s)
- issues/projects/goals/agents snapshot reads

Example:
```python
from integrations.boards.paperclip import PaperclipBoardProvider


def test_validate_credentials_uses_agents_me(httpx_mock, board_connection):
    httpx_mock.add_response(
        method="GET",
        url="https://paperclip.ing/api/agents/me",
        json={"id": "agent_123", "name": "Hermes"},
    )
    provider = PaperclipBoardProvider()
    identity = provider.validate_credentials(board_connection)
    assert identity.provider_user_id == "agent_123"
```

Step 2: Run tests to verify failure

Run:
`pytest tests/integrations/boards/test_paperclip.py -v`

Expected:
- FAIL

Step 3: Implement `PaperclipBoardProvider`

Required behavior:
- build base headers from stored/env API key
- validate with `GET /api/agents/me`
- support company snapshot fetch for at least:
  - companies
  - agents
  - issues
  - projects
  - goals
- normalize responses into `CompanySnapshot`
- preserve raw payload fragments for debugging

Implementation rules:
- use `httpx.Client`
- centralize request helper for headers, timeouts, error mapping
- do not hardcode secrets into payloads or logs
- keep pagination support pluggable even if first pass only handles a single page cleanly

Step 4: Re-run tests

Run:
`pytest tests/integrations/boards/test_paperclip.py -v`

Expected:
- PASS for auth + snapshot tests

Step 5: Commit

```bash
git add integrations/boards/paperclip.py tests/integrations/boards/test_paperclip.py
git commit -m "feat: add paperclip board provider reads"
```

---

## Task 7: Implement issue mutation methods in the Paperclip adapter

Objective: support the actual operational workflow: create, update, comment, checkout, release.

Files:
- Modify: `integrations/boards/paperclip.py`
- Test: `tests/integrations/boards/test_paperclip.py`

Step 1: Add failing tests for issue writes

Cover:
- create issue
- update issue status/title/body
- add comment
- checkout issue
- release issue
- 409 conflict maps to a domain-specific error/result

Example:
```python
def test_checkout_issue_maps_409_to_conflict(httpx_mock, provider, board_connection):
    httpx_mock.add_response(method="POST", url="https://paperclip.ing/api/issues/iss_1/checkout", status_code=409)
    with pytest.raises(BoardConflictError):
        provider.checkout_issue(board_connection, "iss_1")
```

Step 2: Run tests to verify failure

Run:
`pytest tests/integrations/boards/test_paperclip.py -v`

Expected:
- FAIL on missing mutation methods.

Step 3: Implement issue mutation methods

Required methods:
- `list_issues`
- `get_issue`
- `create_issue`
- `update_issue`
- `checkout_issue`
- `release_issue`
- `list_issue_comments`
- `add_issue_comment`

Design rules:
- use explicit DTO → JSON translation helpers
- keep status mapping centralized
- raise typed provider exceptions for auth, not-found, conflict, validation
- include `raw` payload on returned objects when safe

Step 4: Re-run tests

Run:
`pytest tests/integrations/boards/test_paperclip.py -v`

Expected:
- PASS

Step 5: Commit

```bash
git add integrations/boards/paperclip.py tests/integrations/boards/test_paperclip.py
git commit -m "feat: add paperclip issue workflow mutations"
```

---

## Task 8: Add board security coverage

Objective: make sure new board credentials cannot leak through local tool env passthrough or logs.

Files:
- Modify: `agent/redact.py`
- Modify: `tests/tools/test_local_env_blocklist.py`
- Add/Modify tests if needed under `tests/tools/`

Step 1: Write failing tests

Test expectations:
- `PAPERCLIP_API_KEY` is blocklisted
- `PAPERCLIP_BASE_URL` is blocklisted if treated as sensitive for subprocess leakage control
- bearer tokens in auth headers still redact
- env assignment `PAPERCLIP_API_KEY=...` redacts correctly

Step 2: Run tests to verify failure

Run:
`pytest tests/tools/test_local_env_blocklist.py tests/tools/test_env_passthrough.py -v`

Expected:
- FAIL due to missing blocklist coverage.

Step 3: Implement updates

Required changes:
- extend blocklist coverage to include board-provider auth vars
- extend redact env-name matching if current generic secret name regex misses `PAPERCLIP_API_KEY`
- ensure no raw board tokens appear in error strings or structured debug dumps

Step 4: Re-run tests

Run:
`pytest tests/tools/test_local_env_blocklist.py tests/tools/test_env_passthrough.py -v`

Expected:
- PASS

Step 5: Commit

```bash
git add agent/redact.py tests/tools/test_local_env_blocklist.py tests/tools/test_env_passthrough.py
git commit -m "fix: protect paperclip board credentials"
```

---

## Task 9: Add CLI board commands

Objective: expose the new subsystem through explicit CLI management commands.

Files:
- Modify: `hermes_cli/main.py`
- Test: `tests/cli/test_board_commands.py`

Step 1: Write failing parser/behavior tests

Cover commands:
- `hermes board status`
- `hermes board login --provider paperclip --name paperclip-prod --api-key-env PAPERCLIP_API_KEY --company-id ...`
- `hermes board select <name>`
- `hermes board pull`
- `hermes board link --session <id> --issue <id>`

If current CLI style prefers prompts instead of flags, encode that explicitly in tests.

Step 2: Run tests to verify failure

Run:
`pytest tests/cli/test_board_commands.py -v`

Expected:
- FAIL

Step 3: Implement CLI commands in `main.py`

Recommended subcommands:
- `board login`
- `board status`
- `board select`
- `board pull`
- `board checkout`
- `board release`
- `board link`
- `board unlink`

Implementation rules:
- keep parsing thin
- move operational logic into helper functions/modules where possible
- print concise operator-friendly status
- exit non-zero on conflicts/auth failures

Step 4: Re-run tests

Run:
`pytest tests/cli/test_board_commands.py -v`

Expected:
- PASS

Step 5: Commit

```bash
git add hermes_cli/main.py tests/cli/test_board_commands.py
git commit -m "feat: add board cli commands"
```

---

## Task 10: Add slash command registry entries

Objective: make board workflows available in interactive Hermes sessions and gateway command discovery.

Files:
- Modify: `hermes_cli/commands.py`
- Test: `tests/cli/test_board_commands.py`

Step 1: Write failing slash-command tests

Cover:
- `/board`
- `/board-sync`
- `/board-link`
- `/board-status`
- optional `/board-checkout` and `/board-release`

Example:
```python
from hermes_cli.commands import resolve_command


def test_board_commands_registered():
    assert resolve_command("/board") is not None
    assert resolve_command("/board-link") is not None
```

Step 2: Run tests to verify failure

Run:
`pytest tests/cli/test_board_commands.py -v`

Expected:
- FAIL

Step 3: Implement command registry entries

Recommended category:
- `Tools & Skills` or a new `Board` category if that improves help output

Step 4: Re-run tests

Run:
`pytest tests/cli/test_board_commands.py -v`

Expected:
- PASS

Step 5: Commit

```bash
git add hermes_cli/commands.py tests/cli/test_board_commands.py
git commit -m "feat: add slash commands for board workflows"
```

---

## Task 11: Add the agent-facing board tool

Objective: let Hermes itself read/update linked Paperclip work items through a dedicated tool surface.

Files:
- Create: `tools/board_tool.py`
- Modify: central tool registration module if required by current project structure
- Test: `tests/tools/test_board_tool.py`

Step 1: Write failing tool tests

Cover minimal operations:
- list issues
- get issue
- add comment
- update status
- sync
- link session

Suggested compressed tool signature:
```python
{
  "action": "status|pull|list_issues|get_issue|update_issue|add_comment|checkout|release|link_session",
  "connection": "paperclip-prod",
  "issue_id": "iss_123",
  "session_id": "sess_123",
  "patch": {"status": "in_progress"},
  "comment": "Started implementation"
}
```

Step 2: Run tests to verify failure

Run:
`pytest tests/tools/test_board_tool.py -v`

Expected:
- FAIL

Step 3: Implement tool handler + schema

Requirements:
- return normalized output plus raw provider identifiers where helpful
- refuse dangerous ambiguous writes when issue ID/connection missing
- integrate with `SessionDB` link helpers for `link_session`
- avoid network calls in tests by dependency injection/mocking

Step 4: Re-run tests

Run:
`pytest tests/tools/test_board_tool.py -v`

Expected:
- PASS

Step 5: Commit

```bash
git add tools/board_tool.py tests/tools/test_board_tool.py [tool-registration-file-if-changed]
git commit -m "feat: add board tool for paperclip workflows"
```

---

## Task 12: Implement first shippable linked-session workflow

Objective: prove the control-plane idea actually works in Hermes session semantics.

Files:
- Modify: `integrations/boards/sync.py`
- Modify: `tools/board_tool.py`
- Modify: `hermes_state.py` if additional helper needed
- Test: expand `tests/tools/test_board_tool.py` or add dedicated integration-style test

Step 1: Write a failing end-to-end mocked test

Scenario:
1. board connection configured
2. Paperclip issue exists
3. Hermes links current session to issue
4. Hermes writes execution comment
5. local DB stores mapping
6. after re-opening DB, mapping still resolves

Example assertion flow:
```python
def test_linked_session_can_write_execution_comment(...):
    ...
    assert result["linked_issue_id"] == "iss_123"
    assert persisted_link.remote_item_id == "iss_123"
```

Step 2: Run test to verify failure

Run:
`pytest tests/tools/test_board_tool.py -v -k linked_session`

Expected:
- FAIL

Step 3: Implement the minimal glue

Rules:
- prefer explicit session ID over implicit global state in tests
- append-only comment evidence by default
- do not auto-overwrite issue descriptions in MVP
- use checkout before mutating status/comment only if workflow flag requires it; keep policy explicit

Step 4: Re-run test

Run:
`pytest tests/tools/test_board_tool.py -v -k linked_session`

Expected:
- PASS

Step 5: Commit

```bash
git add integrations/boards/sync.py tools/board_tool.py hermes_state.py tests/tools/test_board_tool.py
git commit -m "feat: support linked paperclip issue session workflow"
```

---

## Task 13: Full targeted test run for MVP

Objective: verify the whole MVP slice without touching unrelated gateway failures.

Files:
- No new code unless failures force a targeted fix

Step 1: Run the targeted suite

Run:
`pytest tests/hermes_cli/test_board_auth.py tests/hermes_cli/test_board_config.py tests/integrations/boards/test_models.py tests/integrations/boards/test_sync.py tests/integrations/boards/test_paperclip.py tests/state/test_board_state.py tests/tools/test_board_tool.py tests/cli/test_board_commands.py tests/tools/test_local_env_blocklist.py tests/tools/test_env_passthrough.py -v`

Expected:
- PASS all new board-related tests

Step 2: If a failure occurs, fix the smallest relevant layer only

Rules:
- do not broaden scope
- do not "fix" unrelated dirty files
- add regression test before patch if bug is uncovered

Step 3: Re-run the suite

Same command as above.

Step 4: Commit if test-fix code was needed

```bash
git add [relevant files]
git commit -m "fix: stabilize paperclip board provider test suite"
```

---

## Task 14: Docs and operator usage examples

Objective: make the feature understandable after the code is stable.

Files:
- Modify: `README.md` or the most relevant docs page
- Optionally add: `docs/board-providers.md`

Step 1: Write doc assertions/tests only if current repo enforces them; otherwise proceed directly

Required content:
- what board providers are
- why Paperclip is not an inference/runtime provider
- required env vars / config shape
- sample `board:` config block
- example CLI commands
- known limitations for MVP

Example snippet:
```yaml
board:
  provider: paperclip-prod
  company_id: company_123
  providers:
    - name: paperclip-prod
      provider: paperclip
      api_base_url: https://paperclip.ing/api
      web_base_url: https://paperclip.ing
      company_id: company_123
```

Step 2: Verify docs mention security caveats

Must mention:
- agent-key mode first
- board-session mode not yet implemented
- approvals/governance writes may require elevated auth later

Step 3: Commit

```bash
git add README.md docs/board-providers.md
git commit -m "docs: add paperclip board provider usage"
```

---

## Acceptance proof requirements

MVP is only complete when all of these are true:
- `hermes board status` can resolve a Paperclip connection and report auth state
- Paperclip credentials are stored in `board_auth.json`, not `auth.json`
- `state.db` contains board tables and persists mappings across restart
- adapter validates credentials with `GET /api/agents/me`
- Hermes can pull a company snapshot into normalized models
- Hermes can create/update/comment on an issue via adapter methods
- Hermes can checkout and release an issue or clearly surface conflict
- Hermes can link a session to a remote issue
- linked session workflow can write append-only execution evidence comment
- blocklist/redaction tests cover `PAPERCLIP_API_KEY`
- no unrelated dirty files are accidentally committed

Optional live proof if credentials are available:
- run a real `hermes board pull` against a Paperclip company
- link a throwaway session to a throwaway issue
- post a comment: "Hermes board provider smoke test"
- verify the comment appears remotely

---

## Anti-bullshit section

What this plan knows confidently from current repo inspection:
- `hermes_state.py` already has explicit schema versioning and helper style worth extending.
- `hermes_cli/main.py` is the right entrypoint for adding `hermes board ...` commands.
- `hermes_cli/commands.py` is the right place for slash command registration.
- `agent/redact.py` and `tests/tools/test_local_env_blocklist.py` are mandatory security touchpoints.
- runtime-provider logic already exists and should remain separate.

What still needs live verification before claiming production-ready:
- exact Paperclip pagination and response shapes on all endpoints used in the adapter
- whether `issues/checkout` and `issues/release` exact routes match docs assumptions
- whether approvals endpoints are writable with agent keys or require elevated auth
- whether comments support structured metadata fields cleanly
- whether company snapshot endpoints are paginated or nested differently per deployment
- rate limits, retry headers, and long-poll/stream behavior

So jangan ngibul bilang “full Paperclip control complete” setelah MVP.
What MVP proves is: issue-centric operational control-plane integration in agent-key mode.

---

## Phase 2 backlog after MVP

Do only after MVP is stable:
1. board-session/elevated auth mode
2. approvals read/write with typed governance flows
3. heartbeat run + activity ingestion into sync cache
4. richer conflict policies (`remote_wins`, `warn`, `merge_append_only`)
5. auto-sync cursors and scheduled pull/push
6. subagent delegation directly from remote issues
7. webhook consumer or streaming updates
8. project/goal linking beyond issue-first workflows
9. richer CLI UX and doctor/status integration

---

## Recommended first execution order

If implementing right now, use this sequence:
1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7
8. Task 8
9. Task 9
10. Task 10
11. Task 11
12. Task 12
13. Task 13
14. Task 14

This order minimizes interface churn and lets Paperclip adapter work start only after the storage + model contracts are frozen.

---

## Handoff

Plan complete. Next sane move is to execute Milestone 1 first: board auth/config foundation.

If lu mau, next gw bisa langsung gas execute plan ini task-by-task, mulai dari:
- `board_auth.py`
- `board_config.py`
- tests-nya

dan gw bakal jagain biar gak nyenggol dirty files lain yang lagi nongkrong.