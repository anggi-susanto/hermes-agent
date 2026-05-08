# Oh My OpenAgent-Inspired Hermes Upgrade Roadmap

> **For Hermes:** Use this roadmap together with `docs/plans/2026-05-08-oh-my-openagent-inspired-hermes-tracker.md`. Use subagent-driven-development or Kanban-backed execution for implementation. Preserve scope boundaries: this is a Hermes-native roadmap inspired by `code-yeongyu/oh-my-openagent`, not a clone of OpenCode plugin internals.

**Goal:** Turn the best harness ideas from `oh-my-openagent` into Hermes-native coding, orchestration, and safety upgrades without duplicating systems Hermes already has.

**Architecture:** Prefer small, composable Hermes primitives: new toolsets for code intelligence, narrow file-tool improvements for safer edits, category presets over hard-coded agent personas, and Kanban/delegation extensions instead of a second coordination backend. Keep prompt caching, profile-safe paths, config/env separation, and gateway/CLI parity intact.

**Tech Stack:** Hermes Python runtime, `tools/registry.py`, `toolsets.py`, `tools/file_tools.py`, `tools/file_operations.py`, `tools/delegate_tool.py`, `tools/terminal_tool.py`, `hermes_cli/config.py`, `hermes_cli/commands.py`, `cli.py`, `run_agent.py`, `agent/*`, `plugins/kanban`, `cron`, `acp_adapter`, pytest, optional external CLIs (`ast-grep`, language servers, tmux).

**Source inspiration audited:** `https://github.com/code-yeongyu/oh-my-openagent` at commit `c7d6a4a2ce55237c7547e5a091a9a1446ae6d2c9`.

**Roadmap date:** 2026-05-08

---

## Mission

Hermes should absorb the useful product lessons from `oh-my-openagent` while staying Hermes: multi-platform, provider-agnostic, skill/memory-driven, and durable across CLI, Telegram, ACP, cron, and future control planes.

The win condition is not “make Hermes look like OmO.” The win condition is:

1. safer code edits,
2. more IDE-grade code intelligence,
3. easier multi-agent orchestration,
4. durable background work that can notify users,
5. better project initialization/context hygiene,
6. and clearer high-intensity modes for “just get it done” work.

---

## Current Hermes Baseline

Hermes already has several primitives that overlap with or exceed OmO:

- **Tool registry and toolsets:** `tools/registry.py`, `toolsets.py`.
- **File tools:** `read_file`, `write_file`, `search_files`, `patch`; patch already uses fuzzy matching and syntax checks.
- **Subagent delegation:** `tools/delegate_tool.py`, synchronous `delegate_task`, batch parallel children, role-based nested delegation, active subagent registry.
- **Durable scheduling:** `cron` jobs with delivery, workdir, script, model override, context chaining.
- **Kanban multi-agent queue:** durable SQLite board, dispatcher, worker toolset, comments, links, task states.
- **Skills:** bundled and external skill dirs, skill manager, curator, inline shell template support, platform configuration.
- **Session search:** existing `session_search` tool and SQLite FTS session store.
- **Gateway:** Telegram/Discord/Slack/etc. surfaces, not just terminal.
- **ACP adapter:** editor integration surface already exists.
- **Goals:** `/goal` continuation loop already covers part of OmO’s Ralph/ultrawork loop concept.

The roadmap should therefore prefer *extension and unification* over duplicate subsystems.

---

## Non-Goals

- Do not port OpenCode-specific plugin hooks directly.
- Do not create a second task board when Hermes Kanban can serve as the durable coordination layer.
- Do not change tool schemas mid-session; preserve prompt caching semantics.
- Do not require OmO, OpenCode, Claude Code, or a specific model provider for Hermes features.
- Do not silently add large context blocks globally; keep new features opt-in or task-scoped.
- Do not make gateway-only features that cannot also work from CLI/ACP unless the feature is explicitly platform-specific.

---

## Roadmap Overview

### Wave 0 — Design freeze and docs spine

Purpose: lock decisions before implementation so feature work does not become a vibes-powered shopping mall.

Deliverables:
- This roadmap.
- Tracker with stable anchors.
- Feature owner lanes and dependency map.
- Public/private docs placement decision.

Exit proof:
- Roadmap and tracker committed.
- Anchors are stable enough to become issues or Kanban tasks.

---

### Wave 1 — Low-risk quick wins

#### 1. AST-grep toolset

**Why:** OmO gets strong mileage from AST-aware search/replace. Hermes currently has regex search and fuzzy patch, but no syntax-aware structural search.

**Hermes-native design:**
- Add `tools/ast_grep_tool.py`.
- Register toolset `ast_grep` in `toolsets.py`.
- Expose:
  - `ast_grep_search(pattern, path='.', language='', file_glob='', limit=50)`
  - `ast_grep_replace(pattern, replacement, path='.', language='', file_glob='', dry_run=True)`
- Use `sg` / `ast-grep` CLI when installed.
- `check_fn` only exposes tools when dependency exists.
- Keep replace safe: dry-run by default, return diff/preview, require explicit write.

Primary files:
- `tools/ast_grep_tool.py` (new)
- `toolsets.py`
- `tests/tools/test_ast_grep_tool.py` (new)
- `website/docs/reference/tools-reference` or equivalent docs path

Acceptance proof:
- Unit tests pass with a fake CLI wrapper or skipped dependency tests.
- If `ast-grep` installed: smoke test finds and dry-runs replacement in a fixture.
- Tool hidden when dependency missing.

---

#### 2. `/init-deep` project context generator

**Why:** OmO’s `/init-deep` creates hierarchical `AGENTS.md`; Hermes already consumes context files, but lacks a generator.

**Hermes-native design:**
- Add CLI/slash command `/init-deep`.
- Generate or update context files only after dry-run preview by default.
- Produce root `AGENTS.md` and selected subdirectory `AGENTS.md` files.
- Use lightweight repo inspection:
  - language/file mix,
  - marker files,
  - test commands,
  - entrypoints,
  - local conventions from existing docs.
- Respect existing `AGENTS.md`: never overwrite silently; support `--create-new`, `--update`, `--max-depth=N`, `--dry-run`.

Primary files:
- `hermes_cli/commands.py`
- `cli.py`
- `agent/subdirectory_hints.py` or new `agent/init_deep.py`
- Gateway command mapping if command should work from Telegram.
- Tests under `tests/cli/` or `tests/agent/`.

Acceptance proof:
- Dry run shows planned files without writing.
- Existing `AGENTS.md` is preserved unless explicit update mode is requested.
- Generated content includes verifiable commands/paths, not invented architecture fanfic.

---

#### 3. Delegation categories

**Why:** OmO routes subagents by intent/category rather than forcing the parent to pick exact model/toolset each time. Hermes already has delegation; categories are a UX/config layer.

**Hermes-native design:**
- Add `delegation.categories` to config.
- Add optional `category` parameter to `delegate_task`.
- Category can provide defaults:
  - provider/model/base_url/api_key,
  - reasoning effort,
  - enabled toolsets,
  - skills,
  - role default,
  - timeout/max_iterations.
- Explicit tool call args override category defaults.
- Provide built-in default categories in code/config docs:
  - `quick`
  - `deep`
  - `review`
  - `research`
  - `visual`
  - `writing`
  - `ultrabrain`

Primary files:
- `hermes_cli/config.py`
- `tools/delegate_tool.py`
- tool schema for `delegate_task`
- `tests/tools/test_delegate_categories.py` (new)
- docs for delegation.

Acceptance proof:
- Category merge tests cover precedence.
- Unknown category produces clear tool error.
- Prompt/tool schema explains category use without hiding raw controls.

---

#### 4. `/ultrawork` UX alias over existing `/goal` + delegation bias

**Why:** OmO’s `ultrawork` is memorable. Hermes has `/goal`; it can expose a higher-intensity convenience mode without inventing a loop from scratch.

**Hermes-native design:**
- Add `/ultrawork <goal>` and maybe alias `/ulw`.
- Internally sets a goal-like continuation with an explicit high-intensity instruction:
  - use todo for multi-step work,
  - use delegation when independent lanes exist,
  - verify before final,
  - stop only when done or blocked.
- Avoid global permanent config changes.
- For Telegram/gateway, expose as slash command only if safe and documented.

Primary files:
- `hermes_cli/commands.py`
- `cli.py`
- `hermes_cli/goals.py` or adjacent goals code
- `gateway/run.py` if gateway command included
- tests for command parsing.

Acceptance proof:
- `/ultrawork` creates the expected goal state.
- `/goal status` or equivalent shows it clearly.
- `/stop` or `/goal pause/clear` stops it.

---

## Wave 2 — High-impact core tool upgrades

#### 5. Hash-anchored read/edit

**Why:** OmO’s Hashline solves the “model saw stale content / reproduces whitespace poorly” edit failure. Hermes patch is already fuzzy, but content-hash anchors would add a hard safety guard.

**Hermes-native design:**
- Add optional hash anchors to read output.
- Keep existing `read_file` line format by default unless the team chooses to switch globally.
- Candidate format:
  - existing: `123|content`
  - anchored: `123#Ab7Q|content`
- Hash must be deterministic, short, and content-based enough to detect line drift.
- Add either:
  - new tool `patch_by_anchor`, or
  - new `patch` mode `anchor`.
- Anchor edit input should support:
  - single-line replace,
  - range replace,
  - insert before/after anchor,
  - delete range.
- Must validate current file hashes before writing.
- On mismatch, refuse and tell the model to re-read.

Primary files:
- `tools/file_operations.py`
- `tools/file_tools.py`
- `tools/file_state.py` if anchor read state is tracked per task
- `tools/patch_parser.py` if patch mode extended
- `tests/tools/test_hash_anchored_patch.py` (new)
- docs/tool schema updates.

Acceptance proof:
- Matching anchor applies patch and returns diff.
- Changed line causes stale-anchor refusal.
- Duplicate line content is handled by line number + hash, not hash alone.
- CRLF/trailing newline behavior has tests.
- No regression in existing `read_file`/`patch` tests.

---

#### 6. LSP toolset

**Why:** OmO gives agents IDE-grade capabilities: diagnostics, symbols, goto definition, references, rename. Hermes should have a native provider-agnostic LSP layer.

**Hermes-native design:**
- Add `lsp` toolset with a small language-server manager.
- Start read-only:
  - `lsp_diagnostics`
  - `lsp_symbols`
  - `lsp_goto_definition`
  - `lsp_find_references`
- Add write/refactor operations later:
  - `lsp_prepare_rename`
  - `lsp_rename`
- Use project/workdir-rooted server processes with timeout and cleanup.
- Keep dependency checks explicit and tool availability honest.

Primary files:
- `tools/lsp_tool.py` (new)
- possibly `tools/lsp/` package for manager/client helpers
- `toolsets.py`
- `tests/tools/lsp/`
- config docs for language server commands.

Acceptance proof:
- Unit tests cover protocol message construction/response parsing with fake server.
- Integration smoke can be skipped when language server missing.
- Tool errors are actionable when no server is configured.
- LSP processes are cleaned up.

---

#### 7. Background agent runs

**Why:** OmO has background agents whose results can be retrieved later. Hermes has synchronous `delegate_task`, background terminal processes, and cron, but no first-class background *agent* result store.

**Hermes-native design:**
- Add toolset or commands:
  - `background_agent_start`
  - `background_agent_status`
  - `background_agent_output`
  - `background_agent_cancel`
- Runtime can initially spawn `hermes chat -q` in a background process with a structured prompt and output file.
- Store metadata under `get_hermes_home()/background_agents/`.
- Support delivery notification in gateway when job finishes.
- Later replace subprocess with durable internal runner if needed.

Primary files:
- `tools/background_agent_tool.py` (new) or extend `tools/process_registry.py`
- `toolsets.py`
- `gateway/run.py` notification bridge if included
- `tests/tools/test_background_agent_tool.py`
- docs.

Acceptance proof:
- Start returns a stable ID.
- Status transitions from running to completed/failed/cancelled.
- Output can be retrieved after completion.
- Cancel terminates running process.
- Stored paths are profile-safe via `get_hermes_home()`.

---

## Wave 3 — Orchestration polish and context economy

#### 8. Team presets over Kanban

**Why:** OmO’s team mode has a nice UX, but Hermes already has a better native durable board candidate: Kanban. Use Kanban rather than creating `.omo/runtime`-style storage.

**Hermes-native design:**
- Add a team preset layer that creates Kanban tasks, owners, links, and optional worker profiles from a declarative spec.
- Candidate command:
  - `hermes team create <preset-or-file>`
  - slash `/team start <preset>` later.
- Presets define:
  - lead/mandor,
  - member lanes,
  - max parallel workers,
  - workdir/worktree rules,
  - acceptance gates,
  - communication/handoff templates.
- Underneath, use existing Kanban board APIs and dispatcher.

Primary files:
- likely `hermes_cli/team.py` (new)
- `hermes_cli/main.py` command registration
- `plugins/kanban` / `hermes_cli/kanban.py` integration
- docs under `website/docs/user-guide/features/`.

Acceptance proof:
- Team spec creates expected Kanban tasks and dependencies.
- No duplicate board/runtime storage.
- Dry-run mode prints exact planned task graph.
- Worker ownership and max parallelism are enforceable.

---

#### 9. Accumulated wisdom pass-forward for orchestrated work

**Why:** OmO emphasizes “wisdom accumulation”: each subagent’s learnings are summarized and passed to later workers. Hermes users already like subagent orchestration; this would reduce repeated mistakes.

**Hermes-native design:**
- For `delegate_task` batch/orchestrator mode, allow parent to maintain a compact “run wisdom” object:
  - conventions,
  - gotchas,
  - commands,
  - failed attempts,
  - discovered contracts.
- For synchronous `delegate_task`, the parent can manually pass context today; this feature makes it structured and optionally automatic.
- For Kanban/team preset mode, store wisdom as board comments or run metadata.

Primary files:
- `tools/delegate_tool.py`
- `plugins/kanban` or `hermes_cli/kanban.py`
- tests around summary extraction/propagation.

Acceptance proof:
- Later child receives prior wisdom when enabled.
- Wisdom is bounded/truncated.
- Sensitive tool output is not blindly copied if redaction/security settings apply.

---

#### 10. IntentGate / mode inference

**Why:** OmO classifies user intent before acting. Hermes can add lightweight routing hints without overriding user instructions.

**Hermes-native design:**
- Add small intent inference helper for coding/task sessions:
  - `research`
  - `implementation`
  - `debug`
  - `review`
  - `planning`
  - `ops`
- Use heuristics first; optionally auxiliary model later.
- Output should affect guidance, not silently mutate toolsets or models mid-session.
- Tie into `/ultrawork`, delegation categories, coding runtime, or future mode system.

Primary files:
- `agent/intent_gate.py` (new) or part of coding runtime module
- `run_agent.py` prompt block integration if session-mode based
- tests for deterministic inference.

Acceptance proof:
- Ambiguous prompts produce conservative/default mode.
- Explicit user mode wins over inference.
- No hidden side effects that surprise users.

---

#### 11. Skill-embedded MCP lifecycle

**Why:** OmO skills can bring scoped MCP servers. Hermes has MCP and skills, but MCP tool schemas are generally configured at session/toolset level. Skill-scoped MCP can reduce context bloat.

**Hermes-native design:**
- Extend Hermes skill frontmatter to allow scoped MCP definitions.
- Only activate skill MCP tools in a fresh session/subagent/task where tool schema can be built before the API call.
- Do not hot-add tools mid-conversation unless the existing prompt-caching/tool-schema rules are explicitly updated.
- Skill `metadata.hermes.mcp` could define command/url and exposed tool filters.

Primary files:
- `agent/skill_utils.py`
- `tools/skills_tool.py`
- `tools/mcp_tool.py`
- prompt/tool discovery path in `model_tools.py`
- tests for skill parsing and gated MCP exposure.

Acceptance proof:
- Skill frontmatter parses correctly.
- Fresh subagent/session can expose the skill MCP.
- Existing sessions do not mutate their tool schema unexpectedly.
- MCP process cleanup is verified.

---

#### 12. Model fallback chains / category fallback policy

**Why:** OmO has explicit fallback chains per agent/category. Hermes has provider flexibility and credential pools, but category-level fallback policy would improve predictable delegation.

**Hermes-native design:**
- For categories, allow fallback arrays:
  - plain model strings,
  - provider/model/effort objects.
- Integrate with existing error classifier and provider retry behavior where possible.
- Keep first implementation small: category fallback only for delegated child construction or background agents.

Primary files:
- `tools/delegate_tool.py`
- `agent/error_classifier.py` only if new failure action is needed
- provider/model routing helpers
- config docs/tests.

Acceptance proof:
- If primary category model unavailable, fallback is attempted and logged.
- Permanent auth failures do not loop forever.
- User-visible output shows actual model/provider used when relevant.

---

## Feature Prioritization

### Must ship first

1. **AST-grep toolset** — easy, powerful, low risk.
2. **Hash-anchored edit** — high correctness impact.
3. **Delegation categories** — improves orchestration immediately.
4. **LSP read-only tools** — high leverage for coding accuracy.

### Should ship next

5. **Background agent runs** — unlocks durable async work.
6. **`/init-deep`** — improves project context hygiene.
7. **`/ultrawork` alias** — UX win using existing goal mechanics.
8. **Team presets over Kanban** — productizes existing multi-agent board.

### Later / depends on architecture review

9. **Skill-embedded MCP** — powerful but touches prompt/tool schema lifecycle.
10. **IntentGate** — useful, but must avoid surprise behavior.
11. **Category fallback chains** — useful after categories exist.
12. **Accumulated wisdom** — best once team/delegation workflows stabilize.

---

## Parallel Execution Lanes

### Lane A — Code intelligence tools

Owns:
- AST-grep toolset.
- LSP toolset.

Does not own:
- Delegation categories.
- Team presets.

Can run after:
- Wave 0 docs accepted.

### Lane B — Safer editing

Owns:
- Hash-anchored read/edit.

Does not own:
- AST-grep replace semantics beyond interop notes.

Can run after:
- Wave 0 docs accepted.

### Lane C — Orchestration ergonomics

Owns:
- Delegation categories.
- `/ultrawork` alias.
- Background agent runs.
- Accumulated wisdom.

Does not own:
- Kanban team preset implementation unless explicitly assigned.

Can run after:
- Category schema is frozen.

### Lane D — Durable multi-agent productization

Owns:
- Team presets over Kanban.
- Kanban integration docs.
- Worker/handoff templates.

Can run after:
- Delegation categories and background agent design decisions are at least drafted.

### Lane E — Context and integration economy

Owns:
- `/init-deep`.
- Skill-embedded MCP.
- IntentGate/mode inference.

Can run after:
- Prompt/tool schema constraints are reviewed.

---

## Sequencing Rules

1. Do **AST-grep** before AST-aware refactor commands.
2. Do **hash-anchored edits** before pushing agents toward more aggressive autonomous edits.
3. Do **delegation categories** before team presets, so teams can reference categories rather than raw models.
4. Do **background agents** before promising long-running team UX outside Kanban workers.
5. Do **LSP read-only** before LSP rename/write tools.
6. Do **skill-embedded MCP** only after deciding how fresh-session/subagent tool schema assembly should work.
7. Do not mark any feature done without docs and tests; agent harness features without proof are just astrology with YAML.

---

## Verification Strategy

Minimum proof package per feature:

- Unit tests for schema/merge/parsing behavior.
- Tool-level tests with fake dependencies where possible.
- Integration smoke tests gated/skipped when optional external CLIs are missing.
- CLI command parse tests for new slash/CLI commands.
- Docs updates for new user-visible toolsets and config.
- `python -m pytest ... -o 'addopts=' -q` targeted tests at minimum.

Feature-specific proof lives in the tracker.

---

## Open Decisions

1. Should hash anchors be default in `read_file`, opt-in via parameter, or separate `read_file_anchored` tool?
2. Should AST-grep be a core toolset or optional off-by-default toolset?
3. Should LSP run as long-lived per-workdir processes or one-shot per tool call for v1?
4. Should `/ultrawork` be CLI-only first or also gateway-visible from day one?
5. Should background agents be implemented as subprocess `hermes chat -q` first, or direct internal process/thread runners?
6. Should team presets be a core feature or a Kanban plugin extension?
7. What is the exact frontmatter schema for skill-embedded MCP without breaking prompt caching?

---

## Anti-Bullshit Notes

- OmO is an OpenCode plugin; not every hook maps cleanly to Hermes.
- Hermes already has Kanban, cron, delegation, skills, and gateway. Rebuilding OmO storage patterns would be wasteful.
- The highest-risk areas are tool schema lifecycle, prompt caching, LSP process lifecycle, and background agent cancellation.
- The lowest-risk quick win is AST-grep.
- The highest direct correctness win is hash-anchored edit.
- The most product-visible orchestration win is delegation categories + `/ultrawork` + background agents.

---

## Related Tracker

Implementation slices, dependencies, acceptance proof, and re-anchor rules are in:

- `docs/plans/2026-05-08-oh-my-openagent-inspired-hermes-tracker.md`
