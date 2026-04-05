---
name: centracast-runtime-phase-implementation
description: Implement a new CentraCast runtime phase end-to-end using the repo’s real testing/doc patterns, not generic test folder assumptions.
---

# CentraCast Runtime Phase Implementation

Use this when landing a planned feature phase in `centracast-runtime` (for example Phase 3 planning, future execution/scheduling phases, or similar contract-driven runtime expansions).

## When to use
- The work is defined in `docs/END-TO-END-IMPLEMENTATION-PLAN.md`
- You need to add new runtime modules plus public exports
- You need to wire the new phase into `entrypoint/lead-orchestrator.ts`
- You need regression coverage in the repo’s existing harness
- You need docs updated after implementation/tests pass

## Key repo-specific lesson
Do **not** assume this repo uses `tests/*.test.ts` for runtime regression coverage, even if the implementation plan mentions those paths.

For `centracast-runtime`, the authoritative regression harness is currently:
- `scripts/run-tests.ts`
- executed via `npm test` (`node --experimental-strip-types scripts/run-tests.ts`)

So for phase work, add/extend coverage there unless the repo has clearly evolved to a different test structure.

## Workflow

1. Read the phase spec in `docs/END-TO-END-IMPLEMENTATION-PLAN.md`
   - Capture required files to create/modify
   - Capture deliverables, tasks, and exit criteria
   - Note any mentioned tests, but verify how the repo actually runs tests before following that literally

2. Inspect the current runtime surfaces
   - `index.ts` for exports
   - `entrypoint/lead-orchestrator.ts` for orchestration wiring
   - `entrypoint/lead-steps.ts` for typed snapshot contracts
   - related existing phase modules/types for naming/style consistency

3. Follow repo-native TDD, not generic TDD theater
   - Add regression cases first in `scripts/run-tests.ts`
   - Cover both unit-style helper behavior and full orchestrator persistence behavior
   - Good phase tests usually include:
     - schema/required-section contract checks
     - deterministic helper logic
     - positive path generation behavior
     - edge cases / fallback behavior
     - end-to-end orchestrator snapshot persistence

4. Implement the new phase modules
   - Create the new phase files from the plan
   - Keep outputs serializable and shaped for downstream phases
   - Prefer explicit typed contracts over loose records
   - Add any supporting schema constants to keep output shape stable

5. Retrofit the orchestration contracts
   - Extend `lead-steps.ts` typed scaffold(s) to carry the new phase output
   - In `lead-orchestrator.ts`, build the phase artifact during the relevant step
   - Persist it into `result_snapshot` before final truth/status resolution

6. Export the feature publicly
   - Update `index.ts` with new types/constants/helpers/builders
   - Export both contract types and main builder/helper functions if downstream phases will need them

7. Verify with the real harness
   - Run `npm test` from `centracast-runtime`
   - Use the real output to confirm all regression cases pass
   - If a patch tool reports TypeScript lint noise because `tsc` is not installed locally, treat that as tooling noise and rely on the repo’s actual test command instead

8. Update docs immediately after green tests
   - Update `README.md` public surface when exports change
   - Update `entrypoint/README.md` when orchestrator snapshot behavior changes
   - Update `docs/END-TO-END-IMPLEMENTATION-PLAN.md` with an implementation status snapshot so the spec doesn’t drift from reality

## Recommended regression pattern
For each new phase, add three layers of checks in `scripts/run-tests.ts`:

1. Contract checks
   - required schema sections
   - exported types/constants remain aligned

2. Engine/helper checks
   - scoring/order behavior
   - allocation/distribution logic
   - fallback/guardrail logic
   - duplicate suppression or similar edge cases

3. Orchestrator integration checks
   - `LeadOrchestrator` persists the new phase artifact into `result_snapshot`
   - non-empty arrays/fields exist where downstream phases depend on them

## Phase 3 example lessons
When implementing the planning engine:
- `ThirtyDayPlanScaffold` needed a `plan_output` field to carry the real generated plan
- `LeadOrchestrator` had to call the planner directly during planning step construction
- `scripts/run-tests.ts` needed both planner-focused tests and full-flow orchestrator assertions
- docs had to mention that planning artifacts are now materially persisted, not just scaffold placeholders

## Phase 4 example lessons
When implementing the execution brief engine:
- add the new phase contract type early (for example `execution/execution-types.ts`) before extending snapshot/orchestrator types, or imports from `lead-steps.ts` will break fast
- extend `LeadResultSnapshot` with a typed scaffold (for example `ExecutionBriefScaffold`) instead of leaving the phase as `Record<string, unknown>`
- update old orchestrator assertions in `scripts/run-tests.ts` when `step_progress` grows; stale expectations can make the harness print passing section summaries and then still die on a later uncaught assertion
- assert both artifact persistence and downstream readiness (for Phase 4: `brief_count` and `ready_for_scheduling`), not just that the new snapshot key exists
- when public contracts change, update both `index.ts` exports and README surface docs in the same pass
- after Phase 4 lands, debt-remediation should extract any inline orchestrator helper (for example `buildExecutionSnapshot`) into its own `execution/` module so the orchestrator stays mostly wiring/persist/transition logic
- when doing that extraction, add a direct regression in `scripts/run-tests.ts` for the extracted builder itself, not just the full orchestrator path; this keeps future Phase 5 work from depending solely on end-to-end assertions
- patch-tool TypeScript lint complaints about missing local `tsc` can be treated as tooling noise here; rely on the repo-native `npm test` harness for real verification unless the repo itself has changed

## Phase 5 contract-hardening lessons
When implementing the scheduling handoff before real slot assignment exists yet:
- do not overcommit to fake scheduler behavior just to satisfy the implementation plan; land the typed handoff contract first, then keep slot assignment/conflict resolution as the next slice
- define the canonical scheduling contract in `scheduler/scheduler-types.ts`, then have `entrypoint/lead-steps.ts` extend or alias that contract so `LeadResultSnapshot.scheduling` stays typed without duplicating semantics in two places
- add a narrow builder (for example `buildSchedulingScaffold()`) that consumes explicit execution outputs (`briefs`, `validation`, `visibility`) rather than letting Phase 5 reach back into raw planning blobs
- keep readiness explicit at the new boundary: `execution.ready_for_scheduling` is upstream readiness, while `scheduling.ready_for_slot_assignment` is the schedule-stage readiness field
- add direct regression coverage for both clean and blocked handoffs; for scheduling, that means at least one case with all briefs ready and one with execution validation issues plus blocked visibility/conflicts
- update debt-tracker/docs status immediately when a boundary-hardening item becomes done, otherwise the plan drifts and future work re-solves already-fixed contract gaps

## Phase 5 slot-assignment/conflict-resolution lessons
When implementing real scheduler behavior after the handoff scaffold exists:
- keep the scheduler split into two explicit slices: `assignPublishSlots()` for deterministic initial allocation and `resolveScheduleConflicts()` for post-allocation repair; this keeps collision logic from bleeding into the initial mapping step
- export both the helper functions and their result-contract types from `index.ts` in the same pass, otherwise downstream callers will reach into `scheduler/*` internals
- add regression coverage in `scripts/run-tests.ts` for five concrete cases: clean assignment, collision detection, outside-window detection, successful reschedule within window, and unresolved tight-window conflict
- use `buildSchedulingScaffold()` in tests as the setup path for scheduler helpers so Phase 5 coverage stays anchored to the real execution->scheduling contract instead of hand-crafted ad-hoc objects
- when the orchestrator is wired, preserve the boundary explicitly in `LeadResultSnapshot`: store the pre-assignment scaffold as `scheduling_handoff` and the post-resolution result as `scheduling`; do not collapse both concepts into one field or downstream semantics get muddy fast
- full-flow orchestrator assertions in `scripts/run-tests.ts` should be upgraded in the same pass: expect the `scheduling` step in `step_progress`, assert `scheduling_handoff.ready_for_slot_assignment`, and assert final `scheduling.scheduled_items` / `scheduling.ready_for_publish`
- `entrypoint/README.md` is especially likely to drift here; if it still says the orchestrator stops after execution, patch it immediately once scheduling is actually wired
- in this repo, patch-tool auto-lint may complain about missing `tsc`; treat that as non-authoritative noise and use `npm test` as the real verifier unless the repo’s test command changes
- docs should describe the two authoritative scheduler-stage outcome flags explicitly: `PublishScheduleOutput.ready_for_conflict_resolution` and `PublishScheduleOutput.ready_for_publish`
- after landing code + tests, update both surface docs (`README.md`, `entrypoint/README.md`) and debt/status docs; it is easy to leave the debt tracker stale even when implementation is complete
- when scheduling is fully wired, docs must stop describing scheduling as handoff-only persistence. Update `docs/RUN-ARTIFACTS-SPEC.md` and `docs/OUTPUT-SCHEMAS.md` so they explicitly distinguish `scheduling_handoff` (pre-assignment scaffold) from `scheduling` (final `PublishScheduleOutput`)
- when you extend a shared runtime contract like `NormalizedChannelAnalytics`, audit all direct fixture-style tests that construct that object manually. The repo has helper-driven tests and also hand-built analytics objects inside `scripts/run-tests.ts`; the latter will fail at runtime if you forget to backfill the new required field.
- when you strengthen analytics evidence-richness scoring or add new missing-anchor semantics, also audit downstream strategy fixtures that currently expect `Evidence richness: strong`. A normalization-only change can silently downgrade old strategy test inputs to `moderate`/`weak`, so either update the fixture payload with the new provider signals (for example `average_view_duration_seconds` / `traffic_sources`) or update the assertion intentionally.
- for analytics/strategy hardening slices, prefer encoding the new grounding signal once at normalization time (for example `evidence_summary.richness`, missing anchors, fallback notes), then thread that through diagnosis, strategy, and QA instead of recomputing similar heuristics independently in each stage.
- when the next high-impact slice is no longer live-provider parity because staging/backend routes still cap the payload, the best follow-on is usually Phase B grounding depth: make `analytics/channel-diagnosis.ts` and `strategy/build-channel-strategy.ts` actively consume the normalized signals already present (for example average-view-duration gaps, traffic-source leaders, winning tag clusters) so the chain becomes normalization -> diagnosis -> strategy instead of stopping at normalization-only richness scoring.
- for that slice, upgrade the hand-built diagnostics/strategy fixtures in `scripts/run-tests.ts` to include those richer fields and assert the exact grounded outputs you expect (for example attention-gap strengths, search-led opportunities, distribution experiments, evidence-summary anchors). Otherwise the new logic lands as dead code or only indirectly covered.
- after moving diagnosis/strategy grounding forward, update both `docs/END-TO-END-IMPLEMENTATION-PLAN.md` and `docs/END-TO-END-GAP-MATRIX.md` in the same pass so Phase 2 / Phase B status reflects the deeper grounding that now exists locally, while still calling out that real staging parity remains limited by backend payload availability.
- after running `npm test`, review `docs/runs/...` generated artifact drift separately from source changes. The harness can rewrite manifest/summary/json artifacts as a side effect; stage only the intentional code/doc edits unless you explicitly want fixture artifact updates in the commit.
- update step-progress docs and harness expectations together: current full-flow order must match the canonical orchestrator flow exactly, and QA-blocked runs are still expected to reach `qa` and `artifacts`
- when adding a brand-new orchestrator phase (for example `release` between `execution` and `scheduling`), audit every hard-coded full-flow assertion in `scripts/run-tests.ts` in the same pass. Search for `.map((step) => step.step)` expectations and `telemetry_summary.expected_artifact_stage_count` literals, then patch both the ordered step list and the expected count. Otherwise the harness fails with drift like `8 !== 7` even though the new phase wiring is correct.
- document the QA-vs-truth nuance explicitly in repo docs when Phase 6 is active: a run may end `blocked` with `truth_verdict = pass` because `qa.passed = false` (for example `strategy_output_missing`), and blocked runs should still persist QA/artifact outputs for audit/replay
- when scheduling overflow/backlog wording matters across orchestration and QA, centralize the semantic assessment and message builders in one shared helper module (for example `scheduler/scheduling-overflow.ts`) instead of duplicating strings in tests/orchestrator/QA logic
- regression coverage should import those shared helper builders directly and assert exact wording from the helper outputs; do not hardcode duplicate strings in multiple tests, or wording drift will creep in silently
- for overflow-only outside-window backlog cases, verify three surfaces stay aligned in one pass: schedule QA warning messages, scheduling step-progress note, and live staging harness output from the real `LeadOrchestrator` path
- when introducing a new authoritative readiness field on an existing phase contract (for example `scheduling.ready_for_qa`), do a full producer→consumer audit in one pass: add the field to the canonical contract type, compute it in every producer (`assignPublishSlots()` and `resolveScheduleConflicts()` here), switch downstream gating (`runQaChecks()` / `validateScheduleOutput()` and orchestrator step status) to the new field intentionally, then update docs that describe both QA and publication boundaries (`PHASE-BOUNDARY-DEBT-TRACKER`, `ROLE-HANDOFF-CONTRACTS`, `OUTPUT-SCHEMAS`, `RUN-ARTIFACTS-SPEC`)
- for that kind of readiness-field migration, expect legacy regression tests to fail in two specific ways: old issue-order/error-count assertions need one more QA issue (for example `schedule_not_ready_for_qa`), and overflow-only warning fixtures may silently encode the old semantics (`ready_for_publish` as QA gate). Reconcile fixture intent against the new boundary semantics instead of blindly weakening the validator
- after `npm test`, immediately clean generated `docs/runs/...` artifact drift before committing (`git restore docs/runs/<date>` plus `git clean -fd docs/runs/<date>` worked here). In this repo the harness can recreate untracked proof/sample JSONs right after a green run, so do the cleanup once more right before `git add` instead of assuming the earlier cleanup stuck.
- when the user asks for “sapu sampah + commit push”, stage only intentional source/docs files after that second cleanup pass. A quick `git status --short` after cleanup is the reliable proof that generated run artifacts are really gone before commit.

## Phase 7 observer/staging lessons
When implementing the observer/prod-debug surface and staging-run UX hardening:
- extend `observer/index.ts` with typed stage-aware summaries instead of adding ad-hoc strings only; keep both a machine-friendly snapshot (`stage_summary`, `run_progress`) and a compact human summary in `summarizeObservation()`
- derive observer stage buckets from the canonical orchestrator step list and treat missing step records as pending, so observation stays stable even when a run has only partially persisted progress
- keep the observer read-only; improving visibility should not mutate orchestrator flow just to make summaries look richer
- for `staging-run`, put JSON loading / input-merging / stage-summary formatting in a small helper module (for example `scripts/staging-run-support.ts`) rather than bloating the CLI entrypoint
- when adding `--intake-file` and `--analytics-file`, track whether CLI values were explicitly provided; explicit CLI `objective` / `channel_id` must override file defaults both at the top-level `LeadInput` and inside nested `channel_intake` / `content_intake`
- if staging needs deterministic analytics, add a typed `analytics_override` on `LeadInput` and have the orchestrator prefer it before provider fetches; this is cleaner than faking provider behavior inside the staging client
- after `LeadOrchestrator.execute()` in live/staging helpers, fetch the final run again before printing summaries so you report persisted `step_progress` and artifact paths, not just the immediate top-level output payload
- add repo-native regression coverage in `scripts/run-tests.ts` for parser behavior, structured input precedence, helper loading, and final stage-summary output; avoid one-off shell-only checks when the repo already has a TypeScript harness
- expect `docs/runs/...` manifests/final summaries to change as a side effect of artifact-writing tests or harness execution; treat them as generated-output drift to review intentionally, not as a surprise unrelated file mutation

## Phase 7 orchestrator-integration lessons
When landing Task 7.x orchestration coverage:
- treat `scripts/run-tests.ts` as the authoritative integration/e2e harness unless the repo has explicitly grown a real `tests/entrypoint/*.test.ts` runner and wired it into `npm test`
- if the implementation plan asks for `tests/entrypoint/lead-orchestrator.e2e.test.ts` but the repo-native test command still only executes `scripts/run-tests.ts`, land the regression there first and update the plan doc so docs match reality
- cover the schedule-blocked orchestration path explicitly, not just happy path + intake-blocked + QA-blocked flows; assert the full boundary chain: `execution.ready_for_scheduling`, blocked `scheduling_handoff.ready_for_slot_assignment`, absent final `scheduling`, persisted `qa` / `artifacts`, and final human escalation
- when asserting escalation/handoff notes, match the exact current `escalation-policy.ts` wording instead of inventing a paraphrase like "Manual review"; these strings are behavior contracts in the current harness
- after adding a new orchestrator regression, run the full repo-native `npm test` harness immediately because a single bad assertion can hide in the middle of an otherwise-green phase section

## Pitfalls
- Don’t blindly follow planned `tests/...` file paths without checking actual repo conventions
- Don’t assume a user-referenced task number is still pending; when they say something like “lanjut task 5.2/5.3”, first re-open `docs/END-TO-END-IMPLEMENTATION-PLAN.md` and confirm whether those tasks are already marked Done before starting a new implementation slice
- Don’t let preserved todo state or recent context compression trick you into continuing the wrong phase; re-anchor against the plan doc and current repo surfaces first
- Don’t stop at helper implementation; wire the phase into `LeadOrchestrator` or the work stays decorative
- Don’t forget `index.ts` exports or downstream consumers will drift into private imports
- Don’t skip docs after tests pass; this user explicitly wants repo docs kept aligned
- Don’t trust patch-tool lint errors about missing local `tsc` over the repo’s actual `npm test` harness in this workspace
- When adding a new QA gate (especially a final run-level gate), do not “fix” regressions by weakening QA first. Audit the old happy-path fixtures and builder outputs: many previously-passing orchestrator tests were only green because the new validator did not exist yet.
- For phase-gated full-flow regressions, trace the exact readiness chain instead of guessing at final status: `execution.validation -> execution.ready_for_scheduling -> scheduling_handoff.ready_for_slot_assignment -> scheduling.ready_for_publish -> run QA summary -> final status`.
- If a full-flow test still expects `completed` after a new QA gate lands, verify the mocked fixture is semantically consistent (status, visibility, conflicts, publish targets, validator-required fields). Old optimistic fixtures often become invalid once QA starts enforcing the contract.
- When strengthening planning/QA for Phase 6, prefer fixing upstream semantic readiness over weakening validators: in this repo, adding a minimal plan backfill for sparse-but-valid strategy/intake inputs preserved the new QA contract while restoring the intended happy path.
- For editorial/product-quality QA slices, add the failing semantic regressions first in `scripts/run-tests.ts` with intentionally narrow fixtures (for example a slate that is all one audience + one format, a brief whose title/hook/angle are identical, or a strategy whose pillars are near-duplicate phrasings and whose success metrics are generic). Then implement equally narrow helpers in the validators (`countDistinct*`, normalized string comparisons, token-overlap checks, generic-metric detectors) so the new warnings encode a clear contract instead of vague taste-based heuristics.
- In strategy-quality QA specifically, simple phrase normalization may under-detect weak novelty when titles differ superficially (`ETF basics for beginners` vs `ETF guide for beginners` vs `Beginner ETF starter guide`). If the first pass misses the intended warning, switch to token-based overlap logic: normalize to lowercase alphanumeric tokens, ignore very short tokens, count repeated tokens across pillar names, and treat 3+ pillars that share most meaningful tokens as novelty-weak even when the full strings are not identical.
- For business-impact QA, generic success signals often look superficially valid because the field is filled (`Make the channel better`, `Build momentum`, `Learn what works`). A reusable detector is: warn when all strategy horizons and experiment metrics lack measurement anchors (numbers or outcome terms like CTR, retention, conversion, revenue, subscriber, lead, watch time) and instead use vague improvement language.
- For weak-differentiation QA in strategy positioning, compare `core_belief` and `competitive_angle` semantically, not just for exact equality. Exact-match detection is a good first pass, but add token-set overlap/Jaccard-style comparison so near-paraphrases still trigger the warning when both fields basically communicate the same promise.
- For QA summary scoring slices, keep the scoring model inside `qa/qa-types.ts` as an explicitly heuristic triage layer, not a hidden editorial-truth system. Add red tests first for both per-stage verdict scoring and run-level aggregation, then calibrate the expected numbers to the actual formula you choose (`buildQaVerdict` and `buildRunQaSummary`) instead of hand-waving score semantics in docs.
- When you add QA scores, update all three operator-facing surfaces in the same pass: verdict summaries (`stage_summaries`), run summary (`operator_summary`), and persisted artifact markdown in `artifacts/write-run-artifacts.ts` so operators can see overall score plus per-stage scorecards without opening `qa.json`.
- If the slice adds compact QA triage helpers (for example top-issue lines or flagged-stage summaries), wire them across all operator-facing surfaces together: `RunArtifactManifest`, `final-summary.md`, staging/live summary output (`scripts/staging-run-support.ts`), and the docs describing artifact discoverability. Otherwise the data exists in `qa.json` but the actual operator UX still feels half-baked.
- If the next slice promotes QA into a faster operator-triage surface, wire it through all artifact/reporting layers together instead of only enriching `qa.json`: add compact helpers in `qa/qa-types.ts` (for example run-level triage summary, flagged-stage alerts, top-issue summaries), persist them as additive manifest fields, render them in `final-summary.md`, expose them in `scripts/staging-run-support.ts` stage-summary output, and lock the behavior with `scripts/run-tests.ts` assertions against both manifest fields and final-summary markdown.
- For this repo, that operator-facing QA bundle is a reusable pattern: `qa_triage_summary`, `qa_stage_alerts`, and `qa_top_issues` should stay additive and discoverable without forcing operators to inspect raw `qa.json`.
- For HRB-001-style truth-contract work, do not stop after adding new types to `entrypoint/lead-types.ts`. Audit all three truth surfaces together: orchestrator return payload (`LeadOutput.fulfillment` / `LeadOutput.outcome`), persisted artifact manifest (`RunArtifactManifest.fulfillment` / `consumer_outcome`), and inspect/runtime-consumer fallback builders. If one surface still invents truth ad hoc, the contract is cosmetic.
- When artifact contracts already declare a required field like `RunArtifactManifest.fulfillment`, wire it inside `artifacts/write-run-artifacts.ts` in the same pass. In this repo the consumer fallback builder can mask that omission until runtime import failures or inspect drift expose it later.
- If `npm test` dies immediately with `does not provide an export named ...`, inspect the exporting module for patch corruption before doing broader refactors. In this slice the real root cause was a mangled `entrypoint/outcome-envelope.ts`, not a deeper design mismatch.
- When restoring a broken helper module, preserve callsite compatibility first and clean signatures later. Here `lead-orchestrator.ts` still passed a second context argument to `buildAiOutcomeEnvelopeFromRun(...)`, so keeping an ignored optional parameter was the safest fast bridge while repairing HRB-001.
- Patch-tool lint noise about missing local `tsc` is still non-authoritative here; for runtime contract repairs, trust the repo-native `npm test -- --runInBand` harness as the real verifier.
- After scoring/artifact changes, expect generated drift not only in `docs/runs/.../final-summary.md` and manifests but also in `docs/runs/.../qa.json`; review those as harness side effects and stage only if you intentionally want generated fixture output refreshed.
- When artifact/staging surfaces gain new QA fields, update the docs in the same pass (`docs/RUN-ARTIFACTS-SPEC.md` and any gap/status tracker that describes artifact comparability/telemetry) so runtime behavior, operator output, and docs do not drift.
- After the main full-flow regression turns green, rerun the entire `scripts/run-tests.ts` harness and watch for uncaught assertions after the section summary. This repo can still fail late on older expectations (for example early-exit `needs_human_input` runs now picking up `qa`/`artifacts` step entries because `persistRunArtifacts()` still executes on intake-blocked runs).
- For early-exit orchestration paths, audit `persistRunArtifacts()` separately from the happy path. If a run should stop at intake with `needs_human_input`, make sure Phase 6 persistence does not append downstream `qa`/`artifacts` steps unless that behavior is explicitly intended and test fixtures are updated accordingly.
- When updating stale harness expectations after orchestration changes, do not assume every red test is just a `step_progress` mismatch. Run the exact scenario (a tiny temporary `node --experimental-strip-types` script with the same mocked provider + intake as the failing test is enough) and inspect the real `output.status`, `escalation_decision`, `qa`, and persisted snapshot fields before patching assertions.
- In the content-intake happy path, a run can now end `blocked` with `truth_summary.verdict === 'pass'` if final QA fails while artifacts still persist correctly. That is not necessarily a truth-gate failure; it can be a contract failure inside QA (for example `strategy.strategy_output` missing while `strategy.next_best_action` exists).
- For these cases, update harness assertions to reflect the new semantics explicitly: keep checking the full phase chain (`intake` through `artifacts`), but assert `output.status`, `output.escalation_decision.escalate`, `snapshot.qa.passed/error_count`, and specific QA issue codes (for example `strategy_output_missing`) instead of only checking publish readiness and assuming completion.
- For publication/release phases that persist asynchronous backend state (draft, queued, upload-status, published-id), implement a dedicated summary helper (e.g., `summarizeReleasePublishTruth`) to map the complex state into a single compact string. Use this helper in the orchestrator `step_progress` note to ensure "runtime honesty" so operators can distinguish between a created-but-queued release and a fully published one without inspecting raw JSON. The helper should check `is_published` / `publish_state === 'published'` first, then `publish_state === 'failed'` or `youtube_upload_status === 'failed'`, then `queued_for_upload` / `publish_state === 'queued'`, then fall back to draft with the `truth_source` field.
- For AF-006.B-style async upload slices, do not stop at persisting `publish_readback`; add an explicit provider capability like `dispatchUpload(releaseId)` plus a small generic polling helper (for example `pollUntilReady`) so the orchestrator can trigger the backend action and then re-read truth until a terminal state or timeout. Persist the dispatch/poll receipt fields directly into `ReleaseWorkflowSnapshot` (for example `upload_dispatch_status`, `upload_dispatch_message`, `publish_poll_attempts`, `publish_poll_timed_out`) so operators can tell the difference between dispatch accepted, still queued, timed out, and truly published.
- Keep the polling helper generic and repo-local instead of burying retry loops inside the provider client. A reusable pattern here was: `timeoutMs`, `intervalMs`, `getState(result)`, and `terminalStates(state)`; that kept AF-006.B wiring simple and made regression testing easy with a mock `getRelease()` that returned `queued` on the first read and `published` on later reads.
- For this repo, the first failing regression after adding publish polling may be unrelated to polling logic at all. In AF-006.B the red test was a stale assumption about which execution item became `asset_id` (`strategy-1` vs a hand-picked fixture id). Fix those assertions to test the semantic contract you actually care about (dispatch called, publish transitioned, poll attempts persisted) instead of overfitting incidental chooser internals.
- In AF-004-style SEO quality-loop work, normalize SEO fields at the provider boundary (`seo_title/seo_description/seo_hashtags` vs `title/description/tags`) before scoring/revision. Mixed field conventions can make revision logic look broken even when update calls fired.
- For SEO revision regressions, assert contract-level outcomes (`seo_revision_count`, `seo_quality_review.initial_score/final_score`, `final_passed`) first; keep title-content assertions non-brittle (avoid strict case-sensitive token checks like `includes('Founder')` unless casing is explicitly part of the contract).
- Patch-tool lint output complaining that `tsc` is missing is still non-authoritative here; after async release wiring, trust the repo-native `node scripts/run-tests.ts` / `npm test` harness and expect the real signal to come from failing assertions, not the patch auto-lint banner.
- When committing after `scripts/run-tests.ts` passes, do one explicit `git status --short` review because unrelated docs or generated audit files may be sitting dirty in the repo and can get swept into the feature commit if you just `git add -A` out of habit.

## Verification checklist
- New phase files created
- `index.ts` exports updated
- `lead-steps.ts` contracts updated
- `lead-orchestrator.ts` persists new phase output
- `scripts/run-tests.ts` covers helper + orchestrator behavior
- `npm test` passes
- README + entrypoint docs + implementation plan doc updated
