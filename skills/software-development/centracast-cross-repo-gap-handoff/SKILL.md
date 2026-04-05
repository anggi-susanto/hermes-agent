---
name: centracast-cross-repo-gap-handoff
description: Reframe and hand off a CentraCast gap from centracast-runtime to centracast when live verification shows the runtime path is working but backend/provider payload richness is still the real blocker.
---

# CentraCast Cross-Repo Gap Handoff

Use this when a runtime-facing issue in `centracast-runtime` turns out to be mostly solved on the runtime side, and the remaining blocker actually lives in the Laravel backend repo `centracast`.

Typical trigger:
- live staging route exists and responds
- runtime normalization/coverage logic is working
- tests pass in `centracast-runtime`
- remaining gap is weak/null-heavy upstream payload richness (not route absence, not runtime glue)

## Goals

1. Tell the truth in docs/tests/issues.
2. Preserve runtime proof in `centracast-runtime`.
3. Create a clean backend follow-up in `centracast`.
4. Close or narrow the runtime issue without mixing repo scopes.
5. Re-anchor yourself on the active GitHub issue contract before going deep on one subproblem.

## First rule: read the active issue before summarizing status

If the user asks “balik ke issue mana yang masih checklist / belum” or points at a specific GitHub issue, do this before giving a status summary:

```bash
gh issue view <number> --repo <owner/repo>
gh issue view <number> --repo <owner/repo> --comments
```

Use the issue body as the outcome contract and the latest comments as the progress ledger.

Do not answer from memory of one technical branch (for example CTR only) if the issue itself is broader (for example payload richness across playlists, retention, duration, and CTR). Reconcile your technical findings back to the issue checklist first.

## Required preflight

Before editing or pushing anything:

```bash
pwd
git branch --show-current
git remote -v | head
git status --short
```

Expected repo defaults in this workspace:
- `centracast-runtime`: `main` is okay by default
- `centracast`: staging-scoped work should stay on `staging` unless the user explicitly asks otherwise

## Runtime-side procedure (`centracast-runtime`)

1. Verify the live truth first.
   - Confirm `/channels/{id}/content-analytics` is reachable on staging.
   - Identify which anchors are:
     - populated
     - explicit null
     - explicit empty
     - unavailable
   - Do not keep stale wording that claims the route is absent if it is now live.

2. Update docs so they match reality.
   - Usually at least:
     - `README.md`
     - `docs/END-TO-END-GAP-MATRIX.md`
   - Replace route-absence claims with payload-richness claims when appropriate.

3. Add or tighten a repo-native regression.
   - Lock the currently observed live contract with a narrow test fixture.
   - Prefer a test that freezes the exact anchor-state ledger, e.g.:
     - `top_videos` => populated
     - `average_ctr` => explicit null
     - `existing_playlists` => unavailable
   - Avoid brittle assertions on derived counts if the count is an implementation detail and the anchor-state contract is the real behavior you care about.

4. Run the authoritative runtime harness.

```bash
npm test
```

5. Comment on the runtime issue with an honest audit.
   - State what is now confirmed.
   - State what remains open.
   - Separate runtime-complete work from backend-richness follow-up.
   - Use the issue comment as a live ledger of proof.

6. If needed, retitle the runtime issue to narrow its scope.
   - Example pattern:
     - from vague parity wording
     - to explicit live-provider-richness wording

## Backend follow-up procedure (`centracast`)

Create a new issue in `gunamaya/centracast` when the remaining work is clearly backend/provider-side.

The issue body should include:
- why the runtime side is no longer the main blocker
- current observed live anchor state
- which anchors remain null/unavailable
- outcome contract for backend richness
- verification path via live staging API
- backlink to the runtime issue

Recommended framing:
- runtime can already ingest/classify richness correctly
- backend still needs to fill CTR / retention / duration / playlist anchors where source data allows
- explicit null/unavailable semantics should remain honest when data truly does not exist

## Closure procedure for the runtime issue

Close the runtime issue only when the runtime side is actually done.

Closure note should say:
- runtime-side ingestion/normalization/tests/docs are complete
- remaining work moved to backend follow-up issue in `centracast`
- include direct link to the backend issue

This avoids fake closure while still keeping issue hygiene clean.

## When both referenced issues are already closed

If the user says “beresin yang masih actionable” but the runtime issue and backend follow-up are both already closed:

1. Re-read both issues/comments first.
2. Search for relevant OPEN follow-up issues before touching code.
3. Inspect local diffs in both repos to see whether you already started on a stale interpretation.
4. If there is no active follow-up issue and the local edits are tied to the closed scope, revert those stray edits instead of forcing more code into a dead track.
5. Report the honest outcome explicitly:
   - no active actionable issue remains on this track
   - workspace was cleaned up
   - any future work (for example a new metric family like `average_view_duration_seconds`) must be tracked as a new issue, not smuggled in under the closed one

This prevents continuing on autopilot just because there are local diffs or because one sub-gap still sounds interesting technically.

## Commit hygiene

When working in `centracast-runtime`, commit only the files that belong to the truth-sync / regression slice.

Common safe set:
- `README.md`
- `docs/END-TO-END-GAP-MATRIX.md`
- `scripts/run-tests.ts`

Be careful with residue in generated artifacts under paths like:
- `docs/runs/<date>/...`

If those were already modified by prior local runs and are not the point of the change, do not sweep them into the commit just because they are dirty.

Useful check:

```bash
git status --short
git diff --stat -- README.md docs/END-TO-END-GAP-MATRIX.md scripts/run-tests.ts
```

## Good commit shape

Example message:

```bash
git add README.md docs/END-TO-END-GAP-MATRIX.md scripts/run-tests.ts
git commit -m "docs: lock live analytics anchor truth for issue 10"
```

## Additional boundary lesson: asset-first operator flow may invalidate the assumed runtime repo target

When auditing a supposed `centracast-runtime` gap around release creation/publish flow, do not assume the runtime is the right place to patch just because the user mentioned runtime alignment or a wrapper flow.

If the operator truth is:
- start from an existing reviewed audio asset
- create a real single release from that asset
- generate SEO
- generate cover art / thumbnail
- upload to YouTube

then do this before patching anything substantial in `centracast-runtime`:

1. Verify whether runtime actually owns a first-class action contract for that lane.
   - Inspect structured request shapes in `entrypoint/lead-types.ts`
   - Inspect `consumer/runtime-consumer.ts` materialization logic
   - Inspect whether the lane is real business mutation routing or only planning/execution scaffolding

2. Check whether the runtime only supports abstract shapes like:
   - `strategy`
   - `selection_plus_execution`
   rather than explicit asset-first business actions.

3. If the runtime lacks an authoritative action contract and the docs show the real mutation endpoints already live in `centracast` (Laravel/OpenClaw), stop calling it a pure runtime bug.

4. Reclassify the gap precisely:
   - runtime wrapper mismatch / fantasy contract
   - backend-owned canonical business lane
   - cross-repo boundary issue, not a local runtime-only bug

5. Report the boundary honestly before coding.
   - Say explicitly that patching runtime first would be cosmetic if the authoritative release/SEO/thumbnail/upload mutations still live in `centracast`
   - Prefer backend-first implementation when the goal is end-to-end proof of the operator happy path

### Reconciliation mode when backend Wave C already landed

If live verification shows the backend gap is no longer open (for example canonical lifecycle/readback truth now exists on staging), do not keep acting like the runtime repo still needs to invent the backend fix.

Use this sequence:
1. Re-anchor the runtime repo (`git status`, HEAD, branch) and confirm the remaining work is actually runtime-side.
2. Search runtime docs for stale claims like:
   - canonical readback is missing
   - upload/publish is hybrid only because backend truth is absent
   - Wave C is still an unshipped backend need
3. Reconcile the affected runtime docs so they say:
   - backend canonical lifecycle/readback truth now exists
   - runtime follow-up is doc/consumer reconciliation
   - any remaining hybrid classification is due to fulfillment/orchestration proof, not endpoint absence folklore
4. Sweep adjacent docs, not just one audit file. In practice this often includes:
   - `README.md`
   - OMB master brief / audit / wave pack / intent-routing matrix / guardrails docs
5. Run the runtime repo's authoritative verification (`npm test`) even if the slice is docs-heavy, so the repo remains cleanly shippable.
6. Commit and push the runtime reconciliation slice as a docs truth-sync change.

This prevents a common failure mode: the backend has already fixed the contract, but runtime docs keep preserving the old story and mislead future audits.

This matters because `centracast-runtime` can look active and structured while still only modeling planning/execution scaffolds. For asset-first release work, the real source of truth may still be the Laravel backend business API.

## Pitfalls

- Leaving stale docs that still claim the route is missing
- Closing the runtime issue without creating a backend follow-up
- Mixing runtime repo fixes and backend repo fixes into one issue scope
- Committing `docs/runs/*` residue accidentally
- Over-asserting implementation-specific counts when anchor-state truth is the stable contract
- Treating an asset-first release lane as a runtime-only implementation gap before checking whether runtime even has a first-class action contract for it
- Shipping a cosmetic runtime wrapper patch when the authoritative business mutations still live only in `centracast`
- Forgetting to inspect `consumer/runtime-consumer.ts` and structured request shapes before concluding that runtime supports the operator lane

## Success criteria

- runtime docs match live staging truth
- runtime regression locks the observed anchor-state contract
- `npm test` passes
- runtime issue comment shows honest proof
- backend follow-up issue exists in `centracast`
- runtime issue is retitled/closed only if its remaining work has truly moved upstream
