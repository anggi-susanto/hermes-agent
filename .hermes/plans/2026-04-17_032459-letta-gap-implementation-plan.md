# Letta Gap-to-Implementation Plan (P0–P1)

## Goal

Close the highest-risk parity gaps so Letta can move from "lightweight durable memory backend" toward a credible Honcho replacement for Hermes memory.

This plan is intentionally scoped to P0–P1 only:
- P0 = functionality needed to avoid major memory regression
- P1 = operational maturity needed to run and support it safely

## Current context / assumptions

Evidence reviewed from repo:
- Honcho provider is mature and feature-rich:
  - `plugins/memory/honcho/__init__.py`
  - `plugins/memory/honcho/session.py`
  - `plugins/memory/honcho/client.py`
  - tests under `tests/honcho_plugin/`
- Letta provider exists but is intentionally lightweight:
  - `plugins/memory/letta/__init__.py`
  - targeted tests in `tests/agent/test_memory_provider.py`
- External provider wiring is already generic and reusable:
  - `plugins/memory/__init__.py`
  - `run_agent.py`
  - `agent/memory_manager.py`
  - `hermes_cli/memory_setup.py`

Assumption:
- We are not trying to make Letta identical to Honcho internally.
- We are trying to make Hermes user-facing memory behavior good enough that swapping providers does not cause obvious regressions.

## Success criteria

Letta reaches an acceptable replacement threshold when all of the following are true:
1. It stores more than explicit durable memory writes; conversation turns contribute to memory.
2. It supports `tools`, `context`, and `hybrid` recall behavior.
3. It can inject useful memory automatically without requiring manual tool calls every time.
4. Existing built-in memory can be migrated into Letta cleanly.
5. Operators can configure, validate, and troubleshoot Letta without reading the source.
6. Regression coverage exists for core behavior, not just smoke tests.

---

## Proposed implementation approach

Build Letta parity in layers, not all at once:

### Layer 1 — Behavioral parity (P0)
Focus on conversation-derived memory, runtime retrieval modes, and continuity.

### Layer 2 — Operational parity (P1)
Focus on setup UX, diagnostics, and test confidence.

Avoid premature expansion into P2 items like AI self-memory or sophisticated Letta-native reasoning until P0–P1 are proven.

---

## P0 plan — must-have parity work

### P0.1 — Add real `sync_turn()` behavior to Letta

#### Problem
Current Letta `sync_turn()` is a no-op, so ordinary conversation turns do not enrich memory.

#### Target behavior
Implement a low-noise write path that converts conversation turns into structured episodic/session memory.

#### Proposed design
Add a configurable turn-sync mode to Letta, with conservative defaults:
- `sync_mode: summary_only | episodic_filtered | full_turn_digest`
- default: `episodic_filtered`

Suggested write rules:
- Ignore extremely short/transient turns.
- Keep only durable or likely-reusable content.
- Store user/assistant turn pairs as compact episodic records.
- Avoid dumping raw chat spam into archival memory.

Suggested episodic payload shape:
```json
{
  "memory_type": "episodic",
  "canonical_user_id": "telegram:73784266",
  "project": "optional",
  "user": "...",
  "assistant": "...",
  "summary": "compact one-line recap",
  "source": "turn_sync",
  "session_id": "...",
  "created_at": "..."
}
```

#### Likely file changes
- `plugins/memory/letta/__init__.py`

#### Validation
- unit tests for:
  - short noise skipped
  - valid turn stored as episodic memory
  - sync disabled in cron/subagent contexts
  - payload shape correctness

#### Notes
Do not attempt full transcript mirroring first. Start with filtered episodic storage.

---

### P0.2 — Add `recall_mode` support (`tools` / `context` / `hybrid`)

#### Problem
Letta always exposes tools and has a simplistic prefetch path. There is no runtime behavior equivalent to Honcho's recall modes.

#### Target behavior
Letta should honor config-driven retrieval mode:
- `tools` = tools only, no auto-injected context
- `context` = auto-injected context only, no Letta tools
- `hybrid` = both

#### Proposed design
Add new config fields to `LettaConfig`:
- `recall_mode: hybrid`
- `init_on_session_start: true|false` (if useful for warm start)
- `context_char_limit`
- `injection_frequency: every-turn | first-turn`
- `prefetch_enabled: true|false`

Implementation rules:
- `get_tool_schemas()` must return empty in `context` mode.
- `prefetch()` must return empty in `tools` mode.
- `system_prompt_block()` should describe the active mode accurately.

#### Likely file changes
- `plugins/memory/letta/__init__.py`
- maybe config documentation/help surfaces if needed

#### Validation
- tests for each mode:
  - context mode hides tools
  - tools mode disables auto context
  - hybrid mode does both

---

### P0.3 — Replace naive prefetch with background-prefetch + first-turn baked context

#### Problem
Current Letta prefetch is synchronous, heuristic-only, and weak compared to Honcho.

#### Target behavior
Make Letta memory available in a stable, low-latency way:
- warm useful memory on session start
- queue background prefetch at end of turn
- consume cached context next turn
- optionally bake a strong first-turn block for prompt stability

#### Proposed design
Add provider state similar in spirit to Honcho, but simpler:
- `_prefetch_result`
- `_prefetch_thread`
- `_first_turn_context`
- `_turn_count`
- `_last_prefetch_turn`

Prefetch strategy:
1. On initialize:
   - run `_refresh_prefetch("session start")`
   - optionally cache a first-turn block
2. On turn end:
   - `queue_prefetch(query)` starts background fetch thread
3. On next turn:
   - `prefetch()` returns cached result and clears it

Improve trigger logic:
- not just keyword matching
- also trigger on:
  - project names
  - references to previous work
  - ambiguous preference/workflow phrasing
  - user correction/memory intent

Suggested config knobs:
- `prefetch_top_k`
- `prefetch_min_query_chars`
- `prefetch_cadence`
- `first_turn_context_enabled`
- `context_char_limit`

#### Likely file changes
- `plugins/memory/letta/__init__.py`

#### Validation
- tests for:
  - initialize prefetch warm-up
  - queue_prefetch stores async result
  - prefetch pops cached result
  - first-turn injection remains stable
  - tools mode returns no injected context

---

### P0.4 — Build migration path from built-in memory to Letta

#### Problem
Switching to Letta today risks perceived amnesia because there is no import path from existing built-in memory files.

#### Target behavior
One-time migration should seed Letta with existing durable memory.

#### Proposed design
Add migration helper(s) to Letta provider:
- import built-in `MEMORY.md` and `USER.md` entries
- optionally import `SOUL.md` only if we later support AI-self memory (not P0 default)
- store imported records with `source: migrated_builtin_memory`
- keep migration idempotent enough to avoid duplicate spam

Two possible implementation modes:
1. Lightweight provider-side migrate-on-first-init if target Letta agent is empty
2. Explicit CLI/setup migration step

Recommended:
- do not auto-import silently on every init
- expose explicit migration during setup and optionally on first activation if empty

Suggested dedup strategy:
- compute stable hash over normalized content
- skip import if identical hash already exists in archival memory

#### Likely file changes
- `plugins/memory/letta/__init__.py`
- `hermes_cli/memory_setup.py` (optional guided migration prompt)

#### Validation
- tests for:
  - import from built-in memory files
  - duplicate prevention
  - empty-file safety
  - correct mapping to profile/preference records

---

## P1 plan — operational maturity

### P1.1 — Add Letta-specific doctor checks

#### Problem
Doctor has dedicated Honcho checks but Letta is treated as a generic provider.

#### Target behavior
`hermes doctor` should tell operators whether Letta is actually ready.

#### Proposed checks
- configured provider is `letta`
- `LETTA_BASE_URL` or config base URL present
- API key presence only if required by deployment mode
- base URL connectivity / simple API probe
- configured project ID/header values shown safely
- provider availability status displayed explicitly

#### Likely file changes
- `hermes_cli/doctor.py`

#### Validation
- tests for:
  - missing base URL
  - unreachable Letta server
  - available Letta provider
  - disabled vs enabled states

---

### P1.2 — Add dedicated Letta `post_setup` flow or richer setup UX

#### Problem
Letta currently uses the generic schema prompt. It works, but it is thin compared to Honcho's guided setup.

#### Target behavior
Setup should validate configuration, optionally seed/migrate memory, and confirm readiness before activation feels “done”.

#### Proposed design
Add `post_setup()` to Letta provider or enrich generic setup with Letta-specific hook behavior.

Recommended `post_setup()` responsibilities:
1. collect/configure fields
2. test API connectivity
3. optionally create/verify target agent convention
4. optionally run built-in memory migration
5. print a clear success/failure summary

#### Likely file changes
- `plugins/memory/letta/__init__.py`
- possibly `plugins/memory/letta/cli.py` if we want a dedicated CLI later

#### Validation
- tests for successful setup path and failing connectivity path

---

### P1.3 — Expand Letta test suite to real provider-grade coverage

#### Problem
Current Letta coverage is too shallow to trust as default replacement.

#### Target behavior
Letta should have focused tests roughly analogous to the Honcho plugin's confidence model.

#### Add test groups
1. Config parsing
   - env vs config precedence
   - optional API key behavior
   - recall mode defaults
2. Runtime behavior
   - initialize
   - canonical user ID scoping
   - agent creation/reuse
   - sync_turn behavior
   - prefetch lifecycle
3. Tool behavior
   - profile/search/context/conclude outputs
   - project filtering
   - malformed response handling
4. Migration
   - built-in memory import
   - duplicate suppression
5. Ops
   - doctor checks
   - setup flow

#### Likely file changes
- `tests/agent/test_memory_provider.py` or preferably split into:
  - `tests/letta_plugin/test_config.py`
  - `tests/letta_plugin/test_provider.py`
  - `tests/letta_plugin/test_setup.py`
  - `tests/letta_plugin/test_doctor.py`

#### Validation
- run targeted Letta test suite first
- then full test suite

---

## Suggested execution order

### Phase A — foundation
1. Add `LettaConfig` fields for recall + sync behavior.
2. Refactor provider internals to support mode-aware behavior.

### Phase B — memory behavior
3. Implement filtered `sync_turn()` episodic storage.
4. Implement background `queue_prefetch()` and cached `prefetch()`.
5. Add first-turn context baking.

### Phase C — continuity
6. Implement built-in memory migration.
7. Add dedup protections.

### Phase D — operator readiness
8. Add Letta-specific doctor checks.
9. Add `post_setup()` flow with connectivity test + migration option.

### Phase E — confidence
10. Expand test suite.
11. Run focused tests.
12. Run full suite.

---

## Files likely to change

### Core provider
- `plugins/memory/letta/__init__.py`

### Runtime wiring / possibly no changes or minimal changes
- `run_agent.py`
- `agent/memory_manager.py`

### Setup / doctor
- `hermes_cli/memory_setup.py`
- `hermes_cli/doctor.py`

### Tests
- `tests/agent/test_memory_provider.py`
- or new split Letta test files under `tests/letta_plugin/`

---

## Risks and tradeoffs

### Risk 1 — Overwriting Letta's intended role
If we force Letta to imitate Honcho too closely, we may lose the simplicity that makes Letta attractive.

Mitigation:
- implement parity at the Hermes behavior layer, not by recreating Honcho internals exactly.

### Risk 2 — Archival memory spam
If `sync_turn()` is too eager, Letta storage quality will collapse.

Mitigation:
- filtered episodic summaries, not raw transcript dumps.
- strong tests for noise suppression.

### Risk 3 — Duplicate migration writes
Repeated imports could bloat memory.

Mitigation:
- content hashing and duplicate checks.

### Risk 4 — False confidence from setup success
A config prompt that saves successfully is not the same as a usable provider.

Mitigation:
- connectivity probe during setup and doctor support.

---

## Recommended implementation slices

### Slice 1 (best first PR)
- Add `recall_mode`
- Implement mode-aware `get_tool_schemas()` and `prefetch()`
- Add background prefetch cache
- Add tests for these behaviors

Why first:
- smallest meaningful step
- immediately improves runtime behavior
- low blast radius

### Slice 2
- Implement filtered `sync_turn()` episodic storage
- add tests

### Slice 3
- Implement migration from built-in memory
- optional setup hook to trigger migration
- add tests

### Slice 4
- Add Letta doctor support
- add post-setup validation UX
- add tests

---

## Verification checklist

Before declaring Letta ready for wider use:
- [ ] `tools/context/hybrid` modes proven by tests
- [ ] `sync_turn()` persists useful episodic records
- [ ] prefetch works from cache, not only synchronous lookup
- [ ] built-in memory migration works and is idempotent enough
- [ ] `hermes doctor` gives actionable Letta diagnostics
- [ ] setup flow validates connectivity
- [ ] full suite passes

---

## Recommendation

Do not jump straight to “replace Honcho by default”.

Recommended rollout:
1. Implement Slice 1 + Slice 2
2. Validate on targeted tests
3. Implement Slice 3 + Slice 4
4. Run full suite
5. Only then consider making Letta the preferred self-hosted memory backend
6. Defer “full Honcho replacement” language until runtime behavior is proven in real sessions
