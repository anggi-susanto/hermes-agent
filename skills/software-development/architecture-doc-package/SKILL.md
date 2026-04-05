---
name: architecture-doc-package
description: Package a new integration/architecture concept into a clean git-ready document set with spec, executive memo, technical contracts, discovery checklist, implementation plan, task brief, matrix, and README.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [architecture, documentation, planning, packaging, git]
---

# Architecture Doc Package

## When to use
Use when the user wants a concept/integration turned into a proper document package instead of a single loose note, especially for new system integrations, orchestration designs, or delegable architecture work.

Typical trigger phrases:
- "bikin integration spec"
- "jadiin file .md"
- "bikin paket lengkap"
- "init git disono"
- wants docs ready to hand to CEO/other agents/implementers

## Output package
Create a folder named after the concept and include these files:

1. `README.md`
   - package summary
   - file guide
   - recommended reading order
   - suggested workflow / next steps

2. `[topic]-integration-spec.md`
   - source-of-truth document
   - scope, goals, operating model, data model, states, mappings, sync, auth, risks, MVP, open questions

3. `[topic]-executive-memo.md`
   - strategic summary for founder/architect/operator
   - why this model, why not alternatives, risks, rollout recommendation

4. `[topic]-typescript-contracts.md` (or language-specific equivalent)
   - canonical types
   - provider interfaces
   - mapper contracts
   - sync/event/evidence/verification types
   - anti-footgun constraints

5. `paperclip-discovery-checklist.md` or `[provider]-discovery-checklist.md`
   - capability discovery checklist
   - API/auth/semantics/reliability/governance/security questions
   - evidence requirements
   - final verdict template

6. `capability-matrix.md`
   - blank matrix ready to fill
   - YES/PARTIAL/NO/UNKNOWN rows
   - semantic mapping section
   - anti-bullshit appendix

7. `IMPLEMENTATION-PLAN.md`
   - preconditions
   - MVP boundaries
   - phased implementation tasks
   - testing, logging, failure handling, acceptance criteria

8. `TASK-BRIEF-CEO-<PROVIDER>.md`
   - anti-ambiguity delegation brief for external manager/CEO agent
   - workstreams
   - deliverables
   - definition of done
   - required evidence and verdict structure

## Writing pattern
Use this order:
1. do a quick repo/workspace preflight first (right repo, branch, dirty-state blast radius)
2. audit the existing command/runtime/API surface before inventing a new one
3. write the big integration spec first
4. derive executive memo from the spec
5. derive technical contracts from the spec
6. derive discovery checklist from unresolved questions in the spec and from audit findings
7. add blank capability matrix for future evidence gathering
8. add implementation plan only after framing MVP boundaries, stable contracts, and rollout order
9. add task brief for external delegates if relevant
10. finish with README tying all files together

For control-surface or chat-ops packages, explicitly anchor the package to currently verified surfaces (existing CLI commands, inspect endpoints, tests, config hooks) instead of writing a fantasy greenfield architecture.

## Naming rules
- Prefer canonical folder naming from the concept, e.g. `hermes-x-paperclip`
- Use consistent prefixes across documents
- If the user later corrects a typo in the folder name, rename the folder immediately and verify file paths after rename

## Git packaging workflow
If the user wants a repo-ready package:
1. create or rename the folder correctly
2. verify files exist
3. `git init <folder>`
4. rename initial branch to `main`
5. leave files uncommitted unless user asks to add/commit/push

## README checklist
The README should always include:
- one-line architecture verdict
- package contents
- what each file is for
- recommended reading order for decision-makers vs implementers
- suggested next steps
- current file list

## Quality bar
The package is good when:
- strategic, technical, and execution audiences all have a dedicated doc
- the discovery doc prevents coding on assumptions
- the implementation plan explicitly blocks semantic collapse (e.g. remote done != accepted)
- the README makes the folder handoff-ready

## Pitfalls
- Do not stop at a single spec if the user asked for a package
- Do not forget to update README when adding new companion docs
- Do not commit or push unless asked
- Do not assume the first folder name is correct if the user later corrects spelling
- Do not blur provider completion with canonical acceptance in any doc set
