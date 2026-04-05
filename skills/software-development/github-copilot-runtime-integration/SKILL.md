---
name: github-copilot-runtime-integration
description: Evaluate and design GitHub Copilot integration into Hermes or repo-local runtimes using supported surfaces like Copilot CLI, MCP, and custom agents while preserving controller authority.
category: software-development
---

# GitHub Copilot Runtime Integration

Use when the user asks whether GitHub Copilot can be integrated into Hermes, a runtime, or an internal agent orchestration system.

## Default recommendation

Prefer this staged approach:

1. Thin Copilot CLI adapter first
2. Keep Hermes/runtime as orchestrator, verifier, and escalation authority
3. Treat Copilot output as advisory only
4. Scale later to MCP-backed context and GitHub custom agents if the first stage proves useful

Do **not** recommend deep/unsupported backend API embedding unless the user explicitly wants risky experimental work.

## Architecture rule

Do not shove Copilot into an unrelated provider/data-plane interface.

Separate:
- provider/data plane: channel status, operator runs, API reads/writes
- delegated engineering plane: coding/debugging/doc assistance from Copilot

If the codebase already has a repair/escalation lane (for example `dev-bridge`), that is usually the best first insertion point.

## Supported integration options to compare

### 1. Hermes -> Copilot CLI adapter
Best first POC.

Pros:
- lowest complexity
- supported surface
- easy to disable/fallback
- easy to wrap with policy/logging

Cons:
- auth/session management needed
- output must be normalized and verified

### 2. Shared MCP ecosystem
Expose selected internal tools/context through MCP so Copilot can use the same tool bus.

Pros:
- cleaner long-term architecture
- future-proof
- reusable beyond Copilot

Cons:
- capability scoping/auth design required

### 3. GitHub custom agents
Use `.github/agents/*.md` for repo-native workflows.

Pros:
- strong fit for GitHub issue/PR workflows

Cons:
- less direct for low-latency CLI/runtime orchestration

### 4. Unofficial/direct backend integration
Avoid by default.

Cons:
- brittle
- auth/terms/maintenance risk
- poor production choice

## What to look for in the target repo

Before writing the design, inspect:
- main orchestrator/control-plane file
- existing provider/client interfaces
- current escalation/repair lane
- artifact persistence layer
- existing smoke-test / regression harness
- package/runtime shape (keep the first integration thin)

## Recommended design shape

Add a small delegated-agent layer instead of mixing Copilot into provider APIs.

Suggested module family:
- `delegated-agents/types.ts`
- `delegated-agents/copilot-cli.ts`
- `delegated-agents/policy.ts`
- `delegated-agents/normalize.ts`
- `delegated-agents/index.ts`

Suggested core contracts:
- delegated task kinds: repair review, error triage, patch proposal, test draft, docs draft
- availability check: binary present + auth usable
- normalized result: summary, warnings, suggested commands/files, next action

## Safety policy

Allowed in first POC:
- explain probable cause
- propose patch
- draft tests
- summarize blast radius
- draft docs

Forbidden in first POC:
- deploy actions
- secrets access
- arbitrary shell execution without controller review
- direct mutation of runtime truth/escalation state
- treating Copilot output as verified fact

## Integration point guidance

Best first insertion point:
- existing repair/escalation lane (for example `dev-bridge`)

Flow:
1. runtime executes
2. truth gate evaluates
3. escalation decides human/dev-bridge/etc.
4. optional Copilot assist is requested only if policy allows
5. result is attached as an advisory artifact/handoff note
6. truth verdict and escalation target remain owned by Hermes/runtime logic

## Artifact rule

Persist Copilot activity separately, e.g.:
- delegated agent request
- delegated agent result
- optional summary note in final artifact

Never blur advisory Copilot output into authoritative runtime truth.

## POC acceptance criteria

A good first POC proves:
1. Copilot CLI discovery works
2. auth/session usability can be detected
3. a narrow non-destructive prompt can run
4. output can be normalized
5. result can be attached to the repair/escalation artifact flow
6. truth/escalation semantics remain unchanged
7. tests cover both available and unavailable Copilot paths

## Doc-writing pattern

When the user asks for a design doc + POC plan:
- verify the target repo/branch first
- inspect orchestrator, provider boundary, escalation lane, artifact writer, and package.json
- explicitly mention why Copilot should not be embedded into unrelated provider interfaces
- recommend Copilot CLI adapter first, MCP/custom agents later
- include exact proposed files and insertion points
- include a tiny staged implementation plan and testing matrix

## Heuristic summary

If only one recommendation fits, use this:

"Build a thin GitHub Copilot CLI adapter and wire it into the existing repair/dev-bridge lane as an optional advisory assistant. Hermes stays judge/jailer; Copilot only proposes."
