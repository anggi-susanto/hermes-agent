---
name: centracast-foreman-callback-signing-rollout
description: Diagnose and roll out CentraCast Foreman callback HMAC signing across GitHub Actions-based Foreman and Laravel staging Vault, including blockers and verification order.
---

# When to use
Use this when Laravel staging rejects Foreman callbacks (401 / unknown signing key / empty callback signing config), or when callback signing needs to be introduced or rotated between `centracast-foreman` and `centracast` staging.

# Key truths
1. `centracast-foreman` may run via GitHub Actions/self-hosted runner + Docker Compose, not via Penpod service deployment. Do not assume there is a Penpod deployment for Foreman.
2. Laravel staging verification depends on Vault-backed env, not just code. Missing Vault vars can make `config('services.foreman.callback_signing_keys')` effectively empty.
3. Required shared config usually includes:
   - `FOREMAN_CALLBACK_SIGNING_KEY_ID`
   - `FOREMAN_CALLBACK_SIGNING_SECRET`
   - optionally `FOREMAN_CALLBACK_SIGNING_TOLERANCE_SECONDS`
4. Repo/remote truth can supersede local work. If local `git push` is rejected, inspect `origin/staging` before redoing the patch — the remote branch may already contain the fix.
5. If Vault returns `403 permission denied` / `invalid token`, stop and report an infra/auth blocker instead of pretending rollout is complete.
6. Hermes MCP Vault can keep using stale credentials even after `~/.hermes/.env` is updated. If MCP still says `invalid token` but a direct HTTP request with `VAULT_ADDR` + `VAULT_TOKEN` succeeds, bypass MCP and use manual Vault API calls for read/diff/write.

# Procedure
1. Confirm runtime topology first.
   - Check `centracast-foreman` workflow(s), deployment path, and whether secrets come from GitHub repo secrets + Vault fetch in Actions.
   - Do not waste time searching Penpod service status if Foreman is Actions-driven.
2. Confirm backend expectation.
   - Verify Laravel staging expects signed callbacks and which env vars map to verifier config.
3. Inspect Foreman repo state.
   - Check `origin/staging` before pushing local commits.
   - If push is rejected (`fetch first`), inspect `git log staging..origin/staging` and `git show origin/staging:<file>`.
   - If origin already has the desired callback signing implementation, prefer rebasing or skipping the local duplicate commit.
4. Check GitHub repo secret surface.
   - `gh secret list` in the relevant repo to see whether callback signing secret exists.
   - If missing, treat this as evidence that secret must be generated/rotated intentionally, not “synced” from nowhere.
5. Generate secret if needed.
   - Example: `openssl rand -base64 48`
6. Before changing Vault, read current secret/config and prepare a before/after diff.
   - If the user has a rule requiring confirmation before Vault/env changes, pause here with the exact diff.
7. Apply both sides consistently.
   - Laravel staging Vault: add/update callback signing vars.
   - Foreman deploy path: ensure the same secret is available to GitHub Actions/deployed `.env`.
8. Resolve the exact Vault path before editing secrets.
   - `VAULT_SECRET_PATH_STG` value is often hidden in GitHub Secrets; do not assume paths like `kv/...`.
   - Enumerate keys from the mount metadata when needed (e.g. `/v1/<mount>/metadata?list=true`) and confirm the real path with operator.
9. Trigger rollout.
   - Re-run or push the relevant workflow(s) for backend/Foreman as needed.
10. Verify with reality checks.
   - Workflow run status
   - deployed env fetch path
   - application logs / callback result
   - run callback proof matrix:
     - bad signature => `401 Invalid callback signature`
     - good signature + nonexistent release_id => `404 Release not found`
     - good signature + existing release_id (even if wrong state) => non-401/non-404 business response (e.g. `200 Release not in expected state`)
11. For manual callback tests, always sign with the current live secret fetched from the same staging Vault path used by web.
   - Do not reuse old/local/redacted secret strings from notes.
   - Recompute timestamp + signature per request (`X-Foreman-Callback-Timestamp` + HMAC over `timestamp.rawBody`), otherwise you can get false negatives (`Invalid callback signature`) even when rollout is actually healthy.
12. If callback remains `Unknown callback signing key` after successful runs, treat it as deployment-topology mismatch (e.g., worker redeployed but web/API pod not restarted). Locate and redeploy the actual web serving surface before declaring success.
13. If you need a valid release_id quickly for business-path proof and no read API is readily accessible, probe a small bounded ID range with signed `status=running` payloads and stop at first non-404 response.
   - This avoids DB-side assumptions and gives direct runtime evidence from the real endpoint.

# Fast commands
- Check repo secrets:
  - `gh secret list`
- Generate secret:
  - `openssl rand -base64 48`
- Compare local vs remote before pushing:
  - `git fetch origin && git log --oneline staging..origin/staging`
- Inspect remote file directly:
  - `git show origin/staging:internal/webhook/notifier.go`

# Blockers to call out explicitly
- Vault auth failure (`403 permission denied`, `invalid token`) means you cannot produce a trustworthy before/after diff or safely apply staging env changes.
- Push rejection does not automatically mean your branch is right; inspect remote first.
- Missing GitHub secret means there may be no existing source-of-truth secret to reuse.

# Reporting template
- Code truth: whether `origin/staging` already includes HMAC signing
- Secret truth: whether GitHub repo secret exists
- Vault truth: whether staging Vault can be read/updated
- Residual gap: the exact missing step (usually secret distribution / Vault access)
- Next action: concrete unblock step, e.g. fix Vault auth, then apply diff and redeploy
