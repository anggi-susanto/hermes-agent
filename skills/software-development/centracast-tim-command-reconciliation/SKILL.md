---
name: centracast-tim-command-reconciliation
description: Audit and reconcile the CentraCast TIM command surface when legacy TIM scripts diverge from the canonical runtime-consumer/LeadOrchestrator flow.
---

# CentraCast TIM command reconciliation

Use this when the user asks to audit, fix, or unify the TIM command flow in `centracast-runtime`, especially when `bin/tim-runner.cjs` or `scripts/tim-*.sh` have drifted away from the canonical runtime flow.

## When to use
- User asks to audit TIM command flow end-to-end
- TIM docs mention one-shot/legacy behavior but runtime reality is `runtime:consumer`
- `bin/tim-runner.cjs` writes placeholder artifacts or bypasses `LeadOrchestrator`
- `inspect` / `compare` surfaces exist in `runtime:consumer` but not in TIM docs/entrypoints

## Goal
Make TIM a compatibility façade over the canonical runtime flow instead of a second execution engine.

## Canonical truth to preserve
- Real execution path: `scripts/runtime-consumer.ts` -> `scripts/staging-run.ts` -> `LeadOrchestrator`
- Authoritative artifacts: `docs/runs/YYYY-MM-DD/run-*/manifest.json`
- Canonical inspect/query surface:
  - `inspect latest`
  - `inspect run <run-id|manifest-path|run-dir>`
  - `inspect blocker [ref]`
  - `compare <left> <right>`

## Audit steps
1. Inspect `bin/tim-runner.cjs`, `scripts/tim-run.sh`, `scripts/tim-resume.sh`, `scripts/runtime-consumer.ts`, and `scripts/run-tests.ts`.
2. Confirm whether TIM is still:
   - reading SSOT/prompt pack directly
   - validating hardcoded required fields
   - writing to `docs/orchestration/runs/...`
3. Confirm runtime-consumer already owns inspect/compare and modern artifact semantics.
4. Search docs under `docs/orchestration/` for stale references to legacy artifact paths or fake one-shot semantics.

## Implementation pattern
1. Keep `bin/tim-runner.cjs` as the TIM-branded entrypoint, but replace its execution logic with a wrapper.
2. Add a small parser module (for example `scripts/tim-cli.js`) that:
   - accepts legacy TIM usage like `input.json --run-type execution --pretty`
   - translates `input.json` into `--intake-file`
   - keeps `--run-type` only as a compatibility hint
   - supports passthrough for `inspect`, `compare`, and explicit `run`
   - supports resume semantics with `--run-id`
3. Have `bin/tim-runner.cjs` spawn:
   - `node --experimental-strip-types scripts/runtime-consumer.ts ...`
4. Do not let TIM write its own artifact tree anymore.
5. Update `scripts/tim-resume.sh` usage so resume means real `--run-id` resume, not fake rerun.
6. If useful, add helper npm scripts like `tim:inspect`.

## Required doc reconciliation
Update TIM docs so they describe TIM as a wrapper/command surface, not the real engine:
- `docs/orchestration/TIM-README.md`
- `docs/orchestration/TIM-ssot.md`
- `docs/orchestration/TIM-runner.md`
- `docs/orchestration/TIM-runner-script.md`
- `docs/orchestration/TIM-quickstart.md`
- `docs/orchestration/TIM-usage.md`
- `docs/orchestration/TIM-resume.md`
- `docs/orchestration/TIM-command-prompt.md` (must stop describing TIM as a standalone one-shot engine)
- `docs/orchestration/TIM-fill-missing.md` (must describe canonical blocker/recovery semantics, not placeholder artifact skeletons)

Also search for stale references to `docs/orchestration/runs/...` across docs and either remove them or explicitly mark them as historical residue / deprecated.

## Required regression coverage
Add tests in `scripts/run-tests.ts` for:
- legacy TIM parser translation -> canonical runtime-consumer args
- inspect/compare passthrough behavior
- assertion that `bin/tim-runner.cjs` delegates to `runtime-consumer.ts`
- assertion that TIM no longer references `docs/orchestration/runs` directly

## Verification checklist
Run at least:
- `node bin/tim-runner.cjs --help`
- `node bin/tim-runner.cjs inspect latest --json`
- `node bin/tim-runner.cjs compare <left> <right> --json`
- `node --experimental-strip-types scripts/run-tests.ts`

After verification, always run `git status --short` and clean any regenerated `docs/runs/...` artifact churn before concluding the repo is ready to commit/push. In this repo, inspect/compare/test verification can re-materialize tracked runtime artifacts or proof files under `docs/runs/YYYY-MM-DD/...` even when the actual TIM wrapper/docs change is already committed.

## Interpretation rules
- If live `run` through TIM fails with upstream API 500s, treat that as proof the wrapper is using the real runtime path; do not misclassify it as wrapper failure.
- Success criteria is command-surface unification plus modern artifact/query behavior, not forcing fake local success.

## Pitfalls
- Do not preserve a second artifact sink under `docs/orchestration/runs/...`
- Do not leave docs claiming TIM itself performs full orchestration if runtime-consumer actually does it
- Do not call fake reruns a “resume” unless they pass `--run-id` into the canonical flow
- `--pretty` may need to map to `--json` for compatibility if runtime-consumer only exposes JSON mode

## Done when
- TIM command delegates to runtime-consumer
- TIM docs point to `docs/runs/...` as authoritative
- inspect/compare are available from the TIM surface
- regression tests cover the wrapper behavior
- no direct legacy artifact-writing logic remains in `bin/tim-runner.cjs`
