---
name: centracast-openclaw-boundary-audit
description: Audit CentraCast backend/runtime boundaries honestly by sweeping OpenClaw API, dashboard routes, and state semantics before concluding gaps.
---

# CentraCast OpenClaw Boundary Audit

Use when:
- auditing `centracast` for runtime-facing capability gaps
- judging whether a Telegram/runtime lane already has backend authority
- comparing dashboard/web routes vs OpenClaw API vs callback truth
- deciding whether a missing capability is truly absent or just under-reported

## Why this exists

A partial backend audit can over-index on `web-studio` routes and under-account the OpenClaw API surface. That creates fake gaps and overconfident boundary conclusions.

## Goal

Before claiming a lane is missing, determine whether the capability already exists in one of these layers:
1. dashboard/web mutation route
2. OpenClaw agent-facing API route
3. persisted row state / callback truth
4. operator visibility/read surfaces

## Procedure

1. Verify target repo/workspace first.
   - Confirm you're in `centracast`, not `centracast-runtime`.
   - Check branch and dirty state.

2. Sweep both route families before writing any conclusion.
   - Inspect `routes/web-studio.php`
   - Inspect `routes/api.php`
   - For the target lane, list all matching routes from both files.

3. Sweep relevant controller semantics, not just route names.
   For each matched route, inspect:
   - controller method
   - validation / blocker logic
   - persisted state updates
   - dispatch/job behavior
   - response payload/message semantics

4. Sweep truth callbacks and row fields.
   - Inspect callback controllers that finalize success/failure.
   - Inspect model fields + migrations for state columns.
   - Record which fields are authoritative for final truth.

5. Sweep read surfaces separately from mutation surfaces.
   Ask explicitly:
   - is there a release-level read endpoint already?
   - can publish truth be derived from operator-status/run-snippet/content-analytics or similar?
   - is the real gap missing read model, missing endpoint, or missing runtime consumption?

6. Reconcile vocabulary across all layers.
   Build a table for:
   - mutation response terms (`queued`, `validated`, etc.)
   - persisted state terms (`uploading`, `published`, `failed`, etc.)
   - callback truth transitions
   - operator-visible summary terms

7. Only then classify the gap.
   Use one of these labels:
   - missing endpoint
   - missing canonical naming
   - missing compact read model
   - semantics drift across existing surfaces
   - runtime not consuming an existing backend surface

8. State audit scope honestly in the writeup.
   Say explicitly one of:
   - OpenClaw API fully swept for this lane
   - dashboard + partial OpenClaw only
   - provisional pending full OpenClaw release-surface audit

## CentraCast-specific checklist for publish/upload lanes

Always inspect at least:
- `routes/web-studio.php`
- `routes/api.php`
- `app/Http/Controllers/Dashboard/SingleReleaseController.php`
- `app/Http/Controllers/Api/Openclaw/ReleaseController.php`
- `app/Http/Controllers/Api/V1/Openclaw/OperatorVisibilityController.php`
- `app/Http/Controllers/ForemanUploadCallbackController.php`
- `app/Services/Inertia/ReleaseActionService.php`
- `app/Jobs/DispatchForemanUploadJob.php`
- `app/Models/SingleRelease.php`
- relevant migrations for YouTube fields

## Pitfalls

- Treating route existence as equivalent to a canonical business contract
- Claiming a gap before checking OpenClaw read surfaces
- Ignoring state-language drift between response payloads and persisted row states
- Saying “does not exist” when the real issue is “exists but not canonically projected”
- Writing architecture conclusions without stating audit completeness

## Success criteria

- both dashboard and OpenClaw surfaces are covered
- controller semantics, callbacks, and row truth are mapped
- state vocabulary drift is explicitly documented
- final conclusion says whether the audit was full or partial
- any claimed gap is classified precisely, not vaguely
