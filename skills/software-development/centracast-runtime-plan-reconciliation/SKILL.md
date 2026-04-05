---
name: centracast-runtime-plan-reconciliation
description: Reconcile the CentraCast runtime implementation plan against the actual repo state, then land the smallest typed-contract slice without breaking the live staging flow.
tags: [centracast, typescript, planning, refactor, regression-testing]
---

# CentraCast Runtime — Plan-vs-Repo Reconciliation

Use when a doc like `docs/END-TO-END-IMPLEMENTATION-PLAN.md` says “implement Phase X”, but the repo already contains partial landing work and you need to finish the phase quickly without duplicating or destabilizing the current staging runtime.

## When to use

- User wants to “just continue the plan” but the repo is not at the clean starting point assumed by the doc.
- A phase appears partially implemented already.
- You need to preserve the live staging/orchestrator path while tightening contracts.
- You want the fastest route: brief gap audit first, then immediate implementation.

## Core approach

Do not treat the implementation plan as ground truth for file existence or test locations.
Treat the repo as the truth, and the plan as the target shape.

Recommended sequence:

1. Read the relevant phase section from the plan.
2. If the work is tied to GitHub issues, read the issue body first as the baseline outcome contract.
3. Then read the issue comments too when the issue has become a running ledger of landed slices; in this repo, comments often contain the freshest truth about what current HEAD already does and what still remains open.
4. Inspect the exact files the phase claims should exist.
5. Compare “plan deliverables” vs “actual current code”.
6. Run the repo’s real test command early as a reality check, not just at the end.
7. If tests fail, determine whether the code regressed or the test expectation is stale relative to the newer intended behavior.
8. Patch only the missing contract surface.
9. Add or update regression coverage in the repo’s real active test location.
10. Re-run the repo’s real test command, not the parent workspace convention.
11. Immediately update the relevant docs/plan/gap-matrix/README after the test passes so implementation and documentation do not drift before the next slice.
12. During doc reconciliation, treat old gap-matrix statements about live route absence or staging 404s as suspect if newer issue comments or live verification prove the route now exists; update docs to describe the real remaining gap (for example sparse/null-rich anchors) instead of preserving stale “endpoint unavailable” wording.

## Critical repo-specific findings

For `centracast-runtime`, do not assume the implementation plan’s phase list matches the actual landing state.

Current reconciliation pattern observed in this repo:
- foundation/intake contracts are already present
- analytics + strategy are already present
- planning is already present
- execution is already present
- scheduling handoff + slot assignment + conflict resolution are already present
- QA summary + artifact persistence are already present
- the orchestrator is already wiring the end-to-end flow
- for asset-first anchors, do not assume AF-006-style "runtime ownership still pending" just because the plan says so; current HEAD may already own createRelease -> generateSeo -> generateCoverArt -> getReleaseLifecycle -> dispatchUpload -> publish polling inside `entrypoint/lead-orchestrator.ts`
- when auditing AF anchors from `docs/ASSET-FIRST-YOUTUBE-LINEAR-IMPLEMENTATION-PLAN.md`, verify the actual orchestrator/provider chain first before opening a coding lane; sometimes the real work is doc/tracker reconciliation, not implementation

So the real job is often reconciliation, not greenfield implementation.

When checking what actually landed, inspect at least:
- `git log --oneline --decorate -8`
- `docs/PHASE-BOUNDARY-DEBT-TRACKER.md`
- `docs/END-TO-END-IMPLEMENTATION-PLAN.md`
- `entrypoint/lead-orchestrator.ts`
- root `index.ts`

Also, the phase doc may mention test files under `tests/...`, but this subrepo may actually keep active regression coverage in:

- `scripts/run-tests.ts`

Do not waste time creating brand-new test directories if the repo’s real test harness is already `npm test` -> `node --experimental-strip-types scripts/run-tests.ts`.

### Current high-value next-slice heuristic

If phases 1 through 6 already appear landed, the next smallest useful slice is usually not “add the next phase”.
Instead, first determine whether the remaining gap is:
- live grounding / provider parity
- product-quality QA depth
- telemetry / comparability depth
- boundary-hardening / orchestrator coupling

Use this audit order before proposing work:
1. `docs/PHASE-BOUNDARY-DEBT-TRACKER.md` — what contract debt is still explicitly Partial/Pending
2. `docs/END-TO-END-GAP-MATRIX.md` — what business/runtime gaps remain even though the scaffold exists
3. `entrypoint/lead-orchestrator.ts` — where fallback synthesis or wiring still lives in the orchestrator
4. `providers/content-analytics-provider.ts` + `analytics/normalize.ts` — whether live analytics richness still lags the local normalized contract
5. `qa/run-qa-checks.ts` — whether QA is still mostly schema/readiness gating instead of editorial/product-quality review
6. `observer/index.ts` and artifact manifest/final summary code — whether telemetry/comparability is still too thin

Current ranking heuristic for this repo when the basic end-to-end pipeline already exists:
1. analytics/provider parity hardening
2. richer QA/editorial quality layer
3. telemetry/comparability enrichment
4. reducing orchestrator knowledge of artifact internals

Why this ranking works:
- analytics/provider parity improves evidence grounding for strategy, planning, and QA all at once
- richer QA raises output quality instead of merely proving shape/readiness
- telemetry/comparability makes runs meaningfully auditable across time
- orchestrator decoupling is valuable, but usually comes after the user-facing/runtime-quality gaps above unless the orchestrator has become the direct blocker

Concrete reusable signs for each bucket:
- analytics/provider parity is the next slice when `normalizeChannelAnalytics()` still carries heavy fallback notes and live staging may still 404 or return sparse payloads
- QA depth is the next slice when `runQaChecks()` mostly checks presence/readiness/conflicts but not novelty, audience fit, strategic coherence, or likely business impact
- telemetry is the next slice when `observer/index.ts` mostly reports stage counts/statuses without richer per-stage quality/evidence metrics
- orchestrator coupling is the next slice when `LeadOrchestrator` still owns fallback analytics synthesis, readiness note composition, or too much snapshot wiring

Current best candidate is often:
- analytics/provider parity hardening if live grounding is still sparse

Current best candidate for a pure boundary-hardening slice remains:
- extract QA assembly from `entrypoint/lead-orchestrator.ts` into a dedicated typed module (for example `qa/run-qa-checks.ts`)

Why these are strong next slices:
- improve explicit builder inputs
- reduce orchestrator knowledge of artifact internals
- create clean builder-level test targets
- fit the debt-tracker pattern better than inventing a fake new phase

### Boundary-readiness contract rule

When adding or reconciling a new top-level readiness field, keep it scoped to its own boundary only.
Do not let downstream blockers contaminate the upstream readiness contract.

Concrete CentraCast runtime example:
- `plan.ready_for_execution` answers only: “is the planning output ready for execution consumption?”
- it must be derived from planning-side execution readiness (for example item readiness), not scheduling conflicts
- scheduling locks/conflicts belong to the scheduling/publication boundary, not the planning boundary

A real regression pattern already observed in this repo:
- adding `plan.ready_for_execution` initially looked correct
- but a regression test for a schedule-blocked run failed because the implementation accidentally folded `schedule.conflicts.length === 0` into planning readiness
- that was semantically wrong even though it felt “safer” at first glance
- the correct fix was to keep `plan.ready_for_execution` independent, then let later boundaries block on their own readiness fields/verdicts

Use this rule whenever docs say “one authoritative readiness field per boundary”:
1. identify the exact question each field answers
2. list which phase owns the evidence for that answer
3. forbid signals from later phases unless the field is explicitly cross-boundary by design
4. add a regression test where upstream readiness is true/false independently of a downstream block
5. update debt-tracker/docs wording so the field is described as boundary-local, not generic pipeline readiness

Important repo-choice rule:
- if the user says “go back to `centracast-runtime`” after discussing Laravel/backend work, do not propose or attempt Penpod deploys for that runtime repo
- Penpod deploy discussion belongs to `centracast` (Laravel) only unless the user explicitly changes that rule
- for runtime-only gap audits, stop at repo verification + docs/code reconciliation + ranked next-slice recommendation

### Editorial reconciliation mode for the implementation plan

When the user asks for a docs-only consistency pass on `docs/END-TO-END-IMPLEMENTATION-PLAN.md`, do not rewrite the whole plan blindly.
Normalize only the target phases so they match the already-landed snapshot style used by the most up-to-date sections.

For current CentraCast runtime plan work, the preferred landed-phase snapshot format is:
- `Implementation status snapshot:`
- implemented modules/files listed as present state (`... are implemented on current HEAD`)
- public/runtime export surface called out via `index.ts`
- orchestrator persistence/wiring note where relevant
- repo-native regression coverage note pointing to `scripts/run-tests.ts`
- repo-native verification note (`npm test` currently passes ...)
- final status line (`Status: Satisfied on current HEAD` or a narrower qualified variant when needed)

Editorial guardrails:
- keep the scope doc-only unless the user explicitly asks for code/test changes
- prefer present-state wording over historical change-log wording like `Added`, `Exported`, `Wired`
- if a status line is embedded awkwardly in exit criteria, move it into the implementation snapshot block for consistency
- mention `scripts/run-tests.ts` instead of inventing `tests/...` coverage if the repo-native harness is still the authoritative path
- do not stop at the `Implementation status snapshot` blocks: also sweep each phase’s earlier `Test:`, `Files:`, and verification-command bullets for stale `tests/...` or `python -m pytest` instructions that no longer match the repo-native harness
- when the repo is Node-native TypeScript, replace stale parent-repo Python/venv verification commands with `npm test` unless the current repo truly has a separate executed Python suite
- verify the final diff is limited to the intended doc file before reporting completion
- after normalizing the per-phase sections, also reconcile the plan tail (`Suggested Build Order`, `Definition of Done`, `Immediate Next Coding Slice`, `Suggested Follow-Up`) so it reads as current-head guidance instead of stale future-tense implementation instructions
- for those tail sections, preserve their strategic value but reframe them as rebuild/re-entry guidance when the work is already landed on current HEAD

## Practical reconciliation pattern by slice

Always follow this rhythm for this repo:
1. audit the real repo state versus the plan
2. if applicable, audit the linked GitHub issue bodies/comments versus the current diff so you do not optimize for the wrong acceptance criteria
3. run the targeted Node test harness early to catch stale assumptions
4. treat a failing regression as a three-way reconciliation problem: issue intent vs current implementation vs current test expectation
5. fix implementation when the code is behind the intended issue outcome
6. fix the test when the code already reflects the newer intended behavior and the assertion is pinned to an older world model
7. remove ad-hoc repro/debug files (`tmp-*`, scratch scripts) before calling the slice done
8. update docs immediately after the tests pass, before moving to the next slice
9. do a terminology sweep across related docs/READMEs so old boundary names do not survive in adjacent files

### Reality-check pattern for issue-driven slices

When a slice is tied to GitHub issues and you inherit a dirty working tree, do this before editing:
- verify repo + branch (`pwd`, `git branch --show-current`, `git remote -v | head`, `git status --short`)
- inspect the issue bodies for the exact outcome being claimed
- run the authoritative test harness once before touching code
- inspect the failing test's assertion text and compare it against current runtime behavior
- capture whether the failure indicates a real implementation gap or just an obsolete expectation

A concrete repo-specific finding worth remembering:
- In CentraCast runtime, a phase-flow regression may fail because the test still expects legacy QA issue codes (for example `strategy_output_missing`) even after the implementation has legitimately evolved to emit richer, later-stage quality findings instead. In that case, do not blindly “fix” the runtime back to the older behavior just to satisfy the stale test.

This repo drifts easily if docs wait until “later”, so keep implementation, verification, and docs locked together.

For contract or phase-boundary work, do not stop after updating one plan doc. At minimum, sweep these files when they exist:
- `README.md`
- `docs/END-TO-END-IMPLEMENTATION-PLAN.md`
- `docs/PHASE-BOUNDARY-DEBT-TRACKER.md`
- `docs/RUN-ARTIFACTS-SPEC.md`
- `docs/ROLE-HANDOFF-CONTRACTS.md`
- `docs/OUTPUT-SCHEMAS.md`
- `entrypoint/README.md`

Then run repo-wide searches for stale phrases/field names (for example old readiness-field paths, old future-tense wording, or docs that still say a boundary is "future" after the slice landed) and patch the leftovers before committing.

When doing a docs parity sweep after a plan reconciliation, explicitly check for these easy-to-miss stale items:
- task bullets that still name hypothetical `tests/...` files even though the real harness is `scripts/run-tests.ts`
- embedded verification snapshots that hardcode an old pass count (`78 passed` vs current `82 passed`, etc.)
- repo docs that are already correct while only the implementation plan is stale — do not churn README/entrypoint docs just to make the diff look bigger
- gap-analysis docs like `docs/END-TO-END-GAP-MATRIX.md` that still describe already-landed modules as `Missing`, `Not implemented`, `docs only`, `roles only`, or `chain hint only`
- future-tense sections such as `Major Missing Workflow Segments`, `Existing Files That Should Be Extended`, `Priority Order for Implementation`, and `Concrete Next-Step Implementation Plan` that may need to be reframed from greenfield build steps into current-head gap analysis
- repo tree sections that still annotate now-landed directories/files with `# NEW`, which becomes misleading once the work has shipped
- stale closing summaries that still claim the business pipeline does not exist, when the accurate statement is that the end-to-end scaffold exists but needs richer live grounding, smarter business logic, better QA depth, or stronger telemetry

For current CentraCast runtime boundary work, also keep this contract-evolution policy explicit in docs:
- root `index.ts` exports are the intentional public runtime API
- `entrypoint/lead-steps.ts` scaffolds and builder input/output contracts are coordinated internal contracts, even when exported for tests or repo-local composition
- if a public API changes, update exports, docs, and regressions in the same change
- if a scaffold/internal contract changes, update the builder, orchestrator wiring, regressions, and docs in the same change

## Practical Phase-1 reconciliation pattern

If the repo already has intake types and validation, look for these common remaining gaps:

### 1. Snapshot still only half typed
A common partial landing is:
- `LeadResultSnapshot.intake` typed
- `LeadResultSnapshot.analytics` typed
- `strategy` / `plan` still `Record<string, unknown>`

Good minimal fix:
- introduce typed scaffold contracts for strategy/plan in `entrypoint/lead-steps.ts`
- update `LeadResultSnapshot` to use those scaffold types
- keep later stages (`execution`, `scheduling`, `qa`, `artifacts`) transitional if they are not implemented yet

Useful scaffold types to add:
- `StrategyOperatorLoadSnapshot`
- `ChannelStrategyScaffold`
- `PlanningBlockerSnapshot`
- `PlanningPublishWindowSnapshot`
- `ThirtyDayPlanScaffold`

This tightens the contract without forcing the full future Phase 2/3 business engine to exist yet.

### 2. Step-progress helper trapped inside orchestrator
If step upsert logic lives only inside `lead-orchestrator.ts`, move or mirror it into the contract layer.

Preferred fix:
- add `recordLeadStepProgress()` in `entrypoint/lead-steps.ts`
- make orchestrator reuse that helper rather than owning its own copy of the logic

This matches the plan’s intent that step progress be a contract-level helper, not just local orchestration glue.

### 3. Public exports lag behind new contracts
After adding scaffold types/helpers, update `index.ts` exports immediately.
Otherwise the repo technically “has” the contracts but downstream imports still act like they do not exist.

### 4. Tests only verify existence, not typed scaffold shape
If current tests only prove that a snapshot can exist, add focused regression checks that prove:
- `recordLeadStepProgress()` upserts deterministically
- `LeadResultSnapshot` can carry typed `strategy` and `plan` scaffolds

## Implementation guardrails

- Preserve current staging flow; do not redesign orchestration just to satisfy the doc literally.
- Prefer typed scaffolds over giant speculative domain models.
- Reuse existing orchestrator behavior whenever possible.
- Keep implementation additive and narrow.

A good minimal orchestration follow-through is:
- `buildStrategySnapshot()` returns `ChannelStrategyScaffold`
- `buildPlanningSnapshot()` returns `ThirtyDayPlanScaffold`
- local `upsertStepProgress()` delegates to `recordLeadStepProgress()`

That gets stronger typing with low blast radius.

## Verification

For this subrepo, use the repo-native Node harness first:

```bash
npm test
```

This currently runs:

```bash
node --experimental-strip-types scripts/run-tests.ts
```

Do not assume the parent Hermes repo Python/pytest workflow applies here.
This workspace is Node-native TypeScript and its active test harness is the package script.

For a runtime-safe smoke check that does not require live staging credentials, use:

```bash
node --experimental-strip-types scripts/provider-smoke-test.ts
```

Treat this as the default manual smoke path when closing a docs/hardening slice.
Only jump to live staging smoke when `CENTRACAST_TOKEN` is actually available.

## Definition of done for a reconciliation slice

A Phase 1-style reconciliation is good enough when all of these are true:

- existing intake models/validators remain intact
- `LeadResultSnapshot` has more specific typed shape than before
- step-progress helper exists at the contract layer
- public exports include the new contracts/helpers
- regression tests cover both helper behavior and typed scaffold attachment
- `npm test` passes cleanly

## Anti-patterns

Avoid these time-wasters:

- blindly creating all plan-named files from scratch when they already exist
- moving tests into `tests/` just because the doc says so, while ignoring the active `scripts/run-tests.ts` harness
- replacing working runtime scaffolds with “clean architecture” rewrites mid-phase
- forcing full Phase 2/3 domain models when a typed scaffold closes the current gap faster and more safely
