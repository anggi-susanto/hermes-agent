---
name: hxp-board-governance-review
description: Review Hermes x Paperclip CEO/program updates, distinguish planning closure from execution sufficiency, verify code/proof against milestone claims, and draft next-step governance tasks.
---

# HxP board governance review

Use this when reviewing Hermes x Paperclip (HxP) updates from the CEO/Paperclip side, especially when they claim:
- a planning issue can close
- execution has started
- a milestone is complete
- a code drop proves a lane or milestone
- the roadmap is ready to close

This skill captures the reusable governance posture that worked in HxP:
- execution visibility is different from staffing completeness
- a lane/ticket existing is different from milestone proof
- Paperclip completion/progress artifacts never bypass Hermes verification or repo-finalization honesty

## Core review rules

1. Separate the claim types
   - Administrative closure: a plan/parent issue can close if its original scope was planning/definition.
   - Execution sufficiency: separate question. Closing planning does NOT mean the execution pack is complete.
   - Milestone completion: separate again. Open lanes/tickets and passing local tests do NOT alone prove the milestone.

2. Always ask these three questions
   - Is the original parent scope actually fulfilled?
   - Are all milestone-critical lanes visible at issue level?
   - Is there real behavior proof, not just scaffolding/docs/tests-in-isolation?

3. Preserve the HxP constitutional boundary
   - API-native only
   - polling only
   - text-first evidence
   - no browser automation
   - no mirror-as-proof semantics
   - no path where Paperclip completion becomes Hermes acceptance automatically
   - repo finalization honesty remains mandatory for repo-backed closure

4. Distinguish execution visibility from staffing completeness
   - It is acceptable for lanes to be `pending staffing`, `unassigned`, or `blocked on staffing`.
   - It is NOT acceptable for milestone-critical work to remain implicit or invisible.
   - Unfilled roles must stay explicit, not silently absorbed into “engineering”.

## Review workflow

### A. If reviewing a CEO update / issue closure
1. Read the claimed result carefully.
2. Compare it to the original parent issue scope.
3. Classify the verdict:
   - approve
   - approve as administrative closure only
   - approve only in part
   - reject / insufficient
4. Check whether milestone-critical lanes are explicitly opened as issues.

For HxP M1-style execution packs, minimum visible lanes are:
- Lane A: adapter skeleton / provider contracts
- Lane B: polling sync + normalization
- Lane C: acceptance gate + reconciliation
- Lane D: QA / live proof
- Lane E: docs / rollout / closeout artifacts

If only one lane exists, do NOT accept it as a complete execution decomposition.

### B. If reviewing a commit/code drop
1. Fetch or pull first if the commit is missing locally.
2. Inspect stat and patch.
3. Run the repo’s authoritative test command immediately.
4. Classify the result by lane/milestone, for example:
   - “strong Lane A drop”
   - “real progress, but not full M1”
5. Look for governance-sensitive footguns:
   - naming or helpers that imply auto-accept too early
   - status mappings that could collapse `submitted` into `accepted`
   - fake health reporting
   - docs that overclaim what tests actually prove

### C. If asked to create the next CEO task
Draft a task that does ALL of these:
1. Reconciles current repo/issue state against the governing roadmap or plan.
2. States what is materially complete already.
3. States what is still not honestly claimable as complete.
4. Converts remaining material gaps into explicit deliverables/issues.
5. Keeps staffing truth explicit.
6. Defines final closeout artifacts and repo-finalization requirements.

## Standard verdict patterns

### 1. Planning issue closure is okay, but execution conversion is incomplete
Use when the plan can close but only one lane/ticket was opened.

Key language:
- “HXP-27 closure is accepted as administrative closure of the planning issue.”
- “The current one-ticket launch is not accepted as a complete execution decomposition for M1.”
- “Unfilled ownership is acceptable. Invisible scope is not.”

### 2. Execution decomposition is now sufficient
Use when all milestone-critical lanes are visible, even if some are pending staffing.

Key language:
- “The program now distinguishes execution visibility from staffing completeness.”
- “Some lanes are active, while others remain explicitly pending staffing.”
- “Visible lane structure does not relax the milestone proof standard.”

### 3. Code drop is good, but not milestone-complete
Use when tests pass and the lane implementation is real, but live/end-to-end proof is still incomplete.

Key language:
- “Approve as a strong Lane A implementation drop, but do not yet treat it as completion of M1.”
- “This is real progress, not final milestone proof.”

## Template phrases that worked well

- “Lane A alone is not the milestone.”
- “Execution visibility is different from staffing completeness.”
- “Open the remaining execution lanes explicitly, even if some remain unassigned pending staffing.”
- “Do not confuse visible lane structure with milestone completion.”
- “This is a start, not a sufficient breakdown for M1.”

## What to require before roadmap closeout
Before saying the roadmap is complete, require:
- milestone-by-milestone reconciliation against actual repo state
- explicit classification: complete / materially complete pending closeout / partially complete / open / intentionally deferred
- final staffing truth table
- final issue/status map
- final closeout note
- final repo-finalization note
- explicit deferred-items appendix if anything remains outside scope

## Final closeout reconciliation pattern
Use this when the repo has already landed the last closeout artifacts and the question becomes “is there any real work left, or just parent closure?”

1. Pull latest main and rerun the authoritative test command.
2. Read the latest closeout artifacts, especially:
   - final milestone closeout note
   - final roadmap closeout pack
   - parent-program reconciliation plan or program note
3. Check for artifact drift:
   - docs still saying `materially complete pending closeout artifacts` after those artifacts have landed
   - issue/status maps that still show closeout children as `in_progress` even though their files now exist in repo
4. If the drift has been reconciled and no roadmap workstream remains open, the correct next action is usually:
   - close the parent program/roadmap issue cleanly
   - state that future work must open as a new phase, not as unfinished roadmap debt
5. Do NOT invent new roadmap tasks once the remaining work is only closure/admin reconciliation.

### Standard final parent-close language
Use language like:
- “the roadmap is complete as scoped”
- “no roadmap workstream remains open within the approved scope”
- “deferred items remain explicitly outside the completed roadmap boundary”
- “any further work should be opened as a new phase or expansion track, not presented as unfinished work from this roadmap”

## Anti-patterns

Reject or push back when you see:
- one lane opened and presented as full execution conversion
- milestone completion claimed from scaffolding/tests alone
- unfilled QA/verification roles disappearing into vague ownership
- passing tests treated as proof of live milestone behavior without artifact evidence
- board closure or Paperclip `done` being treated as repo-finalization truth

## Output style
Write board-review comments in concise, firm language. Prefer:
- clear verdict first
- why it passes/fails
- exact correction required
- restatement that the milestone standard remains unchanged
