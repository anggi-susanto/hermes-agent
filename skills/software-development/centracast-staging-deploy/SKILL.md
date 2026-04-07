---
name: centracast-staging-deploy
description: Deploy CentraCast Laravel staging safely when development happens on main but the staging pipeline triggers from the staging branch.
tags: [centracast, staging, deploy, github-actions, penpod, laravel]
---

# CentraCast Staging Deploy

Use when:
- repo target is `centracast`
- user wants `commit deploy staging`
- normal development happened on `main`
- staging deploy must actually land in the real staging pipeline, not a fake/manual handwave

## Why this skill exists

In this repo, Albert prefers working directly on `main`, but the existing staging deploy workflow is triggered by pushes to branch `staging`.
That means a normal `push main` is not enough to deploy staging.

Also, Penpod manual job triggering has an important trap:
- manual `run_deployment_job` enforces semantic-version tags like `v1.2.3`
- the GitHub staging workflow uses tags like `staging-<shortsha>`
- so trying to reproduce the workflow via Penpod manual trigger can fail even when the real branch-based workflow is valid

## Known CentraCast staging identifiers

As of 2026-03-30, the live staging deployment for CentraCast backend is:
- deployment_id: `36`
- job_id: `19`
- deployment name / service name: `stg-centracast-web`
- repo: `https://github.com/gunamaya/centracast`
- branch spec in Penpod: `*/staging`

Verify these again before relying on them forever.

## Procedure

1. Verify repo/branch before touching git.
   - confirm you're inside `centracast`
   - check `git status --short`
   - check `git branch --show-current`
   - check remotes

2. Commit and push the real change to `main` first if the user asked for normal completion there.
   - If `git push origin main` is rejected because `origin/main` moved, do not force-push.
   - Fetch and inspect divergence first:

```bash
git fetch origin
git log --oneline --decorate main..origin/main
git log --oneline --decorate origin/main..main
```

   - If the remote only has newer upstream work and your local branch is a single clean commit on top, prefer rebasing onto `origin/main`:

```bash
git rebase origin/main
git push origin main
```

   - Re-check `git log --oneline --decorate -3` after the rebase so you can report the final pushed SHA honestly.

3. Inspect staging divergence before deploying.
   - try `git push origin HEAD:staging`
   - if rejected non-fast-forward, do not force-push blindly
   - fetch `origin/staging`
   - inspect ahead/behind and diff

4. If staging has diverged, create a temporary branch from latest `origin/staging`.
   Example:

```bash
git checkout -B staging-deploy-tmp origin/staging
git cherry-pick <main_commit_sha>
```

5. Push the temporary branch to remote `staging`.
   Example:

```bash
git push origin staging-deploy-tmp:staging
```

This preserves the branch-based staging workflow without rewriting remote history.

6. Verify that GitHub Actions staging workflow actually ran.
   Example:

```bash
gh run list --workflow staging.yml --branch staging --limit 5
gh run view <run_id> --json status,conclusion,displayTitle,headBranch,headSha,updatedAt,url
gh run watch <run_id> --exit-status
```

If the user explicitly wants to "kick" staging / Penpod but there are no functional code changes left to deploy, a tiny docs-only commit is acceptable as a deliberate trigger commit.
Practical low-risk pattern used live on 2026-04-04:
- add a small README note explaining the suspected staging issue (for example runtime `.env` loading expectations)
- commit it clearly as docs-only
- push that commit to `staging`
- then trigger the Penpod deploy from the fresh staging SHA

Use this only when:
- the user explicitly asked for a new staging commit / redeploy
- working tree is otherwise clean
- you need a fresh branch-triggered pipeline run to validate infra/runtime behavior

Report it honestly as a trigger commit, not as a product fix.

For CentraCast, the relevant workflow is `.github/workflows/staging.yml`.

Live clarification from 2026-03-30:
- the current workflow title is `Staging Deploy Worker to VPS`
- this workflow deploys the staging worker path, not necessarily the Penpod web service directly
- so a successful run is authoritative for the worker rollout path, but you should still report Penpod web status separately instead of pretending they are the same thing

7. After the `staging` push lands, trigger the real Penpod deployment job manually.
   Current preferred flow:
- call `penpod_get_latest_deployment_history` for deployment `36` / job `19`
- inspect the newest semver tag and build number
- mint the next semver tag instead of reusing the old one
  - example progression: `v0.10.3-beta` -> `v0.10.3-beta-rc1` -> `v0.10.3-beta-rc2`
  - if the newest tag is already an `-rcN`, increment `N`
  - if the newest tag has no rc suffix, create `-rc1`
- submit the new tag with `penpod_run_deployment_job_and_wait`
- wait for terminal state and require `build_status=success`

Practical rule:
- do not stop at "staging branch pushed" or "GitHub Actions succeeded"
- for CentraCast staging, completion means the manual Penpod deployment job for the new tag also finished successfully

8. Verify live deployment state separately via Penpod after the manual run finishes.
   Use:
- `penpod_get_deployment_spec` for deployment/job identifiers
- `penpod_get_latest_deployment_history` to confirm the new tag reached `success`
- `penpod_get_service_deployment_status` with deployment name `stg-centracast-web`

Success looks like:
- workflow run `completed/success`
- latest Penpod history item matches the new tag and shows `build_status=success`
- Penpod service status `Healthy`
- desired/updated/available replicas aligned
- service `generation`/`revision` advances after the rollout

Important nuance from live staging runs:
- GitHub `staging.yml` success alone is not enough to call staging deployed
- the user may fire the manual Penpod deploy separately; if so, poll history until that queued/running item reaches a terminal state
- however, Penpod history can lag or stay stuck on `queued` even while the actual rollout is already progressing/completing
- if `penpod_run_deployment_job_and_wait` times out or `penpod_get_latest_deployment_history` keeps showing `queued`, do a controller-side reality check before declaring failure:
  - first query `penpod_get_latest_deployment_history` filtered to the exact new tag you submitted
  - if that exact tag already appears as a new queued history item, treat the enqueue as accepted even if the wait helper timed out
  - do NOT immediately spam a second trigger for the same tag; a follow-up `run_deployment_job` can return `500 failed to trigger job execution` even though the first attempt already created the queue entry
  - verify the GitHub Actions staging run for the pushed staging SHA completed successfully when that signal is available
  - check `penpod_get_service_deployment_status` for `stg-centracast-web`
  - compare before/after rollout fields, especially `generation`, `revision`, and `current`
  - confirm rollout evidence such as newer `generation`/`revision`, increased `current`, a new replica set name, and new pods moving from Pending to Running or already Running
- if service status reaches `Healthy` on a newer revision and rollout counters advanced, treat that as authoritative evidence that the rollout landed even if deployment history is stale or the wait helper timed out
- explicitly report the split-brain state: history endpoint stale/queued, but controller-side rollout evidence healthy and advanced
- inverse rule from 2026-04-04: service status `Healthy` by itself is NOT evidence that the newest fix landed. A failed newest GitHub Actions run or failed newest Penpod tag can leave `stg-centracast-web` green on an older successful revision while live API behavior still reflects the old bug. Before blaming route/controller code, compare these signals together:
  - confirm the fix commit is actually on `origin/staging`
  - inspect `gh run list --workflow staging.yml --branch staging --limit 3` for the latest staging SHA/result
  - inspect `penpod_get_latest_deployment_history` for deployment `36` / job `19` to see whether the newest web tag is `success` or `failure`
  - then use `penpod_get_service_deployment_status` only as controller health, not as proof that the latest image is serving
- practical failure signature: code already contains the mysql fallback fix in `config/database.php` and `config/queue.php`, but authenticated staging reads still fail with `SQLSTATE ... no such table: personal_access_tokens (Connection: sqlite)` because the newest web rollout failed and the healthy service is still serving an older image
- practical example from live staging: `penpod_run_deployment_job_and_wait` itself timed out for tag `v0.10.3-beta-rc12`, history remained `queued`, but `stg-centracast-web` advanced from generation/revision `226` to `228`, `current` increased from `39` to `41`, a new replica set `stg-centracast-web-6946fcd8d8` appeared, and its pods moved from Pending to Running before the service returned to `Healthy`
- second confirming example from live staging: tag `v0.10.3-beta-rc16` stayed `queued` in history with build `72` / queue `1822`, and `penpod_run_deployment_job_and_wait` timed out, but controller-side status moved `Healthy -> Progressing -> Healthy`, generation/revision advanced `236 -> 238`, current advanced `47 -> 49`, a new replica set `stg-centracast-web-69b6fd8c6d` appeared, and its pods went `Pending -> Running`; this should also be treated as successful rollout with stale history
- third confirming example from live staging: tag `v0.10.3-beta-rc18` stayed `queued` in history even after `stg-centracast-web` became `Healthy` on newer generation/revision `249`, and a brand-new route initially returned `404 route not found` immediately after rollout. Retrying the authoritative staging API about 60 seconds later succeeded with the expected `202` JSON. So for newly-added routes/controllers, do one short delayed API retry after service health turns green before calling the deploy broken
- fourth confirming example from live staging: after pushing commit `ba16558` and triggering manual tag `v0.10.4-beta-rc4`, GitHub Actions worker deploy finished `success`, deployment history still showed the exact tag as `queued`, and `stg-centracast-web` reported `Progressing` with message `active service cutover pending`, newer generation/revision `313`, and a brand-new replica set `stg-centracast-web-85f4f75fdd` whose pods were still `Pending`. Treat this as rollout-in-flight evidence, not an immediate failure. Report it honestly as "deploy triggered and progressing" and, if the user wants full closeout, keep polling until service returns to `Healthy` after cutover.
- fifth confirming example from live staging: after pushing commit `97e43dc` and triggering manual tag `v0.10.4-beta-rc6`, `penpod_run_deployment_job_and_wait` timed out and history still showed the exact new tag as `queued`, but GitHub Actions staging run finished `success`, `stg-centracast-web` advanced from generation/revision `321` to `323` and `current` from `79` to `81`, the service returned `Healthy`, and a short delayed API smoke check about 75 seconds later turned `GET /api/v1/openclaw/releases/155/lifecycle` from prior 404 into live `200` with the expected release lifecycle JSON. For newly added backend truth routes, keep one short delayed authenticated retry in the closeout procedure before calling the deploy broken.
- sixth confirming example from live staging: after pushing main commit `8533997` and staging commit `961911a` for the release lifecycle route-naming regression guard, the GitHub Actions staging worker run `23972113491` completed `success`, `penpod_run_deployment_job_and_wait` for tag `v0.10.4-beta-rc7` timed out at the tool layer, deployment history showed the exact tag as fresh `queued` with build `84` / queue `1850`, and service status moved to `Progressing` with `active service cutover pending`, newer generation/revision `325`, current `83`, and a new replica set `stg-centracast-web-578b8d46df` whose pods were still `Pending`. About 75 seconds later the service returned `Healthy` on generation/revision `325` and the authenticated staging API smoke check `GET /api/v1/openclaw/releases/155/lifecycle` returned `200` with `release_lifecycle_v1`. Treat this pattern as successful rollout with stale queued history, not deployment failure.
- seventh confirming example from live staging: after adding the runtime-facing alias route `POST /api/v1/openclaw/releases/{id}/upload-to-youtube`, source code and deploy signals both looked good, but a fresh runtime proof still saw `404 route not found` for the new endpoint. The decisive evidence came from combining three signals: (1) the runtime artifact showed `Upload dispatch failed: POST /releases/<id>/upload-to-youtube → 404 not found`, (2) Loki web logs for `service_name="stg-centracast-web"` showed a matching `POST /index.php 404` at the same timestamp, and (3) `penpod_get_service_deployment_status` still showed many older replica sets/revisions alive at once while the service overall reported `Healthy`. Treat this as a mixed-revision serving problem first, not an immediate runtime-path or controller-code mismatch.
- practical route-rollout diagnosis rule from 2026-04-05: for newly added Laravel routes/controllers, if live proof still gets `404 route not found` right after an apparently successful rollout, verify in this order:
  1. confirm the route exists in repo source on the deployed branch
  2. confirm the runtime/base URL path is the canonical Openclaw path
  3. check the proof artifact exact error message
  4. query Loki for the matching time window; note that nginx/php-fpm access logs may only show `POST /index.php <status>` rather than the original pretty route
  5. inspect `penpod_get_service_deployment_status` for mixed old/new replica sets, `current` much larger than `desired`, or multiple old revisions still Running
  6. if those mixed-rollout signals exist, conclude the staging surface is not yet homogeneous and do not overclaim that the newly added route is live everywhere
- new guardrail: `stg-centracast-web = Healthy` is still not proof that all traffic is serving the newest backend route surface. When route-level proof contradicts repo source and service health, prefer artifact + Loki timestamp correlation + replica-set spread over the coarse health badge.
- callback-401 diagnosis rule from 2026-04-05: do not assume a `401` on `/api/foreman/callback` means Sanctum or `auth:sanctum` is intercepting the route.
  - first inspect `routes/api.php` and confirm whether the callback route sits outside authenticated route groups
  - then inspect the real gathered middleware on the route, not your memory of Laravel defaults:
    - `php artisan tinker --execute="\$route = collect(app('router')->getRoutes())->first(fn(\$r) => \$r->uri() === 'api/foreman/callback'); echo implode(', ', \$route?->gatherMiddleware() ?? []);"`
  - if the route only shows `api`, inspect the actual `api` middleware group too:
    - `php artisan tinker --execute="echo implode(PHP_EOL, app('router')->getMiddlewareGroups()['api'] ?? []);"`
  - in this repo, live verification showed `/api/foreman/callback` gathered only `api`, and the `api` group effectively resolved to `SubstituteBindings`, so a `401` there was not caused by Sanctum
  - after ruling out middleware interception, inspect `App\Support\ForemanCallbackVerifier` and the callback tests to identify the real auth contract
  - for this callback family, the practical culprit is more likely signature mismatch (`FOREMAN_CALLBACK_SIGNING_KEY_ID` / `FOREMAN_CALLBACK_SIGNING_SECRET`, timestamp tolerance, or auth-mode/header mismatch) than Laravel route auth
  - if you make a speculative middleware patch before verifying, revert it immediately and report the correction plainly instead of cargo-cult deploying the wrong fix

9. Clean up temporary branch and return local checkout to `main`.
   Example:

```bash
git checkout main
git branch -D staging-deploy-tmp
```

## Vault/env change guardrail

If the task involves changing Penpod Vault/env for CentraCast staging:
- do NOT update the Vault payload silently, even if the requested change sounds obvious
- first retrieve and show the current relevant env state when possible
- present a compact before/after diff to Albert
- get explicit approval before applying the change
- when writing the new payload, treat the operation as merge-first, not replace-first; preserve existing keys unless the user explicitly wants removals
- if older env versions are not accessible from the available tools, stop and ask the user for the missing baseline instead of guessing or sending a minimal payload that could wipe unrelated keys

Practical reporting format before any Vault write:
- Before: KEY_A=..., KEY_B=...
- After: KEY_A=..., KEY_B=..., NEW_KEY=...
- Change summary: added / changed / removed

## Important pitfalls

### Pitfall 0: Laravel 12 custom command registration can break staging worker image builds

A reusable CentraCast failure happened during GitHub Actions worker image build at Composer post-autoload stage:
- `composer install --no-dev --optimize-autoloader`
- `@php artisan package:discover --ansi`
- error: `Call to undefined method Illuminate\Foundation\Console\Kernel::starting()`
- source: `routes/console.php`

Root cause:
- repo is using Laravel 12 style bootstrap via `bootstrap/app.php`
- registering custom commands with `Artisan::starting(function ($artisan) { ... })` is the wrong pattern here
- during package discovery, the Artisan facade resolves to a console kernel that does not expose `starting()`

Correct fix for this repo shape:
- remove the manual `Artisan::starting(...)` block from `routes/console.php`
- do not manually `use App\Console\Commands\...` there just to force registration
- register the command directory in `bootstrap/app.php` with:

```php
->withCommands([
    __DIR__.'/../app/Console/Commands',
])
```

Decision rule when a staging build dies inside `package:discover` after adding a new Artisan command:
1. inspect the failed job log first with `gh run view <run_id> --job <job_id> --log-failed`
2. if the stack points at `routes/console.php` and `Kernel::starting()`, treat command registration as the root cause
3. patch registration to `withCommands([...])`
4. keep `routes/console.php` for command definitions/schedules only

This is more reliable than trying to debug Composer, Docker, or the command class itself when the real failure is boot-time registration.

### Pitfall 1: main push != staging deploy

Even if `main` is the preferred working branch, this repo's staging deployment is tied to `staging`, not `main`.
Do not tell the user staging is deployed just because `main` was pushed.

### Pitfall 2: non-fast-forward staging push

If `git push origin HEAD:staging` fails because staging is behind/ahead:
- do not force-push by default
- prefer cherry-picking the deployable commit onto a temp branch rooted at `origin/staging`

### Pitfall 3: Penpod manual run requires a fresh semver tag

This failed in practice:
- attempted tag: `staging-007b123`
- Penpod response: invalid tag, must follow semantic versioning

Updated rule from live usage:
- after pushing `staging`, fetch latest deployment history first
- derive a brand new semver tag from the latest successful/current tag
- submit that new semver tag through Penpod and wait for terminal success
- if `penpod_run_deployment_job_and_wait` itself times out with a transport/MCP timeout, immediately verify whether the trigger actually landed before retrying:
  - query `penpod_get_latest_deployment_history` filtered to the exact tag
  - if the exact tag appears with a fresh queue/build number, treat the submission as accepted
  - then check `penpod_get_service_deployment_status` for controller-side health instead of spamming another trigger

So:
- do not pass GitHub-style tags like `staging-<sha>` to Penpod manual run
- do not reuse the previous semver tag
- prefer branch push -> GitHub Actions workflow -> Penpod manual job with incremented semver tag -> wait for success

### Pitfall 4: wrong deployment name

Querying Penpod with deployment name `centracast` returned `deployment not found`.
The correct service deployment name was `stg-centracast-web`.

## Verification checklist

Before saying deploy is done, confirm all of these:
- commit exists on `main`
- staging branch contains deploy commit
- GitHub Actions staging workflow completed successfully
- Penpod service deployment status is healthy
- local repo is back on `main`
- temp branch cleaned up

## Post-deploy reality-check for analytics/runtime work

If the user asks whether the runtime is "udah jalan lagi" or whether analytics is really populated on staging, do not stop at web deployment health.

Use this decision tree:

1. Confirm what was actually deployed.
   - `stg-centracast-web` health only proves the web service rolled out.
   - It does NOT prove queued ingestion jobs or scheduler-driven jobs succeeded.

2. Check whether staging workers are Penpod-managed or separately deployed.
   In CentraCast, live findings showed:
   - web is visible through Penpod as `stg-centracast-web`
   - worker/scheduler staging may instead be deployed by GitHub Actions onto a separate VPS/docker-compose flow
   - `.github/workflows/staging.yml` can be authoritative evidence for worker rollout steps like:
     - `docker compose up -d --remove-orphans`
     - `docker exec centracast-worker-scheduler php artisan migrate --force`

3. Do not claim end-to-end analytics success unless you verify one of the authoritative live signals:
   - worker/scheduler logs showing `FetchYouTubeAnalyticsJob` succeeded for the relevant channel/date
   - staging API response from `/api/v1/openclaw/channels/{id}/content-analytics` showing real per-video metrics/source metadata
   - read-only DB proof that `youtube_video_analytics_snapshots` rows exist for the target channel/date window

   Important auth reality from live staging checks:
   - hitting `/api/v1/openclaw/channels/{id}/content-analytics` without a valid Sanctum bearer token currently returns `302` redirect to `/studio-new/login`
   - Browserbase/browser checks will also land on the `Sign In` page unless you already have authenticated session state
   - treat that as an auth/access limitation, not as proof that the endpoint or analytics path is broken
   - if you cannot mint a token or log into staging, report the verification limit explicitly instead of guessing whether data is populated
   - practical shortcut discovered on 2026-03-30: the repo-local `centracast-runtime/.env` may already contain a valid `CENTRACAST_TOKEN` that works against `https://staging.centracast.id/api/v1/openclaw`
   - before declaring staging endpoint verification blocked, try reusing that token with direct `curl` to `/channels` and then `/channels/{id}/content-analytics`
   - if `/channels` returns `200` and the channel list looks correct, treat the token as valid for authoritative staging API verification

4. Treat these as different confidence levels:
   - low confidence: web deployment healthy
   - medium confidence: code path + deploy succeeded + worker rollout path identified
   - high confidence: real API/DB/log proof that per-video analytics rows populated and endpoint reads them

5. When evidence is incomplete, report that honestly.
   Example stance:
   - "code dan web deploy udah kebukti"
   - "tapi belum verified end-to-end sampe per-video analytics populated"
   - specify exactly what access is missing: worker logs, staging token, DB read-only, or endpoint response JSON

6. For backend truth-surface changes, do one real staging API smoke check after service health turns green.
   Preferred path discovered in live Wave C validation:
   - source the existing staging token from `centracast-runtime/.env`
   - reuse `CENTRACAST_BASE_URL`, `CENTRACAST_TOKEN`, and `CENTRACAST_CHANNEL_ID`
   - first verify auth with `GET /channels`
   - then hit `GET /channels/{id}/content-analytics`
   - then hit a concrete release readback like `GET /releases/{id}` for the exact truth surface you changed
   - inspect semantic fields, not just HTTP 200
     - for publish truth: `publish_readback.publish_state`, `truth_source`, `is_published`, `youtube_video_id`
     - for cover art: `cover_art.status`, `cover_art.path`, `cover_art.ready`
   - useful live shortcut from 2026-04-04 backend closeout: `/channels` -> `/channels/{id}/content-analytics` -> `/releases/155` was enough to prove auth, analytics surface, and release truth surface in one pass

   New decision rule from 2026-04-04:
   - service status `Healthy` is still not enough to call the backend usable
   - if canonical authenticated Openclaw reads like `GET /channels`, `GET /releases/{id}`, or `GET /releases/{id}/lifecycle` return broad `500 {"message":"Server Error"}` after rollout, treat that as a fresh staging runtime blocker
   - do not collapse this into the earlier feature/config blocker and do not overclaim that the target proof is now possible just because deploy + cutover succeeded
   - report the split honestly: rollout landed, but staging API health on the target truth surface regressed to 500 and must be debugged before rerunning proof
   - first Loki query to run for this class of failure is auth/database-oriented, not route-oriented: search staging web logs for `SQLSTATE`, `personal_access_tokens`, and `database.sqlite`
   - a highly reusable failure signature is: `SQLSTATE[HY000]: General error: 1 no such table: personal_access_tokens (Connection: sqlite, Database: /app/database/database.sqlite, ...)`
   - when that signature appears, the app is usually booting with the sqlite fallback on staging, so Sanctum bearer-token auth explodes before the Openclaw controller logic runs
   - in CentraCast, fix the config fallback to prefer `mysql` outside tests:
     - `config/database.php` default should be `env('DB_CONNECTION', env('APP_ENV') === 'testing' ? 'sqlite' : 'mysql')`
     - `config/queue.php` batching/failed DB fallback should follow the same rule
   - add or keep a regression test that proves `testing => sqlite` and non-testing environments like `staging => mysql` so this does not silently regress
   - before blaming a bad deploy image, also compare local `main` vs `origin/main`; if the mysql-fallback fix exists only in local commits or uncommitted changes, push/deploy that fix before doing deeper route-level debugging
   - new guardrail from 2026-04-04: once the code fallback fix already exists in `origin/main`, inspect live Penpod Vault env before doing more repo surgery
     - fetch vault list/detail for the target deployment (`get_ex_v1_vault`, then `get_ex_v1_vault_id_deployment_deployment_id`)
     - if `DB_CONNECTION` is explicitly set in Vault, that value overrides the code fallback completely
     - practical live case: staging web was still failing broadly on authenticated reads even though the fallback fix existed, because Vault had `APP_ENV=staging` and `DB_CONNECTION=pgsql`
     - in that state, changing `config/database.php` again is wasted motion; the right next step is to propose a Vault diff first (for example `DB_CONNECTION: pgsql -> mysql`) and wait for explicit user approval before writing Vault
     - treat this as an env/runtime config blocker, not a source-code blocker, unless Vault is already confirmed aligned
     - new stronger diagnosis pattern from 2026-04-04: if Vault/deployment spec shows sane staging values (for example `APP_KEY` present and `DB_CONNECTION=pgsql`) and a local container booted with those same values works, but authenticated staging Openclaw reads still return broad `500`, assume the live Penpod web runtime is not actually consuming the effective Vault env
     - verify this with a 3-way check instead of guessing:
       1. local proof: boot the current image locally with the same critical staging env values and verify Laravel sees `app.key`, correct DB driver/host, and basic routes boot cleanly
       2. live smoke: hit authenticated staging reads like `/channels`, `/releases/{id}`, `/releases/{id}/lifecycle`
       3. Loki proof: query staging web logs for `No application encryption key has been specified`, `personal_access_tokens`, `database.sqlite`, and `Connection refused`
     - highly reusable mismatch signatures:
       - `Illuminate\\Encryption\\MissingAppKeyException` / `No application encryption key has been specified.`
       - `SQLSTATE[HY000] [2002] Connection refused (Connection: mysql, Host: 127.0.0.1, Port: 3306, Database: laravel ...)`
       - `SQLSTATE[HY000]: General error: 1 no such table: personal_access_tokens (Connection: sqlite, Database: /app/database/database.sqlite ...)`
     - if those signatures appear while Vault still advertises proper staging values, conclude the problem is environment injection / rollout-state mismatch in Penpod web, not the Laravel repo
     - also check `penpod_get_service_deployment_status`: a redeploy can raise generation/revision and still leave the service `Degraded` with messages like `ProgressDeadlineExceeded`, while mixed replica sets/pods continue serving traffic from inconsistent env states

   Practical example:

```bash
set -a && source ../centracast-runtime/.env && set +a
python - <<'PY'
import os, json, urllib.request
base = os.environ['CENTRACAST_BASE_URL'].rstrip('/')
token = os.environ['CENTRACAST_TOKEN'].strip('"')
channel_id = os.environ.get('CENTRACAST_CHANNEL_ID', '1')
for path in [f"{base}/channels", f"{base}/channels/{channel_id}/content-analytics"]:
    req = urllib.request.Request(path, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
        print(json.dumps(data)[:2000])
PY
```

   For Wave C / publish truth verification, success means live rows show canonical fields such as:
   - `publish_readback.publish_state`
   - `publish_readback.truth_source`
   - `publish_readback.is_published`
   - `publish_readback.youtube_video_id`

   Do not stop at "route exists" when the change is specifically about truth semantics.

## Reporting template

Keep it short and factual:
- main commit SHA
- staging SHA
- workflow run URL/status
- Penpod deployment/service identifiers
- final health status
- any workaround used (for example cherry-pick to staging because direct push was non-fast-forward)
