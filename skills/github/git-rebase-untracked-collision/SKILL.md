---
name: git-rebase-untracked-collision
description: Safely rebase a branch when Git blocks on untracked files that would be overwritten, then verify whether the stash is still needed.
---

# Git Rebase with Untracked-File Collision

Use this when `git rebase <base>` fails with:
- `The following untracked working tree files would be overwritten by checkout`
- `Please move or remove them before you switch branches`
- often followed by `could not detach HEAD`

## Goal

Finish the rebase without losing local untracked artifacts, and avoid blindly restoring redundant stash contents afterward.

## Procedure

1. Confirm branch and workspace state first.
   - Run:
     - `git status --short`
     - `git branch --show-current`

2. If rebase is blocked by untracked files, stash including untracked files.
   - Command:
     - `git stash push -u -m 'hermes-temp-pre-rebase-YYYY-MM-DD'`
   - Important: use `-u` or the blocking files stay in place.

3. Retry the rebase.
   - Example:
     - `git rebase origin/main`

4. After success, do NOT assume `git stash pop` will cleanly restore.
   - If the rebased branch now contains tracked files at the same paths, `stash pop` may fail with many `already exists, no checkout` messages.
   - In that case Git usually keeps the stash entry.

5. Inspect whether the stash is still meaningful before dropping or restoring manually.
   - Show stash list:
     - `git stash list`
   - Compare path sets between HEAD and the stash's untracked parent:
     - `git rev-parse stash@{0}^3`
     - `git ls-tree -r --name-only HEAD <path-prefix>`
     - `git ls-tree -r --name-only stash@{0}^3 <path-prefix>`
   - If needed, script the set comparison in Python to detect:
     - files only in HEAD
     - files only in stash
     - identical overlap count

6. Decide outcome.
   - If stash-only file count is zero and the path sets are identical, the stash is redundant and can be dropped.
   - If stash contains extra files, extract or restore them carefully to a safe location before dropping.

## Useful commands

```bash
git stash push -u -m 'hermes-temp-pre-rebase-2026-04-01'
git rebase origin/main
git stash list
git rev-parse stash@{0}
git rev-parse stash@{0}^3
git ls-tree -r --name-only HEAD docs/runs/2026-04-01
git ls-tree -r --name-only stash@{0}^3 docs/runs/2026-04-01
```

Python set diff example:

```bash
python - <<'PY'
import subprocess, json
head=set(subprocess.check_output([
    'git','ls-tree','-r','--name-only','HEAD','docs/runs/2026-04-01'
], text=True).splitlines())
stash=set(subprocess.check_output([
    'git','ls-tree','-r','--name-only','stash@{0}^3','docs/runs/2026-04-01'
], text=True).splitlines())
print(json.dumps({
  'head_count': len(head),
  'stash_count': len(stash),
  'only_in_head': sorted(head-stash),
  'only_in_stash': sorted(stash-head),
  'common_count': len(head & stash),
}, indent=2))
PY
```

## Pitfalls

- Using plain `git stash` instead of `git stash -u`
- Assuming `git stash show` alone is enough for untracked-file inspection
- Blindly running `git stash drop` without checking whether stash has unique files
- Mistaking `stash pop` failure for a failed rebase; they are separate events

## Success criteria

- Rebase completes successfully
- Local untracked artifacts are preserved during the operation
- Stash is either restored safely or proven redundant before removal
