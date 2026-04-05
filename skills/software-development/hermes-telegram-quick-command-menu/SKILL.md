---
name: hermes-telegram-quick-command-menu
description: Expose Hermes gateway quick_commands in Telegram's slash-command menu so runtime shortcuts like /ccrun are discoverable, not just dispatchable.
---

# Hermes Telegram Quick Command Menu

Use this when:
- quick_commands already work in gateway dispatch, but Telegram users can't discover them from the `/` menu
- the user wants a Telegram channel/chat to run repo-specific wrappers like `/ccinspect`, `/ccblocker`, `/ccrun`
- you need to reconcile Hermes built-in slash commands with config-driven quick commands

## Core finding

Hermes gateway quick_commands are resolved at dispatch time in `gateway/run.py`, but Telegram command hints come from `setMyCommands()` in `gateway/platforms/telegram.py`, which only consumes `hermes_cli.commands.telegram_bot_commands()`.

That means a quick command can be executable but invisible in Telegram UI unless you explicitly mirror quick_commands into `telegram_bot_commands()`.

## Files to inspect

- `gateway/run.py`
- `gateway/platforms/telegram.py`
- `hermes_cli/commands.py`
- `gateway/config.py`
- `tests/hermes_cli/test_commands.py`

## Procedure

1. Verify the symptom before patching.
   - Confirm quick_commands exist in config:
     - load `GatewayConfig.quick_commands`
     - inspect entries like `ccinspect`, `ccblocker`, `ccrun`
   - Confirm dispatch path exists in `gateway/run.py`.
   - Confirm Telegram menu registration only uses built-ins via `telegram_bot_commands()` from `hermes_cli/commands.py`.
   - If a live gateway is already running, also verify runtime reality instead of trusting code alone:
     - inspect `~/.hermes/gateway_state.json` for `telegram: connected`
     - call Telegram Bot API `getMyCommands` with the configured bot token and verify the expected quick commands are actually published in the slash menu
     - inspect `~/.hermes/sessions/sessions.json` to identify the real Telegram DM session key/chat id if you want to run a realistic dispatch smoke

2. Patch the Telegram menu source, not the dispatch logic.
   - Add a helper in `hermes_cli/commands.py` that reads `load_gateway_config()` and converts `quick_commands` into Telegram menu entries.
   - Normalize names for Telegram:
     - strip leading `/`
     - replace `-` with `_`
   - Skip unsupported/non-exec entries unless the implementation is intentionally widened.
   - Deduplicate against built-in commands already present in `telegram_bot_commands()`.
   - Keep descriptions short enough for Telegram; if config has no description, use a safe fallback like `Run quick command`.

3. Keep profile-aware config loading.
   - In `hermes_cli/commands.py`, use `get_hermes_home() / "config.yaml"` instead of hardcoding `~/.hermes/config.yaml` or manual `os.getenv("HERMES_HOME", ...)` path assembly.
   - This matters because Hermes supports profile-specific homes.

4. Add regression tests.
   - In `tests/hermes_cli/test_commands.py`, add coverage for:
     - exec quick commands appearing in `telegram_bot_commands()`
     - hyphenated names normalizing to underscores
     - fallback description behavior when config omits a description
     - non-exec quick commands being excluded from Telegram menu exposure
   - In `tests/test_quick_commands.py`, keep/extend coverage for gateway dispatch itself:
     - `{args}` remains shell-quoted as one blob
     - `{args_raw}` remains raw/unquoted
     - exec quick commands return stdout and timeout handling still works

5. Verify with targeted tests.
   - Run:
     - `source venv/bin/activate && python -m pytest tests/hermes_cli/test_commands.py tests/test_quick_commands.py -q`
   - For a higher-confidence smoke on a live system, also do both:
     - direct wrapper check in `centracast-runtime` (for example `bash scripts/telegram/ccinspect.sh` and a real `ccrun` objective)
     - gateway-dispatch check by constructing a `GatewayRunner` + `MessageEvent` with a Telegram `SessionSource` and calling `_handle_message()` so you prove the Hermes quick-command path, not just the wrapper script

## Good mental model

- `gateway/run.py` = runtime dispatch truth
- `gateway/platforms/telegram.py` = publishes command menu to Telegram
- `hermes_cli/commands.py::telegram_bot_commands()` = actual source of Telegram menu entries

If Telegram discoverability is broken but execution works, the bug is usually in the menu publication path, not in quick-command execution.

## Pitfalls

- Don't waste time debugging `MessageEvent.get_command()` first if manual `/ccinspect` dispatch already works.
- Don't patch only `gateway/run.py`; that won't make Telegram show the commands.
- Don't hardcode `~/.hermes` paths in Hermes code.
- Don't forget deduping; config quick commands may collide with built-ins.

## Done when

- Telegram menu source includes config-driven quick commands
- commands like `/ccinspect`, `/ccblocker`, `/ccrun` appear in `telegram_bot_commands()`
- targeted tests pass
- profile-aware config access remains intact
