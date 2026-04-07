---
name: git-partial-commit-dirty-file
description: Create a clean commit from only selected hunks when a file already has unrelated dirty changes, then verify the staged snapshot and push safely.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [git, partial-commit, patch-staging, dirty-files, index-management]
---

# Git Partial Commit from a Dirty File

Use this when:
- the repo already has unrelated dirty changes
- the user wants a clean commit for only one logical slice
- a target file mixes desired edits with unrelated modifications
- normal `git add <file>` would accidentally stage too much

## Goal

Produce a commit that contains only the intended logical change, even if the same file has additional unstaged or unrelated edits.

## Preferred escalation order

1. Try simple staging first if the target change is already isolated in separate files.
2. If one file mixes multiple changes, use `git add -p` and selectively stage hunks.
3. If `git add -p` is insufficient because the desired hunk is entangled with unrelated edits, write the exact desired blob into the index with `git update-index --cacheinfo` while keeping the working tree untouched.

## Workflow

1. Inspect repo state.
   - Run `git status --short`
   - Run `git diff --stat`
   - Identify which files are safe to include and which must stay out.

2. Verify only the relevant tests for the slice before committing.
   - Example: run the narrow pytest target or other focused validation.
   - Do not block on unrelated failing dirty files if the user asked for a clean isolated commit.

3. Stage clean files normally.
   - Use `git add path/to/file` for files that only contain the intended change.

4. For mixed files, try interactive hunk staging.
   - Run `git add -p path/to/file`
   - Answer `y` only for the intended hunk(s), `n` for unrelated hunks.
   - Afterward inspect with `git diff --cached -- path/to/file`

5. If hunk staging cannot isolate the desired change, stage a synthetic index-only version.
   - Read the committed `HEAD` version of the file.
   - Programmatically apply only the desired logical edits to that `HEAD` content.
   - Write the resulting content to a temporary file.
   - Store that blob with `git hash-object -w <tmpfile>`
   - Replace the index entry only:
     `git update-index --cacheinfo 100644,<sha>,path/to/file`
   - This creates a staged snapshot that differs from both `HEAD` and the working tree, which is exactly what you want for a clean split commit.

6. Verify staged content explicitly.
   - `git diff --cached --stat`
   - `git diff --cached -- path/to/file`
   - `git status --short`
   - Watch for `MM path/to/file` meaning: staged changes exist and additional unstaged edits remain. This is acceptable if intentional.

7. Commit and push.
   - Use a commit message scoped only to the staged slice.
   - Push to the requested remote/branch.

## Verification checklist

Before committing, confirm:
- staged diff contains only the intended slice
- unrelated dirty files remain unstaged
- focused tests for the slice pass
- commit message matches only what is staged

## Useful commands

Inspect:
```bash
git status --short
git diff --stat
git diff --cached --stat
git diff --cached -- path/to/file
```

Interactive staging:
```bash
git add -p path/to/file
```

Index-only staging via synthetic blob:
```bash
git show HEAD:path/to/file > /tmp/basefile
# edit /tmp/desiredfile so it contains only the intended slice
sha=$(git hash-object -w /tmp/desiredfile)
git update-index --cacheinfo 100644,$sha,path/to/file
```

## Pitfalls

- Do not use `git add path/to/file` on a mixed file unless you really want every change in it.
- `git add -p` may still be too coarse when unrelated edits are in the same hunk.
- `git diff` shows working tree changes; `git diff --cached` shows what will actually be committed. Always inspect the cached diff before committing.
- After index-only staging, the working tree may still contain unrelated edits. That is fine; just make sure the staged diff is correct.
- If file mode or symlink state matters, adjust the `git update-index --cacheinfo` mode accordingly instead of blindly using `100644`.

## When this skill helped

This approach was useful when splitting a clean gateway quick-command commit out of `gateway/run.py` even though the file already contained large unrelated document/OCR modifications and `git add -p` alone was not enough for the final clean staged snapshot.
