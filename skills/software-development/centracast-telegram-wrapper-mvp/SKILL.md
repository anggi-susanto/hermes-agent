---
name: centracast-telegram-wrapper-mvp
description: Build Telegram-first CentraCast runtime wrappers in centracast-runtime with human-readable output and Hermes quick_commands wiring.
---

# CentraCast Telegram Wrapper MVP

Use this when the user wants Telegram to become the first control surface for `centracast-runtime` without modifying Hermes gateway code yet.

## Goal

Ship repo-owned wrapper scripts in `centracast-runtime` that expose:
- `/ccinspect`
- `/ccblocker`
- `/ccrun`
- `/ccideas`
- `/ccbriefs`
- `/ccqa`
- `/ccschedule`
- `/ccideas`
- `/ccbriefs`
- `/ccqa`
- `/ccschedule`

These wrappers must consume the canonical `runtime:consumer` surfaces and render Telegram-safe human text instead of raw JSON.

Additional artifact-view wrappers (`ccideas`, `ccbriefs`, `ccqa`, `ccschedule`) should inspect the latest run or an explicit run ref, then render only the relevant artifact slice in human-readable form.

## Preconditions

1. Verify the active repo is `centracast-runtime` on the intended branch.
2. Check dirty files with `git status --short` and avoid unrelated edits.
3. Confirm `runtime:consumer` already supports:
   - `run`
   - `inspect latest`
   - `inspect run <ref>`
   - `inspect blocker [ref]`
4. Confirm `npm test` is the authoritative test harness.

## Files to create

Under `scripts/telegram/`:
- `render-runtime-summary.mjs`
- `ccinspect.sh`
- `ccblocker.sh`
- `ccrun.sh`
- `ccideas.sh`
- `ccbriefs.sh`
- `ccqa.sh`
- `ccschedule.sh`
- `README.md`

## Wrapper contract

### ccinspect
- Accept zero or one arg only.
- No args => `npm run --silent runtime:consumer -- inspect latest --json`
- One arg => `npm run --silent runtime:consumer -- inspect run "$1" --json`
- Pipe JSON to the renderer in `inspect` mode.
- On malformed args, print a compact operator-safe error to stdout and exit nonzero.

### ccblocker
- Accept zero or one arg only.
- No args => `npm run --silent runtime:consumer -- inspect blocker --json`
- One arg => `npm run --silent runtime:consumer -- inspect blocker "$1" --json`
- Pipe JSON to the renderer in `blocker` mode.
- On malformed args, print a compact operator-safe error to stdout and exit nonzero.

### ccrun
- Require at least one arg.
- Forward arguments exactly once via `npm run --silent runtime:consumer -- run "$@"`
- Pipe JSON to the renderer in `run` mode.
- On missing objective, print a compact operator-safe error to stdout and exit nonzero.

### ccideas / ccbriefs / ccqa / ccschedule
- Accept zero or one arg only.
- No args => `npm run --silent runtime:consumer -- inspect latest --json`
- One arg => `npm run --silent runtime:consumer -- inspect run "$1" --json`
- Pipe JSON into the renderer with modes `ideas`, `briefs`, `qa`, or `schedule`.
- On malformed args, print a compact operator-safe error to stdout and exit 2.

## Renderer rules

Implement `scripts/telegram/render-runtime-summary.mjs` as a small Node script that:
- Accepts mode: `inspect|blocker|run|ideas|briefs|qa|schedule|error`
- Reads JSON from stdin (or optional file path for debugging)
- Emits plain human-readable text for Telegram
- Never emits raw JSON on success
- Default operator-facing replies for all three happy-path modes (`inspect`, `blocker`, `run`) should use the same compact shape:
  - product heading
  - `Request:`
  - `Hasil:`
  - `Ringkas:`
  - `Next:`
- In default Telegram output, do NOT dump internal fields like run id, generated_at, artifact paths, proof/comparability fields, `outcome_kind`, `blocker_owner`, or `retryability`
- Technical proof should remain available in persisted artifacts / inspect JSON surfaces, not the default chat reply
- Humanize internal runtime semantics into practical operator language
- Shorten long lines with ellipsis rather than dumping giant text blobs
- Converts parse/runtime failures into a compact error message plus one hint

### Hard-won UX rule: inspect/blocker need the same cleanup as run

Do not stop after humanizing only `ccrun`.
Users will still hit `/ccinspect` and `/ccblocker`, and if those modes keep showing raw fields like:
- `run_id`
- `generated_at`
- `outcome_kind`
- `blocker_owner`
- `retryability`
- proof/comparability labels
- artifact paths
- upstream phrasing like `recorded upstream proof boundary`

then the Telegram UX is still effectively broken.

Treat `inspect`, `blocker`, and `run` as one renderer family and polish them together.

## Important implementation detail

For Hermes quick_commands:
- `ccinspect` and `ccblocker` can use `{args}` because they expect zero or one ref.
- In the current Hermes gateway exec path, do NOT wire `ccrun` to `{args_raw}`. `args_raw` is interpolated directly into the shell command and gets split before the wrapper can reconstruct the intended objective.
- Wire `ccrun` to `{args}` instead.
- Make the wrapper robust to Hermes passing one shell-quoted blob by re-parsing/grouping it inside the wrapper so free-form objectives plus trailing flags like `--channel-id 42` survive Telegram slash invocation.
- Verification should specifically guard against the old failure mode: malformed splitting such as `Unexpected extra argument: execution-ready`.

## Docs updates

Update `README.md` in `centracast-runtime` to list the Telegram wrapper entrypoints and document the actual quick_commands wiring:
- `ccinspect` -> `{args}`
- `ccblocker` -> `{args}`
- `ccrun` -> `{args}`
- `ccideas` -> `{args}`
- `ccbriefs` -> `{args}`
- `ccqa` -> `{args}`
- `ccschedule` -> `{args}`

Call out explicitly that `ccrun` intentionally does not use `{args_raw}` in the current Hermes exec path, and that the four inspect-derived commands also use `{args}` because they accept latest-or-one-ref semantics.

## Tests to add

Extend `scripts/run-tests.ts` with at least:
1. Renderer test for inspect payload:
   - spawn `node scripts/telegram/render-runtime-summary.mjs inspect`
   - feed `inspectManifest(...)` JSON via stdin
   - assert compact Telegram-safe sections (`CentraCast`, `Request:`, `Hasil:`, `Ringkas:`, `Next:`)
   - assert it does not dump raw JSON
2. Renderer test for blocker payload:
   - same idea with `inspectBlocker(...)`
3. Wrapper test for inspect/blocker happy path:
   - spawn `bash scripts/telegram/ccinspect.sh run-phase3-strategy-1`
   - spawn `bash scripts/telegram/ccblocker.sh run-phase7-schedule-blocked-1`
   - assert readable text output
4. Wrapper validation test:
   - malformed `ccinspect` args exits 2
   - missing `ccrun` objective exits 2
5. New wrapper coverage for `/ccideas`, `/ccbriefs`, `/ccqa`, `/ccschedule`:
   - spawn each wrapper with a known run fixture
   - assert the relevant section appears (`Item rencana:`, `Brief yang kebaca:`, `QA ...`, `Ready for publish:` or the explicit empty-scheduling fallback)
   - assert raw internals like `Artifacts:` and `run_id:` do not leak
6. Scheduling-specific gotcha:
   - some inspect fixtures legitimately have no hydrated scheduling payload
   - tests must accept the explicit fallback text `Belum ada jadwal publish yang kebaca...` instead of over-assuming `Ready for publish:` always exists

## Verification

Run:
- `bash scripts/telegram/ccinspect.sh`
- `bash scripts/telegram/ccinspect.sh run-phase3-strategy-1`
- `bash scripts/telegram/ccblocker.sh run-phase7-schedule-blocked-1`
- `CENTRACAST_BASE_URL='https://staging.centracast.id/api/v1/openclaw' bash scripts/telegram/ccrun.sh 'prepare execution-ready briefs --channel-id 1'`
- `npm test`

For the live `ccrun` verification, expect Telegram-safe text like:
- `status: completed`
- `outcome_kind: success_with_upstream_boundary` (or another real outcome)
- artifact root / manifest / summary lines

## Additional hard-won findings

### ccrun should recover from noisy or oversized run stdout

Live staging runs can emit stdout that is not safe to pipe directly into the Telegram renderer because:
- debug transport lines may leak into the run path
- the returned run JSON can become large enough that the captured stdout becomes truncated / non-parseable

Preferred wrapper pattern in `ccrun.sh`:
1. run `npm run --silent runtime:consumer -- run ...`
2. if stdout parses as JSON, render it directly
3. otherwise extract `run_id` from stdout with a small regex
4. if a `run_id` can be extracted, immediately call `npm run --silent runtime:consumer -- inspect run <run_id> --json`
5. if stdout is truncated before `run_id` is visible, fall back once to `npm run --silent runtime:consumer -- inspect latest --json`
6. render the inspect payload instead

This fallback is worth keeping even after transport logging is cleaned up, because it makes Telegram output resilient to large live payloads.

### staging-run transport logs must stay off stdout

If `scripts/staging-run.ts` prints PATCH/transport diagnostics, send them to `stderr`, not `stdout`.
A single line like `→ PATCH /operator-runs/...` is enough to break wrapper-side JSON parsing.

### runtime-consumer run mode should emit a stable machine envelope

Do not let `runtime-consumer run` simply inherit the child process stdio when wrapper consumers expect JSON.
Preferred pattern in `runMachineConsumer()`:
1. spawn `scripts/staging-run.ts` with `stdio: 'pipe'`
2. forward child `stderr` back to parent `stderr`
3. parse child `stdout` as JSON on success
4. normalize the success payload into a stable envelope that always includes:
   - `run_id`
   - `id`
   - `status`
   - `objective`
   - `result_snapshot`
   - `step_progress`
   - `consumer_outcome`
   - `authoritative_artifacts`
   - `artifact_root_dir`

This matters because Telegram/CLI wrappers often consume `runtime-consumer run` directly before deciding whether they need an inspect fallback. If stdout is mixed with logs, the wrapper cannot distinguish a real runtime failure from a parser failure.

### renderer fallback for non-JSON stdin should preserve the original upstream message

When `render-runtime-summary.mjs` is used in `error` mode and stdin is not valid JSON, do not show the JSON parser exception like:
- `Unexpected token ... is not valid JSON`

Instead:
1. capture the raw stdin before JSON parsing fails
2. treat that raw input as the authoritative upstream message
3. render `CentraCast Runtime Error` with the original message plus one compact hint explaining that non-JSON output was returned

This preserves proof honesty for operators: they see the actual upstream failure (`content-analytics unavailable`, `GET /channels -> 500`, etc.) rather than an irrelevant parser complaint.

### normalize staging API status objects before building outcome summaries

A reusable live-staging gotcha: `GET /operator-runs/{id}` may return `status` as an object instead of a plain string, for example:

```json
{ "run": "completed", "stage": "complete", "health": "healthy" }
```

Do not pass that object through untouched in `mapRun()`.
Normalize it first, preferring:
- raw string status when available
- otherwise `raw.status.run` when that nested field exists
- otherwise fallback like `queued`

If you skip this normalization, Telegram renderers will show junk like:
- `status: [object Object]`
- wrong derived outcome such as `in_flight` on a completed run

### renderer should prefer canonical inspect payload artifact fields too

When `ccrun` falls back to `inspect run`, the renderer should read artifact paths from the inspect payload's top-level `authoritative_artifacts` as well as older nested locations, so:
- root
- manifest
- summary

still show up consistently.

### human summary enrichment needs manifest_path and artifact path recovery

A real regression showed that the renderer's human-summary enrichment can silently disappear even when the manifest payload is otherwise valid.

What happened:
- `inspectManifest()` only exposes `final_summary_path` at top level by default
- the renderer wanted to read sibling artifacts like `strategy.json`, `plan.json`, and `execution.json`
- fixture manifests in tests may carry stale absolute paths from another machine (for example `/home/...`) even though the checked-in fixture files exist under the current repo
- result: output falls back to a thin generic summary with no `Fokus sementara yang kebaca:` / plan / brief bullets

Hard rule:
1. when building inspect-like test payloads for the Telegram renderer, explicitly include `authoritative_artifacts.manifest_path`
2. in the renderer, do not trust artifact absolute paths blindly
3. try this resolution order for artifact JSON:
   - direct path from manifest `files.*`
   - `path.join(manifest.root_dir, <basename>)`
   - `path.join(path.dirname(manifest_path), <basename>)`
4. only give up after those fallbacks fail

This makes the human summary resilient to replayed fixtures, copied manifests, and stale absolute artifact roots.

### default Telegram `/ccrun` output should be a human summary, not an operator dump

For the normal happy-path `run` render in Telegram:
- lead with a compact human header like `CentraCast`
- show only:
  - `Request: ...`
  - `Hasil: ...`
  - `Ringkas:` bullets explaining the practical meaning
  - `Next:` with the next safe action
- do **not** show raw internal fields by default:
  - `run_id`
  - artifact paths
  - `outcome_kind`
  - `blocker_owner`

This came from real operator feedback: showing internal proof handles in chat makes the user parse runtime guts manually. Keep proof on inspect/artifact surfaces; keep chat output human.

### important refinement: counts alone are not enough — but do not overclaim them as “new ideas”

A real UX miss happened even after the renderer was already humanized:
- output said things like `3 ide/konten` and `3 brief eksekusi`
- but the user still had to ask `mana aja?` because the actual titles stayed buried in `plan.json` and `execution.json`
- worse, some plan items were actually reusing existing catalog/video topics from `analytics.inventory`, so calling them `ide baru` became misleading

Rule for happy-path `run` and `inspect` summaries when artifact enrichment is available:
- after the count line for plan items, print a compact list of titles
- but label them as `item rencana`, not `ide`, unless you have explicit proof they are truly novel
- after the count line for execution briefs, also print a compact `Brief yang udah kebentuk:` line
- pull the first up to 3 titles from:
  - `plan.plan_output.content_items[*].title`
  - `execution.briefs[*].title`
- keep each title shortened/truncated so Telegram stays readable
- joining them with inline numbering like `1) ... | 2) ... | 3) ...` works well for compact chat output
- preserve the no-raw-JSON rule; titles should come from artifact hydration, not by dumping the artifact body

Important anti-misclassification rule:
- hydrate `analytics.json` alongside `strategy.json`, `plan.json`, and `execution.json`
- compare each plan item against `analytics.inventory[*].title` and `analytics.inventory[*].topic`
- normalize before comparison: lowercase, unicode-normalize, strip combining marks, collapse punctuation/non-alnum to spaces, trim
- if plan items overlap with inventory, add an explicit guardrail line like:
  - `2 item rencana nyambung ke katalog/video existing, jadi jangan dibaca sebagai ide baru mentah.`
- change wording from:
  - `Runtime berhasil nyusun X ide/konten ...`
  - `Ide yang kebaca: ...`
- to safer wording:
  - `Runtime berhasil nyusun X item rencana ...`
  - `Item rencana yang kebaca: ...`

Why this matters:
- strategy/planning can intentionally re-surface or extend existing inventory lanes
- Telegram users should not be forced to infer whether a title is a fresh concept or a catalog-linked continuation
- when in doubt, prefer proof-honest wording (`item rencana`) over salesy wording (`ide baru`)

Verification rule:
- renderer tests should assert the output contains `Item rencana yang kebaca:` and `Brief yang udah kebentuk:`
- renderer tests should explicitly assert the happy-path output no longer says `Ide yang kebaca:` once this safer contract is adopted
- live wrapper verification should check both `/ccinspect <run_id>` and `/ccrun ...` so the user can see the actual 3 item names directly in Telegram without opening artifact paths
- for at least one real run with inventory overlap, verify the overlap warning line appears in chat output

### do not leak verbose blocker explanations into successful happy-path replies

A real gotcha: `consumer_outcome.blocker_explanation` may contain internal QA/runtime wording even on successful runs with bounded certainty.

Rule:
- if status is `blocked` or `failed`, it is fine to surface a shortened blocker explanation
- if status is `completed`, `running`, or `queued`, do not append that explanation to the default Telegram summary

Otherwise the supposedly human summary degenerates back into noisy internal diagnostics.

### tests should lock the concise Telegram contract explicitly

Regression tests for `render-runtime-summary.mjs run` and `ccrun.sh` should assert that happy-path output:
- matches the compact human shape (`CentraCast`, `Request:`, `Hasil:`, `Ringkas:`, `Next:`)
- does **not** contain `Artifacts:`
- does **not** contain `run_id:`
- does **not** contain `outcome_kind:`
- still survives inspect-latest fallback when run stdout is truncated

## Pitfalls

- Do not dump raw JSON into Telegram replies.
- Do not modify Hermes gateway code in this MVP slice.
- For the current Hermes quick_commands path, keep `ccrun` wired to `{args}`, not `{args_raw}`.
- Existing manifests may resolve to older date partitions than expected; assert on contract shape, not a hardcoded date.
- If a live `ccrun` render shows `status: [object Object]` or `outcome_kind: in_flight` for a clearly completed run, inspect staging status normalization before blaming the renderer.
- If renderer parsing fails with JSON errors on live staging, check both stdout contamination and payload truncation; the right fix is usually inspect-fallback, not only stricter parsing.
