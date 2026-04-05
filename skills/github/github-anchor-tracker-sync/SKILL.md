---
name: github-anchor-tracker-sync
description: Turn a tracker document with stable anchor IDs into GitHub child issues plus an epic, then backlink the tracker safely.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitHub, Issues, Tracking, Docs, Re-anchor, Governance]
    related_skills: [github-issues, workspace-target-verification]
---

# GitHub anchor tracker sync

Use this when a repo already has a local tracker/spec document with stable anchor IDs (for example `HRB-001`, `HRB-002`, etc.) and the user wants it made issue-ready in GitHub with durable re-anchor support.

This is not generic issue creation. It is specifically for:
- creating one child issue per anchor
- preserving stable anchor IDs in issue titles/bodies
- creating one epic/parent issue linking the child issues
- updating the local tracker doc with backlinks to the GitHub issues
- auditing stale-open / stale-closed drift between tracker status, shipped repo truth, and GitHub issue state

## When to use

Trigger this skill when all or most of these are true:
- the user asks to "gas bikin issue" or similar
- the source doc already contains stable anchors and acceptance criteria
- the user wants safe anchor/re-anchor handling later
- the repo uses issue-centric governance or milestone planning
- the user asks for a sweep to reconcile tracker status vs GitHub issue state vs current repo reality

## Preflight

1. Verify repo target first.
   - Run:
     - `pwd`
     - `git branch --show-current`
     - `git remote -v | head`
     - `git status --short`
   - Confirm you are in the intended repo before creating issues.

2. Confirm GitHub auth.
   - Run `gh auth status`.
   - Note which account is logged in. Issue authorship will use that account even if the target repo belongs to another org/user.

3. Check existing labels.
   - Run `gh label list --limit 200`.
   - Map desired labels to labels that already exist in the repo. Do not invent label names blindly unless the task explicitly includes label creation.

4. Check for pre-existing issues.
   - Search with `gh issue list --state all --search 'HRB-'` or anchor-specific terms.
   - Avoid duplicate anchor issues.

## Source doc expectations

The tracker works best if each anchor already has:
- Anchor ID
- title
- dependencies
- problem
- objective
- scope
- deliverables
- acceptance proof
- anti-bullshit notes

If those sections already exist, do not over-rewrite them. Reuse them.

## Child issue creation workflow

Before creating anything, check whether the sync already happened.

Audit-first checks:
- search GitHub for the anchor range and epic title
- read the tracker header/master table to see whether issue backlinks already exist
- compare tracker status (`Done` / `Partial` / `In Progress`) against current issue state (`OPEN` / `CLOSED`)
- inspect recent commits / tests / docs so you know whether repo truth matches the tracker or the issue
- if the issues and backlinks already exist, switch to verification-only mode instead of recreating anything
- if tracker says `Done` and repo proof still supports that state, prefer comment + close instead of opening replacement issues or rewriting the tracker again

1. Read the tracker and extract the top-level anchors in order.
2. Build one issue body per anchor with this shape:
   - Anchor ID
   - Source doc links
   - Problem
   - Objective
   - Scope
   - Non-goals
   - Dependencies
   - Deliverables
   - Acceptance proof
   - Anti-bullshit notes
   - Evidence / test requirements
   - Re-anchor notes
3. Preserve the anchor ID in the issue title, e.g.:
   - `HRB-001: Truth contract foundations`
4. Create issues in the intended order so numbers stay sequential and easy to reason about.
5. Record the created issue numbers and URLs immediately.

## Epic issue creation workflow

After child issues exist:
1. Create one epic parent issue.
2. Include:
   - epic anchor ID if relevant
   - source docs
   - program objective
   - success criteria
   - checklist of child issues
   - execution order
   - dependency / parallelism notes
   - re-anchor rules
   - anti-bullshit close
3. Add a stable child checklist like:
   - [ ] #20 — HRB-001: ...
   - [ ] #21 — HRB-002: ...

## Backlinking the tracker doc

Update the tracker doc after GitHub issue creation, not before.

Recommended backlink points:
1. Add epic parent issue near the master tracker header.
2. In the master table, link each anchor cell to its issue number.
3. In each anchor section, add an `Issue:` line directly below the label/dependency metadata.
4. In any “issue creation order” section, replace plain anchor text with links to the created issues.

## Practical editing advice

For large doc-wide backlink insertion, full-file rewrite can be safer than repeated regex patching.

Why:
- anchor headings and spacing may vary
- repeated fuzzy patches can fail halfway
- markdown tables + repeated headings are brittle for regex-heavy automation

Recommended pattern:
1. Read enough of the file to inspect the exact current formatting.
2. If targeted patching becomes brittle, rewrite the full file content with the backlink changes applied cleanly.
3. Re-read key sections after writing to verify the result.

## Gotchas learned in practice

### 1. Epic creation can partially succeed before later automation fails
If your next automation step crashes, do not assume the epic was not created.
Always verify with `gh issue list --state open --search 'EPIC title'` before retrying, or you may duplicate the parent issue.

### 2. Logged-in GitHub account may differ from repo owner
That is fine if permissions allow it, but disclose it in the summary so the user is not surprised by authorship.

### 3. Repo labels are often narrower than your tracker vocabulary
Map to existing labels pragmatically. Preserve semantic structure in the issue body even if the exact label names do not exist.

### 4. Sequential numbering matters for human operability
If the tracker is meant to be a durable control surface, create child issues in the planned order before the epic, or at least keep numbering/order easy to follow.

### 5. Existing tracker backlinks are a strong signal that sync already happened
If the master tracker already has an epic backlink, the anchor rows already point at issue numbers, and each slice section already has an `Issue:` line, do not create anything new blindly. Treat the job as audit/verification unless the user explicitly wants regeneration.

### 6. Verify the doc after backlink insertion or after an audit-only pass
At minimum, re-read:
- the master tracker section
- the first anchor section
- the issue creation order section
- the epic issue body

## Verification checklist

Before declaring done, verify:
- target repo is correct
- issue search showed no accidental duplicates
- all child issues exist and are open
- epic exists and links all child issues
- tracker doc shows epic backlink
- tracker master table shows anchor backlinks
- each anchor section has its per-issue backlink
- issue creation order section links to the created issues

For reconciliation / sweep mode, verify instead:
- target repo is correct and worktree state is known
- tracker status, issue state, and current repo truth were all checked explicitly
- when closing a stale-open issue, the closing comment cites concrete repo truth (commits, tests, docs, or shipped surfaces)
- after closeout, `gh issue list --state all` reflects the expected remaining open anchors
- if all child anchors are closed but the epic/parent is still open, explicitly call that out as a separate governance choice instead of pretending the sweep is incomplete; offer epic closeout/commenting as the next logical step
- no local file drift was introduced if the sweep was GitHub-only

## Output summary format

Give the user:
- epic issue number + URL
- child issue range + URLs
- tracker doc path
- note on which GitHub account authored the issues if relevant
- any notable caveat, especially if one step partially succeeded and needed verification

## Anti-patterns

Do not:
- create issues before checking you are in the right repo
- retry epic creation blindly after a failed automation step
- claim the tracker is linked without re-reading the updated sections
- mark the job done when the issues exist but the local tracker still has no backlinks
