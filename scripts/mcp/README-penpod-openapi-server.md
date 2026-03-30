# Penpod OpenAPI MCP Server

Local stdio MCP server buat akses REST API Penpod dari Swagger/OpenAPI ini:
https://prd-srvc-penpod-ext.penpod.id/in/swagger/swagger.json

Server ini sengaja dibikin model hybrid yang waras, bukan 102 wrapper tool hardcoded yang bikin hidup ngenes tiap upstream berubah.
Jadi dia expose tool MCP berikut:

- `penpod_get_api_info` — metadata API/spec
- `penpod_list_tags` — daftar tag/group endpoint
- `penpod_list_operations` — cari/list operation dari spec
- `penpod_get_operation` — detail schema satu operation
- `penpod_call_operation` — executor generik buat call operation apa pun
- `penpod_get_deployment_spec` — helper spesifik buat `GET /ex/v1/deployment/{id}/spec`
- `penpod_get_latest_deployment_specs` — batch helper buat banyak deployment ID sekaligus
- `penpod_run_deployment_job` — helper spesifik buat `POST /ex/v1/job/run`
- `penpod_get_service_deployment_status` — helper spesifik buat `GET /ex/v1/service/deployment/{deployment_name}`
- `penpod_check_last_deployments` — batch helper buat cek status deployment name sekaligus
- `penpod_get_deployment_history` — list history by `deployment_id` + `job_id`
- `penpod_get_latest_deployment_history` — ambil history terbaru, opsional filter `tag`
- `penpod_run_deployment_job_and_wait` — trigger deploy lalu polling history sampai status terminal/timeout
- `penpod_build_service_logs_websocket_url` — bikin URL websocket siap pakai buat stream service pod logs
- `penpod_build_package_deployment_logs_websocket_url` — bikin URL websocket siap pakai buat package deployment logs
- `penpod_healthcheck` — smoke check spec + konektivitas

## Kenapa model begini?

Karena spec sekarang punya:
- 85 paths
- 102 operations
- Bearer auth di banyak endpoint

Kalau digenerate jadi 102 MCP tools terpisah, hasilnya:
- noisy
- maintenance makin ribet
- lebih gampang drift kalau swagger berubah

Dengan model ini, server tetap “komplit” karena semua operation tetap bisa dipanggil lewat `penpod_call_operation`, tapi masih enak dieksplor via `penpod_list_operations` dan `penpod_get_operation`.

## File

- Server: `scripts/mcp/penpod_openapi_server.py`

## Requirement

Pakai virtualenv repo ini:

```bash
source venv/bin/activate
```

Dependency yang dipakai:
- `mcp`
- `httpx`

Dua-duanya udah available di environment repo ini.

## Env yang didukung

- `PENPOD_OPENAPI_URL`
  - default: `https://prd-srvc-penpod-ext.penpod.id/in/swagger/swagger.json`
- `PENPOD_API_BASE_URL`
  - default: `https://prd-srvc-penpod-ext.penpod.id`
- `PENPOD_API_TIMEOUT_SECONDS`
  - default: `60`
- `PENPOD_API_VERIFY_SSL`
  - default: `true`
- `PENPOD_OPENAPI_FILE`
  - optional path ke spec JSON lokal, kalau mau avoid fetch remote tiap start
- `PENPOD_AUTH_GRANT_PATH`
  - default: `/ex/v1/auth/grant-client`
  - endpoint yang dipakai server buat auto-ambil bearer token kalau token explicit gak diset
- Auth explicit token, bisa salah satu:
  - `PENPOD_BEARER_TOKEN`
  - `PENPOD_API_TOKEN`
  - `PENPOD_TOKEN`
- Auth auto mode via kredensial, bisa salah satu untuk username + password:
  - username: `PENPOD_USERNAME` / `PENPOD_USER` / `PENPOD_EMAIL`
  - password: `PENPOD_PASSWORD` / `PENPOD_PASS`

Priority auth:
1. kalau ada `PENPOD_BEARER_TOKEN`/alias token lain, server pakai itu langsung
2. kalau gak ada token tapi ada username+password, server bakal coba auto-fetch bearer token via `POST /ex/v1/auth/grant-client`
3. kalau dua-duanya gak ada, request tetap jalan tanpa Authorization header

Catatan penting biar gak halu:
- dari Swagger yang exposed sekarang, endpoint `POST /ex/v1/auth/grant-client` tidak mendeklarasikan request body apa pun
- di pengujian live, endpoint itu tetap balikin bearer token walaupun body kosong atau body username/password diisi
- jadi username/password sekarang cuma dipakai sebagai trigger UX biar lu cukup isi `.env` dengan kredensial standar; upstream yang sekarang secara praktis tidak memvalidasi body login di endpoint grant tersebut
- kalau upstream nanti berubah dan mulai butuh payload auth tertentu, helper ini udah nyoba beberapa bentuk umum: `username`, `email`, `user`, dan `login`

## Jalanin self-test lokal

```bash
source venv/bin/activate
python scripts/mcp/penpod_openapi_server.py --self-test
```

## Jalanin sebagai MCP stdio server

```bash
source venv/bin/activate
python scripts/mcp/penpod_openapi_server.py
```

## Contoh config Hermes native MCP

Tambahin ke `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  penpod:
    command: python
    args:
      - scripts/mcp/penpod_openapi_server.py
    env:
      PENPOD_USERNAME: "username-lu"
      PENPOD_PASSWORD: "password-lu"
      PENPOD_API_BASE_URL: "https://prd-srvc-penpod-ext.penpod.id"
      PENPOD_OPENAPI_URL: "https://prd-srvc-penpod-ext.penpod.id/in/swagger/swagger.json"
    timeout: 120
    connect_timeout: 60
```

Kalau mau lebih aman soal path Python, bisa pakai executable venv langsung:

```yaml
mcp_servers:
  penpod:
    command: /home/gunamaya/.hermes/hermes-agent/venv/bin/python
    args:
      - /home/gunamaya/.hermes/hermes-agent/scripts/mcp/penpod_openapi_server.py
```

## Cara pakai dari agent

Flow yang masuk akal:

1. `penpod_list_operations(search="deployment")`
2. `penpod_get_operation(operation_id="...")`
3. `penpod_call_operation(..., dry_run=true)`
4. `penpod_call_operation(..., dry_run=false)`

## Contoh workflow

Cari endpoint database:

```text
penpod_list_operations(search="database")
```

Lihat detail salah satu operation:

```text
penpod_get_operation(operation_id="get_ex_v1_database")
```

Dry run request:

```text
penpod_call_operation(
  operation_id="get_ex_v1_database",
  query_params={"page": 1, "limit": 10},
  dry_run=true
)
```

Request beneran:

```text
penpod_call_operation(
  operation_id="get_ex_v1_database",
  query_params={"page": 1, "limit": 10}
)
```

## Catatan implementasi

- `operationId` upstream banyak yang kosong, jadi server bikin canonical `operation_id` sendiri dari method + path kalau perlu.
- Lookup operation support alias berdasarkan upstream operationId dan slug method/path.
- Validasi basic udah ada untuk:
  - path params
  - query params
  - header params yang dideclare di spec
  - request body required/object/array
- Return payload terstruktur, ada request preview + parsed JSON response kalau memungkinkan.

## Batasan sekarang

Ada beberapa hal yang sengaja belum sok pahlawan:

- belum auto-generate 1 tool per endpoint
- validasi schema body masih basic, belum deep object validation per property required
- formData / multipart Swagger 2 belum diprioritaskan
- auto-auth username/password sekarang bergantung ke perilaku endpoint grant upstream; Swagger-nya sendiri belum ngasih kontrak login yang jelas

Tapi untuk akses API secara komplit dan maintainable, ini udah cukup proper dan gak halu.
