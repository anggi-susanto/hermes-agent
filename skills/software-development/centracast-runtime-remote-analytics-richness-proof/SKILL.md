---
name: centracast-runtime-remote-analytics-richness-proof
description: Add and verify durable remote analytics richness proof artifacts in centracast-runtime staging/run flows.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# CentraCast Runtime Remote Analytics Richness Proof

Use this when a task asks to tighten local-vs-live parity proof around analytics richness in `centracast-runtime`.

## When to use
- User asks to make live/staging analytics parity more explicit
- Need a repo-owned verdict for whether sampled remote analytics are rich enough to claim meaningful live parity
- Need durable proof in artifacts, summaries, and hydrated receipts

## Steps
1. Work in `/opt/gunamaya-ai/workspaces/centracast-studio/centracast-runtime`.
2. Add a dedicated analytics helper (for example `analytics/remote-richness-proof.ts`) that derives a verdict from `AnalyticsCoverageSummary`.
3. Keep the verdict machine-readable. Include at least:
   - verdict
   - can_claim_meaningful_live_parity
   - proof_strength
   - provider_signal_count
   - blocking_anchors
   - boundary_reason
   - boundary_notes
   - per-anchor proof/state
4. Thread that proof through operator-facing staging output (`scripts/staging-run-support.ts`) so the CLI prints explicit gate lines instead of making operators infer the result.
5. Persist the proof in run artifacts by widening:
   - `RunArtifactFileMap`
   - `RunArtifactManifest`
   - `WriteRunArtifactsInput`
   - `buildRunArtifactFileMap()`
   - `writeRunArtifacts()`
6. Add a durable JSON artifact like `remote-analytics-richness-proof.json` and include it in `final-summary.md`.
7. Carry a compact proof envelope into `hydrated-parity-receipt.json` inside `scripts/staging-run.ts`.
8. Widen both compare surfaces:
   - `artifacts/compare-run-artifacts.ts`
   - `artifacts/compare-hydrated-parity-receipts.ts`
9. Update docs the same pass, at minimum:
   - `README.md`
   - `docs/RUN-ARTIFACTS-SPEC.md`
10. Add regression coverage in `scripts/run-tests.ts` for:
   - proof builder behavior
   - summary rendering
   - artifact persistence
   - hydrated receipt compare deltas
   - source guards for staging-run wiring
11. Run `npm test` and ensure generated `docs/runs/...` residue is cleaned before commit.
12. Commit to `main` in this repo if the user asked to push directly.

## Pitfalls
- Do not over-claim parity: `strong` should only be claimable when the richness contract is actually satisfied.
- Preserve explicit null vs explicit empty vs unavailable distinctions.
- Avoid counting the analytics stage twice when adding new artifact files.
- Keep hydrated receipt proof compact; it should be durable and diffable, not a full duplicate of the manifest.

## Verification
- `npm test`
- `git status --short` should be clean after commit/push
- `gh issue comment <n>` with an honest note that proof/auditability improved even if upstream staging richness is still sparse
