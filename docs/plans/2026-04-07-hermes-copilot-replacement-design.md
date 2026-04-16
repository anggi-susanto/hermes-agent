# Hermes as a Copilot Replacement — Design Doc

> For Hermes: this is a design package for making Hermes replace Copilot for engineering work, not integrate with Copilot. Keep Hermes as the full operating system for coding work: intake, context assembly, implementation, verification, evidence, and handoff. Do not reduce this to autocomplete, IDE inline suggestions, or provider wiring.

Goal: define how Hermes can replace Copilot as the default engineering assistant by providing a more disciplined, evidence-backed, SOP-driven coding workflow across CLI, ACP/editor surfaces, and remote runtimes.

Architecture: treat Copilot replacement as an operating-model problem, not a model-vendor problem. Hermes should own the full work loop: normalize requests into structured work orders, assemble repo/runtime context automatically, execute constrained coding workflows, verify outcomes with runtime proof, and present concise evidence-backed results. The first milestone should improve workflow quality without requiring net-new inference providers or IDE-only assumptions.

Tech stack: existing Hermes CLI/ACP/gateway/tool architecture, skills + memory systems, terminal/file/search/read/patch tools, subagents/delegation, context files, profile/toolset controls, and existing docs/website surfaces under `~/.hermes/hermes-agent/`.

Related docs and repo context:
- `README.md`
- `AGENTS.md`
- `docs/acp-setup.md`
- `website/docs/index.md`
- `docs/plans/2026-04-01-paperclip-board-provider-architecture.md`
- `docs/plans/2026-04-01-paperclip-board-provider-implementation-plan.md`

---

## 1. Problem statement

Albert wants Hermes to replace Copilot, not wrap or embed Copilot. The desired replacement is not “Hermes but with IDE autocomplete.” The target is the part of Copilot workflow that feels operationally useful today: a reliable engineering helper with decent context, fast task execution, and a recognizable SOP. Hermes should beat that by being more disciplined about scope, evidence, verification, and remote execution.

This means the design target is:
- not an inference-provider integration,
- not an IDE-specific feature set,
- not a thin “generate code” surface,
- but a coding runtime profile that turns Hermes into a governed engineering operator.

If successful, Hermes should feel better than Copilot on real work because it can do all of these in one loop:
- understand the task,
- inspect the actual repo/runtime,
- edit the right files,
- run validation,
- explain what changed,
- preserve evidence,
- and refuse to bluff completion.

---

## 2. Product thesis

Copilot is strongest at fast code completion and lightweight generation. Hermes can win on end-to-end engineering execution.

Positioning:
- Copilot class product: “suggest code in context.”
- Hermes replacement target: “complete engineering work in context with proof.”

The replacement strategy is therefore:
1. make Hermes excellent at coding workflows first,
2. expose that excellence through consistent modes and UX,
3. optionally add editor-native surfaces later,
4. never anchor the design on vendor-specific Copilot parity.

Short version:
Hermes should replace Copilot by becoming a coding operating system, not by mimicking autocomplete.

---

## 3. Design principles

1. Hermes owns the full loop
   - intake
   - context assembly
   - planning
   - execution
   - verification
   - evidence-backed reporting

2. Runtime proof beats prose
   - no task is “done” because the model says so
   - done requires repo/runtime evidence when tools are available

3. Minimal-safe-change by default
   - prefer narrow edits
   - avoid broad refactors unless requested
   - respect dirty worktrees and unrelated changes

4. Repo-aware, not IDE-bound
   - the primary abstraction is workspace/repo/runtime context
   - editor integrations are convenience surfaces, not the center of the system

5. SOP first, magic second
   - consistency comes from structured workflows and policy
   - model quality helps, but governance quality matters more

6. Advisory reasoning, verified outcome
   - analysis can be heuristic
   - final conclusions should cite actual files, diffs, commands, tests, logs, or screenshots

7. Multi-lane when useful
   - hard tasks should support orchestrator + implementer + reviewer + tester patterns
   - Hermes should scale beyond single-thread pair programming

---

## 4. Non-goals

Non-goals for the first real replacement milestone:
- building IDE inline token-by-token autocomplete parity
- recreating every Copilot UI affordance
- introducing Copilot-specific auth or provider dependencies
- replacing the general inference-provider subsystem
- auto-deploying code changes without explicit policy
- solving all planning/review/shipping workflows in one release

The first milestone should prove that Hermes can handle real coding tasks better than a Copilot-style assistant in a repo-backed workflow.

---

## 5. User promise

When Hermes is used in coding mode, the user should be able to expect:
- Hermes verifies the active workspace before touching code.
- Hermes assembles relevant context without making the user re-explain the repo.
- Hermes uses a consistent SOP for implementation, debugging, review, and shipping.
- Hermes validates changes before claiming success.
- Hermes produces concise evidence-backed summaries.
- Hermes can work locally, in ACP/editor sessions, or against remote runtimes.

The emotional promise is important too:
“Less babysitting than Copilot. Less bluffing. More done.”

---

## 6. Proposed system: Hermes Coding Runtime Profile

The core proposal is a new product/profile concept:

Hermes Coding Runtime Profile

This is a set of workflows, policies, and reusable components that specialize Hermes for engineering work. It is not a single model, tool, or provider. It is a disciplined operating profile spanning CLI, ACP/editor sessions, and remote workspaces.

The profile has five layers:
1. Intake contract
2. Context pack builder
3. Execution SOP engine
4. Verification/evidence engine
5. UX surfaces and mode routing

### 6.1 Intake contract

User requests for coding work should be normalized into a structured work order.

Suggested normalized shape:
- objective
- task kind (`implement`, `debug`, `review`, `test`, `ship`, `explain`)
- scope boundaries
- likely files/modules
- constraints
- validation target
- done definition
- risk notes
- authority policy (read-only, edit-ok, commit-ok, push-ok)

Why this matters:
- reduces ambiguity
- preserves consistent SOP behavior
- makes delegation easier
- creates explicit boundaries for autonomous work

### 6.2 Context pack builder

This is the key feature that makes Hermes feel “repo-aware” instead of generic.

For coding tasks, Hermes should automatically assemble a context pack that may include:
- workspace target identity
- branch and dirty-state snapshot
- package/framework/runtime detection
- relevant source files
- relevant tests
- recent git diff or blame context when useful
- nearby docs/plans/ADRs/incidents
- runtime logs or failing output if debugging
- active context files (`SOUL.md`, `AGENTS.md`, local project docs)
- cross-session recall when the user references prior work

Output should be compact and task-shaped, not a raw dump.

Suggested structure:
- repo summary
- active branch + dirty-state warning
- files likely involved
- relevant docs/issues/plans
- validation commands or test entrypoints
- open risks/unknowns

This layer should exist whether Hermes is used from CLI, ACP/editor, or a messaging surface.

### 6.3 Execution SOP engine

Hermes should expose stable coding modes with distinct SOPs.

Suggested first-class modes:
- implement
- debug
- review
- test
- ship
- explain

These can later map to slash commands, profile presets, ACP shortcuts, or internal prompt templates.

#### Implement SOP
1. Verify workspace target.
2. Inspect branch + dirty state.
3. Read relevant files/docs/tests.
4. Build a minimal plan.
5. Patch the smallest safe surface.
6. Run narrow validation.
7. Summarize changes + proof.
8. Commit/push only if policy allows.

#### Debug SOP
1. Collect failing evidence first.
2. Identify likely root causes.
3. Inspect the real code path.
4. Patch the smallest plausible fix.
5. Re-run the failing case.
6. Report root cause, fix, and evidence.

#### Review SOP
1. Identify the exact diff/branch/PR/worktree.
2. Read changed files with local context.
3. Check contract alignment, risk, and regressions.
4. Run or inspect available validations.
5. Produce findings ordered by severity.
6. Distinguish verified issues from suspicions.

#### Test SOP
1. Determine the narrowest useful validation.
2. Generate missing tests only if needed.
3. Run focused checks before broad suites.
4. Record failures and interpretation.
5. Only recommend larger suites when signal justifies cost.

#### Ship SOP
1. Confirm scope is complete.
2. Re-run final targeted validation.
3. Produce concise closeout summary.
4. Commit using policy-compliant message.
5. Push only when user/policy allows.
6. Capture any rollout caveats or follow-up tasks.

### 6.4 Verification and evidence engine

This is where Hermes should surpass Copilot decisively.

Every coding result should separate:
- model inference/opinion
- observed repo/runtime evidence

Suggested proof sources:
- file diffs
- command outputs
- test results
- logs
- screenshots/browser artifacts when relevant
- git status/branch proof
- built artifacts

Suggested result schema:
- what changed
- why it changed
- validation performed
- evidence summary
- unresolved risks
- next safe action

A task should not be marked complete if the relevant verification step was skipped, failed, or was impossible and not disclosed.

### 6.5 UX surfaces and mode routing

The same underlying coding runtime profile should be accessible from multiple surfaces:
- CLI session
- ACP/editor workflows
- gateway/messaging workflows
- remote runtime / SSH-backed workspaces

Surface-specific UX can differ, but the workflow semantics should remain stable.

Potential command surface:
- `/impl`
- `/debug`
- `/review`
- `/test`
- `/ship`
- `/explain`

These do not need to be literal slash commands on day one. The key requirement is stable mode semantics.

---

## 7. Why this is better than Copilot

Hermes should win on:
1. execution discipline
2. verification honesty
3. remote/runtime flexibility
4. multi-step task ownership
5. memory + procedural learning
6. multi-agent orchestration

Comparison:

1. Code suggestion
- Copilot: strong
- Hermes target: adequate to strong

2. Task completion
- Copilot: medium
- Hermes target: strong

3. Repo governance
- Copilot: weak to medium
- Hermes target: strong

4. Evidence-backed conclusions
- Copilot: weak
- Hermes target: strong

5. Remote work execution
- Copilot: weak
- Hermes target: strong

6. Repeatable SOPs
- Copilot: medium
- Hermes target: strong

7. Cross-session continuity
- Copilot: weak
- Hermes target: strong

The key insight:
Hermes does not need to out-autocomplete Copilot to replace it for serious engineering work.
It needs to out-operate it.

---

## 8. Required subsystems and proposed implementation areas

This section maps the design to likely Hermes code/doc ownership areas inside `~/.hermes/hermes-agent/`.

### 8.1 Coding profile / mode definitions

Need:
- a named coding-oriented profile or mode layer
- mode-specific SOP templates and policy defaults

Likely touchpoints:
- CLI command/profile configuration surfaces
- ACP/editor defaults and toolset bundles
- docs for profile commands and coding usage

Possible additions:
- `website/docs/guides/hermes-as-copilot-replacement.md`
- `website/docs/guides/coding-with-hermes.md`
- `website/docs/reference/coding-modes.md`
- internal profile config/templates for coding mode presets

### 8.2 Context pack builder

Need:
- reusable repo/workspace context collector for coding tasks
- consistent summary output consumable by prompts and subagents

Potential implementation areas:
- task/session preparation layer
- ACP session setup hooks
- optional reusable utility module for repo analysis

Capabilities to include:
- branch detection
- dirty-state detection
- relevant file discovery
- framework/test command discovery
- local docs/context file discovery
- optional session_search/memory recall hooks when available

### 8.3 SOP runner / workflow policy layer

Need:
- clear internal workflow templates per task kind
- stable step sequencing so coding behavior is consistent

Potential implementation shapes:
- prompt templates
- profile-scoped system overlays
- slash-command wrappers
- workflow helper modules for coding sessions

### 8.4 Verification policy layer

Need:
- standardized “do not claim done without evidence” checks
- guidance for narrow-first validation
- explicit behavior when validation cannot be run

Potential implementation shapes:
- response-format utilities
- tool-usage policy helpers
- mode-specific final-response contracts

### 8.5 Artifact and handoff layer

Need:
- optional structured coding-task closeout artifact
- support for commit summaries, handoff notes, and follow-up lists

Potential implementation shapes:
- markdown artifact templates
- session summary helpers
- gateway-compatible condensed output format

### 8.6 Multi-lane execution support

Need:
- recommended orchestrator/reviewer/tester patterns for coding work
- stable task packs for subagent delegation

Potential implementation shapes:
- skills
- delegation templates
- coding-specific review rubrics

---

## 9. Skills and procedural memory strategy

A Copilot replacement should lean heavily on Hermes skills.

Needed skill families:
- coding implementation SOP
- systematic debugging SOP
- code review SOP
- shipping/closeout SOP
- workspace target verification SOP
- stack-specific skills (Laravel, Vue, TS, Python, etc.)

The important shift:
skills are not optional decorations here; they are part of the replacement strategy. They make Hermes behavior stable and accumulative in ways Copilot usually is not.

Recommendation:
introduce a coding skill bundle or documented profile that loads the right skills automatically for engineering sessions.

---

## 10. ACP/editor story

Hermes should not be IDE-dependent, but editor workflows still matter because Copilot lives there.

ACP/editor design goals:
- preserve the same coding modes and SOPs from CLI
- keep tool access curated for editor workflows
- make context assembly visible rather than magical
- avoid turning ACP into a thin chat pane without real repo actions

The ACP story should be:
- editor as convenient front-end
- Hermes as actual runtime brain

This matters because it preserves a single mental model across CLI, remote, and editor usage.

---

## 11. Remote-first story

This is a major differentiator.

Hermes should replace Copilot especially well in remote and hybrid workflows:
- SSH-backed projects
- VPS-hosted repos
- server-side debugging
- long-running validation loops
- messaging-driven coding tasks

The Copilot replacement design should explicitly embrace:
- pure remote workspaces
- local+remote hybrid work
- detached runtime execution
- artifact-driven handoff

In plain language:
Hermes should be better than Copilot anywhere the work is not confined to a local IDE tab.

---

## 12. Proposed milestones

### Milestone 0 — design freeze
Outcome:
- replacement goals clearly defined
- first coding modes agreed
- no confusion with Copilot-provider integration

Proof:
- this design doc reviewed and accepted

### Milestone 1 — SOP-first coding mode v1
Outcome:
- stable coding modes defined (`implement`, `debug`, `review`, `test`, `ship`, `explain`)
- mode semantics documented
- coding sessions can follow repeatable workflows

Proof:
- docs for coding modes exist
- at least one internal/profile mechanism can activate them

### Milestone 2 — context pack builder v1
Outcome:
- Hermes can assemble repo/task context automatically before coding work
- context pack includes branch/dirty state/relevant files/docs/tests

Proof:
- live coding session demonstrates context pack output on a real repo
- edge case: dirty repo warning is surfaced clearly

### Milestone 3 — verification contract v1
Outcome:
- coding outputs follow a proof-oriented structure
- “done” claims require validation disclosure

Proof:
- final coding responses include validation and evidence sections by default in coding mode

### Milestone 4 — multi-lane execution support
Outcome:
- non-trivial tasks can use implementer/reviewer/tester delegation patterns
- task packs and review rubrics are reusable

Proof:
- at least one real multi-agent coding workflow succeeds with review artifacts

### Milestone 5 — ACP/editor parity
Outcome:
- ACP/editor users get the same coding-mode semantics and context behavior
- editor use no longer depends on ad hoc prompting

Proof:
- same repo task can be executed from CLI and ACP with comparable behavior

### Milestone 6 — productized Copilot replacement story
Outcome:
- docs, commands, and examples make Hermes obviously usable as a default coding assistant
- replacement value proposition is user-visible and teachable

Proof:
- public docs/guides exist and are coherent

---

## 13. Risks and failure modes

1. Over-optimizing for docs instead of behavior
Risk:
- nice design, no actual workflow improvement
Mitigation:
- prioritize SOP, context pack, and verification behavior before branding/docs polish

2. Recreating Copilot UI instead of solving the workflow
Risk:
- effort spent on editor sugar, little operational gain
Mitigation:
- keep repo/runtime workflow as the center of design

3. Excessive verbosity in coding mode
Risk:
- Hermes becomes correct but annoying
Mitigation:
- concise operator-facing output with evidence available, not dumped by default

4. Too much autonomy without boundary checks
Risk:
- Hermes stomps dirty worktrees or over-edits
Mitigation:
- workspace verification, dirty-state warnings, minimal-safe-change defaults

5. Weak verification enforcement
Risk:
- Hermes still bluffs, just with better prose
Mitigation:
- explicit final-response contracts and coding-mode policy checks

6. Fragmented behavior across CLI vs ACP vs gateway
Risk:
- users must relearn the agent per surface
Mitigation:
- one coding runtime profile, many front-ends

---

## 14. Acceptance criteria for “Hermes can replace Copilot”

A realistic first acceptance bar is not autocomplete parity. It is workflow preference parity.

Hermes qualifies as a credible Copilot replacement when a user can prefer it for real coding tasks because it reliably does the following:

1. For a new coding task, Hermes identifies the correct repo/workspace and warns on dirty state.
2. Hermes gathers relevant code/docs/tests without excessive user steering.
3. Hermes executes a mode-appropriate SOP (implement/debug/review/test/ship).
4. Hermes patches code directly when authorized.
5. Hermes runs focused validation when possible.
6. Hermes reports what changed, why, and with what proof.
7. Hermes supports remote work as a first-class path.
8. Hermes can scale to subagent-backed multi-lane workflows for larger tasks.
9. Hermes behavior improves over time through skills/memory rather than only prompt tuning.

That is enough to replace Copilot for a large class of serious engineering work.

---

## 15. Recommended first implementation slice

The first shippable slice should be small but unmistakably useful.

Recommended slice:
“SOP-first coding mode with repo context pack and verification contract.”

Specifically:
1. define coding modes and their SOPs
2. add a repo context pack builder
3. add coding-mode final-response contract
4. document the workflow
5. test the flow on one or two real repos

Why this slice:
- highest leverage
- low vendor coupling
- works in CLI first and can later extend to ACP
- creates the backbone for everything else

Not recommended as the first slice:
- full editor-native UX work
- provider changes
- autocomplete ambitions
- complex background daemons just for coding mode

---

## 16. Suggested docs and implementation outputs

Suggested docs to add in future implementation:
- `docs/plans/2026-04-07-hermes-copilot-replacement-implementation-plan.md`
- `website/docs/guides/hermes-as-copilot-replacement.md`
- `website/docs/guides/coding-with-hermes.md`
- `website/docs/reference/coding-modes.md`

Suggested implementation artifacts to consider:
- coding profile presets
- coding mode prompt/templates
- repo context pack utility/module
- verification summary formatter
- subagent task-pack templates for coding lanes

---

## 17. Open questions

These need explicit answers before implementation:

1. Should coding modes be exposed as slash commands, profiles, ACP presets, or all three?
2. Which surface is the first-class launch target: CLI, ACP, or both?
3. How opinionated should commit/push automation be by default?
4. Should coding mode produce optional artifact files, or only conversational summaries at first?
5. What exact context-pack size and file-selection heuristics should be used to avoid bloat?
6. How should coding-mode behavior interact with existing skills auto-loading?
7. Should there be a dedicated “coding runtime” profile name, or should this be a composable preset?

---

## 18. Final recommendation

Do not frame this project as “add Copilot to Hermes.”
Frame it as:

“Make Hermes the default engineering operating system.”

Implementation priority should be:
1. SOP-first coding modes
2. repo context pack builder
3. verification/evidence contract
4. multi-lane execution patterns
5. ACP/editor polish

That path gives Hermes a genuine chance to replace Copilot on substance, not imitation.
