# Hermes Mothership / Queen Ant Architecture Note

**Date:** 2026-05-08
**Status:** Draft discussion capture
**Source:** Telegram discussion with Albert about operating 5+ Hermes agents across different servers
**Working name:** Queen Ant / Hermes Mothership / Sentinel Control Plane

## Context

Albert has more than five Hermes agents running or planned across different servers. A simple `hermes profile` setup is not enough, because profiles only solve local multi-agent isolation inside one Hermes home / one machine. The actual problem is distributed: many servers, many Hermes instances, different credentials, different projects, different runtime access, different costs, and different risk levels.

The product shape discussed here is a **federated Hermes control plane**: one Mothership / Queen Ant instance that can discover, provision, supervise, route, budget, and govern worker Hermes agents across servers.

This is not intended to be a "supreme boss agent" that does all work or holds every secret. The healthy model is:

- Mothership = control plane, registry, scheduler, observer, policy engine, FinOps, incident commander.
- Worker agents = ants that execute bounded tasks on specific servers/projects with scoped permissions.
- Shared state = explicit registry + task board + telemetry + audit trail, not vibes in chat history.

## Problem Statement

When Hermes agents multiply across servers, manual coordination becomes fragile:

- The user becomes the human message broker.
- Different agents may duplicate work or edit overlapping scopes.
- Some agents can get stuck without visible heartbeat.
- Server inventory becomes stale.
- Agent/project ownership becomes implicit and easy to forget.
- Credentials and config drift across machines.
- Token usage and subscription costs become hard to attribute.
- High-risk operations such as Vault/env changes or production deploys need centralized policy.
- Evidence/proofs from workers are scattered across logs, chats, and local files.

The goal is to make distributed Hermes operations observable, governable, and routable.

## Core Product Thesis

**Hermes Mothership is a distributed AI agent operations platform.**

It should answer questions like:

- Which servers do I own?
- Which Hermes workers are alive?
- What can each worker do?
- Which project is each worker focused on?
- Which worker should handle this new task?
- Which task is stuck, blocked, duplicated, or completed without proof?
- Which worker is burning tokens/cost?
- Which provider/subscription is close to quota?
- Which operations require Albert approval?
- Which worker should be quarantined?
- How do we bootstrap a new worker on a server Albert just granted access to?

## Audit Response / Architecture Hardening Decisions

Two external technical audits were reviewed against this architecture. The useful verdict is not "kill Mothership". The useful verdict is: **do not build the overgrown version as written**. Keep the product thesis, but harden the MVP into a boring, deterministic, security-first control plane.

### Accepted Findings

These findings are accepted as architecture requirements, not optional polish:

1. **Mothership must not be a single point of operational paralysis.** Workers need a local degraded-autonomous fallback policy for safe actions when Mothership is unreachable.
2. **Mothership must not become the master skeleton key.** Secrets live in a dedicated backend. Mothership requests scoped sessions; it does not store raw master credentials.
3. **Bootstrap is remote code execution and must be treated as such.** No root-by-default bootstrap, no role assignment during bootstrap, no unverified scripts, and no trusting remote host facts blindly.
4. **Budget enforcement must happen before LLM calls.** Post-fact usage aggregation is too late for runaway agents.
5. **Task state must distinguish reversible and irreversible work.** Irreversible tasks must never auto-requeue on lease expiry.
6. **Audit logs must be append-only from day one.** A mutable table is not an audit trail. Worker self-reports are advisory unless validated.
7. **Crew taxonomy must be collapsed for MVP.** Specialist personas are useful, but starting with 25 active roles creates coordination theater.
8. **Bug bounty/revenue automation must be legally gated.** Scouting is safe; active third-party testing is never autonomous.
9. **Memory and project knowledge must be scope-tagged.** Cross-project context bleed is a real failure mode.
10. **Data lifecycle and compliance must be designed before telemetry spreads.** Append-only operational audit does not mean storing raw personal data forever. Personal/client/minor-related payloads need masking, retention classes, deletion propagation, and exportable evidence of deletion.
11. **Semantic retry loops are a Denial-of-Wallet vector.** HTTP retry limits are insufficient because agents can re-plan the same intent with different wording. The orchestrator needs intent-level circuit breakers and synchronous per-turn spend caps.
12. **Transport reliability is a real architectural risk.** SSH is acceptable for bootstrap/break-glass, but heartbeat/task flow must move to pull/webhook early, with a clear escalation path to buffered transport such as NATS JetStream if observed jitter/offline replay makes webhook insufficient.
13. **Telegram is a cockpit, not sole authority for dangerous mutation.** It can request/approve with guardrails, but high-risk changes need durable approval objects and optional second-channel confirmation.

### Modified / Rejected Findings

Some audit recommendations are directionally correct but too heavy for the first implementation:

- **NATS/gRPC from day one:** modified. Do not install a heavy event-bus stack before the read-only MVP exists, but also do not design around SSH polling. MVP 1 must use local SQLite + append-only JSONL + pull/webhook heartbeat as the normal path; SSH is bootstrap/break-glass/manual observer only. NATS JetStream or equivalent becomes mandatory once we observe sustained offline replay needs, false-positive dead-node alerts, or worker/event volume that webhook cannot handle.
- **SPIFFE/SPIRE from day one:** modified. Start with asymmetric worker identity, short-lived signed JWTs, jti revocation, and external secrets backend. Keep SPIFFE/SPIRE/Vault SVID as the target maturity path once the colony handles high-value secrets or many nodes.
- **Temporal/Rust typestate from day one:** modified. Implement explicit Python/SQLite state machines, idempotency keys, and tests first. Temporal/Saga orchestration becomes required for multi-step external side effects that cannot be safely modeled with a single local transaction and idempotency table.
- **Abolish Telegram entirely:** rejected. Telegram remains useful for Albert-facing UX, read-only status, and approval prompts. It must not be the only control for high-risk mutation.
- **Immutable logs everywhere:** modified. Security audit events should be append-only, but raw payloads that may contain personal/client data must be masked, referenced, retained by class, and deletable through a deterministic propagation mechanism.

### Non-Negotiable Hardening Gates

Do not start implementation of remote mutation until these exist:

- SQLite runtime state, not YAML runtime state. YAML may seed config only.
- External secrets backend selected and wired at least as a stubbed interface.
- Worker identity model: asymmetric keypair or short-lived signed token with revocation.
- Append-only audit JSONL with export path.
- Data classification, masking/redaction pipeline, retention classes, and deterministic delete propagation for payloads that may contain personal/client data.
- Pre-call budget ledger and delegation-subtree budget allocation.
- Semantic circuit breaker for repeated conceptual retries, plus hard per-turn spend caps.
- Task state machine with `execution_phase` and irreversible-action handling.
- Bootstrap approval object with out-of-band host fingerprint confirmation.
- Project knowledge scope tags and brief-time filtering.

### Revised Product Shape

Mothership should be a **secure briefing, registry, policy, budget, and evidence layer**. It may summon autonomous workers, but deterministic infrastructure invariants live in code/state machines, not in LLM vibes.

The ship metaphor remains useful, but the first ship should have seven crew roles and many optional specialist modes — not 25 independent agents arguing in a token bonfire.

## Vocabulary

- **Mothership / Queen Ant:** Central control plane instance.
- **Node:** A server or machine that can host one or more Hermes workers.
- **Worker / Ant:** A Hermes agent instance running on a node.
- **Project:** A durable work domain such as `centracast`, `centracast-runtime`, or `hermes-agent`.
- **Capability:** A declared ability/access pattern, e.g. Laravel, Grafana read, Penpod deploy, docs, GitHub review.
- **Trust tier:** Permission/risk category for a node or worker.
- **Focus:** The primary project or lane a worker should prioritize.
- **Heartbeat:** Periodic health/status report from node/worker to Mothership.
- **Run:** A concrete task execution attempt by a worker.
- **Proof artifact:** Evidence returned by a worker: logs, test output, commit hash, deployment ID, screenshots, route checks.
- **Quarantine:** State where a worker receives no new tasks because it is risky, unhealthy, looping, or misconfigured.

## High-Level Architecture

```text
                    Albert / Telegram / CLI / Web UI
                                  |
                                  v
                         Hermes Mothership
                 Queen / Sentinel / Control Plane
                                  |
       --------------------------------------------------------
       |                         |                            |
  Node A / Worker A         Node B / Worker B            Node C / Worker C
  centracast-dev            infra-watch                  docs/research
       |                         |                            |
  Laravel repos             Grafana/Penpod               docs/GitHub/web
  staging debug             logs/deploy                  planning/tracker
```

The Mothership should not require every worker to be on the same filesystem. It needs transport layers:

- SSH for bootstrap, health checks, and break-glass operations.
- Webhook/API for heartbeats and normal task/report flow.
- Shared board/event bus for durable task coordination.
- Optional remote command runner for controlled task execution.

## Major Capabilities

### 1. Cross-Server Node Registry

Mothership maintains an inventory of owned servers and worker agents.

Minimum fields:

```yaml
nodes:
  - id: centracast-dev-01
    hostname: vps-a
    address: 10.0.0.11
    owner: albert
    environment: staging
    transports: [ssh, webhook]
    status: healthy
    risk_level: medium
    roles: [backend, laravel, centracast]
    projects: [centracast, centracast-runtime]
    hermes_version: unknown
    last_seen: null
```

Longer-term data model should move from YAML to SQLite/Postgres:

- `nodes`
- `workers`
- `projects`
- `capabilities`
- `heartbeats`
- `tasks`
- `runs`
- `budgets`
- `provider_usage`
- `policies`
- `credentials_refs`
- `assignments`
- `incidents`
- `audit_events`

### 2. Bootstrap / Spawn Hermes to a New Server

Albert can give Mothership access to a new server, and Mothership should bootstrap a worker Hermes agent there.

Conceptual command:

```bash
hermes mothership node bootstrap-plan \
  --host provisioner@1.2.3.4 \
  --fingerprint SHA256:... \
  --name docs-ant-01 \
  --trust-tier quarantine

hermes mothership node bootstrap-apply PLAN_ID
hermes mothership worker assign-role docs-ant-01 --role scout --approve APPROVAL_ID
```

Expected bootstrap flow:

1. Validate SSH reachability using a dedicated provisioning user, not `root`.
2. Create an approval object containing host, expected fingerprint, planned commands, package source, requested trust tier, and rollback/finalizer notes.
3. Confirm host fingerprint out-of-band before any install command runs.
4. Treat all remote host facts as untrusted input; validate OS/arch/package-manager/Python/git/systemd outputs with strict allowlists/regex.
5. Generate the bootstrap script locally, compute SHA256, transfer it, and verify `sha256sum -c` remotely before execution.
6. Create/select a non-root `hermes` runtime user and use restricted sudoers only for approved install/service operations.
7. Install Hermes dependencies and Hermes Agent from a pinned source/checksum or signed release.
8. Generate worker identity as an asymmetric keypair or short-lived signed enrollment token; do not place long-lived master secrets on the node.
9. Register node with Mothership as `trust_tier: quarantine`.
10. Start heartbeat cron/service in read-only reporting mode.
11. Run smoke tests and independently verify installed version/binary hash from Mothership.
12. Store bootstrap audit events in append-only audit log.
13. Assign roles/toolsets only in a separate post-enrollment approval step.
14. Report exact installed version, path, config, status, trust tier, and next steps.

Security constraints:

- Do not blindly push master credentials to every worker.
- Mothership must call a dedicated secrets backend; it must not become the secrets backend.
- Prefer scoped, short-lived credentials and least-privilege API keys.
- Prefer non-root runtime and a restricted provisioning user.
- Pin SSH host fingerprints only after out-of-band confirmation.
- Record every bootstrap action in append-only audit log.
- Require approval before installing on unknown hosts if the plan includes privileged operations.
- New nodes start quarantined; role/toolset assignment is a separate approval-gated step.

### 3. Capability and Focus Management

Each worker should have a durable capability profile.

Example:

```yaml
workers:
  centracast-dev-01:
    capabilities:
      languages: [php, typescript, python]
      frameworks: [laravel, node]
      infra: [docker]
      repos:
        - /srv/centracast
        - /srv/centracast-runtime
      strengths:
        - staging-debug
        - backend-api
        - release-proof
      restrictions:
        - no-prod-deploy
        - no-vault-write-without-approval
```

Project focus can be assigned centrally:

```yaml
project_focus:
  centracast:
    primary_node: centracast-dev-01
    reviewer_node: reviewer-ant-01
    deploy_node: infra-watch-01
    docs_node: docs-ant-01

  hermes-agent:
    primary_node: hermes-core-01
    reviewer_node: reviewer-ant-01
    experiment_node: sandbox-ant-01
```

Mothership routing examples:

- Laravel backend bug -> `centracast-dev-01`
- Runtime proof -> `runtime-ant-01`
- Grafana/Loki staging logs -> `infra-watch-01`
- Roadmap/tracker docs -> `docs-ant-01`
- Security/code review -> `reviewer-ant-01`

### 4. Briefing, Summoning, and Delegated Orchestration

Important correction: Mothership should **not** be the default project decomposer for every project. A capable worker agent/profile can already orchestrate subagents locally once it receives a strong enough mission brief. Mothership's primary job is closer to what Albert does when briefing Hermes directly:

1. Understand the high-level intent.
2. Look up stored project knowledge, constraints, server inventory, budgets, and available idle workers.
3. Pick the best available autonomous orchestrator agent for the mission.
4. Build a complete, context-rich brief.
5. Summon/launch that worker with the brief.
6. Monitor progress, budget, risk, and proof quality.
7. Escalate only if the worker blocks, violates policy, exceeds budget, or needs Albert's decision.

In other words: **Mothership briefs and summons orchestrators; it does not micromanage every lane by default.**

Example project request:

> Setup agent yang tersedia / gak ada kerjaan buat kerjain project Pramana OS, ambil dari GitHub, target live 2 hari.

Expected Mothership behavior:

1. Check node/worker registry for idle or low-load agents.
2. Check which workers have the right capabilities: GitHub, Linux/server setup, app stack, deployment, testing, docs.
3. Check budget and token policy for a two-day live-target mission.
4. Look up any stored project knowledge for Pramana OS:
   - GitHub URL/repo ownership
   - known architecture or README summary
   - prior sessions or notes
   - deployment assumptions
   - target environment
   - known credentials or missing access references
5. If project knowledge is missing, perform a bounded discovery pass or ask Albert only for truly blocking facts.
6. Generate a full mission brief for the selected orchestrator worker.
7. Launch that worker on the chosen server.
8. Let the worker orchestrate its own local subagents/profiles as needed.
9. Receive progress reports, run summaries, artifacts, and final live proof.

The worker/orchestrator can then decide its own lanes, for example:

- repo discovery
- architecture read
- local setup
- dependency fix
- deployment plan
- smoke tests
- docs/readme updates
- live proof

Mothership should only override or split centrally when there is a cross-node reason:

- multiple specialized servers are needed
- credentials are separated across workers
- financial/trading and infra/deploy domains must remain isolated
- a worker is overloaded or unhealthy
- task risk requires an independent reviewer
- policy requires central approval
- the first orchestrator asks Mothership to summon additional workers

Routing should consider:

- project focus
- capability match
- current load / idle status
- health
- quota/budget
- trust tier
- required approvals
- repo ownership
- whether task is read-only or write/deploy
- whether a single autonomous orchestrator can own the mission end-to-end

### 4.1 Brief Contract

Mothership's most valuable output is a high-quality brief, not a hand-authored lane split.

A mission brief should include:

- **Mission:** what Albert wants in plain terms.
- **Target outcome:** e.g. "Pramana OS live in 2 days".
- **Selected worker:** who owns the mission.
- **Context bundle:** repo links, prior notes, known architecture, constraints, related docs.
- **Access bundle:** what server/repo/service access exists and what is missing.
- **Budget policy:** model tier, spending ceiling, escalation threshold.
- **Risk policy:** what is auto-allowed vs approval-gated.
- **Autonomy level:** whether the worker may spawn local subagents/profiles.
- **Reporting cadence:** heartbeat/progress summary frequency.
- **Definition of done:** exact live proof, URLs, tests, screenshots, commit hashes, deployment IDs.
- **Escalation rules:** when to ask Mothership/Albert.

Example brief skeleton:

```markdown
# Mission Brief: Pramana OS Live Target

Owner worker: pramana-builder-01
Deadline: 2 days
Autonomy: May spawn local subagents/profiles; may not modify billing/Vault/prod DNS without approval.
Budget: max $X/day, use cheap/medium models unless blocked.

Mission:
Bring Pramana OS from GitHub to a live, verifiable deployment.

Known context:
- GitHub repo: <url>
- Stored project notes: <links/summaries>
- Target server: <node or TBD>
- Known constraints: <...>

DoD:
- App live at URL
- Smoke tests pass
- Deployment steps documented
- Git commit/PR produced if repo changes are needed
- Final report includes costs, risks, and remaining gaps

Escalate if:
- Missing credentials/access
- DNS/billing/Vault/env/prod changes needed
- Daily budget > threshold
- Deadline becomes unrealistic
```

### 4.2 Worker Degraded-Autonomous Fallback

Workers must not freeze completely when Mothership is down. Each enrolled worker receives a local fallback policy and caches its last-known safe assignment/context.

Example `local_fallback_policy.yaml`:

```yaml
fallback_policy:
  mode: degraded_autonomous
  activate_if_mothership_unreachable_for_seconds: 300
  auto_allow:
    - read_logs
    - git_status
    - run_tests
    - safe_health_checks
    - collect_diagnostics
  auto_block:
    - vault_write
    - prod_deploy
    - billing_change
    - credential_rotation
    - third_party_security_testing
    - destructive_migration
  report_mode:
    while_offline: append_local_jsonl
    on_reconnect: replay_with_original_timestamps
```

Rules:

- fallback never grants new power; it only preserves explicitly safe read-only/reversible work.
- local logs are replayed to Mothership after reconnect and marked `source: offline_worker_replay`.
- any blocked action becomes `needs_mothership_or_albert_approval`.
- workers with active irreversible work continue only if the approval and idempotency key were already issued before disconnect; otherwise they stop and report.

This prevents the colony from becoming useless during Mothership downtime without turning every worker into a rogue mini-kingdom.

### 4.3 Domain Agents Can Report Upward

Mothership should also support specialist agents that own ongoing domains and report upward on demand.

Example finance request:

> Kondisi keuangan gimana, aman gak?

Preferred behavior:

1. Mothership does not manually inspect every exchange/wallet/VPS/provider if a finance agent already owns that domain.
2. Mothership asks the finance agent for a compact report or reads its latest signed/structured report.
3. Finance agent checks portfolio, balances, crypto/stocks, VPS spend, provider/token spend, subscriptions, runway, and anomalies.
4. Mothership composes the user-facing answer with risk flags and decisions needed.

This creates a hierarchy of responsibility:

- **Finance agent:** portfolio, balance sheet, subscriptions, VPS/token spend, trading/risk report.
- **Infra agent:** servers, uptime, disk, gateway/cron health.
- **Project orchestrator agents:** project delivery, local subagent decomposition, proofs.
- **Mothership:** registry, brief generation, summon/assign, policy, budget guardrails, final answer synthesis.

Mothership can answer simple questions directly from cached reports. It should only perform fresh deep checks when reports are stale, missing, suspicious, or the user asks for live verification.

### 4.4 Safe Task State Machine

Every mission/task must carry deterministic lifecycle fields. LLM agents may choose how to solve a task inside their lane, but they do not get to invent lifecycle transitions for side-effecting work.

Minimum task fields:

```yaml
task_id: pramana-live-001
status: claimed|running|blocked|done|failed|cancelled
execution_phase: claimed|in_progress_reversible|in_progress_irreversible|orphaned_needs_human_review|completed|failed
active_worker_id: pramana-builder-01
lease_expires_at: ...
idempotency_key: deploy:pramana-os:2026-05-08:abc123
requires_human_review_before_requeue: true
```

Rules:

1. All tasks start in `claimed` or `in_progress_reversible`.
2. Before any write/deploy/mutate action, the worker must atomically transition to `in_progress_irreversible`.
3. If lease expires while phase is `in_progress_irreversible`, Mothership must **not** auto-requeue. It transitions to `orphaned_needs_human_review` and opens an incident.
4. Requeue is only valid from `claimed` or `in_progress_reversible`.
5. Every external mutation must have an idempotency key. If the key is already `completed`, a retry reports success without repeating the action. If the key is `in_progress`, the new worker waits or escalates.
6. Side-effecting workflows should include compensating actions where practical, but rollback must be predefined; the LLM should not improvise rollback in panic mode.

This is the boring state-machine spine that keeps "summon autonomous worker" from becoming "double deploy because the Wi-Fi sneezed."

### 5. Heartbeat and Telemetry

Each node/worker should report compact status.

Example heartbeat:

```json
{
  "node_id": "centracast-dev-01",
  "host": "vps-a",
  "status": "healthy",
  "hermes_version": "0.x.x",
  "gateway": "running",
  "cron": "running",
  "active_tasks": 2,
  "repo_dirty_count": 1,
  "last_seen": "2026-05-08T04:00:00Z"
}
```

Health checks to track:

- SSH reachability
- heartbeat freshness
- Hermes version
- gateway status
- cron status
- dispatcher/kanban status
- provider auth status
- model availability
- disk/memory/CPU basics
- active/background runs
- dirty repos / unpushed commits
- failed cron jobs
- recent tool failures

### 6. Financial Ops / Token Usage / Subscription Tracking

Mothership should be the AI FinOps layer.

Track usage by:

- worker
- project
- provider
- model
- task/run
- day/month
- success vs failed/retried calls

Metrics:

- input tokens
- output tokens
- total tokens
- estimated cost
- request count
- retries
- errors
- average cost per completed task
- cost per project
- cost per worker
- provider quota/subscription status when available

Budget policy example:

```yaml
budgets:
  global:
    daily_usd: 20
    monthly_usd: 300
  projects:
    centracast:
      daily_usd: 8
      monthly_usd: 120
    hermes-agent:
      daily_usd: 5
      monthly_usd: 80
  nodes:
    docs-ant-01:
      daily_usd: 2
      allowed_model_tiers: [cheap, flash]
    reviewer-ant-01:
      daily_usd: 5
      allowed_model_tiers: [medium, strong]
```

Budget actions:

- 70% daily/monthly budget: warn.
- 90%: downgrade non-critical jobs to cheaper models.
- 100%: block non-critical jobs.
- Critical-only mode: allow health, incidents, and explicit Albert-approved tasks.

Budget enforcement must be pre-call, not post-fact. Each mission receives a shared budget envelope; parent agents allocate budget slices to child agents; every LLM/tool call that can incur provider cost reserves budget synchronously before execution.

Semantic circuit breaker requirements:

- Track `semantic_intent_hash`, not only exact URL/body/tool name.
- If the same conceptual action fails three times in one mission/turn window, return a hard `TOOL_UNAVAILABLE` / `CIRCUIT_OPEN` result instead of letting the agent rephrase and retry forever.
- Count repeated failures across tool variants when the desired state is equivalent, e.g. "deploy staging", "retry rollout", and "run deployment job again".
- Store breaker events in the audit log with mission, worker, tool, intent hash, failure class, cost already spent, and recommended human action.
- Provider/API-key hard spending limits remain the bottom circuit breaker, but Mothership should trip earlier before the bill turns into a clown mortgage.

Mothership should answer:

- Which worker was most expensive today?
- Which project burned the most tokens this month?
- Which task had runaway retries?
- Which provider is near quota?
- Which workers should be downgraded to cheap models?

### 7. Credential and Subscription Governance

Workers should not all receive the same all-powerful `.env`.

Policy example:

```yaml
credentials_policy:
  docs-ant-01:
    providers:
      openrouter:
        models: [cheap, flash]
      github:
        scopes: [repo-docs]
    denied:
      - penpod-write
      - vault-write

  infra-watch-01:
    allowed:
      - grafana-read
      - loki-read
      - penpod-read
    requires_approval:
      - penpod-deploy
      - vault-write
```

Preferred design:

- Mothership stores credential references/session IDs, not raw secrets.
- Workers receive scoped, short-lived tokens only.
- Vault/env writes always require Albert approval and before/after diff.
- Credential rotation and revocation are first-class operations.
- Provider subscription metadata is visible centrally.
- MVP identity can be asymmetric worker keys + signed JWTs with `jti` revocation; target maturity is SPIFFE/SPIRE or Vault SVID for high-value/many-node deployments.

### 8. Policy Engine and Approval Rules

Mothership should enforce approval policy consistently across workers.

Baseline policy:

```yaml
approval_rules:
  always_require:
    - vault_write
    - env_change
    - prod_deploy
    - billing_change
    - credential_rotation
    - delete_data
    - destructive_shell
    - public_post
    - merge_protected_branch

  require_diff:
    - config_change
    - dependency_upgrade
    - vault_or_env_change

  auto_allow:
    - read_logs
    - git_status
    - run_tests
    - docs_patch
    - create_tracker_task
    - read_only_health_check
```

Important Albert-specific policy:

- Penpod Vault/env changes must be confirmed first with a clear before/after diff.
- Do not silently update Vault.
- Deploy semantics must respect repo boundaries, especially CentraCast backend vs runtime.

### 9. Data Classification, Compliance, and Deletion Propagation

Mothership needs auditability without accidentally building a permanent personal-data landfill. Append-only audit is for operational evidence; it is not permission to retain raw prompts, customer records, private documents, or minor-related data forever.

Minimum data classes:

```yaml
data_classes:
  operational_metadata:
    examples: [task_id, worker_id, timestamps, status, cost, tool_name]
    retention: long
    append_only_ok: true
  proof_artifact_reference:
    examples: [commit_hash, pr_url, deployment_id, screenshot_path]
    retention: project_policy
    append_only_ok: true
  raw_payload:
    examples: [user_prompt, document_text, logs, copied database rows]
    retention: short_by_default
    append_only_ok: false
    require_masking_before_llm: true
  personal_or_client_data:
    examples: [email, phone, address, credentials, private customer data]
    retention: explicit_policy_only
    append_only_ok: false
    require_delete_propagation: true
  minor_related_data:
    examples: [child account data, school/parental context, age-indicating records]
    retention: avoid_unless_required
    append_only_ok: false
    require_strict_consent_and_delete_sla: true
```

Required primitives:

- `data_subject_id` / `tenant_id` / `project_id` tags where applicable.
- `payload_ref` instead of embedding raw payload inside audit rows.
- masking/redaction before LLM calls and before telemetry export.
- deletion request table with propagation status per worker/artifact store.
- worker-side delete receipt: `node_id`, `request_id`, `deleted_refs`, `completed_at`, `signature`.
- retention sweep that can prune raw payload caches while preserving non-personal operational audit events.

Indonesian PDP/GR compliance note:

- Treat Indonesian PDP-style deletion/consent-withdrawal SLA as a design constraint when handling personal data, especially anything related to minors or client/customer records.
- MVP should avoid ingesting such data into Mothership unless the data lifecycle path already exists.
- If a workflow requires personal data, the approval object must state data class, retention, masking, deletion path, and whether data leaves the sovereign/private network.

This keeps evidence useful without creating a legally radioactive JSONL museum. Very Web3 of us if we ignored it; therefore, we do not.

### 10. Trust Tiers and Quarantine

Trust tier example:

```yaml
trust_tiers:
  sandbox:
    can_read: limited
    can_write: temp_only
    can_deploy: false
  dev:
    can_write_repos: true
    can_push_fork: true
    can_deploy_staging: requires_approval
  ops:
    can_read_infra: true
    can_restart_services: requires_approval
    can_write_vault: never_without_albert
  prod:
    can_touch_prod: explicit_one_time_approval_only
```

Quarantine triggers:

- no heartbeat for threshold
- repeated task failures
- abnormal token spend
- suspected loop
- wrong repo edits
- risky command attempts
- provider auth errors causing repeated retries
- worker completed task without proof multiple times

Quarantine behavior:

- no new assignments
- allow read-only health/reporting
- preserve logs and run history
- notify Albert with recommended recovery

### 11. Incident Management

Mothership detects and summarizes incidents.

Incident examples:

- gateway down
- cron dead
- worker no heartbeat
- provider quota exhausted
- repeated tool failure
- disk full
- CI red after push
- staging deploy queued too long
- duplicate agents editing same repo/branch
- unpushed commits too old
- production/Vault approval pending

Example alert:

```text
🚨 Incident: infra-watch-01 degraded

- Last heartbeat: 47m ago
- Gateway: down
- Cron: unknown
- Last task: staging log audit
- Suggested action: restart gateway via SSH
- Risk: low
- Approval needed: no
```

Alert policy should avoid spam:

- immediate alerts only for critical/degraded/risky conditions
- daily digest for normal status
- silence if all green unless configured otherwise

### 12. Shared Task Board / Event Bus

Multi-server workers need a real source of truth.

Possible phases:

- MVP: Mothership local SQLite + append-only JSONL + pull/webhook heartbeat/task/report.
- SSH: bootstrap, break-glass, manual observer health sweep only; not the normal heartbeat loop.
- Buffered transport escalation: NATS JetStream/Redis/Postgres queue when webhook/pull shows false dead-node alerts, offline replay gaps, or volume pain.
- Hermes-native future: remote-capable Hermes Kanban API layered on the same task/audit semantics.

Useful endpoints:

- `POST /nodes/register`
- `POST /nodes/heartbeat`
- `GET /tasks/claim`
- `POST /tasks/update`
- `POST /runs/report`
- `POST /usage/report`
- `POST /incidents/report`

### 13. Artifact and Proof Store

Workers should return proof, not only final prose.

Store/index:

- commit hashes
- branch names
- PR URLs
- test output
- logs
- screenshots
- deployment IDs
- API route verification
- Grafana/Loki query snippets
- config diffs
- generated docs

Proof should be tied to:

- task ID
- run ID
- worker ID
- project
- timestamp
- approval ID if applicable

### 14. Memory, Skill, and Config Federation

Do not merge all worker memory raw. That causes cross-project contamination.

Preferred model:

- Worker keeps local/project memory.
- Mothership keeps curated summaries:
  - node capabilities
  - project ownership
  - recurring failures
  - stable conventions
  - routing preferences
- Cross-node learning happens via reviewed summaries or skills, not transcript soup.

Skill distribution features:

- list skill versions per worker
- roll out selected skills to selected workers
- detect stale/missing skills
- pin critical skills
- avoid auto-updating risky operational skills without review

Config drift detection:

- Hermes version
- enabled toolsets
- model/provider
- MCP servers
- gateway platforms
- cron jobs
- approval mode
- secret redaction/privacy settings

### 15. UI and Command Surface

CLI examples:

```bash
hermes mothership status
hermes mothership nodes list
hermes mothership nodes show centracast-dev-01
hermes mothership nodes bootstrap-plan provisioner@1.2.3.4 --fingerprint SHA256:...
hermes mothership focus set centracast --primary centracast-dev-01
hermes mothership tasks list
hermes mothership assign TASK_ID --node docs-ant-01
hermes mothership budget status
hermes mothership incidents list
hermes mothership quarantine runtime-ant-02
```

Telegram examples:

```text
/mothership status
/mothership nodes
/mothership budget
/mothership incidents
/mothership assign
```

Digest example:

```text
🐜 Colony Brief

Healthy:
- centracast-dev-01
- docs-ant-01
- reviewer-ant-01

Degraded:
- infra-watch-01: no heartbeat 42m

Active work:
- CentraCast AF cleanup: 2 active tasks
- Hermes OMO roadmap: docs done, implementation pending

Cost:
- Today: $3.84 / $20
- Month: $47.21 / $300

Needs Albert:
- Vault env diff pending approval for staging deploy
```


## Expanded Possibility Map

This section broadens the product surface beyond the first Mothership sketch. These are not all MVP items. They are planning inventory: things that are possible, useful, and realizable if the system grows from a single-server Hermes assistant into a distributed agent colony.

Reference families used for this expansion — **translated into implementable Hermes primitives, not copied wholesale**:

The earlier list can sound like enterprise soup. The rule is: borrow the smallest useful idea, then implement it in boring SQLite/YAML/CLI first. Do not import the whole circus unless the colony actually earns it.

| Reference family | Concrete thing to steal for Hermes | MVP implementation | Do **not** build yet |
|---|---|---|---|
| Kubernetes controllers/operators | desired state vs observed state, reconcile loop, safe removal | SQLite registry + heartbeat rows + one cron that flags drift | CRDs, admission webhooks, real cluster semantics |
| Terraform/Ansible | plan/apply preview, idempotent bootstrap | `mothership plan` writes a JSON diff; `apply` runs approved SSH steps | full IaC engine |
| GitHub Actions runners | labels, runner pools, task lease/requeue | worker labels + `mission_lease_expires_at` | hosted runner marketplace clone |
| FleetDM/MDM | enrollment token, device facts, compliance labels | invite token + `worker_facts` table | full device management product |
| OpenTelemetry/LangSmith | trace id, spans, replayable evidence | append-only JSONL `events` table/file per mission | distributed tracing stack on day one |
| AutoGen/CrewAI/LangGraph | specialist handoff, council/debate, local orchestration | structured `handoff_report` and bounded council vote | free-form agent group chats |
| Temporal/Prefect/Airflow | durable workflow state and retry | SQLite state machine: `intake -> brief -> launch -> report -> verify` | running Temporal cluster |
| FinOps/AWS Budgets | spend attribution and budget gates | per-mission token/cost ledger + Telegram warning | enterprise chargeback bureaucracy |
| OPA/Vault/STS/CloudTrail | policy decision, short-lived credentials, audit trail | Python/YAML policy rules + approval object + audit log | complex policy language migration |
| SRE/incident tooling | dedup incidents, kill switch, runbooks | `incidents` table + `/mothership kill worker_id` | PagerDuty clone |

Implementation sanity filter:

1. If it cannot be represented as a YAML file, SQLite row, JSONL event, or CLI command in MVP, it is probably overdesigned.
2. If Albert cannot understand what it does from one Telegram summary, rename or cut it.
3. If it does not help one of these jobs — summon, guard, report, earn, expand, recover — it is not core Mothership.
4. The colony should start as a **useful ship**, not a space bureaucracy with a logo and no engine.

### A. Control Plane Concepts

#### Desired State vs Observed State

Mothership should not only run one-off commands. It should keep desired state and continuously compare it with observed state.

Desired state examples:

```yaml
nodes:
  pramana-builder-01:
    desired_status: enrolled
    hermes_version: ">=0.x"
    enabled_roles: [project-orchestrator, deploy-staging]
    allowed_projects: [pramana-os]
    heartbeat_ttl_seconds: 120

projects:
  pramana-os:
    target: live-in-2-days
    primary_worker: pramana-builder-01
    budget_daily_usd: 10
    required_proofs: [live_url, smoke_test, deploy_doc]
```

Observed state examples:

- node reachable/unreachable
- actual Hermes version
- actual toolsets enabled
- current tasks/runs
- latest heartbeat
- disk/memory health
- repo dirty/unpushed state
- active credentials/leases
- daily token spend

Reconciliation behavior:

- install/update worker if version drift is detected
- mark worker degraded if heartbeat expires
- requeue task if lease expires
- quarantine worker if risk signals repeat
- revoke credentials when worker retires
- open incident if desired state cannot be achieved

Pitfall:

- Reconciliation can create loops/storms if actions are not idempotent. Every mutating action needs idempotency keys, leases, and retry budgets.

#### Declarative Plan / Apply

For dangerous or large changes, Mothership should support a Terraform-like plan/apply model.

Examples:

```bash
hermes mothership plan node bootstrap provisioner@1.2.3.4 --fingerprint SHA256:... --trust-tier quarantine
hermes mothership apply PLAN_ID
```

Plan output should show:

- nodes affected
- credentials requested
- packages installed
- services created/restarted
- policies changed
- cost/budget impact
- rollback path
- approval required or not

Useful for:

- bootstrap new server
- rotate credentials
- rollout policy/toolset changes
- upgrade Hermes workers
- migrate project focus
- enable finance/trading agent permissions

Pitfall:

- Plans can go stale. Apply must verify version/fingerprint/desired-state preconditions before executing.

#### Finalizers and Safe Removal

Before deleting a node/worker/project from the registry, Mothership should run finalizers:

- drain active tasks
- collect final logs/artifacts
- revoke node token
- revoke credential leases
- stop heartbeat service
- remove runner registration
- archive project state
- write audit event

If finalizer fails, the node enters `terminating_blocked`, not silently deleted.

### B. Worker and Node Lifecycle

#### Enrollment / Invite Flow

A new node joins with a short-lived invite token.

Flow:

1. Mothership creates invite.
2. Albert runs bootstrap command on target server or gives SSH access for Mothership to run it.
3. Node presents invite token + host facts.
4. Mothership verifies host fingerprint and policy.
5. Mothership approves enrollment.
6. Node receives scoped config and starts heartbeat.

Node identity should include:

- node ID
- host fingerprint
- public key or workload identity
- enrollment time
- approved_by
- trust tier
- allowed projects/roles

#### Persistent vs Ephemeral Workers

Persistent workers:

- good for known projects and long-running ownership
- keep local repo cache and project memory
- can run cron/reporting

Ephemeral workers:

- good for risky, one-off, untrusted, or high-isolation tasks
- spawned per task then destroyed
- useful for dependency-heavy experiments or third-party repo triage
- avoids long-term secret/config drift

Possible lifecycle:

```text
requested -> provisioning -> ready -> assigned -> running -> uploading_artifacts -> draining -> destroyed
```

Pitfall:

- Ephemeral workers need warm pools or bootstrap latency will annoy everyone and their goat.

#### Capability Attestation

Worker labels should not be trusted just because the worker says so.

Attested capability examples:

- `has_docker`: verified by command probe
- `can_push_github`: verified by token scope probe
- `can_read_grafana`: verified by read-only API call
- `can_deploy_staging`: verified by policy + dry-run deploy check
- `has_gpu`: verified from hardware facts
- `trusted_prod`: assigned by Albert/policy, never self-reported

Use labels for routing, but derive them from facts/policy where possible.

### C. Scheduling and Assignment

#### Agent Pools

Group workers into pools:

- `personal`: direct Albert assistants
- `project-orchestrators`: can own full project missions
- `coding`: code changes/tests
- `review`: diff review/security/risk
- `ops`: infra/logs/deploy
- `finance`: portfolio/budget/subscription/trading analysis
- `research`: web/docs/market/public data
- `sandbox`: untrusted experiments
- `prod`: rare, heavily gated production access

Routing should use:

- pool
- labels/capabilities
- health
- current load
- budget remaining
- trust tier
- project focus
- required data access
- locality/server placement

#### Task Lease and Requeue

Every assignment should have a lease:

```yaml
assignment:
  task_id: pramana-live-001
  worker_id: pramana-builder-01
  lease_expires_at: ...
  heartbeat_interval: 60s
  idempotency_key: pramana-live-001:v1
```

If worker does not pick up or heartbeat:

- mark run `lost`
- collect partial artifact if possible
- requeue task if safe
- require human review if task has side effects

#### Recursion and Delegation Budget

Because workers can orchestrate their own subagents, Mothership needs colony-wide recursion controls:

- max child agents per mission
- max depth of delegation
- max spend per mission
- max wall time
- max concurrent write workers per repo/branch
- required worktree isolation for parallel code writers

Default rule:

- Worker may summon local subagents only within its mission budget and trust tier.
- Cross-server summons go through Mothership.
- High-risk domains require approval.

### D. Project Knowledge and Briefing System

#### Scoped Knowledge and Provenance

Every reusable piece of Mothership knowledge must carry scope metadata. The brief generator must filter by scope before injecting context into any worker.

Example:

```yaml
knowledge_item:
  id: conv_001
  content: "Penpod deploys for CentraCast require before/after Vault env diff approval."
  scope_type: project_specific
  projects: [centracast, centracast-runtime]
  not_applicable_to: [pramana-os, hermes-agent]
  source: session:...
  reviewed_by: albert
  reviewed_at: 2026-05-08
  confidence: 0.95
```

Allowed scope types:

- `global`: safe everywhere, e.g. "run tests before deploy".
- `user_preference`: Albert's stable preferences.
- `project_specific`: only injected for matching projects.
- `environment_specific`: tied to staging/prod/local/server identity.
- `temporary`: never injected into future mission briefs unless promoted.

This prevents CentraCast-specific deployment lore from leaking into Pramana OS and quietly summoning the wrong demon.

#### Project Memory Packs

Mothership should maintain a project pack for each durable project.

Example:

```yaml
project_id: pramana-os
repo_url: https://github.com/...
owners: [albert]
primary_worker: pramana-builder-01
known_stack: [node, docker, postgres]
target_environments:
  staging: ...
  live: ...
known_constraints:
  - target live in 2 days
  - no paid infra changes without approval
proof_requirements:
  - live URL
  - smoke test output
  - deployment doc
memory_refs:
  - session:...
  - docs/plans/...
```

A project pack should be composed into mission briefs.

#### Brief Quality Gate

Before launching a worker, Mothership should grade its own brief:

- Is mission clear?
- Is owner selected?
- Is repo/server context present?
- Is budget defined?
- Are approvals clear?
- Is definition of done measurable?
- Are reporting expectations clear?
- Are unknowns labeled?

If the brief fails, Mothership should do bounded discovery or ask Albert targeted questions.

#### Mission Types

Useful mission templates:

- `project-live-target`: bring repo/app live by deadline
- `bugfix`: reproduce, patch, test, PR
- `research-brief`: gather sources, summarize, recommend
- `staging-proof`: verify real runtime/API path
- `ops-incident`: diagnose and mitigate service issue
- `finance-health`: portfolio/spend/runway report
- `security-review`: audit repo/config/secrets posture
- `content-production`: draft/publish gated content
- `migration`: move service/server/config safely
- `cleanup`: archive/decommission/rotate/remove safely

Each template has a different brief contract and approval policy.

### E. Multi-Agent Patterns

#### Agents-as-Tools

For predictable delegation, Mothership can expose specialist workers as tools:

```text
finance_report(scope, freshness) -> structured report
infra_health(nodes) -> health summary
project_launch(project_id, target, deadline) -> mission run id
security_review(target, mode) -> findings
```

This is safer than open-ended group chat because outputs are structured and easier to audit.

#### Handoff

If a request enters the wrong domain, Mothership can hand off ownership:

- finance question -> finance agent
- deployment issue -> ops agent
- code implementation -> project orchestrator
- security concern -> security reviewer

Handoff should carry:

- user intent
- context bundle
- authority/limits
- requested output schema
- deadline
- budget
- approval rules

#### Group Review / Debate Mode

Use sparingly for high-stakes decisions:

- architecture choice
- trading strategy review
- security incident assessment
- launch readiness

Pattern:

- 2–4 specialist opinions
- one integrator summary
- hard max rounds
- structured final decision

Pitfall:

- Group chat can burn tokens like a teenager with their parent's credit card.

#### Durable State Graph

For serious workflows, use graph/state machine:

```text
intake -> enrich_context -> select_worker -> brief -> launch -> monitor -> approval_gate? -> verify -> summarize -> archive
```

Use checkpointing so restart does not lose state.

### F. Human Approval and Governance

#### First-Class Approval Object

Approval should be a durable object, not a casual prompt.

```yaml
approval_id: appr_123
requested_by: mothership
human_approver: albert
action_type: vault_env_change
target: centracast-staging
risk_tier: high
preview_diff: ...
estimated_cost_usd: 0
expires_at: ...
status: pending
```

Actions:

- approve
- reject
- approve once
- approve with edits
- request more info
- expire

#### Policy-as-Code

Use OPA-style policy decisions:

Input:

```json
{
  "agent_id": "ops-ant-01",
  "project_id": "centracast",
  "action": "penpod_vault_write",
  "environment": "staging",
  "estimated_cost_usd": 0,
  "risk_tier": "high"
}
```

Output:

```json
{
  "allow": false,
  "requires_approval": true,
  "required_preview": "before_after_diff",
  "audit_level": "high"
}
```

Albert-specific hard rule:

- Penpod Vault/env changes require explicit confirmation with before/after diff. No silent Vault updates. Jangan jadi ninja env goblok.

#### Break-Glass Mode

For emergencies:

- short TTL
- strong justification required
- all actions high-audit
- automatic post-incident review
- automatic credential revocation after expiry

### G. FinOps and Resource Economics

#### Token and Cost Ledger

Every LLM call/run should be attributable.

Dimensions:

- human requester
- project
- mission
- task
- worker
- provider
- model
- toolset
- approval ID
- cost center

Track:

- prompt tokens
- completion tokens
- cached tokens
- retries
- failed calls
- tool/API costs
- VPS/server cost allocation
- subscription cost allocation
- artifact/storage cost

#### Budget Enforcement Modes

- `observe`: track only
- `warn`: alert at threshold
- `degrade`: switch to cheaper model/tool strategy
- `queue`: delay non-urgent tasks
- `block`: refuse non-critical work
- `approval`: ask Albert to exceed budget

#### Finance Agent Integration

Finance agent can own:

- crypto/stocks portfolio
- cash/bank/exchange balances where integrations exist
- VPS/provider subscriptions
- token/API usage
- runway
- planned spend
- anomaly detection
- trading/risk notes

Mothership composes finance answers from:

- latest finance report
- fresh finance agent query if stale
- Mothership's own token/VPS/subscription ledger
- explicit uncertainty labels

### H. Credentials and Secrets

#### Credential Broker

Mothership should not paste secrets into prompts. It also should not be the master secrets store. It should call a dedicated secrets backend (Vault, Bitwarden Secrets Manager, Infisical, or an adapter with equivalent separation) and receive scoped, short-lived sessions.

Credential broker responsibilities:

- issue short-lived scoped credentials
- attach credential session to task/run
- revoke on task completion/cancel/quarantine
- log source identity
- enforce policy

Credential types:

- GitHub token/session
- cloud provider credentials
- Vault dynamic secrets
- exchange read-only/trading API keys
- VPS provider tokens
- Grafana/Loki tokens
- SSH certificates

#### Secret Access Modes

- `none`: no secrets
- `read-only`: can inspect/report
- `write-scoped`: can modify bounded resources
- `deploy-scoped`: can deploy specific service/env
- `trading-scoped`: can trade within strategy/risk limits
- `break-glass`: temporary high-risk emergency access

### I. Observability and Audit

#### Trace Model

Trace hierarchy:

```text
user_request
  -> mothership_intake
  -> context_enrichment
  -> policy_decision
  -> worker_selection
  -> mission_brief
  -> remote_run
      -> worker_subtask
          -> tool_call
  -> proof_verification
  -> final_response
```

Every span/event should carry:

- trace_id
- mission_id
- task_id
- worker_id
- project_id
- model/provider
- policy version
- approval_id
- cost estimate/actual

#### Audit Event Classes

- `node.enrolled`
- `node.heartbeat_missed`
- `worker.assigned`
- `mission.brief_created`
- `run.started`
- `tool.called`
- `policy.denied`
- `approval.requested`
- `credential.issued`
- `credential.revoked`
- `budget.threshold_crossed`
- `incident.opened`
- `worker.quarantined`
- `proof.accepted`
- `proof.rejected`

#### Tamper-Evident Logs

Advanced option:

- hash-chain audit batches
- sign daily audit bundle
- store in append-only bucket/repo
- useful if agents can touch money, infra, or trading

### J. Incident Response and Safety

#### Incident Types

- runaway cost
- agent loop
- no heartbeat
- suspicious command
- credential leak suspicion
- policy bypass attempt
- wrong repo edits
- deploy failure
- trading anomaly
- finance drawdown threshold
- disk full / server pressure
- token quota exhausted

#### Kill Switches

Mothership should be able to freeze:

- one worker
- one node
- one project
- one toolset
- one provider/model
- one credential broker integration
- all trading actions
- all deploy actions
- all non-read-only actions

Kill switch should be immediate, audited, and reversible only with approval.

#### Runbook Library

Runbooks:

- gateway down
- cron stuck
- no heartbeat
- provider quota exhausted
- runaway token spend
- Vault/env approval pending
- worker wrong repo
- unpushed commits on dead node
- trading bot anomaly
- production deploy failed
- policy bundle rollback
- credential revocation

### K. MVP Crew Model: Seven Operational Roles

For implementation, collapse the ship into seven operational roles. The detailed ship-crew taxonomy remains useful as an appendix-style possibility map, but **MVP scheduling and permissions should use these seven roles only**.

| MVP role | Absorbs / specialist modes | Default power | Notes |
|---|---|---|---|
| Orchestrator | Project Orchestrator, Code Architect, Chief of Staff | Owns mission brief and local decomposition | One orchestrator per mission by default. |
| Builder | Code Worker, Data/Analytics | Code/docs/test changes within repo scope | Requires worktree isolation for parallel writes. |
| Reviewer | Reviewer, Security Guard, Risk/Compliance | Read-only review and block recommendation | Security Guard is a mode first, not separate worker by default. |
| Ops | DevOps, Provisioner, Infra | Deploy/log/server work | High approval requirements. Bootstrap starts quarantined. |
| Finance | Finance, read-only Trading, Procurement | Reports budgets/runway/spend | Mutating purchases/trades require approval. |
| Scout | Research, Revenue Scout, Content/Comms | Read/search/summarize/draft | Bug bounty scout is read-only by default. |
| Auditor | Auditor, Librarian, Skillsmith | Evidence, memory scope, skills proposals | Writes append-only audit/provenance; curates knowledge. |

Rules:

- Council is a **process**, not a permanent crew swarm. Use it only for irreversible/high-risk go/no-go decisions.
- Expansion Agent is not an autonomous buyer/provisioner in MVP. Expansion is a proposal mode under Auditor/Ops until the colony has stable operating history.
- Specialist personas may exist as prompt/skill modes under these seven roles, but they should not create separate scheduling/permission surfaces until there is repeated evidence they are needed.
- For small missions, prefer one Orchestrator plus optional Reviewer/Ops over a ten-agent ceremony. Jangan bikin rapat kabinet buat deploy side project.

### K. Domain Agent Families / Ship Crew

Mothership should think less like a random bag of workers and more like a ship/colony crew. Every specialist agent has:

- a **domain** it owns,
- a **permission envelope**,
- a **report schema**,
- an **escalation rule**,
- and a **money/cost posture**: cost center, savings center, or revenue center.

#### Command Crew

##### Captain / Mothership

Receives Albert's high-level brief, turns it into a mission-grade brief, selects crew, enforces policy, monitors proof, and synthesizes final answers. It does not micromanage the worker's local decomposition.

##### Council Agent / War Room

A bounded decision council for important ship decisions: architecture direction, launch readiness, large spend, risky automation, trading strategy, or security incidents.

Council is not a permanent group chat swamp. It is a structured ritual:

1. Mothership frames the decision and constraints.
2. 3-5 relevant specialists submit independent memos.
3. Council agent identifies agreement, disagreement, risk, missing evidence.
4. Mothership gives Albert a final recommendation with dissent notes.

Default council seats by topic:

- architecture decision: project orchestrator + code architect + security guard + infra + finance if cost relevant
- launch readiness: project orchestrator + reviewer + infra + security guard
- new revenue plan: finance + growth + legal/compliance + security guard + operator
- trading/portfolio: finance + trading + risk guard + market research

Hard limits:

- max council members: 5 by default
- max rounds: 1-2
- output must be a decision memo, not vibes soup
- Albert approval required for irreversible decisions

##### Chief of Staff / Mission Planner

Keeps the mission calendar, active commitments, deadlines, dependencies, and follow-up queue. Useful when many projects run in parallel and Albert asks, "hari ini kapal ngapain aja?"

#### Guard Rails / Safety Crew

##### Security Guard Agent

Dedicated guard, separate from generic reviewer. It protects the ship itself.

Responsibilities:

- watch for secret leaks, dangerous commands, suspicious diffs, dependency risk
- inspect permission creep across agents
- validate that workers are using scoped credentials
- review bootstrap scripts and remote execution plans
- enforce kill-switch recommendations
- maintain threat model and security checklist

Default mode: read-only and advisory.

Authority:

- can recommend quarantine
- can block automatic execution by policy signal
- cannot silently rotate/delete secrets without approval

##### Risk / Compliance Agent

Checks whether a plan violates explicit rules, platform terms, bug bounty scopes, trading limits, privacy boundaries, or legal-ish constraints. This is especially important for revenue agents like bug hunting and scraping/research agents.

##### Auditor / Black Box Agent

Maintains tamper-resistant mission logs, proof artifacts, and post-run summaries. Answers: "who did what, with what approval, using what credential, and what proof came back?"

#### Build / Delivery Crew

##### Project Orchestrator Agent

Owns a project mission end-to-end. Can spawn local subagents if allowed. This is the worker that receives a full mission brief such as "Pramana OS live in 2 days" and does local decomposition.

##### Code Worker Agent

Implements scoped changes. Requires worktree isolation for parallel writers.

##### Code Architect Agent

Designs interfaces, migration paths, module boundaries, and implementation sequencing. Should be used before letting multiple code workers stampede into the same repo like caffeinated goats.

##### Reviewer Agent

Reviews diffs, tests, docs, regressions, maintainability, and acceptance proof. Separate from Security Guard: reviewer cares whether the work is correct; Security Guard cares whether the ship survives.

##### QA / Proof Agent

Runs smoke tests, browser checks, API checks, route verification, screenshots, and regression scripts. Produces proof packages.

##### DevOps Agent

Owns deployment, logs, server health, Grafana/Loki/Penpod, DNS, SSL, backups, and rollback playbooks. Higher approval requirements.

##### Data / Analytics Agent

Owns dashboards, event schemas, product metrics, attribution, pipeline checks, and data quality.

#### Ship Expansion / Colony Growth Crew

##### Expansion Agent / Recruiter Agent

Grows the ship's capacity. This is the missing piece if the colony should become more autonomous.

Responsibilities:

- find underused servers or cheap new VPS options
- propose new worker roles based on backlog bottlenecks
- generate bootstrap plans for new agents
- maintain worker templates and profile presets
- evaluate whether to create persistent or ephemeral workers
- detect capability gaps: "we need a security guard", "we need a QA/proof runner", etc.

Guardrails:

- cannot purchase servers without approval
- cannot grant broad credentials by itself
- can propose, plan, and prepare; Mothership/Albert approves expansion

##### Provisioner Agent

Executes approved bootstrap plans: install Hermes, configure profile, enroll worker, start heartbeat, run smoke checks. It should be boring, idempotent, and heavily audited.

##### Skillsmith / Training Agent

Turns repeated successful procedures into Hermes skills, patches stale skills, maintains agent templates, and keeps project packs fresh. This is how the colony learns without dumping everything into fragile chat memory.

##### Librarian / Memory Curator Agent

Curates project packs, decisions, runbooks, architecture docs, postmortems, and source-of-truth links. Separates durable knowledge from temporary task chatter.

#### Money / Growth Crew

##### Finance Agent

Owns balance sheet, portfolio, subscriptions, token/VPS spend, runway, and risk reporting.

##### Trading Agent

If ever enabled, must be separate from finance reporting. Trading actions need strict risk policy, position limits, kill switch, and audit. Default should be paper-trading/read-only until proven.

##### Revenue Scout Agent

Finds legal, realistic revenue opportunities beyond crypto. It does not execute risky work automatically; it scouts, ranks, and briefs.

Opportunity types:

- bug bounty programs and responsible disclosure opportunities
- small freelance gigs matching existing code/ops skills
- grants, hackathons, bounties, OSS sponsorships
- domain/content/product opportunities
- marketplace tasks that can be automated safely
- cost-saving opportunities that are effectively "found money"

Output schema:

```yaml
opportunity_id: rev_...
type: bug_bounty|freelance|grant|hackathon|cost_saving|product
expected_value_usd: ...
time_estimate_hours: ...
risk_level: low|medium|high
required_capabilities: [...]
requires_account_or_kyc: true|false
terms_or_scope_url: ...
recommended_agent: ...
next_action: scout_more|apply|execute|reject
```

##### Bug Bounty / Security Research Agent

A revenue-capable agent, but must be heavily scoped. Legal line-nya jangan dilompati cuma karena agent lagi semangat cari duit.

Allowed by default:

- read public bug bounty program scopes
- track eligible targets and rules
- prepare passive-recon plans only after scope is attached; execute nothing against third-party targets without explicit per-target approval
- analyze own assets and explicitly authorized targets
- prepare responsible disclosure reports

Requires explicit approval and scope proof:

- active scanning
- exploit validation
- credentialed testing
- touching third-party systems
- submission under Albert/company identity

Must never do:

- out-of-scope exploitation
- persistence, exfiltration, destructive testing
- bypassing rate limits or access controls outside program rules
- "spray and pray" scanning of random internet targets

##### Sales / Outreach Agent

Drafts proposals, pitches, partnership emails, and follow-ups for approved opportunities. Public sending requires approval until whitelisted.

##### Product Growth Agent

Looks for ways existing projects can earn: paid feature packaging, landing pages, usage analytics, pricing experiments, waitlists, SEO/content, distribution channels.

#### Knowledge / External World Crew

##### Research Agent

Searches web/docs, builds market/technical briefs, keeps source citations.

##### Procurement Agent

Can compare VPS/provider/software subscriptions. Purchase actions require approval.

##### Content/Comms Agent

Drafts posts/emails/docs. Public posting requires approval unless explicitly whitelisted.

##### Home/Ops Personal Agent

Personal automations, reminders, smart-home, calendar. Keep separate from finance/prod infra credentials.

#### Crew Composition Starter Pack

Minimum useful ship:

- Mothership / Captain
- Project Orchestrator
- DevOps
- Reviewer
- Security Guard
- Finance
- Librarian

Autonomous growth pack:

- Expansion Agent
- Provisioner
- Skillsmith
- QA / Proof
- Auditor

Money-seeking pack:

- Revenue Scout
- Bug Bounty / Security Research
- Sales / Outreach
- Product Growth
- Finance / Risk

Council pack:

- Council Agent
- Security Guard
- Finance/Risk
- relevant domain expert
- Reviewer/Auditor

### L. Data Model Expansion

Core tables/entities:

- `nodes`
- `workers`
- `worker_facts`
- `capabilities`
- `capability_attestations`
- `projects`
- `project_packs`
- `missions`
- `tasks`
- `runs`
- `leases`
- `heartbeats`
- `artifacts`
- `proofs`
- `policies`
- `policy_decisions`
- `approvals`
- `credentials_sessions`
- `budgets`
- `usage_events`
- `incidents`
- `audit_events`
- `skills_inventory`
- `config_snapshots`
- `reports`
- `crew_roles`
- `council_sessions`
- `council_memos`
- `revenue_opportunities`
- `bug_bounty_programs`
- `scope_rules`
- `expansion_proposals`
- `agent_templates`
- `skill_improvement_proposals`

Extra tables for ship autonomy:

```yaml
crew_roles:
  - role_id
  - family: command|guard|delivery|expansion|money|knowledge
  - default_permissions
  - required_approvals
  - report_schema

council_sessions:
  - session_id
  - decision_topic
  - participating_agents
  - max_rounds
  - final_recommendation
  - dissent_notes
  - albert_decision

revenue_opportunities:
  - opportunity_id
  - type
  - source_url
  - expected_value_usd
  - estimated_hours
  - risk_level
  - required_capabilities
  - status
  - assigned_agent

bug_bounty_programs:
  - program_id
  - platform
  - scope_url
  - in_scope_assets
  - out_of_scope_rules
  - safe_harbor_present
  - active_testing_allowed
  - last_scope_reviewed_at

expansion_proposals:
  - proposal_id
  - reason
  - new_role_or_node
  - expected_monthly_cost
  - capability_gap_closed
  - approval_status
```

### M. Protocols and APIs

Potential API surface:

- `POST /nodes/enroll`
- `POST /nodes/heartbeat`
- `POST /nodes/facts`
- `GET /workers/available?capability=...`
- `POST /missions`
- `POST /missions/{id}/brief`
- `POST /missions/{id}/launch`
- `POST /runs/{id}/events`
- `POST /artifacts`
- `POST /proofs`
- `POST /usage`
- `POST /policy/decide`
- `POST /approvals`
- `POST /credentials/issue`
- `POST /credentials/revoke`
- `POST /incidents`
- `POST /kill-switch`
- `POST /council/sessions`
- `POST /council/sessions/{id}/memo`
- `POST /council/sessions/{id}/decision`
- `GET /revenue/opportunities`
- `POST /revenue/opportunities/scout`
- `POST /revenue/opportunities/{id}/assign`
- `GET /bug-bounty/programs`
- `POST /bug-bounty/programs/{id}/scope-review`
- `POST /expansion/proposals`
- `POST /expansion/proposals/{id}/approve`
- `POST /skills/proposals`

Transport options:

- SSH for bootstrap/break-glass
- HTTPS webhook/API for normal operations
- message queue for event stream
- pull-based worker polling for firewalled nodes
- optional regional Queen nodes for locality

### N. Dashboards and User Interfaces

CLI:

```bash
hermes mothership status
hermes mothership nodes list
hermes mothership missions list
hermes mothership workers available --project pramana-os
hermes mothership budget status
hermes mothership finance report
hermes mothership incidents list
hermes mothership approvals list
hermes mothership council start --topic "launch readiness"
hermes mothership revenue scout --mode weekly
hermes mothership bug-bounty scopes list
hermes mothership expansion propose --capability qa-proof
```

Telegram:

```text
/mothership status
/mothership summon project pramana-os live 2d
/mothership finance
/mothership approvals
/mothership incidents
/mothership kill worker <id>
/mothership council launch-readiness pramana-os
/mothership revenue weekly
/mothership bounty scopes
/mothership expand propose security-guard
```

Web dashboard views:

- Colony overview
- Node health map
- Worker pool/capability matrix
- Mission timeline
- Budget and token spend
- Finance runway view
- Approvals queue
- Incidents/runbooks
- Audit search
- Project packs
- Skill/config drift
- Crew roster and capability gaps
- Council sessions and decisions
- Revenue opportunity pipeline
- Bug bounty scope queue
- Expansion proposals and approved bootstraps

### O. Realizable MVP Ladder

The ladder below supersedes the earlier fantasy-roadmap interpretation. It is intentionally narrower: secure boring control plane first, ant empire later.

#### MVP 0: Local State + Architecture Grounding

- SQLite runtime schema for nodes, workers, missions, tasks, approvals, budgets, audit pointers, data classes, delete requests, and circuit-breaker events.
- YAML only as seed/config, not mutable runtime state.
- Project packs and knowledge scope tags.
- Data lifecycle policy: classification, masking, retention, and deletion propagation shape.
- Seven-role MVP crew model.
- No remote mutation.

Acceptance proof:

- `mothership.db` schema exists.
- one project pack can be loaded and filtered by scope.
- architecture docs include hardening gates and non-goals.

#### MVP 1: Read-Only Registry / Heartbeat / Audit

- Node and worker registry.
- Read-only pull/webhook heartbeat ingest.
- SSH health sweep for manual/observer mode only.
- Append-only JSONL audit log for operational metadata.
- Payload references + masking/redaction path for raw/personal data.
- Daily/status digest via Telegram/CLI.

Acceptance proof:

- Mothership can list nodes/workers.
- heartbeat changes health state without mutation.
- audit JSONL receives append-only events.

#### MVP 2: Secure Worker Summon, No Mutation

- Generate mission brief with project context and scope-filtered memory.
- Pick idle worker by seven-role/capability mapping.
- Launch read-only/reporting task.
- Collect structured worker report.
- Trace ID across mission, worker report, and audit event.
- Pre-call budget ledger for Mothership-side calls.
- Semantic circuit breaker for repeated conceptual retries.

Acceptance proof:

- Mothership summons a worker for a docs/research mission.
- worker returns structured report + artifact link.
- cost is attributed to mission/worker.

#### MVP 3: Quarantined Bootstrap

- Bootstrap plan/apply flow.
- Dedicated provisioning user, no root-by-default.
- Out-of-band fingerprint approval.
- Locally generated bootstrap script with SHA256 verification.
- Node identity issued as short-lived signed token or asymmetric keypair.
- New node starts `trust_tier: quarantine`.
- No role/toolset assignment until separate approval.

Acceptance proof:

- test server is enrolled as quarantined.
- installed Hermes version and script hash are independently verified.
- bootstrap audit trail is append-only.

#### MVP 4: Policy + Approval + Secrets Backend

- External secrets backend interface: Vault, Bitwarden Secrets Manager, Infisical, or equivalent.
- Mothership stores references/session IDs, not raw master secrets.
- Approval objects for high-risk actions.
- Telegram approval may initiate/confirm low-risk actions; high-risk actions require durable approval and optional second-channel confirmation.
- Worker local fallback policy generated at enrollment.

Acceptance proof:

- Vault/env/prod/billing action is blocked until approval.
- read-only action is auto-allowed.
- fallback policy blocks mutation while offline.

#### MVP 5: Controlled Mutation

- Task state machine with `execution_phase`.
- Irreversible phase transition before write/deploy/mutate.
- No auto-requeue for irreversible orphaned tasks.
- Idempotency keys for external mutations.
- Reconciliation states: healthy -> degraded alert-only -> unreachable -> intervention_required.
- Reconciler never mutates locked/active workers.

Acceptance proof:

- simulated lease expiry in irreversible phase opens incident, not requeue.
- duplicate deploy idempotency key blocks second execution.

#### MVP 6: Finance / Revenue Scout Read-Only

- Finance report from read-only data sources and manual ledgers.
- Revenue Scout ranks opportunities: grants, hackathons, freelance, cost-saving, bug bounty listings.
- Bug bounty activity is scouting only by default.
- Active third-party testing requires per-target approval, attached scope doc, scope version, and legal acknowledgment.

Acceptance proof:

- Mothership can answer finance status from a fresh report.
- revenue opportunities include EV/risk/effort/source.
- bug bounty task without approval is blocked.

#### MVP 7: Event Bus / HA / Scale

- Move normal worker communication from SSH toward pull/webhook API.
- Buffered transport decision: Redis/NATS/Postgres/gRPC only when measured webhook/pull pain justifies it; NATS JetStream is the preferred candidate for offline telemetry replay.
- Hot standby or backup/restore plan for Mothership.
- OTel/OpenInference-compatible spans if JSONL tracing becomes painful.
- Provider/API-key hard spending limits as final circuit breaker.

Acceptance proof:

- worker can claim/report without SSH.
- Mothership outage does not erase local worker evidence.
- restore drill proves registry/audit recovery.

### P. Concrete Example Scenarios

#### Scenario: Pramana OS Live in 2 Days

Albert request:

> Setup agent yang available buat Pramana OS dari GitHub, target live 2 hari.

Mothership:

1. Finds idle worker with `project-orchestrator`, `github`, `linux`, `deploy` capabilities.
2. Loads/creates `project_pack: pramana-os`.
3. Runs bounded repo discovery if missing.
4. Checks budget and risk policy.
5. Generates mission brief with deadline, DoD, reporting cadence.
6. Launches worker.
7. Worker does local decomposition.
8. Mothership monitors progress, costs, and proof.
9. Final answer includes live URL, smoke test, deployment doc, cost, remaining gaps.

#### Scenario: “Kondisi Keuangan Gimana?”

Mothership:

1. Checks latest finance report freshness.
2. If stale, asks finance agent for refresh.
3. Finance agent checks portfolio/balance/spend/subscription/token/VPS/trading risk.
4. Mothership combines finance report with token/VPS usage ledger.
5. Final answer gives:
   - safe/not safe
   - runway
   - top spend
   - anomalies
   - decisions needed

#### Scenario: Worker Goes Rogue / Token Burn

Signals:

- token spend 10x baseline
- repeated retries
- no useful artifact

Mothership:

1. Opens incident.
2. Freezes worker or mission budget.
3. Revokes short-lived credentials.
4. Collects forensic bundle.
5. Reports to Albert.
6. Suggests resume/retry with cheaper model or stricter brief.

#### Scenario: Cross-Server Project Needs Specialized Agents

If one project needs finance + infra + code:

- project orchestrator owns mission
- finance agent supplies budget/ROI constraints
- infra agent supplies deployment/server readiness
- reviewer agent checks risk
- Mothership coordinates only the boundaries and final synthesis

This preserves worker autonomy while keeping cross-domain policy centralized.

#### Scenario: Council Decides Launch Readiness

Albert asks:

> Kapal siap launch Pramana OS besok gak?

Mothership:

1. Opens council session with project orchestrator, QA/proof, DevOps, Security Guard, and Finance if cost matters.
2. Each specialist submits an independent memo:
   - ready/not ready
   - evidence
   - blockers
   - risk
   - recommended go/no-go
3. Council agent merges disagreement and calls out missing proof.
4. Mothership returns concise decision to Albert:
   - go / no-go / go-with-conditions
   - top 3 risks
   - exact approval needed
   - fallback/rollback path

Council is for important decisions, not every tiny task. Kalau tiap tombol butuh rapat kabinet, kapalnya tenggelam sebelum layar login.

#### Scenario: Expansion Agent Proposes New Crew

Signals:

- QA/proof tasks keep blocking launches.
- Security review is always late.
- Existing workers are overloaded.

Expansion Agent:

1. Reads backlog, mission history, stuck reasons, cost ledger.
2. Detects capability gap: `qa-proof` and `security-guard`.
3. Proposes:
   - one persistent QA/proof worker on cheap VPS
   - one read-only Security Guard profile on existing server
   - estimated monthly cost
   - required credentials
   - bootstrap steps
4. Mothership asks Albert for approval before purchase/provision.
5. Provisioner executes approved plan and Auditor stores proof.

#### Scenario: Ship Tries to Earn Money via Bug Bounty

Albert asks:

> Cari peluang duit selain crypto. Bug hunting boleh, tapi jangan bikin masalah.

Mothership:

1. Summons Revenue Scout to rank opportunities.
2. Revenue Scout finds bug bounty programs, grants, hackathons, freelance tasks, and cost-saving opportunities.
3. Security Guard/Risk checks legal scope and platform rules.
4. Bug Bounty Agent only does passive recon or own-asset testing unless explicit scope/approval exists.
5. Mothership returns opportunity queue:
   - expected value
   - effort
   - risk
   - required approval
   - recommended agent
6. Any active third-party testing requires Albert approval with program scope link.

This makes revenue-seeking possible without turning the colony into an accidental cybercrime Roomba.

### Q. Architecture Principles

1. **Brief, don't micromanage.** Mothership creates strong briefs and lets capable orchestrators own execution.
2. **Policy before power.** No high-risk tools without policy and approval.
3. **Observe before automate.** Start read-only, then summon, then mutate.
4. **Every cost has an owner.** Token/VPS/API spend must map to project/worker/mission.
5. **Every side effect has an audit trail.** No ghost writes.
6. **Use short-lived credentials.** Static all-powerful `.env` everywhere is how empires become barbeque.
7. **Separate memory types.** Project packs, task state, reports, and audit logs are different beasts.
8. **Prefer structured reports.** Mothership should synthesize from reports, not scrape random chat soup.
9. **Quarantine beats regret.** Suspicious workers stop receiving tasks.
10. **Human approval is a durable object.** Approval must pause execution and leave evidence.
11. **Workers can orchestrate locally.** Cross-server or cross-domain orchestration goes through Mothership.
12. **Proof or it didn't happen.** Done requires artifacts, not vibes.
13. **Crew roles beat vague workers.** A ship needs guards, builders, auditors, scouts, expansion, and finance — not just five generic terminals with delusions of grandeur.
14. **Earn legally or don't earn.** Revenue agents must respect scope, terms, privacy, and explicit authorization. No out-of-scope bug hunting, no internet goblin behavior.
15. **Expansion is proposed before provisioned.** The colony can recommend new agents/nodes, but purchases, broad credentials, and high-risk bootstrap require approval.

## Implementation Roadmap

This roadmap follows the audit hardening decisions. It intentionally delays remote mutation until identity, secrets, audit, budget, and task-state guarantees exist.

### Phase 0: Hardening Rewrite and Schema Freeze

Deliverables:

- architecture note revised with audit response
- SQLite schema draft for nodes/workers/missions/tasks/approvals/budgets/audit pointers
- seven-role crew model documented
- project knowledge scope-tag contract
- non-goals and hardening gates explicit

Acceptance proof:

- docs exist in repo
- schema has deterministic state fields
- no root bootstrap or raw secret pattern remains in examples

### Phase 1: Read-Only Mothership Core

Deliverables:

- SQLite registry
- read-only node/worker inventory command
- heartbeat ingest or heartbeat file collector
- append-only JSONL audit writer
- compact Telegram/CLI status digest
- no remote writes except safe read-only health checks

Acceptance proof:

- Mothership lists nodes/workers
- heartbeat updates healthy/degraded state
- audit JSONL has immutable append events
- no secrets are printed

### Phase 2: Brief + Summon Read-Only Worker

Deliverables:

- mission brief generator
- scope-filtered project memory injection
- worker selection by MVP role/capability/health/budget
- structured worker report schema
- trace ID and mission ID propagation
- pre-call budget ledger for local calls

Acceptance proof:

- Mothership assigns a docs/research mission to a worker
- worker returns structured report and artifact
- cost attributed to worker/project/mission

### Phase 3: Secure Quarantined Bootstrap

Deliverables:

- bootstrap plan/apply command design
- out-of-band host fingerprint approval
- dedicated provisioning user model
- script checksum verification
- node identity issuance and revocation
- quarantine-by-default enrollment
- local fallback policy generated for worker

Acceptance proof:

- test node enrolled as quarantined
- role assignment blocked until approval
- bootstrap events written to append-only audit
- installed Hermes version/hash independently verified

### Phase 4: Policy, Approval, and Secrets Interface

Deliverables:

- approval object schema
- trust tiers and risk tiers
- external secrets backend adapter/stub
- scoped credential session model
- high-risk gates for Vault/env/prod/billing/bug-bounty active testing
- Telegram as cockpit with durable approval backend

Acceptance proof:

- Vault/env write request is blocked pending explicit approval and diff
- read-only commands auto-allow
- credential session can be issued/revoked without raw secret exposure

### Phase 5: Controlled Mutation and Reconciliation

Deliverables:

- task lifecycle state machine
- `execution_phase` transitions
- irreversible-action lock
- idempotency-key table
- reconciler three-state model: degraded alert-only, unreachable, intervention_required
- no reconciler mutation on active task leases
- Saga/Temporal escalation decision record for multi-step external side effects

Acceptance proof:

- simulated network partition does not double-run deploy
- irreversible orphan opens incident instead of requeue
- duplicate idempotency key prevents repeated mutation

### Phase 6: Read-Only Finance and Revenue Scout

Deliverables:

- finance report schema
- cost/subscription/manual ledger ingestion
- revenue opportunity schema
- bug bounty scope-reader/scout mode
- per-target approval schema for any active testing

Acceptance proof:

- Mothership answers finance status from latest report
- Revenue Scout produces ranked opportunities
- active bug bounty action without approved target/scope is blocked

### Phase 7: Scale Transport and Resilience

Deliverables:

- worker pull/webhook task API as default transport
- SSH reduced to bootstrap/break-glass/manual observer sweeps
- optional event bus decision record: when Redis/NATS/Postgres/gRPC becomes worth it, with NATS JetStream favored for disconnected telemetry replay
- standby/backup/restore runbook
- trace export improvements if JSONL is insufficient

Acceptance proof:

- worker claims task without SSH
- Mothership restore drill succeeds
- worker offline logs replay on reconnect with source tags

## Non-Goals / Guardrails

Do not build these accidentally:

- A central all-powerful agent that owns every secret.
- A recursive spawn pyramid with no depth/budget limit.
- A raw transcript-sharing memory soup across projects.
- A raw personal-data telemetry lake with no masking, retention, or deletion propagation.
- A system that auto-approves Vault/env/prod/billing changes.
- A distributed worker system with no append-only audit log.
- A system that requires every task to flow through Mothership if direct worker use is simpler.
- A replacement for project-specific proof; Mothership summaries must link evidence.
- Root-by-default bootstrap or long-lived SSH master keys on Mothership.
- Mothership as a raw secret store.
- Automatic requeue of irreversible side-effecting tasks.
- Autonomous active bug bounty testing against third-party targets.
- Full NATS/SPIFFE/Temporal/OTel stack before the boring MVP proves it needs them — but do preserve clear escalation hooks so the MVP does not paint itself into a corner.

## Design Decisions After Audit

These are no longer open for the initial implementation:

1. **Runtime registry/state:** SQLite from MVP 0. YAML may seed config only.
2. **Bootstrap transport:** SSH-first for bootstrap/break-glass/manual observer sweeps, but not for long-term task/heartbeat flow.
3. **Normal worker transport:** start with pull/webhook API in the read-only MVP; consider Redis/NATS/gRPC only after measured evidence. If disconnected telemetry replay becomes important, prefer NATS JetStream as the first serious candidate.
4. **Node identity:** asymmetric worker identity or short-lived signed JWT with `node_id`, `trust_tier`, `expires_at`, and `jti` revocation. Signing key lives in secrets backend. SPIFFE/SPIRE remains the maturity target for high-value/many-node deployments.
5. **Secrets:** external secrets backend interface is required before remote mutation.
6. **Audit:** append-only JSONL from day one for operational metadata, exported to an external sink when available. Raw/personal payloads are referenced, masked, retained by policy, and deletable.
7. **Data lifecycle:** data classification, masking, retention, and delete propagation are part of MVP 0/1, not a compliance garnish for future lawyers to cry over.
8. **Circuit breaker:** pre-call budget and semantic retry breaker are required before worker summon can spend real money.
9. **Crew model:** seven MVP roles; specialist roles are modes/capabilities until proven necessary.
10. **Telegram:** allowed for status, low-risk commands, and approval UX; not sole authority for high-risk mutation.
11. **Bug bounty:** scout/read-only by default; active testing requires per-target approval and scope document.

Still open, but not blocking the boring MVP:

1. Which secrets backend is easiest for Albert's setup first: Vault OSS, Bitwarden Secrets Manager, Infisical, or existing host-level secret files wrapped by an adapter?
2. Which first real colony should validate the MVP: CentraCast agents, Hermes Agent agents, or docs/research workers?
3. When does event bus become worth it: worker count threshold, heartbeat volume, observed webhook/pull pain, offline replay needs, or Indonesian ISP jitter causing false dead-node alerts?
4. Which external audit sink should be used first: separate git repo, object storage with lock, or low-tech Telegram/channel mirror?
5. Which data classes will Mothership explicitly refuse to ingest until delete propagation and masking are verified?

## Initial Product Slice Recommendation

Start with a boring but useful, audit-hardened observer:

1. Create SQLite registry/runtime schema.
2. Add append-only JSONL audit writer for operational metadata.
3. Add data-classification, masking, retention, and delete-request tables.
4. Add read-only node/worker inventory and pull/webhook heartbeat ingest.
5. Add daily/incident Telegram digest.
6. Add seven-role worker capability/focus fields.
7. Add project knowledge scope tags.
8. Add cost placeholders/manual budgets plus pre-call ledger and semantic circuit-breaker shape.
9. Add explicit approval policy file.

Only after observer mode is stable, add quarantined bootstrap. Only after secrets, approval, budget, audit, and task state machine exist, add remote mutation. Boring first, secure first, ant empire later. 🐜👑
