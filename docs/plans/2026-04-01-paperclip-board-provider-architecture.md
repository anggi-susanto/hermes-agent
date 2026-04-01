# Paperclip Board Provider Architecture Plan

> For Hermes: this is a design package for making Hermes control an external board system like Paperclip as a first-class control plane, not just as an installed runtime endpoint.

Goal: let Hermes treat Paperclip board state as an authoritative orchestration surface for planning, delegation, execution tracking, and evidence collection.

Architecture: add a new board-provider layer parallel to the existing model/runtime-provider layer. Keep inference-provider auth and model selection untouched; introduce a separate provider registry, persistence store, and sync engine dedicated to external workboards. Hermes remains the thinking/execution engine, while Paperclip becomes the source of truth for work decomposition, status, assignee semantics, and human-visible progress.

Tech stack: Python, existing Hermes config/auth patterns, SQLite state.db for durable sync metadata, YAML config for named providers, and provider-specific API clients (REST/WebSocket if Paperclip exposes both).

---

## 1. Why this is a different beast from installed runtime support

Today Hermes already has:
- inference provider registry in `hermes_cli/auth.py`
- runtime credential resolution in `hermes_cli/runtime_provider.py`
- durable auth store in `~/.hermes/auth.json`
- user-editable named endpoints in `custom_providers` via `hermes_cli/main.py`
- session/message persistence in `hermes_state.py`

That stack is about: "how Hermes talks to an LLM endpoint".

Paperclip board control is instead about:
- pulling board/project/task graph state
- mapping Hermes sessions/subagents to cards/issues/checklists
- pushing structured updates, status changes, comments, evidence, and artifacts
- preserving bidirectional identity mappings and sync cursors
- handling orchestration semantics like lane ownership, blockers, dependency ordering, and review loops

So kalau lu mau Hermes full control di Paperclip board, jangan dipaksa masuk ke `runtime_provider.py` doang. Itu bakal jadi desain sesat yang kelihatannya cepat tapi ujungnya semrawut.

The correct shape is: new board-provider subsystem.

---

## 2. What “full control” should mean

Hermes should be able to do all of this against Paperclip:

1. Discover and select a workspace/board/project
2. Read board structure: lanes, epics, tasks, owners, labels, status, dependencies
3. Create/update/archive items
4. Move items across lanes/status columns
5. Attach operational evidence:
   - commit hashes
   - PR links
   - deployment links
   - test results
   - verification notes
   - generated docs/plans
6. Spawn subagents from board items and write results back to the originating item
7. Keep a local durable mapping from Hermes concepts to Paperclip IDs
8. React to remote changes safely without stomping human edits
9. Offer a “board-native operating mode” where the active objective comes from a selected Paperclip card/epic instead of only the chat prompt

That’s why this should be modeled as a control-plane integration, not just another provider dropdown.

---

## 3. Proposed subsystem split

### 3.1 New concepts

Introduce three layers:

1. Board provider registry
   - defines known board backends like `paperclip`
   - similar spirit to `PROVIDER_REGISTRY`, but separate concerns

2. Board auth/config store
   - stores credentials and selected workspace/board defaults
   - should not piggyback on inference `active_provider`

3. Board sync state
   - stores remote IDs, local mappings, sync cursors, conflict metadata, and last successful pushes/pulls
   - belongs in SQLite, not only flat JSON

### 3.2 Recommended modules

New files:
- `hermes_cli/board_auth.py`
  - provider registry for boards
  - auth persistence helpers for board providers
  - active board provider selection
- `hermes_cli/board_config.py`
  - config helpers for named board providers and defaults
- `integrations/boards/base.py`
  - abstract `BoardProvider` interface
- `integrations/boards/paperclip.py`
  - Paperclip-specific implementation
- `integrations/boards/sync.py`
  - push/pull reconciliation logic
- `integrations/boards/models.py`
  - typed dataclasses for Board, Lane, Card, Comment, Attachment, SyncCursor
- `tools/board_tool.py`
  - user-facing tool(s) for reading/updating board state

Likely modified files:
- `hermes_state.py`
  - add board sync tables
- `hermes_cli/main.py`
  - add CLI setup and management commands
- `hermes_cli/commands.py`
  - add slash commands such as `/board`, `/board-link`, `/board-sync`
- `README.md` and docs
  - explain board mode vs inference provider mode

---

## 4. Provider model: keep it parallel, not overloaded

### 4.1 Existing anti-pattern to avoid

Do NOT do this:
- add `paperclip` into `PROVIDER_REGISTRY` in `hermes_cli/auth.py`
- force `resolve_runtime_provider()` to return board credentials
- store board workspace state under inference provider records

Why this sucks:
- mixes inference auth with workflow-system auth
- breaks auto-detection assumptions in `resolve_provider()`
- pollutes env-var blocklist logic meant for model providers
- makes “active provider” ambiguous: model provider or board provider?

### 4.2 Better model

Create a separate registry, e.g.:

```python
@dataclass
class BoardProviderConfig:
    id: str
    name: str
    auth_type: str  # api_key, oauth_device_code, oauth_web
    api_base_url: str = ""
    web_base_url: str = ""
    api_key_env_vars: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)
```

And then:

```python
BOARD_PROVIDER_REGISTRY = {
    "paperclip": BoardProviderConfig(
        id="paperclip",
        name="Paperclip",
        auth_type="api_key",  # or oauth if Paperclip supports it
        api_base_url="https://paperclip.ing/api",
        web_base_url="https://paperclip.ing",
        api_key_env_vars=("PAPERCLIP_API_KEY",),
    )
}
```

Separate active state:
- inference active provider stays in `auth.json.active_provider`
- board active provider becomes something like `board_auth.json.active_provider`

---

## 5. Persistence design

### 5.1 Config vs auth vs sync

Use three durability tiers:

1. `~/.hermes/config.yaml`
   - non-secret preferences
   - named board endpoints
   - defaults like workspace slug, board slug, auto-sync policy

2. `~/.hermes/board_auth.json`
   - secret-ish provider auth state
   - tokens, refresh tokens, active board provider
   - same locking pattern as `_auth_store_lock()` in `hermes_cli/auth.py`

3. `~/.hermes/state.db`
   - operational mappings and sync metadata
   - local↔remote IDs, sync cursors, last hashes, drift flags, timestamps

### 5.2 Why not shove everything into config.yaml?

Because lu bakal butuh:
- concurrency-safe updates
- incremental sync cursors
- structured many-to-many mappings
- queryable reconciliation state
- ability to answer “which Hermes session created this Paperclip task?” fast

YAML buat preferensi oke. Buat sync brain, jangan.

### 5.3 Suggested `config.yaml` section

```yaml
board:
  provider: paperclip
  workspace: my-team
  board: ceo
  sync:
    mode: manual
    pull_on_start: true
    push_on_task_update: true
    conflict_policy: warn
  providers:
    - name: paperclip-prod
      provider: paperclip
      api_base_url: https://paperclip.ing/api
      web_base_url: https://paperclip.ing
      workspace: my-team
      board: ceo
```

Keep secrets out of this file.

### 5.4 Suggested `board_auth.json`

```json
{
  "version": 1,
  "active_provider": "paperclip-prod",
  "providers": {
    "paperclip-prod": {
      "provider": "paperclip",
      "auth_type": "api_key",
      "api_key": "***",
      "workspace_id": "ws_123",
      "board_id": "board_456",
      "updated_at": "2026-04-01T13:00:00Z"
    }
  }
}
```

Use the same file-locking strategy already proven in `hermes_cli/auth.py`.

---

## 6. SQLite schema additions

Add new tables in `hermes_state.py` migrations.

### 6.1 `board_connections`
Stores named logical provider selections.

```sql
CREATE TABLE board_connections (
  id TEXT PRIMARY KEY,
  provider_key TEXT NOT NULL,
  provider_type TEXT NOT NULL,
  workspace_id TEXT,
  board_id TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  last_sync_at REAL,
  status TEXT
);
```

### 6.2 `board_items`
Local cache of remote board entities.

```sql
CREATE TABLE board_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  connection_id TEXT NOT NULL,
  remote_item_id TEXT NOT NULL,
  remote_parent_id TEXT,
  item_type TEXT NOT NULL,
  title TEXT,
  status TEXT,
  assignee TEXT,
  payload_json TEXT,
  remote_updated_at REAL,
  local_last_seen_at REAL NOT NULL,
  UNIQUE(connection_id, remote_item_id)
);
```

### 6.3 `board_links`
Maps Hermes entities to board entities.

```sql
CREATE TABLE board_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  connection_id TEXT NOT NULL,
  session_id TEXT,
  message_id INTEGER,
  local_entity_type TEXT NOT NULL,
  local_entity_id TEXT NOT NULL,
  remote_item_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
```

Examples:
- session → epic
- delegated subagent run → task
- commit-proof artifact → comment thread

### 6.4 `board_sync_events`
Audit trail and cursor progression.

```sql
CREATE TABLE board_sync_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  connection_id TEXT NOT NULL,
  direction TEXT NOT NULL,
  operation TEXT NOT NULL,
  remote_item_id TEXT,
  status TEXT NOT NULL,
  cursor TEXT,
  detail_json TEXT,
  created_at REAL NOT NULL
);
```

This gives you traceability when Paperclip sync gets weird. Which, because software is software, it will.

---

## 7. Core abstract interface

Define a provider contract so Paperclip is one implementation, not special spaghetti.

```python
class BoardProvider(Protocol):
    def validate_credentials(self, connection: BoardConnection) -> BoardIdentity: ...
    def list_workspaces(self, connection: BoardConnection) -> list[WorkspaceRef]: ...
    def list_boards(self, connection: BoardConnection, workspace_id: str) -> list[BoardRef]: ...
    def fetch_board_snapshot(self, connection: BoardConnection) -> BoardSnapshot: ...
    def create_item(self, connection: BoardConnection, item: CreateBoardItem) -> RemoteItemRef: ...
    def update_item(self, connection: BoardConnection, patch: UpdateBoardItem) -> RemoteItemRef: ...
    def move_item(self, connection: BoardConnection, move: MoveBoardItem) -> RemoteItemRef: ...
    def add_comment(self, connection: BoardConnection, comment: AddBoardComment) -> RemoteCommentRef: ...
    def add_attachment(self, connection: BoardConnection, attachment: AddBoardAttachment) -> RemoteAttachmentRef: ...
    def fetch_incremental_events(self, connection: BoardConnection, cursor: str | None) -> IncrementalBoardEvents: ...
```

This contract is what unlocks:
- future Notion/Linear/Trello/Jira support
- testability without real Paperclip API in unit tests
- separation between orchestration logic and transport details

---

## 8. Paperclip-specific operating model

Assuming Paperclip is a board/work delegation product, Hermes should treat it as:
- source of work definitions
- human review surface
- final evidence sink

### 8.1 Canonical local concepts

Hermes concepts to map:
- objective
- plan
- workstream/lane
- task
- subtask
- blocker
- review request
- proof artifact
- deployment artifact

Paperclip entities should map into these canonical local dataclasses first, then the rest of Hermes works against the normalized model.

That way lu nggak ngotori seluruh codebase dengan `paperclip_card`, `paperclip_lane`, `paperclip_whatever` everywhere.

### 8.2 Suggested status mapping layer

Paperclip board statuses may not match Hermes task lifecycle one-to-one.

Define explicit mappings, e.g.:

```python
REMOTE_TO_LOCAL_STATUS = {
    "backlog": "pending",
    "todo": "pending",
    "in_progress": "in_progress",
    "review": "review",
    "blocked": "blocked",
    "done": "completed",
    "cancelled": "cancelled",
}
```

And inverse mapping config per provider connection.

Do not hardcode one universal lane assumption.

---

## 9. Full-control workflows Hermes should support

### Workflow A: Board-driven execution
1. User links Hermes to a Paperclip board
2. Hermes syncs board snapshot
3. User says “gas objective A”
4. Hermes resolves that to a Paperclip epic/card
5. Hermes decomposes into internal todo/subagent tasks
6. Hermes writes subtask structure or comments back to Paperclip
7. Hermes updates status as work progresses
8. Hermes posts evidence when done

### Workflow B: Chat-created work pushed to board
1. User asks Hermes to plan a feature
2. Hermes writes plan locally
3. Hermes creates matching Paperclip epic + child tasks
4. Hermes stores mappings in `board_links`
5. Later updates route to the linked Paperclip items automatically

### Workflow C: Human edits remotely, Hermes reconciles
1. Human reprioritizes or reassigns cards in Paperclip
2. Hermes pull-sync sees remote changes
3. Hermes updates local cache and warns if an in-flight local assumption drifted
4. Hermes avoids overwriting unless conflict policy allows it

---

## 10. Conflict handling rules

This is where fake “full control” integrations die if not designed upfront.

### 10.1 You need field-level ownership

Suggested ownership defaults:
- remote-owned by human/board:
  - assignee
  - status when manually changed by reviewer
  - lane ordering
- local-owned by Hermes:
  - generated implementation notes
  - proof comments
  - execution metadata
  - subagent trace references
- shared/conflict-sensitive:
  - title
  - description/spec body
  - checklist completeness

### 10.2 Minimal safe conflict policy set

Implement per connection:
- `remote_wins`
- `local_wins`
- `warn`
- `merge_append_only`

Recommended default: `warn` for mutable text fields, `merge_append_only` for comments/evidence.

### 10.3 Never silently stomp these
- manually edited descriptions
- reviewer comments
- status moved backward for a reason
- reassignment by human operator

Hermes should annotate conflict, not cosplay god-mode and erase human input.

---

## 11. CLI and UX surface

### 11.1 New CLI commands

Add commands like:
- `hermes board login`
- `hermes board status`
- `hermes board select`
- `hermes board pull`
- `hermes board push`
- `hermes board link`
- `hermes board unlink`
- `hermes board mode on|off`

### 11.2 New slash commands

Add registry entries in `hermes_cli/commands.py` for:
- `/board`
- `/board-sync`
- `/board-link`
- `/board-status`

### 11.3 Board-native session mode

A nice future feature:
- session metadata includes an attached board item
- title generation can include board card title
- delegated subagents inherit the board context and write back to the same linked artifact set

---

## 12. Tool surface for the agent itself

Expose one or more tools, for example:

- `board_list_items`
- `board_get_item`
- `board_create_item`
- `board_update_item`
- `board_add_comment`
- `board_sync`
- `board_link_session`

Or a compressed tool if you want Hermes-style ergonomics.

Important: tool outputs should return both normalized fields and raw provider payload fragments for debugging.

---

## 13. Authentication pattern recommendation

If Paperclip only needs API key:
- store in `board_auth.json`
- optionally also allow env fallback `PAPERCLIP_API_KEY`
- validate immediately on login/select

If Paperclip supports OAuth:
- copy the same file-locking and refresh lifecycle pattern from `hermes_cli/auth.py`
- but do it in `board_auth.py`, not by bolting it into inference auth

Best practice:
- board auth store structure should mirror inference auth store ergonomics
- but remain physically separate so active states don’t collide

---

## 14. Security implications

Need to extend env sanitization and secret redaction to cover board creds.

### Required changes
1. Add board provider env vars to the subprocess blocklist logic tested in `tests/tools/test_local_env_blocklist.py`
2. Ensure secret redaction catches `PAPERCLIP_API_KEY` and any bearer tokens
3. Ensure board comments/attachments don’t accidentally dump secrets from local state or prompts
4. Avoid storing raw secret-bearing API responses in `payload_json`

If lu lupa bagian ini, nanti board integration jadi jalan bocor. Klasik banget.

---

## 15. Recommended implementation sequence

### Phase 1: foundation
1. Create `board_auth.py` with separate registry and JSON auth store
2. Add config schema for `board:` settings and named providers
3. Add `BoardProvider` base interface and normalized models
4. Add no-op/mock provider tests

### Phase 2: persistence
5. Add `state.db` schema migration for board tables
6. Add repository/helpers for board connections, items, links, and sync events
7. Add tests for migration and CRUD

### Phase 3: Paperclip adapter
8. Implement `integrations/boards/paperclip.py`
9. Add credential validation and snapshot pull
10. Add item create/update/move/comment support
11. Add incremental sync cursor support if API allows

### Phase 4: UX and tooling
12. Add `hermes board ...` CLI commands
13. Add slash commands in `hermes_cli/commands.py`
14. Add agent-facing board tools
15. Add docs and examples

### Phase 5: orchestration mode
16. Allow sessions to be linked to board items
17. Auto-write execution evidence to linked items
18. Support board-driven task spawning and subagent feedback loops

---

## 16. Proof requirements for “full control achieved”

Don’t call it done until all of these work on a real Paperclip workspace:

1. Hermes can authenticate and list workspaces/boards
2. Hermes can pull a board snapshot into normalized local models
3. Hermes can create a task/card from chat
4. Hermes can move that task across statuses
5. Hermes can attach a structured execution update comment
6. Hermes can map a local session to the remote task and persist the mapping
7. Hermes can survive restart and continue syncing with the same board state
8. Hermes can detect a human remote edit and avoid stomping it silently
9. Hermes can run at least one end-to-end board-driven workflow with evidence stored remotely

---

## 17. Honest feasibility read

Short answer: yes, very feasible.

But with one important caveat:
- feasible as a new board-provider/control-plane subsystem
- not feasible cleanly if treated as “just another installed runtime”

Installed runtime thinking assumes:
- Hermes sends prompt
- remote runtime executes
- maybe returns output

Board-control thinking assumes:
- Hermes continuously coordinates state across human and agent surfaces
- sync, mapping, conflict resolution, and auditability matter
- orchestration semantics become first-class product behavior

So the possibility is strong, but the shape has to be right from day one.

---

## 18. Concrete recommendation

If lu mau serious ngebedah ini buat Hermes:

Recommendation:
1. Do NOT implement Paperclip under `runtime_provider.py`
2. Introduce `board_auth.py` + `integrations/boards/*`
3. Store secrets in separate `board_auth.json`
4. Store sync/mapping state in `state.db`
5. Normalize Paperclip into canonical board/task abstractions
6. Add a board-native mode only after the core sync model is stable

In one kalimat:
Hermes should use Paperclip as an external orchestration control plane, not pretend Paperclip is merely another inference/runtime endpoint.

---

## 19. First shippable milestone

A good first milestone is not “full control”. Itu marketing dulu, engineering belakangan.

First shippable milestone:
- login/select Paperclip board
- pull snapshot
- create/update/move one task
- persist local↔remote mapping
- post execution evidence comment from a Hermes session

Once that is stable, baru gas ke:
- linked sessions
- board-driven subagent spawning
- automatic reconciliation
- human/agent co-control policies

---

## 20. Anti-bullshit notes

What this plan assumes but has not yet verified live:
- exact Paperclip API shape
- whether Paperclip exposes REST only or also webhooks/websocket streams
- whether comments, attachments, dependencies, and custom fields are supported
- whether auth is API-key or OAuth based
- exact status/lane model and whether ordering is explicit or implicit

So next real step should be: inspect actual Paperclip API/docs or traffic model, then adapt the adapter contract and schema details accordingly.
