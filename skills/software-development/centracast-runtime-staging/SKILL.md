---
name: centracast-runtime-staging
description: Run and debug centracast-runtime LeadOrchestrator against the staging API. Covers StagingProviderClient setup, API shape mismatches, valid status values, and URL parsing pitfalls.
tags: [centracast, staging, typescript, orchestration]
---

# CentraCast Runtime — Staging Integration

Use when running `centracast-runtime` against `staging.centracast.id` or debugging LeadOrchestrator end-to-end.

## Setup

Preferred setup is now a local runtime env file:

```bash
cp .env.example .env
# fill in the real token value (not a redacted display string)
```

Supported variables:
- `CENTRACAST_TOKEN`
- `CENTRACAST_BASE_URL` (default: `https://staging.centracast.id/api/v1/openclaw`)
- `CENTRACAST_CHANNEL_ID` (default: `1`)

The repo's `.env.example` now also serves as the onboarding template for local staging runs. Keep it concise and practical:
- include the 3 core `CENTRACAST_*` keys with comments
- add optional commented placeholders only for integrations that are plausibly needed during local runtime debugging (provider keys, GitHub, Telegram, light debug knobs)
- avoid stuffing it with speculative `TIM_*` or internal-only vars that are not actually read by the helpers, because that makes onboarding noisier instead of clearer

The following helpers now auto-load env from either the current working directory `.env` or `centracast-runtime/.env`:
- `scripts/staging-run.ts`
- `scripts/spawn-runtime.sh`
- `scripts/live-staging-harness.sh`
- `bin/spawn-runtime.cjs`

Use `cp .env.example .env` as the starting point for local setup.
You can still source `~/.hermes/.env` manually if needed, but it is no longer required when local `.env` is present.

Examples:

```bash
node --experimental-strip-types scripts/staging-run.ts [objective] [--channel-id N] [--base-url URL]
./scripts/spawn-runtime.sh "objective" --channel-id 1 --status queued --json
./scripts/live-staging-harness.sh [--channel-id N] [--base-url URL]
./bin/spawn-runtime.cjs "objective" --channel-id 1 --json --pretty --retries 3
```

## Helper CLI Behavior

The staging helpers were normalized to behave consistently across shell, Node, and TypeScript entrypoints:

- `scripts/staging-run.ts` supports `--base-url`
- `scripts/spawn-runtime.sh` should stay a thin wrapper around `bin/spawn-runtime.cjs`
- `scripts/live-staging-harness.sh` should stay a thin wrapper around `node --experimental-strip-types scripts/staging-run.ts`, not a separate curl-based implementation
- use the harness to exercise two orchestrator entry modes:
  - create mode with an objective and `--channel-id` / `--base-url`
  - resume mode with `--run-id`, objective, `--channel-id`, and `--base-url`
- `scripts/staging-run.ts` should not own ad-hoc CLI plumbing anymore; keep shared staging CLI logic in `scripts/staging-cli.ts`
- shared staging behavior is now intentionally split by responsibility:
  - `scripts/staging-shared.cjs` = cross-runtime source of truth for local `.env` loading, default staging values, token normalization, and primitive validation helpers that must be reused by both CJS and TS entrypoints
  - `scripts/staging-cli.ts` = TypeScript-facing wrapper plus create/resume arg parsing for `scripts/staging-run.ts`
  - `bin/spawn-runtime.cjs` = spawn-runtime-specific parser, request payload construction, retry handling, and response handling; it should reuse `scripts/staging-shared.cjs` for defaults/env/token/validation instead of duplicating those primitives
  - `scripts/staging-cli.sh` = shell-side helpers only for wrappers that truly need shell defaults/validation
- shell wrappers that need staging defaults or primitive validation should reuse `scripts/staging-cli.sh` instead of hardcoding their own copies
- if a legacy CJS entrypoint still exists, do not duplicate env loading or default constants inside it; pull them from `scripts/staging-shared.cjs`
- keep direct regression coverage for shared staging helper behavior inside `scripts/run-tests.ts`; at minimum cover:
  - default constant values
  - create/resume arg parsing
  - local `.env` load precedence (`$PWD/.env` before repo `.env`)
  - repo-root `.env` safety rules: allow safe shared-secret hydration (currently `CENTRACAST_TOKEN`) but do not let repo `.env` silently retarget `CENTRACAST_BASE_URL` or `CENTRACAST_CHANNEL_ID`
  - an explicit regression proving cwd-local `.env` is still allowed to override `CENTRACAST_BASE_URL` / `CENTRACAST_CHANNEL_ID` intentionally for local-clone verification
  - token quote trimming
  - alignment between `scripts/staging-shared.cjs` constants and `scripts/staging-cli.ts` exports
  - shared create payload construction staying aligned across CJS and TS helpers
  - `bin/spawn-runtime.cjs --help` working without requiring `CENTRACAST_TOKEN`
  - shell helper defaults staying aligned with `scripts/staging-shared.cjs` exports
  - live harness resume behavior using an extracted real `run_id`, not a fake placeholder
- `bin/spawn-runtime.cjs` should parse args before calling `getRequiredToken()` so `--help` remains usable even when auth is unset
- `scripts/staging-shared.cjs` should remain the source of truth not just for defaults/env/token/primitive validation, but also for create-run payload construction (for example a shared `buildCreateRunPayload()` helper)
- reuse the shared create payload builder from both `bin/spawn-runtime.cjs` and `scripts/staging-run.ts` so the documented create contract cannot drift between legacy CJS and orchestrator codepaths
- `scripts/staging-run.ts` should import and use `DEFAULT_BASE_URL` from `scripts/staging-cli.ts` / `scripts/staging-shared.cjs` instead of hardcoding the staging URL inside `StagingProviderClient`
- `scripts/staging-cli.sh` should not hardcode staging default literals separately; source `DEFAULT_BASE_URL` and `DEFAULT_CHANNEL_ID` from `scripts/staging-shared.cjs` (for example via tiny `node -e` reads) so shell wrappers stay in lockstep with CJS/TS helpers
- `scripts/live-staging-harness.sh` must not use a fake hardcoded resume id like `harness-smoke-run-id`; it should run the live create path first, capture the output, extract the returned `run_id`, then execute the resume path against that same real run
- experiential pitfall: avoid clever shell/Node regex extractors for parsing the captured harness stdout when the value is piped through bash functions; this proved flaky in live use and caused false `Failed to extract run_id from staging-run output` failures even though the output clearly contained the field
- preferred fix: use tiny Python extractors for `run_id` and manifest lines inside `scripts/live-staging-harness.sh` (read stdin, `re.search(...)`, fail loudly on no match). It is uglier, but way less cursed than nested shell quoting
- keep a direct source-level regression in `scripts/run-tests.ts` that asserts the harness still uses dedicated extract helpers (for example `extract_run_id()` / `extract_manifest()`), still resumes with `--run-id "$RUN_ID"`, and still runs `npm run artifacts:compare -- "$CREATE_MANIFEST" "$RESUME_MANIFEST"`
- once the harness already persists a manifest-compare receipt (for example `compare-create-vs-resume.txt`), the next useful live-proof hardening step is to persist a second backend-hydrated receipt from the final GET row, not just the locally regenerated manifest. Current preferred pattern:
  - `scripts/staging-run.ts` writes `hydrated-parity-receipt.json` beside the manifest after the final `getOperatorRun(output.run_id)`
  - the receipt should be derived only from the hydrated backend row shape, not from any extra local reconstruction logic
  - good fields to include: `run_id`, `channel_id`, `status`, `objective`, `parent_objective_id`, `started_at`, `completed_at`, `retry_count`, `truth_verdict`, `handoff_note_present`, `error_summary_present`, `step_progress_signature`, `result_snapshot_present`, `artifacts_present`, `artifact_root_dir`, per-file booleans under `artifact_files_present`, `comparability`, `telemetry_summary`, `qa_status`, `qa_counts`, and a slim `phase_outcomes` skeleton
  - `scripts/live-staging-harness.sh` should require both create/resume hydrated receipts to exist and run a cheap `diff -u` between them in addition to the manifest compare
  - this does not replace `manifest.json`; it complements it by making backend persistence/serialization drift auditable when local code can still regenerate a rich manifest around a thinner row
- keep source-level regressions for this too: assert the staging runner writes `hydrated-parity-receipt.json` from the final GET path and the harness checks/diffs the create/resume receipts
- cleanup pitfall after `git pull` on current `main`: do not blindly `rm -rf docs/runs/<date>` when trying to remove live-run residue. In this repo, some `docs/runs/2026-03-31/*` artifact trees are intentionally tracked in git, while a fresh live harness run may create a neighboring untracked directory (for example `run-1/` or a UUID run dir).
  - safe cleanup order:
    1. run `git status --short docs/runs/<date>` first
    2. remove only the specific untracked run directory you created
    3. if you accidentally deleted tracked proof fixtures, recover immediately with `git restore --source=HEAD --worktree -- docs/runs/<date>`
  - reporting rule: if a cleanup command turned tracked fixtures into `D` entries, say so explicitly and restore them before finishing; do not leave the repo looking like the proof corpus was intentionally removed
- once hydrated receipts already carry the three key analytics proof anchors, the next useful hardening step is to persist the sampled `analytics_coverage` summary there too — not just `analytics_anchor_states` / boundary proof. Current preferred fields are `endpoint_available`, `evidence_richness`, `provider_signal_count`, missing/populated/unavailable/explicit-null/explicit-empty buckets, and provenance `notes`.
- when widening hydrated receipts that way, also widen `compareHydratedParityReceipts()` and its regression so `summary_lines` / `delta_fields` include `analytics_coverage_summary`; otherwise create-vs-resume parity can still hide live-vs-override richness drift behind similar anchor states.
- expose the common staging entrypoints in `package.json` scripts so docs and usage stay aligned:
  - `staging:run`
  - `staging:harness`
  - `staging:provider-smoke`
- `bin/tim-runner.cjs` should be kept strict and fail-fast:
  - `--run-type` must include a value
  - run type must be one of `analysis` or `execution`
  - unknown flags must error immediately
  - extra positional arguments must error immediately
- wrapper scripts that invoke TIM should point to `bin/tim-runner.cjs` (not the old `.js` path); `scripts/tim-resume.sh` is one such wrapper
- important April 2026 command-surface audit finding: `bin/tim-runner.cjs` is a legacy one-shot validator/artifact writer, not the canonical modern runtime flow.
  - current real behavior of `bin/tim-runner.cjs`:
    - reads `docs/orchestration/TIM-ssot.md` and `docs/prompts/tim-prompt-pack.md`
    - validates a small required-field set for `analysis` or `execution`
    - writes simple JSON artifacts under `docs/orchestration/runs/<date>/`
    - returns fields like `status`, `missing_data`, `input_summary`, and an empty `output: {}`
  - it does **not** invoke `LeadOrchestrator`, does not talk to provider anchors, does not run QA, and does not write the modern `manifest.json` / `final-summary.md` bundle under `docs/runs/...`
- canonical modern machine-consumer flow is instead:
  - `npm run runtime:consumer -- run ...`
  - `scripts/runtime-consumer.ts`
  - `consumer/runtime-consumer.ts`
  - `scripts/staging-run.ts`
  - `LeadOrchestrator.execute(...)`
- practical decision rule when auditing or extending "TIM commands":
  1. first decide whether the task targets the legacy local one-shot flow or the canonical orchestrator/live-runtime flow
  2. if the user means real runtime execution, artifact proof, inspect/latest, blocker routing, or compare semantics, treat `runtime:consumer` + `staging-run.ts` as authoritative, not `bin/tim-runner.cjs`
  3. if the user only needs local intake validation / placeholder JSON artifacts with no backend/API orchestration, the legacy TIM runner may still be acceptable
  4. do not mix the two surfaces casually; they write to different artifact roots (`docs/orchestration/runs/...` vs `docs/runs/...`) and expose different truth contracts
- reusable audit warning: the repo currently has a split-brain TIM command surface.
  - docs like `docs/orchestration/TIM-command-prompt.md`, `TIM-ssot.md`, and `tim-prompt-pack.md` can make the legacy TIM runner look like the main runtime path
  - in reality, production-grade orchestration, proof artifacts, inspect/blocker/compare flows, and `consumer_outcome` live on the runtime-consumer/staging-run path
  - if you are asked to "make TIM command canonical" or debug an end-to-end TIM command, explicitly call out this split before patching anything
- recommended remediation direction for future work:
  - either promote `runtime:consumer` / `staging-run.ts` as the canonical TIM command surface
  - or rewrite `bin/tim-runner.cjs` into a thin wrapper over the modern consumer flow
  - if a local no-API validator is still needed, rename/reframe it as a dry-run or intake-check surface instead of leaving it as the primary TIM-branded command
- current inspect nuance from the audit:
  - `runtime:consumer inspect latest` only reads modern manifests from `docs/runs/...`
  - it does not inspect legacy artifacts from `docs/orchestration/runs/...`
  - so a run created by `bin/tim-runner.cjs` is effectively invisible to the modern inspect path
- all helpers should fail fast on:
  - missing flag values (for example `--channel-id` with no number)
  - unknown options
  - unexpected extra positional arguments
  - empty base URL values

Practical maintenance rule: if a shell helper starts duplicating env loading, curl JSON construction, or response parsing that already exists in a Node helper, collapse it back into a wrapper. That avoids drift and prevents shell-only bugs around quoting and JSON escaping.

When debugging local staging access, verify both the happy path and the error path with `--help` plus one intentionally broken invocation (for example `--base-url` without a value or `--run-type` without a value). That quickly confirms parser consistency before blaming env/auth.

Recommended live validation order after parser/tests are green:
1. `npm run staging:provider-smoke` to confirm token + base connectivity first
2. `npm run staging:harness` to exercise real create + resume against staging with the returned live `run_id`
3. immediately fetch `GET /operator-runs/{run_id}` for that exact fresh row to separate current behavior from historical sparse rows

For this subrepo, run the Node/TypeScript test suite directly with `npm test`. Do not prepend `source venv/bin/activate` just because the parent Hermes repo uses a Python venv; `centracast-runtime` is a separate TypeScript workspace and typically has no local `venv/`.

Interpret live harness results carefully:
- a run ending in orchestrator status `needs_human_input` with PATCH payloads mapped to API status `blocked` is still a successful integration test if the helper completed both create and resume paths without transport/auth/parser errors
- if the output shows escalation to human because of schedule conflict / blocked window and `truth_summary.verdict` is `fail`, treat that as a business-state block from staging data, not automatically as a helper/runtime wiring bug
- capture the returned `run_id` from the harness output so you can inspect the corresponding operator run or channel state afterward
- a strong current-HEAD proof pattern is:
  - run `npm run staging:harness`
  - copy the emitted `run_id`
  - fetch `GET /operator-runs/{run_id}` with the same staging token
  - confirm the fresh row now contains `result_snapshot`, `step_progress`, `truth_verdict`, `handoff_note`, expected timestamps, and usually `total_attempts: 1`
- if the fresh GET row contains those fields, do not keep blaming current runtime transport for older null/sparse rows; those older rows are more likely historical transport gaps or create-only interrupted runs

## Staging API: Known Shape Mismatches

### `/channels/{id}/schedule-visibility`
API returns a **different shape** than the `ScheduleVisibility` type — must map manually:

| API field | ScheduleVisibility field |
|---|---|
| `health` | → derive `can_proceed_now` (blocked/halt = false) |
| `is_critical_gap` | → `conflicts[]` (non-empty if true) |
| `next_scheduled_at` | → `publish_window_end` |

### `/operator-runs` PATCH — Valid Statuses
Staging API only accepts: `queued`, `running`, `completed`, `blocked`, `failed`

**Does NOT support:** `needs_human_input` (returns 422)

**Fix:** Map `needs_human_input` → `blocked` in `patchOperatorRun`, and only send `status` (+ optionally `started_at`/`completed_at`) — extra fields like `updated_at` may cause validation errors.

### `OperatorStatusSummary.current_status`
`/channels/{id}/operator-status` returns `latest_run.status` — extract and cast manually, don't pass raw response to type.

## PostgreSQL URL Parsing (@ in Password)

If `POSTGRES_CENTRACAST_URL` or `POSTGRES_CENTRACAST_STAGING_URL` has `@` in the password, Node's URL parser breaks. Parse manually:

```typescript
function parsePgUrl(rawUrl: string) {
  const withoutProto = rawUrl.replace(/^postgresql:\/\//, '');
  const user = withoutProto.split(':')[0];
  const lastAt = withoutProto.lastIndexOf('@');
  const hostPortDb = withoutProto.slice(lastAt + 1);
  const password = withoutProto.slice(user.length + 1, lastAt);
  const [hostPort, database] = hostPortDb.split('/');
  const [host, port] = hostPort.split(':');
  return { user, password, host, port: parseInt(port), database };
}
```

Note: DB credentials in env (`POSTGRES_CENTRACAST_*`) may be stale — staging API token (`CENTRACAST_TOKEN`) is the reliable auth path.

## Pitfalls

- **Don't use `connectionString`** with pg client when password contains `@` — always use object params.
- **PATCH payload**: Send only `status` field (+ timestamps if needed). Sending full `OperatorRun` object triggers 422.
- **`needs_human_input` status**: Not recognized by staging API. Map to `blocked` before sending.
- **Token format**: Env value may include surrounding quotes (`"2|abc..."`), strip with `.replace(/^"|"$/g, '')` if needed.
- **`schedule-visibility` endpoint**: Returns `at_risk`/`nominal` health, not `can_proceed_now`. Always map explicitly.

## Live Debug Findings

Recent live staging checks against channel 1 established these reusable diagnostics:

- analytics-rich live parity is now expected to show an additive probe for `/channels/{id}/content-analytics` before the runtime falls back to intake/channel-metadata-derived analytics.
- current live staging behavior has advanced past route absence: `/channels/{id}/content-analytics` now returns `200` with the expected top-level JSON shape (`channel_id`, `summary`, `top_videos`, `underperforming_videos`, `inventory`, `audience_signals`, `source_window`, `notes`).
- treat this carefully: route availability is now verified, but payload richness is still partial on current staging because core fields such as `average_ctr`, `average_retention_rate`, `average_view_duration_seconds`, and real per-video `views` often remain null / absent in the live response.
- March 30, 2026 live-verification trap: when the user says the staging `.env` is ready, do not blindly trust `CENTRACAST_BASE_URL` in `centracast-runtime/.env`. A valid staging token can coexist with a leftover local base URL like `http://127.0.0.1:8080/api/v1/openclaw`.
- Preferred verification pattern for this case:
  - read `centracast-runtime/.env`
  - extract `CENTRACAST_TOKEN` and `CENTRACAST_CHANNEL_ID`
  - probe staging explicitly against `https://staging.centracast.id/api/v1/openclaw`, regardless of the env base URL, when the task is specifically to verify live staging
  - first hit `GET /channels` to prove auth/token validity
  - then hit `GET /channels/{id}/content-analytics`
- even better for runtime-side proof: override the base URL inline when invoking the packaged helpers, so you validate the exact real staging path instead of trusting the checked-in/default env:
  - `CENTRACAST_BASE_URL='https://staging.centracast.id/api/v1/openclaw' npm run staging:provider-smoke`
  - `CENTRACAST_BASE_URL='https://staging.centracast.id/api/v1/openclaw' npm run staging:harness`
- April 2, 2026 reusable `/ccrun` trap: if Telegram wrapper output mentions staging-ish API failures but feels wrong, inspect `centracast-runtime/.env` before blaming auth/runtime.
  - a leftover `CENTRACAST_BASE_URL=http://127.0.0.1:8080/api/v1/openclaw` will make `/ccrun` hit local even when the token is valid for staging
  - one concrete symptom from live debugging: probing that local base URL can return `200` HTML (`<title>CentraCast-Staging</title>`) instead of JSON API payloads, which makes the failure look like "staging-ish" noise while actually proving the helper is pointed at the wrong host
  - fast diagnosis order for this case:
    1. read `centracast-runtime/.env`
    2. confirm `CENTRACAST_BASE_URL`
    3. probe the current base URL directly for `/channels/{id}/content-analytics` and `/channels/{id}/operator-status`
    4. probe `https://staging.centracast.id/api/v1/openclaw` explicitly with the same token
  - interpretation rule: if explicit staging probes return `200` JSON while the current env target returns local HTML or other non-API content, the bug is env mis-targeting, not wrapper parsing, token auth, or staging route health
  - fix: set `CENTRACAST_BASE_URL=https://staging.centracast.id/api/v1/openclaw` in `.env`, then re-run `/ccrun`
- interpretation rule from that live helper run:
  - if `staging:provider-smoke` prints `provider smoke ok`, transport/auth to real staging is good even if `.env` still points localhost
  - if `staging:harness` returns a fresh `run_id` with final `status = completed` and `truth_summary.verdict = pass`, then the runtime-to-staging live path is verified as working
  - keep reporting analytics richness separately after that; a completed harness does not mean staging analytics fields are fully populated
- interpretation rule from that live check:
  - if `/channels` returns `200` and `content-analytics` returns `200`, auth + route parity are good even if the env base URL still points local
  - if the payload notes include strings like `No youtube_analytics_snapshots rows found for the last 30 days` and `Per-video CTR and retention are not yet stored in Openclaw`, conclude that backend data freshness/richness is the current blocker, not auth or deploy health
- reporting rule: separate `endpoint/auth live verification passed` from `real analytics population still sparse/null on staging`; do not collapse those into one vague success/failure label.
- important March 30, 2026 refinement: for issue-10-style audits, do not collapse all missing anchors into one bucket. The live payload can distinguish between:
  - anchors omitted entirely / structurally unavailable
  - anchors present in the contract but returned as literal `null`
  - anchors present in the contract as deliberate empty arrays (for example `underperforming_videos: []`), which is different from both omission and null
- current proven example from channel 1 no-override live sampling:
  - `top_videos`, `underperforming_videos`, and `traffic_sources` were populated
  - `average_ctr`, `average_retention_rate`, and per-video `average_view_duration_seconds` were returned as explicit `null`
  - `existing_playlists` still behaved like absent / unavailable evidence
- current runtime-side observability pattern should therefore keep three explicit audit buckets in the staging summary whenever applicable:
  - `analytics_explicit_nulls`
  - `analytics_explicit_empties`
  - the remaining unavailable/omitted anchors
- stronger March 30, 2026 proof pattern: also print a per-anchor ledger (for all core anchors) so the CLI names the exact state of each anchor line-by-line instead of forcing humans to reconstruct it from multiple buckets. Current preferred labels are:
  - `populated`
  - `explicit null`
  - `explicit empty`
  - `unavailable`
- current live channel-1 example after that refinement:
  - `top_videos`: populated
  - `underperforming_videos`: populated
  - `average_ctr`: explicit null
  - `average_retention_rate`: explicit null
  - `average_view_duration_seconds`: explicit null
  - `traffic_sources`: populated
  - `existing_playlists`: unavailable
- if a later authenticated direct curl proves the backend has progressed (for example provider rows are now populated and fallback flags are false), do not stop at saying "nice, sudah populated". Do the cleanup loop too:
  1. reconcile any stale repo docs that still describe route absence or older fallback behavior (for example `docs/END-TO-END-GAP-MATRIX.md`, `README.md`)
  2. add or update a narrow repo-native regression in `scripts/run-tests.ts` that locks the currently observed sampled live anchor state, so future drift is caught by `npm test`
  3. comment on the GitHub issue with a short ledger separating:
     - what is now live-verified
     - what runtime-side acceptance is effectively satisfied
     - what still remains an upstream/backend richness gap
- important nuance from this audit: do not assert `provider_signal_count` in that live-contract regression unless you intentionally derive it from the current normalization math. It is safer to lock anchor states (`populated` / `explicit null` / `explicit empty` / `unavailable`) and evidence richness than to overfit to a count that may legitimately shift when normalization scoring evolves.
- reusable runtime-side fix pattern:
  - widen raw provider types to allow `null` on summary fields, arrays, nested metrics, and notes/source-window fields
  - make normalization helpers filter nullable array items and preserve `null` as `undefined` only at the normalized layer, not by lying in the raw contract types
  - add a staging coverage summary field like `explicitly_null_anchors` so the CLI output can say `analytics_explicit_nulls: ...`
- why this matters: it separates contract-shape parity from backend richness. If a field is explicitly `null`, the endpoint shape may be deployed correctly even though the backend still lacks data to populate it.
- confirmed source-level root cause in Laravel (`app/Http/Controllers/Api/V1/Openclaw/OperatorVisibilityController.php`):
  - `summary.average_ctr`, `summary.average_retention_rate`, and `summary.subscriber_count` are currently hardcoded to `null`
  - `top_videos[*].views/watch_hours/ctr/retention_rate/average_view_duration_seconds` are currently hardcoded to `null`
  - `underperforming_videos[*]` carries the same hardcoded-null metric fields
  - the endpoint only computes totals from `youtube_analytics_snapshots` (`views`, `watch_time_minutes`) plus inventory/backlog shape from `SingleRelease`
- confirmed schema-level limitation in `youtube_analytics_snapshots`:
  - migration `2026_03_16_175500_create_youtube_analytics_snapshots_table.php` stores only `views`, `watch_time_minutes`, `subscribers_gained`, `subscribers_lost`, and `estimated_revenue_micros`
  - there is no stored CTR / retention / average-view-duration / per-video breakdown to hydrate the richer response fields from
- confirmed ingestion dependency:
  - snapshots are populated by `FetchYouTubeAnalyticsJob` (scheduled daily at `02:00` in `routes/console.php`)
  - the job itself is queued onto `api_heavy` via `onQueue('api_heavy')`, so successful population requires both the scheduler path and an active `api_heavy` worker
  - the job writes channel totals into `youtube_analytics_snapshots` and per-video rows into `youtube_video_analytics_snapshots`
  - it only processes channels with `status = active`, non-null `tenant_id`, and both YouTube OAuth tokens present
  - if live notes say `No youtube_analytics_snapshots rows found`, first suspect missing/stale job execution, missing/stale YouTube auth, or absent worker consumption before blaming the runtime
- reusable staging audit pattern for sparse `content-analytics` data:
  1. verify the Laravel/web endpoint directly (`GET /channels/{id}/content-analytics`) so route/auth parity is separated from ingestion
  2. inspect `routes/console.php` to confirm the scheduler entry exists
  3. inspect `FetchYouTubeAnalyticsJob` to confirm queue name + target tables + channel preconditions
  4. inspect `deployments/worker/docker-compose.staging.yml` to confirm the intended staging worker topology includes:
     - `worker-scheduler` running `php artisan schedule:work`
     - `worker-api-heavy` running `php artisan queue:work --queue=api_heavy`
  5. verify live infra separately from code: a healthy `stg-centracast-web` deployment only proves the web app rolled out; it does not prove the scheduler/worker ingestion path is alive
  6. if Penpod only exposes the web deployment and you cannot identify a corresponding worker deployment/service, report that as an evidence gap instead of pretending ingestion was verified
- useful current staging log labels from `docker-compose.staging.yml` when Grafana/Loki is available:
  - `job=centracast-vps-worker-scheduler,env=staging`
  - `job=centracast-vps-worker-api,env=staging`
  - these are the first places to look for proof that `FetchYouTubeAnalyticsJob` was dispatched and then consumed
- interpretation rule from this audit:
  - `content-analytics` returning `200` plus `stg-centracast-web` being healthy means web/API deploy parity is probably fine
  - missing `youtube_analytics_snapshots` / `youtube_video_analytics_snapshots` evidence after that should be framed as an ingestion-pipeline problem (scheduler/worker/auth/data freshness), not automatically a route/runtime failure
- when verifying this slice, separate the conclusions explicitly:
  - runtime parity passed if the harness visibly uses the live `content-analytics` response and persists analytics-shaped artifacts
  - route/deploy parity passed if direct GET on `/channels/{id}/content-analytics` returns `200` JSON instead of `404`
  - backend analytics richness is still only partial until staging fills the core performance anchors, so downstream strategy should keep assumption-aware wording
- for this parity check, a good current proof bundle is:
  - `npm test`
  - `npm run staging:provider-smoke`
  - `npm run staging:harness`
  - direct GET on `/channels/{id}/content-analytics`
  - immediate GET on the fresh `/operator-runs/{run_id}` row
- current expected proof pattern on healthy HEAD:
  - harness finishes `status = completed`
  - fresh operator-run row shows `started_at`, `completed_at`, `total_attempts > 0`, `truth_verdict`, `step_progress`, and `result_snapshot.analytics`
  - direct content-analytics GET returns `200`, but analytics evidence may still classify as weak because live summary/video fields are sparse

- `npm run staging:provider-smoke` can pass even when all orchestrator runs still end in `blocked`; treat provider smoke as connectivity/auth validation only.
- Different objectives should drive different classifier choices in healthy classification paths:
  - generic smoke objective → often `strategist`
  - verification objective → `qa`
  - scheduling objective → `scheduler`
- If role selection changes across objectives but every run still ends in escalation, the likely fault is downstream gating/truth logic, not the classifier.
- Live staging may report:
  - `/channels/{id}/operator-status` → `latest_run.status = blocked`, `needs_human_input = false`, `fleet_health = nominal`
  - `/channels/{id}/schedule-visibility` → `health = at_risk`, `is_critical_gap = true`, `suggested_action = generate_now`, `next_scheduled_at = null`
  - `/operator-runs/{id}` → `result_snapshot = null`, `started_at = null`, `total_attempts = 0`, no last error
- That combination usually means the run was gated before real execution began. Do not start by blaming provider calls or executor failures.
- There is a semantic mismatch to remember during debugging:
  - orchestrator output may say `needs_human_input`
  - persisted staging API record may only show `blocked`
  - `needs_human_input` can remain `false` in the API payload because unsupported statuses are mapped to `blocked`
- Working hypothesis for future audits: inspect truth-gate handling of `result_snapshot_exists`, `no_active_intervention`, and any rule that treats `critical_gap` / `at_risk` as a hard stop even when the API suggests `generate_now`.
- Confirmed reusable fix pattern for false blocked / human-escalation outcomes:
  - do not treat `result_snapshot` absence as an intrinsic failure while the run is still `running`; it should only become a truth failure when the run claims `completed` without a snapshot
  - do not route missing-snapshot cases to dev-bridge unless the run is already `completed`
  - in orchestrator truth checks, treat `operator_status.current_status === 'needs_human_input'` as active intervention, but do not treat plain staging `blocked` as equivalent human intervention
  - when mapping staging schedule visibility, `is_critical_gap` plus `suggested_action = generate_now` should not become a hard blocker if `can_proceed_now` is still true
  - escalation-to-human should key off inability to proceed now (`can_proceed_now === false`), not merely `conflicts.length > 0`
  - final status mapping should preserve `running` when the run is still in progress, has no result snapshot yet, and there is no actual schedule stop or human intervention; otherwise the orchestrator will incorrectly collapse an in-progress run into `blocked` or `failed`
  - after fixing the human-escalation path, run a real live harness check (`npm run staging:harness`) to confirm there is not a second false blocker hiding in dev-bridge routing
  - specifically audit `dev-bridge/index.ts` for any fallback like `truth.verdict === 'blocked' => route`; that is too broad once `blocked` also means "not yet complete" for `running` runs without snapshots
  - if live output shows `truth_summary.verdict = blocked`, `no_active_intervention = true`, `schedule_conflict_resolved = true`, and the run is still effectively in progress, dev-bridge should not escalate solely on that blocked verdict or it will override `determineFinalStatus()` and force the run to persisted `blocked`
  - preserve the distinction between "blocked because unsafe/unrecoverable" and "blocked because completion cannot yet be claimed"; only the former should automatically route to dev-bridge or final blocked status
- Add regression coverage for these semantics in `scripts/run-tests.ts`:
  - `running` + no snapshot => `blocked` truth verdict, not `fail`
  - `completed` + no snapshot => `fail`
  - critical gap with `can_proceed_now: true` => no human escalation
  - `truth.verdict === 'blocked'` by itself must not trigger dev-bridge escalation for an otherwise healthy in-progress run
  - orchestrator final status should remain `running` when the only missing piece is the not-yet-produced result snapshot
  - include at least one full-flow orchestrator regression that calls `LeadOrchestrator.execute()` with a mock provider, not just helper-level unit checks
  - in that full-flow case, allow `updateRunState()` to be a no-op when the run has already transitioned to `running` in-memory via `transitionRun()`; do not assume there will always be a `patchOperatorRun(...status='running')` call just to preserve the running state

## Phase 3 Artifact Enrichment Findings

When extending `LeadOrchestrator` to persist richer artifacts (analytics / strategy / plan), keep these implementation rules in mind:

- Persist artifact fields separately from status transitions. A reusable pattern is:
  - `persistRunArtifacts(run)` to patch `result_snapshot`, `step_progress`, `error_summary`, `truth_verdict`, and `handoff_note`
  - `updateRunState(run, status)` to patch those same artifact fields plus transition-derived status/timestamps when the status actually changes
- If `updateRunState()` is called with the same status, it should still patch the artifact payload. Otherwise enriched snapshots can be silently lost just because no state transition happened.
- Preserve `handoff_note` on finalization with a nullish fallback:
  - use `escalation?.handoff_summary ?? observedRun.handoff_note`
  - do not overwrite an existing planning note with `undefined`
- Extend the phase snapshot shape explicitly when adding new artifacts. For example, if phase output now includes a planning handoff, add `plan?: Record<string, unknown>` to `PhaseTwoExecutionArtifacts` / `LeadResultSnapshot`-adjacent typing before wiring logic.
- Good phase-3 snapshot composition pattern:
  - analytics: derive from validated intake plus provider anchors (`channel_profile`, `schedule_visibility`, `operator_status`)
  - strategy: include role chain, rationale, missing data, schedule readiness, operator load, and next-best action
  - plan: include execution mode, immediate next role, publish window, requested topics, blockers, carry-forward assumptions, and a human-readable `handoff_note`
- Add a dedicated planning step to `step_progress` once handoff data exists; do not overload `strategy` to imply planning completion.
- Regression-test both major intake paths after enrichment:
  - channel strategy flow should persist `analytics`, `strategy`, and `plan`, plus expected step order `['intake', 'analytics', 'strategy', 'planning']`
  - content execution intake should populate inventory, audience signals, requested topics, and a planning handoff for the next role
- Keep naming coherent once phase-3 artifacts land:
  - update legacy test titles / fixture IDs that still say `phase 2` if they now validate phase-3 artifact behavior
  - prefer neutral runtime copy like `lead orchestration` or `strategy workflow` when the text is not specifically about numbered rollout phases
- Strengthen `scripts/provider-smoke-test.ts` after artifact enrichment:
  - do not stop at call-order assertions
  - capture patched payloads and assert the smoke path persists `result_snapshot`, `step_progress`, and `handoff_note`
  - also assert enriched snapshot sections exist (`analytics`, `strategy`, `plan`) so staging/provider smoke catches regressions in artifact persistence, not just transport wiring
- Keep `scripts/staging-run.ts` aligned with phase-3 artifact persistence, not just orchestrator types:
  - `StagingProviderClient.patchOperatorRun()` must forward artifact fields accepted by staging (`result_snapshot`, `step_progress`, `error_summary`, `truth_verdict`, `handoff_note`) alongside `status` and any timestamps
  - keep the `needs_human_input -> blocked` status mapping, but do not accidentally strip non-status artifact fields while building the PATCH payload
  - `StagingProviderClient.mapRun()` should hydrate those same artifact fields back onto the local `OperatorRun`, otherwise resume/debug flows lose visibility into what staging actually stored
  - if phase-3 tests pass but live staging appears to "lose" analytics/strategy/plan, inspect `scripts/staging-run.ts` before blaming `LeadOrchestrator`; the runner transport layer may be dropping artifacts on PATCH
- if live `GET /operator-runs/{id}` shows `result_snapshot` but omits `step_progress`, `truth_verdict`, or `handoff_note`, check `scripts/staging-run.ts` before assuming a runtime bug:
  - `patchOperatorRun()` explicitly forwards `result_snapshot`, `step_progress`, `error_summary`, `truth_verdict`, and `handoff_note`
  - `mapRun()` explicitly hydrates `result_snapshot`, `step_progress`, `error_summary`, `truth_verdict`, and `handoff_note`
  - `LeadOrchestrator.persistRunArtifacts()` and `updateRunState()` both send those fields on the real live path
  - if those fields are still absent from the live GET response, the likelier culprit is the staging backend persistence layer or response serializer/read model, not the TypeScript runtime transport
  - a strong proof pattern is: compare a logged PATCH payload from `scripts/staging-run.ts` against the subsequent `GET /operator-runs/{id}` response; if the PATCH includes the fields and the GET omits them, escalate to the Laravel/API side rather than continuing to debug the runtime
- an even stronger live proof is: run `npm run staging:harness`, capture the returned real `run_id`, then immediately fetch `GET /operator-runs/{id}` with the same staging token and confirm the row contains `result_snapshot`, `step_progress`, `truth_verdict`, `handoff_note`, timestamps, and `total_attempts > 0`
- if the harness does both create and resume against the same live `run_id`, expect multiple PATCHes to the same row; that is normal and useful. If the final GET still preserves the artifact fields after resume, both `patchOperatorRun()` and `mapRun()` are behaving correctly instead of stripping data on the second pass
- fresh live proof from the current runtime can look like this: a newly created `GET /operator-runs/{id}` row contains `result_snapshot`, `step_progress`, `truth_verdict`, `handoff_note`, and `error_summary`, but still shows `started_at = null`, `completed_at = null`, and `total_attempts = 0`
- interpret that combination carefully: it is strong evidence that the TypeScript runtime transport did persist artifacts, but it does not by itself prove the backend is at fault; first inspect whether the runtime ever persisted a real `queued -> running` transition before the later blocked/artifact PATCH
- confirmed fix pattern for fresh rows that showed artifacts with `started_at = null` and `total_attempts = 0`: in `LeadOrchestrator.execute()`, persist `updateRunState(run, 'running')` immediately after create/resume when the run is still `queued` and has no `started_at`, before `executeRoleStep()` or any artifact persistence
- why this matters: `executeRoleStep()` can transition to `running` only in memory and then return `needs_human_input` / `blocked` with artifacts; if the first persisted PATCH is blocked-like, Laravel may never stamp `started_at` or increment attempts
- add regression assertions for this invariant in both orchestrator tests and provider smoke:
  - first persisted patch on a fresh queued run must be `status = running`
  - that first patch must include `started_at`
  - then later blocked / `needs_human_input` / artifact-rich patches may follow
- after this runtime-first fix lands, a fresh enriched row with null `started_at` / zero attempts is no longer expected behavior on current HEAD and should be treated as a new regression or backend-side issue
- current proven-good live pattern after the fix is:
  - `npm run staging:provider-smoke` passes
  - `npm run staging:harness` emits a fresh live `run_id`
  - the first persisted PATCH for that fresh run is `status = running` and includes `started_at`
  - a later PATCH may legitimately move the run to `blocked` while also carrying `result_snapshot`, `step_progress`, `error_summary`, `truth_verdict`, and `handoff_note`
  - an immediate `GET /operator-runs/{run_id}` should then show `started_at` populated and `total_attempts` incremented (commonly `1`) alongside the persisted artifacts
- interpret a final live `blocked` row carefully after this fix:
  - if `started_at`, `total_attempts`, and artifacts are all present, lifecycle persistence is working
  - remaining `blocked` status is then much more likely a business-state outcome (for example schedule conflicts / QA fail / dev-bridge escalation) rather than a transport or timestamp bug
- confirmed reusable schedule-overflow fix pattern for live harness rows that were blocked only because backlog items fell outside a degenerate current publish window:
  - inspect the persisted `scheduling` artifact, not just the final row status
  - if `publish_window.can_proceed_now === true`, at least one scheduled item is `within_window === true`, and every unresolved conflict is `type === 'outside_publish_window'`, treat the extra items as backlog overflow rather than a hard scheduling failure
  - in `qa/run-qa-checks.ts`, downgrade both `schedule_conflicts_present` and `schedule_not_publish_ready` from `error` to `warning` for that exact overflow-only case
  - add a regression in `scripts/run-tests.ts` that proves `validateScheduleOutput()` returns warnings, not failure, for overflow-only outside-window conflicts with at least one publishable-now item
  - also clean up scheduling step semantics so `step_progress` matches QA: overflow-only outside-window backlog should be recorded as `scheduling.status = completed`, not `blocked`
  - when asserting this path in orchestrator tests, inspect the persisted artifact patch (`client.patches.find((patch) => patch.result_snapshot !== undefined)`) for `result_snapshot` and `step_progress`; do not assume those fields are returned directly on the top-level orchestrator output object
  - make the regression resilient to unrelated warning noise (for example plan-level warnings like `plan_pillar_balance_weak`): assert the presence of `schedule_conflicts_present:warning` and `qa.error_count === 0` rather than requiring an exact full issue list unless the fixture intentionally isolates schedule-only warnings
  - assert the scheduling note semantics by disallowing stale blocked wording like `still need resolution`; acceptable completed notes may either explicitly mention overflow backlog or say the schedule was marked publish-ready, depending on the exact step-note generator state
  - after the patch, re-run `node --experimental-strip-types scripts/run-tests.ts` and then `npm run staging:harness` / `./scripts/live-staging-harness.sh`; expected live pattern is `qa.status = warning`, `truth_summary.verdict = pass`, final run `status = completed`, and the persisted/live stage summary should show `✅ scheduling completed` instead of a blocked scheduling step
- current proven-good live row shape for that path is stronger than just the console summary: an immediate fresh `GET /operator-runs/{run_id}` should show `status = completed`, non-null `started_at` and `completed_at`, `total_attempts = 1` (or otherwise > 0), `result_snapshot` present with keys through `artifacts`, `step_progress` length 8, `truth_verdict = pass`, `handoff_note` populated, and `error_summary = null`
- when `/channels/{id}/content-analytics` is live again on staging, expect `result_snapshot.analytics` in that same fresh row to be richly populated from the backend response (for example `summary`, `top_videos`, `underperforming_videos`, `inventory`, `audience_signals`, `source_window`, and explanatory `notes`), not just the older fallback-only analytics scaffold
- in that post-fix state, reframe the verification conclusion explicitly:
  - deploy / Laravel route drift: resolved if the endpoint returns JSON instead of `404`
  - runtime grounding: passed if the fresh persisted `result_snapshot.analytics` clearly contains backend-fed content-analytics sections
  - transport + lifecycle persistence: passed if the same row still has `started_at`, `completed_at`, `total_attempts > 0`, `step_progress`, `truth_verdict`, and `handoff_note`
- if the live row matches that shape, treat deploy drift and transport-artifact persistence as verified and move attention to higher-order gaps (output quality, local-vs-live parity, richer strategist/curator/executor logic) rather than re-debugging transport
- new March 30, 2026 live-parity finding for issue #10: it is possible for `npm run staging:harness` to complete successfully, print a fresh run id, and persist local artifacts while an immediate direct `GET /operator-runs/{run_id}` still returns `404`, and `GET /operator-runs?per_page=100` also fails to show that fresh id
- interpret that mismatch carefully:
  - do not blame playlist-normalization / analytics-contract code first if direct `GET /channels/{id}/content-analytics` already returns `200` and the harness output clearly shows live PATCH traffic plus completed local artifact persistence
  - separate the conclusions into two tracks:
    1. analytics route parity / runtime contract safety
    2. operator-run visibility / read-model parity
- practical current proof pattern for this mismatch:
  - run `npm run staging:provider-smoke`
  - run `npm run staging:harness` and capture the emitted `run_id`
  - direct GET `/channels/{id}/content-analytics`
  - direct GET `/operator-runs/{run_id}`
  - direct GET `/operator-runs?per_page=100`
- new March 30, 2026 worker-ingestion audit lesson: do not assume the shell session you control is the same machine/context as the self-hosted GitHub Actions runner that performed the staging worker deploy.
  - even if `gh run view <run_id> --log` proves `~/centracast`, `docker compose up`, `centracast-worker-scheduler`, and `centracast-worker-api-heavy-1` all existed during the workflow, your current Hermes shell may still be a different host/workspace entirely
  - before attempting manual trigger commands like `docker exec centracast-worker-scheduler php artisan schedule:run`, verify controller-side access first:
    - check whether `~/centracast` exists in the current shell
    - check whether `docker ps` in the current shell shows the worker containers
    - if not, do not pretend you can manually trigger the staging job from this environment
  - interpretation rule: a successful worker deploy workflow plus a live `GET /channels/{id}/content-analytics` returning sparse/null analytics narrows the issue to runtime ingestion, but it does not by itself grant manual-trigger access from the current session
  - reporting rule: explicitly separate `remote workflow proved deploy happened` from `current shell lacks direct host access to run scheduler/queue commands`
  - when manual triggering is blocked by access mismatch, hand off the exact commands for the real staging host instead of continuing to poke the wrong machine:
    - `cd ~/centracast`
    - `docker exec centracast-worker-scheduler php artisan schedule:run`
    - `docker exec centracast-worker-scheduler php artisan tinker --execute="dispatch(new App\\Jobs\\FetchYouTubeAnalyticsJob);"`
    - `docker logs --tail 200 centracast-worker-scheduler`
    - `docker logs --tail 200 centracast-worker-api-heavy-1`
- if content-analytics passes but operator-run detail/list cannot read back the fresh id, report it as a staging API visibility/read-model mismatch instead of calling the runtime slice unverified
- this distinction matters especially for provider-ingestion slices: the runtime-side contract may still be proven live-safe even when the staging API cannot immediately round-trip the same fresh operator-run row by id
- a newly observed non-blocking artifact quality gap: local `final-summary.md` can still show an empty `objective:` line even when the live operator run row correctly persists the objective in `parent_objective_id`; treat that as a summary templating/content issue to fix separately, not as an E2E runtime or backend failure
- current implementation note: `artifacts/write-run-artifacts.ts` now resolves the summary objective by checking, in order, `input.objective`, `input.parent_objective_id`, `snapshot.intake?.validated_intake?.objective`, `snapshot.strategy?.objective`, then `snapshot.plan?.plan_output?.objective`, and finally falling back to `unknown`
- when comparing a fresh `GET /operator-runs/{id}` row against local run artifacts, use `row.objective || row.parent_objective_id` as the effective live objective; current staging rows may leave top-level `objective` null even though the run is grounded correctly via `parent_objective_id`
- important April 4, 2026 Type-A proof-run lesson: a successful live `staging:run` proof with a fresh `run_id`, live PATCH trace, local artifact bundle, and backend readback (`started_at`, `completed_at`, `total_attempts > 0`, `truth_verdict`, `result_snapshot`, `step_progress`) is strong proof of runtime/operator-run persistence — but it is still only a bounded orchestration proof unless you also prove a concrete backend release object or publish state.
  - do not overclaim this as `video creation` or `final publish` proof by default
  - honest wording is closer to: `chat -> runtime -> staging operator-run persistence -> readback proven`
  - not yet proven unless separately read back by id: a newly created `single_release` / backend release object, upload artifact, or final YouTube publish state caused by that same run
  - if the goal is stricter Type A acceptance, the next proof slice should explicitly create or mutate one concrete release object and read that exact object back by id
- important AF-006.B live-proof lesson (April 4, 2026): after runtime-side upload-dispatch + poll wiring is implemented and tests are green, live staging can still fail before polling begins because the Laravel backend route itself is missing or not deployed.
  - concrete observed pattern from a fresh live run:
    - operator run completes successfully and persists `release_workflow`
    - `release_id` is present (example: `160`)
    - `upload_dispatch_status = rejected`
    - `upload_dispatch_message` contains `POST /releases/{id}/upload-to-youtube -> 404 not found`
    - `publish_state = draft`, `truth_source = not_published`
    - `publish_poll_attempts = null` and `publish_poll_timed_out = null` because the runtime correctly never entered the poll loop after dispatch rejection
  - interpretation rule: this is not evidence that the new runtime polling logic is broken. It is evidence that live backend route/deploy parity is missing for the upload-dispatch endpoint.
  - preferred proof sequence for this slice:
    1. run the live staging objective via `npm run staging:run -- "..." --channel-id 1 --intake-file ... --json`
    2. capture the fresh `run_id`
    3. read back the exact `/operator-runs/{run_id}` row and inspect `result_snapshot.release_workflow`
    4. if dispatch was rejected, read back the exact `/releases/{release_id}` object too
    5. separate conclusions explicitly:
       - runtime artifact persistence: passed if `upload_dispatch_status` / message are persisted honestly
       - backend upload endpoint parity: failed if the dispatch message shows `404 route not found`
       - publish polling proof: not exercised if dispatch never succeeded
  - reporting rule: call this `partial pass / backend blocker`, not end-to-end publish proof.
  - next action rule: switch to the `centracast` Laravel repo and implement/deploy the missing `POST /releases/{id}/upload-to-youtube` endpoint before spending more time re-debugging runtime poll behavior.
- important AF-002 trap (April 4, 2026): a completed staging run can still skip the release lane entirely when execution selects strategy-generated items (`strategy-1`, `strategy-2`, ...) instead of a concrete reviewed audio asset id
  - `deriveReleaseAssetId()` depends on `linked_execution.chosen_item_id` being a real asset id
  - when that id points to strategy items, `buildReleaseWorkflowSnapshot()` returns `undefined`
  - manifest/release artifact then shows release proof missing (`not_recorded` / `missing`) even though the orchestrator run itself is `completed`
  - do not misreport this as AF-002 live pass
- AF-002 live-proof checklist for runtime-owned release lane:
  1. use an explicit existing reviewed `asset_id` (or an execution path guaranteed to resolve to one)
  2. verify runtime-created `release_id` is persisted in `result_snapshot.release_workflow` / `release-workflow.json`
  3. verify SEO + cover dispatch/readback are present without manual curl side-calls
- important April 4, 2026 AF-002 follow-up from the first successful live asset-first run:
  - `deriveReleaseAssetId()` must not rely only on `execution.linked_execution.chosen_item_id`; for explicit asset-first intake runs, fall back to `content_intake.items[0].item_id` or the release lane will be silently skipped when the chosen execution item is a strategy identifier
  - `POST /releases` on staging validates `asset_id` as an integer; if runtime carries it as a string, coerce numeric strings before POST so the backend does not reject with `422 The asset id field must be an integer.`
  - `POST /releases/{id}/generate/cover-image` can still return `400 Image prompt is missing. Generate SEO first.` immediately after a successful SEO dispatch because the SEO/image-prompt read model lags behind the dispatch acceptance
  - preferred runtime-safe sequence is: create release -> await SEO dispatch result -> attempt cover dispatch afterward (not in parallel with SEO)
  - for staging proof runs, treat that specific 400 as a deferred/queued cover-art state caused by read-model lag, not as proof that release creation or SEO dispatch failed
  - a proven live run used asset `10`, created release `159`, and completed operator-run `019d591a-2526-71d5-a1cc-0c5f7f383228` with `seo_status=generating` and `cover_art_status=generating`; backend readback already showed `seo_title` populated on the release even though final cover-art URL/path was not yet readable
- a good report artifact for this run type should separately record:
  - strongest proof: live `/operator-runs/{run_id}` readback with lifecycle + snapshot fields present
  - weakest gap: no release-object-by-id or publish-state proof
  - verdict: usually `PARTIAL PASS` rather than full pass when only operator-run persistence is proven
- do not assume `step_progress` uses the same shape or vocabulary as `final-summary.md` / manifest stage lists:
  - live API `step_progress` entries currently use the key `step`, not `stage`
  - live API may include an `artifacts` step
  - local `final-summary.md` / manifest `completed_stages` may include `scheduling_handoff` and omit `artifacts`
  - treat that as representation drift between runtime execution steps and artifact-stage reporting unless there is actual missing persistence
- practical compare pattern for fresh-row audits:
  - compare status directly (`row.status` vs `final-summary status`)
  - compare effective objective (`row.objective || row.parent_objective_id`) vs `final-summary objective`
  - compare lifecycle fields (`started_at`, `completed_at`, `total_attempts > 0`)
  - compare `result_snapshot.qa.status` vs local `qa.json status`
  - compare `result_snapshot.strategy.objective` vs local `strategy.json objective`
  - inspect `step_progress[*].step` separately from `completed_stages`; do not fail the audit just because one side says `artifacts` and the other says `scheduling_handoff`
  - when doing the live `GET /operator-runs/{id}` check through Hermes `terminal`, prefer a compact `python3 -c '...'` request over a bash heredoc; in this environment heredoc-wrapped Python can get mangled by the terminal wrapper and produce false syntax errors unrelated to the API/debug target
- if this bug reappears, do not assume the implementation is missing first; inspect `write-run-artifacts.ts` and add/repair a direct regression in `scripts/run-tests.ts` that writes real artifacts and asserts `final-summary.md` includes the expected fallback objective text
- good regression shape for this case:
  - create a temp output dir with `fs.mkdtempSync(...)`
  - call `writeRunArtifacts({ objective: '', parent_objective_id: '...', snapshot: {}, ... })`
  - read `manifest.files.final_summary`
  - assert the markdown contains `- objective: ...`
  - clean up the temp dir in `finally`
- docs rule for this slice: if only internal regression coverage changed and helper CLI/public contracts did not, avoid broad doc churn; a small README/runbook note is enough only when the observable artifact behavior (`final-summary.md` objective preservation) is worth anchoring for future audits
- when hardening the regression, prefer expectations derived from the persisted scheduling snapshot (for example via the same overflow assessment helper used by runtime logic) instead of brittle hardcoded warning counts/messages; exact schedule warning text can legitimately vary depending on whether the persisted snapshot still qualifies as overflow-only backlog
- if verification only changes internal runtime semantics/tests and the staging helper commands / flags / payload contract stay the same, do not churn README/docs just to say "verified"; only update docs when the public helper surface or documented operator behavior actually changed
- when reporting results, separate three conclusions explicitly:
  - transport/auth/connectivity: passed
  - artifact persistence: passed if the fresh row contains `result_snapshot` + `step_progress`
  - lifecycle metadata consistency: passed only if the same fresh row also has `started_at` populated and `total_attempts > 0`; otherwise treat it as a current regression worth debugging
- before blaming the current live path, separate historical rows from current behavior with live DB inspection:
  - use the Hermes native MCP postgres tool to query recent `operator_runs` directly, not just API responses
  - check whether rows with missing runtime artifacts also have `total_attempts = 0`, `started_at = null`, `result_snapshot IS NULL`, or unchanged `created_at == updated_at`; those are strong signs of create-only rows that never reached artifact persistence
  - if only newer rows contain `truth_verdict` / `handoff_note` while older rows are null, suspect historical transport drift first, not an active regression
  - in this workspace, a key timeline clue was: `LeadOrchestrator` started generating phase-3 artifacts before `scripts/staging-run.ts` forwarded them on PATCH; that produces a mixed database where legacy rows are sparse/null and fresh rows are enriched
  - use `git log` on `entrypoint/lead-orchestrator.ts`, `scripts/staging-run.ts`, and `scripts/live-staging-harness.sh` to correlate when artifact generation landed versus when staging transport wiring landed
  - do not conclude "Laravel is still broken" from old null rows alone; first create a fresh run on current HEAD and inspect that exact row
  - after confirming the live path, lock it down with source-level regression tripwires in `scripts/run-tests.ts` that assert `scripts/staging-run.ts` still forwards `result_snapshot`, `step_progress`, `error_summary`, `truth_verdict`, and `handoff_note`, still preserves `started_at` / `completed_at`, and still maps `needs_human_input` to `blocked`
  - add a small repo note like `docs/staging-phase3-artifact-regression.md` summarizing the historical-row explanation plus the current verification flow, so future audits do not re-debug the same sparse-row story from scratch

### Important pitfall: do not "normalize away" invalid intake

A bug surfaced when the orchestrator created a `normalizedInput` that dropped `channel_intake` unless it already had `channel_id`. That looked harmless, but it changed validation behavior:

- `deriveIntakeFromInput()` falls back to `buildChannelIntake({ channel_id, objective, channel_context: objective })` when no intake is present
- so removing an incomplete `channel_intake` can accidentally fabricate a more valid fallback intake
- result: tests expecting `needs_human_input` can incorrectly pass as `completed`

Rule: pass the original user intake through validation, even if incomplete. Let `validateIntake()` see the actual missing fields; do not replace it with a synthesized fallback during normal orchestrator execution.

## Laravel Staging 404 Audit Pattern

When a newly expected Laravel endpoint returns `404` on staging, do not assume the backend route is missing from source. Use this audit sequence to separate source-code absence from deploy-layer drift:

1. Verify the Laravel repo/branch first.
   - Confirm you are in `centracast` on the intended branch (usually `main`).
   - Check `git branch --show-current`, `git remote -v`, and `git status --short`.

2. Prove whether the route exists in source.
   - Search `routes/api.php` for the endpoint path.
   - Search the controller for the mapped method.
   - Example proof bundle for `/channels/{id}/content-analytics`:
     - route exists in `routes/api.php`
     - controller method exists in `app/Http/Controllers/Api/V1/Openclaw/OperatorVisibilityController.php`

3. Check when the endpoint landed.
   - Run `git log --oneline -- routes/api.php <controller-file>`.
   - If the route was added in a recent commit and that commit is already on `main` / `origin/main`, the repo is not the problem.

4. Interpret the mismatch correctly.
   - If live staging still returns `404` while the route and controller both exist on current `main`, the strongest default diagnosis is deploy-layer drift, not missing source code.
   - Most likely causes, in order:
     1. staging web/API container is still running an older image/artifact
     2. Laravel route cache on staging is stale (`route:cache` not rebuilt/cleared)
     3. deploy pipeline rolled worker/runtime components but not the web app serving Laravel HTTP
     4. load balancer / multiple instances still send traffic to an old node

5. Recommend server-side verification, not more repo churn.
   - On the staging Laravel host, check:
     - `php artisan route:list | grep content-analytics`
     - `php artisan optimize:clear`
     - `php artisan route:clear`
     - `php artisan config:clear`
   - Then verify the active web container/image revision and restart or redeploy the web service.

6. Important interpretation rule for CentraCast specifically.
   - If runtime harness and persistence flows succeed live, but a newly added Laravel visibility endpoint returns `404`, that often means the runtime/worker deploy succeeded while the staging web/API deploy did not fully roll forward.
   - Do not keep debugging TypeScript runtime transport in that situation; escalate to Laravel/web deploy verification.

7. Post-cleanup retest rule (April 2026 upload lane finding).
   - After stale ReplicaSets/pods are cleaned up and service converges (`current=desired=updated=available=1` with a single active ReplicaSet), rerun the same runtime proof immediately.
   - If `POST /releases/{id}/upload-to-youtube` shifts from `404 route not found` to `400 Release must be in "ready" status to upload`, treat that as **deploy/API surface parity recovered**.
   - Interpretation: route/deploy drift is resolved; the remaining blocker has moved to domain state gating (`release` lifecycle still `planned/draft`, not `ready`).
   - Next action should switch from rollout debugging to readiness-gate debugging (why release is not yet `ready` before upload dispatch).

## Channel Info

- Channel ID 1: **NiskalaVault** (niche: Majapahit Cyberpunk Ambient)
- Base URL: `https://staging.centracast.id/api/v1/openclaw`
