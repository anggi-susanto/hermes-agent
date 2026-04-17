# Letta vs Honcho — Replacement Readiness Execution Tracker

> For Hermes: use subagent-driven-development when executing this tracker. Preserve anchor IDs. Do not mark anything Done without code/test/proof. This tracker is for making Letta honestly replacement-ready for Hermes external memory duties, not for marketing parity claims.

Goal: close the evidence-backed gap between Letta and Honcho so Hermes can eventually claim Letta is a safe full replacement for the current Honcho memory plugin, not just a lighter structured-memory alternative.

Architecture: treat this as a replacement-parity program, not a one-off feature. The work is split into runtime parity, migration continuity, reasoning/retrieval parity, and confidence hardening. The tracker assumes the current repo state as of 2026-04-17: Letta is integrated and usable, but still trails Honcho in conversational continuity, self/AI memory, incumbent migration, and depth of verification.

Tech stack: Hermes memory provider interface (`agent/memory_provider.py`, `agent/memory_manager.py`), Letta plugin (`plugins/memory/letta/__init__.py`), Honcho plugin (`plugins/memory/honcho/*`), CLI setup/doctor (`hermes_cli/memory_setup.py`, `hermes_cli/doctor.py`), pytest suites under `tests/agent/`, `tests/honcho_plugin/`, and any new `tests/letta_plugin/` coverage added by this program.

Audit basis:
- `plugins/memory/letta/__init__.py`
- `plugins/memory/honcho/__init__.py`
- `plugins/memory/honcho/client.py`
- `agent/memory_provider.py`
- `agent/memory_manager.py`
- `hermes_cli/memory_setup.py`
- `hermes_cli/doctor.py`
- `tests/agent/test_memory_provider.py`
- `tests/honcho_plugin/test_async_memory.py`
- `tests/honcho_plugin/test_session.py`
- `tests/honcho_plugin/test_client.py`

Audit verdict frozen into this tracker:
- Letta status today: integrated, partly usable, not full-replacement-ready
- Honcho status today: incumbent with broader runtime behavior and deeper test confidence
- Safe claim today: Letta can replace explicit/manual structured durable memory for some workflows
- Unsafe claim today: Letta can replace Honcho end-to-end without meaningful regression

---

## Status vocabulary

Use only these statuses:
- Pending
- In Progress
- Partial
- Blocked
- Done
- Split
- Dropped

Rules:
1. Preserve anchor IDs even if wording changes.
2. If a parent is decomposed, keep the parent and mark it Split; link children.
3. Code existing is not enough for Done. Acceptance proof is mandatory.
4. “Parity” means behavior parity plus operational confidence, not just tool name parity.

---

## Current state assessment

Already true in the repo:
- Letta has a real plugin integration, config schema, post-setup path, doctor check, and migration from built-in `USER.md` / `MEMORY.md`.
- Letta supports `recall_mode` (`hybrid` / `context` / `tools`), first-turn warmed context, auto-session summary, built-in memory mirroring, and selective episodic writes.
- Honcho still has the stronger runtime model for conversational continuity: true turn sync, background prefetch orchestration, first-turn baked context, richer session strategy/config, and AI/self-peer modeling.
- Honcho still has much deeper targeted test coverage than Letta.

Main gap classes:
1. Conversational continuity gap
2. AI/self-memory gap
3. Incumbent migration gap
4. Reasoning/context semantics gap
5. Test-confidence gap
6. Operational parity gap

---

## Dependency map

High-level sequencing:
- LRR-001 must land before any honest full-replacement claim.
- LRR-002 and LRR-003 are also P0 and should not wait until after docs/marketing work.
- LRR-004 can begin in parallel once LRR-001 behavior contracts are frozen.
- LRR-005 should run alongside implementation, but final signoff waits for LRR-001..LRR-004.
- LRR-006 and LRR-007 are hardening/rollout lanes and should not be used to mask unresolved P0 gaps.

Parallel-safe grouping:
- Group A: LRR-001 + LRR-005.A
- Group B: LRR-002
- Group C: LRR-003
- Group D: LRR-004 + LRR-005.B
- Group E: LRR-006 + LRR-007 after P0 lanes are at least Partial with evidence

---

## Master tracker table

| Anchor | Title | Status | Priority | Depends on | Owner lane | Why it matters |
|---|---|---:|---:|---|---|---|
| LRR-001 | Replace selective episodic writes with true conversational continuity model | Pending | P0 | - | Runtime lane | Biggest blocker to Honcho replacement claim |
| LRR-002 | Add AI/self-memory parity model for Letta | Pending | P0 | - | Runtime/modeling lane | Honcho supports dual-peer memory; Letta currently does not |
| LRR-003 | Build Honcho-to-Letta migration path | Pending | P0 | - | Migration lane | Full cutover without continuity migration is regression by design |
| LRR-004 | Upgrade Letta context semantics from retrieval render to synthesized memory answer | Pending | P0 | LRR-001 contract freeze | Retrieval lane | Same tool names are misleading without closer behavior parity |
| LRR-005 | Build dedicated Letta parity test suite | Pending | P1 | LRR-001..LRR-004 contracts | Verification lane | Replacement confidence depends on targeted tests, not optimism |
| LRR-006 | Reach setup/doctor/runtime ops parity for Letta | Pending | P1 | LRR-001..LRR-004 partial | Ops lane | Operators need stable setup, diagnostics, and safe failure behavior |
| LRR-007 | Produce replacement-readiness proof pack and cutover rubric | Pending | P2 | LRR-001..LRR-006 | Proof lane | Prevent premature full-replacement claims |

---

## Anchor details

### LRR-001 — Replace selective episodic writes with true conversational continuity model

Status: Pending
Priority: P0
Owner lane: Runtime lane

Problem:
- `plugins/memory/letta/__init__.py` currently writes only filtered episodic summaries for some turns.
- Honcho persists actual conversation turns into a session model and flushes them in the background.
- That means Letta currently behaves like a durable-memory extractor, not a full conversation-memory backend.

Objective:
- Make Letta preserve enough turn-by-turn session continuity that a user switching from Honcho would not lose the main cross-session conversational memory behavior Hermes currently relies on.

Scope:
- Define a Letta-side session record model or equivalent archival/session structure.
- Persist user and assistant turns consistently, not only heuristic “durable” episodes.
- Preserve context fencing/sanitization so injected memory doesn’t poison storage.
- Define what gets stored verbatim vs summarized vs skipped.

Suggested files:
- Modify: `plugins/memory/letta/__init__.py`
- Modify: `agent/memory_provider.py` only if interface clarification is truly needed
- Add tests: `tests/letta_plugin/test_session_continuity.py` or equivalent dedicated suite

Deliverables:
- A concrete Letta session continuity design in code
- Updated `sync_turn()` semantics
- Clear storage policy comments/docstrings
- Targeted tests proving continuity behavior

Acceptance proof:
- Tests prove consecutive user/assistant turns are stored deterministically
- Tests prove short/noisy turns are handled by an explicit contract, not accidental heuristics
- Tests prove session-end behavior does not lose pending turn data
- Live/local smoke output demonstrates at least one multi-turn conversation can be recalled meaningfully on a later turn

Anti-bullshit notes:
- Not enough: keeping the current `episodic` summary write and renaming it
- Not enough: adding comments claiming “session continuity” without real per-turn persistence
- Not enough: a passing generic plugin load test

Suggested child split if needed:
- LRR-001.A — storage model contract
- LRR-001.B — sync/flush implementation
- LRR-001.C — continuity recall formatting/tests

---

### LRR-002 — Add AI/self-memory parity model for Letta

Status: Pending
Priority: P0
Owner lane: Runtime/modeling lane

Problem:
- Honcho supports user and AI/self memory concepts.
- Letta is currently centered around one lightweight agent per canonical user.
- There is no evidence of comparable AI/self-peer querying or first-turn self-memory context in Letta.

Objective:
- Add a Letta-side model that can represent Hermes/assistant self-memory closely enough to avoid a meaningful regression against Honcho’s dual-peer behavior.

Scope:
- Define whether this is separate Letta agents, separate memory types, or a structured peer namespace.
- Support both user-facing and assistant-facing memory retrieval where needed.
- Ensure first-turn context can include the assistant/self side when configured.

Suggested files:
- Modify: `plugins/memory/letta/__init__.py`
- Add tests: `tests/letta_plugin/test_self_memory.py`
- Optionally add docs: `docs/plans/` follow-up or `website/docs/` later

Deliverables:
- Explicit self-memory design
- Tool/runtime retrieval behavior covering user vs assistant/self scope
- Tests proving correct scoping and retrieval

Acceptance proof:
- Tests show user memory and AI/self memory are stored and retrieved separately
- Tests show first-turn or explicit retrieval can include assistant/self context intentionally
- No cross-contamination between user and AI namespaces in tests

Anti-bullshit notes:
- Not enough: storing everything under the same archival bucket and calling it “self-memory”
- Not enough: docs-only claim that Letta can model the assistant

Suggested child split if needed:
- LRR-002.A — namespace/model design
- LRR-002.B — retrieval/tool semantics
- LRR-002.C — first-turn/self-context behavior

---

### LRR-003 — Build Honcho-to-Letta migration path

Status: Pending
Priority: P0
Owner lane: Migration lane

Problem:
- Letta can import built-in `USER.md` / `MEMORY.md` entries.
- There is no evidence of a migration path from incumbent Honcho state into Letta.
- That makes a full replacement claim operationally dishonest for real users with existing Honcho memory.

Objective:
- Provide a migration/import path from Honcho-backed state into Letta so cutover does not reset the user’s effective memory history.

Scope:
- Determine what can be exported from Honcho safely and reproducibly.
- Map Honcho concepts into Letta memory types/namespaces.
- Define dedup/idempotency rules.
- Expose migration through setup or explicit migration command only when safe.

Suggested files:
- Modify: `plugins/memory/letta/__init__.py`
- Modify: `plugins/memory/honcho/*` only if exporter helpers are needed
- Modify: `hermes_cli/memory_setup.py` if migration entrypoint belongs there
- Add tests: `tests/letta_plugin/test_migration_from_honcho.py`

Deliverables:
- Honcho export/import mapping code
- Idempotent migration routine
- Tests covering duplicates and partial migration retries
- Operator-facing entrypoint for migration

Acceptance proof:
- Tests prove a representative Honcho-derived dataset can be imported into Letta
- Tests prove repeat migration does not duplicate entries
- Operator-facing path reports imported/skipped/error counts honestly

Anti-bullshit notes:
- Not enough: only migrating built-in memory files and calling that “replacement migration”
- Not enough: a one-off script outside repo without test coverage

Suggested child split if needed:
- LRR-003.A — concept mapping + exporter contract
- LRR-003.B — importer/dedup implementation
- LRR-003.C — CLI/setup entrypoint + reporting

---

### LRR-004 — Upgrade Letta context semantics from retrieval render to synthesized memory answer

Status: Pending
Priority: P0
Owner lane: Retrieval lane
Depends on: LRR-001 contract freeze

Problem:
- `honcho_context` performs dialectic-style synthesized answering.
- `letta_context` currently renders search hits back to the model/user.
- Surface parity exists, behavior parity does not.

Objective:
- Make Letta’s context query behavior materially closer to Honcho’s “answer from memory” semantics.

Scope:
- Decide whether synthesis is performed by Letta backend APIs, Hermes-side assembly, or a constrained summarization pass.
- Preserve a cheap/raw search path separately.
- Keep response shape explicit about synthesized answer vs raw evidence.

Suggested files:
- Modify: `plugins/memory/letta/__init__.py`
- Add tests: `tests/letta_plugin/test_context_semantics.py`

Deliverables:
- Revised `letta_context` behavior
- Stable result shape documenting answer + evidence excerpts if applicable
- Tests proving non-empty, question-oriented synthesis over retrieved memory

Acceptance proof:
- Tests show `letta_context` returns a synthesized answer contract, not only bullet-dumped hits
- Tests show `letta_search` remains available for raw evidence access
- Tests cover no-hit, ambiguous-hit, and multi-hit cases

Anti-bullshit notes:
- Not enough: wrapping the same hit list in a different string label
- Not enough: adding “summary” wording with no real semantic change

Suggested child split if needed:
- LRR-004.A — result contract design
- LRR-004.B — implementation
- LRR-004.C — retrieval-vs-synthesis test coverage

---

### LRR-005 — Build dedicated Letta parity test suite

Status: Pending
Priority: P1
Owner lane: Verification lane

Problem:
- Honcho has dedicated client/session/async test suites.
- Letta coverage currently lives mostly in broad plugin contract tests.
- That asymmetry is itself evidence against replacement readiness.

Objective:
- Give Letta a dedicated test surface deep enough to support replacement claims.

Scope:
- Add targeted suites for session continuity, self-memory, migration, context semantics, and ops behavior.
- Prefer dedicated `tests/letta_plugin/` or similarly scoped files.
- Keep generic `tests/agent/test_memory_provider.py` as contract smoke coverage, not the whole story.

Suggested files:
- Add: `tests/letta_plugin/test_session_continuity.py`
- Add: `tests/letta_plugin/test_self_memory.py`
- Add: `tests/letta_plugin/test_migration.py`
- Add: `tests/letta_plugin/test_context_semantics.py`
- Add: `tests/letta_plugin/test_ops.py`

Deliverables:
- Dedicated Letta-focused test directory/files
- Coverage of all P0 lane contracts
- Documentation/comments that explain what each suite proves

Acceptance proof:
- Test inventory visibly mirrors the main behavioral domains under active development
- New tests run green in isolation and within broader relevant suites
- Reviewers can point to specific tests for each replacement claim

Anti-bullshit notes:
- Not enough: adding a few more cases to `tests/agent/test_memory_provider.py` only
- Not enough: test names claiming parity without asserting parity-critical behavior

Suggested child split if needed:
- LRR-005.A — runtime continuity tests
- LRR-005.B — migration/semantics tests
- LRR-005.C — ops/doctor/setup tests

---

### LRR-006 — Reach setup/doctor/runtime ops parity for Letta

Status: Pending
Priority: P1
Owner lane: Ops lane

Problem:
- Letta setup and doctor are decent, but parity means more than “connects successfully.”
- Operators need diagnostics around mode, migration state, and failure boundaries.

Objective:
- Make Letta operationally legible enough for real cutover readiness.

Scope:
- Improve doctor/status output to reflect parity-relevant config and migration state.
- Add explicit warnings when Letta is configured in a reduced-capability mode relative to replacement claims.
- Add runtime-safe failure/skip behavior where needed.

Suggested files:
- Modify: `hermes_cli/doctor.py`
- Modify: `hermes_cli/memory_setup.py`
- Modify: `plugins/memory/letta/__init__.py`
- Add tests under `tests/hermes_cli/` and/or `tests/letta_plugin/`

Deliverables:
- Better operator diagnostics
- Explicit migration/readiness signaling
- Tests covering doctor/setup output for key modes

Acceptance proof:
- Doctor output distinguishes “configured” from “replacement-ready” if applicable
- Setup/migration path makes reduced/partial capability visible
- Tests assert these user-facing diagnostics

Anti-bullshit notes:
- Not enough: a green connection test alone
- Not enough: hiding reduced capability behind optimistic wording

---

### LRR-007 — Produce replacement-readiness proof pack and cutover rubric

Status: Pending
Priority: P2
Owner lane: Proof lane
Depends on: LRR-001..LRR-006

Problem:
- Even after code lands, teams drift into premature “ready” claims without a consistent proof bar.

Objective:
- Create the final evidence rubric that decides whether Letta is:
  1. lightweight replacement only,
  2. partial replacement,
  3. or full Honcho replacement.

Scope:
- Summarize the parity matrix with hard evidence links.
- Define required tests, migration proof, and smoke checks for any cutover recommendation.
- Keep this repo-local and evidence-first.

Suggested files:
- Add or update: `docs/plans/2026-04-17-letta-honcho-replacement-readiness-tracker.md`
- Add follow-up doc if needed: `docs/plans/2026-04-17-letta-honcho-cutover-rubric.md`

Deliverables:
- Cutover rubric
- Evidence checklist
- Final classification table

Acceptance proof:
- Each claim in the rubric points to a test, file, or reproducible command
- There is an explicit “do not claim full replacement if…” section

Anti-bullshit notes:
- Not enough: narrative summary with no linked evidence
- Not enough: marking “ready” because P1/P2 docs were polished while P0 behavior gaps remain

---

## Recommended lane ownership

Lane A — Runtime continuity
- Owns: LRR-001
- Output: continuity design + implementation + tests
- Must not decide migration semantics alone

Lane B — Modeling parity
- Owns: LRR-002
- Output: self-memory design + retrieval rules + tests
- Must not weaken continuity proof requirements

Lane C — Migration continuity
- Owns: LRR-003
- Output: exporter/importer path + idempotency tests + operator entrypoint
- Must not relabel built-in migration as Honcho migration

Lane D — Retrieval semantics
- Owns: LRR-004
- Output: synthesized context answer contract + tests
- Must not break raw evidence retrieval path

Lane E — Verification and ops
- Owns: LRR-005, LRR-006, LRR-007
- Output: dedicated suites, doctor/setup parity, final cutover rubric
- Must not sign off unresolved P0 gaps

---

## Acceptance proof checklist for eventual “full replacement” claim

All must be true:
- [ ] Letta stores and recalls multi-turn conversational continuity with evidence
- [ ] Letta supports user and assistant/self memory scoping with evidence
- [ ] Honcho-to-Letta migration exists and is idempotent with evidence
- [ ] `letta_context` semantics are materially closer to synthesized memory answers than raw retrieval dumps
- [ ] Dedicated Letta parity test suites exist and cover the above
- [ ] Doctor/setup output makes capabilities and limitations explicit
- [ ] A proof pack/classification rubric is written and evidence-linked

If any are false:
- Do not claim “Letta can replace Honcho fully.”
- Allowed fallback labels:
  - “structured durable-memory alternative”
  - “partial replacement”
  - “lightweight replacement for explicit/manual memory workflows”

---

## Re-anchor checklist

When updating this tracker after partial work:
1. Keep the original anchor.
2. Update status using the closed vocabulary only.
3. Add proof links: files, tests, commands, or docs.
4. State what remains missing.
5. If splitting, mark parent as Split and add child anchors.
6. Never silently collapse P0 gaps into a generic “hardening” label.

---

## Reviewer checklist

Reject completion if any of these are true:
- The change only improves wording/comments/docs but not parity behavior
- A test claims parity without asserting the parity-critical behavior
- Migration only covers built-in memory files, not incumbent Honcho continuity
- `letta_context` still just returns reformatted hit lists
- “self-memory” still shares one indistinct namespace with user memory
- Operational docs imply full replacement while P0 anchors remain Pending/Partial/Blocked

---

## Next recommended execution order

1. LRR-001 — runtime continuity
2. LRR-003 — migration continuity
3. LRR-002 — self-memory parity
4. LRR-004 — context semantics parity
5. LRR-005 — dedicated parity tests
6. LRR-006 — ops parity
7. LRR-007 — final cutover rubric

Reason:
- LRR-001 and LRR-003 are the hardest honesty blockers.
- LRR-002 and LRR-004 close the biggest semantic mismatch with Honcho.
- LRR-005..LRR-007 convert implementation into auditable readiness.
