---
name: centracast-anchor-issue-closeout
description: Audit a CentraCast runtime anchor issue against repo reality, sync tracker/docs honestly, then comment and close only if acceptance is truly satisfied.
---

# CentraCast Anchor Issue Closeout

Use this when the user says things like:
- "sikat HRB-003"
- "close issue X if repo truth is satisfied"
- "review tracker vs code reality"
- "mark anchor done honestly"

This skill is for anchor-driven closeout in `centracast-runtime`, especially when the issue/tracker may be stale relative to the code.

## Why this exists

In this repo, issues, tracker docs, and code reality can drift.
A parent anchor may stay open even though later child anchors or downstream work already satisfied the original acceptance.
Do not close based on vibes. Do not leave it stale if the repo already crossed the finish line.

## Goal

Determine whether an anchor issue is truthfully done, then make the repo + issue tracker consistent:
1. inspect issue acceptance criteria
2. inspect tracker status/progress note
3. inspect actual code/docs/tests
4. run proof tests
5. if satisfied, update tracker/doc wording first
6. commit/push
7. comment proof on the issue
8. close the issue

If not satisfied, leave it open and comment the remaining gap honestly.

## Procedure

1. Preflight repo identity
   - Confirm you are in the intended repo/worktree.
   - Check branch and dirty state first.
   - Prefer `main` when the user wants direct closeout in this repo.

2. Read the issue directly
   - Use `gh issue view <num> --json ...`.
   - Extract:
     - problem/objective/scope
     - acceptance proof bullets
     - anti-bullshit notes
     - comments that redefine scope or split child anchors

3. Read the tracker doc section for the anchor
   - Usually `docs/HERMES-RUNTIME-BOUNDARY-IMPLEMENTATION-TRACKER.md`.
   - Read both:
     - the summary table row
     - the full anchor section
   - Look for stale wording like "Partial" or progress notes that no longer match repo reality.

4. Audit repo truth against acceptance
   - Search for the exact code path that should satisfy the anchor.
   - Prefer direct proof locations:
     - orchestrator entrypoint / routing logic
     - inspect/fulfillment surfaces
     - contract docs
     - regression tests that explicitly name the scenario
   - Map acceptance bullets to concrete files and line ranges.

5. Run proof tests when the anchor is code-bearing
   - If the anchor closes via runtime/code behavior, run the relevant test suite or targeted proof tests.
   - Record exact pass/fail counts.
   - If the issue is about routing/authority behavior in code, make sure at least one regression test proves the conflict case, not only the happy path.
   - If the anchor is documentation-only by scope (for example a matrix/tracker/doc deliverable), repo-proof can be the landed docs themselves plus tracker synchronization and issue-body acceptance matching; do not invent meaningless test runs just to satisfy ritual.

6. Decide honestly
   - Close only if the current repo truth satisfies the issue's stated acceptance.
   - Important: if the old tracker says "remaining work" but that work is now actually covered by later anchors already marked done, reconcile the parent honestly instead of repeating stale wording.
   - If acceptance is still not met, do not force closure; comment the exact gap.

7. Sync tracker/docs before closing
   - Update the tracker table row status.
   - Update the full anchor section status.
   - Rewrite the progress note so it explains why the anchor is now done in present repo reality.
   - If prior text said work remained, explicitly explain whether that work:
     - is still open, or
     - actually belongs to later anchors that already landed.
   - If there is a repo-level audit summary (for example `AUDIT-*.md`), refresh it too so AF-007/AF-008 style status nuance is captured in one reviewer-facing place, not only buried in tracker rows.
   - Be careful to distinguish:
     - missing implementation
     - missing live proof
     - missing proof-packaging / reviewer-readable closeout mapping
     These are not the same thing, and AF-008-style anchors often fail because reviewers collapse them together.

8. Commit and push the tracker/doc sync
   - Make a small, honest commit just for tracker closeout if possible.
   - Push to the repo branch the user expects.

9. Comment on the issue with proof
   - Include:
     - why it is now done
     - exact proof files/functions/tests checked
     - test command + result count
     - tracker-sync commit hash
   - Keep the comment crisp but evidence-backed.

10. Close the issue
   - Use `gh issue close <num> --comment ...` after the proof comment is in place.

## Recommended evidence format

Use this structure in the issue comment:
- repo reality sweep complete
- why this is truthfully done
- concrete proof checked in repo
- verification run
- tracker sync commit
- net conclusion

## Pitfalls

- Closing because child work exists somewhere nearby without mapping it to the parent's acceptance
- Trusting stale tracker wording more than current code/tests
- Updating issue status without syncing the tracker doc
- Claiming done without a live test run in the current HEAD
- Forgetting that a parent anchor can become truthfully done after downstream anchors land

## Success criteria

- Issue acceptance is mapped to concrete repo evidence
- Tracker wording matches actual code reality
- Proof tests are run and reported with exact counts
- Issue comment cites real files/tests, not vague summaries
- Issue is closed only when repo truth actually satisfies the anchor
