---
name: centracast-grafana-loki-direct
description: Query CentraCast staging and production logs directly from Grafana/Loki over HTTP when the native Grafana MCP path is noisy or broken.
---

# CentraCast Grafana Loki Direct

Use this when:
- you need CentraCast logs from staging or production fast
- native `mcp_grafana_*` tools return `No response from Grafana server`
- `@leval/mcp-grafana` is printing junk to stdout and breaking JSON-RPC framing

## Why this exists

In this environment, Grafana backend access works, but the native stdio MCP server can still be flaky because it prints startup/log lines to stdout.

Proven reality:
- reachable Grafana URL: `https://grafana.gunamaya.id`
- old internal URL `http://10.0.0.35:3000` is not the reliable target from this environment
- Loki datasource exists and was observed with uid: `cfasxl82dd534d`
- CentraCast-relevant Loki labels include:
  - `service_name=stg-centracast-web`
  - `service_name=prd-gnm-centracast-web`
  - `service_name=centracast-vps-worker-api`
  - `service_name=centracast-vps-worker-express`
  - `service_name=centracast-vps-worker-scheduler`
  - `service_name=centracast-foreman`

## Credential source

Read the Grafana token from:
- `~/.hermes/config.yaml`
- path: `mcp_servers.grafana.env.GRAFANA_API_KEY`

Important:
- the token may be redacted in tool output; use Python/YAML to read it, not eyeballing masked output

## Fast smoke test

Use this exact pattern:

```bash
python - <<'PY'
import yaml, requests
cfg=yaml.safe_load(open('/home/gunamaya/.hermes/config.yaml'))
url='https://grafana.gunamaya.id'
token=cfg['mcp_servers']['grafana']['env']['GRAFANA_API_KEY']
headers={'Authorization':'Bearer '+token}
for path in ['/api/health','/api/datasources']:
    r=requests.get(url+path, headers=headers, timeout=20)
    print(path, r.status_code, r.text[:400])
PY
```

Expected:
- `/api/health` → `200`
- `/api/datasources` → includes Loki datasource

## Find the Loki datasource UID

```bash
python - <<'PY'
import yaml, requests, json
cfg=yaml.safe_load(open('/home/gunamaya/.hermes/config.yaml'))
url='https://grafana.gunamaya.id'
token=cfg['mcp_servers']['grafana']['env']['GRAFANA_API_KEY']
headers={'Authorization':'Bearer '+token}
r=requests.get(url+'/api/datasources', headers=headers, timeout=20)
r.raise_for_status()
for ds in r.json():
    if ds.get('type') == 'loki':
        print(json.dumps({'name': ds['name'], 'uid': ds['uid']}, separators=(',',':')))
PY
```

Known observed UID in this environment:
- `cfasxl82dd534d`

Still re-check instead of hardcoding blindly.

## List available Loki labels / values

```bash
python - <<'PY'
import yaml, requests, time
cfg=yaml.safe_load(open('/home/gunamaya/.hermes/config.yaml'))
url='https://grafana.gunamaya.id'
token=cfg['mcp_servers']['grafana']['env']['GRAFANA_API_KEY']
headers={'Authorization':'Bearer '+token}
uid='cfasxl82dd534d'
start=str(int((time.time()-86400)*1e9))
end=str(int(time.time()*1e9))
base=f'{url}/api/datasources/proxy/uid/{uid}/loki/api/v1'
for path in [
    '/labels',
    '/label/service_name/values',
    '/label/namespace/values',
    '/label/job/values',
]:
    r=requests.get(base+path, headers=headers, params={'start':start,'end':end}, timeout=30)
    print(path, r.status_code, r.text[:3000])
PY
```

## Query logs directly

Basic pattern:

```bash
python - <<'PY'
import yaml, requests, json, time
cfg=yaml.safe_load(open('/home/gunamaya/.hermes/config.yaml'))
url='https://grafana.gunamaya.id'
token=cfg['mcp_servers']['grafana']['env']['GRAFANA_API_KEY']
headers={'Authorization':'Bearer '+token}
uid='cfasxl82dd534d'
query='{service_name="stg-centracast-web"}'
start=str(int((time.time()-86400)*1e9))
end=str(int(time.time()*1e9))
base=f'{url}/api/datasources/proxy/uid/{uid}/loki/api/v1/query_range'
r=requests.get(base, headers=headers, params={
    'query': query,
    'limit': 20,
    'start': start,
    'end': end,
    'direction': 'backward',
}, timeout=40)
r.raise_for_status()
print(json.dumps(r.json())[:5000])
PY
```

## Common CentraCast queries

### Staging web
```logql
{service_name="stg-centracast-web"}
```

### Production web
```logql
{service_name="prd-gnm-centracast-web"}
```

### Staging analytics-related lines
```logql
{service_name="stg-centracast-web"} |= "analytics"
```

### Production analytics-related lines
```logql
{service_name="prd-gnm-centracast-web"} |= "analytics"
```

### Staging scheduler worker
```logql
{service_name="centracast-vps-worker-scheduler"}
```

### Staging API-heavy worker
```logql
{service_name="centracast-vps-worker-api"}
```

### Foreman logs
```logql
{service_name="centracast-foreman"}
```

### Narrow by known error keyword
```logql
{service_name="stg-centracast-web"} |= "FetchYouTubeAnalyticsJob"
```

```logql
{service_name="stg-centracast-web"} |= "AnalyticsDashboardService"
```

```logql
{service_name="stg-centracast-web"} |= "Unknown identifier (impressions)"
```

## Python helper output pattern

When reporting results upstream, reduce the giant Loki response into compact JSON:

```python
out=[]
for stream in data.get('data',{}).get('result',[]):
    meta=stream.get('stream',{})
    for ts, line in stream.get('values',[]):
        out.append({
            'service_name': meta.get('service_name'),
            'pod': meta.get('pod'),
            'job': meta.get('job'),
            'ts': ts,
            'line': line,
        })
print(json.dumps(out[:20], separators=(',',':')))
```

Use this instead of dumping the full Loki payload unless debugging the query engine itself.

## Interpretation rules

- `200` with empty `result` means query path is healthy but no matching lines in that time window
- if raw web logs appear for `{service_name="stg-centracast-web"}` or prod equivalent, Grafana/Loki access is working
- separate these states carefully:
  1. Grafana backend reachable
  2. Loki datasource queryable
  3. matching logs exist for the selected query/time window

Do not collapse them into one vague "Grafana works/doesn't work" blob.

## Native MCP caveat

If `hermes mcp test grafana` shows things like:
- `Failed to parse JSONRPC message from server`
- `Starting MCP Grafana server with stdio transport...`
- `Enabled tool categories: ...`

then the MCP server is noisy on stdout.

Interpretation:
- direct Grafana HTTP API can still work perfectly
- native `mcp_grafana_*` Hermes tools may remain unreliable until the server stops printing non-JSON-RPC output on stdout

## Helper script

A reusable helper script lives at:
- `scripts/query_loki.py`

Example usage:

```bash
python ~/.hermes/skills/software-development/centracast-grafana-loki-direct/scripts/query_loki.py --service staging --grep analytics --since 24h --show-query
python ~/.hermes/skills/software-development/centracast-grafana-loki-direct/scripts/query_loki.py --service api-worker --grep FetchYouTubeAnalyticsJob --since 6h
python ~/.hermes/skills/software-development/centracast-grafana-loki-direct/scripts/query_loki.py --preset staging-impressions-error --since 7d --stats
```

Supported shortcuts:
- `--service staging|stg`
- `--service prod|production`
- `--service api-worker`
- `--service express-worker`
- `--service scheduler-worker`
- `--service foreman`

Presets currently available:
- `staging-analytics`
- `prod-analytics`
- `staging-fetch-job`
- `staging-dashboard-service`
- `staging-impressions-error`

Output stays compact JSON by default:
- `rows`: reduced list of matching lines with service/pod/job metadata
- `meta`: only when `--show-query` is used
- `stats`: only when `--stats` is used

## Pitfalls

- using the old internal URL instead of `https://grafana.gunamaya.id`
- assuming empty analytics query results mean Grafana is broken
- hardcoding the Loki UID forever without re-checking datasource metadata
- dumping the entire Loki JSON blob into chat when a compact reduced projection is enough
- forgetting nanosecond timestamps for Loki `start` / `end` when using proxy API directly
