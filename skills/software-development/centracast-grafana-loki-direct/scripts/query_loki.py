#!/usr/bin/env python3
import argparse
import json
import sys
import time
from pathlib import Path

import requests
import yaml

CONFIG_PATH = Path('/home/gunamaya/.hermes/config.yaml')
DEFAULT_GRAFANA_URL = 'https://grafana.gunamaya.id'
DEFAULT_LIMIT = 20

SERVICE_ALIASES = {
    'staging': 'stg-centracast-web',
    'stg': 'stg-centracast-web',
    'prod': 'prd-gnm-centracast-web',
    'production': 'prd-gnm-centracast-web',
    'web-stg': 'stg-centracast-web',
    'web-prod': 'prd-gnm-centracast-web',
    'api-worker': 'centracast-vps-worker-api',
    'express-worker': 'centracast-vps-worker-express',
    'scheduler-worker': 'centracast-vps-worker-scheduler',
    'foreman': 'centracast-foreman',
}

PRESET_QUERIES = {
    'staging-analytics': '{service_name="stg-centracast-web"} |= "analytics"',
    'prod-analytics': '{service_name="prd-gnm-centracast-web"} |= "analytics"',
    'staging-fetch-job': '{service_name="stg-centracast-web"} |= "FetchYouTubeAnalyticsJob"',
    'staging-dashboard-service': '{service_name="stg-centracast-web"} |= "AnalyticsDashboardService"',
    'staging-impressions-error': '{service_name="stg-centracast-web"} |= "Unknown identifier (impressions)"',
}


def load_config():
    return yaml.safe_load(CONFIG_PATH.read_text())


def get_token_and_url(cfg):
    grafana = cfg.get('mcp_servers', {}).get('grafana', {})
    env = grafana.get('env', {})
    token = env.get('GRAFANA_SERVICE_ACCOUNT_TOKEN') or env.get('GRAFANA_API_KEY')
    url = env.get('GRAFANA_URL') or DEFAULT_GRAFANA_URL
    if not token:
        raise SystemExit('Grafana token not found in ~/.hermes/config.yaml under mcp_servers.grafana.env')
    return token, url.rstrip('/')


def get_loki_uid(url, headers):
    r = requests.get(f'{url}/api/datasources', headers=headers, timeout=20)
    r.raise_for_status()
    for ds in r.json():
        if ds.get('type') == 'loki':
            return ds['uid']
    raise SystemExit('No Loki datasource found')


def since_to_ns(value):
    unit = value[-1]
    amount = int(value[:-1])
    seconds = {
        'm': 60,
        'h': 3600,
        'd': 86400,
    }.get(unit)
    if not seconds:
        raise SystemExit('--since must end with m, h, or d (examples: 30m, 6h, 2d)')
    now = time.time()
    start = int((now - amount * seconds) * 1e9)
    end = int(now * 1e9)
    return str(start), str(end)


def build_query(args):
    if args.preset:
        return PRESET_QUERIES[args.preset]

    service = args.service
    if service:
        service = SERVICE_ALIASES.get(service, service)
        query = f'{{service_name="{service}"}}'
    elif args.raw_query:
        query = args.raw_query
    else:
        raise SystemExit('Provide --service, --preset, or --raw-query')

    if args.grep:
        query += f' |= {json.dumps(args.grep)}'
    return query


def compact_rows(payload, limit):
    out = []
    for stream in payload.get('data', {}).get('result', []):
        meta = stream.get('stream', {})
        for ts, line in stream.get('values', []):
            out.append({
                'service_name': meta.get('service_name'),
                'namespace': meta.get('namespace'),
                'pod': meta.get('pod'),
                'job': meta.get('job'),
                'stream': meta.get('stream'),
                'ts': ts,
                'line': line,
            })
            if len(out) >= limit:
                return out
    return out


def main():
    parser = argparse.ArgumentParser(description='Query CentraCast Loki logs via Grafana HTTP API')
    parser.add_argument('--service', help='Service name or alias (staging, prod, api-worker, scheduler-worker, foreman, etc.)')
    parser.add_argument('--grep', help='Substring filter appended as |= "..."')
    parser.add_argument('--preset', choices=sorted(PRESET_QUERIES), help='Use a saved LogQL preset')
    parser.add_argument('--raw-query', help='Full raw LogQL query')
    parser.add_argument('--since', default='24h', help='Lookback window like 30m, 6h, 2d (default: 24h)')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT, help='Max returned log rows (default: 20)')
    parser.add_argument('--direction', choices=['forward', 'backward'], default='backward')
    parser.add_argument('--stats', action='store_true', help='Print Loki stats summary too')
    parser.add_argument('--show-query', action='store_true', help='Include resolved query + datasource metadata in output')
    args = parser.parse_args()

    cfg = load_config()
    token, url = get_token_and_url(cfg)
    headers = {'Authorization': f'Bearer {token}'}
    uid = get_loki_uid(url, headers)
    start, end = since_to_ns(args.since)
    query = build_query(args)

    r = requests.get(
        f'{url}/api/datasources/proxy/uid/{uid}/loki/api/v1/query_range',
        headers=headers,
        params={
            'query': query,
            'limit': args.limit,
            'start': start,
            'end': end,
            'direction': args.direction,
        },
        timeout=45,
    )
    r.raise_for_status()
    payload = r.json()

    result = {
        'rows': compact_rows(payload, args.limit),
    }
    if args.show_query:
        result['meta'] = {
            'grafana_url': url,
            'datasource_uid': uid,
            'query': query,
            'since': args.since,
            'direction': args.direction,
        }
    if args.stats:
        result['stats'] = payload.get('data', {}).get('stats', {}).get('summary', {})

    json.dump(result, sys.stdout, separators=(',', ':'))
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
