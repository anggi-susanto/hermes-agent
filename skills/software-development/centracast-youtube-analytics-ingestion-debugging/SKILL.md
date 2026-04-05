---
name: centracast-youtube-analytics-ingestion-debugging
description: Debug sparse/null CentraCast staging content-analytics by tracing FetchYouTubeAnalyticsJob, worker logs, and YouTube Analytics API metric compatibility.
---

# CentraCast YouTube Analytics Ingestion Debugging

Use this when:
- `/api/v1/openclaw/channels/{id}/content-analytics` returns 200 but key analytics fields stay sparse/null
- staging worker logs mention `FetchYouTubeAnalyticsJob` or `AnalyticsDashboardService`
- per-video analytics snapshots are expected but not being populated

## Goal

Separate three failure classes cleanly:
1. auth/scope/token failure
2. worker/scheduler not running
3. YouTube Analytics query contract is invalid for the requested report

## Workspace preflight

Always verify you are in the Laravel backend repo first, not `centracast-runtime`:

```bash
pwd
git branch --show-current
git remote -v | head
git status --short
```

Expected repo for code inspection:
- `centracast`
- usually branch `main`

## Fast diagnosis flow

### 1. Confirm live symptom

If you have API access, check:
- `GET /channels`
- `GET /channels/{id}/content-analytics`

Interpretation:
- `200` on `content-analytics` with null/sparse metrics means route/web deploy is fine, but ingestion may still be broken
- notes like these are strong ingestion clues:
  - `No youtube_analytics_snapshots rows found for the last 30 days`
  - `Per-video CTR and retention are not yet stored in Openclaw`

### 2. Check worker evidence

Look for logs from the actual worker host/container, especially:
- `App\Jobs\FetchYouTubeAnalyticsJob .............. RUNNING`
- `AnalyticsDashboardService failed`
- `AnalyticsDashboardService video report failed`
- `FetchYouTubeAnalyticsJob per-channel failure`

Important distinction:
- if logs show job started, scheduler/worker path is alive
- then focus on per-channel failures instead of infra deployment

### 3. Map the exact failing code path

Inspect:
- `app/Jobs/FetchYouTubeAnalyticsJob.php`
- `app/Services/AnalyticsDashboardService.php`

Current important flow:
- `FetchYouTubeAnalyticsJob::handle()` first calls `getAnalyticsReport()` for channel totals
- then calls `getVideoAnalyticsReport()` for per-video rows
- if `getVideoAnalyticsReport()` throws, the enclosing per-channel `try/catch` logs `FetchYouTubeAnalyticsJob per-channel failure` and skips persistence for that channel's video rows

## Known March 30 2026 root cause

A proven staging failure pattern is:

Worker log:
- `Unknown identifier (impressions) given in field parameters.metrics.`

Source location:
- `app/Services/AnalyticsDashboardService.php`
- method `getVideoAnalyticsReport()`

Problem query shape:
- `dimensions=video`
- metrics string includes:
  - `views`
  - `estimatedMinutesWatched`
  - `averageViewDuration`
  - `impressions`
  - `impressionsCtr`
  - `averageViewPercentage`
- but the request may also be missing the channel-report contract for top-video style queries:
  - `sort` is required
  - `maxResults` must be set to `<= 200`

The reusable conclusion from this incident:
- `dimensions=video` video-report queries should be treated like YouTube Analytics "Top videos" channel reports
- they should send `sort=-views` and `maxResults=200` on both the primary and fallback query shapes
- `impressions` is not accepted for the current YouTube Analytics video report being requested in some cases
- when that invalid metric is included, Google returns HTTP 400
- an older reduced fallback query without impressions could succeed for a 1-day window yet still return `row_count=0`
- the more robust fix is to chunk wide per-video windows into 7-day slices and use a stricter doc-safe fallback metric set: `views,estimatedMinutesWatched,averageViewDuration`
- live staging proof on 2026-03-30: a 29-day rerun for channel `1` via direct service invocation (`getVideoAnalyticsReport($channel, now()->subDays(29), now()->subDay())`) produced fallback row counts per chunk of `43`, `32`, `31`, `17`, and `0`, then merged into `68` unique video rows overall
- on this doc-safe fallback path, `impressions`, `ctr`, and `retention_rate` are expected to stay `null`; that is by design, not a new bug
- historically `FetchYouTubeAnalyticsJob` hardcoded `Carbon::yesterday()` for both `startDate` and `endDate`, which explains why the real save/upsert path could still persist `youtube_analytics_snapshots` while producing `0` `youtube_video_analytics_snapshots` rows for a specific day like `2026-03-29`
- the reusable fix is to let the same job accept an inclusive date range and optional `channelId`, then expose it through an Artisan wrapper instead of inventing a second persistence path
- the command added from this debugging pattern is:
  - `php artisan centracast:backfill-youtube-analytics [start_date] [end_date] [--channel=<id>] [--queue]`
  - defaults to the last 30 days ending yesterday
  - reuses the exact same `FetchYouTubeAnalyticsJob` save/upsert logic for both `youtube_analytics_snapshots` and `youtube_video_analytics_snapshots`
  - supports safer staging repros with `--channel=1`
  - supports inline execution or dispatch to the existing `api_heavy` queue via `--queue`
- this command is the preferred way to prove endpoint population through the real persistence layer when a single-day scheduled run legitimately returns zero video rows
- if a copied command prints one date range in `dump()` but passes another into `getVideoAnalyticsReport()`, trust the actual method arguments and emitted log `start_date`/`end_date`, not the label

## How to prove it quickly

1. Find `impressions` usage in backend source:
```bash
# use Hermes search_files in practice
```

2. Read `AnalyticsDashboardService::getVideoAnalyticsReport()` and confirm the metrics string includes `impressions`

3. Read `FetchYouTubeAnalyticsJob::handle()` and confirm video-report exceptions are caught at the channel level, causing persistence to be skipped

4. Correlate with live worker log message:
- same error text
- same run time
- same channel ids

At that point, treat the root cause as confirmed. Do not keep blaming Penpod or the runtime.

## Interpretation rules

### If the error is 401 / insufficient permission
Likely cause:
- auth scope / reauth issue

### If the error is token refresh bad request
Likely cause:
- invalid/revoked refresh token or mismatched OAuth client

### If the error is `Unknown identifier (impressions)`
Likely cause:
- invalid YouTube Analytics metric contract for the requested video report

### If the error is 403 `SERVICE_DISABLED` / `accessNotConfigured`
Likely cause:
- the analytics path fell back to the global `services.youtube.*` OAuth client instead of the channel's cluster BYOK credentials
- or the channel/cluster mapping is not what you think in live staging

Reusable finding from 2026-03-31:
- `AnalyticsDashboardService::buildAuthenticatedClient()` defaults to `config('services.youtube.client_id')` and `config('services.youtube.client_secret')`
- it only switches to cluster BYOK credentials if:
  - `$channel->cluster` resolves successfully, and
  - `$cluster->hasByokYouTubeCredentials()` returns true
- therefore a channel that is "supposed to be on cluster 4" can still hit the old global GCP project if any of these are true:
  - `channel.cluster_id` in live staging is not actually `4`
  - the relation does not resolve in the worker context
  - cluster `4` exists but `youtube_client_id` / `youtube_client_secret` are empty, undecryptable, or otherwise unreadable

Critical observability gap discovered:
- `YouTubeOAuthController` and `YouTubeUploadService` log when BYOK credentials are used
- historically `AnalyticsDashboardService` did not log whether it resolved `cluster` or fell back to global credentials
- if worker logs show a GCP project number you did not expect, do not guess; patch/add logging for:
  - `channel_id`
  - configured `cluster_id`
  - resolved `cluster_id`
  - whether the `cluster` relation was already preloaded
  - `byok_available` true/false
  - `byok_used` true/false
  - credential source `cluster|global`
  - a masked client-id fingerprint

Proven reusable patch from 2026-03-31:
- add a dedicated info log in `AnalyticsDashboardService::buildAuthenticatedClient()`:
  - log name: `AnalyticsDashboardService credential resolution`
  - payload keys:
    - `channel_id`
    - `tenant_id`
    - `configured_cluster_id`
    - `resolved_cluster_id`
    - `cluster_relation_preloaded`
    - `byok_available`
    - `byok_used`
    - `credential_source`
    - `client_id_masked`
- mask the client id rather than logging the raw secret-bearing identifier; a simple reusable pattern is first 4 chars + ellipsis + last 4 chars
- keep this log before token refresh so you can tell which OAuth client/project was selected even when the later Google call fails
- for testability, extract the direct Google query call behind a protected wrapper like `executeAnalyticsQuery(...)` so unit tests can assert credential-resolution logging without performing a real API request
- add unit coverage for both cases:
  - cluster BYOK available -> `credential_source=cluster`
  - cluster BYOK unavailable -> `credential_source=global`

Log-querying rule from this incident:
- backfill execution and analytics failures were visible under Loki `service_name="centracast-vps-worker-api"`
- not under `stg-centracast-web`
- so when debugging queued analytics backfills, query worker-api logs first before concluding the web app is clean

These are different classes. Do not merge them into one vague "analytics is broken" story.

## Recommended fix strategies

### Option A — fast safe unblock
Remove unsupported metrics from the video report query so ingestion starts working again.

Conservative reduced metric set:
- `views`
- `estimatedMinutesWatched`
- `averageViewDuration`

Then map:
- `impressions => null`
- `ctr => null`
- `retention_rate => null`

Use this when the priority is to restore per-video snapshot ingestion immediately.

Important: do not keep `averageViewPercentage` in the fallback unless you have direct current documentation proving it is valid for the exact `dimensions=video` report shape you are issuing. A stale assumption here causes tests and docs to drift away from the intended safe-query contract.

### Option B — graceful fallback
Try the rich metric set first. If Google returns the specific invalid-metric 400 for `impressions` / `impressionsCtr`, retry with the reduced set.

Use this when:
- some channels/accounts/report combinations may support richer metrics
- you want resilient production behavior instead of one brittle query shape

## Live staging observability reality check

When the user asks to "pantau rerun" after an observability patch, do not claim the rerun happened unless you have direct live evidence.

Current proven staging access pattern:
- Penpod MCP can confirm project/service state for CentraCast staging via project `13` (`gunamaya`)
- `get_ex_v1_service_project_project_id` for project `13` returns `stg-centracast-web` and its health/revision
- `get_ex_v1_project_id_deployment` may only show the production deployment record (`prd-gnm-centracast-web`) even when staging service exists
- `get_ex_v1_package_deployment` for project `13` may return empty, so do not assume package log streaming is available
- Grafana MCP may fail with `No response from Grafana server`; treat that as an access limitation, not proof that logs are absent
- In the repo, staging worker topology is still documented in `deployments/worker/docker-compose.staging.yml`:
  - `worker-api-heavy` runs `php artisan queue:work --queue=api_heavy --timeout=2400 --tries=3`
  - `worker-scheduler` runs `php artisan schedule:work`
  - scheduler path includes `Schedule::job(new FetchYouTubeAnalyticsJob)->dailyAt('02:00')`

Practical rule:
- If you can only verify code path + healthy staging web service + scheduled worker path, report exactly that.
- Do NOT overstate with "rerun observed" or invent row counts.
- Say explicitly that worker/Loki evidence is still missing if live worker logs are not reachable.

## Staging endpoint verification pitfalls

When trying to verify `/api/v1/openclaw/channels/{id}/content-analytics` from a shell:
- use `curl -L` and save the raw response first before interpreting it
- if you get an HTML redirect to `/studio-new/login`, that is not a valid analytics payload; it means auth/session routing intercepted the request
- if `curl -L` resolves to `{"message":"Unauthenticated."}`, treat the bearer token/path as invalid for this check, not as evidence about analytics availability
- do not summarize redirected HTML or unauthenticated JSON as if it were the real endpoint response
- practical shortcut discovered on 2026-03-30: the repo-local `centracast-runtime/.env` may already contain a valid `CENTRACAST_TOKEN` usable against staging
- important nuance: that same `.env` may still point `CENTRACAST_BASE_URL` at `http://127.0.0.1:8080/api/v1/openclaw` for local smoke tests, so do not blindly reuse the base URL from the file when your goal is live staging verification
- important tooling nuance discovered on 2026-03-31: file-reading tools may show the token redacted/truncated in `.env` (for example `"5|csRB...c018"`) even when the real secret is present in the shell environment for the repo
- therefore, for authoritative staging checks, prefer executing the request from the repo shell with `$CENTRACAST_TOKEN` already loaded instead of copying the token string from file-tool output
- important environment nuance: `centracast-runtime/.env` may contain a valid `CENTRACAST_TOKEN` while still pointing `CENTRACAST_BASE_URL` at local clone `http://127.0.0.1:8080/api/v1/openclaw`; for staging-only verification, override the base URL explicitly to `https://staging.centracast.id/api/v1/openclaw`
- practical staging-only probe sequence proven on 2026-04-01:
  - `GET /channels`
  - `GET /channels/1/content-analytics`
  - `GET /channels/1/operator-status`
- if those direct authenticated staging calls return `200`, treat that as stronger request-path truth than an empty Loki search for `"/api/v1/openclaw/channels"` or `"content-analytics"`; access logs may simply not be shipped/queryable in Grafana even when the endpoint is healthy
- if a direct pipe from `curl` into Python yields empty stdin plus `curl: (23) Failure writing output to destination`, treat that as a local piping artifact; save the response to a temp file first, then parse the file
- on 2026-03-30 this path succeeded: `GET /channels` returned `200` with channel `1` (`NiskalaVault`), and `GET /channels/1/content-analytics` returned `200` with `source_metadata.counts.channel_snapshot_rows=29`, `video_snapshot_rows=302`, `video_aggregate_rows=68`, and `flags.has_video_analytics=true`
- on 2026-04-01 a fresh staging-only recheck also succeeded: `GET /channels` returned `200`, `GET /channels/1/content-analytics` returned `200` with populated summary/top_videos/inventory/source_metadata, and `GET /channels/1/operator-status` returned `200` with nominal fleet health
- interpretation rule from that live proof: if `video_snapshot_rows > 0` and `has_video_analytics=true` but `summary.average_ctr` is still `null` and per-video `ctr` values are also `null`, then the problem is no longer "endpoint empty" or "video snapshots not persisted"; it is specifically a metric-richness/provider-contract issue in the stored rows or aggregation path
- same live payload also showed `summary.average_retention_rate=null` while per-video `retention_rate` values were effectively `0`; treat that as evidence that ingestion and persistence are alive but CTR/retention richness is still degraded
- contrasting live proof from 2026-03-31 before the BYOK/GCP fix took effect: the same authenticated staging endpoint path could return `200` with `channel_snapshot_rows=0`, `video_snapshot_rows=0`, `video_aggregate_rows=0`, `has_video_analytics=false`, `used_channel_snapshot_fallback_for_totals=true`, and `used_single_release_fallback_for_rankings=true` for channel `1` over source window `2026-03-02..2026-03-31`
- after the user updated the active GCP/BYOK project and a real backfill reran, the authoritative live endpoint for the same channel recovered to non-empty data (`channel_snapshot_rows=13`, `video_snapshot_rows=164`, `video_aggregate_rows=53`, `has_video_analytics=true`, `total_views=1609`), and worker logs no longer showed the prior `SERVICE_DISABLED` / `accessNotConfigured` failures
- in other words: a healthy endpoint plus partial-metrics code patch is still not enough by itself; you need one more controller-side reality check after rerun/backfill to distinguish "still empty because project/API blocked earlier" from "ingestion alive but metric richness degraded"

## Field-level DB truthing for null-heavy CTR/retention

When the live endpoint proves `youtube_video_analytics_snapshots` rows exist but CTR/retention stay sparse, inspect the stored columns directly before blaming the controller.

Recommended sequence:
1. verify controller math in `OperatorVisibilityController`
   - CTR is only computed from rows with both non-null `ctr` and non-null positive `impressions`
   - retention is only weighted from rows with non-null `retention_rate`
2. verify the mapper contract in `AnalyticsDashboardService`
   - `mapVideoAnalyticsRows(..., false)` explicitly sets:
     - `impressions => null`
     - `ctr => null`
     - `retention_rate => null`
3. verify persistence in `FetchYouTubeAnalyticsJob`
   - the job writes those fallback values directly into `youtube_video_analytics_snapshots`
4. inspect the DB for the full date window, not just a few sample rows

If `psql` is unavailable and native MCP postgres auth is broken, a reusable workaround is:
- read DB credentials from the Laravel repo `.env`
- create a temporary Python venv
- install `pg8000`
- run read-only SQL through that temporary client

Proven staging pattern from 2026-03-30 for channel `1`, source window `2026-03-01..2026-03-30`:
- endpoint proved `video_snapshot_rows = 302`, `video_aggregate_rows = 68`, `has_video_analytics = true`
- direct DB inspection proved:
  - `rows_with_impressions = 0`
  - `rows_with_ctr = 0`
  - `rows_with_retention = 0`
  - `rows_with_positive_retention = 0`
  - every sampled high-view row still had `impressions=null`, `ctr=null`, `retention_rate=null`
- conclusion: the null-heavy CTR/retention came from the persisted fallback rows themselves, not from the controller inventing nulls later

Proven staging access failure pattern from 2026-03-31:
- repo-local staging `.env` in `centracast` pointed to:
  - `DB_HOST=10.0.0.15`
  - `DB_PORT=5432`
  - `DB_DATABASE=centracast_stg_db`
  - `DB_USERNAME=centracast`
- but both native MCP postgres (`postgres-centracast-staging`) and direct ad-hoc Python connection using `pg8000` failed with the same auth error:
  - `password authentication failed for user "centracast"`
- practical rule:
  - do not assume the repo `.env` staging DB credentials are currently valid just because they exist
  - before planning DB truthing as the next step, test the connection quickly
  - if both MCP and direct connection fail with the same auth error, report DB verification as blocked by credential drift instead of pretending the DB was checked
  - in that state, pivot to app/runtime verification (authenticated staging API, worker logs, added observability) or request fresh read-only DB credentials

Recommended SQL checks:
- total row counts plus non-null counts for `impressions`, `ctr`, `retention_rate`
- grouped daily counts to detect date gaps near the end of the window
- a `sample_nonnull` query to prove whether any row in the window actually contains rich metrics
- an aggregate-by-`youtube_video_id` query to confirm whether any weighted CTR/retention can be computed at all

Interpretation rule:
- if all persisted `impressions` / `ctr` / `retention_rate` values are null across the window, the root cause is upstream fallback ingestion or provider contract limitations
- if retention becomes non-null but `impressions` / `ctr` stay null, narrow the diagnosis further: the split fallback path is succeeding for `averageViewPercentage` but failing for `impressions` / `impressionsCtr`
- do not start by blaming the controller summary math

## Proven CTR-null pattern after project fix

A reusable March 31 2026 pattern:
- after the user fixed the BYOK/GCP project and reran backfill, worker execution recovered and endpoint data repopulated
- live endpoint showed non-zero analytics again (`has_video_analytics=true`, non-zero `video_snapshot_rows`, non-zero `video_aggregate_rows`)
- the prior `SERVICE_DISABLED` / `accessNotConfigured` errors disappeared
- but `summary.average_ctr` still stayed `null`

The decisive worker-log signature was:
- `AnalyticsDashboardService video report impressions enrichment unavailable`
- metrics: `views,impressions,impressionsCtr`
- Google error: `Unknown identifier (impressions) given in field parameters.metrics.`

At the same time, observability logs showed:
- `AnalyticsDashboardService video report rows observed`
- stage `split-retention` with non-zero `row_count` on some dates
- stage `split-fallback` often with `includes_impressions=false`

Interpretation:
- this is not a generic ingestion failure anymore
- it means the worker is successfully persisting partial video analytics (views/watch/retention), but Google still rejects the impressions metric family for this channel/report shape
- therefore `OperatorVisibilityController` correctly returns `average_ctr = null`, because it intentionally requires non-null CTR plus positive impressions weight before computing the summary

## Null-vs-zero presentation pitfall

This behavior changed after the `OperatorVisibilityController` null-preservation patch deployed on 2026-03-30.

Current correct behavior:
- summary `average_retention_rate` stays `null` when there is no retention weight
- per-video aggregate `retention_rate` also stays `null` when every source row has `retention_rate = null`
- the controller now computes a dedicated per-video retention weight from rows that have both non-null `retention_rate` and positive `views`, instead of dividing a zero numerator by total views
- if video snapshots exist but CTR still cannot be computed, do not leave operators with a silent `average_ctr = null`; expose an explicit availability contract in the response

Reusable controller-side product patch from 2026-03-31:
- in `OperatorVisibilityController::contentAnalytics()`, compute dedicated availability metadata after summary weighting:
  - `source_metadata.metric_availability.average_ctr`
  - `source_metadata.metric_availability.average_retention_rate`
- recommended fields per metric:
  - `available` (boolean)
  - `reason` (machine-readable string)
  - `source` (`youtube_video_analytics_snapshots` or `unavailable`)
  - `upstream_hint` (nullable string; especially useful for CTR)
- proven CTR mapping when video rows exist but all persisted `impressions`/`ctr` values are null:
  - `available=false`
  - `reason=video_analytics_rows_missing_ctr_or_impressions`
  - `source=youtube_video_analytics_snapshots`
  - `upstream_hint=youtube_impressions_metrics_unavailable_or_unsupported`
- proven retention mapping when video rows exist but `retention_rate` is missing:
  - `available=false`
  - `reason=video_analytics_rows_missing_retention_rate`
- when the weighted metric is actually computable, use:
  - `available=true`
  - `reason=video_analytics_rows_present`
- add matching human-readable notes so operators/UI consumers do not have to reverse-engineer null semantics:
  - CTR note should explain persisted video rows lack usable impressions/CTR and mention upstream YouTube impressions metrics may be unavailable for the channel/report shape
  - retention note should explain persisted rows do not include `retention_rate` values yet
- regression tests worth adding in `tests/Feature/OpenclawContentAnalyticsTest.php`:
  1. video snapshots exist but all `impressions`/`ctr`/`retention_rate` are null -> both availability entries are false and notes explain why
  2. video snapshots have non-null `retention_rate` but null `impressions`/`ctr` -> retention availability true, CTR availability false with the upstream hint
- this is the preferred product behavior when upstream metric richness is partial: preserve honest null summaries, but pair them with explicit provenance and availability reasons instead of a mysterious null

Live staging verification after deploy proved:
- `/api/v1/openclaw/channels/1/content-analytics` returned `200`
- `source_metadata.counts.video_snapshot_rows = 302`
- `source_metadata.counts.video_aggregate_rows = 68`
- `source_metadata.flags.has_video_analytics = true`
- `summary.average_retention_rate = null`
- sampled `top_videos[].retention_rate = null`
- sampled `underperforming_videos[].retention_rate = null`

Later live verification after the BYOK/GCP fix changed the picture slightly:
- the endpoint recovered to non-empty analytics again
- retention could become populated (`summary.average_retention_rate` non-null) while `summary.average_ctr` still remained `null`
- this split outcome is a strong clue that the backend/controller is behaving honestly: retention metrics are available from Google for this channel/report shape, but impressions/CTR metrics are still unsupported or absent upstream

Interpretation rule now:
- if per-video `retention_rate` is `null`, that is the honest signal that persisted source rows lacked retention richness
- do not describe this as zero retention
- if per-video `retention_rate` becomes non-null while CTR stays null, do not chase the controller first; verify whether impressions/impressionsCtr were ever returned by the worker path
- if you ever see per-video `retention_rate = 0` again in this path, treat it as a regression in aggregation semantics rather than expected provider behavior

This means the remaining problem is no longer a controller presentation bug; it is upstream provider/query richness. CTR only comes back when the worker receives real `impressions` and `impressionsCtr` values and persists them into `youtube_video_analytics_snapshots`.

## Local verification environment pitfalls

Two host-side failures are now known and reusable:
- running `php artisan centracast:backfill-youtube-analytics ...` on the bare host can fail with `could not find driver` for `pgsql`
- running `php artisan test ...` on the bare host can fail because PHP extensions like `dom`, `xml`, and `xmlwriter` are missing

Interpretation:
- those failures mean the host shell is not a trustworthy Laravel execution environment
- prefer the app/container environment for backfills and test verification
- if host PHP is missing extensions/drivers, report that as environment drift and avoid treating host failures as application regressions

## Test guidance

Do not rely only on feature tests that seed DB rows directly into `youtube_video_analytics_snapshots`. Those prove the endpoint serializer, not the upstream Google ingestion contract.

Add regression coverage around the service/job boundary:
- rich video metric query rejected by Google
- fallback query succeeds
- job still persists per-video rows with partial metrics
- `impressions` / `ctr` become null instead of aborting the whole channel

Useful target files to inspect/update:
- `tests/Unit/FetchYouTubeAnalyticsJobUpsertTest.php`
- any AnalyticsDashboardService unit coverage if present
- feature tests may stay, but they are not enough on their own

## Reporting template

When reporting this failure, separate the conclusions explicitly:
- worker/scheduler execution: confirmed running
- web route / content-analytics endpoint: confirmed reachable if 200
- ingestion blocker: invalid YouTube Analytics metric contract in `getVideoAnalyticsReport()`
- downstream impact: `youtube_video_analytics_snapshots` not populated, so live endpoint stays sparse/null

## Pitfalls

- assuming sparse analytics means the worker never ran
- continuing to debug `centracast-runtime` after worker logs already identify a Laravel-side query failure
- claiming CTR/retention storage is generally broken without checking whether the query itself is invalid first
- trusting seeded feature tests as proof that Google ingestion works
- fixing only the endpoint presentation while the ingestion job still throws upstream
