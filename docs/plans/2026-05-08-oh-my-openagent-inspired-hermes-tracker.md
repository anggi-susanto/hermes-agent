# Oh My OpenAgent-Inspired Hermes Upgrade Tracker

Goal: track implementation of the Hermes-native upgrades inspired by `code-yeongyu/oh-my-openagent` without losing scope, proof requirements, or ownership boundaries.

Related roadmap:
- `docs/plans/2026-05-08-oh-my-openagent-inspired-hermes-roadmap.md`

Audit source:
- `https://github.com/code-yeongyu/oh-my-openagent`
- Audited commit: `c7d6a4a2ce55237c7547e5a091a9a1446ae6d2c9`

Tracker date: 2026-05-08

---

## Stable Anchor Rules

1. Preserve anchor IDs even if titles or scope wording change.
2. Never silently delete a parent item after splitting; mark it `Split` and link child anchors.
3. Do not mark work `Done` just because code exists. Require tests, docs, and runtime/tool proof where applicable.
4. If a slice is partially delivered, mark it `Partial`, record proof, and create child anchors for remaining gaps.
5. If a dependency changes, update both the dependency map and affected anchor sections.
6. Prefer child IDs like `OMO-005.A` for follow-up splits.

---

## Status Vocabulary

- `Pending` — not started.
- `In Progress` — actively being implemented or reviewed.
- `Partial` — some accepted proof exists, but scope remains.
- `Blocked` — cannot proceed until dependency or decision is resolved.
- `Done` — implementation, tests, docs, and acceptance proof are complete.
- `Split` — parent was decomposed into child anchors; parent should not be closed directly.
- `Dropped` — intentionally removed from roadmap, with rationale.

---

## Owner Lanes

- **Lane A — Code intelligence tools:** AST-grep and LSP.
- **Lane B — Safer editing:** hash-anchored read/edit.
- **Lane C — Orchestration ergonomics:** delegation categories, ultrawork, background agents, wisdom pass-forward.
- **Lane D — Durable multi-agent productization:** team presets over Kanban.
- **Lane E — Context and integration economy:** init-deep, IntentGate, skill-embedded MCP.
- **Lane F — Docs/release:** public docs, migration notes, final acceptance matrix.

---

## Dependency Map

Hard dependencies:

- `OMO-000` must land before implementation anchors are opened as issues.
- `OMO-003` should land before `OMO-008`, because team presets should reference categories.
- `OMO-006` read-only LSP should land before any future LSP write/rename child anchors.
- `OMO-007` should land before promising non-Kanban long-running team UX.
- `OMO-011` requires a prompt/tool schema lifecycle decision before implementation.

Soft dependencies:

- `OMO-001` AST-grep can run in parallel with `OMO-005` hash-anchored edit.
- `OMO-002` init-deep can run in parallel with code-tool work.
- `OMO-004` ultrawork can run after minimal category semantics are drafted, but does not require category implementation.
- `OMO-010` IntentGate can start as docs/design while implementation waits for coding-runtime decisions.
- `OMO-012` fallback chains should follow `OMO-003` categories.

Parallel-safe starter set:

- `OMO-001` AST-grep toolset.
- `OMO-002` init-deep generator.
- `OMO-003` delegation categories.
- `OMO-005` hash-anchored edit design/tests.
- `OMO-006` LSP read-only design/tests.

---

## Master Tracker

- `OMO-000`: Roadmap and tracker freeze
  - Status: `Pending`
  - Dependencies: none
  - Owner lane: Lane F
  - Why it matters: locks shared scope before agents scatter like caffeinated raccoons.

- `OMO-001`: AST-grep toolset
  - Status: `Pending`
  - Dependencies: `OMO-000`
  - Owner lane: Lane A
  - Why it matters: adds structural code search/replace with low risk.

- `OMO-002`: `/init-deep` hierarchical context generator
  - Status: `Pending`
  - Dependencies: `OMO-000`
  - Owner lane: Lane E
  - Why it matters: makes Hermes-generated project context files first-class.

- `OMO-003`: Delegation categories
  - Status: `Pending`
  - Dependencies: `OMO-000`
  - Owner lane: Lane C
  - Why it matters: makes subagent routing ergonomic and configurable.

- `OMO-004`: `/ultrawork` and `/ulw` UX mode
  - Status: `Pending`
  - Dependencies: `OMO-000`; soft dependency `OMO-003`
  - Owner lane: Lane C
  - Why it matters: exposes high-intensity execution using Hermes-native `/goal` mechanics.

- `OMO-005`: Hash-anchored read/edit
  - Status: `Pending`
  - Dependencies: `OMO-000`
  - Owner lane: Lane B
  - Why it matters: prevents stale-line edits and improves patch reliability.

- `OMO-006`: LSP read-only toolset
  - Status: `Pending`
  - Dependencies: `OMO-000`
  - Owner lane: Lane A
  - Why it matters: gives agents IDE-grade diagnostics/navigation.

- `OMO-007`: Background agent runs
  - Status: `Pending`
  - Dependencies: `OMO-000`; soft dependency `OMO-003`
  - Owner lane: Lane C
  - Why it matters: lets Hermes run autonomous agents asynchronously with retrievable output.

- `OMO-008`: Team presets over Kanban
  - Status: `Pending`
  - Dependencies: `OMO-003`; soft dependency `OMO-007`
  - Owner lane: Lane D
  - Why it matters: productizes multi-agent teams without duplicating Kanban storage.

- `OMO-009`: Accumulated wisdom pass-forward
  - Status: `Pending`
  - Dependencies: `OMO-003`; soft dependency `OMO-008`
  - Owner lane: Lane C
  - Why it matters: reduces repeated subagent mistakes in multi-lane work.

- `OMO-010`: IntentGate / mode inference
  - Status: `Pending`
  - Dependencies: `OMO-000`; soft dependency coding-runtime decisions
  - Owner lane: Lane E
  - Why it matters: improves intent-aware behavior without user micromanagement.

- `OMO-011`: Skill-embedded MCP lifecycle
  - Status: `Pending`
  - Dependencies: `OMO-000`; blocked by tool-schema lifecycle decision
  - Owner lane: Lane E
  - Why it matters: lets skills bring scoped tools without global context bloat.

- `OMO-012`: Category fallback policy
  - Status: `Pending`
  - Dependencies: `OMO-003`
  - Owner lane: Lane C
  - Why it matters: improves resilience when category-preferred providers/models fail.

- `OMO-013`: Docs and release acceptance matrix
  - Status: `Pending`
  - Dependencies: all shipped feature anchors
  - Owner lane: Lane F
  - Why it matters: ensures shipped behavior is documented and verifiable.

---

## Anchor Details

## OMO-000 — Roadmap and Tracker Freeze

### Problem

The OmO audit surfaced many tempting features. Without a frozen roadmap/tracker, implementation can drift into duplicating OpenCode plugin internals or inventing overlapping systems Hermes already has.

### Objective

Create durable docs that define scope, sequencing, dependencies, owner lanes, and proof expectations.

### Scope

In scope:
- Roadmap doc.
- Tracker doc.
- Stable anchor IDs.
- Dependency map.
- Anti-bullshit notes.

Out of scope:
- Feature implementation.
- Public website docs.
- GitHub issue creation unless explicitly requested later.

### Dependencies

None.

### Deliverables

- `docs/plans/2026-05-08-oh-my-openagent-inspired-hermes-roadmap.md`
- `docs/plans/2026-05-08-oh-my-openagent-inspired-hermes-tracker.md`

### Acceptance Proof

- Both files exist.
- `git status --short` shows only expected docs changes for this docs-only slice.
- Tracker includes stable anchors, statuses, dependencies, proof, anti-bullshit notes, and re-anchor rules.

### Anti-Bullshit Notes

- This anchor is docs-only. It does not prove implementation started.
- Do not mark later feature anchors `Done` just because they are described here.

---

## OMO-001 — AST-grep Toolset

### Problem

Hermes has regex search and fuzzy patch, but lacks syntax-aware structural search/replace. Regex refactors are where optimism goes to die wearing clown shoes.

### Objective

Expose AST-aware code search and safe dry-run replacement as a Hermes optional toolset.

### Scope

In scope:
- New tool module wrapping `ast-grep` / `sg` CLI.
- `ast_grep_search` tool.
- `ast_grep_replace` tool with dry-run default.
- Toolset registration.
- Dependency check so tools hide when CLI missing.
- Unit tests and optional integration smoke.

Out of scope:
- LSP integration.
- Complex codemod DSL beyond what `ast-grep` supports.
- Automatic large refactors without explicit user/tool approval.

### Expected Files

- Create: `tools/ast_grep_tool.py`
- Modify: `toolsets.py`
- Create: `tests/tools/test_ast_grep_tool.py`
- Modify docs under `website/docs/` or tool reference path chosen by maintainer.

### Dependencies

- `OMO-000`

### Deliverables

- Tool schema with clear parameters.
- Safe command invocation with path validation and timeout.
- JSON result output with matches/diff/summary.
- Tests.
- Docs.

### Acceptance Proof

- `python -m pytest tests/tools/test_ast_grep_tool.py -o 'addopts=' -q` passes.
- Dependency-missing behavior is tested.
- Dry-run replacement returns preview and does not mutate files.
- If CLI is available, fixture smoke proves search works.

### Anti-Bullshit Notes

- A wrapper that shells out without dependency gating is not done.
- Replace mode without dry-run default is not done.
- A docs-only mention of AST-grep is not done.

---

## OMO-002 — `/init-deep` Hierarchical Context Generator

### Problem

Hermes can read context files, but users/agents must manually author good `AGENTS.md` context. Large repos need scoped context files to reduce repeated discovery.

### Objective

Add a safe command that generates root and directory-level `AGENTS.md` context files from repo inspection.

### Scope

In scope:
- CLI slash command `/init-deep`.
- Dry-run default.
- `--max-depth`, `--create-new`, and explicit update behavior.
- Existing-file protection.
- Marker-file and language-mix inspection.
- Tests for generation and overwrite refusal.

Out of scope:
- Perfect architecture understanding.
- Auto-committing generated files.
- Running destructive repo commands.

### Expected Files

- Modify: `hermes_cli/commands.py`
- Modify: `cli.py`
- Create or modify: `agent/init_deep.py` or nearby context helper module
- Tests under `tests/cli/` or `tests/agent/`
- Docs under `website/docs/` if exposed publicly.

### Dependencies

- `OMO-000`

### Deliverables

- Dry-run output listing target files and summaries.
- Generation logic using existing filesystem/git context.
- Safe update behavior.
- Tests/docs.

### Acceptance Proof

- Dry-run creates no files.
- Existing `AGENTS.md` is not overwritten without explicit flag.
- Generated file includes repo-specific observed facts, not hallucinated stack claims.
- Targeted tests pass.

### Anti-Bullshit Notes

- A generator that blindly writes over existing instructions is rejected.
- A generic AGENTS.md template with no repo inspection does not satisfy this anchor.

---

## OMO-003 — Delegation Categories

### Problem

`delegate_task` is powerful but forces callers to specify low-level choices. OmO’s category layer shows the ergonomic value of routing by work type.

### Objective

Add configurable category presets for Hermes subagent delegation.

### Scope

In scope:
- `delegation.categories` config schema/default docs.
- Optional `category` parameter on `delegate_task`.
- Category merge logic.
- Built-in documented examples.
- Tests for precedence and invalid categories.

Out of scope:
- Full model fallback chains; tracked separately in `OMO-012`.
- Team mode/presets; tracked separately in `OMO-008`.
- Hard-coded mythology/persona agents.

### Expected Files

- Modify: `hermes_cli/config.py`
- Modify: `tools/delegate_tool.py`
- Modify: tool schema in `tools/delegate_tool.py`
- Create: `tests/tools/test_delegate_categories.py`
- Docs update.

### Dependencies

- `OMO-000`

### Deliverables

- Category config docs.
- Merge helper with explicit precedence:
  1. explicit tool args,
  2. category config,
  3. delegation defaults,
  4. parent inherited settings.
- Test coverage.

### Acceptance Proof

- Targeted delegation category tests pass.
- Unknown category returns structured error.
- Explicit toolsets/model override category defaults.
- Subagent prompt/toolset remains bounded by existing blocked tools.

### Anti-Bullshit Notes

- Do not add categories by only changing prompt text.
- Do not bypass child tool blocklist.
- Do not mutate global config during a tool call.

---

## OMO-004 — `/ultrawork` and `/ulw` UX Mode

### Problem

Hermes has `/goal`, but lacks the memorable high-intensity “do the whole thing” UX exposed by OmO’s `ultrawork`.

### Objective

Add `/ultrawork` and `/ulw` as Hermes-native aliases that use existing goal/continuation mechanics with stronger execution guidance.

### Scope

In scope:
- Slash command registration.
- CLI handler.
- Optional gateway handler if command support is clean.
- Integration with `/goal` state or adjacent goals module.
- Tests for parsing and stop/pause behavior.

Out of scope:
- New infinite loop engine.
- Silent global reasoning/model changes.
- Autonomous destructive actions.

### Expected Files

- Modify: `hermes_cli/commands.py`
- Modify: `cli.py`
- Possibly modify: `hermes_cli/goals.py`
- Possibly modify: `gateway/run.py`
- Tests for command behavior.

### Dependencies

- `OMO-000`
- Soft: `OMO-003`

### Deliverables

- `/ultrawork <goal>` starts a bounded continuation workflow.
- `/ulw` alias.
- Clear user-visible status/stop semantics.

### Acceptance Proof

- Command parser tests pass.
- `/goal status` or equivalent shows active ultrawork goal.
- Existing stop/clear mechanisms stop the loop.

### Anti-Bullshit Notes

- Must not become an unbounded spend loop.
- Must not bypass approvals.
- Must not rely on OmO/OpenCode.

---

## OMO-005 — Hash-Anchored Read/Edit

### Problem

Line-number edits can go stale when files change. Fuzzy matching helps but does not provide a hard freshness guarantee.

### Objective

Add content-hash anchored edit support so Hermes can reject stale edits before writing.

### Scope

In scope:
- Hash anchor rendering for reads or new anchored read mode.
- Anchor-based patch mode or tool.
- Validation against current file content before mutation.
- Diff output and clear stale-anchor errors.
- Tests for newline, duplicate line, mismatch, and success cases.

Out of scope:
- Replacing all existing patch behavior.
- Cross-file AST refactors.
- Persisting every read forever.

### Expected Files

- Modify: `tools/file_tools.py`
- Modify: `tools/file_operations.py`
- Possibly modify: `tools/file_state.py`
- Possibly modify: `tools/patch_parser.py`
- Create: `tests/tools/test_hash_anchored_patch.py`
- Docs/tool schema updates.

### Dependencies

- `OMO-000`

### Deliverables

- Anchor format decision documented.
- Tool implementation.
- Tests.
- Docs.

### Acceptance Proof

- Matching anchor edit applies and returns unified diff.
- Stale anchor refuses write.
- Duplicate content lines are addressed by line number + hash.
- Existing file tool tests pass.

### Anti-Bullshit Notes

- Hash display without edit validation is not done.
- Edit validation without tests for stale file content is not done.
- Any implementation that silently falls back to fuzzy patch after hash mismatch is rejected.

---

## OMO-006 — LSP Read-Only Toolset

### Problem

Hermes agents lack IDE-grade symbol/diagnostic context. Grep is useful, but not semantic enough for many coding tasks.

### Objective

Add an optional read-only LSP toolset for diagnostics and navigation.

### Scope

In scope:
- LSP client/manager.
- `lsp_diagnostics`.
- `lsp_symbols`.
- `lsp_goto_definition`.
- `lsp_find_references`.
- Configurable language server commands.
- Process cleanup and timeouts.
- Tests with fake LSP server/protocol fixtures.

Out of scope:
- Rename/write operations in v1.
- Full IDE feature parity.
- Mandatory language server installation.

### Expected Files

- Create: `tools/lsp_tool.py` or `tools/lsp/` package
- Modify: `toolsets.py`
- Create: `tests/tools/lsp/` tests
- Modify config docs.

### Dependencies

- `OMO-000`

### Deliverables

- Optional toolset.
- Honest dependency/config errors.
- Tests/docs.

### Acceptance Proof

- Fake-server tests pass.
- Missing-server behavior is actionable.
- No orphan language server process after tests.
- Tool outputs are bounded for context size.

### Anti-Bullshit Notes

- Do not expose LSP tools if no server can run.
- Do not implement rename in this anchor; split a child anchor later.

---

## OMO-007 — Background Agent Runs

### Problem

`delegate_task` is synchronous. Long work that should continue while the parent works needs a first-class background agent abstraction with retrievable output.

### Objective

Add background agent start/status/output/cancel tools or commands.

### Scope

In scope:
- Stable background agent ID.
- Metadata and output storage under `get_hermes_home()`.
- Start/status/output/cancel operations.
- Initial backend may be `hermes chat -q` subprocess.
- Optional gateway completion notification.

Out of scope:
- Full team mode.
- Realtime bidirectional steering in v1.
- Replacing `delegate_task`.

### Expected Files

- Create: `tools/background_agent_tool.py`
- Modify: `toolsets.py`
- Possibly modify: `tools/process_registry.py`
- Possibly modify: `gateway/run.py`
- Tests under `tests/tools/`.

### Dependencies

- `OMO-000`
- Soft: `OMO-003`

### Deliverables

- Tool API.
- Persistent metadata/output.
- Cancellation path.
- Tests/docs.

### Acceptance Proof

- Start returns ID and status running/completed.
- Output remains retrievable after completion.
- Cancel terminates running job.
- Profile-safe paths verified.

### Anti-Bullshit Notes

- Raw terminal background process without metadata/output API is not enough.
- Tool must not hide failure output.

---

## OMO-008 — Team Presets over Kanban

### Problem

OmO team mode has good UX, but Hermes should not duplicate board storage. Hermes Kanban should be the durable backend.

### Objective

Add team preset creation that compiles a declarative team spec into Kanban tasks/workers/dependencies.

### Scope

In scope:
- Team spec format.
- Dry-run graph preview.
- Kanban task creation/linking.
- Owner lanes and max parallelism where supported.
- Optional worktree/profile references.

Out of scope:
- New `.omo`-style runtime directories.
- Nested teams.
- Replacing Kanban dispatcher.

### Expected Files

- Create: `hermes_cli/team.py` or plugin extension.
- Modify: `hermes_cli/main.py` if CLI subcommand is added.
- Integrate with `hermes_cli/kanban.py` or `plugins/kanban`.
- Docs/tests.

### Dependencies

- `OMO-003`
- Soft: `OMO-007`

### Deliverables

- Team spec parser.
- Dry-run output.
- Kanban graph creation.
- Tests/docs.

### Acceptance Proof

- Example spec creates expected tasks and dependencies in test board.
- Dry-run creates nothing.
- No second task storage backend is introduced.

### Anti-Bullshit Notes

- If it bypasses Kanban, it violates this anchor.
- If ownership/dependencies cannot be inspected afterward, it is not done.

---

## OMO-009 — Accumulated Wisdom Pass-Forward

### Problem

Parallel/subsequent subagents often rediscover the same gotchas. OmO explicitly passes accumulated learnings forward.

### Objective

Provide a bounded structured run-wisdom mechanism for orchestrated delegation and/or Kanban teams.

### Scope

In scope:
- Wisdom categories: conventions, gotchas, commands, failures, contracts.
- Bounded summary format.
- Injection into later child prompts when enabled.
- Storage as run metadata/comment when used with Kanban.

Out of scope:
- Permanent memory writes by child agents.
- Unbounded transcript copying.
- Replacing parent reasoning.

### Expected Files

- Modify: `tools/delegate_tool.py`
- Possibly modify: Kanban plugin/CLI files
- Tests around truncation and injection.

### Dependencies

- `OMO-003`
- Soft: `OMO-008`

### Deliverables

- Structured wisdom object.
- Opt-in/controlled injection.
- Tests.

### Acceptance Proof

- Later child receives prior wisdom in tests.
- Wisdom truncates predictably.
- Child cannot write shared memory directly through this mechanism.

### Anti-Bullshit Notes

- Copying full previous child outputs is not wisdom; it is context arson.
- Must respect redaction/security settings.

---

## OMO-010 — IntentGate / Mode Inference

### Problem

Agents can misread whether a user wants research, implementation, debug, review, or planning. OmO uses intent detection to route behavior.

### Objective

Add conservative intent inference that informs Hermes behavior without surprising users.

### Scope

In scope:
- Deterministic heuristic classifier for v1.
- Explicit user mode overrides inference.
- Intent block can inform prompts/categories.
- Tests for common phrases and ambiguous prompts.

Out of scope:
- Mandatory auxiliary model calls.
- Silent toolset/model mutation mid-session.
- Aggressive auto-execution beyond user scope.

### Expected Files

- Create: `agent/intent_gate.py` or integrate into coding runtime.
- Possibly modify: `run_agent.py` or CLI command surfaces.
- Tests under `tests/agent/`.

### Dependencies

- `OMO-000`
- Soft: coding runtime/mode decisions.

### Deliverables

- Inference helper.
- Prompt integration or consumer integration.
- Tests/docs.

### Acceptance Proof

- Explicit mode wins.
- Ambiguous prompt defaults conservatively.
- Tests cover Indonesian/English common command phrases if relevant to Hermes users.

### Anti-Bullshit Notes

- The classifier must not become a bossy gremlin that overrides explicit user instructions.

---

## OMO-011 — Skill-Embedded MCP Lifecycle

### Problem

Global MCP tool exposure can bloat context. OmO scopes MCP tools to skills. Hermes has both skills and MCP but needs lifecycle rules before merging them.

### Objective

Allow skills to declare MCP servers that are only exposed in fresh sessions/subagents where tool schema can be built safely.

### Scope

In scope:
- Frontmatter schema design.
- Parser support.
- Fresh session/subagent activation path.
- MCP process cleanup.
- Tests for parsing and exposure gating.

Out of scope:
- Hot-adding tools mid-session.
- Trusting arbitrary skill MCP without user/config gates.
- Replacing normal MCP config.

### Expected Files

- Modify: `agent/skill_utils.py`
- Modify: `tools/skills_tool.py`
- Modify: `tools/mcp_tool.py`
- Possibly modify: `model_tools.py`
- Tests for lifecycle behavior.

### Dependencies

- `OMO-000`
- Blocked by tool-schema lifecycle decision.

### Deliverables

- Schema proposal.
- Implementation respecting prompt caching.
- Cleanup and tests.

### Acceptance Proof

- Skill with MCP frontmatter exposes scoped tool in a fresh controlled context.
- Existing running session tool schema is not mutated unexpectedly.
- MCP cleanup verified.

### Anti-Bullshit Notes

- If it breaks prompt caching, reject.
- If all skill MCPs become globally visible, reject.

---

## OMO-012 — Category Fallback Policy

### Problem

Delegation categories should remain useful when preferred provider/model fails.

### Objective

Add optional fallback chains to delegation categories.

### Scope

In scope:
- Category fallback array syntax.
- Plain model string and object entries.
- Integration with child agent construction/retry.
- Logging/output of selected fallback.
- Tests for fallback ordering and permanent failure bounds.

Out of scope:
- Global provider routing redesign.
- Infinite fallback loops.
- Billing/auth bypass.

### Expected Files

- Modify: `tools/delegate_tool.py`
- Possibly modify: provider routing helpers
- Config/docs/tests.

### Dependencies

- `OMO-003`

### Deliverables

- Fallback schema.
- Execution behavior.
- Tests/docs.

### Acceptance Proof

- Simulated model-not-found tries fallback.
- Permanent auth failure does not loop forever.
- Actual selected provider/model is surfaced in result metadata where appropriate.

### Anti-Bullshit Notes

- Fallback config that is parsed but unused is not done.

---

## OMO-013 — Docs and Release Acceptance Matrix

### Problem

Harness features are easy to add and hard to operate if undocumented. Users need clear docs, setup, limits, and proof examples.

### Objective

Document shipped features and collect final acceptance proof across anchors.

### Scope

In scope:
- User docs for each shipped feature.
- Tool reference updates.
- Config reference updates.
- Release note or changelog entry.
- Acceptance matrix linking anchors to tests/proof.

Out of scope:
- Documenting unshipped roadmap items as available.
- Marketing claims without runtime proof.

### Expected Files

- `website/docs/...`
- `docs/plans/...` acceptance matrix or release notes path
- Possibly README updates.

### Dependencies

- Depends on shipped feature anchors.

### Deliverables

- Docs.
- Acceptance matrix.
- Release notes.

### Acceptance Proof

- Docs build passes if docs build is available.
- Every shipped anchor has test command/proof entry.
- Unshipped anchors remain marked pending/partial, not implied available.

### Anti-Bullshit Notes

- Docs must say optional dependencies are optional.
- Do not claim OmO compatibility; claim Hermes-native inspired features.

---

## Re-Anchor Checklist

When updating any anchor:

1. Change status in Master Tracker.
2. Add implementation branch/commit/PR if available.
3. Add proof commands and outputs.
4. Update dependencies if changed.
5. If partial, create child anchors for remaining work.
6. Add anti-bullshit notes for what still does not count as done.
7. Update roadmap priority if implementation discoveries change sequencing.

---

## Reviewer Checklist

Reject `Done` unless all are true:

- Code is merged or the exact commit/branch is referenced.
- Tests covering the feature pass.
- Optional dependency behavior is tested or explicitly skipped with reason.
- Docs/tool schema/config reference are updated for user-visible behavior.
- The feature uses profile-safe paths (`get_hermes_home()` where relevant).
- No prompt/tool schema caching invariant is violated.
- No duplicate storage backend is introduced where Hermes already has one.
- Runtime behavior was verified through actual tool/CLI path where applicable.

---

## First Suggested Issue Batch

If converting this tracker into GitHub issues, open these first:

1. `OMO-001` AST-grep toolset.
2. `OMO-005` Hash-anchored read/edit design + implementation.
3. `OMO-003` Delegation categories.
4. `OMO-006` LSP read-only toolset.
5. `OMO-002` `/init-deep` generator.

Rationale:
- They are high-leverage.
- They can run mostly in parallel.
- They create foundations for later orchestration polish.

---

## Current Proof Log

### 2026-05-08 — Roadmap/tracker creation

Evidence to fill after verification:
- Roadmap path: `docs/plans/2026-05-08-oh-my-openagent-inspired-hermes-roadmap.md`
- Tracker path: `docs/plans/2026-05-08-oh-my-openagent-inspired-hermes-tracker.md`
- Git status: pending verification after file write.
