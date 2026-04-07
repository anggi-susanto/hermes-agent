---
name: mcp-config-troubleshooting
description: Diagnose and fix MCP server connection failures in Hermes Agent — wrong packages, masked passwords, broken config edits, and verifying actual file content vs display.
version: 1.0.0
author: Hermes Agent
tags: [MCP, config, troubleshooting, postgres, grafana]
related_skills: [native-mcp]
---

# MCP Config Troubleshooting

Use when MCP servers fail to connect, return auth errors, or don't appear as tools.

## Quick Diagnosis

Run all three MCP servers' list_resources simultaneously to see which are live vs broken.
Cross-reference failures against `~/.hermes/config.yaml` under `mcp_servers:`.

## Common Failure Modes

### 1. Wrong npm Package Name
Symptom: MCP server fails silently or with "package not found" on startup.
Fix: Verify the exact npm package name before adding to config.

Known correct packages:
- Grafana: verify the package/version actually installed before changing names. In this environment `@leval/mcp-grafana` was real and runnable, but its CLI flags had changed.
- Postgres: `@modelcontextprotocol/server-postgres`
- Filesystem: `@modelcontextprotocol/server-filesystem`

Grafana-specific lessons:
- A failure like `unknown option '--enabled-tools'` can mean the package is valid but the configured flags are stale.
- For current `@leval/mcp-grafana`, prefer category-disabling flags such as `--disable-dashboard`, `--disable-prometheus`, etc. instead of `--enabled-tools`.
- Check the live CLI contract first with:
```bash
npx -y @leval/mcp-grafana --help
```
- Another proven failure mode: the Grafana MCP process can be reachable enough for `hermes mcp test grafana` to show discovered tools, yet actual agent tool calls still fail with `No response from Grafana server` because the server writes startup banners/log lines to stdout before JSON-RPC traffic.
- Symptom in `hermes mcp test grafana`:
  - `Failed to parse JSONRPC message from server`
  - raw lines like `Starting MCP Grafana server with stdio transport...`
  - or JSON log objects that are not JSON-RPC envelopes
- Interpretation:
  - transport/discovery may still partially work
  - but stdio framing is polluted, so native tool calls become flaky or dead on arrival
- In the same environment, another independent issue was that `GRAFANA_URL` pointed at the internal address `http://10.0.0.35:3000`, while the actually reachable endpoint was the external URL `https://grafana.gunamaya.id`.
- The server also emits `Warning: GRAFANA_API_KEY is deprecated. Please use GRAFANA_SERVICE_ACCOUNT_TOKEN instead.` on stderr when only the old env var is provided. This warning alone is not what breaks JSON-RPC parsing, but it is a config hygiene issue and should be cleaned up.
- Practical fix sequence:
  1. verify the Grafana backend directly with the configured token via `/api/health` and `/api/datasources`
  2. if internal URL fails but external works, update `GRAFANA_URL` to the reachable external URL
  3. run `hermes mcp test grafana` and inspect for JSON-RPC parse errors
  4. if parse errors mention human/log output on stdout, treat the MCP server implementation as noisy/broken even if discovery says `✓ Tools discovered`
  5. for immediate operational work, bypass the broken stdio MCP path and query Grafana/Loki directly over the HTTP API using the same service-account/API token
  6. to restore native MCP tool reliability long-term, the Grafana MCP server must stop printing banners/logs to stdout (move them to stderr or disable them)
- Reporting rule:
  - separate `Grafana backend access works` from `Hermes native Grafana MCP tools are reliable` — these are not the same thing.

### 2. Password Looks Like `***` in File
Symptom: `read_file` or `grep` shows `***` as the password in a postgres connection string.
Cause: Hermes has `redact_secrets: true` in config — it masks credential-like patterns in tool OUTPUT, but the file itself may be correct.

**Always verify actual file bytes before editing:**
```python
with open('/home/gunamaya/.hermes/config.yaml', 'rb') as f:
    raw = f.read()
import re
for m in re.finditer(b'postgresql://[^\n]+', raw):
    print(repr(m.group()))
```

If the hex decode shows the real password, the file is fine and display is just masked.
If it literally contains `***` bytes, then fix is needed.

### 3. Password Contains Special Characters (e.g. `@`)
Symptom: Connection string auth fails even with correct password.
Cause: `@` in password conflicts with the `user:pass@host` URL format.
Fix: URL-encode special chars in the password:
- `@` → `%40`
- `#` → `%23`
- `%` → `%25`

Example: password `centracast@gnmy2026` becomes `centracast%40gnmy2026` in the URL.

### 3.5. Server Name Does Not Match Target Database
Symptom: MCP server appears healthy, but you're inspecting or mutating the wrong environment.
Cause: The `mcp_servers` entry name (for example `postgres-centracast-staging`) may point at a connection string whose database name is actually `*_dev_*` or another environment.
Fix: Verify BOTH the label and the real DSN target before trusting the setup.

Checklist:
- Read `~/.hermes/config.yaml` and inspect the `mcp_servers.<name>.args` entry
- Confirm the final postgres URL points to the expected host, port, and database name
- If output masking is enabled, verify raw bytes from the file instead of trusting displayed `***`
- Separately test TCP reachability to `host:port`
- Start the MCP server process and confirm it stays alive for a few seconds (not just config presence)

This catches the sneaky case where a server called `staging` is actually connected to `centracast_dev_db`.

### 4. File Edit Fails Due to Masked Display
Symptom: `patch` or `sed` can't match the string because display shows `***` but bytes differ.
Fix: Use Python to do raw byte replacement:
```python
with open('/home/gunamaya/.hermes/config.yaml', 'rb') as f:
    raw = f.read()

fixed = raw.replace(
    b'postgresql://user:***@host/db',
    b'postgresql://user:realpassword@host/db'
)

with open('/home/gunamaya/.hermes/config.yaml', 'wb') as f:
    f.write(fixed)
```

If `patch` keeps failing, skip it entirely and rewrite the whole `mcp_servers:` block using Python regex substitution on the raw string.

### 4.5. Wrong Client Config File Is Being Tested
Symptom: Hermes-native MCP works, but another client/tooling path (for example Roo, Claude Desktop, or an ad-hoc MCP launcher) still fails with auth or malformed URL errors.
Cause: You fixed `~/.hermes/config.yaml`, but the failing client is actually reading a different config file such as `.roo/mcp.json`.

Common pattern:
- Hermes config contains a valid encoded DSN like `postgresql://user:password%40withat@host/db`
- Alternate client config still contains a broken raw DSN like `postgresql://user:password@withat@host/db`
- Because secrets are masked in output, both can look superficially similar until you inspect raw bytes or parse the URL

Checklist:
1. Identify which client is failing (`hermes`, `mcporter`, Roo, Claude Desktop, etc.)
2. Inspect THAT client's config file, not just `~/.hermes/config.yaml`
3. For JSON configs like `.roo/mcp.json`, read the exact DSN and look for unencoded `@` in the password
4. Normalize DSNs to URL-encoded form (`@` → `%40`)
5. Restart/reload the affected client after editing so it re-reads config

Practical lesson:
- A successful `hermes mcp test <server>` only proves Hermes can spawn and discover tools from its own config
- It does NOT prove that a separate MCP client using a different config file is healthy

### 5. Config Block Gets Corrupted
Symptom: After multiple edits, the config has duplicate or malformed lines.
Fix: Reconstruct the entire `mcp_servers:` block from scratch using Python regex:
```python
import re

new_mcp = """mcp_servers:
  server_name:
    command: npx
    ..."""

with open('/home/gunamaya/.hermes/config.yaml', 'r') as f:
    content = f.read()

# Replace block up to the comment separator
result = re.sub(r'mcp_servers:.*?(?=\n# ──)', new_mcp + '\n', content, flags=re.DOTALL)

with open('/home/gunamaya/.hermes/config.yaml', 'w') as f:
    f.write(result)
```

## Verification After Fixing

1. Confirm file bytes are correct (see step 2 above)
2. Restart Hermes Agent to re-trigger MCP discovery
3. Re-run list_resources on each server to confirm connection
4. If the server is configured in Hermes, also run:
```bash
uv run hermes mcp test <server-name>
```
This validates Hermes can spawn the MCP server and discover tools.
5. For Grafana MCP specifically, distinguish these layers:
   - MCP process spawn/discovery works
   - the MCP server can actually reach the Grafana backend URL
   - the Grafana backend can actually execute datasource/Loki queries

   A successful `hermes mcp test grafana` is NOT enough. After discovery, immediately do one of:
```bash
python -c "import requests, yaml; cfg=yaml.safe_load(open('/home/gunamaya/.hermes/config.yaml')); env=cfg['mcp_servers']['grafana']['env']; print(requests.get(env['GRAFANA_URL'].rstrip('/') + '/api/datasources', headers={'Authorization': 'Bearer ' + env.get('GRAFANA_SERVICE_ACCOUNT_TOKEN', env.get('GRAFANA_API_KEY',''))}, timeout=15).status_code)"
```
or ask Hermes to call a lightweight Grafana MCP tool like `list_datasources`.

   If that fails with connection refused / no response, the problem is backend reachability or bad `GRAFANA_URL`, not the Loki query syntax.
6. If you need to query through `mcporter`, remember `mcporter` does NOT automatically use Hermes' `~/.hermes/config.yaml` MCP entries. Either:
   - use `mcporter` with its own config, or
   - use an ad-hoc invocation such as `mcporter call --stdio "npx -y @modelcontextprotocol/server-postgres '<dsn>'" ...`

## Additional Failure Mode: Hermes Test Passes, Direct Query Still Fails
Symptom: `hermes mcp test <server>` reports success and tool discovery, but direct `mcporter call` or an actual `query` returns `password authentication failed`.

Interpretation:
- Hermes successfully launched the MCP server process
- The server advertised tools
- but real DB auth may still be broken for live queries

Do NOT treat tool discovery alone as proof that the backing database is usable.

Recommended sequence:
1. Test raw TCP reachability to `host:port`
2. Run `hermes mcp test <server>` to confirm Hermes-side spawn/discovery
3. Run an actual read-only query against `information_schema` or `select 1`
4. Only after a real query succeeds should you conclude the MCP Postgres setup is healthy

## Additional Failure Mode: One Noisy MCP Server Pollutes `hermes chat`, But the Target Server Is Fine
Symptom:
- `hermes mcp test context7` (or another target server) succeeds cleanly
- but `hermes chat -q ...` shows JSON-RPC parse errors during startup such as `Failed to parse JSONRPC message from server`
- the noisy output often comes from a different stdio MCP server printing banners, warnings, or logs to stdout

Interpretation:
- the target MCP server may be healthy
- a separate configured stdio server is violating the MCP contract by writing non-JSON to stdout
- Hermes chat loads all configured MCP servers, so one bad actor can create scary noise even when the server you care about still works

Practical lesson:
- treat `hermes mcp test <server>` as the clean per-server transport/discovery check
- if chat startup is noisy, inspect other configured MCP servers (Grafana-style servers are common offenders)
- stdout must be reserved for JSON-RPC only; banner/log output must move to stderr or be disabled
- a noisy sibling server does not necessarily invalidate successful tool calls from the target server

Useful workflow:
1. Run `hermes mcp test <target>` first
2. If that passes but `hermes chat` is noisy, identify which other configured server is printing to stdout
3. Fix that server's flags/env/logging, then re-test chat
4. Keep the distinction explicit in reporting: target server healthy, separate MCP server noisy/broken

## Pitfalls

- `redact_secrets: true` makes ALL tool output mask secrets — grep, cat, read_file will all show `***`. Always use raw bytes for verification.
- Double URL-encoding can happen if you replace already-encoded strings. Check with hex decode before replacing.
- After a botched multi-step edit, it's faster to rewrite the whole block than to try patching incrementally.
