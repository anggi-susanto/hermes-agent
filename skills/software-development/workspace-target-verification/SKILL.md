---
name: workspace-target-verification
description: Verify the active repo/workspace matches the user's intended target before auditing, editing, testing, committing, or pushing.
---

# Workspace Target Verification

Use this whenever the user asks for repo-specific work (audit docs, implement code, run tests, commit/push) and there is any chance the current session context, AGENTS.md, or loaded project files belong to a different repository than the one the user intended.

This is especially important in multi-repo environments, monorepos with nested apps, or when the chat/project context may have been opened from a different root.

## Trigger conditions

- The user names a specific repo/app/workspace (`centracast-runtime`, `centracast`, `hermes-agent`, etc.)
- The current conversation contains project context for one repo, but the user request appears to target another
- You are about to modify docs/code, run tests, or commit/push
- The filesystem contains multiple sibling repos/workspaces

## Goal

Catch repo-target mismatches before making changes.

## Procedure

1. Confirm the intended target from the user message.
   - Extract the exact repo/app name and expected path if provided.
   - Do not assume the loaded AGENTS.md or project context is the correct target.

2. Inspect the active location before touching files.
   - Run:
     - `pwd`
     - `git branch --show-current`
     - `git remote -v | head`
     - `git status --short`
   - If needed, list likely sibling workspaces with file tools or shell commands.

3. Compare what you found against the user's intended repo.
   - Check repo name, remote URL, and top-level files/directories.
   - Also check whether the current branch matches the user's requested branch or default branch preference.
   - If the user expects `centracast-runtime` but the current repo is `hermes-agent`, stop and correct course immediately.
   - If the repo is correct but the branch is not (for example you're on `staging` while the user expects direct work on `main`), correct that before editing unless there is a deliberate reason not to.

4. Check for pre-existing dirty state before editing.
   - Review `git status --short` closely, not just repo identity.
   - Separate files that are already dirty from files you plan to touch.
   - If unrelated dirty files exist, treat them as a blast-radius constraint: avoid editing them unless the task explicitly requires it.
   - If tests fail later, do not assume your change caused the failure when pre-existing dirty files or broader in-flight changes are present.

5. Only after repo identity, branch target, and dirty-state boundaries are confirmed, begin the real task.
   - Then audit files, patch docs/code, run tests, and commit.
   - Prefer scope-local tests first when the repo already has unrelated dirty files.
   - If you discover the intended changes already exist as uncommitted work on the wrong branch, preserve them carefully: either switch before editing if clean, or commit on the current branch only as a temporary safety step and immediately cherry-pick or recreate on the correct branch.

6. Before commit/push, verify again.
   - Re-check `git status --short` and ensure modified files belong to the intended repo only.
   - Re-check `git branch --show-current` and make sure the final commit is landing on the branch the user actually wanted.

## Recovery if you already changed the wrong repo

1. Stop further edits immediately.
2. Report the mistake clearly and explicitly.
3. Check whether anything was pushed.
   - If not pushed, say so.
4. Preserve the commit hash if one exists.
5. Ask or default to a safe cleanup plan:
   - reset/revert the mistaken local commit
   - switch to the correct repo
   - redo the task in the correct workspace

## Example quick preflight

```bash
pwd
git branch --show-current
git remote -v | head
git status --short
```

## Repo-mapping nuance for CentraCast wave work

When the user references OMB/HRB wave language without naming the repo explicitly, verify the wave-to-repo mapping before acting.

Reusable mapping learned in practice:
- Wave B / renderer-hardening / Telegram proof-wording work usually targets `centracast-runtime`
- Wave C / backend publish-read truth improvement usually targets `centracast` (Laravel/OpenClaw backend)

Do not let the currently loaded AGENTS/project context decide this by inertia. In this environment it is easy to be sitting inside one repo while the requested wave logically belongs to its sibling.

## Repo-mapping nuance for CentraCast AF anchor packs

When the user says a short command like `gas AF-002 pack` or `gas AF-005 pack`, do not assume the current repo or the most recently edited pack is the correct target. Verify the anchor's ownership lane from the tracker/plan and then confirm the sibling repo before writing files.

Reusable mapping learned in practice:
- `AF-002` (asset-first release flow runtime ownership) usually belongs in `centracast-runtime`
- `AF-005` (release lifecycle transition + direct YouTube upload proof) usually belongs in `centracast`
- `AF-006` (runtime provider/orchestrator ownership of release lifecycle) usually belongs in `centracast-runtime`

Recommended preflight for AF pack work:
1. Read the tracker row / child anchors for the requested AF anchor.
2. Inspect both sibling repos' git identity and dirty state if there is any ambiguity.
3. Prefer placing the pack in the repo that owns the implementation/proof lane, even if the canonical tracker lives in the sibling repo.
4. In the new pack, explicitly link back to the canonical tracker/plan across repos so the split remains honest.

This prevents a subtle failure mode: creating a strong issue pack in the wrong repo simply because the last pack was authored there.

## Pitfalls

- Trusting loaded project context more than the user's explicit repo name
- Assuming the current working directory is the intended workspace
- Letting wave/epic shorthand implicitly select the repo without checking the actual wave scope
- Committing doc/code changes before checking the repo remote/name
- Discovering the mismatch only after a failed push

## Success criteria

- Repo identity is verified before edits
- Tests and commits happen only in the intended repo
- If a mismatch occurs, it is contained locally and disclosed immediately
