---
name: generated-artifact-ignore-policy
description: Handle generated verification/artifact directories without polluting git status; prefer folder-level ignore rules and remember tracked-file caveats.
---

# Generated Artifact Ignore Policy

Use this when a repo produces local/live verification artifacts (for example under `docs/runs/...`) and the user wants a clean worktree.

## Trigger conditions

- `git status` shows lots of generated files under a repeatable artifact tree like `docs/runs/`, `tmp/`, `reports/`, or `coverage/`
- You are tempted to ignore specific files one by one (`*.json`, `final-summary.md`, sidecars, etc.)
- The user is clearly asking to stop the whole artifact bundle from dirtying the repo

## Core rule

Prefer ignoring the artifact directory pattern at the folder level, not patching `.gitignore` file-by-file.

Bad first instinct:
- ignore only `remote-analytics-richness-proof.json`
- ignore only `analytics-provider-sample.json`

Better default:
- ignore the whole generated run folder pattern, e.g.
  - `docs/runs/*/run-*/`
  - `docs/runs/*/????????-????-????-????-????????????/`

If the repo occasionally wants to keep a blessed fixture bundle, note that it can be force-added later with `git add -f`.

## Procedure

1. Inspect the dirt first.
   - Run `git status --short --branch`
   - Identify whether the noise is:
     - untracked generated files
     - tracked generated fixture files being rewritten
     - both

2. Choose the ignore scope based on user intent.
   - If the user wants local verification artifacts out of the repo entirely, ignore the folder pattern.
   - Only use per-file ignores when the repo intentionally tracks most of the folder and truly wants just a tiny sidecar exception.

3. Patch `.gitignore` at the directory-pattern level.
   - Add the broadest safe pattern that matches the generated artifact family.
   - Include a short comment explaining that future intentional fixtures can be force-added.

4. Verify ignore behavior explicitly.
   - Use `git check-ignore -v <path>` on representative files.
   - Confirm both named run folders and UUID-like folders if both exist.

5. Explain the tracked-file caveat immediately.
   - `.gitignore` does NOT hide modifications to files already tracked by git.
   - If tracked artifact files still appear dirty, say so clearly.

6. If the user wants a truly clean future state, propose the real cleanup.
   - `git rm --cached -r <artifact-path>` for tracked generated files/directories that should stop being versioned
   - commit the `.gitignore` change plus the index cleanup
   - push

## Decision heuristic

Ask yourself: is the user's actual complaint about one file type, or about the whole generated artifact workflow?

If it is about the workflow, ignore the folder.

## Good response shape

- acknowledge the better method quickly
- fix `.gitignore` at folder scope
- verify with `git check-ignore`
- tell the user if remaining dirt is caused by already-tracked files

## Pitfalls

- solving only the newest sidecar files instead of the artifact tree
- forgetting that tracked files ignore the ignore rules
- claiming the repo is clean after only changing `.gitignore`
- using a narrow pattern when the user obviously wants the whole run folder treated as disposable

## Example

For generated CentraCast run artifacts:

```gitignore
# Ignore generated verification run folders; force-add only if blessing a fixture.
docs/runs/*/????????-????-????-????-????????????/
docs/runs/*/run-*/
```

Then verify:

```bash
git check-ignore -v docs/runs/2026-04-01/run-orch-1/final-summary.md
git check-ignore -v docs/runs/2026-04-01/019d4abe-5438-7041-a2f0-d68ec63be712/manifest.json
```
