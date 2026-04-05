---
name: centracast-runtime-epic-slice
description: Execute a scoped slice from a CentraCast runtime epic on main with issue-first intent reconciliation, doc updates, verification, and issue-comment reporting.
---

# CentraCast Runtime Epic Slice

Use this when the user says things like:
- `gas epic #8`
- `lanjut epic #N`
- `ambil slice paling impactful dari tracker`

This skill is for `centracast-runtime`, especially when the issue is a tracker/hardening epic rather than a single narrowly-scoped code bug.

## Why this exists

In practice, epic work here is not “implement the whole issue.”
It is:
1. verify the target repo/branch,
2. read the issue body as the outcome contract,
3. identify the highest-impact achievable slice,
4. land code + docs together,
5. run the authoritative harness,
6. update the GitHub issue inline with what changed and why.

That pattern is reusable.

## Procedure

1. Preflight the workspace first
   - Confirm repo identity and branch before editing.
   - Run:
     - `pwd`
     - `git branch --show-current`
     - `git remote -v | head -n 2`
     - `git status --short`
   - For this user, default to `main` unless explicitly told otherwise.

2. Read the epic/tracker issue before touching code
   - Use `gh issue view <N> --json number,title,body,state,url`.
   - Treat the issue body as the real contract.
   - Extract the remaining focus areas and pick the smallest meaningful slice that actually advances one of them.

3. Inspect the repo for the current reality
   - Read the relevant exports, scripts, docs, and test harness files.
   - In `centracast-runtime`, common places are:
     - `index.ts`
     - `scripts/run-tests.ts`
     - `package.json`
     - `docs/END-TO-END-GAP-MATRIX.md`
     - `docs/RUN-ARTIFACTS-SPEC.md`
     - `docs/staging-phase3-artifact-regression.md`
     - relevant module files under `artifacts/`, `scheduler/`, `qa/`, `entrypoint/`
   - Prefer slices that fit existing architecture instead of inventing a new subsystem.

4. Implement a thin, high-leverage slice
   Good pattern for hardening epics:
   - add typed contracts first,
   - add one focused helper/module,
   - expose it through `index.ts` if it is part of the public surface,
   - add a CLI/script entrypoint if operator usage matters,
   - wire a package script if it helps real usage.

   For strategist-grounding slices specifically, a good thin cut is:
   - add one new normalized evidence anchor (for example playlist/topic winners) to diagnosis,
   - thread that same anchor into strategy `evidence_summary` and pillar-level evidence,
   - preserve weak-evidence framing in `assumptions` when core anchors are missing,
   - add QA rules that flag unsupported certainty when evidence richness is weak/fallback.

   For analytics-parity slices where the backend payload is still thin, another good thin cut is:
   - add a small repo-native helper that normalizes a sampled provider payload and computes per-anchor coverage,
   - print an operator-facing summary in the staging runner showing which core anchors are populated vs unavailable on the sampled live `/channels/{id}/content-analytics` payload,
   - keep this as measurement/visibility work, not pretend it fixes backend richness,
   - cover both the structured helper output and the rendered CLI lines in `scripts/run-tests.ts`.

   Example from artifact-comparability work:
   - add comparison types in `artifacts/artifact-types.ts`
   - add helper `artifacts/compare-run-artifacts.ts`
   - add CLI script `scripts/compare-run-artifacts.ts`
   - add npm script `artifacts:compare`
   - export helper from `index.ts`
   - if the manifest now persists a richer analytics ledger, widen `compareRunArtifacts()` in two places together: structured `deltas` and human-facing `summary_lines` (for example endpoint availability, missing/populated/unavailable anchor lists, explicit-null/explicit-empty buckets), not just per-anchor state flips

5. Update docs inline in the same slice
   This user expects docs updated immediately, not as an afterthought.
   - For tracker-driven CentraCast work, distinguish carefully between repo-native proof and live staging proof. If code + `npm test` prove the slice on HEAD but no real runtime-owned staging run exists yet, update the tracker/plan docs with a dated progress note and keep the parent anchor `Partial` instead of claiming `Done`.
   Update the docs that define current reality, not random notes.
   For runtime-hardening slices, that usually means:
   - `README.md`
   - `docs/RUN-ARTIFACTS-SPEC.md`
   - `docs/END-TO-END-GAP-MATRIX.md`
   - `docs/staging-phase3-artifact-regression.md`

   Make the docs say exactly what is now true on HEAD and what remains a gap.

6. Add or update authoritative tests
   - Put behavior coverage in `scripts/run-tests.ts` when that is the repo’s existing test harness.
   - Prefer a real scenario assertion over only source-shape assertions.
   - Cover both top-level deltas and phase/detail-level deltas if the feature is a comparison/reporting helper.
   - If you are expanding a typed runtime contract, write the failing assertions first for the new field/anchor semantics, then implement the smallest contract change needed to satisfy them.
   - Important regression lesson from AF-002 / Wave 1 release-flow work: before changing runtime code, audit whether the failure is actually a brittle test that over-asserts one planner artifact or one exact step ordering. In `centracast-runtime`, planner/execution flows can legitimately rerank from a route-like candidate (for example `item-structured-route-1`) to a strategy winner (for example `strategy-1`), and orchestration may truthfully report execution before release creation. If the implementation behavior is semantically correct, fix the test contract first instead of forcing code to match stale expectations.
   - For HRB-003 / structured-authority slices specifically, cover three surfaces in the same pass: ingress builders must emit `request_contract` (`scripts/staging-run-support.ts` or equivalent), orchestrator routing must actually obey that contract (`LeadOrchestrator.decideRolePath(...)`), and consumption surfaces (`entrypoint/outcome-envelope.ts`, inspect/runtime-consumer fulfillment) must preserve the chosen authority into `fulfillment`. If you only wire ingress + fulfillment while `decideRolePath(...)` still follows free-text objective vibes, the boundary will still behave legacy even though the payload looks structured.
  - A strong regression for that slice is not just `request_contract` shape assertions. Add at least one orchestration-level test where the raw prompt says one thing (for example verification/check) but structured content intake declares `selection_plus_execution`, then assert `role_delegation.chosen_role`, `role_delegation.chain`, and downstream handoff fields like `snapshot.plan.immediate_next_role` follow the structured lane.
  - For HRB-004 / single-selection-proof slices, audit the contract end-to-end before editing: planner output (where the candidate set currently lives, usually `plan_output.content_items`), artifact file map + manifest types, fulfillment logic, inspect/runtime-consumer surfaces, and any Telegram/operator wrappers that currently force humans to infer the chosen item. The reusable rule is: if `selection` or `selection_plus_execution` semantically means "ambil satu", then the runtime is not done until one explicit chosen-item structure survives artifact persistence + inspect round-trips.
  - Good implementation bundle for HRB-004: add typed candidate/chosen-item structures, persist first-class artifacts such as `candidate-items.json` and `chosen-item.json`, thread manifest linkage, make `buildFulfillmentSummary...` mark the run `partial` when a single-selection request has no chosen-item proof yet, and extend inspect/runtime-consumer to answer the chosen item explicitly instead of returning only a list.
  - Practical RED-phase guard for HRB-004: write one manifest-level fulfillment regression and one inspect-surface regression before implementation. The fulfillment regression should assert `buildFulfillmentSummaryFromManifest(...)` downgrades `selection` / `selection_plus_execution` runs to `partial` with a chosen-item-specific reason when no explicit chosen-item proof exists. The inspect regression should assert `inspectManifest(...)` returns `candidate_items`, `chosen_item`, and authoritative artifact refs for both `candidate_items_path` and `chosen_item_path`. Also remember to wire the new helper import into `scripts/run-tests.ts` immediately; otherwise you can get a fake-red failure (`...is not defined`) that proves only the test harness import is stale, not that the runtime contract is missing.
  - Extra hard-won HRB-004 detail: when rebuilding tests or docs from `git show HEAD:<file>` or another clean baseline, verify your reinsertion anchor against the actual HEAD text first. In this repo the same worktree may already contain partial local edits, so a rewrite script can fail with `anchor missing` even though the intended target exists in HEAD under slightly different surrounding content. The safe pattern is: inspect the HEAD snippet with a direct `git show`/Python preview, patch from that exact baseline, then confirm the intended import block and insertion point landed before running the full test harness.
  - Important repair pitfall from HRB-008: if you need to reconstruct a file from a clean baseline, do NOT copy content out of Hermes `read_file()` output because that tool prefixes lines with `LINE|...` markers. Writing that back can silently poison the source file with fake line-number text and create a huge misleading diff. Use `git show HEAD:path/to/file`, `git checkout -- path`, or a direct Python `Path.read_text()`/`write_text()` flow from the real file content instead, then apply the minimal targeted change.
  - Follow-on recovery lesson from HRB-002: if a rewrite accidentally poisons multiple operator scripts with line-number prefixes (for example `scripts/run-tests.ts`, `scripts/staging-run.ts`, `scripts/runtime-consumer.ts`), stop feature work immediately and restore those files from `git show HEAD:<path> > <path>` before continuing. Do not try to debug downstream syntax errors first — the parser explosions are usually just fallout from the poisoned file content. After restore, verify the first few lines with a controller-side read (`Path.read_text()` or similar) before re-applying the intended patch.
  - Another useful HRB-004 doc-sync rule: after the code/tests go green, update three docs together or the slice still reads half-done to future auditors: the tracker entry (`HRB-004` status/progress note), the consumer contract (inspect payload now exposes candidate/chosen item + authoritative artifact paths, and selection truth must stay `partial` without chosen-item proof), and the artifact spec (new file-map links plus planning/execution selection-proof semantics).
  - For HRB-005 / explicit execution-linkage-proof slices, treat co-presence of `chosen-item.json` and `execution.json` as insufficient. The reusable contract is: if authority says `selection_plus_execution`, fulfillment is still only `partial` until one first-class linkage object survives persistence and inspect round-trips.
  - Good implementation bundle for HRB-005: add a typed `linked_execution` structure to the execution scaffold / artifact manifest / file map, persist a dedicated artifact such as `linked-execution.json`, thread its path into `AiAuthoritativeArtifacts`, and expose both the linkage payload and `linked_execution_path` from `inspectManifest(...)` / runtime-consumer surfaces.
  - Strong RED-phase guards for HRB-005 are two manifest/inspect regressions written before implementation: (1) `buildFulfillmentSummaryFromManifest(...)` must downgrade `selection_plus_execution` runs to `partial` with an execution-linkage-specific reason when chosen item + execution exist but no explicit linkage proof is persisted; (2) `inspectManifest(...)` must surface `linked_execution` plus `authoritative_artifacts.linked_execution_path` so operators do not infer the relationship indirectly.
  - Practical implementation pitfall from HRB-005: when widening the artifact contract, update all four surfaces in the same pass — type definitions (`lead-types.ts`, `lead-steps.ts`, `artifact-types.ts`), artifact path/writer plumbing, fulfillment derivation in `entrypoint/outcome-envelope.ts`, and consumer inspect/rendering. If one surface lags, tests can misleadingly show that the file exists while fulfillment still reports `fulfilled` or inspect still hides the linkage.
  - For HRB-006 / novelty-honesty slices, treat renderer wording as a downstream consumer of explicit proof, not as freeform summary copy. The reusable contract is: novelty claims only get stronger if one inspectable `novelty_assessment` survives persistence and reaches inspect/runtime-consumer plus Telegram/operator rendering.
  - Good implementation bundle for HRB-006: add typed novelty-assessment fields (`novelty_confidence`, overlap flags/notes, source candidate ids, selection-strategy metadata), add `novelty-assessment.json` to the artifact file map/writer, thread `novelty_assessment_path` into `AiAuthoritativeArtifacts`, and make renderer helpers map `high|medium|low` confidence to safe wording instead of defaulting to `ide baru` vibes.
  - Strong RED/verify guards for HRB-006 are threefold: (1) `inspectManifest(...)` must return `novelty_assessment` plus `authoritative_artifacts.novelty_assessment_path`; (2) renderer tests must prove explicit novelty proof suppresses generic fallback wording like `Item rencana yang kebaca` / `ide baru mentah`; and (3) low/medium confidence cases should assert overlap-aware wording, not just file existence.
  - Practical implementation pitfall from HRB-006: even when types, writer, outcome-envelope, and Telegram renderer are already patched, `runtime-consumer.ts` can still lag behind and hide the new proof surface. In this repo that showed up as a near-complete slice with one failing regression; the fix was a small consumer inspect patch plus a full `node scripts/run-tests.ts` rerun. So after adding a new artifact-proof field, always audit inspect/runtime-consumer explicitly instead of assuming outcome-envelope exposure is enough.
  - Companion doc-sync pitfall from the same slice: after the code/tests are green, also update the tracker row/section plus consumer/artifact contract docs in the same pass. Otherwise the repo can have landed novelty-proof code while `HRB-006` still reads `Pending` and the published consumer schema still omits `novelty_assessment_path`, which makes later audits think the slice is unfinished.
   - For structured-authority conflict regressions, be careful what you compare. `conflict_with_source_prompt` should compare the raw `source_prompt` against the structured objective/request intent, not against the final resolved objective after CLI overrides; otherwise an explicit CLI objective can accidentally mask the very conflict you were trying to prove.
   - When adding structured authority provenance, assert the high-value fields directly in tests (`source_prompt`, `request_shape`, `authority.primary`, `authority.selected_path`, `authority.conflict_with_source_prompt`, `fallback_behavior`) so the contract cannot silently degrade back to legacy-free-text behavior.
   - For HRB tracker docs, update the parent and child status honestly in the same pass. If a child slice like `HRB-003.A` lands but the parent problem is only partially solved, mark the parent `Partial`, add the child row/section explicitly, and write down what the child does not claim. That keeps the tracker from pretending provenance/reporting work means routing authority is already fixed.
   - For `centracast-runtime` analytics-contract slices specifically, remember the blast radius: update the provider payload type, normalization path, fallback shape, any runtime type guard (for example `isNormalizedAnalytics()`), root exports in `index.ts`, and the docs/gap matrix in the same pass.
   - Also check the normalized `analytics_override` path inside `entrypoint/lead-orchestrator.ts`: if the orchestrator re-wraps a normalized analytics object back into provider-shaped input, new anchors (for example `playlists`) may need explicit remapping (for example `playlists -> existing_playlists`) or the harness path will silently lose evidence even though raw-provider ingestion works.
   - Add at least one orchestration-level regression, not just a pure normalization test, whenever analytics fields are added. A field can pass unit normalization and still get dropped during the override/handoff path.
   - For parity/comparability slices, do not stop at anchor-state ledgers alone. If normalization already emits provenance or weak-evidence notes, explicitly thread them through the coverage-summary layer too. Otherwise CLI/artifacts will show which anchors are missing but hide whether the sample came from live provider payloads, fallback-only evidence, or operator-supplied overrides.
   - If the slice adds a new persisted artifact field (for example analytics coverage metadata), check both persistence paths: the core artifact writer and the staging CLI post-processing/final-hydration path (`scripts/staging-run-support.ts`, `scripts/staging-run.ts`). Otherwise the value may appear in stdout or `result_snapshot` but never make it into the rewritten local `manifest.json` / `final-summary.md` artifacts.
   - When you add provenance/parity notes to analytics coverage, cover three surfaces in tests: the structured summary object, rendered staging-output lines, and persisted `final-summary.md` content. This repo is especially prone to values surviving normalization but being dropped by the human-facing reporting layer.
   - One more parity pitfall: after notes are visible in CLI/artifacts, widen `compareRunArtifacts()` too. Otherwise local-vs-live comparisons can still hide a meaningful provenance mismatch when anchor states/richness happen to match. Add a regression where only `analytics_coverage.notes` changes (for example live sampled payload vs override/fallback note) and assert both `deltas` and `summary_lines` surface that drift.
   - Another comparability pitfall from issue #17: even after analytics drift is covered, runs can still look "similar" while the operator-facing story changed. For artifact-comparison slices, consider manifest-level narrative fields as parity signals too: `objective`, `parent_objective_id`, `qa_triage_summary`, `qa_stage_alerts`, and `qa_top_issues`. If you widen `compareRunArtifacts()` to include them, also update any older regression that asserted the exact `deltas.map(field)` list — otherwise a good contract improvement will break a brittle expectation.

7. Run reality checks
   Minimum:
   - `npm test`

   If the slice adds operator-facing tooling, also exercise it directly against real persisted artifacts or real repo examples.
   Example:
   - `npm run artifacts:compare -- <left-manifest> <right-manifest>`

   Do not claim a tool works until it has been run on actual files.

8. Reconcile tracker status honestly before closing anything
   - If the target is a tracker/epic, inspect the child issues or explicitly named focus areas before declaring it done.
   - Check whether the epic is actually finishable in this session versus only partially advanced.
   - If multiple child issues remain open, do NOT close the parent just because one or two slices landed.
   - Instead:
     - comment on the parent with what is now proven,
     - name the remaining open areas,
     - pick the most leverage-y next child slice.
   - Useful pattern:
     - `gh issue view <parent> --comments`
     - `gh issue view <child> --json number,title,state,body,url`
   - In practice for CentraCast runtime hardening, if live staging parity/comparability is proven but analytics grounding is still thin, prefer continuing into provider-ingestion work before claiming epic closure.
   - Another hard-won tracker-sync rule: when preserved todo/context says an HRB slice is still in progress but the repo is already clean, treat the tracker itself as potentially stale. Audit the current HEAD against the slice's acceptance proof before changing issue state. If the code has clearly advanced beyond `Pending` but still misses explicit contract surfaces from the redesign doc, mark the slice `Partial` instead of forcing `Done` or leaving it `Pending`. Also sync any adjacent rows exposed by the audit (for example a child slice that is actually already done) so the tracker table and per-section status tell the same story.

9. If the user wants “mode mandor”, use subagents as auditors before choosing the next slice
   - Good trigger phrases: `mode mandor`, `lanjut next slice`, `ambil thin slice berikutnya`.
   - After finishing/pushing the current slice, delegate 2–3 parallel audit tasks that inspect the repo from slightly different angles:
     - one reviewer for highest-value next thin slice from the issue body / recent commits,
     - one reviewer focused on staging/live proof gaps,
     - one reviewer focused on docs/tests/operator workflow.
   - Tell each subagent to recommend exactly one narrow next slice, with rationale, likely files, acceptance criteria, and risks, and to avoid making edits.
   - Controller-side rule: trust the synthesis, not any single reviewer. Choose the slice with the best proof-per-blast-radius ratio.
   - In practice, this works especially well after comparability/reporting slices land: auditors often reveal that the cheapest remaining gap is proof durability, not another comparison-field expansion.
   - Example reusable outcome from issue #17: once `compareRunArtifacts()` already surfaced objective/QA/provenance drift, the best next slice was to persist the live harness compare output as a durable receipt beside the run artifacts rather than adding more diff fields.
   - Follow-on lesson from the same issue: after the compare receipt exists, the next cheap blind spot is often backend-vs-local reconstruction drift. A strong next thin slice is to persist a second proof artifact derived only from the final hydrated backend row (for example `hydrated-parity-receipt.json` from `GET /operator-runs/{id}` containing status/timestamps, truth+hahdoff presence, step-progress signature, artifact presence/file booleans, comparability, telemetry, QA counts, and phase-outcome skeleton) and make the live harness diff create-vs-resume receipts too. That catches backend persistence/serialization drift that can stay hidden when local code can still regenerate a rich `manifest.json` around a thinner row.
   - One more experiential follow-on: once hydrated receipts exist, don’t stop at generic backend-row skeleton parity. Thread the highest-value analytics proof anchors into the hydrated receipt too — specifically the remote-parity troublemakers like retention, traffic sources, and playlists (for example `average_retention_rate`, `traffic_sources`, `existing_playlists`). Add a dedicated compare helper/CLI (for example `compareHydratedParityReceipts()` / `artifacts:compare-hydrated`) and make the live harness persist that JSON compare artifact and fail non-zero on meaningful hydrated drift. Otherwise the harness can still bless runs where the backend row silently drops or mutates anchor-proof state even though the locally regenerated manifest looks fine.
  - Final follow-on from issue #17: once hydrated compare covers the three headline analytics anchors, widen it one more notch to carry the sampled `analytics_coverage` summary too (`endpoint_available`, `evidence_richness`, `provider_signal_count`, missing/populated/unavailable/explicit-null/explicit-empty buckets, and provenance notes). Reason: backend-row parity can still look deceptively similar on anchor-state alone while the real live-vs-override/fallback richness story drifted. When adding this, update both the persisted `hydrated-parity-receipt.json` writer and the hydrated compare regression in `scripts/run-tests.ts`, then sync README/spec/runbook docs so operators know the hydrated receipt is no longer just an anchor-proof skeleton.
  - One more durable-proof follow-on from the same issue: after normalized coverage, manifest compare, and hydrated receipts are all persisted, the next cheap blind spot may be the exact upstream analytics payload itself. If staging sampled a real provider payload before orchestration, consider persisting that raw sample as a first-class artifact (for example `analytics-provider-sample.json`) beside `analytics.json` / `manifest.json` so parity audits can inspect both the pre-normalization source and the normalized runtime view without reconstructing from logs. When doing this, remember the subtle artifact-writer pitfall: adding a second file under the same stage can accidentally duplicate `completed_stages` and skew telemetry unless stage completion is deduped; cover the file on disk, summary/discovery output, and telemetry expectations in `scripts/run-tests.ts`.

10. Update the GitHub issue inline before finishing
   - Post a comment on the epic/tracker with:
     - what slice landed,
     - which files/interfaces/scripts changed,
     - verification results,
     - why the slice matters relative to the issue’s focus areas.
   - When working from a tracker, include the honest remaining gaps and the next recommended child issue.
   - Use `gh issue comment <N> --body-file - <<'EOF' ... EOF`
   - This keeps progress visible and matches the user’s preference.

11. Final audit
   - Re-run `git status --short`
   - Call out any untracked generated artifacts (for example `docs/runs/...`) separately from source changes.
   - Do not pretend the tree is clean if generated run artifacts are still present.
   - If the worktree is already dirty when you enter the slice, do not assume the in-flight changes are valid just because they point at the right issue. Inspect the changed files directly before running tests, commenting on issues, or claiming partial completion.
   - Specifically for runtime truth/fulfillment slices: if `git status`/`git diff` shows edits around `entrypoint/outcome-envelope.ts`, `entrypoint/lead-orchestrator.ts`, `artifacts/write-run-artifacts.ts`, or consumer inspect surfaces, read the helper source itself before proceeding. A dirty tree can contain half-applied or corrupted edits that make the apparent slice look farther along than reality.
   - Do not trust search hits / imports / exports alone as proof that a helper exists or is valid. In this repo, a corrupted helper can still appear in `search_files` results because other files import/export the symbol. Always open the defining file with `read_file` and confirm the implementation is actually present and syntactically sane before wiring more call sites.
   - Also do not over-trust a single file-preview/readout when it shows obviously impossible placeholder garbage. In this repo/tooling mix, preview/cache noise can show stale fragments like `input....ion`, `outcom...acts`, or `***` even after the real file is fixed. If that happens, cross-check the actual file state with at least one controller-side reality check such as: `search_files` for the garbage token, a direct Python `Path(...).read_text()` snippet, and/or `git diff` / `git show` on the file before deciding the tree is still broken.
  - Extra nuance from HRB-002 closeout: if a controller-side Python/text snippet still appears to show an impossible token but a raw character/byte inspection reveals normal source text (for example `const authoritativeArtifacts = outcome?.authoritative_artifacts` while the display renders `outcom...acts`), treat it as tool/UI truncation rather than source corruption. Verify by checking token presence/absence explicitly before doing any restore/rewrite.
   - If a foundational helper file is syntactically or semantically corrupted (for example obvious placeholder garbage like `input....ion`, `***`, or truncated builder calls inside the fulfillment/outcome path), treat that as the primary blocker: do not post progress comments, do not claim the slice landed, and do not move to commit/push until the helper is repaired and re-verified.
   - If the user says to `sapu` / clean the artifact residue first, prefer a two-step cleanup:
     1. restore tracked generated files under the affected run-date folder (for example `git restore -- docs/runs/2026-04-01`)
     2. explicitly remove leftover untracked run folders or generated proof/sample files (`run-*`, `remote-analytics-richness-proof.json`, `analytics-provider-sample.json`) only after verifying they are just local residue.
   - After cleanup, re-run `git status --short` and make sure only intentional source files remain before commit/push.
   - If the user says `beresin` / `gas lanjut` after you already reported commit/push/comment as done, or the session resumes with preserved todos/context that still say `in_progress`, do a controller-side verification pass before taking any new destructive or redundant action.
   - Important: preserved todo state and compressed context are not authoritative. They can lag behind the actual repo/issue state after a successful previous slice.
   - Verify with:
     - `git status --short --branch`
     - `git rev-parse HEAD && git rev-parse origin/main`
     - `gh issue view <N> --comments` or `--json comments`
   - Treat `clean source worktree (ignoring clearly-generated docs/runs residue if applicable) + HEAD == origin/main + issue comment present` as a valid terminal state. In that case, report that everything is already landed instead of inventing extra cleanup work.
  - Extra tracker-hygiene nuance from HRB-005: after proving the code path is already landed (clean tree, tests green, relevant commits present), separately verify whether the tracker markdown and GitHub issue still say `Pending`/`OPEN`. If code is done but tracker hygiene lags, classify it honestly as `implementation already landed; docs/issue status still stale` rather than reopening implementation work. The right next step is tracker/doc reconciliation, not another code pass.
  - Follow-on nuance from HRB-007: when resumed/compressed context still says a slice is `in_progress` but `git status` shows only tracker-doc edits or even a clean tree, do not assume more implementation is needed. Audit three things first: (1) summary-table row status in the tracker, (2) per-slice section status/progress note, and (3) issue comments proving the slice landed. If code/tests already back the acceptance proof, the correct closure path may be docs/issue sync + one docs-only commit/push.
  - HRB-007 also showed a reusable renderer/wrapper closure pattern: for operator-facing truth-consumption slices, acceptance is not just code green. Confirm the human surfaces are already covered by regressions (`render-runtime-summary`, wrapper scripts like `ccrun`/`ccinspect`/`ccblocker`), then update tracker row + slice section + issue comment in the same pass so the repo stops claiming `Pending` after the behavior already shipped.
  - OMB wave work added a similar doc-sync rule for execution-pack repos: if the active contract lives in a wave pack / master brief (for example `OPENCLAW-OMB-WAVE-IMPLEMENTATION-PACK.md`), do not stop at code + tests + GitHub issue. Update the wave section status itself (`Proposed` -> `Done` or honest partial state) and add a dated progress note that names the concrete behavior now proven on HEAD. That keeps the execution pack, issue state, and repo reality aligned.
  - For Wave B / renderer-hardening style slices specifically, the reusable proof bundle is: (1) renderer helpers must consume persisted proof fields like `fulfillment_level`, `fulfillment_reason`, `proof_status`, `comparability_status`, and `next_safe_action`; (2) regressions must cover a `completed` run that still renders as partial when proof is incomplete; and (3) blocker wording must distinguish `inspect_blocking_artifact` from an actual resumed run. If those are already green, the remaining work is usually docs/issue closeout, not more renderer churn.
  - HRB-009 added one more reusable closeout pattern: sometimes the highest-leverage slice is not new implementation but proving that implementation already exists on HEAD and then closing the documentation/guardrail gap honestly. In that case, first audit the issue acceptance proof against repo reality (`gh issue view`, tracker section, `git diff --stat`, focused `git diff`, and the authoritative test harness). If the named regressions are already present and green, do not invent extra code churn just to "do work" — land a docs/tracker/issue closeout slice instead: explicitly document what is now true on HEAD, add reviewer guardrails/checklists to the repo-facing docs, comment the issue with proof, close it, then commit/push the docs-only reconciliation.

## Heuristics for choosing the slice

Prefer slices that are:
- directly named by the issue body,
- testable in one session,
- additive instead of risky refactors,
- useful for future live staging verification,
- observable by operators (scripts, summaries, comparable outputs).

For tracker issues, avoid trying to “finish the epic” in one swing.
Choose one slice that reduces manual debugging pain or increases verification credibility.

If the user pushes back on overly-thin slicing and wants something more bundled (`sekalian`, `jangan thin slice mulu`, `bundle issue #N`), change strategy deliberately:
- do NOT expand to “everything in the repo”;
- instead choose one medium-sized bundle inside a single contract area;
- keep code, tests, docs, and live-proof surfaces in the same bundle;
- avoid mixing unrelated domains just to make the diff look bigger.

A good bundle for `centracast-runtime` usually looks like one of these:
- live analytics richness audit + stronger remote proof surfaces + operator-facing compare/report tightening
- one analytics/parity contract change across normalization, artifact persistence, compare helpers, tests, and docs
- one operator-proofing bundle across staging runner output, persisted receipts, regressions, and runbook docs

For the specific “remote analytics richness proof” bundle (issue #17 style), the durable implementation checklist is:
- add a small typed proof helper (for example `buildRemoteAnalyticsRichnessProof(summary)`) that turns `analytics_coverage` into an explicit verdict (`strong` / `bounded` / `weak` / `fallback`), blocking-anchor list, parity-claim boolean, boundary reason, and per-anchor proof notes
- persist that proof as its own first-class artifact (for example `remote-analytics-richness-proof.json`) and also thread it into `manifest.json` / `final-summary.md`
- surface the same verdict in staging operator output, including an explicit gate line like `remote_live_parity_gate: pass|hard-warn` plus the boundary reason; do not leave the operator to infer it from raw anchor lists
- widen both comparison surfaces, not just one: `compareRunArtifacts()` for manifest parity and `hydrated-parity-receipt.json` + `compareHydratedParityReceipts()` for backend-row parity
- when wiring staging persistence, remember there are usually two `writeRunArtifacts()` refresh paths in `scripts/staging-run.ts` (post-execute and post-final-GET). Thread the proof through both, or the artifact can appear in one path and disappear in the authoritative final path
- cover five surfaces in regression tests: proof builder semantics, rendered staging summary lines, persisted manifest/final-summary content, staging-run source wiring assertions, and hydrated compare drift

When deciding between thin-slice vs bundle, use this rule:
- thin slice if the root cause or blast radius is still uncertain
- medium bundle if the domain is already clear and the user explicitly wants faster progress without fragmented PRs

In other words: bundle aggressively within one coherent proof domain, not across unrelated subsystems.

## Pitfalls

- Editing before reading the epic body
- Treating the issue title as enough context
- Landing code without docs updates
- Running only unit-ish assertions and never exercising the operator-facing script
- Forgetting to comment back on the GitHub issue
- Hiding untracked generated artifacts in the final summary

## Success criteria

A good epic slice ends with all of this true:
- repo/branch was verified first,
- issue body drove slice selection,
- code + docs were updated together,
- `npm test` passed,
- new operator-facing path was exercised for real if applicable,
- the GitHub issue received a progress comment,
- final summary clearly distinguishes code changes from generated artifact drift.
