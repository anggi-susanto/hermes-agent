---
name: centracast-laravel-operator-run-contract
description: Patch CentraCast Laravel operator_runs API when runtime fields are missing from PATCH/GET due to schema-model-controller contract drift.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [centracast, laravel, api-contract, migrations, regression-tests, operator-runs]
    related_skills: [systematic-debugging, test-driven-development, centracast-runtime-staging]
---

# CentraCast Laravel Operator Run Contract Alignment

## When to use

Use this when the TypeScript runtime sends new `operator_runs` fields to the Laravel API, but those fields do not persist or do not appear on `GET /operator-runs/{id}`.

Typical symptoms:
- PATCH succeeds but fields disappear on read-back
- `result_snapshot` persists but newer fields like `step_progress`, `truth_verdict`, or `handoff_note` vanish
- Runtime and backend use different names for the same concept, e.g. `error_summary` vs `last_error_message`

## Root cause pattern

In this codebase, missing fields are usually caused by contract drift across three layers at once:

1. Database migration does not define the columns
2. `OperatorRunController@update()` does not validate/whitelist the fields
3. `OperatorRun` model does not cast JSON fields

`show()` returns `response()->json($run)`, so if a field is absent there, the problem is almost never a serializer/resource issue. It is usually schema or validation drift.

## Files to inspect

In `centracast/` inspect:
- `routes/api.php`
- `app/Http/Controllers/Api/V1/Openclaw/OperatorRunController.php`
- `app/Models/OperatorRun.php`
- `database/migrations/*operator_runs*.php`
- `tests/Feature/OperatorHardeningTest.php`
- optionally `tests/Feature/OperatorLoopTest.php`

## Fix procedure

### 1. Confirm route and read path

Verify `GET /api/v1/openclaw/operator-runs/{id}` points to `OperatorRunController@show`.

If `show()` does `return response()->json($run);`, then missing fields are not being filtered by a resource transformer.

### 2. Audit update validation

Open `OperatorRunController@update()` and compare runtime payload fields with the Laravel validation whitelist.

For runtime contract fields, add validations like:

```php
'step_progress' => 'sometimes|array|nullable',
'truth_verdict' => ['sometimes', 'nullable', Rule::in(['pass', 'fail', 'blocked'])],
'handoff_note' => 'sometimes|string|nullable',
'error_summary' => 'sometimes|string|nullable',
'started_at' => 'sometimes|date|nullable',
'completed_at' => 'sometimes|date|nullable',
```

Important: Laravel only returns validated keys from `$request->validate()`. If a field is missing from the validation array, it will be silently dropped before `$run->fill($validated)`.

### 3. Add backward-compat mapping for renamed fields

If the old backend field is `last_error_message` but runtime now sends `error_summary`, mirror them:

```php
if (array_key_exists('error_summary', $validated) && !array_key_exists('last_error_message', $validated)) {
    $validated['last_error_message'] = $validated['error_summary'];
}

if (array_key_exists('last_error_message', $validated) && !array_key_exists('error_summary', $validated)) {
    $validated['error_summary'] = $validated['last_error_message'];
}
```

Do this before `$run->fill($validated)`.

### 4. Patch the model casts

In `app/Models/OperatorRun.php`, add JSON casts for any structured fields:

```php
'step_progress' => 'array',
```

String/text fields usually need no cast.

### 5. Add a migration for missing columns

Create a new migration adding the missing runtime columns to `operator_runs`, e.g.:

```php
$table->json('step_progress')->nullable();
$table->string('truth_verdict')->nullable();
$table->text('handoff_note')->nullable();
$table->text('error_summary')->nullable();
```

Do not rewrite old migrations unless explicitly requested; add a new migration.

### 6. Add regression coverage

Add a feature test that:
- creates an `OperatorRun`
- PATCHes the new runtime fields
- asserts the PATCH response includes them
- GETs the run back via `/operator-runs/{id}`
- asserts the fields persisted and round-tripped
- verifies `error_summary` and `last_error_message` stay aligned
- verifies client-supplied `started_at` / `completed_at` are not discarded

A good home is `tests/Feature/OperatorHardeningTest.php`.

## Pitfalls

- `show()` returning a model does not guarantee new fields will appear; they must exist in schema and survive validation.
- If PHP is unavailable locally, you can still patch files safely, but you cannot run `php artisan migrate` or PHPUnit until on a Laravel-capable environment.
- Keep status transition logic intact. Add field support without weakening `isValidTransition()` checks.
- If client timestamps are allowed, preserve the existing fallback logic that auto-populates `started_at`/`completed_at` only when still null.

## Verification checklist

Run in `centracast/` when PHP is available:

```bash
php artisan migrate
php artisan test --filter=OperatorHardeningTest
php artisan test
```

Expected result:
- PATCH persists `step_progress`, `truth_verdict`, `handoff_note`, `error_summary`
- GET returns those fields
- `error_summary` and `last_error_message` remain mirrored for compatibility

## Notes specific to this workspace

In this CentraCast codebase, the runtime contract drift was fixed by editing:
- `app/Http/Controllers/Api/V1/Openclaw/OperatorRunController.php`
- `app/Models/OperatorRun.php`
- `tests/Feature/OperatorHardeningTest.php`
- a new migration adding runtime fields to `operator_runs`

This is the default playbook any time the TS runtime evolves faster than the Laravel staging API.
