# Hermes as a Copilot Replacement — Execution Tracker

Goal: convert the implementation plan into file-specific execution steps based on a read-only codebase audit. This tracker is intentionally concrete: each task maps to observed insertion points in the current Hermes repo so implementation can proceed with minimal wandering.

Related docs:
- `docs/plans/2026-04-07-hermes-copilot-replacement-design.md`
- `docs/plans/2026-04-07-hermes-copilot-replacement-implementation-plan.md`

Audit date: 2026-04-07
Audit scope: read-only inspection of current Hermes repo

---

## Audit summary

The repo already has three strong seams for this feature:

1. Prompt seam
- `run_agent.py::_build_system_prompt()` already assembles layered prompt state.
- It already injects tool-aware guidance, memory, skills, context files, and platform hints.
- This is the cleanest place to append coding-runtime guidance blocks when a coding mode is active.

2. Surface/session seam
- CLI session creation already passes `ephemeral_system_prompt`, `prefill_messages`, `platform`, `session_id`, and toolset config into `AIAgent` from `cli.py` around line 2237.
- ACP session creation already centralizes agent construction in `acp_adapter/session.py::_make_agent()`.
- Both surfaces therefore have a natural place to carry coding-mode session state into the agent.

3. Slash-command seam
- CLI command registration is centralized in `hermes_cli/commands.py::COMMAND_REGISTRY`.
- CLI slash dispatch is centralized in `cli.py::process_command()` around line 4177.
- ACP headless slash commands are centralized in `acp_adapter/server.py::_SLASH_COMMANDS` and `_handle_slash_command()`.
- This makes `/mode`-style activation feasible without scattered edits.

Conclusion:
- The coding-runtime slice should be implemented as a lightweight shared module plus narrow changes in `run_agent.py`, `cli.py`, `hermes_cli/commands.py`, `acp_adapter/session.py`, and `acp_adapter/server.py`.
- No major redesign of the agent loop is required for v1.

---

## Recommended new module boundary

Create a small shared module under `agent/` rather than a brand-new top-level package.

Recommended file:
- `agent/coding_runtime.py`

Why:
- The prompt and session behavior already live around `agent/` + `run_agent.py`.
- `agent/` is already used for cross-cutting runtime helpers (`prompt_builder.py`, `context_references.py`, etc.).
- This minimizes import churn and reduces the risk of circular dependencies.

Recommended contents of `agent/coding_runtime.py`:
- canonical mode constants
- work-order normalization helpers
- repo context pack builder helpers
- compact rendering helpers for prompt injection
- validation/evidence closeout helpers or section-contract text helpers

Keep v1 implementation stdlib-only where possible.

---

## File-specific insertion points

### 1. `agent/coding_runtime.py` — new

Status:
- does not exist yet

Use for:
- Task 2: coding-runtime module boundary
- Task 3: work-order normalization
- Task 4: repo context pack builder
- Task 8: closeout/verification contract helpers

Recommended API surface:
- `CODING_MODE_NAMES = (...)`
- `normalize_coding_mode(text: str | None) -> str | None`
- `infer_coding_mode(user_message: str) -> str`
- `build_work_order(user_message: str, requested_mode: str | None, authority_policy: str = "edit-ok") -> dict`
- `build_repo_context_pack(cwd: str | None = None, user_message: str | None = None) -> dict`
- `render_work_order_for_prompt(work_order: dict) -> str`
- `render_context_pack_for_prompt(context_pack: dict) -> str`
- `build_coding_system_block(mode: str, work_order: dict, context_pack: dict) -> str`
- `build_closeout_contract_block() -> str`

Implementation notes:
- Repo context pack should use subprocess/stdlib for git discovery to avoid depending on tool calls.
- Framework hints can start from marker files only:
  - `package.json`
  - `pyproject.toml`
  - `requirements.txt`
  - `Cargo.toml`
  - `go.mod`
- Dirty state can be derived from `git status --porcelain`.
- Branch can be derived from `git rev-parse --abbrev-ref HEAD`.
- Validation hints can be conservative marker-based guesses, not full command synthesis magic.

---

### 2. `run_agent.py`

Observed insertion points:
- `AIAgent.__init__` around lines 441–529 already accepts session-wide runtime knobs like `ephemeral_system_prompt`, `prefill_messages`, `platform`, `skip_context_files`.
- `_build_system_prompt()` around lines 2595–2763 assembles the cached system prompt.
- API-call-time system prompt composition occurs around lines 6487–6495 and 7018–7033 where ephemeral system prompt and prefill messages are injected.

Use for:
- Task 5: integrate coding mode + context pack into prompt assembly
- possibly lightweight state plumbing for Task 3/4/8

Recommended edits:
1. Add optional constructor fields to `AIAgent`:
- `coding_mode: str | None = None`
- `coding_work_order: dict | None = None`
- `coding_context_pack: dict | None = None`

2. Store them on `self` in `__init__`.

3. In `_build_system_prompt()`:
- after tool-use guidance and before memory/context files is the cleanest spot to inject a coding-runtime block when `self.coding_mode` is set.
- append a compact block rendered from `agent.coding_runtime` helpers.

4. Keep the block gated:
- no coding block when `coding_mode` is absent
- non-coding sessions should remain unaffected

5. Consider a small helper in `run_agent.py` or `agent/coding_runtime.py` to rebuild work-order/context-pack lazily if only `coding_mode` is present.

Why this spot:
- `_build_system_prompt()` is the canonical place where stable session behavior is frozen.
- The resulting prompt is cached, which matches the desired “session mode” semantics.

Caution:
- if mode changes mid-session, cached prompt invalidation will be required.
- reuse `_invalidate_system_prompt()` rather than inventing new cache behavior.

---

### 3. `cli.py`

Observed insertion points:
- CLI agent construction happens around lines 2237–2275.
- Slash dispatch lives in `process_command()` around lines 4177–4456.
- Main conversation path calls `self.agent.run_conversation(...)` around line 6362.

Use for:
- Task 6: CLI activation surface
- lightweight mode state storage
- session-to-agent propagation for Task 5

Recommended edits:
1. Add CLI session fields, likely initialized on the CLI instance:
- `self.coding_mode = None`
- optionally `self.coding_authority_policy = "edit-ok"`

2. In agent construction around line 2237:
- compute work order/context pack at agent creation time when `self.coding_mode` is set
- pass `coding_mode`, `coding_work_order`, and `coding_context_pack` into `AIAgent`

3. Add a `/mode` command handler in `process_command()`:
- branch near other configuration/session commands
- recommended handler name: `_handle_mode_command(cmd_original)`

4. Add the handler method in `cli.py`:
- `/mode` with no args shows current mode
- `/mode off` clears coding mode
- `/mode <implement|debug|review|test|ship|explain>` sets mode
- after changing mode:
  - update CLI state
  - rebuild or replace `self.agent` with updated coding metadata, or mutate agent state then call `_invalidate_system_prompt()`

Recommended implementation preference:
- mutate current agent state and invalidate prompt if safe
- if agent recreation is cleaner/safer, do that using the existing agent creation path

5. Optional but useful:
- surface current coding mode in `/status`-like info or banner later, but not required for v1

Caution:
- `process_command()` is already large, so add one small handler method rather than inlining logic.
- Keep new logic parallel to existing `/reasoning`, `/voice`, `/model` patterns.

---

### 4. `hermes_cli/commands.py`

Observed insertion points:
- `COMMAND_REGISTRY` starts near line 48.
- registry-driven alias/help/autocomplete generation already exists.

Use for:
- Task 6: CLI activation surface

Recommended edits:
- Add one canonical command entry:
  - `CommandDef("mode", "Show or set coding mode", "Configuration", args_hint="[implement|debug|review|test|ship|explain|off]")`

Optional later:
- alias `("m",)` only if you really want it; probably skip for clarity
- dedicated sugar commands should wait until usage justifies them

Why this is enough:
- autocomplete/help/registry behavior updates automatically
- no extra per-surface registration churn for the CLI side

---

### 5. `acp_adapter/session.py`

Observed insertion points:
- `SessionState` dataclass at lines 46–56 currently tracks `session_id`, `agent`, `cwd`, `model`, `history`, `cancel_event`.
- `_make_agent()` at lines 410–461 is the ACP agent factory seam.

Use for:
- Task 7: ACP alignment
- shared mode/session state for editor sessions

Recommended edits:
1. Extend `SessionState` with:
- `coding_mode: str = ""`
- optionally `coding_authority_policy: str = "edit-ok"`

2. Update `_make_agent()` signature to accept:
- `coding_mode: str | None = None`

3. In `_make_agent()`, when coding mode exists:
- build work order/context pack from the ACP cwd
- pass them into `AIAgent`

4. Ensure `create_session()`, `fork_session()`, and restore flows preserve `coding_mode`.

Why here:
- ACP should not invent a second mode system inside `server.py`.
- Session state belongs in the session manager, not ad hoc inside the request handler.

---

### 6. `acp_adapter/server.py`

Observed insertion points:
- prompt execution uses `agent.run_conversation(...)` around lines 363–370.
- headless ACP slash commands live in `_SLASH_COMMANDS` and `_handle_slash_command()` around lines 414–452.
- model switching already recreates the session agent in the ACP path around lines 482–489.

Use for:
- Task 7: ACP alignment
- ACP-side mode command support

Recommended edits:
1. Extend `_SLASH_COMMANDS` with:
- `"mode": "Show or set current coding mode"`

2. Add `_cmd_mode(self, args: str, state: SessionState) -> str`.

3. In `_handle_slash_command()`, route `mode` to `_cmd_mode`.

4. `_cmd_mode` should:
- show current mode if no args
- clear on `off`
- validate canonical mode names
- set `state.coding_mode`
- recreate `state.agent` through `self.session_manager._make_agent(...)` similarly to model switching
- persist session via `self.session_manager.save_session(state.session_id)`

Why this is the right ACP surface:
- ACP already has a mini slash-command layer separate from CLI
- the model-switch pattern already proves agent recreation is acceptable in this layer

Caution:
- ACP currently defaults to generic prompting; don’t silently force coding mode for all ACP sessions in v1 unless you explicitly want that behavior
- safer v1: support explicit `/mode` plus docs guidance

---

### 7. `agent/prompt_builder.py`

Observed insertion points:
- file already owns system-prompt building primitives like `build_skills_system_prompt()`, `load_soul_md()`, and `build_context_files_prompt()`.
- current tests exist under `tests/agent/test_prompt_builder.py`.

Use for:
- optional extraction of prompt text helpers for Task 5 and Task 8

Recommended role:
- keep `run_agent.py::_build_system_prompt()` as the orchestrator
- optionally add text-only helper(s) here if you want coding-runtime prompt block rendering to live beside other prompt utilities

Recommendation:
- do not overload `prompt_builder.py` with repo inspection logic
- if needed, only put render helpers here, not git/project discovery

---

## Testing insertion points

### 8. `tests/agent/test_prompt_builder.py`

Observed:
- already covers context-file and prompt-builder behavior extensively

Use for:
- Task 5 tests if prompt text rendering logic lands in `agent/prompt_builder.py`
- otherwise add adjacent tests for coding prompt block rendering

Potential test cases:
- coding block absent in non-coding sessions
- coding block includes canonical mode name
- coding block includes validation/evidence contract text

---

### 9. New test file: `tests/agent/test_coding_runtime.py`

Recommended new file.

Use for:
- Task 2/3/4/8 unit tests

Test matrix:
1. mode normalization
- explicit valid mode passes through
- invalid mode rejected or normalized to `None`

2. mode inference
- “fix bug” -> `debug`
- “review this diff” -> `review`
- “write tests” -> `test`
- generic change request -> `implement`

3. work-order normalization
- objective captured
- done/constraints fields populated conservatively

4. repo context pack
- non-git directory
- git repo clean branch
- git repo dirty state warning
- marker-file framework hints

5. closeout contract helpers
- verified and not-verified wording stays explicit

---

### 10. `tests/test_cli_prefix_matching.py`

Observed:
- already exercises `HermesCLI.process_command()` dispatch behavior

Use for:
- Task 6 command routing tests

Add cases:
- `/mode` shows current value
- `/mode debug` dispatches to mode handler
- invalid `/mode banana` reports valid choices
- `/mo` uniquely resolves to `/mode` if no ambiguity is introduced

---

### 11. Possibly new test file: `tests/test_cli_mode_command.py`

Recommended if `/mode` handler grows beyond trivial dispatch.

Use for:
- state mutation and agent refresh behavior in CLI

Test cases:
- mode set updates CLI state
- mode off clears state
- setting mode invalidates/rebuilds agent prompt state

---

### 12. `tests/acp/test_server.py`

Observed:
- already has `TestSlashCommands`
- already tests ACP slash interception and stateful command behavior

Use for:
- Task 7 ACP mode command tests

Add cases:
- `/mode` lists current mode
- `/mode debug` updates `SessionState.coding_mode`
- `/mode off` clears mode
- invalid mode returns validation error
- slash command is intercepted without calling the LLM

---

## Best v1 implementation strategy

### Session-state strategy

Preferred strategy:
- store canonical mode on the session object/surface (`HermesCLI` or `SessionState`)
- derive work order + context pack when building/rebuilding the agent
- store derived data on `AIAgent` for prompt injection

Why:
- keeps the source of truth small
- avoids re-parsing every turn unless needed
- matches current cached system prompt architecture

### Prompt strategy

Preferred strategy:
- inject coding-runtime behavior as a gated system-prompt block
- do not mutate user messages for this feature in v1

Why:
- cleaner with current caching design
- easier to test
- avoids surprising transcript behavior

### ACP strategy

Preferred strategy:
- explicit `/mode` support first
- docs can recommend using `/mode implement` at session start for coding-focused tasks

Why:
- minimal risk
- avoids breaking generic ACP usage
- still proves shared behavior across CLI and ACP

---

## Concrete implementation order

1. Create `agent/coding_runtime.py`
2. Add unit tests in `tests/agent/test_coding_runtime.py`
3. Extend `AIAgent` in `run_agent.py` to accept coding metadata
4. Inject coding block in `_build_system_prompt()`
5. Add `/mode` to `hermes_cli/commands.py`
6. Add CLI mode handling in `cli.py`
7. Extend ACP `SessionState` and `_make_agent()` in `acp_adapter/session.py`
8. Add ACP `/mode` in `acp_adapter/server.py`
9. Add/extend tests in `tests/test_cli_prefix_matching.py`, `tests/test_cli_mode_command.py`, and `tests/acp/test_server.py`
10. Update docs after behavior is real

---

## Acceptance checklist for implementation phase

Before calling the feature slice done, verify:
- CLI supports `/mode <name>` and `/mode off`
- ACP supports `/mode <name>` and `/mode off`
- agent prompt changes only when coding mode is active
- repo context pack captures branch/dirty-state in git repos
- final coding guidance explicitly requires validation disclosure
- tests cover non-coding fallback, CLI mode switching, ACP mode switching, and context-pack edge cases

---

## Notes on scope control

Do not do these in the first implementation slice unless required:
- no new persistent profile type
- no gateway-wide mode system
- no autocomplete/editor inline features
- no heavy repo indexing
- no tool-call-based context pack builder inside the agent loop
- no giant command taxonomy beyond `/mode`

This tracker should be treated as the implementation handoff for Tasks 2–8.