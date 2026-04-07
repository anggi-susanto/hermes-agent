# Paperclip Board Provider Architecture Plan

> For Hermes: this is a design package for making Hermes control an external board system like Paperclip as a first-class control plane, not just as an installed runtime endpoint.

Goal: let Hermes treat Paperclip board state as an authoritative orchestration surface for planning, delegation, execution tracking, and evidence collection.

Architecture: add a new board-provider layer parallel to the existing model/runtime-provider layer. Keep inference-provider auth and model selection untouched; introduce a separate provider registry, persistence store, and sync engine dedicated to external workboards. Hermes remains the thinking/execution engine, while Paperclip becomes the source of truth for work decomposition, status, assignee semantics, and human-visible progress.

Tech stack: Python, existing Hermes config/auth patterns, SQLite state.db for durable sync metadata, YAML config for named providers, and provider-specific API clients (REST/WebSocket if Paperclip exposes both).

Paperclip API reality check from docs reviewed on 2026-04-01:
- API base path is `/api`
- local docs examples use `http://localhost:3100/api`
- authentication splits into board-session auth for humans and bearer API keys for agents
- top-level entity is `company`, not workspace/board/project as initially abstracted
- key orchestration resources exist already: `companies`, `agents`, `issues`, `projects`, `goals`, `approvals`, `heartbeat-runs`, and `activity`
- issue/task lifecycle, comments, checkout/release, active run lookup, runtime-state inspection, and approval governance are all first-class

This makes Paperclip even more suitable as a Hermes board/control plane than the initial abstract guess.

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

## 2. What “full control” should mean in actual Paperclip terms

From the docs, Hermes should be able to do all of this against Paperclip:

1. Discover and select a company
2. Read company structure:
   - agents
   - issues/tasks
   - projects
   - goals
   - approvals
   - heartbeat runs
   - activity log
3. Create/update/archive issues and related entities
4. Move issues across status values (`backlog`, `todo`, `in_progress`, `in_review`, `done`, `blocked`, `cancelled`)
5. Attach operational evidence via:
   - issue comments
   - activity events
   - heartbeat run logs/sessions linkage
6. Spawn Hermes subagents from issues and write results back to originating issues
7. Keep a local durable mapping from Hermes concepts to Paperclip IDs
8. React to remote changes safely without stomping human edits
9. Respect Paperclip governance surfaces:
   - approvals
   - board-member only actions
   - agent-scoped API permissions
10. Optionally drive or observe heartbeat execution as the runtime/monitoring truth

That’s why this should be modeled as a control-plane integration, not just another provider dropdown.

---

## 3. Revised Paperclip domain model from docs

The initial generic board abstraction needs one important correction:
- Paperclip is not “workspace -> board -> card” first
- Paperclip is closer to “company -> agents/issues/projects/goals/approvals/heartbeats/activity”

So Hermes should normalize Paperclip like this:

- Company → top-level org/workspace
- Issue → task/work item
- Project → grouping/container
- Goal → strategic objective
- Agent → worker/executor identity
- Approval → governance gate
- HeartbeatRun → execution cycle / run record
- ActivityEvent → audit/event stream

This is actually better for Hermes than a thin kanban API because execution and governance are already in the same platform.

---

## 4. Full feasibility read after docs check

Short answer: yes, lebih feasible dari dugaan awal.

Why:
- there is already a first-class issue/task API
- comments are first-class on issues and approvals
- approvals are explicit, not a hidden UI-only concept
- runtime execution is visible through heartbeat runs, run events, run logs, active run per issue, runtime state, and task sessions
- activity log provides an audit/event surface
- issue checkout/release creates a built-in reservation/lock-like workflow that Hermes can respect

This means Hermes does not merely control a passive board. It can integrate with:
- planning
- delegation
- execution state
- governance
- auditability

That is basically a real control plane.

---

## 5. Why this still should NOT be modeled as a runtime provider

Even though Paperclip contains runtime-ish concepts like:
- agents
- heartbeat runs
- runtime state
- task sessions

it still should not be jammed into `runtime_provider.py`.

Reason:
- `runtime_provider.py` is about finding credentials/base URLs for remote execution adapters
- Paperclip’s API surface is much broader: governance, task graph, approvals, activity, comments, assignment, checkout, and logs
- if you place it under runtime-provider logic, the task/control semantics get trapped under the wrong abstraction boundary

Better split:
- existing runtime adapters continue to represent “how an agent process executes”
- new Paperclip board provider represents “where orchestration truth lives”
- optional future bridge: a Hermes runtime adapter may report execution into a linked Paperclip provider connection

So Paperclip is a control-plane provider, maybe with runtime-observability features, not a mere runtime endpoint.

---

## 6. Proposed subsystem split

### 6.1 New concepts

Introduce three layers:

1. Board/control-plane provider registry
   - defines known control-plane backends like `paperclip`
   - similar spirit to `PROVIDER_REGISTRY`, but separate concerns

2. Board auth/config store
   - stores credentials and selected company defaults
   - should not piggyback on inference `active_provider`

3. Board sync state
   - stores remote IDs, local mappings, sync cursors, conflict metadata, and last successful pushes/pulls
   - belongs in SQLite, not only flat JSON

### 6.2 Recommended modules

New files:
- `hermes_cli/board_auth.py`
  - provider registry for boards/control planes
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
  - typed dataclasses for Company, Issue, Project, Goal, Agent, Approval, HeartbeatRun, ActivityEvent, SyncCursor
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

## 7. Provider model: keep it parallel, not overloaded

### 7.1 Existing anti-pattern to avoid

Do NOT do this:
- add `paperclip` into `PROVIDER_REGISTRY` in `hermes_cli/auth.py`
- force `resolve_runtime_provider()` to return Paperclip credentials
- store company/session state under inference provider records

Why this sucks:
- mixes inference auth with workflow-system auth
- breaks auto-detection assumptions in `resolve_provider()`
- pollutes env-var blocklist logic meant for model providers
- makes “active provider” ambiguous: model provider or board provider?

### 7.2 Better model

Create a separate registry, e.g.:

```python
@dataclass
class BoardProviderConfig:
    id: str
    name: str
    auth_type: str  # api_key, oauth_device_code, oauth_web, session_cookie
    api_base_url: str = ""
    web_base_url: str = ""
    api_key_env_vars: tuple[str, ...] = ()
    supports_user_session: bool = False
    supports_agent_keys: bool = True
    extra: dict[str, Any] = field(default_factory=dict)
```

And then:

```python
BOARD_PROVIDER_REGISTRY = {
    "paperclip": BoardProviderConfig(
        id="paperclip",
        name="Paperclip",
        auth_type="api_key",
        api_base_url="https://paperclip.ing/api",
        web_base_url="https://paperclip.ing",
        api_key_env_vars=("PAPERCLIP_API_KEY",),
        supports_user_session=True,
        supports_agent_keys=True,
    )
}
```

Separate active state:
- inference active provider stays in `auth.json.active_provider`
- board active provider becomes something like `board_auth.json.active_provider`

---

## 8. Persistence design

### 8.1 Config vs auth vs sync

Use three durability tiers:

1. `~/.hermes/config.yaml`
   - non-secret preferences
   - named Paperclip endpoints
   - defaults like company ID, company slug if available, sync policy

2. `~/.hermes/board_auth.json`
   - secret-ish provider auth state
   - agent API keys, optional session-cookie metadata, active board provider
   - same locking pattern as `_auth_store_lock()` in `hermes_cli/auth.py`

3. `~/.hermes/state.db`
   - operational mappings and sync metadata
   - local↔remote IDs, sync cursors, last hashes, drift flags, timestamps

### 8.2 Why not shove everything into config.yaml?

Because lu bakal butuh:
- concurrency-safe updates
- incremental sync cursors
- structured many-to-many mappings
- queryable reconciliation state
- ability to answer “which Hermes session created this Paperclip issue?” fast

YAML buat preferensi oke. Buat sync brain, jangan.

### 8.3 Suggested `config.yaml` section

```yaml
board:
  provider: paperclip-prod
  company_id: company_xyz
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
      company_id: company_xyz
```

Keep secrets out of this file.

### 8.4 Suggested `board_auth.json`

```json
{
  "version": 1,
  "active_provider": "paperclip-prod",
  "providers": {
    "paperclip-prod": {
      "provider": "paperclip",
      "auth_type": "api_key",
      "api_key": "***",
      "company_id": "company_xyz",
      "updated_at": "2026-04-01T13:00:00Z"
    }
  }
}
```

Use the same file-locking strategy already proven in `hermes_cli/auth.py`.

---

## 9. SQLite schema additions

Add new tables in `hermes_state.py` migrations.

### 9.1 `board_connections`
Stores named logical provider selections.

```sql
CREATE TABLE board_connections (
  id TEXT PRIMARY KEY,
  provider_key TEXT NOT NULL,
  provider_type TEXT NOT NULL,
  company_id TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  last_sync_at REAL,
  status TEXT
);
```

### 9.2 `board_items`
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

`item_type` should include at least:
- `company`
- `agent`
- `issue`
- `project`
- `goal`
- `approval`
- `heartbeat_run`
- `activity_event`

### 9.3 `board_links`
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
- session → issue
- delegated subagent run → issue
- plan document → goal
- approval request → governance checkpoint
- runtime run → heartbeat_run

### 9.4 `board_sync_events`
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

This gives traceability when Paperclip sync gets weird. Which, because software is software, it will.

---

## 10. Core abstract interface

Define a provider contract so Paperclip is one implementation, not special spaghetti.

```python
class BoardProvider(Protocol):
    def validate_credentials(self, connection: BoardConnection) -> BoardIdentity: ...
    def list_companies(self, connection: BoardConnection) -> list[CompanyRef]: ...
    def get_company(self, connection: BoardConnection, company_id: str) -> CompanyRef: ...
    def fetch_company_snapshot(self, connection: BoardConnection) -> CompanySnapshot: ...

    def list_agents(self, connection: BoardConnection, company_id: str) -> list[AgentRef]: ...
    def get_agent(self, connection: BoardConnection, agent_id: str) -> AgentRef: ...

    def list_issues(self, connection: BoardConnection, company_id: str, **filters) -> list[IssueRef]: ...
    def get_issue(self, connection: BoardConnection, issue_id: str) -> IssueRef: ...
    def create_issue(self, connection: BoardConnection, issue: CreateIssue) -> RemoteItemRef: ...
    def update_issue(self, connection: BoardConnection, patch: UpdateIssue) -> RemoteItemRef: ...
    def checkout_issue(self, connection: BoardConnection, issue_id: str) -> RemoteItemRef: ...
    def release_issue(self, connection: BoardConnection, issue_id: str) -> RemoteItemRef: ...
    def list_issue_comments(self, connection: BoardConnection, issue_id: str) -> list[CommentRef]: ...
    def add_issue_comment(self, connection: BoardConnection, issue_id: str, comment: AddComment) -> RemoteCommentRef: ...

    def list_projects(self, connection: BoardConnection, company_id: str) -> list[ProjectRef]: ...
    def list_goals(self, connection: BoardConnection, company_id: str) -> list[GoalRef]: ...

    def list_approvals(self, connection: BoardConnection, company_id: str, **filters) -> list[ApprovalRef]: ...
    def create_approval(self, connection: BoardConnection, approval: CreateApproval) -> ApprovalRef: ...

    def list_heartbeat_runs(self, connection: BoardConnection, company_id: str, **filters) -> list[HeartbeatRunRef]: ...
    def get_live_runs(self, connection: BoardConnection, company_id: str) -> list[HeartbeatRunRef]: ...
    def get_run_logs(self, connection: BoardConnection, run_id: str) -> RunLogs: ...
    def get_task_sessions(self, connection: BoardConnection, issue_id: str) -> TaskSessions: ...
    def get_active_run_for_issue(self, connection: BoardConnection, issue_id: str) -> HeartbeatRunRef | None: ...

    def list_activity(self, connection: BoardConnection, company_id: str, **filters) -> list[ActivityEventRef]: ...
```

This contract is what unlocks:
- future Notion/Linear/Trello/Jira support through a normalized control-plane abstraction
- testability without live Paperclip API in unit tests
- separation between orchestration logic and transport details

---

## 11. Paperclip-specific operating model

Paperclip should be treated as:
- source of work definitions
- human governance/review surface
- execution observability surface
- final evidence sink

### 11.1 Canonical local concepts

Hermes concepts to map:
- objective
- plan
- workstream
- task
- subtask
- blocker
- review request
- proof artifact
- deployment artifact
- execution run
- governance approval

Paperclip entities should map into these canonical local dataclasses first, then the rest of Hermes works against the normalized model.

That way lu nggak ngotori seluruh codebase dengan `paperclip_issue`, `paperclip_run`, `paperclip_approval` in every corner.

### 11.2 Suggested status mapping layer

Paperclip issue statuses map pretty well already:

```python
REMOTE_TO_LOCAL_STATUS = {
    "backlog": "pending",
    "todo": "pending",
    "in_progress": "in_progress",
    "in_review": "review",
    "blocked": "blocked",
    "done": "completed",
    "cancelled": "cancelled",
}
```

And heartbeat run statuses map separately:

```python
REMOTE_RUN_TO_LOCAL = {
    "queued": "queued",
    "running": "running",
    "succeeded": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
    "timed_out": "timed_out",
}
```

Do not collapse task-state and execution-run-state into one enum. Itu beda domain.

---

## 12. Full-control workflows Hermes should support

### Workflow A: Company-driven execution from issue queue
1. User links Hermes to a Paperclip company
2. Hermes syncs company snapshot
3. Hermes picks or is given an issue
4. Hermes optionally checks out the issue to reserve work
5. Hermes decomposes into internal todo/subagent tasks
6. Hermes writes updates/comments back to the issue
7. Hermes updates status as work progresses
8. Hermes posts evidence when done

### Workflow B: Chat-created work pushed to Paperclip
1. User asks Hermes to plan a feature
2. Hermes writes plan locally
3. Hermes creates matching Paperclip issue/project/goal as needed
4. Hermes stores mappings in `board_links`
5. Later updates route to the linked Paperclip items automatically

### Workflow C: Human edits remotely, Hermes reconciles
1. Human reprioritizes, reassigns, or edits issues in Paperclip
2. Hermes pull-sync sees remote changes
3. Hermes updates local cache and warns if an in-flight local assumption drifted
4. Hermes avoids overwriting unless conflict policy allows it

### Workflow D: Governance-aware orchestration
1. Hermes wants to propose a sensitive change
2. Hermes creates an approval request if required
3. Hermes waits/polls approval status
4. Hermes proceeds only when approved, or revises when revision requested

### Workflow E: Execution observability bridge
1. Hermes starts internal execution/subagent flow
2. Hermes maps execution to an issue and optionally to a heartbeat/run record
3. Hermes writes logs/evidence and can read active run/log state from Paperclip
4. Hermes uses activity log for audit stitching

---

## 13. Conflict handling rules

This is where fake “full control” integrations die if not designed upfront.

### 13.1 You need field-level ownership

Suggested ownership defaults:
- remote-owned by human/control plane:
  - assignee
  - approval decisions
  - issue status when manually changed by reviewer
  - company-level settings
- local-owned by Hermes:
  - generated implementation notes
  - proof comments
  - execution metadata
  - subagent trace references
- shared/conflict-sensitive:
  - title
  - description/spec body
  - issue status during active execution
  - project/goal linkage

### 13.2 Minimal safe conflict policy set

Implement per connection:
- `remote_wins`
- `local_wins`
- `warn`
- `merge_append_only`

Recommended default:
- `warn` for mutable text fields
- `merge_append_only` for comments/evidence/activity notes
- explicit reserve/checkout before in-place work mutation when possible

### 13.3 Never silently stomp these
- manually edited descriptions
- reviewer comments
- approval decisions
- reassignment by human operator
- status moved backward for a reason

Hermes should annotate conflict, not cosplay god-mode and erase human input.

### 13.4 Use checkout/release as soft locking

The docs show issue checkout/release and 409 conflict handling.
That’s gold.

Hermes should use:
- checkout before active work on an issue when running agent mode
- release on handoff/cancel/failure
- conflict-aware retries if issue is already checked out elsewhere

This gives a native coordination primitive instead of inventing fake local locks.

---

## 14. CLI and UX surface

### 14.1 New CLI commands

Add commands like:
- `hermes board login`
- `hermes board status`
- `hermes board select`
- `hermes board pull`
- `hermes board push`
- `hermes board link`
- `hermes board unlink`
- `hermes board mode on|off`
- `hermes board checkout`
- `hermes board release`

### 14.2 New slash commands

Add registry entries in `hermes_cli/commands.py` for:
- `/board`
- `/board-sync`
- `/board-link`
- `/board-status`
- `/board-checkout`
- `/board-release`

### 14.3 Board-native session mode

A nice future feature:
- session metadata includes an attached Paperclip issue/goal/project
- title generation can include issue identifier/title
- delegated subagents inherit the Paperclip context and write back to the same linked artifact set

---

## 15. Tool surface for the agent itself

Expose one or more tools, for example:
- `board_list_companies`
- `board_get_company`
- `board_list_issues`
- `board_get_issue`
- `board_create_issue`
- `board_update_issue`
- `board_checkout_issue`
- `board_release_issue`
- `board_add_comment`
- `board_list_approvals`
- `board_create_approval`
- `board_list_runs`
- `board_get_run_logs`
- `board_sync`
- `board_link_session`

Or a compressed tool if you want Hermes-style ergonomics.

Important: tool outputs should return both normalized fields and raw provider payload fragments for debugging.

---

## 16. Authentication pattern recommendation

Paperclip docs clearly separate two auth modes:
- board session auth for human operators
- bearer API keys for agents

For Hermes integration, start with agent API keys.

Why:
- stable server-to-server pattern
- explicit Authorization header
- less browser/session coupling
- aligns with autonomous Hermes control-plane worker mode

### 16.1 Recommended phase-1 auth support

Phase 1:
- support `PAPERCLIP_API_KEY`
- store agent key in `board_auth.json`
- require explicit `company_id`
- validate immediately with something like `GET /api/agents/me`

Phase 2 optional:
- support imported board session cookie for operator-superuser workflows
- only if really needed for board-member-only endpoints

### 16.2 Important limitation from docs

Agent keys are scoped.
Docs explicitly say agents can do things like:
- read org/task/company context
- read/write their own assigned tasks and comments
- create tasks/comments for delegation
- report heartbeats and cost events

But board-member-only operations exist too, including:
- company management
- approval decisions
- budget management
- certain governance actions

So “full control” depends on which auth mode Hermes uses:
- agent-key mode = full operational control within agent scope, but not total board-member superpowers
- board-session mode = broader superuser control, but harder and more security-sensitive

This means Hermes may need two roles:
1. Hermes-as-agent (default, safe)
2. Hermes-as-board-operator (optional elevated mode)

---

## 17. Security implications

Need to extend env sanitization and secret redaction to cover board creds.

### Required changes
1. Add board provider env vars to the subprocess blocklist logic tested in `tests/tools/test_local_env_blocklist.py`
2. Ensure secret redaction catches `PAPERCLIP_API_KEY` and any bearer/session tokens
3. Ensure board comments/attachments don’t accidentally dump secrets from local state or prompts
4. Avoid storing raw secret-bearing API responses in `payload_json`

If lu lupa bagian ini, nanti board integration jadi jalan bocor. Klasik banget.

---

## 18. Recommended implementation sequence

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
9. Add credential validation with `GET /api/agents/me`
10. Add company snapshot pull (`companies`, `agents`, `issues`, `projects`, `goals`)
11. Add issue create/update/comment support
12. Add issue checkout/release support
13. Add approvals read/create support where auth allows
14. Add heartbeat/activity read support for observability and evidence stitching

### Phase 4: UX and tooling
15. Add `hermes board ...` CLI commands
16. Add slash commands in `hermes_cli/commands.py`
17. Add agent-facing board tools
18. Add docs and examples

### Phase 5: orchestration mode
19. Allow sessions to be linked to Paperclip issues/goals/projects
20. Auto-write execution evidence to linked issues
21. Support issue-driven task spawning and subagent feedback loops
22. Add governance-aware approval gating where needed

---

## 19. Proof requirements for “full control achieved”

Don’t call it done until all of these work on a real Paperclip company:

1. Hermes can authenticate and identify itself via `GET /api/agents/me`
2. Hermes can list/select a company
3. Hermes can pull a company snapshot into normalized local models
4. Hermes can create an issue from chat
5. Hermes can update issue status and metadata
6. Hermes can add a structured execution update comment
7. Hermes can checkout and release an issue safely
8. Hermes can map a local session to the remote issue and persist the mapping
9. Hermes can survive restart and continue syncing with the same Paperclip state
10. Hermes can detect a human remote edit and avoid stomping it silently
11. Hermes can inspect run/activity evidence tied to work
12. Hermes can run at least one end-to-end issue-driven workflow with evidence stored remotely

For true board-operator supercontrol, add:
13. Hermes can interact with approvals in the intended governance path
14. Hermes can safely separate agent-scope actions from board-member-only actions

---

## 20. Honest feasibility conclusion after doc review

Short answer: yes, this is real and strong.

Actually stronger than the original abstract idea because Paperclip already exposes:
- tasks/issues
- subtasks via `parentId`
- projects
- goals
- comments
- approvals
- activity log
- heartbeat runs
- task sessions
- runtime state
- issue checkout/release semantics

That means Paperclip is not just a visual board.
It is already a combined:
- org model
- work graph
- execution monitor
- governance layer
- audit trail

So yes, Hermes controlling Paperclip as a board/control plane is not only possible — it’s architecturally very aligned.

The only caveat:
- don’t confuse “full operational control under agent key” with “full board-member control under session auth”

That’s the one place where the word “full” can become marketing goblin nonsense if not defined precisely.

---

## 21. Concrete recommendation

If lu mau serious ngebedah ini buat Hermes:

Recommendation:
1. Do NOT implement Paperclip under `runtime_provider.py`
2. Introduce `board_auth.py` + `integrations/boards/*`
3. Store secrets in separate `board_auth.json`
4. Store sync/mapping state in `state.db`
5. Normalize Paperclip into canonical company/issue/approval/run abstractions
6. Start with agent-key mode
7. Add optional elevated board-session mode only for operations that truly need operator authority
8. Treat checkout/release as native coordination primitive
9. Treat heartbeat/activity as observability/evidence channels, not just debug fluff

In one kalimat:
Hermes should use Paperclip as an external orchestration control plane with native execution/governance hooks, not pretend Paperclip is merely another inference/runtime endpoint.

---

## 22. First shippable milestone

A good first milestone is not “full control”. Itu marketing dulu, engineering belakangan.

First shippable milestone:
- login/select Paperclip company via agent key
- validate with `/api/agents/me`
- pull company + issues snapshot
- create/update/comment on one issue
- checkout/release issue
- persist local↔remote mapping
- post execution evidence comment from a Hermes session
- read heartbeat/activity context for that issue when available

Once that is stable, baru gas ke:
- linked sessions
- issue-driven subagent spawning
- automatic reconciliation
- approval-aware orchestration
- elevated board-session mode

---

## 23. Anti-bullshit notes

What this revised plan now knows from docs:
- exact base path: `/api`
- auth modes: board session vs agent API key
- top-level scope: company
- issue status model exists and is explicit
- approvals are first-class
- heartbeats and runtime inspection are first-class
- activity log is first-class
- issue checkout/release and conflict handling exist

What still needs live verification:
- exact request/response bodies for every endpoint we’ll use in production
- whether auth/session endpoints are exposed for non-browser clients
- whether comments support structured metadata cleanly
- whether webhooks or streaming APIs exist beyond polling
- rate limits and pagination behavior under load
- any hidden permission caveats around agent keys vs board sessions

So next real step should be:
- inspect actual endpoint schemas in more depth or hit a live Paperclip instance
- then turn this into file-by-file implementation work.
