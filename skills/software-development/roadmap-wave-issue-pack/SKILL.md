---
name: roadmap-wave-issue-pack
description: Turn a completed strategy/master-brief doc set into an implementation wave pack plus concrete GitHub issues, with dependency order, acceptance proof, anti-bullshit notes, and epic linkage.
---

# Roadmap Wave Issue Pack

Use this when a repo already has planning/audit/master-brief docs, and the user wants the next step turned into real execution tickets instead of more prose.

Typical trigger phrases:
- "gas point 1"
- "bikin issue pack"
- "pecah jadi tiket"
- "Wave A/B/C"
- "issue-ready"
- "implementasi setelah audit/brief"

## Goal

Convert a finished strategic doc set into:
1. one issue-pack markdown file in the repo
2. a small set of concrete GitHub issues (usually waves/slices)
3. a linkage comment on the parent epic
4. clean commit/push state

## When to use

Best fit when:
- an audit/roadmap/master brief already exists
- the next work is known conceptually but not yet ticketed
- the user wants direct execution, not another discussion round
- you need to preserve proof standards and dependency order from the planning docs

## Procedure

1. Identify the canonical source docs
   Read only the minimum docs needed:
   - master brief / tracker
   - implementation plan / slimming plan / roadmap
   - guardrails / truth-rules doc
   - current epic issue on GitHub

2. Extract the real execution order
   Do not invent a new sequence if the docs already establish one.
   Usually capture:
   - wave/slice name
   - why it comes first
   - dependencies
   - likely touchpoints
   - acceptance proof
   - anti-bullshit / not-done conditions

3. Write one repo doc for the pack
   Recommended filename pattern:
   - `docs/*WAVE-IMPLEMENTATION-PACK.md`

   Recommended structure:
   - title/status/parent epic
   - purpose
   - dependency order
   - issue-ready slices (one section per wave)
   - suggested execution notes
   - success rule for the whole pack
   - source refs

4. Keep each issue slice copy-paste ready
   Each wave should include:
   - Problem
   - Objective
   - Scope
   - Likely touchpoints
   - Deliverables
   - Acceptance proof
   - Anti-bullshit notes
   - Source refs

5. Create GitHub issues immediately
   Use `gh issue create` with labels that already exist in the repo.
   Before creating issues, inspect available labels with `gh label list` and current epic state with `gh issue view <epic>`.
   Prefer a tight set of issues (e.g. Wave A/B/C), not a ticket explosion.

6. Link back to the epic
   Post one concise comment on the parent epic containing:
   - the new issue numbers
   - the pack doc path
   - recommended execution order
   - one-paragraph anti-bullshit summary

7. Commit and push the pack doc
   Use one focused commit message, e.g.:
   - `docs: add omb wave implementation pack`

## Important rules

- Do not create tickets from vibes; derive them from existing repo truth.
- Do not flatten dependency order just because the user said "gas"; keep the proven order unless the repo docs say otherwise.
- Do not mark backend-truth work as solved from runtime-side prose alone.
- Do not create labels ad hoc unless the repo clearly needs them; prefer existing labels.
- If the repo already has an epic, comment there instead of silently creating disconnected issues.
- Keep anti-bullshit sections in every issue so future execution does not overclaim completion.

## Good output characteristics

A good wave pack gives the team:
- one canonical doc to read
- one epic to follow
- a small numbered set of execution tickets
- explicit acceptance proof per wave
- explicit "not done if..." conditions

## Pitfalls

- Creating tickets before checking existing repo labels
- Writing issue bodies that are too vague to execute
- Forgetting to link the issues back to the epic
- Letting runtime-side docs pretend backend truth is already fixed
- Making Wave C sound as easy/safe as Wave A when it depends on backend authority changes

## Success criteria

- a new wave implementation pack doc exists in the repo
- GitHub issues are open for the intended waves
- the epic references the new issues
- dependency order is explicit
- worktree is clean after commit/push
