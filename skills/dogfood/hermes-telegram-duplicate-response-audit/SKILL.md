---
name: hermes-telegram-duplicate-response-audit
description: Audit and mitigate duplicate Telegram replies in Hermes gateway by checking process topology, polling/webhook mode, inbound replay, and outbound resend/idempotency behavior.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, telegram, gateway, debugging, idempotency, polling]
    related_skills: [systematic-debugging, hermes-agent-setup]
---

# Hermes Telegram duplicate-response audit

Use when Hermes appears to send the same Telegram reply multiple times.

## What this skill is for

This workflow is for the Hermes codebase itself, especially `gateway/platforms/telegram.py` and the systemd-managed gateway runtime.

It is optimized for the common real-world failure modes found during production-style audit:
1. inbound update replay during polling reconnect/restart
2. ambiguous outbound send timeout/retry causing the same final text to be sent twice
3. mistaken suspicion of two active gateway instances or polling/webhook conflicts
4. poor logs that make root cause impossible to prove
5. gateway process is alive but Telegram adapter is not actually enabled/connected due to config-source drift

## Fast triage order

### 1) Prove whether multiple runtimes actually exist
Do not assume “dua Hermes aktif” without checking.

Run process + systemd inspection first:
- inspect active `python -m hermes_cli.main gateway run --replace`
- inspect user service file `~/.config/systemd/user/hermes-gateway.service`
- inspect `systemctl --user status hermes-gateway.service`
- inspect process tree and listening ports

Useful commands:
- `ps -ef | grep 'hermes_cli.main gateway run' | grep -v grep`
- `pstree -ap <pid>`
- `systemctl --user status hermes-gateway.service --no-pager`
- `journalctl --user -u hermes-gateway.service --since '24 hours ago' --no-pager`
- `lsof -iTCP -sTCP:LISTEN -n -P`

Interpretation:
- one active gateway process + one user systemd service => duplicate replies are probably not from two live instances
- stop/start bursts around the incident window strongly increase probability of polling replay

### 2) Check polling vs webhook reality, not assumptions
Validate whether Hermes is actually in polling mode, webhook mode, or neither.

Look for:
- webhook config/env in service file or runtime config
- log messages mentioning webhook setup/remove
- Hermes-owned listeners on 8080/8443
- explicit Telegram startup logs like `Connected to Telegram (polling mode)`

Important lesson:
- open ports 8080/8443 are not evidence by themselves; confirm they belong to Hermes
- if no Hermes listener and service uses normal gateway run path, polling is the dominant path
- if the gateway process is healthy but there are zero Telegram startup/inbound/outbound logs even after real user messages, treat that as evidence that the Telegram adapter may not be enabled at all, not as proof that dedup is working

### 3) Audit log quality before trusting conclusions
If logs do not include update/message/send correlation fields, call that out explicitly.

Minimum forensic fields you want:
- inbound: update_id, chat_id, message_id, dedup hit/miss, reconnect reason
- outbound: chat_id, chunk index, attempt, dedup key/hash, returned message_id, timeout/success/failure

If current logs are weak, patch logging before overconfident blame assignment.

## Root-cause heuristic discovered from live audit

Use this priority order unless evidence disproves it:

1. Most likely: inbound replay after polling restart/reconnect
   - especially when service restarted recently
   - especially when inbound dedup does not exist yet

2. Next likely: outbound resend on ambiguous send failure
   - Telegram may have accepted the message but client times out or retries
   - if final text is identical, use an outbound idempotency guard

3. Less likely: two active gateways competing for token
   - verify, don’t guess

4. Secondary concern: config-source mismatch
   - `~/.hermes/config.yaml` may not fully explain runtime behavior
   - env/overlay/service-specific config may be the real source of truth

5. Newly confirmed failure mode: gateway alive, Telegram absent
   - service can be fully healthy under systemd while Telegram is functionally offline
   - signs: no `Connected to Telegram`, no inbound/outbound Telegram logs, and user test messages produce no journal evidence
   - in that situation, stop attributing behavior to dedup logic and pivot to config/runtime activation audit first

## Code-level mitigation pattern

### A. Inbound dedup for polling replay
In `gateway/platforms/telegram.py`:
- keep a short-lived cache of recent inbound message/update identities
- prune by monotonic time
- suppress exact duplicates within TTL
- log dedup hits with update_id/chat_id/message_id

Use when reconnect/restart may replay backlog.

### B. Outbound idempotency guard for final replies
In `gateway/platforms/telegram.py` send path:
- normalize content/chunks (collapse whitespace, trim)
- build a dedup key from:
  - `chat_id`
  - `reply_to`
  - `thread_id`
  - normalized chunks content
- hash the payload (sha256 works fine)
- cache recent outbound sends for 30–120s
- if the same dedup key reappears inside TTL:
  - log suppression
  - return success with previous `message_id`
  - annotate `raw_response` with `duplicate_suppressed=true`

Recommended env:
- `HERMES_TELEGRAM_OUTBOUND_IDEMPOTENCY_TTL_SECONDS=120`

### C. Forensic logging additions
Add logs at these points:
- send start: chat_id, reply_to, thread_id, chunk count, short dedup key, preview
- per send attempt: chunk x/y, attempt number, parse mode
- markdown fallback to plain text
- send success: returned message_id
- retry due to network error: wait duration + dedup key
- exhausted retries
- duplicate suppression: age + preview + dedup key
- send complete: message_ids + elapsed

This makes later incidents debuggable instead of mystical.

## TDD pattern that worked here

Before patching production logic:
1. extend existing Telegram adapter tests
2. add a failing test for duplicate outbound suppression within TTL
3. add a test that same content is allowed again after TTL expiry
4. run focused test file with project venv pytest, not system pytest
   - `./venv/bin/pytest -q tests/gateway/test_telegram_thread_fallback.py -q`

Important gotchas discovered:
- host may not have `pytest` globally installed; use `./venv/bin/pytest`
- if monkeypatching `time.monotonic`, provide enough values or a default fallback to avoid teardown `StopIteration`
- fake Telegram modules may leave `ParseMode` as `None`; tests can still pass via plain-text fallback, but log noise is expected unless the fake constant is set
- when testing Telegram media-group or photo-burst buffering, do not reuse the same `(chat.id, message_id)` for separate inbound events unless the test is explicitly about dedup; inbound duplicate protection will correctly drop the second event and make the batch look truncated
- for album/burst fixtures, keep `media_group_id` shared where needed but assign distinct `message_id` values per message (for example 42 and 43) so buffering behavior is tested instead of dedup behavior

## What to say in conclusions

When evidence matches the above pattern, report clearly:
- only one active gateway process was observed
- no evidence of Hermes webhook listener or simultaneous webhook+polling
- recent service restarts make polling replay plausible
- duplicate suppression now has two layers:
  - inbound dedup
  - outbound idempotency
- if duplicates still happen after both patches, next suspects are:
  - cross-process duplicate send with no shared state
  - non-identical duplicate outputs from separate execution paths

If live verification shows zero Telegram logs despite real test messages, report a different conclusion:
- the patch may be loaded, but Telegram itself is not proven active in this runtime
- the active systemd service may be missing Telegram config/token/enablement
- verification is blocked until Telegram activation is confirmed by startup and traffic logs

## Verification checklist

- [ ] confirmed actual number of gateway processes
- [ ] checked systemd service + ExecStart
- [ ] checked restart timing around incident window
- [ ] checked whether Hermes owns any webhook/listener ports
- [ ] confirmed current log quality and patched if needed
- [ ] added/verified inbound dedup if replay suspected
- [ ] added/verified outbound idempotency if resend suspected
- [ ] ran focused regression tests with `./venv/bin/pytest`
- [ ] documented new env knobs / expected log lines
