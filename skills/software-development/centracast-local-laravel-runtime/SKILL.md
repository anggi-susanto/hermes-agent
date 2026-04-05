---
name: centracast-local-laravel-runtime
description: Bring up CentraCast Laravel locally with Docker plus run centracast-runtime locally, using vault-derived .env values and without starting centracast-foreman.
tags: [centracast, laravel, docker, runtime, local]
---

# CentraCast Local Laravel + Runtime

Use when the user wants a local CentraCast setup with:
- `centracast` Laravel running locally
- `centracast-runtime` executed locally
- `centracast-foreman` explicitly NOT started

This is especially useful when the user says to pull env values from Vault/Penpod and only validate Laravel + runtime.

## Scope rule

If the user says scope is only runtime + CentraCast Laravel:
- do not start `centracast-foreman`
- do not spend time wiring foreman unless explicitly asked

## Recommended flow

1. Put the relevant `.env` values in:
   - `centracast/.env`
   - `centracast-runtime/.env` if runtime helpers need local env
2. Start Laravel dependencies and app from `centracast`
3. Verify the web app responds locally
4. Run runtime via script/harness from `centracast-runtime`
5. Report clearly that runtime is a script/orchestrator flow, not necessarily an HTTP server

## Laravel local start

From `centracast`:

```bash
sudo -n docker compose --profile production up -d --build pgsql redis app
```

Expected containers:
- `centracast-pgsql`
- `centracast-redis`
- `centracast-app`

Expected ports commonly seen:
- app: `8080`
- postgres: `5432`
- redis: `6379`

## Important pitfall: bind mount can break vendor/autoload

A reusable failure mode occurred:
- container starts
- local app returns `500`
- logs show:

```text
require(/app/public/../vendor/autoload.php): Failed to open stream
Failed opening required '/app/public/../vendor/autoload.php'
```

Likely cause:
- compose bind-mounts the host source tree over `/app`
- image build installed Composer deps into the image
- host repo does not have matching `vendor/`
- bind mount hides the image's built `vendor/`

## Fix for that failure

Keep DB/Redis running, but replace only the app container with a container from the built image using the env file and no source bind mount:

```bash
sudo -n docker rm -f centracast-app && \
sudo -n docker run -d \
  --name centracast-app \
  --network centracast_centracast-net \
  -p 8080:8080 -p 8443:443 \
  --env-file /opt/gunamaya-ai/workspaces/centracast-studio/centracast/.env \
  centracast-app:latest
```

After this, verify:

```bash
curl -sS -o /tmp/cc_root.out -w '%{http_code}\n' http://127.0.0.1:8080/
```

A healthy result is `200` with HTML.

## Auth expectation for API checks

Unauthenticated local API requests are expected to return `401`, for example:

```bash
curl -sS -o /tmp/cc_channels.out -w '%{http_code}\n' \
  http://127.0.0.1:8080/api/v1/openclaw/channels \
  -H 'Accept: application/json'
```

So:
- `200` on `/` proves Laravel app is serving
- `401` on protected API routes is normal unless you provide auth

## Runtime verification

`centracast-runtime` is not necessarily a local HTTP service. Treat it as an orchestration runner unless you confirm otherwise from source.

Useful proof from `package.json`:
- `staging:run`
- `staging:harness`
- `staging:provider-smoke`

### Point runtime to local Laravel

If the goal is to make runtime hit the local Laravel app rather than staging, set `centracast-runtime/.env` like this:

```env
CENTRACAST_TOKEN="<local sanctum token>"
CENTRACAST_BASE_URL=http://127.0.0.1:8080/api/v1/openclaw
CENTRACAST_CHANNEL_ID=1
```

Then verify with:

```bash
cd /opt/gunamaya-ai/workspaces/centracast-studio/centracast-runtime
npm run staging:provider-smoke
npm run staging:harness -- --channel-id 1 --base-url http://127.0.0.1:8080/api/v1/openclaw
```

A good result is:
- `provider smoke ok`
- harness create path succeeds
- harness resume path succeeds
- final run status reaches `completed`

This validates the local runtime→Laravel OpenClaw path more directly than trying to invent a separate local runtime server endpoint.

## Local OpenClaw auth verification with a real agent token

When local OpenClaw routes are protected by `auth:sanctum` plus `agent`, do not rely on anonymous curl checks alone.

### Important pitfall: anonymous local API may redirect to staging login

A reusable local behavior occurred:
- anonymous request to `/api/v1/openclaw/channels` returned `302`
- `Location` pointed to `https://staging.centracast.id/studio-new/login`

Why this can happen:
- the Laravel `.env` may still contain `APP_URL=https://staging.centracast.id`
- browser-style or unauthenticated requests can redirect through auth/login flow instead of returning JSON `401`

So for local API verification:
- do not assume anonymous `302` means the API route is broken
- use a real Bearer token and `Accept: application/json`
- judge success from authenticated API behavior, not the login redirect

### Critical pitfall: remote 'staging-style' DB target can be schema-complete but data-empty

A reusable CentraCast failure mode occurred when local Docker was pointed at a remote Postgres target from `.env`:
- `.env` showed a staging-looking target such as `DB_HOST=10.0.0.15` and `DB_DATABASE=centracast_dev_db`
- Laravel connected successfully
- `migrations` table was populated and `php artisan migrate:status` showed many migrations as `Ran`
- but business tables were empty: `users=0`, `channels=0`, `tenants=0`, `personal_access_tokens=0`
- requests with a supposedly valid Bearer token still returned `401 Unauthenticated`

Why this matters:
- a successful DB connection plus a fully migrated schema does NOT prove you are hitting the correct populated staging dataset
- you may actually be pointed at an empty clone/dev DB or a wiped target with only schema remaining
- if `personal_access_tokens` is empty, tokens copied from `centracast-runtime/.env` cannot authenticate against that DB-backed app

Decision rule before blaming code/auth:
1. verify the app's active DB config from inside the container:

```bash
sudo -n docker exec centracast-app php artisan tinker --execute="echo json_encode(['database'=>DB::connection()->getDatabaseName(),'host'=>DB::connection()->getConfig('host'),'port'=>DB::connection()->getConfig('port')]);"
```

2. verify key row counts from the same live connection:

```bash
sudo -n docker exec centracast-app php artisan tinker --execute="echo json_encode(['users'=>DB::table('users')->count(),'channels'=>DB::table('channels')->count(),'tenants'=>DB::table('tenants')->count(),'personal_access_tokens'=>DB::table('personal_access_tokens')->count()]);"
```

3. if those counts are all zero, treat the result as an environment/data-source problem first, not as proof that the API patch failed
4. explicitly report: `schema exists, but target DB is empty`, and recommend either:
   - point `.env` to the actually populated staging DB
   - restore/clone a populated dump locally
   - seed the minimum local auth/channel data needed for endpoint verification

This check prevents wasting time debugging bearer auth or endpoint code when the real issue is that the selected database has no tenants, users, channels, or tokens.

### Proven flow to generate a local agent token

1. Find a user with role `agent` in the cloned local DB.
2. Confirm that user is assigned to at least one channel through `channel_user`.
3. Generate a Sanctum token for that agent from inside the app container.
4. Use that token to hit `/api/v1/openclaw/channels` locally.

Example queries:

```bash
sudo -n docker exec centracast-pgsql psql -U centracast_admin -d centracast_dev_clone -c "SELECT id, name, email, role, tenant_id, is_approved FROM users WHERE role = 'agent' ORDER BY id;"
sudo -n docker exec centracast-pgsql psql -U centracast_admin -d centracast_dev_clone -c "SELECT channel_id FROM channel_user WHERE user_id = 29 ORDER BY channel_id;"
```

### Proven token-generation method

Avoid fragile `php artisan tinker --execute=...` one-liners for this. A reusable failure mode was PsySH parse errors on inline assignment-heavy expressions.

Instead, write a tiny PHP bootstrap script on the host, copy it into the app container, and execute it there.

Host file contents:

```php
<?php
require '/app/vendor/autoload.php';
$app = require '/app/bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();
$user = App\Models\User::find(29);
if (!$user) {
    fwrite(STDERR, "USER_NOT_FOUND\n");
    exit(1);
}
echo $user->createToken('local-runtime-smoke')->plainTextToken;
```

Run it:

```bash
sudo -n docker cp /opt/gunamaya-ai/workspaces/centracast-studio/centracast/tmp-local-token.php centracast-app:/tmp/local-token.php
sudo -n docker exec centracast-app php /tmp/local-token.php
```

### Verify local OpenClaw with Bearer auth

```bash
TOKEN='<paste-generated-token>'
curl -sS -D /tmp/local_openclaw_headers.txt \
  -o /tmp/local_openclaw_channels.json \
  -H "Accept: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8080/api/v1/openclaw/channels
```

Healthy result:
- HTTP `200`
- JSON body includes the agent's assigned channels
- for the known local clone case, `NiskalaVault` / channel `1` appeared successfully

### Fast path: reuse the local runtime token when it already points at local Laravel

If `centracast-runtime/.env` already contains a valid local token plus:

```env
CENTRACAST_BASE_URL=http://127.0.0.1:8080/api/v1/openclaw
```

then you can reuse that token instead of minting a new one.

Example extraction + channel verification:

```bash
TOKEN=$(python3 - <<'PY'
from pathlib import Path
for line in Path('/opt/gunamaya-ai/workspaces/centracast-studio/centracast-runtime/.env').read_text().splitlines():
    if line.startswith('CENTRACAST_TOKEN='):
        print(line.split('=', 1)[1].strip().strip('"'))
        break
PY
)

curl -sS -D /tmp/cc_openclaw_headers.txt \
  -o /tmp/cc_openclaw_channels.json \
  -H "Accept: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8080/api/v1/openclaw/channels"
```

This is useful as a quick authoritative check before deeper endpoint validation.

### Verifying local `content-analytics` changes authoritatively

When the backend slice touches `GET /channels/{id}/content-analytics`, prefer this sequence:

1. sync the changed PHP files into `centracast-app` if the app container is the no-bind-mount image-run fallback
2. syntax check the changed controller with `php -l`
3. hit the local authenticated endpoint with the Bearer token
4. inspect the raw JSON for the newly added anchors / provenance fields

Example:

```bash
sudo -n docker cp /opt/gunamaya-ai/workspaces/centracast-studio/centracast/app/Http/Controllers/Api/V1/Openclaw/OperatorVisibilityController.php centracast-app:/app/app/Http/Controllers/Api/V1/Openclaw/OperatorVisibilityController.php
sudo -n docker exec centracast-app php -l /app/app/Http/Controllers/Api/V1/Openclaw/OperatorVisibilityController.php

TOKEN=$(python3 - <<'PY'
from pathlib import Path
for line in Path('/opt/gunamaya-ai/workspaces/centracast-studio/centracast-runtime/.env').read_text().splitlines():
    if line.startswith('CENTRACAST_TOKEN='):
        print(line.split('=', 1)[1].strip().strip('"'))
        break
PY
)

curl -sS -D /tmp/cc_content_headers.txt \
  -o /tmp/cc_content_analytics.json \
  -H "Accept: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8080/api/v1/openclaw/channels/1/content-analytics"
```

For playlist-anchor work, inspect for:
- `existing_playlists`
- `source_metadata.playlists.playlists_source`
- `source_metadata.counts.playlist_rows`
- matching provenance note inside `notes`

Decision rule:
- if local endpoint returns `200` with the new fields present, treat that as the authoritative functional proof when the container image cannot run Laravel tests
- report separately that the code path works and that the remaining blocker is the test runner/tooling image, not the endpoint behavior

## Important pitfall: host may not have PHP CLI

A reusable failure mode occurred while trying to verify Laravel changes locally:
- running `php artisan test ...` on the host failed with `Command 'php' not found`
- the repo code could still be valid; only the host toolchain was incomplete

Decision rule:
- if host `php` is missing, do not stop at that error and do not report tests as impossible without checking the container path first
- prefer running Laravel test commands inside the app container or via the project Docker workflow

### Preferred test commands when host PHP is missing

If `centracast-app` is already running:

```bash
sudo -n docker exec centracast-app php artisan test tests/Unit/FetchYouTubeAnalyticsJobTest.php
sudo -n docker exec centracast-app php artisan test tests/Feature/OpenclawContentAnalyticsTest.php
```

### Critical pitfall: `php artisan test` can fail in production-style image builds

A reusable failure mode occurred in the image-baked `centracast-app` container:
- `php artisan test ...` crashed before running tests
- error was:

```text
Class "SebastianBergmann\\Environment\\Console" not found
```

This comes from the Laravel/Collision test command path inside the production-style image, not necessarily from the code under test.

Decision rule:
- if `php artisan test` dies in this way, do not treat it as an application regression yet
- try invoking PHPUnit directly inside the container:

```bash
sudo -n docker exec centracast-app sh -lc 'vendor/bin/phpunit tests/Unit/AnalyticsDashboardServiceTest.php'
```

- but verify first whether the production-style image actually contains PHPUnit tooling; in one live CentraCast case `vendor/bin/phpunit` was absent and `class_exists("PHPUnit\\Framework\\TestCase")` returned false
- when both Laravel test runner and PHPUnit binary are unavailable, do syntax verification (`php -l`) plus authoritative live repros with `php artisan tinker --execute=...`
- if local Docker code appears stale versus edited files, rebuild the relevant service or explicitly `docker cp`/resync files into the running container before trusting the repro
- report clearly when the blocker is container toolchain/build freshness rather than PHP syntax or app boot


### Test instrumentation pitfall: delay `Log::spy()` / `Log::fake()` until after fixture factories

A reusable failure mode showed up in CentraCast Laravel tests:
- the test called `Log::spy()` very early
- then model factories ran (`Channel::factory()->create()` etc.)
- app/factory side effects touched logging during setup
- the spy/fake replaced the logger too early and the test blew up with errors like `Call to a member function warning() on null`

Decision rule:
- when a test needs to assert logs, create tenants/channels/assets/releases first
- only call `Log::spy()` / `Log::fake()` after the fixture setup is done and right before invoking the unit under test
- then assert `warning` / `info` calls after the action

This is especially relevant in CentraCast because factories and related model boot/observer flows may emit logs or touch code paths that expect a fully wired logger.

### Critical pitfall: no-bind-mount app container will not see fresh host code/test edits

A reusable failure mode occurred after switching to the fallback `centracast-app` container started directly from the image with `--env-file` and no source bind mount:
- edits were made on the host repo
- running `php artisan test ...` inside `centracast-app` still executed the old in-container files
- this can make it look like a fix did not apply, when actually the container filesystem is stale

Decision rule:
- if the app container was started without a bind mount, sync changed files into the container before authoritative test runs
- do not assume the container automatically reflects host repo changes

### Proven sync flow for targeted verification

For a few changed files, copy them in explicitly:

```bash
sudo -n docker cp /opt/gunamaya-ai/workspaces/centracast-studio/centracast/tests/Feature/OpenclawContentAnalyticsTest.php centracast-app:/app/tests/Feature/OpenclawContentAnalyticsTest.php
sudo -n docker cp /opt/gunamaya-ai/workspaces/centracast-studio/centracast/tests/Unit/FetchYouTubeAnalyticsJobTest.php centracast-app:/app/tests/Unit/FetchYouTubeAnalyticsJobTest.php
```

If the runtime slice touched production code as well as tests, also sync the changed app files before treating in-container results as authoritative. Example from the YouTube analytics slice:

```bash
sudo -n docker cp /opt/gunamaya-ai/workspaces/centracast-studio/centracast/app/Jobs/FetchYouTubeAnalyticsJob.php centracast-app:/app/app/Jobs/FetchYouTubeAnalyticsJob.php
sudo -n docker cp /opt/gunamaya-ai/workspaces/centracast-studio/centracast/app/Http/Controllers/Api/V1/Openclaw/OperatorVisibilityController.php centracast-app:/app/app/Http/Controllers/Api/V1/Openclaw/OperatorVisibilityController.php
```

Then run the tests in-container:

```bash
sudo -n docker exec centracast-app php artisan test tests/Feature/OpenclawContentAnalyticsTest.php
```

If many files changed, prefer rebuilding/recreating the container from the updated source context instead of spraying many `docker cp` commands.

If the container name differs, first inspect running containers:

```bash
sudo -n docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

If the app container is not up yet, bring the stack up first and then run tests in-container.

### Reporting guidance for this case

When verification is blocked by missing host PHP:
- explicitly say host PHP CLI is absent
- explicitly say container-based verification is the next authoritative path
- avoid implying the code failed tests when the real blocker is only the host runtime

## Cleanup note

If you create temporary token/bootstrap files or copy dumps into containers, clean them up before declaring victory. Common leftovers from this flow:

```bash
rm -f /opt/gunamaya-ai/workspaces/centracast-studio/centracast/tmp-local-token.php
sudo -n docker exec centracast-app rm -f /tmp/local-token.php
sudo -n docker exec centracast-pgsql rm -f /tmp/staging.dump
```

Note: Hermes safety policy may require explicit approval before delete operations on root-path files or container `/tmp` paths.

## Local database cloning from staging

When the user wants staging data available locally, prefer cloning into a separate local database instead of dropping the default local DB unless they explicitly want overwrite.

### Why

A direct restore into the existing local DB can fail noisily because schema objects already exist.
A destructive reset (`DROP DATABASE`) also triggers approval/safety gates.
Creating a clone DB is usually faster, safer, and matches the user's likely intent.

### Proven flow

1. Confirm source staging DB is reachable.
2. Dump staging DB to a local file.
3. Create a new local database, e.g. `centracast_dev_clone`.
4. Restore the dump into that new DB.
5. Point Laravel `.env` at the clone DB.
6. Restart the app container and verify Laravel connects successfully.

### Reachability checks

Local Postgres container:

```bash
sudo -n docker exec centracast-pgsql pg_isready -U centracast_admin -d centracast_db
```

Remote staging Postgres using values from `.env`:

```bash
sudo -n docker run --rm --network host \
  -e PGPASSWORD='...' postgres:16-alpine \
  pg_isready -h 10.0.0.15 -p 5432 -U centracast -d centracast_dev_db
```

### Critical pitfall: remote "staging" DB target may be reachable but empty

A reusable failure mode occurred during local Docker verification:
- `centracast/.env` pointed Laravel at remote Postgres (`10.0.0.15`, `centracast_dev_db`)
- connectivity checks passed
- local app booted fine
- but authenticated OpenClaw verification still failed because the remote DB had no usable data at all

Observed shape in that case:
- `users = 0`
- `channels = 0`
- `personal_access_tokens = 0`
- Bearer requests to `/api/v1/openclaw/channels` and `/channels/1/content-analytics` returned `401 Unauthenticated`

Decision rule:
- do not equate "DB_HOST points to staging" with "authoritative staging data is available"
- after confirming connectivity, immediately sanity-check row counts before spending time debugging auth or endpoint code
- if counts are zero, report the blocker as a data-source problem, not an application regression

Fast sanity checks:

```bash
sudo -n docker exec centracast-app php artisan tinker --execute="echo json_encode(['database'=>DB::connection()->getDatabaseName(),'host'=>DB::connection()->getConfig('host'),'users'=>DB::table('users')->count(),'channels'=>DB::table('channels')->count(),'personal_access_tokens'=>DB::table('personal_access_tokens')->count()]);"
```

Or query the remote DB directly from Docker using `.env`:

```bash
set -a
source .env
set +a
sudo -n docker run --rm --network host \
  -e PGPASSWORD="$DB_PASSWORD" postgres:16-alpine \
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USERNAME" -d "$DB_DATABASE" -At -F ',' \
  -c "SELECT (SELECT count(*) FROM users),(SELECT count(*) FROM channels),(SELECT count(*) FROM personal_access_tokens);"
```

If this returns zeros, stop chasing token/auth issues and switch to one of:
- restore/clone a populated staging dump locally
- point `.env` at the actually populated DB
- seed minimal local user/channel/token fixtures for endpoint-path verification only

### Dump staging DB

From `centracast/`, after loading `.env`:

```bash
set -euo pipefail
set -a
source .env
set +a
DUMP_BASENAME="centracast_staging_$(date +%Y%m%d_%H%M%S).dump"
DUMP_PATH="/tmp/$DUMP_BASENAME"
sudo -n docker run --rm --network host \
  -e PGPASSWORD="$DB_PASSWORD" \
  -v /tmp:/dump postgres:16-alpine \
  pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USERNAME" -d "$DB_DATABASE" -Fc -f "/dump/$DUMP_BASENAME"
```

### Create clone DB and restore

Create DB:

```bash
sudo -n docker exec centracast-pgsql sh -lc 'export PGPASSWORD="supersecretpassword"; psql -U centracast_admin -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE centracast_dev_clone;"'
```

Copy dump into container if needed, then restore:

```bash
sudo -n docker cp /tmp/centracast_staging_YYYYMMDD_HHMMSS.dump centracast-pgsql:/tmp/staging.dump
sudo -n docker exec centracast-pgsql sh -lc 'export PGPASSWORD="supersecretpassword"; pg_restore -U centracast_admin -d centracast_dev_clone --no-owner --no-privileges /tmp/staging.dump'
```

### Critical pitfall: do NOT use 127.0.0.1 for DB_HOST inside app container

A reusable failure mode occurred after pointing Laravel at the clone DB:
- `.env` used `DB_HOST=127.0.0.1`
- app returned `500`
- logs showed connection refused to Postgres

Why:
- Laravel runs inside the `centracast-app` container
- inside that container, `127.0.0.1` means the app container itself, not the Postgres container

Use the Docker network hostname instead:

```env
DB_CONNECTION=pgsql
DB_DATABASE=centracast_dev_clone
DB_HOST=centracast-pgsql
DB_PASSWORD=supersecretpassword
DB_PORT=5432
DB_USERNAME=centracast_admin
```

### App restart after `.env` change

If you are using the no-bind-mount fallback app container, recreate it with the updated env file:

```bash
sudo -n docker rm -f centracast-app && \
sudo -n docker run -d \
  --name centracast-app \
  --network centracast_centracast-net \
  -p 8080:8080 -p 8443:443 \
  --env-file /opt/gunamaya-ai/workspaces/centracast-studio/centracast/.env \
  centracast-app:latest
```

### Critical pitfall: rebuilding via docker compose can reintroduce the bind-mount problem

A reusable failure mode occurred after rebuilding with:

```bash
sudo -n docker compose --profile production up -d --build app
```

The image rebuilt successfully, but the compose-managed `app` service still bind-mounted `.:/app`, so the container came up using the host tree and immediately failed with:

```text
require(/app/vendor/autoload.php): Failed to open stream: No such file or directory
Failed opening required '/app/vendor/autoload.php'
```

Decision rule:
- rebuilding the image is fine when you need fresh code baked in
- but if `docker-compose.yml` still has `volumes: - .:/app`, a plain compose restart is not an authoritative runtime check for this repo state
- after a rebuild, prefer launching the image directly with `docker run ... --env-file ... centracast-app:latest` and no source bind mount when you need the container to use the image-baked `vendor/` and built assets


### Verification after clone switch

Root page:

```bash
curl -sS -o /tmp/cc_root.out -w '%{http_code}\n' http://127.0.0.1:8080/
```

Database name from Laravel:

```bash
sudo -n docker exec centracast-app php artisan tinker --execute="echo DB::connection()->getDatabaseName();"
```

Migration visibility:

```bash
sudo -n docker exec centracast-app php artisan migrate:status
```

Useful DB sanity checks:

```bash
sudo -n docker exec centracast-pgsql psql -U centracast_admin -d centracast_dev_clone -c "SELECT count(*) AS table_count FROM information_schema.tables WHERE table_schema='public';"
sudo -n docker exec centracast-pgsql psql -U centracast_admin -d centracast_dev_clone -c "SELECT count(*) AS channels_count FROM channels;"
```

### Decision rule

- User asks to mirror staging locally but does not explicitly request overwrite: create `centracast_dev_clone`
- User explicitly wants local DB replaced: explain that restore into existing DB will conflict, then ask/obtain approval before drop/recreate

## Quick status commands

Check containers:

```bash
sudo -n docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

View app logs:

```bash
sudo -n docker logs --tail 120 centracast-app
sudo -n docker logs -f centracast-app
```

Stop stack:

```bash
cd /opt/gunamaya-ai/workspaces/centracast-studio/centracast
sudo -n docker compose --profile production down
```

## Local repro for Penpod web env / APP_KEY boot issues

Use this when staging web returns `MissingAppKeyException` or another boot-time env error and you need to prove whether the bug is source code or Penpod runtime env injection.

### Key lesson from a real APP_KEY incident

A reusable split-brain failure mode showed up:
- Penpod Vault for web deployment had `APP_KEY` populated
- `.github/workflows/staging.yml` also fetched `.env`, but only for the worker VPS flow (`worker.env` -> `~/centracast/.env`)
- local Docker with the current repo plus the web Vault env booted fine
- staging web still threw `No application encryption key has been specified`

Decision rule:
- do not treat the worker workflow's Vault fetch path as proof that Penpod web pods receive the same env
- if local image + Penpod web Vault env reproduces cleanly, suspect Penpod web rollout/env injection state first, not Laravel code
- the dummy `APP_KEY` in the Dockerfile `scribe:generate` RUN layer is build-time only and is not the runtime key source

### Proven local APP_KEY/env verification flow

1. Pull latest staging branch first:

```bash
cd /opt/gunamaya-ai/workspaces/centracast-studio/centracast
git fetch origin && git checkout staging && git pull --ff-only origin staging
```

2. Fetch the web deployment's Vault env from Penpod, not the worker workflow path. For deployment `36` / vault `17`, the relevant API operation was `get_ex_v1_vault_id_deployment_deployment_id`.

3. Write a temporary env file with the key runtime variables from that Vault payload, including at least:

```env
APP_ENV=staging
APP_KEY=base64:...
APP_DEBUG=false
APP_URL=https://staging.centracast.id
DB_CONNECTION=pgsql
DB_HOST=10.0.0.15
DB_PORT=5432
DB_DATABASE=centracast_stg_db
DB_USERNAME=centracast
DB_PASSWORD=...
CACHE_STORE=redis
SESSION_DRIVER=database
QUEUE_CONNECTION=redis
REDIS_HOST=10.0.0.13
REDIS_PORT=6379
REDIS_PASSWORD=...
LOG_CHANNEL=stderr
LOG_LEVEL=debug
```

4. Build the app image and run it directly with `--env-file` and no bind mount:

```bash
sudo -n docker compose --profile production up -d pgsql redis
sudo -n docker build -t centracast-app:latest .
sudo -n docker rm -f centracast-app >/dev/null 2>&1 || true
sudo -n docker run -d \
  --name centracast-app \
  --network centracast_centracast-net \
  -p 8080:8080 -p 8443:443 \
  --env-file /tmp/centracast-staging-web.env \
  centracast-app:latest
```

5. Verify the effective runtime env and Laravel config from inside the container:

```bash
sudo -n docker exec centracast-app env
sudo -n docker exec centracast-app php artisan tinker --execute="echo json_encode(['app_key'=>config('app.key'),'db_default'=>config('database.default'),'db_host'=>config('database.connections.pgsql.host'),'db_database'=>config('database.connections.pgsql.database')]);"
```

6. Smoke test both root and a protected OpenClaw route:

```bash
curl -sS -o /tmp/cc_local_root.out -w 'HTTP:%{http_code}\n' http://127.0.0.1:8080/
curl -sS -D /tmp/cc_local_channels_headers.txt \
  -o /tmp/cc_local_channels_body.txt \
  -H 'Accept: application/json' \
  -w 'HTTP:%{http_code}\n' \
  http://127.0.0.1:8080/api/v1/openclaw/channels
sudo -n docker logs --tail 120 centracast-app
```

Expected healthy result for this APP_KEY class of issue:
- `config('app.key')` shows the Vault key
- `/` returns `200`
- unauthenticated `/api/v1/openclaw/channels` returns `401`
- no `MissingAppKeyException` in container logs

If that passes locally while staging web still fails, report the blocker as Penpod web env injection / stale rollout state, not repo code.

## Reporting guidance

When done, separate conclusions clearly:
- Laravel local app status: up/down and root HTTP status
- API auth status: whether protected routes correctly return `401`
- runtime status: whether `npm run staging:harness` succeeded
- foreman status: explicitly not started, by request

## Pitfalls

- Do not claim `centracast-runtime` is a web service unless you found an actual server entrypoint.
- If Laravel returns `500`, inspect container logs before touching app code.
- If the log shows missing `vendor/autoload.php`, suspect bind-mount/image overlay first.
- If the user explicitly scoped out foreman, do not start it “just in case”.
