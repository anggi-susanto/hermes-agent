---
name: penpod-env-mismatch-diagnosis
description: Diagnose Penpod/K8s staging environment variable mismatches when runtime behavior contradicts Vault config, using remote evidence collection without direct pod access
tags: [penpod, kubernetes, vault, env-vars, staging, diagnostic, laravel]
---

# Penpod Environment Mismatch Diagnosis

Systematic approach to diagnose why a Penpod/K8s service uses wrong environment variables despite correct Vault configuration, when you have no direct pod/container access.

## When to Use

- Staging API returns errors indicating wrong DB connection (e.g., mysql://127.0.0.1 instead of pgsql://10.0.0.x)
- Vault config is verified correct but runtime behavior contradicts it
- You have access to: Grafana Loki logs, Penpod API, Jenkins build logs, repo Dockerfile
- You do NOT have: kubectl access, pod shell access, direct container inspection

## Evidence Collection Layers (Execute in Order)

### 1. Confirm Vault Truth
```bash
# Via Penpod MCP or API
mcp_penpod_penpod_call_operation(
  operation_id="get_ex_v1_vault_vault_id",
  path_params={"vault_id": 17}
)
```

**What to extract:**
- Claimed DB_CONNECTION, DB_HOST, DB_PORT, DB_DATABASE, DB_USERNAME
- APP_KEY validity (base64: prefix, length)
- Total variable count

### 2. Extract Live Runtime Evidence from Logs
```bash
# Grafana Loki query for DB connection errors
{service_name="stg-centracast-web"} |= "SQLSTATE[HY000] [2002]"
```

**What to extract from error traces:**
- Effective DB driver (mysql vs pgsql)
- Effective DB_HOST (127.0.0.1 vs expected IP)
- Effective DB_DATABASE (laravel vs expected name)
- Pod names generating errors
- Timestamp range

**Key insight:** Laravel QueryException messages reveal exact connection params used at runtime.

### 3. Check Penpod Service Deployment Status
```bash
mcp_penpod_penpod_get_service_deployment_status(
  deployment_name="stg-centracast-web"
)
```

**What to extract:**
- Current status (Healthy vs Progressing)
- Active replica sets and their revisions
- Pod names and ready state
- Generation number
- BlueGreen cutover state

**Red flags:**
- Status "Progressing" with "active service cutover pending"
- Multiple replica sets with different revisions running
- Pod names in logs don't match current active pods

### 4. Trace Build Pipeline Evidence
```bash
# Read Jenkins/GitHub Actions build log for the deployed tag
# Look for:
# - Vault fetch step output (variable count)
# - .env write confirmation
# - Docker build context
```

**What to extract:**
- Did Vault fetch succeed? (e.g., "✅ Number of variables: 81")
- Was .env written before docker build?
- Which Dockerfile steps ran?
- Any config:cache or optimize commands?

### 5. Audit Dockerfile and .dockerignore
```bash
# Check if .env is excluded from build context
cat .dockerignore | grep -E "^\.env"

# Check if any RUN commands cache config
grep -E "config:cache|optimize|artisan config" Dockerfile
```

**Red flags:**
- `.env` or `.env.*` in .dockerignore → env not baked into image
- No `config:cache` in Dockerfile → runtime reads env fresh (good)
- Dummy env used for build steps (e.g., scribe:generate) → verify it doesn't leak

### 6. Check Deployment History vs Active Pods
```bash
mcp_penpod_penpod_get_latest_deployment_history(
  deployment_id=36,
  job_id=19,
  tag="v0.10.4-beta-rc19"
)
```

**What to extract:**
- build_status (queued vs success)
- created_at timestamp
- Compare with pod names from logs

**Red flag:** History shows new tag "queued" but logs show errors from pods with older replica set names → new image not yet rolled out.

## Diagnosis Decision Tree

### If Vault is correct AND logs show wrong env:

**A. Pod revision mismatch (most common)**
- Symptom: Log pod names don't match current service replica sets
- Symptom: Deployment history shows new tag "queued" but service status shows older revision
- Root cause: New image built but not yet rolled out to K8s
- Fix: Trigger rollout or wait for BlueGreen cutover to complete

**B. .dockerignore excludes .env (common)**
- Symptom: Jenkins log shows .env written, but Dockerfile has `.env` in .dockerignore
- Root cause: .env not copied into image build context
- Fix: Either (1) remove .env from .dockerignore and rebuild, OR (2) ensure Penpod injects env vars at pod startup (preferred for secrets)

**C. Laravel config fallback (symptom, not root cause)**
- Symptom: Runtime uses exact default values from config/database.php (e.g., `'host' => env('DB_HOST', '127.0.0.1')`)
- Root cause: Env vars not available at runtime, so Laravel uses hardcoded fallbacks
- Fix: Resolve A or B above

**D. Config cache baked into image (rare)**
- Symptom: Dockerfile has `php artisan config:cache` before CMD
- Root cause: Config cached with build-time env, not runtime env
- Fix: Remove config:cache from Dockerfile, or ensure it runs after env injection

## Verification After Fix

1. **Confirm new pod spawned:**
   ```bash
   # Check service status again
   mcp_penpod_penpod_get_service_deployment_status(...)
   # Verify pod names changed and revision incremented
   ```

2. **Confirm logs show correct connection:**
   ```bash
   # Query Loki for recent logs from new pods
   {service_name="stg-centracast-web", pod=~".*NEW_REPLICA_SET.*"} |= "DB_HOST"
   # Should show pgsql://10.0.0.x instead of mysql://127.0.0.1
   ```

3. **Test API endpoints:**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://staging.centracast.id/api/v1/openclaw/channels
   # Should return 200, not 500
   ```

## Pitfalls

- **Don't assume Vault is wrong first** - Vault config is usually correct; the issue is env injection or pod rollout
- **Don't trust deployment history alone** - Penpod history can lag behind actual K8s rollout state
- **Don't ignore .dockerignore** - Even if Jenkins writes .env, it won't be in the image if excluded
- **Don't confuse build-time env with runtime env** - Dummy env for scribe:generate is fine; runtime env must come from Vault/K8s

## Related Skills

- `centracast-staging-deploy` - For triggering and verifying Penpod deployments
- `systematic-debugging` - General debugging methodology
- `centracast-grafana-loki-direct` - For querying staging logs

## Real-World Example

**Scenario:** CentraCast staging API returns 500 with "SQLSTATE[HY000] [2002] Connection refused (mysql, 127.0.0.1, laravel)" despite Vault 17 having correct pgsql config.

**Evidence collected:**
1. Vault 17: DB_CONNECTION=pgsql, DB_HOST=10.0.0.15, DB_DATABASE=centracast_stg_db ✓
2. Loki logs: Runtime uses mysql://127.0.0.1/laravel (fallback values from config/database.php)
3. Penpod service: Status "Healthy", revision 85, pod `stg-centracast-web-855f94c4d8-f2ccr`
4. Loki error pods: `stg-centracast-web-bbdb9f444-mhzq7` (older replica set)
5. Deployment history: Tag rc19 status "queued", created 20:55
6. .dockerignore: Contains `.env` and `.env.*` → env not in image
7. Dockerfile: No config:cache → runtime reads env fresh

**Root cause:** Two-part issue:
1. .env excluded from image build context (by design for security)
2. New image rc19 built but not yet rolled out - active pods are from older revision

**Fix:** Trigger Penpod rollout of rc19 to spawn new pods with Vault env injection.
