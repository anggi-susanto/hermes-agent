---
name: architecture-note-to-issue-tracker
description: Convert a corrected architecture/re-audit note into a repo-native tracker doc plus GitHub epic/child issues with stable anchors, dependencies, acceptance proof, and anti-bullshit guardrails.
---

# Architecture Note → Issue Tracker

Use this when the user has an architecture note, boundary verdict, or re-audit conclusion and wants it turned into concrete task breakdown + GitHub issues.

Typical triggers:
- “mulai buat task breakdown dan github issues”
- “ubah hasil audit jadi backlog”
- “bikin epic + child issues dari dokumen ini”
- a re-audit changed the conclusion and now needs an executable tracker

## Goal

Turn prose-heavy architecture conclusions into:
1. a repo doc with stable anchor IDs and issue-ready slices
2. a GitHub epic issue
3. GitHub child issues derived from the slices
4. synchronized README/doc references if the new tracker should be discoverable

## Preconditions

- Verify the target repo/workspace first.
- Check whether a related tracker already exists before creating a new one.
- Check open/closed GitHub issues to avoid duplicate epics.
- Read the source architecture/re-audit note and any existing tracker docs.

## Recommended document set

When the source note is trying to freeze a corrected product/architecture flow and avoid future semantic drift, do **not** jump straight to a tracker.

Create a two-doc set under `docs/`:

1. **Canonical plan doc** — the anti-drift source of truth
2. **Issue tracker doc** — the execution/handoff surface derived from the canonical plan

### 1) Canonical plan doc

Use this first when the user is really saying:
- “clarify the real linear flow”
- “document all the answers so they don’t drift”
- “freeze what is proven vs missing before implementation starts”

Recommended sections:
1. `Goal`
2. `Non-goals`
3. `Canonical user story`
4. `The linear flow this plan standardizes`
5. `Current truth snapshot`
   - what is already proven live
   - what is not yet proven
6. `Readback truth hierarchy`
7. `Stable anchor map`
8. one section per anchor with:
   - Problem
   - Objective
   - Scope / desired flow
   - Acceptance proof
   - Anti-bullshit notes
9. `Dependency order`
10. `Recommended implementation sequence`
11. `Concrete blocker-closure mapping`
12. `Definition of done for the whole plan`
13. `Changelog / status updates`

Important pattern:
- if there are multiple valid entry points (for example asset-first vs generate-first), preserve **all** of them in the canonical plan even if only one is implemented today
- explicitly separate `proven live today` from `intended product flow`
- record exact currently proven write surfaces when discovered experimentally (example: `PUT /releases/{id}/seo` works, but cover-art readback URL is still missing)

### 2) Issue tracker doc

Derive this from the canonical plan, not directly from chat.

Recommended sections:
1. `Canonical source docs`
2. `Status vocabulary`
3. `Master tracker`
4. `Issue-ready task packs`
5. `Cross-lane execution plan`
6. `Parallelization rules`
7. `Re-anchor protocol`
8. `Closeout comment template`
9. `Initial tracker status note`

Each slice should include:
- Status
- Owner lane
- Dependencies
- Recommended labels
- Issue link (initially TBD, then backfilled)
- Problem
- Objective
- Scope
- Deliverables
- Acceptance proof
- Anti-bullshit notes

Strong recommendation:
- use a **closed status vocabulary** like `Pending`, `In Progress`, `Partial`, `Blocked`, `Split`, `Done`, `Dropped`
- add a **re-anchor protocol** so future sessions can resume without chat archaeology
- add a **closeout template** so no anchor gets marked done from vibes

## Anchor pattern

Use a short stable prefix tied to the initiative, e.g.:
- `HRB-*` for Hermes Runtime Boundary
- `OMB-*` for OpenClaw MCP Boundary

Rules:
- parent slices get top-level anchors like `OMB-001`
- follow-up splits use suffixes like `OMB-002.A`
- never silently delete a parent after splitting; mark it split and link children

## Execution workflow

1. Read the source note and pull out the corrected verdict.
2. Separate:
   - proven truths
   - missing proof
   - implied implementation consequences
3. Translate those into 3-7 issue-worthy slices.
4. Write the tracker doc first.
5. If appropriate, patch `README.md` or canonical docs lists so the tracker is discoverable.
6. Create the epic issue.
7. Create one child issue per slice using the doc text as the source.
8. Backfill issue links into the tracker doc.
9. Commit and push if the user expects autonomous docs/commit/push.

## Practical GitHub pattern

- Create the epic first so child issues can reference it.
- Put `Parent epic: #NN` in each child issue body.
- Use existing repo labels where possible; do not invent new labels unless needed.
- After issue creation, update the tracker doc from `Issue: TBD` to actual links.

## Anti-bullshit rules

- Do not create slices that are only slogans like “make runtime thinner”.
- Every slice must have a falsifiable acceptance proof.
- Explicitly preserve uncertainty from the source note; do not flatten provisional claims into certainty.
- If the source problem was overconfident auditing, add a dedicated guardrail/docs slice.
- If the issue depends on controller-side truth, say so explicitly; do not rely on route names alone.
- If a draft slice says "what endpoint transitions X -> Y?", verify that an explicit endpoint really exists before freezing tracker wording. If code truth shows Y is a derived state (for example `status=ready` causing lifecycle `prepared`), rename the slice from `transition endpoint` to `transition truth` or `transition mechanism`.
- When correcting that kind of semantic drift, patch all linked docs inline (canonical plan, tracker doc, proof pack/implementation note) so the board cannot keep repeating the wrong mental model.
- Prefer attaching one focused regression test that encodes the derived-state semantics, especially when live/staging proof is not yet attached. Example pattern: prove the concrete write path that sets the persisted field, then prove the readback/lifecycle projection that derives the user-facing state.
- If local PHPUnit execution is blocked by environment issues, still run syntax-level checks where possible and record the limitation explicitly instead of pretending tests passed.

## Good slice themes for architecture follow-up

Common reusable slices:
- capability/authority matrix
- source-of-truth audit
- intent-to-operation mapping
- implementation backlog for affected components
- docs/reviewer guardrails

## Verification checklist

Before finishing, confirm:
- tracker doc exists and is readable in-repo
- epic issue exists
- all child issues exist
- tracker doc links to the issues
- dependencies are coherent
- acceptance proof and anti-bullshit notes exist for every slice
- git status is clean or intentionally committed/pushed

## Example outcome

For a re-audit that says “backend authority is fatter than we thought; runtime should be thinner”, the resulting slices often look like:
1. capability matrix
2. authority/publish-truth audit
3. intent routing matrix
4. runtime/wrapper slimming plan
5. docs + anti-bullshit guardrails
