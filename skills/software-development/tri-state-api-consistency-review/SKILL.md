---
name: tri-state-api-consistency-review
description: Audit tri-state or sentinel-return APIs for subtle semantic mismatches across call sites, docs, comments, and tests.
---

# Tri-state API Consistency Review

Use this skill when a function returns more than two meaningful states, especially:
- `True / False / None`
- `allow / block / ask`
- sentinel values with caller-specific meaning
- multiple callers interpreting the same return value differently

This is useful for finding bugs that are not obvious from runtime behavior alone but can still confuse maintainers or cause future regressions.

## Goal

Make sure the API’s meaning is consistent across:
- implementation
- call sites
- docstrings/comments
- logs/UI text
- tests

## Review workflow

1. **Find the contract**
   - Open the function definition and read the return type, docstring, and decision logic.
   - Identify every distinct state and what each one means.

2. **Search all call sites**
   - Look for direct unpacking of the function result.
   - Search for truthiness checks like `if not x`, `if x`, `elif x is None`, etc.
   - Search for related status strings such as `BLOCKED`, `ALLOWED`, `NEEDS CONFIRMATION`, `ask`.

3. **Compare semantics, not just syntax**
   - A call site may intentionally treat the same sentinel differently.
   - Verify whether that difference is documented and obvious.
   - Look for comments that overgeneralize one caller’s behavior to all callers.

4. **Check for subtle inconsistency types**
   - One caller treats `None` as “prompt user” while another uses it as “log warning, continue”.
   - Docs say a value means one thing, but code uses it differently in one branch.
   - Tests assert the raw return value but do not capture the user-facing meaning.
   - Log/status text suggests a stronger guarantee than the code actually provides.

5. **Prefer explicit branching**
   - Replace truthiness checks with explicit `is True`, `is False`, `is None` when tri-state is involved.
   - Avoid comments like “allow but...” if the value is actually only a local convention in one caller.

6. **Update the weakest link**
   - If the code is correct but comments are misleading, fix comments.
   - If tests don’t cover the semantic difference, add targeted tests.
   - If the API contract itself is ambiguous, update the docstring.

7. **Verify with focused tests**
   - Run the smallest relevant test set first.
   - Confirm both behavior and messaging remain aligned.

## Good signals of a real issue

- A value like `None` is used as a sentinel in multiple places but means different things depending on context.
- A comment says “this means confirm with the user” but another branch uses the same return value as “non-blocking warning”.
- Search results show explicit branch handling in one place and truthiness handling in another.

## What to change when you find one

- Make branching explicit.
- Rename comments to reflect caller-specific meaning.
- Adjust status strings to match actual behavior.
- Add or update tests for each semantic branch.

## Verification checklist

- [ ] Function contract is clear
- [ ] All call sites are reviewed
- [ ] Any caller-specific semantics are documented
- [ ] No truthiness traps remain
- [ ] Tests cover each state
- [ ] User-facing wording matches behavior
