---
name: master-brief-consolidation
description: Consolidate scattered project docs into one readable master brief with summary, roles, prioritized tasks, assignees, and source references.
---

# Master Brief Consolidation

Use this when the user is overwhelmed by scattered context and wants “one .md file” that is easy to read without scrolling through many files.

This is especially useful when the repo already has separate docs for:
- summaries / executive memos
- role definitions
- priority matrices
- assignment drafts
- ticket trackers
- roadmap / sprint order

## Trigger conditions

- User asks for “1 file .md komplit”, “single brief”, “master brief”, “gabungin semua”, or similar
- There are multiple overlapping docs and the user wants one readable source
- The user wants summary + roles + prioritized task list + assignee + detail in one place
- There is risk of using the wrong project/session as reference context

## Goal

Produce a single markdown file that:
1. Uses the correct project/workspace as the reference base
2. Merges the most relevant docs into one readable structure
3. Preserves priority order and assignee ownership
4. Makes source references explicit
5. Reduces the need to scroll between many files

## Procedure

1. Verify the target workspace first
   - Do not assume the currently loaded conversational context is the correct target.
   - Prefer explicit project docs over cross-session summaries if the user says “reference it here” or redirects the target.
   - If needed, load `workspace-target-verification` skill first.

2. Find the relevant document set
   - Search the target workspace for markdown files.
   - Prioritize docs that cover:
     - summary / executive view
     - role map / skill matrix
     - requirements / operating principles
     - priority matrix
     - assignment draft
     - sprint order / roadmap
     - tracker / ticket breakdown

3. Read only the docs needed to reconstruct the operating picture
   - Avoid dumping every file.
   - Pick the minimum set that answers:
     - what this initiative is
     - what roles exist
     - what should be done first
     - who owns each lane
     - what “done” means
     - what references back the merged brief

4. Reconcile contradictions explicitly
   - Historic trackers may say many items are DONE while planning docs still define canonical priority order.
   - In the master brief, keep both truths separate:
     - current reality / historical tracker snapshot
     - canonical priority / dependency order for understanding the system
   - Do not silently flatten these into one ambiguous statement.

5. Write the master brief in a reading-first structure
   Recommended structure:
   - Title / status / owner / audience / purpose
   - Executive Summary
   - Current Reality Snapshot
   - Operating Principles
   - Role Map
   - Assignee Model by Lane
   - Priority-Ordered Task List
   - Task Details by Wave
   - Success / Truth Rules
   - Quick Reading Order
   - Source References Used
   - Super Short Version

6. Prefer lane-based assignees when named humans are not fixed
   - Example assignees:
     - Provider / Backend Control Plane
     - Runtime / Orchestration Builder
     - Dev-Bridge
     - QA / Verification
     - Docs / Continuity
   - This keeps the document reusable even when staffing changes.

7. Make the output blunt and low-friction to scan
   - Use short sections
   - Use numbered lists for priority order
   - Use explicit “Why now” / “Definition of done” where helpful
   - End with exact source file references used for consolidation

## Important rules

- Do not accidentally reference the wrong project just because a recent session mentioned it.
- If the user corrects the reference target mid-task, pivot immediately and rebuild from the correct workspace docs.
- Do not pretend a tracker is the same thing as the canonical plan; trackers show execution history, plans show intended dependency order.
- Keep the consolidated brief readable first, exhaustive second.
- If the user expects issue-tracker-ready output (for example numbered issue packs, exact titles/bodies, assignees/reviewers), do not assume workspace docs alone are sufficient. Check whether some of that material came from chat-drafted content rather than repo files.
- When chat-sourced issue drafts are missing from the workspace, explicitly say so in the consolidated brief instead of silently omitting them.
- In that situation, create a separate reconstructed issue-pack markdown file rather than stuffing speculative issue text into the main master brief.

## Good output characteristics

A strong master brief should let the user answer these quickly:
- What is this project trying to do?
- What roles exist and what do they do?
- What should happen first, second, third?
- Who owns each lane?
- What rules define truthful completion?
- Which docs back this summary?

## Pitfalls

- Pulling references from the wrong repo or previous conversation
- Copying too many raw sections instead of synthesizing
- Losing assignee clarity
- Mixing current status with canonical order without explanation
- Omitting source references, which makes future refreshes painful

## Success criteria

- One markdown file exists in the target workspace
- It contains summary, roles, prioritized task list, assignee mapping, and task detail
- The references are explicitly tied to the correct workspace docs
- The user can read one file instead of scrolling through many
