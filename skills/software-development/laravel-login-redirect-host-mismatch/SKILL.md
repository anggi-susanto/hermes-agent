---
name: laravel-login-redirect-host-mismatch
description: Investigate Laravel/Inertia login flows that redirect to the wrong host or port after authentication, especially behind reverse proxies or ingress.
tags: [laravel, login, redirect, proxy, host, ingress, staging]
---

# Laravel Login Redirect Host Mismatch

Use when:
- login succeeds but browser lands on the wrong domain or port
- examples: `staging.gunamaya.id:80` instead of `https://staging.centracast.id/...`
- internal menu links work after load, so the bug seems isolated to post-login redirect or intended URL handling

## Goal

Separate app-code redirect bugs from proxy / env / session-origin bugs.

## Fast triage logic

If the controller returns a relative redirect like:

```php
return redirect()->intended('/studio-new/' . $user->tenant->slug);
```

then a cross-host redirect is usually **not** caused by that line alone.

Primary suspects become:
1. `url.intended` stored in session as an absolute wrong-host URL
2. reverse proxy headers (`Host`, `X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Forwarded-Port`)
3. deploy-time env drift (`APP_URL`, session/cookie domain, ingress host rules)
4. framework URL forcing (`URL::forceRootUrl`, `URL::forceScheme`) interacting with bad upstream headers or stale config

## Investigation flow

1. Verify repo/workspace first.
   - `pwd`
   - `git branch --show-current`
   - `git remote -v | head`
   - `git status --short`

2. Inspect login controller and logout/login routes.
   - Look for `redirect()->intended(...)`, `redirect()->to(...)`, Fortify `LoginResponse`, custom auth controllers.
   - Also inspect panel/framework auth entrypoints, not just app controllers.
     - In Filament apps, check `PanelProvider` definitions for `->path(...)` and `->login()`.
     - Then search for a custom login page override (for example a class extending Filament's Login page). If none exists, the panel is likely still using the framework-default login flow.
   - For CentraCast, relevant path was:
     - `app/Http/Controllers/Dashboard/AuthController.php`

3. Inspect URL-forcing and proxy config.
   - Search for:
     - `URL::forceRootUrl`
     - `URL::forceScheme`
     - `trustProxies`
     - `APP_URL`
     - `SESSION_DOMAIN`
     - `SANCTUM_STATEFUL_DOMAINS`
   - For CentraCast, useful findings were:
     - `app/Providers/AppServiceProvider.php` forces scheme + root URL in `production`/`staging`
     - `bootstrap/app.php` already had `trustProxies(at: '*')`
     - repo env showed `APP_URL=https://staging.centracast.id`, `ASSET_URL=https://staging.centracast.id`, `SESSION_DOMAIN=null`

4. Look for hardcoded wrong hosts in code.
   - Search repo for the unexpected host, port, and related domains.
   - If absent, lean harder toward session/proxy/runtime drift rather than source code literals.

5. Treat relative redirect code as suspicious-but-not-conclusive.
   - If redirect target in code is relative but browser lands on an absolute wrong host, explicitly note that the likely culprit is upstream or session state.

6. Capture the decisive runtime evidence next.
   - Inspect the first response after POST login:
     - status
     - `Location`
     - `Set-Cookie`
   - Inspect request headers received by Laravel if possible:
     - `Host`
     - `X-Forwarded-Host`
     - `X-Forwarded-Proto`
     - `X-Forwarded-Port`
   - Check whether session key `url.intended` already contains the wrong absolute URL before auth completes.

## CentraCast-specific finding worth remembering

A live CentraCast staging case showed:
- user reported successful login always landing on `staging.gunamaya.id:80`
- menu links inside the app were fine afterward
- source inspection found login redirects were relative (`redirect()->intended('/studio-new/...')`)
- `AppServiceProvider` was forcing root URL from `config('app.url')`
- runtime config inside the app container still resolved correctly:
  - `app()->environment()` = `staging`
  - `config('app.url')` = `https://staging.centracast.id`
  - `route('dashboard.login')` = `https://staging.centracast.id/studio-new/login`
- no `staging.gunamaya.id` literal existed in repo search results
- later tracing showed CentraCast actually has two distinct auth surfaces:
  - `/studio-new/login` uses the custom `App\Http\Controllers\Dashboard\AuthController`
  - `/studio/login` comes from Filament `StudioPanelProvider` with `->path('studio')->login()` and no custom Filament Login page override was present
- therefore, a defensive patch added only to `Dashboard\AuthController` mitigates `/studio-new` but does **not** automatically protect `/studio`
- a practical CentraCast fix for `/studio` was to create a custom Filament login page (for example `App\Filament\Pages\Auth\Login` extending `Filament\Pages\Auth\Login`) and wire it in `StudioPanelProvider` via `->login(App\Filament\Pages\Auth\Login::class)` instead of the default `->login()`
- to avoid duplicated logic between `/studio-new` and `/studio`, extract the host-allowlist logic into a shared trait/helper (for example `App\Support\Auth\SanitizesIntendedRedirects`) and reuse it from both the dashboard controller and the custom Filament login page
- when testing Filament auth, route inspection (`php artisan route:list --path=studio`) is a quick way to confirm whether `/studio/login` is a framework panel auth surface rather than your app controller stack

A decisive local proof came from executing a tiny PHP script inside the Laravel app container using `Illuminate\Routing\Redirector` directly:
- if request host is good and `url.intended` is null, `redirect()->intended('/studio-new/...')` stays on `https://staging.centracast.id/...`
- if request host is bad, the generated location follows the bad host
- if request host is good but session `url.intended` already contains an absolute wrong-host URL like `http://staging.gunamaya.id:80/studio-new/mabes`, `redirect()->intended(...)` will redirect to that wrong host verbatim
- if session `url.intended` is only a relative path, Laravel normalizes it back onto the current good host

This combination strongly suggests the first redirect is being influenced by runtime session/proxy/origin state, not by a direct hardcoded redirect target in source.

## Reusable proof technique

When you need to prove whether Laravel is obeying a poisoned intended URL versus generating a bad host itself:

1. Inspect runtime values inside the app container:
   - `php artisan tinker --execute="echo json_encode(['env'=>app()->environment(),'app_url'=>config('app.url')]);"`
   - `php artisan tinker --execute="echo route('dashboard.login');"`
2. Create a tiny PHP script inside the container that:
   - boots Laravel
   - builds a synthetic `Request`
   - instantiates `UrlGenerator` + `Redirector`
   - injects a session containing either a relative or absolute `url.intended`
   - prints the resulting redirect target
3. Compare these cases explicitly:
   - good host + no intended
   - bad host + no intended
   - good host + bad absolute intended
   - good host + relative intended

If only the `bad absolute intended` case reproduces the exact wrong-host redirect, you have strong evidence that the app is honoring a poisoned session value rather than inventing the host in the login controller.

## GitHub issue template guidance

When you cannot fully prove the root cause yet, file the issue with:
- exact repro URL
- actual wrong redirect host/port
- expected host/path
- code paths inspected
- env/proxy findings
- explicit hypothesis buckets:
  - wrong `url.intended`
  - wrong forwarded headers
  - env drift
  - ingress canonical host mismatch

This keeps the issue grounded without pretending the cause is already proven.

## Defensive patch pattern

When the product needs an immediate mitigation before infra is fixed, patch the login success flow itself:

1. Wrap `redirect()->intended(...)` behind a helper such as `safeIntendedRedirect($request, $fallback)`.
2. Read `url.intended` from session before redirecting.
3. Treat these as safe and leave them alone:
   - empty / missing intended URL
   - relative paths beginning with `/`
   - absolute URLs whose host matches either:
     - `$request->getHost()`
     - `parse_url(config('app.url'), PHP_URL_HOST)`
4. If the intended URL is absolute and its host is outside that allowlist:
   - `forget('url.intended')`
   - then continue with `redirect()->intended($fallback)` so Laravel falls back to the known-good relative path
5. Add regression tests for:
   - poisoned absolute intended URL on wrong host -> falls back to safe relative path
   - relative intended URL -> preserved
   - same-host absolute intended URL -> preserved

6. For Filament / Livewire login surfaces, be careful with return types.
   - `redirect()->intended(...)` may return `Livewire\Features\SupportRedirects\Redirector`, not always `Illuminate\Http\RedirectResponse`
   - if you extract a helper like `safeIntendedRedirect()` and hard-type it to `RedirectResponse`, `/studio` can crash at runtime with:
     - `Return value must be of type Illuminate\Http\RedirectResponse, Livewire\Features\SupportRedirects\Redirector returned`
   - the same applies if you wrap the result in a custom `LoginResponse` implementation for Filament; the constructor property and `toResponse()` return type must also accept `RedirectResponse | Redirector`
   - practical CentraCast fix:
     - shared sanitizer trait imported both `Illuminate\Http\RedirectResponse` and `Livewire\Features\SupportRedirects\Redirector`
     - `safeIntendedRedirect(...): RedirectResponse | Redirector`
     - custom Filament login response wrapper stored and returned `RedirectResponse | Redirector`

This keeps the blast radius small: only cross-host absolute intended URLs get discarded, while the patched flow still matches Filament/Livewire's actual redirect object types.

## Success criteria

- distinguish app redirect code from upstream host/origin problems
- identify whether redirect target is relative or absolute at source
- explicitly map each user-facing login surface to its actual auth handler (custom controller vs framework/panel default)
- produce a focused issue or patch plan with concrete next checks
- if needed, implement a narrow defensive host allowlist around `url.intended` without breaking legitimate relative or same-host redirects
- add regression coverage for every affected login surface; do not assume a `/studio-new` test protects `/studio`
