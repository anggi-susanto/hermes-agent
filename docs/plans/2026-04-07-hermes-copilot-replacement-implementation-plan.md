# Hermes as a Copilot Replacement — Implementation Plan

> For Hermes: use this plan to implement a real Copilot replacement workflow inside Hermes itself. The goal is not provider integration, IDE autocomplete parity, or Copilot compatibility layers. The goal is to make Hermes the default engineering operating system for coding work through SOP-driven modes, automatic repo context assembly, evidence-backed execution, and reusable UX surfaces. Keep scope tight for the first shippable slice and avoid unrelated refactors.

Goal: ship the first real Hermes coding-runtime workflow that can credibly replace Copilot for repo-backed engineering tasks by adding coding modes, a reusable context-pack builder, and a verification-oriented response contract across CLI and ACP-capable sessions.

Architecture: add a coding-runtime layer parallel to existing generic chat behavior. This layer should normalize coding requests into structured work orders, build a compact repo context pack before acting, route the session through a mode-specific SOP (`implement`, `debug`, `review`, `test`, `ship`, `explain`), and enforce evidence-aware completion semantics. Start docs-first and workflow-first: avoid any attempt to mimic IDE autocomplete, and do not entangle this work with provider routing or unrelated gateway features.

Tech stack: existing Hermes CLI, ACP adapter, prompt-builder stack, slash-command registry, profile system, skill system, terminal/file/search/read/patch tools, delegation/subagent tooling, and Docusaurus docs under `website/docs/`.

Source design doc: `docs/plans/2026-04-07-hermes-copilot-replacement-design.md`

Current state assessment:
- Hermes already has the agent loop, tool calling, and multi-surface runtime needed for engineering work (`run_agent.py`, `cli.py`, `gateway/`, `acp_adapter/`).
- Hermes already has a strong tool surface for coding tasks: terminal, file tools, patch, delegation, browser, memory, and search.
- Hermes already has reusable slash-command plumbing in `hermes_cli/commands.py` and CLI dispatch in `cli.py`.
- Hermes already supports profiles, which makes a coding-focused profile or preset plausible without inventing a new config root.
- ACP already exists and uses a curated `hermes-acp` toolset, but ACP docs currently position Hermes generically as an editor coding agent rather than a governed coding-runtime profile.
- Public docs explicitly say Hermes is “not a coding copilot tethered to an IDE,” which is good positioning, but there is no positive “replace Copilot with disciplined coding workflows” story yet.
- There is no first-class concept today for coding modes, a repo context pack, or proof-oriented coding closeout contracts.

Non-goals for first shippable milestone:
- No inline autocomplete or editor ghost text.
- No new inference-provider integration or Copilot provider reuse.
- No major redesign of the core agent loop.
- No new gateway-specific command system unless the same feature also cleanly fits CLI/ACP.
- No broad changes to non-coding user journeys.
- No requirement to persist coding artifacts to disk by default unless that meaningfully improves the workflow.

---

## Mission

Turn Hermes into a coding operating system that users can prefer over Copilot for real engineering work. The first implementation should make Hermes reliably better at task execution, debugging discipline, repo awareness, and verification honesty.

A successful first release should let a user start a coding task and feel that Hermes:
1. understands the workspace before editing,
2. gathers the right local context without prompting gymnastics,
3. follows a predictable mode-specific SOP,
4. validates what it changes,
5. and reports results with proof instead of vibes.

---

## Staffing model

Recommended execution lanes:

1. Lane A — workflow contract and prompt integration
   Owner: implementation agent
   Reviewer: spec-compliance reviewer
   Scope: coding mode schema, work-order normalization, prompt-builder integration, mode semantics
   Must not own: doc-site polish, ACP UX copy

2. Lane B — repo context pack builder
   Owner: implementation agent
   Reviewer: code-quality reviewer
   Scope: workspace detection, branch/dirty-state summary, relevant-file discovery, test-command hints
   Must not own: slash-command/public docs strategy

3. Lane C — CLI/ACP surfacing
   Owner: implementation agent
   Reviewer: UX/integration reviewer
   Scope: slash commands/profile hooks/config plumbing for coding modes, ACP alignment
   Must not own: core prompt heuristics redesign beyond agreed contracts

4. Lane D — docs, examples, and tests
   Owner: implementation agent
   Reviewer: docs/testing reviewer
   Scope: public docs, reference docs, smoke tests, usage examples, acceptance matrix
   Must not own: changing mode semantics unilaterally

Parallelization rule:
- Lane A must freeze the coding mode contract first.
- Lane B can start once Lane A defines the work-order schema and required context-pack fields.
- Lane C can start once Lane A defines mode names and activation mechanisms.
- Lane D should begin once Lane A/B freeze terminology and once Lane C selects the initial surfaces.

---

## First shippable milestone

The first shippable milestone is intentionally narrow:

“SOP-first coding mode with repo context pack and verification contract.”

This milestone must include:
- named coding modes,
- internal work-order normalization for coding tasks,
- a reusable repo context pack builder,
- a coding-mode response contract that foregrounds validation/evidence,
- CLI and ACP-compatible documentation,
- at least a small acceptance test matrix.

This milestone does not need:
- persistent coding task files,
- complex UI affordances,
- new background services,
- model-provider changes,
- complete gateway integration.

---

## Milestone coding map

### Milestone 0 — contract freeze and file map
Outcome:
- coding-runtime scope frozen
- initial surfaces chosen
- implementation areas mapped to concrete modules
Proof:
- implementation plan accepted
- file/module insertion points agreed

### Milestone 1 — coding mode contract
Outcome:
- canonical coding modes defined
- work-order schema defined
- SOP semantics frozen for v1
Proof:
- unit tests or prompt-builder tests cover mode parsing/defaulting
- docs reference mode names consistently

### Milestone 2 — repo context pack builder v1
Outcome:
- Hermes can collect a compact coding context pack before acting
- context pack warns on dirty repo and captures likely validation targets
Proof:
- tests cover branch/dirty-state and file discovery logic
- live smoke on a real repo produces context pack output

### Milestone 3 — verification/evidence contract v1
Outcome:
- coding-mode final responses consistently separate changes, validation, evidence, and risks
- “done” claims require explicit disclosure of what was or was not verified
Proof:
- tests or golden-output snapshots cover coding closeout formatting/instructions

### Milestone 4 — surface activation
Outcome:
- CLI can activate coding modes cleanly
- ACP/editor sessions can use the same semantics or defaults
Proof:
- slash command/profile activation works in CLI
- ACP docs and behavior map to the same mode semantics

### Milestone 5 — docs and product story
Outcome:
- public docs clearly position Hermes as a Copilot replacement for disciplined engineering work
- coding workflow docs are coherent across installation/ACP/reference surfaces
Proof:
- guide and reference docs render correctly
- examples are runnable/readable

### Milestone 6 — hardening and extension hooks
Outcome:
- multi-lane execution guidance exists
- profile/preset extension path is clear
- future gateway or artifact expansion points are documented
Proof:
- follow-up design notes or TODO anchors exist without blocking v1 release

---

## File-by-file implementation map

This map is intentionally concrete but still conservative. It prefers additive changes and minimal churn.

### Likely code files to modify

1. `agent/prompt_builder.py`
Purpose:
- inject coding-mode instructions and work-order/context-pack semantics into prompts without disturbing non-coding flows unnecessarily

2. `cli.py`
Purpose:
- route slash commands or session mode toggles into coding mode behavior
- expose mode state in the CLI session if needed

3. `hermes_cli/commands.py`
Purpose:
- define any new slash commands or aliases for coding modes

4. `acp_adapter/` (specific file(s) to determine during implementation)
Purpose:
- ensure ACP sessions can activate or default into the same coding semantics
- keep editor UX aligned with CLI behavior

5. `run_agent.py`
Purpose:
- only if needed for lightweight mode/session metadata propagation
- avoid major loop changes

6. new helper module(s), likely under one of:
- `agent/`
- `hermes_cli/`
- or a small new `coding_runtime/` package if clarity justifies it
Purpose:
- work-order normalization
- repo context pack generation
- coding closeout formatting/policy helpers

### Likely docs files to modify or add

1. Create `website/docs/guides/hermes-as-copilot-replacement.md`
Purpose:
- tell the product story and explain why Hermes is different

2. Create `website/docs/guides/coding-with-hermes.md`
Purpose:
- practical day-to-day workflow guide

3. Create `website/docs/reference/coding-modes.md`
Purpose:
- reference for modes, activation, and expected behavior

4. Modify `website/docs/index.md`
Purpose:
- add a clearer path into coding-runtime workflows

5. Modify `docs/acp-setup.md`
Purpose:
- explain how ACP fits the coding-runtime profile rather than describing only a generic coding agent

6. Possibly modify `website/docs/reference/profile-commands.md`
Purpose:
- if profiles/presets become part of activation guidance

### Likely tests to add

1. Prompt/mode tests
- coding mode normalization
- default mode behavior
- mode-specific instruction injection

2. Context-pack tests
- non-git workspace
- clean git workspace
- dirty git workspace
- file discovery heuristics
- validation command hint derivation

3. CLI command tests
- slash command parsing
- mode switching semantics

4. Golden-output or formatter tests
- final response sections for coding mode
- explicit not-verified disclosure behavior

---

## Proposed internal contracts

These contracts should be frozen early to prevent churn.

### Contract A — coding mode names
Canonical mode names:
- `implement`
- `debug`
- `review`
- `test`
- `ship`
- `explain`

Optional aliases can exist later, but docs and code should speak canonically.

### Contract B — coding work order
Suggested internal structure:
- `objective: str`
- `task_kind: Literal[...]`
- `scope_boundaries: list[str]`
- `likely_targets: list[str]`
- `constraints: list[str]`
- `validation_targets: list[str]`
- `done_definition: list[str]`
- `authority_policy: Literal["read-only", "edit-ok", "commit-ok", "push-ok"]`
- `risk_notes: list[str]`

This can be an internal dict/dataclass/Pydantic-style model depending on the surrounding code style.

### Contract C — repo context pack
Suggested fields:
- `workspace_summary`
- `repo_root`
- `branch_name`
- `dirty_state`
- `dirty_warning`
- `framework_hints`
- `relevant_files`
- `relevant_tests`
- `relevant_docs`
- `validation_hints`
- `open_questions`

Keep it compact and deterministic enough for test coverage.

### Contract D — coding closeout structure
Suggested logical sections for coding-mode final outputs:
- `what_changed`
- `why`
- `validation`
- `evidence`
- `risks`
- `next_safe_action`

The exact rendering can differ by surface, but semantics should remain stable.

---

## Task breakdown

The tasks below are intentionally bite-sized and implementation-friendly.

### Task 1: Freeze activation strategy

Objective:
Decide how coding modes are activated in v1 so implementation does not sprawl.

Files:
- Modify: `docs/plans/2026-04-07-hermes-copilot-replacement-design.md` only if a small clarification is needed
- Modify: this plan if decisions need to be recorded

Work:
1. Decide whether v1 uses slash commands, profile presets, implicit heuristics, or a hybrid.
2. Recommendation: hybrid
   - slash commands for explicit session mode switching in CLI
   - ACP guidance for equivalent behavior
   - no mandatory new profile primitive in v1
3. Record chosen activation mechanism in implementation notes.

Verification:
- plan text reflects one clear activation story

Commit:
- docs-only commit if changed

### Task 2: Add a lightweight coding-runtime module boundary

Objective:
Create a minimal home for coding-mode contracts so they don’t get smeared across unrelated modules.

Files:
- Create: likely `agent/coding_runtime.py` or `agent/coding_runtime/` package
- Modify: imports in affected callers

Work:
1. Add mode enums/constants.
2. Add work-order normalization helpers.
3. Add closeout/response helper stubs if useful.
4. Keep code additive and small.

Verification:
- unit tests import and use the new module cleanly
- no circular imports introduced

Commit:
- `feat: add coding runtime contracts`

### Task 3: Implement coding work-order normalization

Objective:
Turn raw user coding requests plus session state into a structured work order.

Files:
- Modify/Create: coding-runtime module from Task 2
- Modify: prompt builder integration point(s)
- Test: new unit tests under `tests/`

Work:
1. Add a helper that takes user intent + optional explicit mode and returns normalized fields.
2. Define sensible defaults:
   - default coding mode likely `implement` or inferred by instruction verbs
   - unresolved uncertainty becomes open questions/constraints, not hallucinated certainty
3. Keep heuristics transparent and overrideable.

Verification:
- tests for explicit mode
- tests for inferred debug/review/test cases
- tests for default fallback

Commit:
- `feat: normalize coding work orders`

### Task 4: Implement repo context pack builder v1

Objective:
Build the minimum useful repo-aware context summary for coding tasks.

Files:
- Modify/Create: coding-runtime helper module(s)
- Possibly use existing utilities if available
- Test: new context-pack tests

Work:
1. Detect whether cwd is inside a git repo.
2. Capture repo root, branch, and dirty state.
3. Derive likely relevant files from request keywords or nearby docs/files heuristics.
4. Derive likely validation hints from project structure when feasible.
5. Include docs/context-file discovery (`AGENTS.md`, local docs, etc.) conservatively.
6. Return a compact structure, not raw command dumps.

Verification:
- test non-git workspace behavior
- test clean git workspace behavior
- test dirty workspace warning
- test compact output shape

Commit:
- `feat: add repo context pack builder`

### Task 5: Integrate coding mode + context pack into prompt assembly

Objective:
Make the agent actually use the work order and context pack during coding sessions.

Files:
- Modify: `agent/prompt_builder.py`
- Possibly modify: `run_agent.py` or mode/session metadata plumbing if required
- Test: prompt-builder tests or snapshot tests

Work:
1. Inject coding-mode semantics only when the session is in coding mode.
2. Include compact work-order and context-pack summaries.
3. Add explicit verification expectations to coding-mode instructions.
4. Avoid bloating prompts for non-coding sessions.

Verification:
- prompt-builder tests show coding instructions present only when expected
- non-coding prompts remain stable enough

Commit:
- `feat: integrate coding runtime prompt contract`

### Task 6: Add CLI activation surface

Objective:
Allow users to intentionally switch into coding modes in CLI.

Files:
- Modify: `hermes_cli/commands.py`
- Modify: `cli.py`
- Test: CLI command parsing tests

Work:
1. Add one or more slash commands to activate/switch coding modes.
2. Keep command semantics simple.
   Recommendation:
   - `/mode <implement|debug|review|test|ship|explain>`
   or
   - dedicated aliases like `/debug`, `/review`, etc. layered on top of one internal mode setter
3. Surface current mode state in session feedback if useful.

Verification:
- command registry tests
- CLI dispatch tests
- invalid mode handling test

Commit:
- `feat: add coding mode CLI activation`

### Task 7: Align ACP/editor behavior

Objective:
Ensure ACP users get the same coding-runtime semantics without a second mental model.

Files:
- Modify: relevant `acp_adapter/` entrypoints/config
- Modify: `docs/acp-setup.md`
- Test: ACP-focused smoke test if feasible

Work:
1. Determine how ACP sessions enter coding mode by default or through explicit instruction.
2. Reuse the same mode/work-order/context-pack pipeline.
3. Document the behavior clearly without promising unsupported editor UI magic.

Verification:
- ACP docs are accurate
- ACP path exercises the same coding-runtime code path where possible

Commit:
- `feat: align ACP with coding runtime modes`
  or doc-only if behavior already aligns and only docs changed

### Task 8: Add coding closeout / verification contract

Objective:
Make coding outputs honest, concise, and evidence-backed.

Files:
- Modify/Create: coding-runtime helper module(s)
- Possibly modify: display/formatting helpers if needed
- Test: formatter/golden-output tests

Work:
1. Add a helper or instruction contract that shapes final coding responses.
2. Ensure it distinguishes:
   - what changed
   - validation performed / not performed
   - evidence basis
   - unresolved risks
3. Ensure “not verified” is treated as a first-class honest outcome, not hidden.

Verification:
- tests for verified path
- tests for could-not-run-validation path
- tests for no-change review/debug path

Commit:
- `feat: add coding verification closeout contract`

### Task 9: Publish the user-facing story

Objective:
Make the Copilot replacement positioning visible and understandable.

Files:
- Create: `website/docs/guides/hermes-as-copilot-replacement.md`
- Create: `website/docs/guides/coding-with-hermes.md`
- Create: `website/docs/reference/coding-modes.md`
- Modify: `website/docs/index.md`
- Possibly modify: `website/docs/reference/profile-commands.md`

Work:
1. Explain the difference between autocomplete and coding-runtime workflows.
2. Document coding modes and expected behavior.
3. Show CLI and ACP examples.
4. Keep claims honest and aligned with actual shipped behavior.

Verification:
- docs build passes if docs build is available
- link paths are valid
- examples match real commands

Commit:
- `docs: add coding runtime and Copilot replacement guides`

### Task 10: Add acceptance tests and smoke checklist

Objective:
Prove the first slice works on real repo-backed tasks.

Files:
- Modify/Create: relevant tests under `tests/`
- Create/Modify: optional internal smoke checklist doc under `docs/` if helpful

Work:
1. Add targeted tests for mode activation, work-order normalization, context-pack output, and closeout contracts.
2. Create a manual smoke checklist for one or two real repos.
3. Verify dirty-worktree handling and validation disclosure behavior.

Verification:
- targeted test suite passes
- manual smoke checklist can be executed reproducibly

Commit:
- `test: add coding runtime acceptance coverage`

---

## Suggested command and UX shape

Recommended v1 activation UX:

CLI:
- `/mode implement`
- `/mode debug`
- `/mode review`
- `/mode test`
- `/mode ship`
- `/mode explain`

Optional sugar later:
- `/debug`
- `/review`
- `/ship`

ACP:
- preserve natural language usage
- document explicit recommended prompts
- optionally adopt the same mode semantics internally

Reasoning:
- one canonical activation command reduces command sprawl
- dedicated aliases can be added later if users actually want them

---

## Testing strategy

### Unit tests
- work-order normalization
- mode parsing/defaulting
- repo context pack output
- closeout contract formatting/sections

### Integration-ish tests
- CLI command activation
- prompt-builder receives coding mode metadata
- ACP path does not bypass the coding-runtime contract

### Manual smoke tests
Use one clean git repo and one dirty git repo.

Smoke checklist:
1. Start a coding task in default/implement mode.
2. Confirm repo/branch/dirty info appears in working context behavior.
3. Ask for a debug task; confirm debug semantics emphasize evidence-first behavior.
4. Complete a small change; confirm final output includes validation disclosure.
5. Repeat in ACP if available.

---

## Acceptance proof requirements

For v1 to count as done:
1. There is one canonical coding-mode activation path in CLI.
2. Hermes can normalize coding requests into a work-order structure.
3. Hermes can build a compact repo context pack and warn on dirty state.
4. Coding-mode prompts clearly demand evidence-backed completion.
5. Final coding outputs disclose validation status and risks.
6. Public docs explain the workflow without overclaiming editor parity.
7. Tests cover the happy path and at least key failure/edge cases.

What does not count as done:
- adding docs only, with no behavior change
- adding commands only, with no prompt/context/verification semantics
- claiming “Copilot replacement” because Hermes can edit files in ACP
- vague output formatting changes with no evidence policy behind them

---

## Parallel execution risks

1. Terminology drift
Risk:
- docs say one thing, commands another
Control:
- freeze canonical mode names early

2. Prompt coupling bloat
Risk:
- coding-mode instructions leak into all sessions
Control:
- explicit mode gating and tests

3. Heuristic overreach in context-pack builder
Risk:
- giant noisy context dumps
Control:
- compact schema, deterministic limits, narrow-first implementation

4. Surface divergence
Risk:
- CLI and ACP behave differently enough to confuse users
Control:
- shared internal contracts, docs reviewed together

5. Verification theater
Risk:
- polished summaries that still do not prove anything
Control:
- explicit validation/evidence fields and tests for “not verified” paths

---

## Recommended implementation order

If executed serially, do it in this order:
1. Task 1 — activation strategy freeze
2. Task 2 — coding-runtime module boundary
3. Task 3 — work-order normalization
4. Task 4 — repo context pack builder
5. Task 5 — prompt integration
6. Task 8 — closeout/verification contract
7. Task 6 — CLI activation
8. Task 7 — ACP alignment
9. Task 9 — docs
10. Task 10 — acceptance coverage and smoke checklist

Why this order:
- contracts first
- context and prompt semantics second
- surfaces third
- docs/testing after behavior stabilizes

---

## Next-step recommendation

After this plan, the best immediate move is not to write more design prose. It is to do a read-only codebase audit for the exact insertion points and then turn Tasks 2–8 into file-specific implementation edits.

Recommended next document after this one:
- an execution tracker or issue-ready anchor doc for the coding-runtime milestone
- or begin implementation directly if the file map is already sufficiently clear
